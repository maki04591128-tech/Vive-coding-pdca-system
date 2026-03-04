"""Proposal 30: Edge Case and Corner Case Exploration のテスト。"""

from __future__ import annotations

import pytest

from vibe_pdca.engine.edge_case_explorer import (
    BoundaryValueAnalyzer,
    EdgeCaseExplorer,
    EdgeCaseResult,
    EdgeCaseType,
    ExplorationReport,
    PropertyTestGenerator,
)


# ============================================================
# EdgeCaseType enum
# ============================================================


class TestEdgeCaseType:
    """EdgeCaseType 列挙型のテスト。"""

    def test_values(self) -> None:
        assert EdgeCaseType.BOUNDARY_VALUE == "boundary_value"
        assert EdgeCaseType.NULL_INPUT == "null_input"
        assert EdgeCaseType.OVERFLOW == "overflow"

    def test_all_members(self) -> None:
        assert len(EdgeCaseType) == 9


# ============================================================
# EdgeCaseResult データクラス
# ============================================================


class TestEdgeCaseResult:
    """EdgeCaseResult データクラスのテスト。"""

    def test_defaults(self) -> None:
        r = EdgeCaseResult(
            case_type=EdgeCaseType.BOUNDARY_VALUE,
            test_description="test",
            input_description="input",
            expected_behavior="pass",
            passed=True,
        )
        assert r.error_message == ""
        assert r.passed is True

    def test_with_error(self) -> None:
        r = EdgeCaseResult(
            case_type=EdgeCaseType.OVERFLOW,
            test_description="overflow test",
            input_description="x=999",
            expected_behavior="error",
            passed=False,
            error_message="値が範囲外",
        )
        assert r.error_message == "値が範囲外"


# ============================================================
# ExplorationReport データクラス
# ============================================================


class TestExplorationReport:
    """ExplorationReport データクラスのテスト。"""

    def test_defaults(self) -> None:
        rp = ExplorationReport(total_cases=10, passed=8, failed=2)
        assert rp.results == []
        assert rp.coverage_by_type == {}
        assert rp.risk_score == 0.0

    def test_with_values(self) -> None:
        rp = ExplorationReport(
            total_cases=5,
            passed=3,
            failed=2,
            risk_score=0.4,
            coverage_by_type={"boundary_value": 3},
        )
        assert rp.coverage_by_type["boundary_value"] == 3


# ============================================================
# BoundaryValueAnalyzer
# ============================================================


class TestBoundaryValueAnalyzer:
    """BoundaryValueAnalyzer のテスト。"""

    def setup_method(self) -> None:
        self.analyzer = BoundaryValueAnalyzer()

    def test_numeric_single_param(self) -> None:
        results = self.analyzer.analyze_numeric_params({"age": (0, 120)})
        assert len(results) == 6
        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]
        assert len(passed) >= 3
        assert len(failed) >= 2

    def test_numeric_multiple_params(self) -> None:
        results = self.analyzer.analyze_numeric_params({
            "x": (0, 100),
            "y": (-50, 50),
        })
        assert len(results) == 12

    def test_numeric_zero_in_range(self) -> None:
        results = self.analyzer.analyze_numeric_params({"val": (-10, 10)})
        zero_case = [r for r in results if "ゼロ" in r.test_description]
        assert len(zero_case) == 1
        assert zero_case[0].passed is True

    def test_numeric_zero_out_of_range(self) -> None:
        results = self.analyzer.analyze_numeric_params({"val": (1, 100)})
        zero_case = [r for r in results if "ゼロ" in r.test_description]
        assert len(zero_case) == 1
        assert zero_case[0].passed is False

    def test_string_single_param(self) -> None:
        results = self.analyzer.analyze_string_params({"name": 50})
        assert len(results) == 4
        types = {r.case_type for r in results}
        assert EdgeCaseType.EMPTY_COLLECTION in types
        assert EdgeCaseType.UNICODE in types

    def test_string_overflow_fails(self) -> None:
        results = self.analyzer.analyze_string_params({"name": 10})
        overflow = [r for r in results if r.case_type == EdgeCaseType.OVERFLOW]
        assert len(overflow) == 1
        assert overflow[0].passed is False

    def test_empty_params(self) -> None:
        assert self.analyzer.analyze_numeric_params({}) == []
        assert self.analyzer.analyze_string_params({}) == []


# ============================================================
# PropertyTestGenerator
# ============================================================


class TestPropertyTestGenerator:
    """PropertyTestGenerator のテスト。"""

    def setup_method(self) -> None:
        self.gen = PropertyTestGenerator()

    def test_generate_for_function(self) -> None:
        tests = self.gen.generate_for_function("add", {"a": "int", "b": "int"})
        assert len(tests) == 2
        assert "def test_add_a_property" in tests[0]
        assert "assert" in tests[0]

    def test_generate_for_unknown_type(self) -> None:
        tests = self.gen.generate_for_function("f", {"x": "CustomType"})
        assert len(tests) == 1
        assert "None" in tests[0]

    def test_generate_null_tests(self) -> None:
        tests = self.gen.generate_null_tests(["x", "y"])
        assert len(tests) == 2
        assert "None" in tests[0]
        assert "pytest.raises" in tests[0]

    def test_generate_null_tests_empty(self) -> None:
        assert self.gen.generate_null_tests([]) == []


# ============================================================
# EdgeCaseExplorer
# ============================================================


class TestEdgeCaseExplorer:
    """EdgeCaseExplorer のテスト。"""

    def setup_method(self) -> None:
        self.explorer = EdgeCaseExplorer(
            boundary_analyzer=BoundaryValueAnalyzer(),
            test_generator=PropertyTestGenerator(),
        )

    def test_explore_numeric(self) -> None:
        report = self.explorer.explore_numeric({"x": (0, 100)})
        assert report.total_cases == 6
        assert report.passed + report.failed == report.total_cases
        assert 0.0 <= report.risk_score <= 1.0

    def test_explore_strings(self) -> None:
        report = self.explorer.explore_strings({"name": 255})
        assert report.total_cases == 4
        assert report.passed + report.failed == report.total_cases

    def test_explore_all(self) -> None:
        report = self.explorer.explore_all(
            numeric_params={"x": (0, 10)},
            string_params={"s": 5},
        )
        assert report.total_cases == 10
        assert len(report.coverage_by_type) > 0

    def test_explore_all_empty(self) -> None:
        report = self.explorer.explore_all({}, {})
        assert report.total_cases == 0
        assert report.risk_score == 0.0

    def test_generate_report_markdown(self) -> None:
        report = self.explorer.explore_numeric({"val": (1, 100)})
        md = self.explorer.generate_report_markdown(report)
        assert "# エッジケース探索レポート" in md
        assert "リスクスコア" in md
        assert "失敗ケース" in md

    def test_report_coverage_types(self) -> None:
        report = self.explorer.explore_all(
            numeric_params={"n": (-10, 10)},
            string_params={"s": 100},
        )
        assert "boundary_value" in report.coverage_by_type
