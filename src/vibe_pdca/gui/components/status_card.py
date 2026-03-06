"""ステータスカード – プロバイダ状態表示コンポーネント。"""

from __future__ import annotations

from typing import Any

import flet as ft


# --- ステータスカード: LLMプロバイダの状態をカード型UIで表示するウィジェット ---
class StatusCard(ft.Card):
    """プロバイダのステータスを表示するカードウィジェット。

    Parameters
    ----------
    title : str
        カードのタイトル（例: "クラウドLLM", "ローカルLLM"）。
    """

    def __init__(self, title: str, **kwargs: Any) -> None:
        self._title = title
        self._items_column = ft.Column(spacing=4)
        super().__init__(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(title, weight=ft.FontWeight.BOLD, size=16),
                        ft.Divider(height=1),
                        self._items_column,
                    ],
                    spacing=8,
                ),
                padding=16,
            ),
            **kwargs,
        )

    def update_items(self, items: dict[str, dict[str, Any]]) -> None:
        """表示内容を更新する。

        Parameters
        ----------
        items : dict[str, dict[str, Any]]
            プロバイダ名 → ステータス情報の辞書。
        """
        self._items_column.controls.clear()
        for name, info in items.items():
            self._items_column.controls.append(self._build_item_row(name, info))

    def _build_item_row(self, name: str, info: dict[str, Any]) -> ft.Row:
        """プロバイダ1件分の行を生成する。"""
        # ステータスアイコン
        status = info.get("circuit_state") or info.get("status", "unknown")
        icon, color = self._status_icon(status)

        # 情報テキスト
        detail_parts: list[str] = []
        if "model" in info:
            detail_parts.append(info["model"])
        if "circuit_state" in info:
            detail_parts.append(f"CB: {info['circuit_state']}")
        if info.get("total_fallbacks"):
            detail_parts.append(f"FB: {info['total_fallbacks']}")
        detail = "  |  ".join(detail_parts)

        return ft.Row(
            controls=[
                ft.Icon(icon, color=color, size=18),
                ft.Column(
                    controls=[
                        ft.Text(name, size=13, weight=ft.FontWeight.W_500),
                        ft.Text(detail, size=11, color=ft.Colors.GREY_600),
                    ],
                    spacing=0,
                    expand=True,
                ),
            ],
            spacing=8,
        )

    @staticmethod
    def _status_icon(status: str) -> tuple[str, str]:
        """ステータスに応じたアイコンと色を返す。"""
        mapping = {
            "closed": (ft.Icons.CHECK_CIRCLE, ft.Colors.GREEN),
            "healthy": (ft.Icons.CHECK_CIRCLE, ft.Colors.GREEN),
            "open": (ft.Icons.ERROR, ft.Colors.RED),
            "unhealthy": (ft.Icons.ERROR, ft.Colors.RED),
            "half_open": (ft.Icons.WARNING, ft.Colors.ORANGE),
            "degraded": (ft.Icons.WARNING, ft.Colors.ORANGE),
        }
        return mapping.get(status, (ft.Icons.HELP, ft.Colors.GREY))


# --- コストカード: API利用コスト（USD/日、合計）を表示するウィジェット ---
class CostCard(ft.Card):
    """コスト情報を表示するカードウィジェット。"""

    def __init__(self, **kwargs: Any) -> None:
        self._cost_text = ft.Text("$0.00 / $30.00", size=22, weight=ft.FontWeight.BOLD)
        self._calls_text = ft.Text("0 / 500 calls", size=13, color=ft.Colors.GREY_600)
        self._progress = ft.ProgressBar(value=0, width=250, color=ft.Colors.BLUE)
        super().__init__(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("コスト (日次)", weight=ft.FontWeight.BOLD, size=16),
                        ft.Divider(height=1),
                        self._cost_text,
                        self._progress,
                        self._calls_text,
                    ],
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=16,
            ),
            **kwargs,
        )

    def update_cost(self, cost: dict[str, Any], limits: dict[str, float]) -> None:
        """コスト情報を更新する。"""
        daily = cost.get("daily_cost_usd", 0.0)
        limit = limits.get("daily_limit_usd", 30.0)
        calls = cost.get("daily_calls", 0)
        max_calls = limits.get("max_calls_per_day", 500)

        self._cost_text.value = f"${daily:.2f} / ${limit:.2f}"
        self._calls_text.value = f"{calls} / {max_calls} calls"

        ratio = daily / limit if limit > 0 else 0
        self._progress.value = min(ratio, 1.0)
        if ratio >= 0.9:
            self._progress.color = ft.Colors.RED
        elif ratio >= 0.7:
            self._progress.color = ft.Colors.ORANGE
        else:
            self._progress.color = ft.Colors.BLUE
