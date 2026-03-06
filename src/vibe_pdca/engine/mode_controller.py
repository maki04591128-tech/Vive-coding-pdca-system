"""運転モード制御 – 手動/半自動/全自動モードの切替と承認フロー管理。

M2 タスク 2-11: 要件定義書 §10.2 準拠。

| モード         | 定義                                          |
|---------------|----------------------------------------------|
| 手動承認モード  | 重要操作に人間承認が必要                        |
| 半自動モード   | 一定条件を満たす場合のみ自動進行                |
| 全自動モード   | 事前定義した範囲内で自動進行。逸脱検知時は即停止 |
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from vibe_pdca.models.pdca import GovernanceLevel, PDCAPhase

logger = logging.getLogger(__name__)


class OperationMode(StrEnum):
    """運転モード（§10.2）。"""

    MANUAL = "manual"
    SEMI_AUTO = "semi_auto"
    FULL_AUTO = "full_auto"


# --- フェーズ自動進行マトリクス: モードごとに各フェーズの自動進行可否を定義 ---
_AUTO_ADVANCE_MATRIX: dict[OperationMode, dict[PDCAPhase, bool]] = {
    OperationMode.MANUAL: {
        PDCAPhase.PLAN: False,
        PDCAPhase.DO: False,
        PDCAPhase.CHECK: False,
        PDCAPhase.ACT: False,
    },
    OperationMode.SEMI_AUTO: {
        PDCAPhase.PLAN: True,
        PDCAPhase.DO: True,
        PDCAPhase.CHECK: True,
        PDCAPhase.ACT: False,  # ACTは人間承認
    },
    OperationMode.FULL_AUTO: {
        PDCAPhase.PLAN: True,
        PDCAPhase.DO: True,
        PDCAPhase.CHECK: True,
        PDCAPhase.ACT: True,
    },
}

# --- ガバナンス自動実行マトリクス: A操作は常に人間承認が必要 ---
_GOVERNANCE_AUTO: dict[OperationMode, dict[GovernanceLevel, bool]] = {
    OperationMode.MANUAL: {
        GovernanceLevel.A: False,
        GovernanceLevel.B: False,
        GovernanceLevel.C: False,
    },
    OperationMode.SEMI_AUTO: {
        GovernanceLevel.A: False,  # A操作は常に人間承認
        GovernanceLevel.B: True,   # B操作はペルソナ承認で自動
        GovernanceLevel.C: True,   # C操作は自動
    },
    OperationMode.FULL_AUTO: {
        GovernanceLevel.A: False,  # A操作は常に人間承認
        GovernanceLevel.B: True,
        GovernanceLevel.C: True,
    },
}


# --- モード制御: 手動/半自動/全自動モードの切替と承認要否の判定 ---
class ModeController:
    """運転モードを管理し、操作の承認要否を判定する。

    Parameters
    ----------
    initial_mode : OperationMode
        初期モード。デフォルトは手動承認モード。
    """

    def __init__(
        self,
        initial_mode: OperationMode = OperationMode.MANUAL,
    ) -> None:
        self._mode = initial_mode
        self._history: list[dict[str, Any]] = []

    @property
    def mode(self) -> OperationMode:
        """現在の運転モードを返す。"""
        return self._mode

    @property
    def mode_history(self) -> list[dict[str, Any]]:
        """モード変更履歴を返す。"""
        return list(self._history)

    def set_mode(self, new_mode: OperationMode, reason: str = "") -> None:
        """運転モードを変更する。

        Parameters
        ----------
        new_mode : OperationMode
            新しい運転モード。
        reason : str
            変更理由。
        """
        old_mode = self._mode
        self._mode = new_mode
        self._history.append({
            "from": old_mode.value,
            "to": new_mode.value,
            "reason": reason,
        })
        logger.info(
            "運転モード変更: %s → %s (理由: %s)",
            old_mode.value, new_mode.value, reason,
        )

    def can_auto_advance(self, phase: PDCAPhase) -> bool:
        """指定フェーズの自動進行が可能かどうかを判定する。

        Parameters
        ----------
        phase : PDCAPhase
            判定対象フェーズ。

        Returns
        -------
        bool
            自動進行可能なら True。
        """
        return _AUTO_ADVANCE_MATRIX[self._mode].get(phase, False)

    def requires_approval(
        self,
        governance_level: GovernanceLevel,
    ) -> bool:
        """指定ガバナンスレベルの操作に承認が必要かどうかを判定する。

        Parameters
        ----------
        governance_level : GovernanceLevel
            操作のガバナンスレベル。

        Returns
        -------
        bool
            承認が必要なら True。
        """
        auto = _GOVERNANCE_AUTO[self._mode].get(governance_level, False)
        return not auto

    def get_status(self) -> dict[str, Any]:
        """現在のモード状態を返す。"""
        return {
            "mode": self._mode.value,
            "auto_advance": {
                phase.value: self.can_auto_advance(phase)
                for phase in PDCAPhase
            },
            "approval_required": {
                level.value: self.requires_approval(level)
                for level in GovernanceLevel
            },
        }
