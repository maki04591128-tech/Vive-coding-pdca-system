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
from vibe_pdca.gui.views.goal_input import GoalInputView
from vibe_pdca.gui.views.intervention_view import InterventionView
from vibe_pdca.gui.views.mode_settings import ModeSettingsView
from vibe_pdca.gui.views.progress_view import ProgressView
from vibe_pdca.llm.models import ProviderType

logger = logging.getLogger(__name__)

# アプリケーションのバージョン（pyproject.toml と同期）
APP_VERSION = "0.2.0"

# ── ナビゲーション定義 ──
_NAV_ITEMS = [
    {"icon": ft.Icons.DASHBOARD, "label": "ダッシュボード"},
    {"icon": ft.Icons.FLAG, "label": "ゴール入力"},
    {"icon": ft.Icons.TRENDING_UP, "label": "進捗閲覧"},
    {"icon": ft.Icons.SETTINGS, "label": "モード設定"},
    {"icon": ft.Icons.PAN_TOOL, "label": "介入操作"},
]


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

    # ── ビュー生成 ──
    def navigate_to(index: int) -> None:
        """指定インデックスのビューに切替える。"""
        nav_rail.selected_index = index
        content_area.content = views[index]
        page.update()

    def on_nav_change(e: ft.ControlEvent) -> None:
        """ナビゲーション選択変更のハンドラ。"""
        navigate_to(int(e.control.selected_index))

    dashboard = DashboardView(on_mode_change=on_mode_change)
    goal_input = GoalInputView(
        on_submit=lambda goal: dashboard.add_log(f"ゴール設定: {goal[:50]}...", "INFO"),
        on_back=lambda: navigate_to(0),
    )
    progress = ProgressView(on_back=lambda: navigate_to(0))
    mode_settings = ModeSettingsView(
        on_mode_change=lambda m: dashboard.add_log(f"運転モード変更: {m}", "INFO"),
        on_back=lambda: navigate_to(0),
    )
    intervention = InterventionView(
        on_stop=lambda: dashboard.add_log("PDCAサイクル停止", "WARNING"),
        on_back=lambda: navigate_to(0),
    )

    views: list[ft.Control] = [dashboard, goal_input, progress, mode_settings, intervention]

    # ── ナビゲーションレール ──
    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=200,
        destinations=[
            ft.NavigationRailDestination(
                icon=item["icon"],
                label=item["label"],
            )
            for item in _NAV_ITEMS
        ],
        on_change=on_nav_change,
    )

    content_area = ft.Container(
        content=dashboard,
        expand=True,
    )

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

    # ── レイアウト ──
    page.add(
        ft.Row(
            controls=[
                nav_rail,
                ft.VerticalDivider(width=1),
                content_area,
            ],
            expand=True,
        )
    )


def main() -> None:
    """アプリケーションを起動する。"""
    ft.app(target=create_app)


if __name__ == "__main__":
    main()
