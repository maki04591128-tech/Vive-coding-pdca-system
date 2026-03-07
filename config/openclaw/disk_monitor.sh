#!/bin/bash
# ============================================================
# OpenClaw Disk Space Monitor
# 実行間隔: 15分ごと（cron: */15 * * * *）
# 概要: ディスク使用率を監視し、閾値超過時にDiscordへ通知する
#        緊急時は古いvLLMログを自動アーカイブする
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

DISK_WARN="${OPENCLAW_DISK_WARN:-80}"
DISK_CRITICAL="${OPENCLAW_DISK_CRITICAL:-90}"

LOG_ARCHIVE_DIR="${OPENCLAW_LOG_ARCHIVE_DIR:-/backup/logs}"
VLLM_LOG_DIR="${OPENCLAW_VLLM_LOG_DIR:-/var/log/vllm}"
LOG_RETENTION_DAYS="${OPENCLAW_LOG_RETENTION_DAYS:-7}"

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

# --- ディスク使用率チェック ---

check_disk_usage() {
    while IFS= read -r line; do
        local mount_point usage_pct filesystem
        filesystem=$(echo "$line" | awk '{print $1}')
        usage_pct=$(echo "$line" | awk '{print $5}' | tr -d '%')
        mount_point=$(echo "$line" | awk '{print $6}')

        # tmpfs などの仮想ファイルシステムはスキップ
        case "$filesystem" in
            tmpfs|devtmpfs|overlay) continue ;;
        esac

        if [ "$usage_pct" -ge "$DISK_CRITICAL" ]; then
            local msg="🚨 **[OpenClaw] ディスク容量緊急警告** (${TIMESTAMP})\nマウント: ${mount_point}\n使用率: **${usage_pct}%** （緊急閾値: ${DISK_CRITICAL}%）\n古いログの自動アーカイブを実行します。"
            send_discord "$DISCORD_WEBHOOK_CRITICAL" "$msg"
            echo "[${TIMESTAMP}] CRITICAL: ${mount_point} = ${usage_pct}% (>= ${DISK_CRITICAL}%)"

            # 自動修復: 古い vLLM ログをアーカイブ
            auto_archive_old_logs

        elif [ "$usage_pct" -ge "$DISK_WARN" ]; then
            local msg="⚠️ **[OpenClaw] ディスク容量警告** (${TIMESTAMP})\nマウント: ${mount_point}\n使用率: **${usage_pct}%** （警告閾値: ${DISK_WARN}%）\n24時間以内に容量対策を確認してください。"
            send_discord "$DISCORD_WEBHOOK" "$msg"
            echo "[${TIMESTAMP}] WARNING: ${mount_point} = ${usage_pct}% (>= ${DISK_WARN}%)"

        else
            echo "[${TIMESTAMP}] OK: ${mount_point} = ${usage_pct}%"
        fi
    done < <(df -P | tail -n +2)
}

# --- 古いログの自動アーカイブ ---

auto_archive_old_logs() {
    if [ ! -d "$VLLM_LOG_DIR" ]; then
        echo "[${TIMESTAMP}] INFO: vLLM ログディレクトリが存在しません: ${VLLM_LOG_DIR}"
        return 0
    fi

    mkdir -p "$LOG_ARCHIVE_DIR"

    local archived_count=0
    while IFS= read -r -d '' logfile; do
        mv "$logfile" "$LOG_ARCHIVE_DIR/" 2>/dev/null && archived_count=$((archived_count + 1))
    done < <(find "$VLLM_LOG_DIR" -name '*.log.*' -mtime +"$LOG_RETENTION_DAYS" -print0 2>/dev/null)

    if [ "$archived_count" -gt 0 ]; then
        local msg="ℹ️ **[OpenClaw] ログ自動アーカイブ完了** (${TIMESTAMP})\n${archived_count} 件の古いログを ${LOG_ARCHIVE_DIR} へ移動しました。"
        send_discord "$DISCORD_WEBHOOK" "$msg"
        echo "[${TIMESTAMP}] INFO: ${archived_count} 件のログをアーカイブしました"
    fi
}

# --- メイン処理 ---

echo "=== OpenClaw Disk Monitor: ${TIMESTAMP} ==="
check_disk_usage
echo "=== 完了 ==="
