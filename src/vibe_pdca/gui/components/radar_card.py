"""レーダーチャートカード – ペルソナ別の評価スコアを表示するコンポーネント。"""

from __future__ import annotations

from typing import Any

import flet as ft

from vibe_pdca.gui.dashboard import RadarChartData


# --- レーダーカード: 5ペルソナの評価スコアをバー形式で比較表示するウィジェット ---
class RadarCard(ft.Card):
    """ペルソナ別レーダーチャート風カードウィジェット。

    5ペルソナの評価軸ごとのスコアをバーチャート形式で表示する。
    （Flet の描画機能制限のため、棒グラフ形式でスコアを可視化する）
    """

    _PERSONA_COLORS: dict[str, str] = {
        "PM": ft.Colors.BLUE,
        "Scribe": ft.Colors.GREEN,
        "Developer": ft.Colors.ORANGE,
        "Designer": ft.Colors.PURPLE,
        "User": ft.Colors.PINK,
    }

    def __init__(self, **kwargs: Any) -> None:
        self._data_column = ft.Column(spacing=8)
        super().__init__(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "🕸️ ペルソナ別スコア",
                            weight=ft.FontWeight.BOLD,
                            size=16,
                        ),
                        ft.Divider(height=1),
                        self._data_column,
                    ],
                    spacing=8,
                ),
                padding=16,
            ),
            **kwargs,
        )

    def update_radar(self, data: list[RadarChartData]) -> None:
        """レーダーチャートデータを更新する。

        Parameters
        ----------
        data : list[RadarChartData]
            ペルソナ別レーダーチャートデータのリスト。
        """
        self._data_column.controls.clear()
        if not data:
            self._data_column.controls.append(
                ft.Text("スコアデータなし", size=12, color=ft.Colors.GREY)
            )
            return
        for persona_data in data:
            self._data_column.controls.append(
                self._build_persona_section(persona_data)
            )

    def _build_persona_section(self, data: RadarChartData) -> ft.Container:
        """ペルソナ1件分のスコアセクションを生成する。"""
        color = self._PERSONA_COLORS.get(data.persona, ft.Colors.GREY)
        bars: list[ft.Control] = []
        for axis, score in data.scores.items():
            bars.append(
                ft.Row(
                    controls=[
                        ft.Text(axis, size=10, width=60, color=ft.Colors.GREY_600),
                        ft.Container(
                            width=max(score * 120, 2),
                            height=10,
                            bgcolor=color,
                            border_radius=3,
                        ),
                        ft.Text(
                            f"{score:.0%}",
                            size=10,
                            color=ft.Colors.GREY_600,
                        ),
                    ],
                    spacing=4,
                )
            )
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        data.persona,
                        size=13,
                        weight=ft.FontWeight.W_500,
                        color=color,
                    ),
                    *bars,
                ],
                spacing=2,
            ),
            padding=ft.Padding(left=4, right=4, top=4, bottom=4),
        )
