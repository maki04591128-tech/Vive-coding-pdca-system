"""LLMレスポンス品質スコアリングと自動リトライのテスト。"""

from __future__ import annotations

import json

import pytest

from vibe_pdca.engine.quality_scorer import (
    AutoRetryPolicy,
    CompletenessChecker,
    HallucinationDetector,
    ModelQualityTracker,
    QualityAwareRetrier,
    QualityDimension,
    QualityReport,
    QualityScore,
    StructuralValidator,
)


# ── QualityDimension ──


class TestQualityDimension:
    """QualityDimension列挙型のテスト。"""

    def test_values(self) -> None:
        assert QualityDimension.STRUCTURAL_VALIDITY == "structural_validity"
        assert QualityDimension.COMPLETENESS == "completeness"
        assert QualityDimension.CONSISTENCY == "consistency"
        assert QualityDimension.HALLUCINATION_FREE == "hallucination_free"

    def test_member_count(self) -> None:
        assert len(QualityDimension) == 4


# ── QualityScore ──


class TestQualityScore:
    """QualityScoreデータクラスのテスト。"""

    def test_default_issues(self) -> None:
        qs = QualityScore(dimension=QualityDimension.COMPLETENESS, score=0.8)
        assert qs.issues == []

    def test_with_issues(self) -> None:
        qs = QualityScore(
            dimension=QualityDimension.STRUCTURAL_VALIDITY,
            score=0.0,
            issues=["JSON解析エラー"],
        )
        assert qs.score == 0.0
        assert len(qs.issues) == 1


# ── QualityReport ──


class TestQualityReport:
    """QualityReportデータクラスのテスト。"""

    def test_defaults(self) -> None:
        report = QualityReport(
            scores=[],
            overall_score=0.8,
            is_acceptable=True,
        )
        assert report.threshold == 0.7
        assert report.retry_recommended is False
        assert report.timestamp > 0

    def test_custom_threshold(self) -> None:
        report = QualityReport(
            scores=[],
            overall_score=0.5,
            is_acceptable=False,
            threshold=0.6,
            retry_recommended=True,
        )
        assert report.threshold == 0.6
        assert report.retry_recommended is True


# ── StructuralValidator ──


class TestStructuralValidator:
    """StructuralValidatorのテスト。"""

    @pytest.fixture()
    def validator(self) -> StructuralValidator:
        return StructuralValidator()

    def test_validate_json_valid(self, validator: StructuralValidator) -> None:
        result = validator.validate_json('{"key": "value"}')
        assert result.score == 1.0
        assert result.issues == []
        assert result.dimension == QualityDimension.STRUCTURAL_VALIDITY

    def test_validate_json_invalid(self, validator: StructuralValidator) -> None:
        result = validator.validate_json("not json at all")
        assert result.score == 0.0
        assert len(result.issues) == 1
        assert "JSON解析エラー" in result.issues[0]

    def test_validate_required_keys_all_present(
        self, validator: StructuralValidator
    ) -> None:
        data = {"a": 1, "b": 2, "c": 3}
        result = validator.validate_required_keys(data, ["a", "b"])
        assert result.score == 1.0
        assert result.issues == []

    def test_validate_required_keys_some_missing(
        self, validator: StructuralValidator
    ) -> None:
        data = {"a": 1}
        result = validator.validate_required_keys(data, ["a", "b", "c"])
        assert result.score == pytest.approx(1 / 3)
        assert len(result.issues) == 1
        assert "b" in result.issues[0]
        assert "c" in result.issues[0]

    def test_validate_required_keys_empty_required(
        self, validator: StructuralValidator
    ) -> None:
        result = validator.validate_required_keys({"a": 1}, [])
        assert result.score == 1.0

    def test_validate_markdown_structure_all_present(
        self, validator: StructuralValidator
    ) -> None:
        md = "# 概要\n\nテスト\n\n## 詳細\n\n内容"
        result = validator.validate_markdown_structure(md, ["概要", "詳細"])
        assert result.score == 1.0

    def test_validate_markdown_structure_missing(
        self, validator: StructuralValidator
    ) -> None:
        md = "# 概要\n\nテスト"
        result = validator.validate_markdown_structure(md, ["概要", "詳細"])
        assert result.score == 0.5
        assert "詳細" in result.issues[0]

    def test_validate_markdown_structure_empty_required(
        self, validator: StructuralValidator
    ) -> None:
        result = validator.validate_markdown_structure("# Anything", [])
        assert result.score == 1.0


