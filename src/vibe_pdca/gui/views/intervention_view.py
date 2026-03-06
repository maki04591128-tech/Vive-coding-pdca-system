"""介入操作画面 – 停止・原因分析・ロールバック・採否上書き等の操作画面。

要件定義書 §10.4 に基づく介入操作画面。
ユーザーがPDCAサイクルを停止・ロールバック・上書き等で介入する。
"""

from __future__ import annotations

from typing import Any

import flet as ft


# --- 介入ビュー: PDCAサイクルへの停止/ロールバック/上書き等の介入操作を行う画面 ---
class InterventionView(ft.Column):
    """介入操作画面。

    §10.4 に基づき、停止ボタン・原因分析レポート・再開条件・
    ロールバック候補・採否上書き・優先度変更・MS再編の操作を提供する。

    Parameters
    ----------
    on_stop : callable | None
        「停止」ボタン押下時のコールバック。
    on_rollback : callable | None
        「ロールバック」ボタン押下時のコールバック ``(target_id) -> None``。
    on_override : callable | None
        「採否上書き」ボタン押下時のコールバック ``(decision) -> None``。
    on_back : callable | None
        「戻る」ボタン押下時のコールバック。
    """

    def __init__(
        self,
        on_stop: Any = None,
        on_rollback: Any = None,
        on_override: Any = None,
        on_back: Any = None,
        **kwargs: Any,
    ) -> None:
        self._on_stop = on_stop
        self._on_rollback = on_rollback
        self._on_override = on_override
        self._on_back = on_back
        self._is_stopped = False

        # ── 停止ボタン ──
        self._stop_btn = ft.ElevatedButton(
            "⛔ サイクル停止",
            icon=ft.Icons.STOP_CIRCLE,
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.RED,
            on_click=self._handle_stop,
        )

        # ── 原因分析レポート ──
        self._analysis_text = ft.Text(
            "", size=12, color=ft.Colors.GREY_600
        )
        self._analysis_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "📊 原因分析レポート",
                        weight=ft.FontWeight.BOLD,
                        size=14,
                    ),
                    self._analysis_text,
                ],
                spacing=8,
            ),
            visible=False,
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            border=ft.Border.all(1, ft.Colors.ORANGE_200),
            border_radius=8,
            bgcolor=ft.Colors.ORANGE_50,
        )

        # ── 再開条件 ──
        self._restart_text = ft.Text(
            "", size=12, color=ft.Colors.GREY_600
        )
        self._restart_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "🔄 再開条件",
                        weight=ft.FontWeight.BOLD,
                        size=14,
                    ),
                    self._restart_text,
                ],
                spacing=8,
            ),
            visible=False,
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            border=ft.Border.all(1, ft.Colors.GREEN_200),
            border_radius=8,
            bgcolor=ft.Colors.GREEN_50,
        )

        # ── ロールバック候補 ──
        self._rollback_column = ft.Column(spacing=4)
        self._rollback_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "⏪ ロールバック候補",
                        weight=ft.FontWeight.BOLD,
                        size=14,
                    ),
                    self._rollback_column,
                ],
                spacing=8,
            ),
            visible=False,
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            border=ft.Border.all(1, ft.Colors.BLUE_200),
            border_radius=8,
        )

        # ── 採否上書き ──
        self._override_dropdown = ft.Dropdown(
            label="採否判定",
            width=200,
            options=[
                ft.dropdown.Option("approve", "✅ 承認"),
                ft.dropdown.Option("reject", "❌ 却下"),
                ft.dropdown.Option("redo", "🔄 やり直し"),
            ],
        )
        self._override_btn = ft.ElevatedButton(
            "採否上書き",
            icon=ft.Icons.EDIT,
            on_click=self._handle_override,
        )

        # ── 優先度変更 ──
        self._priority_dropdown = ft.Dropdown(
            label="新しい優先度",
            width=200,
            options=[
                ft.dropdown.Option("high", "🔴 高"),
                ft.dropdown.Option("medium", "🟡 中"),
                ft.dropdown.Option("low", "🟢 低"),
            ],
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
                                "🛑 介入操作",
                                size=22,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Container(expand=True),
                            self._stop_btn,
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                ),
                ft.Divider(height=1),
                # 停止後に表示されるエリア
                self._analysis_container,
                self._restart_container,
                self._rollback_container,
                # 操作エリア
                ft.Container(
                    content=ft.ResponsiveRow(
                        controls=[
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text(
                                            "⚖️ 採否上書き",
                                            weight=ft.FontWeight.BOLD,
                                            size=14,
                                        ),
                                        self._override_dropdown,
                                        self._override_btn,
                                    ],
                                    spacing=8,
                                ),
                                col={"sm": 12, "md": 6},
                                padding=8,
                                border=ft.Border.all(1, ft.Colors.GREY_300),
                                border_radius=8,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text(
                                            "🔀 優先度変更",
                                            weight=ft.FontWeight.BOLD,
                                            size=14,
                                        ),
                                        self._priority_dropdown,
                                    ],
                                    spacing=8,
                                ),
                                col={"sm": 12, "md": 6},
                                padding=8,
                                border=ft.Border.all(1, ft.Colors.GREY_300),
                                border_radius=8,
                            ),
                        ],
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                ),
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            **kwargs,
        )

    # ── 公開メソッド ──

    def set_analysis_report(self, report: str) -> None:
        """原因分析レポートを表示する。"""
        self._analysis_text.value = report
        self._analysis_container.visible = True

    def set_restart_conditions(self, conditions: str) -> None:
        """再開条件を表示する。"""
        self._restart_text.value = conditions
        self._restart_container.visible = True

    def set_rollback_candidates(
        self, candidates: list[dict[str, str]]
    ) -> None:
        """ロールバック候補を表示する。

        Parameters
        ----------
        candidates : list[dict]
            候補のリスト。各項目は ``{"id": str, "description": str}``。
        """
        self._rollback_column.controls.clear()
        for c in candidates:
            cid = c.get("id", "")
            self._rollback_column.controls.append(
                ft.Row(
                    controls=[
                        ft.TextButton(
                            f"⏪ {cid}",
                            on_click=lambda _e, _cid=cid: (
                                self._on_rollback(_cid) if self._on_rollback else None
                            ),
                        ),
                        ft.Text(
                            c.get("description", ""),
                            size=12,
                            color=ft.Colors.GREY_600,
                        ),
                    ],
                    spacing=8,
                )
            )
        self._rollback_container.visible = bool(candidates)

    @property
    def is_stopped(self) -> bool:
        """停止状態を返す。"""
        return self._is_stopped

    # ── イベントハンドラ ──

    def _handle_stop(self, _e: ft.ControlEvent) -> None:
        """停止ボタンのハンドラ。"""
        self._is_stopped = True
        self._stop_btn.disabled = True
        self._stop_btn.text = "⛔ 停止済み"
        if self._on_stop:
            self._on_stop()

    def _handle_override(self, _e: ft.ControlEvent) -> None:
        """採否上書きボタンのハンドラ。"""
        decision = self._override_dropdown.value
        if decision and self._on_override:
            self._on_override(decision)

    def _handle_back(self, _e: ft.ControlEvent) -> None:
        """戻るボタンのハンドラ。"""
        if self._on_back:
            self._on_back()
