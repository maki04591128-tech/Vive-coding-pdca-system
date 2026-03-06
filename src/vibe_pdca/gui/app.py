"""Flet GUI アプリケーション – メインエントリポイント。

以下のコマンドで起動可能:
  python -m vibe_pdca           # モジュール実行
  vibe-pdca                     # pip install 後のスクリプト

ビルド:
  flet pack src/vibe_pdca/gui/app.py --name VibePDCA   # → .exe
  flet build apk                                        # → .apk
"""

from __future__ import annotations

import logging
from typing import Any

import flet as ft

from vibe_pdca.gui.views.dashboard import DashboardView
from vibe_pdca.llm.models import ProviderType

logger = logging.getLogger(__name__)

# アプリケーションのバージョン（pyproject.toml と同期）
APP_VERSION = "0.1.0"


# LLMゲートウェイ（AIサービスへの接続窓口）を設定ファイルから構築
def _build_gateway() -> Any:
    """設定ファイルから LLMGateway を構築する。失敗時は None。"""
    try:
        from vibe_pdca.config.loader import build_gateway_from_config, load_config

        config = load_config()
        return build_gateway_from_config(config)
    except Exception as e:
        logger.warning("ゲートウェイ初期化スキップ（設定ファイル不在等）: %s", e)
        return None


# --- アプリケーション起動: Fletフレームワークでダッシュボード画面を構築する ---
def create_app(page: ft.Page) -> None:
    """Flet アプリケーションを構成する。

    Parameters
    ----------
    page : ft.Page
        Flet のページオブジェクト。
    """
    # ── ページ設定 ──
    page.title = "Vibe PDCA システム"
    page.window.width = 960
    page.window.height = 700
    page.window.min_width = 480
    page.window.min_height = 600
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    # ── ゲートウェイ初期化 ──
    gateway = _build_gateway()

    # ── モード切替コールバック ──
    def on_mode_change(mode_str: str) -> None:
        if gateway is None:
            dashboard.add_log("ゲートウェイ未初期化 — モード切替スキップ", "WARNING")
            page.update()
            return
        mode = ProviderType.CLOUD if mode_str == "cloud" else ProviderType.LOCAL
        gateway.set_mode(mode, reason="GUI から手動切替")
        dashboard.add_log(f"モード切替: {mode_str}", "INFO")
        dashboard.update_status(gateway.get_status())
        page.update()

    # ── ダッシュボード ──
    dashboard = DashboardView(on_mode_change=on_mode_change)

    # 初期ステータス反映
    if gateway:
        dashboard.update_status(gateway.get_status())
        dashboard.add_log("ゲートウェイ初期化完了", "INFO")
    else:
        dashboard.add_log("ゲートウェイ未初期化（デモモードで表示中）", "WARNING")
        # デモ用ステータス
        dashboard.update_status({
            "preferred_mode": "local",
            "auto_fallback_enabled": True,
            "cloud_providers": {
                "openai-gpt5.1": {
                    "circuit_state": "closed",
                    "consecutive_failures": 0,
                    "total_fallbacks": 0,
                },
            },
            "local_providers": {
                "ollama-pm": {
                    "model": "qwen3:72b",
                    "base_url": "http://localhost:11434/v1",
                    "status": "unknown",
                },
                "ollama-programmer": {
                    "model": "codestral:22b",
                    "base_url": "http://localhost:11434/v1",
                    "status": "unknown",
                },
            },
            "cost": {
                "daily_cost_usd": 0.0,
                "cycle_cost_usd": 0.0,
                "daily_calls": 0,
                "cycle_calls": 0,
            },
        })

    page.add(dashboard)


def main() -> None:
    """アプリケーションを起動する。"""
    ft.app(target=create_app)


if __name__ == "__main__":
    main()
