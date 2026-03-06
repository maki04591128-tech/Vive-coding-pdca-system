"""最終到達点入力画面 – ゴール入力・差分質問・コスト見積もり表示。

要件定義書 §10.1 に基づくゴール入力フォーム。
ユーザーが最終到達点を入力し、5ペルソナレビューを開始する。
"""

from __future__ import annotations

from typing import Any

import flet as ft


# --- ゴール入力ビュー: 最終到達点の入力→レビュー開始までのフローを制御する画面 ---
class GoalInputView(ft.Column):
    """最終到達点入力画面。

    §10.1 に基づき、ゴール入力・欠落検出・差分質問・コスト見積もり
    の一連のフローを提供する。

    Parameters
    ----------
    on_submit : callable | None
        「要件定義完了」ボタン押下時のコールバック ``(goal_text) -> None``。
    on_back : callable | None
        「戻る」ボタン押下時のコールバック。
    """

    def __init__(
        self,
        on_submit: Any = None,
        on_back: Any = None,
        **kwargs: Any,
    ) -> None:
        self._on_submit = on_submit
        self._on_back = on_back

        # ── ゴール入力フォーム ──
        self._goal_input = ft.TextField(
            label="最終到達点（ゴール）",
            hint_text="例: Webアプリケーションの自動テスト・デプロイパイプラインを構築する",
            multiline=True,
            min_lines=3,
            max_lines=8,
        )

        # ── 差分質問エリア（システムが自動提示） ──
        self._questions_column = ft.Column(spacing=4)
        self._questions_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "📝 確認事項（差分質問）",
                        weight=ft.FontWeight.BOLD,
                        size=14,
                    ),
                    self._questions_column,
                ],
                spacing=8,
            ),
            visible=False,
            padding=ft.Padding(left=16, right=16, top=8, bottom=8),
            border=ft.Border.all(1, ft.Colors.BLUE_200),
            border_radius=8,
            bgcolor=ft.Colors.BLUE_50,
        )

        # ── コスト見積もりエリア ──
        self._estimate_text = ft.Text(
            "", size=13, color=ft.Colors.GREY_600
        )
        self._estimate_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "💰 コスト見積もり",
                        weight=ft.FontWeight.BOLD,
                        size=14,
                    ),
                    self._estimate_text,
                ],
                spacing=8,
            ),
            visible=False,
            padding=ft.Padding(left=16, right=16, top=8, bottom=8),
            border=ft.Border.all(1, ft.Colors.GREEN_200),
            border_radius=8,
            bgcolor=ft.Colors.GREEN_50,
        )

        # ── ボタン ──
        self._submit_btn = ft.ElevatedButton(
            "要件定義完了 → 5ペルソナレビュー開始",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._handle_submit,
            disabled=True,
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
                                "🎯 最終到達点入力",
                                size=22,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                ),
                ft.Divider(height=1),
                # ゴール入力
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "プロジェクトのゴール（最終到達点）を入力してください",
                                size=14,
                            ),
                            self._goal_input,
                        ],
                        spacing=8,
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                ),
                # 差分質問
                self._questions_container,
                # コスト見積もり
                self._estimate_container,
                # ボタン
                ft.Container(
                    content=ft.Row(
                        controls=[self._submit_btn],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                ),
            ],
            spacing=8,
            expand=True,
            **kwargs,
        )

    # ── 公開メソッド ──

    def set_questions(self, questions: list[str]) -> None:
        """差分質問を表示する。

        Parameters
        ----------
        questions : list[str]
            表示する質問のリスト。
        """
        self._questions_column.controls.clear()
        for i, q in enumerate(questions, 1):
            self._questions_column.controls.append(
                ft.Text(f"Q{i}. {q}", size=13)
            )
        self._questions_container.visible = bool(questions)

    def set_estimate(
        self,
        milestones: int,
        cycles: int,
        estimated_cost_usd: float,
    ) -> None:
        """コスト見積もりを表示する（§20.2 準拠）。

        Parameters
        ----------
        milestones : int
            推定マイルストーン数。
        cycles : int
            推定サイクル数。
        estimated_cost_usd : float
            推定LLMコスト（USD）。
        """
        self._estimate_text.value = (
            f"推定マイルストーン数: {milestones}\n"
            f"推定サイクル数: {cycles}\n"
            f"推定LLMコスト: ${estimated_cost_usd:.2f}"
        )
        self._estimate_container.visible = True
        self._submit_btn.disabled = False

    def get_goal_text(self) -> str:
        """入力されたゴールテキストを返す。"""
        return self._goal_input.value or ""

    # ── イベントハンドラ ──

    def _handle_submit(self, _e: ft.ControlEvent) -> None:
        """要件定義完了ボタンのハンドラ。"""
        if self._on_submit:
            self._on_submit(self.get_goal_text())

    def _handle_back(self, _e: ft.ControlEvent) -> None:
        """戻るボタンのハンドラ。"""
        if self._on_back:
            self._on_back()
