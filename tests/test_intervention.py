"""介入操作のテスト。"""

import pytest

from vibe_pdca.engine.intervention import (
    IncidentPriority,
    InterventionManager,
)
from vibe_pdca.models.pdca import (
    Cycle,
    CycleStatus,
    Decision,
    DecisionType,
    Milestone,
    PDCAPhase,
    StopReason,
    Task,
    TaskStatus,
)

# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def manager():
    return InterventionManager()


@pytest.fixture
def stopped_milestone():
    return Milestone(
        id="ms-1",
        title="テストMS",
        cycles=[
            Cycle(
                cycle_number=1,
                phase=PDCAPhase.DO,
                status=CycleStatus.STOPPED,
                stop_reason=StopReason.CI_CONSECUTIVE_FAILURE,
                tasks=[
                    Task(id="t-1", title="タスク1", status=TaskStatus.IN_PROGRESS),
                ],
                decision=Decision(
                    decision_type=DecisionType.REJECT,
                    reason="CI失敗",
                ),
            ),
        ],
    )


@pytest.fixture
def clean_milestone():
    return Milestone(
        id="ms-2",
        title="クリーンMS",
        cycles=[
            Cycle(
                cycle_number=1,
                phase=PDCAPhase.ACT,
                status=CycleStatus.COMPLETED,
                tasks=[
                    Task(id="t-1", title="完了タスク", status=TaskStatus.COMPLETED),
                ],
            ),
        ],
    )


# ============================================================
# テスト: インシデント優先度
# ============================================================


class TestPriorityClassification:
    def test_critical_is_p0(self, manager, stopped_milestone):
        report = manager.analyze_stop(
            stopped_milestone, StopReason.CRITICAL_INCIDENT,
        )
        assert report.incident_priority == IncidentPriority.P0

    def test_audit_inconsistency_is_p0(self, manager, stopped_milestone):
        report = manager.analyze_stop(
            stopped_milestone, StopReason.AUDIT_LOG_INCONSISTENCY,
        )
        assert report.incident_priority == IncidentPriority.P0

    def test_ci_failure_is_p1(self, manager, stopped_milestone):
        report = manager.analyze_stop(
            stopped_milestone, StopReason.CI_CONSECUTIVE_FAILURE,
        )
        assert report.incident_priority == IncidentPriority.P1

    def test_timeout_is_p1(self, manager, stopped_milestone):
        report = manager.analyze_stop(
            stopped_milestone, StopReason.CYCLE_TIMEOUT,
        )
        assert report.incident_priority == IncidentPriority.P1

    def test_user_stop_is_p2(self, manager, stopped_milestone):
        report = manager.analyze_stop(
            stopped_milestone, StopReason.USER_STOP,
        )
        assert report.incident_priority == IncidentPriority.P2


# ============================================================
# テスト: 原因分析レポート
# ============================================================


class TestRootCauseAnalysis:
    def test_has_summary(self, manager, stopped_milestone):
        report = manager.analyze_stop(
            stopped_milestone, StopReason.CI_CONSECUTIVE_FAILURE,
        )
        assert report.root_cause.summary

    def test_has_contributing_factors(self, manager, stopped_milestone):
        report = manager.analyze_stop(
            stopped_milestone, StopReason.CI_CONSECUTIVE_FAILURE,
        )
        assert len(report.root_cause.contributing_factors) > 0

    def test_affected_resources(self, manager, stopped_milestone):
        report = manager.analyze_stop(
            stopped_milestone, StopReason.CI_CONSECUTIVE_FAILURE,
        )
        assert len(report.root_cause.affected_resources) > 0


# ============================================================
# テスト: ロールバック候補
# ============================================================


class TestRollbackCandidates:
    def test_generates_candidates(self, manager, clean_milestone):
        report = manager.analyze_stop(
            clean_milestone, StopReason.USER_STOP,
        )
        assert len(report.rollback_candidates) > 0

    def test_fallback_to_initial(self, manager):
        empty_ms = Milestone(id="ms-empty", title="Empty")
        report = manager.analyze_stop(empty_ms, StopReason.USER_STOP)
        assert len(report.rollback_candidates) == 1
        assert report.rollback_candidates[0].target_cycle == 0


# ============================================================
# テスト: 再開条件
# ============================================================


class TestResumeConditions:
    def test_ci_failure_conditions(self, manager, stopped_milestone):
        report = manager.analyze_stop(
            stopped_milestone, StopReason.CI_CONSECUTIVE_FAILURE,
        )
        assert len(report.resume_conditions) >= 2  # 固有 + 共通

    def test_critical_has_extra_conditions(self, manager, stopped_milestone):
        report = manager.analyze_stop(
            stopped_milestone, StopReason.CRITICAL_INCIDENT,
        )
        assert len(report.resume_conditions) >= 3


# ============================================================
# テスト: Markdownレポート
# ============================================================


class TestMarkdownReport:
    def test_to_markdown(self, manager, stopped_milestone):
        report = manager.analyze_stop(
            stopped_milestone, StopReason.CI_CONSECUTIVE_FAILURE,
        )
        md = report.to_markdown()
        assert "介入操作レポート" in md
        assert "原因分析" in md
        assert "ロールバック候補" in md
        assert "再開条件" in md

    def test_report_count(self, manager, stopped_milestone):
        manager.analyze_stop(stopped_milestone, StopReason.USER_STOP)
        manager.analyze_stop(stopped_milestone, StopReason.CYCLE_TIMEOUT)
        assert manager.report_count == 2


# ============================================================
# テスト: スレッドセーフティ
# ============================================================


class TestInterventionManagerThreadSafety:
    """InterventionManagerのスレッドセーフティテスト。"""

    def test_concurrent_analyze_stop(self):
        import threading

        manager = InterventionManager()
        n_threads = 10
        barrier = threading.Barrier(n_threads)

        milestone = Milestone(
            id="m-concurrent",
            title="concurrent test",
            cycles=[
                Cycle(
                    cycle_number=1,
                    phase=PDCAPhase.DO,
                    status=CycleStatus.STOPPED,
                    stop_reason=StopReason.USER_STOP,
                    tasks=[
                        Task(id="t-1", title="タスク1", status=TaskStatus.IN_PROGRESS),
                    ],
                ),
            ],
        )

        def worker():
            barrier.wait()
            manager.analyze_stop(milestone, StopReason.USER_STOP)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert manager.report_count == n_threads