# ── CompletenessChecker ──


class TestCompletenessChecker:
    """CompletenessCheckerのテスト。"""

    @pytest.fixture()
    def checker(self) -> CompletenessChecker:
        return CompletenessChecker()

    def test_check_task_list_valid(self, checker: CompletenessChecker) -> None:
        tasks = [{"id": i} for i in range(3)]
        result = checker.check_task_list(tasks, min_tasks=1, max_tasks=5)
        assert result.score == 1.0
        assert result.dimension == QualityDimension.COMPLETENESS

    def test_check_task_list_empty(self, checker: CompletenessChecker) -> None:
        result = checker.check_task_list([], min_tasks=1)
        assert result.score == 0.0
        assert len(result.issues) == 1

    def test_check_task_list_too_few(self, checker: CompletenessChecker) -> None:
        tasks = [{"id": 1}]
        result = checker.check_task_list(tasks, min_tasks=3)
        assert result.score == pytest.approx(1 / 3)

    def test_check_task_list_too_many(self, checker: CompletenessChecker) -> None:
        tasks = [{"id": i} for i in range(10)]
        result = checker.check_task_list(tasks, min_tasks=1, max_tasks=5)
        assert result.score < 1.0
        assert "過多" in result.issues[0]

    def test_check_review_findings_complete(
        self, checker: CompletenessChecker
    ) -> None:
        findings = [{"severity": "high", "message": "issue"}]
        result = checker.check_review_findings(
            findings, required_fields=["severity", "message"]
        )
        assert result.score == 1.0

    def test_check_review_findings_empty(
        self, checker: CompletenessChecker
    ) -> None:
        result = checker.check_review_findings([], required_fields=["severity"])
        assert result.score == 0.0

    def test_check_review_findings_partial(
        self, checker: CompletenessChecker
    ) -> None:
        findings = [{"severity": "high"}, {"severity": "low", "message": "ok"}]
        result = checker.check_review_findings(
            findings, required_fields=["severity", "message"]
        )
        # 4 total fields, 3 present -> 0.75
        assert result.score == pytest.approx(0.75)

    def test_check_review_findings_no_required_fields(
        self, checker: CompletenessChecker
    ) -> None:
        result = checker.check_review_findings([{"a": 1}], required_fields=[])
        assert result.score == 1.0


# ── HallucinationDetector ──


class TestHallucinationDetector:
    """HallucinationDetectorのテスト。"""

    @pytest.fixture()
    def detector(self) -> HallucinationDetector:
        return HallucinationDetector()

    def test_check_file_references_all_known(
        self, detector: HallucinationDetector
    ) -> None:
        text = "See `src/main.py` for details."
        known = {"src/main.py"}
        result = detector.check_file_references(text, known)
        assert result.score == 1.0
        assert result.dimension == QualityDimension.HALLUCINATION_FREE

    def test_check_file_references_unknown(
        self, detector: HallucinationDetector
    ) -> None:
        text = "See `src/main.py` and `src/ghost.py`"
        known = {"src/main.py"}
        result = detector.check_file_references(text, known)
        assert result.score == 0.5
        assert "ghost.py" in result.issues[0]

    def test_check_file_references_no_known(
        self, detector: HallucinationDetector
    ) -> None:
        result = detector.check_file_references("some text", set())
        assert result.score == 1.0

    def test_check_file_references_no_refs(
        self, detector: HallucinationDetector
    ) -> None:
        result = detector.check_file_references("no file references here", {"a.py"})
        assert result.score == 1.0

    def test_check_api_references_all_known(
        self, detector: HallucinationDetector
    ) -> None:
        text = "Call fetch_data() and process()"
        known = {"fetch_data", "process"}
        result = detector.check_api_references(text, known)
        assert result.score == 1.0

    def test_check_api_references_unknown(
        self, detector: HallucinationDetector
    ) -> None:
        text = "Call fetch_data() and mystery_func()"
        known = {"fetch_data"}
        result = detector.check_api_references(text, known)
        assert result.score == 0.5
        assert "mystery_func" in result.issues[0]

    def test_check_api_references_no_known(
        self, detector: HallucinationDetector
    ) -> None:
        result = detector.check_api_references("some text", set())
        assert result.score == 1.0


