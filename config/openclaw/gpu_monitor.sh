#!/bin/bash
# ============================================================
# OpenClaw GPU Temperature Monitor
# 実行間隔: 5分ごと（cron: */5 * * * *）
# 概要: GPU温度を監視し、閾値超過時にDiscordへ通知する
# ============================================================

set -euo pipefail

# --- 環境変数からの設定読み込み ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "${SCRIPT_DIR}/.env" ]; then
    # shellcheck source=/dev/null
    . "${SCRIPT_DIR}/.env"
fi

DISCORD_WEBHOOK="${OPENCLAW_DISCORD_WEBHOOK:-}"
DISCORD_WEBHOOK_CRITICAL="${OPENCLAW_DISCORD_WEBHOOK_CRITICAL:-$DISCORD_WEBHOOK}"

GPU_TEMP_WARN="${OPENCLAW_GPU_TEMP_WARN:-85}"
GPU_TEMP_CRITICAL="${OPENCLAW_GPU_TEMP_CRITICAL:-95}"

VLLM_HEALTH_URL="${OPENCLAW_VLLM_HEALTH_URL:-http://localhost:8000/health}"
VLLM_HEALTH_TIMEOUT="${OPENCLAW_VLLM_HEALTH_TIMEOUT:-5}"

TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S %Z')"

# --- 関数定義 ---

send_discord() {
    local webhook_url="$1"
    local message="$2"

    if [ -z "$webhook_url" ]; then
        echo "[${TIMESTAMP}] WARNING: Discord Webhook URL が未設定です" >&2
        return 1
    fi

    curl -s -o /dev/null -w "%{http_code}" \
        -H "Content-Type: application/json" \
        -d "{\"content\": \"${message}\"}" \
        "$webhook_url"
}

# --- GPU 温度チェック ---

check_gpu_temperature() {
    if ! command -v nvidia-smi &>/dev/null; then
        echo "[${TIMESTAMP}] INFO: nvidia-smi が見つかりません（GPU 非搭載環境）"
        return 0
    fi

    local gpu_index=0
    while IFS= read -r gpu_temp; do
        if [ -z "$gpu_temp" ]; then
            continue
        fi

        if [ "$gpu_temp" -ge "$GPU_TEMP_CRITICAL" ]; then
            local msg="🚨 **[OpenClaw] GPU${gpu_index} 温度緊急警告** (${TIMESTAMP})\nGPU${gpu_index}: **${gpu_temp}℃** （緊急閾値: ${GPU_TEMP_CRITICAL}℃）\n即座の冷却対応が必要です。"
            send_discord "$DISCORD_WEBHOOK_CRITICAL" "$msg"
            echo "[${TIMESTAMP}] CRITICAL: GPU${gpu_index} = ${gpu_temp}℃ (>= ${GPU_TEMP_CRITICAL}℃)"

        elif [ "$gpu_temp" -ge "$GPU_TEMP_WARN" ]; then
            local msg="⚠️ **[OpenClaw] GPU${gpu_index} 温度警告** (${TIMESTAMP})\nGPU${gpu_index}: **${gpu_temp}℃** （警告閾値: ${GPU_TEMP_WARN}℃）\n24時間以内に冷却状況を確認してください。"
            send_discord "$DISCORD_WEBHOOK" "$msg"
            echo "[${TIMESTAMP}] WARNING: GPU${gpu_index} = ${gpu_temp}℃ (>= ${GPU_TEMP_WARN}℃)"

        else
            echo "[${TIMESTAMP}] OK: GPU${gpu_index} = ${gpu_temp}℃"
        fi

        gpu_index=$((gpu_index + 1))
    done < <(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null)
}

# --- vLLM ヘルスチェック ---

check_vllm_health() {
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        --connect-timeout "$VLLM_HEALTH_TIMEOUT" \
        "$VLLM_HEALTH_URL" 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        echo "[${TIMESTAMP}] OK: vLLM ヘルスチェック正常 (HTTP ${http_code})"
    else
        local msg="🚨 **[OpenClaw] vLLM ヘルスチェック失敗** (${TIMESTAMP})\nURL: ${VLLM_HEALTH_URL}\nHTTP ステータス: ${http_code}\nvLLM プロセスの確認が必要です。"
        send_discord "$DISCORD_WEBHOOK_CRITICAL" "$msg"
        echo "[${TIMESTAMP}] CRITICAL: vLLM ヘルスチェック失敗 (HTTP ${http_code})"
    fi
}

# --- メイン処理 ---

echo "=== OpenClaw GPU Monitor: ${TIMESTAMP} ==="
check_gpu_temperature
check_vllm_health
echo "=== 完了 ==="
