"""PDCA状態機械のユニットテスト。

M1 タスク 1-3: 全状態遷移 + 7停止条件のテスト。
"""


import pytest

from vibe_pdca.engine import (
    InvalidTransitionError,
    PDCAStateMachine,
    PDCAStateMachineError,
    StopConditionError,
)
from vibe_pdca.models.pdca import (
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


@pytest.fixture
def milestone():
    return Milestone(id="M-TEST", title="テストマイルストーン")


@pytest.fixture
def sm(milestone):
    return PDCAStateMachine(milestone)


# ============================================================
# サイクル管理テスト
# ============================================================


class TestCycleManagement:
    def test_start_new_cycle(self, sm):
        tasks = [Task(id="T-1", title="タスク1")]
        cycle = sm.start_new_cycle(tasks=tasks)
        assert cycle.cycle_number == 1
        assert cycle.phase == PDCAPhase.PLAN
        assert cycle.status == CycleStatus.RUNNING
        assert len(cycle.tasks) == 1

    def test_start_cycle_sets_milestone_in_progress(self, sm, milestone):
        assert milestone.status == MilestoneStatus.OPEN
        sm.start_new_cycle()
        assert milestone.status == MilestoneStatus.IN_PROGRESS

    def test_cannot_start_while_running(self, sm):
        sm.start_new_cycle()
        with pytest.raises(PDCAStateMachineError, match="未完了"):
            sm.start_new_cycle()

    def test_cannot_start_while_stopped(self, sm):
        sm.stop(StopReason.USER_STOP)
        with pytest.raises(PDCAStateMachineError, match="停止中"):
            sm.start_new_cycle()

    def test_max_7_tasks_per_cycle(self, sm):
        tasks = [Task(id=f"T-{i}", title=f"タスク{i}") for i in range(8)]
        with pytest.raises(PDCAStateMachineError, match="上限超過"):
            sm.start_new_cycle(tasks=tasks)

    def test_7_tasks_is_allowed(self, sm):
        tasks = [Task(id=f"T-{i}", title=f"タスク{i}") for i in range(7)]
        cycle = sm.start_new_cycle(tasks=tasks)
        assert len(cycle.tasks) == 7

    def test_cycle_count_increments(self, sm):
        assert sm.cycle_count == 0
        sm.start_new_cycle()
        assert sm.cycle_count == 1

        # 完了して次サイクル
        decision = Decision(decision_type=DecisionType.REJECT, reason="継続")
        sm.complete_cycle(decision)
        sm.start_new_cycle()
        assert sm.cycle_count == 2


# ============================================================
# フェーズ遷移テスト
# ============================================================


class TestPhaseTransitions:
    def test_plan_to_do(self, sm):
        sm.start_new_cycle()
        sm.transition(PDCAPhase.DO)
        assert sm.current_phase == PDCAPhase.DO

    def test_do_to_check(self, sm):
        sm.start_new_cycle()
        sm.transition(PDCAPhase.DO)
        sm.transition(PDCAPhase.CHECK)
        assert sm.current_phase == PDCAPhase.CHECK

    def test_check_to_act(self, sm):
        sm.start_new_cycle()
        sm.transition(PDCAPhase.DO)
        sm.transition(PDCAPhase.CHECK)
        sm.transition(PDCAPhase.ACT)
        assert sm.current_phase == PDCAPhase.ACT

    def test_full_cycle_transition(self, sm):
        sm.start_new_cycle()
        assert sm.current_phase == PDCAPhase.PLAN

        sm.transition(PDCAPhase.DO)
        assert sm.current_phase == PDCAPhase.DO

        sm.transition(PDCAPhase.CHECK)
        assert sm.current_phase == PDCAPhase.CHECK

        sm.transition(PDCAPhase.ACT)
        assert sm.current_phase == PDCAPhase.ACT

    def test_invalid_plan_to_check(self, sm):
        sm.start_new_cycle()
        with pytest.raises(InvalidTransitionError):
            sm.transition(PDCAPhase.CHECK)

    def test_invalid_do_to_act(self, sm):
        sm.start_new_cycle()
        sm.transition(PDCAPhase.DO)
        with pytest.raises(InvalidTransitionError):
            sm.transition(PDCAPhase.ACT)

    def test_invalid_plan_to_act(self, sm):
        sm.start_new_cycle()
        with pytest.raises(InvalidTransitionError):
            sm.transition(PDCAPhase.ACT)

    def test_cannot_transition_while_stopped(self, sm):
        sm.start_new_cycle()
        sm.stop(StopReason.USER_STOP)
        with pytest.raises(PDCAStateMachineError, match="停止中"):
            sm.transition(PDCAPhase.DO)

    def test_no_active_cycle(self, sm):
        with pytest.raises(PDCAStateMachineError, match="アクティブ"):
            sm.transition(PDCAPhase.DO)


# ============================================================
# サイクル完了テスト
# ============================================================


class TestCycleCompletion:
    def test_accept_completes_cycle(self, sm):
        tasks = [Task(id="T-1", title="t1", status=TaskStatus.IN_PROGRESS)]
        sm.start_new_cycle(tasks=tasks)
        decision = Decision(decision_type=DecisionType.ACCEPT, reason="DoD達成")
        result = sm.complete_cycle(decision)
        assert result is True
        assert sm.current_cycle.status == CycleStatus.COMPLETED
        assert sm.current_cycle.tasks[0].status == TaskStatus.COMPLETED

    def test_reject_allows_next_cycle(self, sm):
        sm.start_new_cycle()
        decision = Decision(decision_type=DecisionType.REJECT, reason="blocker残")
        result = sm.complete_cycle(decision)
        assert result is False
        assert sm.current_cycle.status == CycleStatus.COMPLETED

    def test_abort_marks_failed(self, sm):
        sm.start_new_cycle()
        decision = Decision(decision_type=DecisionType.ABORT, reason="重大問題")
        result = sm.complete_cycle(decision)
        assert result is False
        assert sm.current_cycle.status == CycleStatus.FAILED

    def test_milestone_completion(self, sm, milestone):
        sm.start_new_cycle()
        sm.complete_milestone()
        assert milestone.status == MilestoneStatus.COMPLETED
        assert milestone.completed_at is not None


# ============================================================
# 停止条件テスト（7条件）
# ============================================================


class TestStopConditions:
    def test_ci_consecutive_failure(self, sm):
        sm.start_new_cycle()
        reason = sm.check_stop_conditions(ci_failures=5)
        assert reason == StopReason.CI_CONSECUTIVE_FAILURE
        assert sm.is_stopped is True

    def test_ci_below_threshold_no_stop(self, sm):
        sm.start_new_cycle()
        reason = sm.check_stop_conditions(ci_failures=4)
        assert reason is None
        assert sm.is_stopped is False

    def test_diff_lines_total_exceeded(self, sm):
        sm.start_new_cycle()
        reason = sm.check_stop_conditions(diff_lines_total=2001)
        assert reason == StopReason.DIFF_SIZE_EXCEEDED

    def test_diff_lines_single_file_exceeded(self, sm):
        sm.start_new_cycle()
        reason = sm.check_stop_conditions(diff_lines_max_file=601)
        assert reason == StopReason.DIFF_SIZE_EXCEEDED

    def test_same_error_retry(self, sm):
        sm.start_new_cycle()
        # 1回目: OK
        reason = sm.check_stop_conditions(error_key="err-001")
        assert reason is None
        # 2回目: OK (閾値=2なので3回目で停止)
        reason = sm.check_stop_conditions(error_key="err-001")
        assert reason is None
        # 3回目: 停止
        reason = sm.check_stop_conditions(error_key="err-001")
        assert reason == StopReason.SAME_ERROR_RETRY

    def test_cycle_timeout(self, sm):
        # タイムアウトを非常に短く設定
        sm_short = PDCAStateMachine(
            Milestone(id="M-T", title="短タイムアウト"),
            thresholds={"cycle_timeout_seconds": 0},
        )
        sm_short.start_new_cycle()
        reason = sm_short.check_stop_conditions()
        assert reason == StopReason.CYCLE_TIMEOUT

    def test_critical_incident_immediate_stop(self, sm):
        sm.start_new_cycle()
        with pytest.raises(StopConditionError) as exc_info:
            sm.check_critical_incident("秘密情報露出の疑い")
        assert exc_info.value.reason == StopReason.CRITICAL_INCIDENT
        assert sm.is_stopped is True

    def test_audit_inconsistency_immediate_stop(self, sm):
        sm.start_new_cycle()
        with pytest.raises(StopConditionError) as exc_info:
            sm.check_audit_inconsistency("ハッシュ不一致")
        assert exc_info.value.reason == StopReason.AUDIT_LOG_INCONSISTENCY

    def test_user_stop(self, sm):
        sm.start_new_cycle()
        sm.user_stop()
        assert sm.is_stopped is True
        assert sm.stop_reason == StopReason.USER_STOP
        assert sm.current_cycle.status == CycleStatus.STOPPED


# ============================================================
# 再開テスト
# ============================================================


class TestResume:
    def test_resume_after_stop(self, sm):
        sm.start_new_cycle()
        sm.user_stop()
        assert sm.is_stopped is True
        sm.resume()
        assert sm.is_stopped is False
        assert sm.stop_reason is None

    def test_resume_when_not_stopped(self, sm):
        with pytest.raises(PDCAStateMachineError, match="停止中ではありません"):
            sm.resume()


# ============================================================
# ステータス取得テスト
# ============================================================


class TestGetStatus:
    def test_initial_status(self, sm):
        status = sm.get_status()
        assert status["milestone_id"] == "M-TEST"
        assert status["milestone_status"] == "open"
        assert status["cycle_count"] == 0
        assert status["current_phase"] is None
        assert status["is_stopped"] is False

    def test_status_after_cycle_start(self, sm):
        sm.start_new_cycle()
        status = sm.get_status()
        assert status["cycle_count"] == 1
        assert status["current_phase"] == "plan"
        assert status["current_cycle_number"] == 1
        assert status["current_cycle_status"] == "running"

    def test_status_after_stop(self, sm):
        sm.start_new_cycle()
        sm.user_stop()
        status = sm.get_status()
        assert status["is_stopped"] is True
        assert status["stop_reason"] == "user_stop"
