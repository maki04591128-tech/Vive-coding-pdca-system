"""アラートパネル – レベル別フィルタ付きのアラート通知表示コンポーネント。"""

from __future__ import annotations

import time
from typing import Any

import flet as ft

from vibe_pdca.gui.dashboard import AlertItem


# --- アラートパネル: レベル別フィルタ付きのアラート通知を表示するウィジェット ---
class AlertPanel(ft.Card):
    """アラート通知パネルウィジェット。

    レベル（info/warning/error/critical）別にフィルタリングして
    アラートを表示する。
    """

    _LEVEL_STYLES: dict[str, tuple[str, str, str]] = {
        "info": ("ℹ️", ft.Colors.BLUE, ft.Colors.BLUE_50),
        "warning": ("⚠️", ft.Colors.ORANGE, ft.Colors.ORANGE_50),
        "error": ("❌", ft.Colors.RED, ft.Colors.RED_50),
        "critical": ("🚨", ft.Colors.RED_900, ft.Colors.RED_100),
    }

    def __init__(self, **kwargs: Any) -> None:
        self._alerts: list[AlertItem] = []
        self._current_filter: str | None = None
        self._alerts_column = ft.Column(spacing=4)
        self._filter_row = ft.Row(
            controls=[
                ft.TextButton("全て", on_click=lambda _: self._set_filter(None)),
                ft.TextButton(
                    "⚠️ 警告", on_click=lambda _: self._set_filter("warning")
                ),
                ft.TextButton(
                    "❌ エラー", on_click=lambda _: self._set_filter("error")
                ),
                ft.TextButton(
                    "🚨 重大", on_click=lambda _: self._set_filter("critical")
                ),
            ],
            spacing=4,
        )
        self._count_text = ft.Text("0件", size=12, color=ft.Colors.GREY_600)

        super().__init__(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(
                                    "🔔 アラート",
                                    weight=ft.FontWeight.BOLD,
                                    size=16,
                                ),
                                ft.Container(expand=True),
                                self._count_text,
                            ],
                        ),
                        ft.Divider(height=1),
                        self._filter_row,
                        ft.Container(
                            content=self._alerts_column,
                            height=200,
                        ),
                    ],
                    spacing=8,
                ),
                padding=16,
            ),
            **kwargs,
        )

    def update_alerts(self, alerts: list[AlertItem]) -> None:
        """アラートリストを更新する。

        Parameters
        ----------
        alerts : list[AlertItem]
            アラート項目のリスト。
        """
        self._alerts = list(alerts)
        self._render_alerts()

    def add_alert(self, alert: AlertItem) -> None:
        """アラートを追加する。"""
        self._alerts.append(alert)
        self._render_alerts()

    def _set_filter(self, level: str | None) -> None:
        """フィルタレベルを設定して再描画する。"""
        self._current_filter = level
        self._render_alerts()

    def _render_alerts(self) -> None:
        """現在のフィルタに基づいてアラートを描画する。"""
        self._alerts_column.controls.clear()
        filtered = self._alerts
        if self._current_filter:
            filtered = [a for a in self._alerts if a.level == self._current_filter]

        self._count_text.value = f"{len(filtered)}件"

        if not filtered:
            self._alerts_column.controls.append(
                ft.Text("アラートなし", size=12, color=ft.Colors.GREY)
            )
            return

        for alert in reversed(filtered[-50:]):
            self._alerts_column.controls.append(self._build_alert_row(alert))

    def _build_alert_row(self, alert: AlertItem) -> ft.Container:
        """アラート1件分の行を生成する。"""
        icon, color, bgcolor = self._LEVEL_STYLES.get(
            alert.level, ("❓", ft.Colors.GREY, ft.Colors.GREY_100)
        )
        ts = time.strftime("%H:%M:%S", time.localtime(alert.timestamp))
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(icon, size=14),
                    ft.Text(ts, size=10, color=ft.Colors.GREY_600),
                    ft.Text(
                        alert.message,
                        size=12,
                        color=color,
                        expand=True,
                    ),
                    ft.Text(
                        alert.category,
                        size=10,
                        color=ft.Colors.GREY_400,
                    ),
                ],
                spacing=4,
            ),
            bgcolor=bgcolor,
            border_radius=4,
            padding=ft.Padding(left=8, right=8, top=4, bottom=4),
        )
