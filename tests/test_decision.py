"""ACTフェーズ（ActDecisionMaker）のテスト。"""

import pytest

from vibe_pdca.engine.checker import CheckResult, CIStatus, CISummary
from vibe_pdca.engine.decision import ActDecisionMaker, ProgressReport
from vibe_pdca.models.pdca import (
    Cycle,
    DecisionType,
    DoDItem,
    Milestone,
    ReviewSummary,
    Task,
    TaskStatus,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def decision_maker():
    return ActDecisionMaker()


def _make_check_result(
    *,
    dod_achieved: bool = True,
    blocker_count: int = 0,
    major_count: int = 0,
    minor_count: int = 0,
    ci_all_passed: bool = True,
    dod_unmet_reasons: list[str] | None = None,
) -> CheckResult:
    return CheckResult(
        review_summary=ReviewSummary(
            blocker_count=blocker_count,
            major_count=major_count,
            minor_count=minor_count,
            dod_achieved=dod_achieved,
            dod_unmet_reasons=dod_unmet_reasons or [],
        ),
        ci_summary=CISummary(
            total_jobs=3,
            passed_jobs=3 if ci_all_passed else 1,
            failed_jobs=0 if ci_all_passed else 2,
            overall_status=CIStatus.SUCCESS if ci_all_passed else CIStatus.FAILURE,
        ),
        dod_achieved=dod_achieved,
        dod_unmet_reasons=dod_unmet_reasons or [],
    )


# ============================================================
# テスト: 判定ロジック
# ============================================================


class TestDecisionMaking:
    def test_accept_when_dod_achieved_ci_passed(self, decision_maker):
        result = _make_check_result(dod_achieved=True, ci_all_passed=True)
        decision = decision_maker.make_decision(result)
        assert decision.decision_type == DecisionType.ACCEPT

    def test_reject_with_blockers(self, decision_maker):
        result = _make_check_result(
            dod_achieved=False, blocker_count=2, ci_all_passed=True,
        )
        decision = decision_maker.make_decision(result)
        assert decision.decision_type == DecisionType.REJECT
        assert "ブロッカー" in decision.reason

    def test_degrade_on_repeated_ci_failures(self, decision_maker):
        result = _make_check_result(dod_achieved=False, ci_all_passed=False)
        history = ["error-1", "error-2", "error-3"]
        decision = decision_maker.make_decision(result, failure_history=history)
        assert decision.decision_type == DecisionType.DEGRADE

    def test_defer_with_many_major_findings(self, decision_maker):
        result = _make_check_result(
            dod_achieved=False, major_count=6, ci_all_passed=True,
        )
        decision = decision_maker.make_decision(result)
        assert decision.decision_type == DecisionType.DEFER

    def test_reject_on_ci_failure(self, decision_maker):
        result = _make_check_result(dod_achieved=False, ci_all_passed=False)
        decision = decision_maker.make_decision(result)
        assert decision.decision_type == DecisionType.REJECT

    def test_reject_on_dod_unmet(self, decision_maker):
        result = _make_check_result(
            dod_achieved=False,
            ci_all_passed=True,
            dod_unmet_reasons=["未完了タスク: 1件"],
        )
        decision = decision_maker.make_decision(result)
        assert decision.decision_type == DecisionType.REJECT
        assert "DoD未達" in decision.reason

    def test_decision_has_required_fields(self, decision_maker):
        """§6.5: 決定ログに必須記録する項目の確認。"""
        result = _make_check_result(dod_achieved=True, ci_all_passed=True)
        decision = decision_maker.make_decision(result)
        assert decision.reason != ""
        assert decision.impact_scope != ""


# ============================================================
# テスト: 進捗レポート
# ============================================================


class TestProgressReport:
    def test_generate_report(self, decision_maker):
        milestone = Milestone(
            id="ms-001",
            title="テストMS",
            dod=[
                DoDItem(description="条件1", achieved=True),
                DoDItem(description="条件2", achieved=False),
            ],
            cycles=[
                Cycle(
                    cycle_number=1,
                    tasks=[
                        Task(id="t-1", title="T1", status=TaskStatus.COMPLETED),
                        Task(id="t-2", title="T2", status=TaskStatus.IN_PROGRESS),
                    ],
                ),
            ],
        )
        check_result = _make_check_result(dod_achieved=False)
        from vibe_pdca.models.pdca import Decision

        decision = Decision(
            decision_type=DecisionType.REJECT,
            reason="テスト",
            next_cycle_policy="改善継続",
        )
        report = decision_maker.generate_progress_report(
            milestone, 1, decision, check_result,
        )
        assert isinstance(report, ProgressReport)
        assert report.milestone_id == "ms-001"
        assert report.dod_progress == 0.5
        assert report.completed_tasks == 1
        assert report.total_tasks == 2

    def test_report_to_markdown(self, decision_maker):
        milestone = Milestone(
            id="ms-001", title="テスト",
            dod=[DoDItem(description="条件", achieved=True)],
            cycles=[Cycle(cycle_number=1, tasks=[])],
        )
        check_result = _make_check_result(dod_achieved=True)
        from vibe_pdca.models.pdca import Decision

        decision = Decision(
            decision_type=DecisionType.ACCEPT, reason="完了",
        )
        report = decision_maker.generate_progress_report(
            milestone, 1, decision, check_result,
        )
        md = report.to_markdown()
        assert "サイクル 1" in md
        assert "テスト" in md
