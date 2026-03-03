"""要件定義確定フローのテスト。"""

import pytest

from vibe_pdca.engine.requirements import (
    GapCategory,
    RequirementFinalizer,
    RequirementStatus,
)
from vibe_pdca.models.pdca import Goal, ReviewCategory, ReviewFinding, Severity

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def finalizer():
    return RequirementFinalizer()


@pytest.fixture
def complete_goal():
    return Goal(
        id="goal-1",
        purpose="テストシステムの構築",
        acceptance_criteria=[
            "全テストが通過すること",
            "カバレッジ80%以上",
            "ドキュメントが完備されていること",
        ],
        constraints=["Python 3.12以上"],
        prohibitions=["外部DB禁止"],
    )


@pytest.fixture
def incomplete_goal():
    return Goal(
        id="goal-2",
        purpose="テスト",
        acceptance_criteria=["OK"],
    )


# ============================================================
# テスト: 欠落検出
# ============================================================


class TestGapDetection:
    def test_complete_goal_no_gaps(self, finalizer, complete_goal):
        gaps = finalizer.detect_gaps(complete_goal)
        assert len(gaps) == 0

    def test_incomplete_goal_has_gaps(self, finalizer, incomplete_goal):
        gaps = finalizer.detect_gaps(incomplete_goal)
        assert len(gaps) > 0

    def test_missing_constraints(self, finalizer):
        goal = Goal(
            id="g-1",
            purpose="テスト",
            acceptance_criteria=[
                "条件1が達成されること",
                "条件2が達成されること",
                "条件3が達成されること",
            ],
            prohibitions=["禁止事項あり"],
        )
        gaps = finalizer.detect_gaps(goal)
        categories = [g.category for g in gaps]
        assert GapCategory.AMBIGUOUS_CONSTRAINT in categories

    def test_missing_prohibitions(self, finalizer):
        goal = Goal(
            id="g-1",
            purpose="テスト",
            acceptance_criteria=[
                "条件1が達成されること",
                "条件2が達成されること",
                "条件3が達成されること",
            ],
            constraints=["制約あり"],
        )
        gaps = finalizer.detect_gaps(goal)
        categories = [g.category for g in gaps]
        assert GapCategory.MISSING_PROHIBITION in categories

    def test_short_acceptance_criteria(self, finalizer):
        goal = Goal(
            id="g-1",
            purpose="テスト",
            acceptance_criteria=["短い", "OK", "テストが全て通過すること"],
            constraints=["制約"],
            prohibitions=["禁止"],
        )
        gaps = finalizer.detect_gaps(goal)
        assert any(g.category == GapCategory.AMBIGUOUS_CONSTRAINT for g in gaps)


# ============================================================
# テスト: 差分質問
# ============================================================


class TestDiffQuestions:
    def test_generate_questions(self, finalizer, incomplete_goal):
        finalizer.detect_gaps(incomplete_goal)
        questions = finalizer.generate_diff_questions(incomplete_goal)
        assert len(questions) > 0
        assert all(q.question for q in questions)

    def test_answer_question(self, finalizer, incomplete_goal):
        finalizer.detect_gaps(incomplete_goal)
        questions = finalizer.generate_diff_questions(incomplete_goal)
        result = finalizer.answer_question(questions[0].id, "回答テスト")
        assert result is True
        assert questions[0].resolved

    def test_answer_unknown_question(self, finalizer):
        result = finalizer.answer_question("unknown-id", "回答")
        assert result is False


# ============================================================
# テスト: 確定フロー
# ============================================================


class TestFinalization:
    def test_approve_with_no_issues(self, finalizer, complete_goal):
        finalizer.detect_gaps(complete_goal)
        result = finalizer.finalize(complete_goal, review_findings=[])
        assert result.can_start_pdca
        assert result.status == RequirementStatus.APPROVED

    def test_reject_with_blockers(self, finalizer, complete_goal):
        findings = [
            ReviewFinding(
                id="f-1",
                reviewer_role="PM",
                severity=Severity.BLOCKER,
                category=ReviewCategory.CORRECTNESS,
                description="重大な問題",
            ),
        ]
        finalizer.detect_gaps(complete_goal)
        result = finalizer.finalize(complete_goal, review_findings=findings)
        assert not result.can_start_pdca
        assert result.blocker_count == 1

    def test_reject_with_unresolved_gaps(self, finalizer, incomplete_goal):
        finalizer.detect_gaps(incomplete_goal)
        result = finalizer.finalize(incomplete_goal, review_findings=[])
        assert not result.can_start_pdca
        assert len(result.unresolved_gaps) > 0
