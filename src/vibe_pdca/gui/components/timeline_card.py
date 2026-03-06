"""タイムラインカード – PDCAサイクルのフェーズ進行を時系列で表示するコンポーネント。"""

from __future__ import annotations

import time
from typing import Any

import flet as ft

from vibe_pdca.gui.dashboard import TimelineEntry


# --- タイムラインカード: PDCAフェーズの進行をガントチャート風に表示するウィジェット ---
class TimelineCard(ft.Card):
    """PDCAサイクルのタイムライン表示カード。

    Parameters
    ----------
    title : str
        カードのタイトル。
    """

    _PHASE_COLORS: dict[str, str] = {
        "plan": ft.Colors.BLUE,
        "do": ft.Colors.GREEN,
        "check": ft.Colors.ORANGE,
        "act": ft.Colors.PURPLE,
    }

    _PHASE_ICONS: dict[str, str] = {
        "plan": "📋",
        "do": "🔧",
        "check": "🔍",
        "act": "✅",
    }

    def __init__(self, **kwargs: Any) -> None:
        self._entries_column = ft.Column(spacing=4)
        super().__init__(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "📅 PDCAタイムライン",
                            weight=ft.FontWeight.BOLD,
                            size=16,
                        ),
                        ft.Divider(height=1),
                        self._entries_column,
                    ],
                    spacing=8,
                ),
                padding=16,
            ),
            **kwargs,
        )

    def update_timeline(self, entries: list[TimelineEntry]) -> None:
        """タイムラインエントリを更新する。

        Parameters
        ----------
        entries : list[TimelineEntry]
            タイムラインエントリのリスト。
        """
        self._entries_column.controls.clear()
        if not entries:
            self._entries_column.controls.append(
                ft.Text("タイムラインデータなし", size=12, color=ft.Colors.GREY)
            )
            return
        for entry in entries:
            self._entries_column.controls.append(self._build_entry_row(entry))

    def _build_entry_row(self, entry: TimelineEntry) -> ft.Container:
        """タイムラインエントリ1件分の行を生成する。"""
        color = self._PHASE_COLORS.get(entry.phase, ft.Colors.GREY)
        icon = self._PHASE_ICONS.get(entry.phase, "❓")
        duration = self._format_duration(entry.start_time, entry.end_time)
        status_text = "進行中" if entry.status == "running" else entry.status

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=4,
                        height=40,
                        bgcolor=color,
                        border_radius=2,
                    ),
                    ft.Text(icon, size=16),
                    ft.Column(
                        controls=[
                            ft.Text(
                                entry.phase.upper(),
                                size=13,
                                weight=ft.FontWeight.W_500,
                                color=color,
                            ),
                            ft.Text(
                                f"{duration} | {status_text}",
                                size=11,
                                color=ft.Colors.GREY_600,
                            ),
                        ],
                        spacing=0,
                        expand=True,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.Padding(left=4, right=4, top=2, bottom=2),
        )

    @staticmethod
    def _format_duration(start: float, end: float | None) -> str:
        """期間を人間が読みやすい形式にフォーマットする。"""
        if end is None:
            elapsed = time.time() - start
            suffix = " (進行中)"
        else:
            elapsed = end - start
            suffix = ""
        if elapsed < 60:
            return f"{elapsed:.0f}秒{suffix}"
        if elapsed < 3600:
            return f"{elapsed / 60:.1f}分{suffix}"
        return f"{elapsed / 3600:.1f}時間{suffix}"
