"""進捗閲覧画面 – マイルストーン・DoD・直近PLAN/CHECK/ACT の一覧表示。

要件定義書 §10.3 に基づく進捗閲覧画面。
現在のマイルストーン・DoD・直近サイクルの結果を一画面で閲覧する。
"""

from __future__ import annotations

from typing import Any

import flet as ft


# --- 進捗ビュー: マイルストーン・DoD・直近PDCA結果を一覧表示する画面 ---
class ProgressView(ft.Column):
    """進捗閲覧画面。

    §10.3 に基づき、現在のマイルストーン・DoD一覧・直近PLAN/CHECK/ACT
    を一画面で表示する。

    Parameters
    ----------
    on_back : callable | None
        「戻る」ボタン押下時のコールバック。
    """

    def __init__(
        self,
        on_back: Any = None,
        **kwargs: Any,
    ) -> None:
        self._on_back = on_back

        # ── マイルストーン表示 ──
        self._milestone_text = ft.Text(
            "マイルストーン: --", size=16, weight=ft.FontWeight.W_500
        )
        self._milestone_status = ft.Text(
            "ステータス: --", size=13, color=ft.Colors.GREY_600
        )

        # ── DoD一覧 ──
        self._dod_column = ft.Column(spacing=4)

        # ── 直近 PLAN ──
        self._plan_text = ft.Text(
            "データなし", size=12, color=ft.Colors.GREY
        )

        # ── 直近 CHECK ──
        self._check_text = ft.Text(
            "データなし", size=12, color=ft.Colors.GREY
        )

        # ── 直近 ACT ──
        self._act_text = ft.Text(
            "データなし", size=12, color=ft.Colors.GREY
        )

        super().__init__(
            controls=[
                # ヘッダー
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.IconButton(
                                ft.Icons.ARROW_BACK,
                                on_click=self._handle_back,
                            ),
                            ft.Text(
                                "📈 進捗閲覧",
                                size=22,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                ),
                ft.Divider(height=1),
                # マイルストーン
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "📍 現在のマイルストーン",
                                weight=ft.FontWeight.BOLD,
                                size=14,
                            ),
                            self._milestone_text,
                            self._milestone_status,
                        ],
                        spacing=4,
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                    border=ft.Border.all(1, ft.Colors.GREY_300),
                    border_radius=8,
                ),
                # DoD
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "✅ DoD（完了条件）一覧",
                                weight=ft.FontWeight.BOLD,
                                size=14,
                            ),
                            self._dod_column,
                        ],
                        spacing=8,
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                    border=ft.Border.all(1, ft.Colors.GREY_300),
                    border_radius=8,
                ),
                # 直近 PLAN / CHECK / ACT
                ft.ResponsiveRow(
                    controls=[
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Text(
                                        "📋 直近 PLAN",
                                        weight=ft.FontWeight.BOLD,
                                        size=14,
                                        color=ft.Colors.BLUE,
                                    ),
                                    self._plan_text,
                                ],
                                spacing=4,
                            ),
                            col={"sm": 12, "md": 4},
                            padding=8,
                            border=ft.Border.all(1, ft.Colors.BLUE_200),
                            border_radius=8,
                        ),
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Text(
                                        "🔍 直近 CHECK",
                                        weight=ft.FontWeight.BOLD,
                                        size=14,
                                        color=ft.Colors.ORANGE,
                                    ),
                                    self._check_text,
                                ],
                                spacing=4,
                            ),
                            col={"sm": 12, "md": 4},
                            padding=8,
                            border=ft.Border.all(1, ft.Colors.ORANGE_200),
                            border_radius=8,
                        ),
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Text(
                                        "✅ 直近 ACT",
                                        weight=ft.FontWeight.BOLD,
                                        size=14,
                                        color=ft.Colors.PURPLE,
                                    ),
                                    self._act_text,
                                ],
                                spacing=4,
                            ),
                            col={"sm": 12, "md": 4},
                            padding=8,
                            border=ft.Border.all(1, ft.Colors.PURPLE_200),
                            border_radius=8,
                        ),
                    ],
                ),
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            **kwargs,
        )

    # ── 公開メソッド ──

    def update_milestone(
        self,
        milestone_id: str,
        status: str,
        description: str = "",
    ) -> None:
        """マイルストーン情報を更新する。"""
        self._milestone_text.value = f"マイルストーン: {milestone_id}"
        desc = f" — {description}" if description else ""
        self._milestone_status.value = f"ステータス: {status}{desc}"

    def update_dod(self, dod_items: list[dict[str, Any]]) -> None:
        """DoD一覧を更新する。

        Parameters
        ----------
        dod_items : list[dict]
            DoD項目のリスト。各項目は ``{"text": str, "done": bool}``。
        """
        self._dod_column.controls.clear()
        if not dod_items:
            self._dod_column.controls.append(
                ft.Text("DoD未定義", size=12, color=ft.Colors.GREY)
            )
            return
        for item in dod_items:
            icon = "✅" if item.get("done") else "⬜"
            color = ft.Colors.GREEN if item.get("done") else ft.Colors.GREY_600
            self._dod_column.controls.append(
                ft.Text(
                    f"{icon} {item.get('text', '')}",
                    size=12,
                    color=color,
                )
            )

    def update_recent_plan(self, text: str) -> None:
        """直近PLANを更新する。"""
        self._plan_text.value = text or "データなし"

    def update_recent_check(self, text: str) -> None:
        """直近CHECKを更新する。"""
        self._check_text.value = text or "データなし"

    def update_recent_act(self, text: str) -> None:
        """直近ACTを更新する。"""
        self._act_text.value = text or "データなし"

    # ── イベントハンドラ ──

    def _handle_back(self, _e: ft.ControlEvent) -> None:
        """戻るボタンのハンドラ。"""
        if self._on_back:
            self._on_back()
