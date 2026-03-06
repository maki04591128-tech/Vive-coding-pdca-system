"""コスト推移カード – サイクル・日別のコスト推移を表示するコンポーネント。"""

from __future__ import annotations

from typing import Any

import flet as ft

from vibe_pdca.gui.dashboard import CostDataPoint


# --- コスト推移カード: APIコストの推移をバーグラフ風に表示するウィジェット ---
class CostChartCard(ft.Card):
    """コスト推移を表示するカードウィジェット。

    日別・サイクル別のコストデータをバーチャート風に表示する。
    """

    def __init__(self, **kwargs: Any) -> None:
        self._chart_column = ft.Column(spacing=4)
        self._total_text = ft.Text(
            "合計: $0.00", size=14, weight=ft.FontWeight.W_500
        )
        super().__init__(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "📊 コスト推移",
                            weight=ft.FontWeight.BOLD,
                            size=16,
                        ),
                        ft.Divider(height=1),
                        self._total_text,
                        self._chart_column,
                    ],
                    spacing=8,
                ),
                padding=16,
            ),
            **kwargs,
        )

    def update_chart(self, data_points: list[CostDataPoint]) -> None:
        """コスト推移データを更新する。

        Parameters
        ----------
        data_points : list[CostDataPoint]
            コストデータポイントのリスト。
        """
        self._chart_column.controls.clear()
        if not data_points:
            self._chart_column.controls.append(
                ft.Text("コストデータなし", size=12, color=ft.Colors.GREY)
            )
            self._total_text.value = "合計: $0.00"
            return

        total = sum(p.cost_usd for p in data_points)
        self._total_text.value = f"合計: ${total:.2f}"
        max_cost = max(p.cost_usd for p in data_points) if data_points else 1.0
        if max_cost == 0:
            max_cost = 1.0

        # 直近10件を表示
        recent = data_points[-10:]
        for point in recent:
            ratio = point.cost_usd / max_cost
            self._chart_column.controls.append(
                self._build_bar_row(point, ratio)
            )

    def _build_bar_row(
        self, point: CostDataPoint, ratio: float
    ) -> ft.Container:
        """コストデータ1件分のバーを生成する。"""
        color = ft.Colors.BLUE if ratio < 0.7 else (
            ft.Colors.ORANGE if ratio < 0.9 else ft.Colors.RED
        )
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        f"C{point.cycle_number}",
                        size=11,
                        width=30,
                        color=ft.Colors.GREY_600,
                    ),
                    ft.Container(
                        width=max(ratio * 150, 2),
                        height=14,
                        bgcolor=color,
                        border_radius=3,
                    ),
                    ft.Text(
                        f"${point.cost_usd:.2f}",
                        size=11,
                        color=ft.Colors.GREY_600,
                    ),
                    ft.Text(
                        point.model,
                        size=10,
                        color=ft.Colors.GREY_400,
                    ),
                ],
                spacing=4,
            ),
            padding=ft.Padding(left=0, right=0, top=1, bottom=1),
        )
