"""共有フィクスチャデータの読み込み・モデル生成テスト。

tests/fixtures/ 配下のJSONデータを使用し、
Pydanticモデルへの変換が正しく動作することを検証する。
"""

from vibe_pdca.models.pdca import (
    Goal,
    ReviewCategory,
    ReviewFinding,
    Severity,
)

# ============================================================
# フィクスチャからのGoal生成テスト
# ============================================================


class TestGoalFixture:
    """sample_goal.json からGoalモデルを生成するテスト。"""

    def test_load_goal_data(self, sample_goal_data: dict) -> None:
        """JSONフィクスチャからゴールデータが正しく読み込まれること。"""
        assert sample_goal_data["id"] == "G-001"
        assert len(sample_goal_data["acceptance_criteria"]) == 3

    def test_create_goal_from_fixture(self, sample_goal_data: dict) -> None:
        """JSONデータからGoalモデルが正しく生成されること。"""
        goal = Goal(**sample_goal_data)
        assert goal.id == "G-001"
        assert goal.purpose == "ユーザー管理機能を持つWebアプリケーションを構築する"
        assert len(goal.acceptance_criteria) == 3
        assert len(goal.constraints) == 2

    def test_goal_serialization_roundtrip(self, sample_goal_data: dict) -> None:
        """Goal→JSON→Goal の往復変換が一致すること。"""
        goal = Goal(**sample_goal_data)
        json_str = goal.model_dump_json()
        restored = Goal.model_validate_json(json_str)
        assert restored.id == goal.id
        assert restored.purpose == goal.purpose
        assert restored.acceptance_criteria == goal.acceptance_criteria


# ============================================================
# フィクスチャからのReviewFinding生成テスト
# ============================================================


class TestReviewFindingFixture:
    """sample_review_findings.json からReviewFindingモデルを生成するテスト。"""

    def test_load_review_findings_data(
        self, sample_review_findings_data: list,
    ) -> None:
        """JSONフィクスチャからレビュー指摘データが正しく読み込まれること。"""
        assert len(sample_review_findings_data) == 3
        assert sample_review_findings_data[0]["id"] == "RF-001"

    def test_create_findings_from_fixture(
        self, sample_review_findings_data: list,
    ) -> None:
        """JSONデータからReviewFindingモデルが正しく生成されること。"""
        findings = [
            ReviewFinding(**item) for item in sample_review_findings_data
        ]
        assert len(findings) == 3
        assert findings[0].severity == Severity.MAJOR
        assert findings[1].category == ReviewCategory.UX
        assert findings[2].severity == Severity.BLOCKER

    def test_severity_distribution(
        self, sample_review_findings_data: list,
    ) -> None:
        """フィクスチャデータの重大度が想定通りであること。"""
        findings = [
            ReviewFinding(**item) for item in sample_review_findings_data
        ]
        severities = [f.severity for f in findings]
        assert Severity.BLOCKER in severities
        assert Severity.MAJOR in severities
        assert Severity.MINOR in severities