# ── AutoRetryPolicy ──


class TestAutoRetryPolicy:
    """AutoRetryPolicyのテスト。"""

    def test_defaults(self) -> None:
        policy = AutoRetryPolicy()
        assert policy.max_retries == 3
        assert policy.quality_threshold == 0.7
        assert policy.include_error_feedback is True

    def test_custom(self) -> None:
        policy = AutoRetryPolicy(
            max_retries=5, quality_threshold=0.9, include_error_feedback=False
        )
        assert policy.max_retries == 5
        assert policy.quality_threshold == 0.9
        assert policy.include_error_feedback is False


# ── QualityAwareRetrier ──


class TestQualityAwareRetrier:
    """QualityAwareRetrierのテスト。"""

    @pytest.fixture()
    def retrier(self) -> QualityAwareRetrier:
        return QualityAwareRetrier(
            validators=[StructuralValidator()],
            policy=AutoRetryPolicy(quality_threshold=0.7),
        )

    def test_evaluate_valid_json(self, retrier: QualityAwareRetrier) -> None:
        report = retrier.evaluate('{"key": "value"}', context={})
        assert report.is_acceptable is True
        assert report.overall_score == 1.0

    def test_evaluate_invalid_json(self, retrier: QualityAwareRetrier) -> None:
        report = retrier.evaluate("not json", context={})
        assert report.is_acceptable is False
        assert report.overall_score == 0.0

    def test_evaluate_with_required_keys(self) -> None:
        retrier = QualityAwareRetrier(validators=[StructuralValidator()])
        text = json.dumps({"a": 1, "b": 2})
        report = retrier.evaluate(text, context={"required_keys": ["a", "b", "c"]})
        # JSON valid (1.0) + keys (2/3) -> avg
        assert report.overall_score == pytest.approx((1.0 + 2 / 3) / 2)

    def test_evaluate_multiple_validators(self) -> None:
        retrier = QualityAwareRetrier(
            validators=[StructuralValidator(), CompletenessChecker()],
        )
        text = json.dumps({"tasks": []})
        context = {"tasks": [{"id": 1}, {"id": 2}], "min_tasks": 1, "max_tasks": 5}
        report = retrier.evaluate(text, context=context)
        assert report.is_acceptable is True

    def test_should_retry_acceptable(self) -> None:
        retrier = QualityAwareRetrier(validators=[])
        report = QualityReport(
            scores=[], overall_score=0.8, is_acceptable=True
        )
        assert retrier.should_retry(report, attempt=1) is False

    def test_should_retry_not_acceptable_within_limit(self) -> None:
        retrier = QualityAwareRetrier(
            validators=[], policy=AutoRetryPolicy(max_retries=3)
        )
        report = QualityReport(
            scores=[], overall_score=0.3, is_acceptable=False
        )
        assert retrier.should_retry(report, attempt=1) is True
        assert retrier.should_retry(report, attempt=2) is True

    def test_should_retry_not_acceptable_at_limit(self) -> None:
        retrier = QualityAwareRetrier(
            validators=[], policy=AutoRetryPolicy(max_retries=3)
        )
        report = QualityReport(
            scores=[], overall_score=0.3, is_acceptable=False
        )
        assert retrier.should_retry(report, attempt=3) is False

    def test_build_retry_feedback_with_issues(self) -> None:
        retrier = QualityAwareRetrier(validators=[])
        report = QualityReport(
            scores=[
                QualityScore(
                    dimension=QualityDimension.STRUCTURAL_VALIDITY,
                    score=0.0,
                    issues=["JSON解析エラー: Expecting value"],
                ),
            ],
            overall_score=0.0,
            is_acceptable=False,
        )
        feedback = retrier.build_retry_feedback(report)
        assert "品質問題が検出されました" in feedback
        assert "JSON解析エラー" in feedback
        assert "structural_validity" in feedback

    def test_build_retry_feedback_disabled(self) -> None:
        retrier = QualityAwareRetrier(
            validators=[],
            policy=AutoRetryPolicy(include_error_feedback=False),
        )
        report = QualityReport(
            scores=[
                QualityScore(
                    dimension=QualityDimension.COMPLETENESS,
                    score=0.0,
                    issues=["タスク数が不足"],
                ),
            ],
            overall_score=0.0,
            is_acceptable=False,
        )
        assert retrier.build_retry_feedback(report) == ""

    def test_evaluate_no_scores_returns_acceptable(self) -> None:
        """バリデータがスコアを返さない場合、overall=1.0 で acceptable。"""
        retrier = QualityAwareRetrier(validators=[])
        report = retrier.evaluate("anything", context={})
        assert report.overall_score == 1.0
        assert report.is_acceptable is True


