#!/bin/bash
# ============================================================
# OpenClaw Hourly Health Report
# 実行間隔: 1時間ごと（cron: 0 * * * *）
# 概要: サーバーの総合ヘルスレポートを生成し、
#        Discord hw-status チャンネルへ送信する
# ============================================================

set -euo pipefail

# --- 環境変数からの設定読み込み ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "${SCRIPT_DIR}/.env" ]; then
    # shellcheck source=/dev/null
    . "${SCRIPT_DIR}/.env"
fi

DISCORD_WEBHOOK_STATUS="${OPENCLAW_DISCORD_WEBHOOK_STATUS:-}"
VLLM_HEALTH_URL="${OPENCLAW_VLLM_HEALTH_URL:-http://localhost:8000/health}"

TIMESTAMP="$(date '+%Y-%m-%d %H:%M %Z')"
NEXT_HOUR="$(date -d '+1 hour' '+%H:%M %Z' 2>/dev/null || date -v+1H '+%H:%M %Z' 2>/dev/null || echo '次の正時')"

# --- 関数定義 ---

send_discord() {
    local webhook_url="$1"
    local message="$2"

    if [ -z "$webhook_url" ]; then
        echo "[${TIMESTAMP}] WARNING: Discord Webhook URL (STATUS) が未設定です" >&2
        return 1
    fi

    curl -s -o /dev/null -w "%{http_code}" \
        -H "Content-Type: application/json" \
        -d "{\"content\": \"${message}\"}" \
        "$webhook_url"
}

# --- 情報収集 ---

get_uptime_info() {
    uptime -p 2>/dev/null || uptime | awk -F'up ' '{print $2}' | awk -F',' '{print $1}'
}

get_load_average() {
    uptime | awk -F'load average: ' '{print $2}'
}

get_gpu_info() {
    if ! command -v nvidia-smi &>/dev/null; then
        echo "  GPU: 非搭載（nvidia-smi 未検出）"
        return 0
    fi

    local gpu_index=0
    while IFS=',' read -r name temp vram_used vram_total utilization; do
        name=$(echo "$name" | xargs)
        temp=$(echo "$temp" | xargs)
        vram_used=$(echo "$vram_used" | xargs)
        vram_total=$(echo "$vram_total" | xargs)
        utilization=$(echo "$utilization" | xargs)

        local vram_pct=""
        if [ -n "$vram_used" ] && [ -n "$vram_total" ] && [ "$vram_total" != "0" ]; then
            vram_pct="$(( vram_used * 100 / vram_total ))%"
        fi

        local status_icon="✅"
        if [ -n "$temp" ] && [ "$temp" -ge 85 ] 2>/dev/null; then
            status_icon="⚠️"
        fi
        if [ -n "$temp" ] && [ "$temp" -ge 95 ] 2>/dev/null; then
            status_icon="🔴"
        fi

        echo "  GPU${gpu_index} (${name}): ${temp}℃ / VRAM ${vram_used}MiB/${vram_total}MiB (${vram_pct}) / 使用率 ${utilization}% ${status_icon}"
        gpu_index=$((gpu_index + 1))
    done < <(nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>/dev/null)
}

get_memory_info() {
    local mem_info
    mem_info=$(free -h | awk '/^Mem:/ {printf "%s / %s (%s 使用中)", $3, $2, $3}')
    local swap_info
    swap_info=$(free -h | awk '/^Swap:/ {printf "%s / %s", $3, $2}')
    echo "  メモリ: ${mem_info}"
    echo "  スワップ: ${swap_info}"
}

get_disk_info() {
    while IFS= read -r line; do
        local filesystem usage_pct mount_point size used
        filesystem=$(echo "$line" | awk '{print $1}')
        size=$(echo "$line" | awk '{print $2}')
        used=$(echo "$line" | awk '{print $3}')
        usage_pct=$(echo "$line" | awk '{print $5}' | tr -d '%')
        mount_point=$(echo "$line" | awk '{print $6}')

        case "$filesystem" in
            tmpfs|devtmpfs|overlay) continue ;;
        esac

        local status_icon="✅"
        if [ "$usage_pct" -ge 80 ] 2>/dev/null; then
            status_icon="⚠️"
        fi
        if [ "$usage_pct" -ge 90 ] 2>/dev/null; then
            status_icon="🔴"
        fi

        echo "  ${mount_point}: ${used} / ${size} (${usage_pct}%) ${status_icon}"
    done < <(df -h -P | tail -n +2)
}

get_vllm_status() {
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        --connect-timeout 5 \
        "$VLLM_HEALTH_URL" 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        echo "  vLLM (${VLLM_HEALTH_URL}): 応答あり ✅"
    else
        echo "  vLLM (${VLLM_HEALTH_URL}): 応答なし (HTTP ${http_code}) 🔴"
    fi
}

get_docker_status() {
    if docker info &>/dev/null 2>&1; then
        echo "  Docker: 稼働中 ✅"
    else
        echo "  Docker: 未検出または停止中 ⚠️"
    fi
}

get_network_status() {
    if command -v ip &>/dev/null; then
        local nic_info
        nic_info=$(ip -br link show | grep -v lo | head -3)
        while IFS= read -r line; do
            local nic_name nic_state
            nic_name=$(echo "$line" | awk '{print $1}')
            nic_state=$(echo "$line" | awk '{print $2}')
            if [ "$nic_state" = "UP" ]; then
                echo "  ${nic_name}: ${nic_state} ✅"
            else
                echo "  ${nic_name}: ${nic_state} ⚠️"
            fi
        done <<< "$nic_info"
    fi
}

# --- レポート生成 ---

generate_report() {
    local report=""
    report+="📊 **【OpenClaw 定時ヘルスレポート】${TIMESTAMP}**\\n\\n"

    report+="🖥️ **サーバー基本情報**\\n"
    report+="  稼働時間: $(get_uptime_info)\\n"
    report+="  負荷平均: $(get_load_average)\\n\\n"

    report+="🎮 **GPU状態**\\n"
    report+="$(get_gpu_info)\\n\\n"

    report+="💾 **メモリ**\\n"
    report+="$(get_memory_info)\\n\\n"

    report+="📁 **ストレージ**\\n"
    report+="$(get_disk_info)\\n\\n"

    report+="🔌 **ネットワーク**\\n"
    report+="$(get_network_status)\\n\\n"

    report+="🤖 **プロセス確認**\\n"
    report+="$(get_vllm_status)\\n"
    report+="$(get_docker_status)\\n\\n"

    report+="次回レポート: ${NEXT_HOUR}"

    echo "$report"
}

# --- メイン処理 ---

echo "=== OpenClaw Health Report: ${TIMESTAMP} ==="

REPORT=$(generate_report)

# コンソール出力（ログ用）
echo -e "$REPORT"

# Discord 送信
send_discord "$DISCORD_WEBHOOK_STATUS" "$REPORT"

echo "=== 完了 ==="
