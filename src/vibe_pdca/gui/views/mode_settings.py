"""運転モード設定画面 – 手動/半自動/全自動モードの切替。

要件定義書 §10.2 に基づく運転モード設定画面。
ユーザーが運転モード（手動承認/半自動/全自動）を選択する。
"""

from __future__ import annotations

from typing import Any

import flet as ft


# --- モード設定ビュー: 手動承認/半自動/全自動の3運転モードを選択する画面 ---
class ModeSettingsView(ft.Column):
    """運転モード設定画面。

    §10.2 に基づき、3つの運転モードの選択と設定を提供する。

    - 手動承認モード: 重要操作に人間承認が必要
    - 半自動モード: 一定条件を満たす場合のみ自動進行
    - 全自動モード: 事前定義範囲内で自動進行、逸脱検知時は即停止

    Parameters
    ----------
    on_mode_change : callable | None
        モード変更時のコールバック ``(mode) -> None``。
    on_back : callable | None
        「戻る」ボタン押下時のコールバック。
    """

    _MODE_DESCRIPTIONS: dict[str, dict[str, str]] = {
        "manual": {
            "title": "🖐️ 手動承認モード",
            "description": (
                "すべての重要操作（PR作成・マージ・デプロイ等）に人間の承認が必要です。\n"
                "最も安全なモードで、システムの動作を完全に把握したい場合に推奨。"
            ),
            "badge_color": ft.Colors.BLUE,
        },
        "semi_auto": {
            "title": "🤖 半自動モード",
            "description": (
                "事前定義した条件を満たす場合のみ自動進行します。\n"
                "B操作（低リスク）は自動、A操作（高リスク）は承認待ちとなります。"
            ),
            "badge_color": ft.Colors.ORANGE,
        },
        "full_auto": {
            "title": "⚡ 全自動モード",
            "description": (
                "事前定義された範囲内で完全自動進行します。\n"
                "逸脱検知時（コスト超過・品質低下・連続失敗等）は即座に停止します。"
            ),
            "badge_color": ft.Colors.GREEN,
        },
    }

    def __init__(
        self,
        on_mode_change: Any = None,
        on_back: Any = None,
        **kwargs: Any,
    ) -> None:
        self._on_mode_change = on_mode_change
        self._on_back = on_back
        self._current_mode = "manual"

        # ── モード選択ラジオボタン ──
        self._mode_radio = ft.RadioGroup(
            value="manual",
            on_change=self._handle_mode_change,
            content=ft.Column(
                controls=[
                    self._build_mode_card("manual"),
                    self._build_mode_card("semi_auto"),
                    self._build_mode_card("full_auto"),
                ],
                spacing=8,
            ),
        )

        # ── 現在のモード表示 ──
        self._current_mode_text = ft.Text(
            "現在のモード: 🖐️ 手動承認モード",
            size=16,
            weight=ft.FontWeight.W_500,
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
                                "⚙️ 運転モード設定",
                                size=22,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                ),
                ft.Divider(height=1),
                # 現在のモード
                ft.Container(
                    content=self._current_mode_text,
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                ),
                # モード選択
                ft.Container(
                    content=self._mode_radio,
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                ),
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            **kwargs,
        )

    # ── 公開メソッド ──

    def get_current_mode(self) -> str:
        """現在の運転モードを返す。"""
        return self._current_mode

    def set_mode(self, mode: str) -> None:
        """運転モードを設定する。"""
        if mode in self._MODE_DESCRIPTIONS:
            self._current_mode = mode
            self._mode_radio.value = mode
            title = self._MODE_DESCRIPTIONS[mode]["title"]
            self._current_mode_text.value = f"現在のモード: {title}"

    # ── 内部メソッド ──

    def _build_mode_card(self, mode: str) -> ft.Container:
        """モード1つ分のラジオカードを生成する。"""
        info = self._MODE_DESCRIPTIONS[mode]
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Radio(value=mode),
                    ft.Column(
                        controls=[
                            ft.Text(
                                info["title"],
                                size=14,
                                weight=ft.FontWeight.W_500,
                            ),
                            ft.Text(
                                info["description"],
                                size=12,
                                color=ft.Colors.GREY_600,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding(left=12, right=12, top=8, bottom=8),
            border=ft.Border.all(1, ft.Colors.GREY_300),
            border_radius=8,
        )

    # ── イベントハンドラ ──

    def _handle_mode_change(self, e: ft.ControlEvent) -> None:
        """モード変更のハンドラ。"""
        mode = e.control.value
        if mode and mode in self._MODE_DESCRIPTIONS:
            self._current_mode = mode
            title = self._MODE_DESCRIPTIONS[mode]["title"]
            self._current_mode_text.value = f"現在のモード: {title}"
            if self._on_mode_change:
                self._on_mode_change(mode)

    def _handle_back(self, _e: ft.ControlEvent) -> None:
        """戻るボタンのハンドラ。"""
        if self._on_back:
            self._on_back()
