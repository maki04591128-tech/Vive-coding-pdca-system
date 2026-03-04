"""PDCA状態機械 – サイクルのフェーズ遷移と停止条件を管理する。

M1 タスク 1-3: 要件定義書 §6.1 準拠。
状態遷移: PLAN → DO → CHECK → ACT → (DoD達成? → 完了 or 次PLAN)
7つの停止条件を常時監視する。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from vibe_pdca.models.pdca import (
    Cycle,
    CycleStatus,
    Decision,
    DecisionType,
    Milestone,
    MilestoneStatus,
    PDCAPhase,
    StopReason,
    Task,
    TaskStatus,
)

logger = logging.getLogger(__name__)

__all__ = [
    "PDCAStateMachine",
    "PDCAStateMachineError",
    "InvalidTransitionError",
    "StopConditionError",
    "STOP_THRESHOLDS",
]

# 停止条件の閾値（§6.6）
STOP_THRESHOLDS: dict[str, int | float] = {
    "ci_consecutive_failure": 5,
    "diff_lines_total": 2000,
    "diff_lines_single_file": 600,
    "same_error_retry": 2,
    "cycle_timeout_seconds": 6 * 3600,  # 6時間
    "max_tasks_per_cycle": 7,
    "max_tasks_per_milestone": 30,
}


class PDCAStateMachineError(Exception):
    """PDCA状態機械のエラー基底クラス。"""


class InvalidTransitionError(PDCAStateMachineError):
    """不正なフェーズ遷移。"""


class StopConditionError(PDCAStateMachineError):
    """停止条件が発火した。"""

    def __init__(self, reason: StopReason, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"停止条件: {reason.value} – {detail}")


class PDCAStateMachine:
    """PDCAサイクルの状態遷移を管理する。

    Parameters
    ----------
    milestone : Milestone
        対象マイルストーン。
    thresholds : dict | None
        停止条件の閾値（デフォルト: STOP_THRESHOLDS）。
    """

    # 有効な遷移マップ
    VALID_TRANSITIONS: dict[PDCAPhase, list[PDCAPhase]] = {
        PDCAPhase.PLAN: [PDCAPhase.DO],
        PDCAPhase.DO: [PDCAPhase.CHECK],
        PDCAPhase.CHECK: [PDCAPhase.ACT],
        PDCAPhase.ACT: [PDCAPhase.PLAN],  # 次サイクルへ
    }

    def __init__(
        self,
        milestone: Milestone,
        thresholds: dict[str, Any] | None = None,
    ) -> None:
        self._milestone = milestone
        self._thresholds: dict[str, int | float] = {
            **STOP_THRESHOLDS,
            **(thresholds or {}),
        }
        self._stopped = False
        self._stop_reason: StopReason | None = None
        self._ci_consecutive_failures = 0
        self._same_error_count: dict[str, int] = {}

    # ── プロパティ ──

    @property
    def milestone(self) -> Milestone:
        return self._milestone

    @property
    def current_cycle(self) -> Cycle | None:
        """現在のサイクルを返す。"""
        if not self._milestone.cycles:
            return None
        return self._milestone.cycles[-1]

    @property
    def current_phase(self) -> PDCAPhase | None:
        """現在のフェーズを返す。"""
        cycle = self.current_cycle
        return cycle.phase if cycle else None

    @property
    def is_stopped(self) -> bool:
        return self._stopped

    @property
    def stop_reason(self) -> StopReason | None:
        return self._stop_reason

    @property
    def cycle_count(self) -> int:
        return len(self._milestone.cycles)

    # ── サイクル管理 ──

    def start_new_cycle(self, tasks: list[Task] | None = None) -> Cycle:
        """新しいPDCAサイクルを開始する（PLANフェーズ）。

        Parameters
        ----------
        tasks : list[Task] | None
            PLANフェーズで生成されるタスクリスト（最大7件）。

        Raises
        ------
        PDCAStateMachineError
            停止中またはサイクル実行中の場合。
        """
        if self._stopped:
            raise PDCAStateMachineError(
                f"停止中のためサイクル開始不可（理由: {self._stop_reason}）"
            )

        # 前サイクルが完了済みであることを確認
        if self.current_cycle and self.current_cycle.status == CycleStatus.RUNNING:
            raise PDCAStateMachineError(
                "前サイクルが未完了のため新サイクル開始不可"
            )

        # タスク数の上限チェック
        task_list = tasks or []
        max_tasks = int(self._thresholds["max_tasks_per_cycle"])
        if len(task_list) > max_tasks:
            raise PDCAStateMachineError(
                f"タスク数上限超過: {len(task_list)} > {max_tasks}"
            )

        cycle = Cycle(
            cycle_number=self.cycle_count + 1,
            phase=PDCAPhase.PLAN,
            status=CycleStatus.RUNNING,
            tasks=task_list,
        )
        self._milestone.cycles.append(cycle)

        if self._milestone.status == MilestoneStatus.OPEN:
            self._milestone.status = MilestoneStatus.IN_PROGRESS

        logger.info(
            "サイクル %d 開始 (マイルストーン: %s, タスク数: %d)",
            cycle.cycle_number, self._milestone.id, len(task_list),
        )
        return cycle

    def transition(self, to_phase: PDCAPhase) -> None:
        """フェーズを遷移させる。

        Parameters
        ----------
        to_phase : PDCAPhase
            遷移先フェーズ。

        Raises
        ------
        InvalidTransitionError
            不正な遷移の場合。
        StopConditionError
            停止条件が発火した場合。
        """
        cycle = self.current_cycle
        if cycle is None:
            raise PDCAStateMachineError("アクティブなサイクルがありません")

        if self._stopped:
            raise PDCAStateMachineError(
                f"停止中のため遷移不可（理由: {self._stop_reason}）"
            )

        # 遷移の妥当性チェック
        valid_targets = self.VALID_TRANSITIONS.get(cycle.phase, [])
        if to_phase not in valid_targets:
            raise InvalidTransitionError(
                f"不正な遷移: {cycle.phase.value} → {to_phase.value} "
                f"(有効: {[p.value for p in valid_targets]})"
            )

        # タイムアウトチェック
        self._check_cycle_timeout(cycle)

        old_phase = cycle.phase
        cycle.phase = to_phase

        logger.info(
            "フェーズ遷移: %s → %s (サイクル %d)",
            old_phase.value, to_phase.value, cycle.cycle_number,
        )

    def complete_cycle(self, decision: Decision) -> bool:
        """現在のサイクルを完了させる。

        Parameters
        ----------
        decision : Decision
            ACTフェーズの判定結果。

        Returns
        -------
        bool
            DoD達成で完了した場合True。
        """
        cycle = self.current_cycle
        if cycle is None:
            raise PDCAStateMachineError("アクティブなサイクルがありません")

        cycle.decision = decision
        cycle.completed_at = time.time()

        if decision.decision_type == DecisionType.ACCEPT:
            cycle.status = CycleStatus.COMPLETED
            for task in cycle.tasks:
                if task.status == TaskStatus.IN_PROGRESS:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = time.time()
            return True

        if decision.decision_type in (DecisionType.ABORT, DecisionType.DEGRADE):
            cycle.status = CycleStatus.FAILED
            return False

        # REJECT / DEFER → 次サイクルへ
        cycle.status = CycleStatus.COMPLETED
        return False

    def complete_milestone(self) -> None:
        """マイルストーンを完了させる。"""
        self._milestone.status = MilestoneStatus.COMPLETED
        self._milestone.completed_at = time.time()
        logger.info("マイルストーン完了: %s", self._milestone.id)

    # ── 停止条件 ──

    def stop(self, reason: StopReason, detail: str = "") -> None:
        """PDCAを停止させる（§6.6）。"""
        self._stopped = True
        self._stop_reason = reason

        cycle = self.current_cycle
        if cycle and cycle.status == CycleStatus.RUNNING:
            cycle.status = CycleStatus.STOPPED
            cycle.stop_reason = reason
            cycle.completed_at = time.time()

        logger.warning(
            "PDCA停止: %s – %s (サイクル %d)",
            reason.value, detail,
            cycle.cycle_number if cycle else 0,
        )

    def resume(self) -> None:
        """停止状態から再開する（人間承認後）。"""
        if not self._stopped:
            raise PDCAStateMachineError("停止中ではありません")

        self._stopped = False
        old_reason = self._stop_reason
        self._stop_reason = None

        logger.info("PDCA再開 (前回停止理由: %s)", old_reason)

    def check_stop_conditions(
        self,
        ci_failures: int = 0,
        diff_lines_total: int = 0,
        diff_lines_max_file: int = 0,
        error_key: str | None = None,
    ) -> StopReason | None:
        """停止条件を評価する（§6.6）。

        発火した場合は自動的に stop() を呼び出す。

        Returns
        -------
        StopReason | None
            発火した停止条件。なければ None。
        """
        # 1. CI連続失敗
        self._ci_consecutive_failures = ci_failures
        if ci_failures >= self._thresholds["ci_consecutive_failure"]:
            reason = StopReason.CI_CONSECUTIVE_FAILURE
            self.stop(reason, f"CI連続失敗: {ci_failures}回")
            return reason

        # 2. 変更量超過（diff行数）
        if diff_lines_total > self._thresholds["diff_lines_total"]:
            reason = StopReason.DIFF_SIZE_EXCEEDED
            self.stop(reason, f"合計diff行数超過: {diff_lines_total}")
            return reason
        if diff_lines_max_file > self._thresholds["diff_lines_single_file"]:
            reason = StopReason.DIFF_SIZE_EXCEEDED
            self.stop(reason, f"単一ファイルdiff行数超過: {diff_lines_max_file}")
            return reason

        # 3. 同一エラーの連続リトライ
        if error_key:
            self._same_error_count[error_key] = (
                self._same_error_count.get(error_key, 0) + 1
            )
            if self._same_error_count[error_key] > self._thresholds["same_error_retry"]:
                reason = StopReason.SAME_ERROR_RETRY
                self.stop(reason, f"同一エラー連続: {error_key}")
                return reason

        # 4. サイクルタイムアウト
        cycle = self.current_cycle
        if cycle:
            elapsed = time.time() - cycle.started_at
            if elapsed > self._thresholds["cycle_timeout_seconds"]:
                reason = StopReason.CYCLE_TIMEOUT
                self.stop(reason, f"タイムアウト: {elapsed:.0f}秒")
                return reason

        return None

    def check_critical_incident(self, detail: str) -> None:
        """重大インシデント即停止（§6.6）。"""
        self.stop(StopReason.CRITICAL_INCIDENT, detail)
        raise StopConditionError(StopReason.CRITICAL_INCIDENT, detail)

    def check_audit_inconsistency(self, detail: str) -> None:
        """監査ログ不整合即停止（§6.6）。"""
        self.stop(StopReason.AUDIT_LOG_INCONSISTENCY, detail)
        raise StopConditionError(StopReason.AUDIT_LOG_INCONSISTENCY, detail)

    def user_stop(self) -> None:
        """ユーザーの停止指示（§6.6）。"""
        self.stop(StopReason.USER_STOP, "ユーザーによる手動停止")

    # ── 内部メソッド ──

    def _check_cycle_timeout(self, cycle: Cycle) -> None:
        """サイクルタイムアウトチェック。"""
        elapsed = time.time() - cycle.started_at
        timeout = float(self._thresholds["cycle_timeout_seconds"])
        if elapsed > timeout:
            self.stop(
                StopReason.CYCLE_TIMEOUT,
                f"サイクル {cycle.cycle_number} がタイムアウト ({elapsed:.0f}s > {timeout}s)",
            )
            raise StopConditionError(
                StopReason.CYCLE_TIMEOUT,
                f"タイムアウト: {elapsed:.0f}秒 > {timeout}秒",
            )

    # ── ステータス取得 ──

    def get_status(self) -> dict[str, Any]:
        """状態機械の現在の状態を返す。"""
        cycle = self.current_cycle
        return {
            "milestone_id": self._milestone.id,
            "milestone_status": self._milestone.status.value,
            "cycle_count": self.cycle_count,
            "current_phase": cycle.phase.value if cycle else None,
            "current_cycle_number": cycle.cycle_number if cycle else None,
            "current_cycle_status": cycle.status.value if cycle else None,
            "is_stopped": self._stopped,
            "stop_reason": self._stop_reason.value if self._stop_reason else None,
            "ci_consecutive_failures": self._ci_consecutive_failures,
        }
