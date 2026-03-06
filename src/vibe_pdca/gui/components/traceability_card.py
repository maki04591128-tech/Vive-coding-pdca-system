"""トレーサビリティカード – アーティファクト間の関連を表示するコンポーネント。"""

from __future__ import annotations

from typing import Any

import flet as ft

from vibe_pdca.gui.dashboard import TraceLink


# --- トレーサビリティカード: Goal→MS→Task→PR→Decision の関連を表示するウィジェット ---
class TraceabilityCard(ft.Card):
    """トレーサビリティマップを表示するカードウィジェット。

    アーティファクト間のリンク（ゴール→マイルストーン→タスク→PR→判定）
    をリスト形式で表示する。
    """

    _TYPE_ICONS: dict[str, str] = {
        "goal": "🎯",
        "milestone": "📍",
        "task": "📝",
        "pr": "🔀",
        "decision": "⚖️",
        "issue": "🐛",
        "review": "🔍",
    }

    def __init__(self, **kwargs: Any) -> None:
        self._links_column = ft.Column(spacing=4)
        super().__init__(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "🔗 トレーサビリティ",
                            weight=ft.FontWeight.BOLD,
                            size=16,
                        ),
                        ft.Divider(height=1),
                        self._links_column,
                    ],
                    spacing=8,
                ),
                padding=16,
            ),
            **kwargs,
        )

    def update_links(self, links: list[TraceLink]) -> None:
        """トレースリンクを更新する。

        Parameters
        ----------
        links : list[TraceLink]
            トレースリンクのリスト。
        """
        self._links_column.controls.clear()
        if not links:
            self._links_column.controls.append(
                ft.Text("トレースリンクなし", size=12, color=ft.Colors.GREY)
            )
            return
        for link in links:
            self._links_column.controls.append(self._build_link_row(link))

    def _build_link_row(self, link: TraceLink) -> ft.Row:
        """トレースリンク1件分の行を生成する。"""
        src_icon = self._TYPE_ICONS.get(link.source_type, "📄")
        tgt_icon = self._TYPE_ICONS.get(link.target_type, "📄")
        return ft.Row(
            controls=[
                ft.Text(src_icon, size=14),
                ft.Text(
                    f"{link.source_type}:{link.source_id}",
                    size=12,
                    weight=ft.FontWeight.W_500,
                ),
                ft.Text("→", size=14, color=ft.Colors.GREY),
                ft.Text(tgt_icon, size=14),
                ft.Text(
                    f"{link.target_type}:{link.target_id}",
                    size=12,
                    weight=ft.FontWeight.W_500,
                ),
            ],
            spacing=4,
        )
