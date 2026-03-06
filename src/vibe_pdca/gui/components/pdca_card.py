"""PDCA状態カード – サイクルの進捗を表示するコンポーネント。"""

from __future__ import annotations

from typing import Any

import flet as ft


# --- PDCAカード: 現在のサイクル進行状況を視覚的に表示するウィジェット ---
class PDCAStatusCard(ft.Card):
    """PDCAサイクルの状態を表示するカードウィジェット。"""

    # 各PDCAフェーズの表示スタイル（アイコン・色の組み合わせ）
    _PHASE_STYLES: dict[str, tuple[str, str, str]] = {
        "plan": ("📋 PLAN", ft.Icons.EDIT_NOTE, ft.Colors.BLUE),
        "do": ("🔧 DO", ft.Icons.BUILD, ft.Colors.GREEN),
        "check": ("🔍 CHECK", ft.Icons.FACT_CHECK, ft.Colors.ORANGE),
        "act": ("✅ ACT", ft.Icons.TASK_ALT, ft.Colors.PURPLE),
    }

    def __init__(self, **kwargs: Any) -> None:
        self._phase_text = ft.Text(
            "フェーズ: --",
            size=18,
            weight=ft.FontWeight.BOLD,
        )
        self._cycle_text = ft.Text(
            "サイクル: --",
            size=13,
            color=ft.Colors.GREY_600,
        )
        self._status_text = ft.Text(
            "状態: --",
            size=13,
            color=ft.Colors.GREY_600,
        )
        self._milestone_text = ft.Text(
            "マイルストーン: --",
            size=13,
            color=ft.Colors.GREY_600,
        )
        self._stop_indicator = ft.Container(visible=False)

        super().__init__(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "🔄 PDCAサイクル",
                            weight=ft.FontWeight.BOLD,
                            size=16,
                        ),
                        ft.Divider(height=1),
                        self._phase_text,
                        self._cycle_text,
                        self._milestone_text,
                        self._status_text,
                        self._stop_indicator,
                    ],
                    spacing=6,
                ),
                padding=16,
            ),
            **kwargs,
        )

    def update_pdca_status(self, status: dict[str, Any]) -> None:
        """PDCAステータスを更新する。

        Parameters
        ----------
        status : dict
            ``PDCAStateMachine.get_status()`` の戻り値。
        """
        phase = status.get("current_phase")
        if phase and phase in self._PHASE_STYLES:
            label, _, color = self._PHASE_STYLES[phase]
            self._phase_text.value = f"フェーズ: {label}"
            self._phase_text.color = color
        else:
            self._phase_text.value = "フェーズ: 未開始"
            self._phase_text.color = ft.Colors.GREY

        cycle_num = status.get("current_cycle_number")
        cycle_status = status.get("current_cycle_status", "--")
        self._cycle_text.value = (
            f"サイクル: #{cycle_num} ({cycle_status})"
            if cycle_num else "サイクル: 未開始"
        )

        ms_id = status.get("milestone_id", "--")
        ms_status = status.get("milestone_status", "--")
        self._milestone_text.value = f"MS: {ms_id} ({ms_status})"

        is_stopped = status.get("is_stopped", False)
        stop_reason = status.get("stop_reason")
        if is_stopped and stop_reason:
            self._status_text.value = f"⛔ 停止中: {stop_reason}"
            self._status_text.color = ft.Colors.RED
        else:
            self._status_text.value = "状態: 正常稼働"
            self._status_text.color = ft.Colors.GREEN