# ── ModelQualityTracker ──


class TestModelQualityTracker:
    """ModelQualityTrackerのテスト。"""

    @pytest.fixture()
    def tracker(self) -> ModelQualityTracker:
        return ModelQualityTracker()

    def _make_report(
        self, score: float, acceptable: bool = True
    ) -> QualityReport:
        return QualityReport(
            scores=[],
            overall_score=score,
            is_acceptable=acceptable,
        )

    def test_record_and_get_model_stats(
        self, tracker: ModelQualityTracker
    ) -> None:
        tracker.record("gpt-4", "planner", self._make_report(0.9))
        tracker.record("gpt-4", "reviewer", self._make_report(0.7))
        tracker.record("gpt-4", "planner", self._make_report(0.5, acceptable=False))

        stats = tracker.get_model_stats("gpt-4")
        assert stats["total_evaluations"] == 3
        assert stats["average_score"] == pytest.approx((0.9 + 0.7 + 0.5) / 3)
        assert stats["acceptance_rate"] == pytest.approx(2 / 3)
        assert "planner" in stats["role_breakdown"]
        assert "reviewer" in stats["role_breakdown"]

    def test_get_model_stats_empty(self, tracker: ModelQualityTracker) -> None:
        stats = tracker.get_model_stats("unknown")
        assert stats["total_evaluations"] == 0
        assert stats["average_score"] == 0.0

    def test_record_and_get_role_stats(
        self, tracker: ModelQualityTracker
    ) -> None:
        tracker.record("gpt-4", "planner", self._make_report(0.8))
        tracker.record("claude", "planner", self._make_report(0.6, acceptable=False))

        stats = tracker.get_role_stats("planner")
        assert stats["total_evaluations"] == 2
        assert stats["average_score"] == pytest.approx(0.7)
        assert stats["acceptance_rate"] == pytest.approx(0.5)
        assert "gpt-4" in stats["model_breakdown"]
        assert "claude" in stats["model_breakdown"]

    def test_get_role_stats_empty(self, tracker: ModelQualityTracker) -> None:
        stats = tracker.get_role_stats("unknown")
        assert stats["total_evaluations"] == 0
        assert stats["average_score"] == 0.0
