"""ダッシュボードビュー – ゲートウェイ・PDCAサイクル状態の一覧・操作 UI。"""

from __future__ import annotations

from typing import Any

import flet as ft

from vibe_pdca.gui.components.pdca_card import PDCAStatusCard
from vibe_pdca.gui.components.status_card import CostCard, StatusCard


# --- ダッシュボードビュー: メイン画面のレイアウトと表示更新ロジック ---
class DashboardView(ft.Column):
    """メインダッシュボード画面。

    LLM ゲートウェイの状態表示・モード切替・ログ表示を行う。

    Parameters
    ----------
    on_mode_change : callable | None
        モード切替時のコールバック ``(mode_str) -> None``。
    """

    def __init__(
        self,
        on_mode_change: Any = None,
        **kwargs: Any,
    ) -> None:
        self._on_mode_change = on_mode_change

        # ── モード切替 ──
        self._mode_toggle = ft.Switch(
            label="ローカルLLM優先",
            value=False,
            on_change=self._handle_mode_toggle,
        )
        self._mode_label = ft.Text(
            "現在のモード: cloud",
            size=14,
            weight=ft.FontWeight.W_500,
        )

        # ── ステータスカード ──
        self._cloud_card = StatusCard(title="☁️ クラウドLLM")
        self._local_card = StatusCard(title="🖥️ ローカルLLM")
        self._cost_card = CostCard()
        self._pdca_card = PDCAStatusCard()

        # ── ログ表示 ──
        self._log_list = ft.ListView(
            expand=True,
            spacing=2,
            auto_scroll=True,
        )

        # ── レイアウト組み立て ──
        super().__init__(
            controls=[
                # ヘッダー
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SMART_TOY, size=28, color=ft.Colors.BLUE),
                            ft.Text(
                                "Vibe PDCA システム",
                                size=22,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Container(expand=True),
                            self._mode_label,
                            self._mode_toggle,
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                ),
                ft.Divider(height=1),
                # カード群（上段: LLM状態）
                ft.ResponsiveRow(
                    controls=[
                        ft.Container(
                            content=self._cloud_card,
                            col={"sm": 12, "md": 4},
                        ),
                        ft.Container(
                            content=self._local_card,
                            col={"sm": 12, "md": 4},
                        ),
                        ft.Container(
                            content=self._cost_card,
                            col={"sm": 12, "md": 4},
                        ),
                    ],
                ),
                # カード群（下段: PDCA状態）
                ft.ResponsiveRow(
                    controls=[
                        ft.Container(
                            content=self._pdca_card,
                            col={"sm": 12, "md": 6},
                        ),
                    ],
                ),
                # ログ領域
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "📋 ログ",
                                weight=ft.FontWeight.BOLD,
                                size=16,
                            ),
                            ft.Container(
                                content=self._log_list,
                                border=ft.Border.all(1, ft.Colors.GREY_300),
                                border_radius=8,
                                height=200,
                                padding=8,
                            ),
                        ],
                        spacing=8,
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                    expand=True,
                ),
            ],
            spacing=8,
            expand=True,
            **kwargs,
        )

    # ── 公開メソッド ──

    def update_status(self, status: dict[str, Any]) -> None:
        """ゲートウェイの全ステータスを更新する。

        Parameters
        ----------
        status : dict
            ``LLMGateway.get_status()`` の戻り値。
        """
        mode = status.get("preferred_mode", "cloud")
        is_local = mode == "local"
        self._mode_toggle.value = is_local
        self._mode_label.value = f"現在のモード: {mode}"

        self._cloud_card.update_items(status.get("cloud_providers", {}))
        self._local_card.update_items(status.get("local_providers", {}))

        cost = status.get("cost", {})
        self._cost_card.update_cost(cost, cost)

    def update_pdca_status(self, pdca_status: dict[str, Any]) -> None:
        """PDCAサイクルの状態を更新する。

        Parameters
        ----------
        pdca_status : dict
            ``PDCAStateMachine.get_status()`` の戻り値。
        """
        self._pdca_card.update_pdca_status(pdca_status)

    def add_log(self, message: str, level: str = "INFO") -> None:
        """ログメッセージを追加する。"""
        colors = {
            "ERROR": ft.Colors.RED,
            "WARNING": ft.Colors.ORANGE,
            "INFO": ft.Colors.BLACK,
            "DEBUG": ft.Colors.GREY,
        }
        self._log_list.controls.append(
            ft.Text(
                f"[{level}] {message}",
                size=12,
                color=colors.get(level, ft.Colors.BLACK),
            )
        )

    # ── イベントハンドラ ──

    def _handle_mode_toggle(self, e: ft.ControlEvent) -> None:
        """モード切替トグルのハンドラ。"""
        new_mode = "local" if e.control.value else "cloud"
        self._mode_label.value = f"現在のモード: {new_mode}"
        if self._on_mode_change:
            self._on_mode_change(new_mode)
        try:
            if self.page:
                self.page.update()
        except RuntimeError:
            pass
