"""エッジケース・コーナーケース探索 – 境界値分析・プロパティテスト生成・リスク評価。

Proposal 30: Edge Case and Corner Case Exploration。

入力: パラメータ定義（数値範囲・文字列長制約・型情報）
出力: テストケース一覧・探索レポート・リスクスコア
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# 列挙型
# ============================================================


class EdgeCaseType(enum.StrEnum):
    """エッジケースの分類。"""

    BOUNDARY_VALUE = "boundary_value"
    NULL_INPUT = "null_input"
    TYPE_MISMATCH = "type_mismatch"
    OVERFLOW = "overflow"
    EMPTY_COLLECTION = "empty_collection"
    CONCURRENCY = "concurrency"
    NEGATIVE_VALUE = "negative_value"
    UNICODE = "unicode"
    LARGE_INPUT = "large_input"


# ============================================================
# データクラス
# ============================================================


@dataclass
class EdgeCaseResult:
    """個別エッジケースのテスト結果。"""

    case_type: EdgeCaseType
    test_description: str
    input_description: str
    expected_behavior: str
    passed: bool
    error_message: str = ""


@dataclass
class ExplorationReport:
    """エッジケース探索レポート。"""

    total_cases: int
    passed: int
    failed: int
    results: list[EdgeCaseResult] = field(default_factory=list)
    coverage_by_type: dict[str, int] = field(default_factory=dict)
    risk_score: float = 0.0  # 0.0 ~ 1.0


# ============================================================
# BoundaryValueAnalyzer – 境界値分析
# ============================================================


class BoundaryValueAnalyzer:
    """数値・文字列パラメータの境界値テストケースを生成する。"""

    def analyze_numeric_params(
        self,
        params: dict[str, tuple[float, float]],
    ) -> list[EdgeCaseResult]:
        """数値パラメータの境界値テストケースを生成する。

        Parameters
        ----------
        params:
            パラメータ名 → (最小値, 最大値) のマッピング。

        Returns
        -------
        list[EdgeCaseResult]
            各境界値に対するテスト結果。
        """
        results: list[EdgeCaseResult] = []
        for name, (min_val, max_val) in params.items():
            test_cases: list[tuple[str, float, EdgeCaseType, bool]] = [
                (f"{name}: 最小値 ({min_val})", min_val, EdgeCaseType.BOUNDARY_VALUE, True),
                (f"{name}: 最大値 ({max_val})", max_val, EdgeCaseType.BOUNDARY_VALUE, True),
                (f"{name}: 最小値-1 ({min_val - 1})", min_val - 1, EdgeCaseType.OVERFLOW, False),
                (f"{name}: 最大値+1 ({max_val + 1})", max_val + 1, EdgeCaseType.OVERFLOW, False),
                (f"{name}: ゼロ (0)", 0, EdgeCaseType.BOUNDARY_VALUE, min_val <= 0 <= max_val),
                (f"{name}: 負値 (-1)", -1, EdgeCaseType.NEGATIVE_VALUE, min_val <= -1),
            ]
            for desc, value, case_type, expected_pass in test_cases:
                results.append(
                    EdgeCaseResult(
                        case_type=case_type,
                        test_description=desc,
                        input_description=f"{name}={value}",
                        expected_behavior="範囲内" if expected_pass else "範囲外エラー",
                        passed=expected_pass,
                    )
                )
        logger.info("数値境界値分析完了: %d パラメータ → %d ケース", len(params), len(results))
        return results

    def analyze_string_params(
        self,
        params: dict[str, int],
    ) -> list[EdgeCaseResult]:
        """文字列パラメータの境界値テストケースを生成する。

        Parameters
        ----------
        params:
            パラメータ名 → 最大文字列長 のマッピング。

        Returns
        -------
        list[EdgeCaseResult]
            各境界値に対するテスト結果。
        """
        results: list[EdgeCaseResult] = []
        for name, max_length in params.items():
            test_cases: list[tuple[str, str, EdgeCaseType, bool]] = [
                (
                    f"{name}: 空文字列",
                    "",
                    EdgeCaseType.EMPTY_COLLECTION,
                    True,
                ),
                (
                    f"{name}: 最大長 ({max_length}文字)",
                    "a" * max_length,
                    EdgeCaseType.BOUNDARY_VALUE,
                    True,
                ),
                (
                    f"{name}: 最大長+1 ({max_length + 1}文字)",
                    "a" * (max_length + 1),
                    EdgeCaseType.OVERFLOW,
                    False,
                ),
                (
                    f"{name}: Unicode文字列",
                    "こんにちは世界🌍",
                    EdgeCaseType.UNICODE,
                    True,
                ),
            ]
            for desc, value, case_type, expected_pass in test_cases:
                results.append(
                    EdgeCaseResult(
                        case_type=case_type,
                        test_description=desc,
                        input_description=f"{name}='{value[:20]}{'…' if len(value) > 20 else ''}'",
                        expected_behavior="有効" if expected_pass else "長さ超過エラー",
                        passed=expected_pass,
                    )
                )
        logger.info("文字列境界値分析完了: %d パラメータ → %d ケース", len(params), len(results))
        return results


# ============================================================
# PropertyTestGenerator – プロパティテスト生成
# ============================================================


class PropertyTestGenerator:
    """関数シグネチャからプロパティベーステストのテンプレートを生成する。"""

    _TYPE_GENERATORS: dict[str, str] = {
        "int": "random.randint(-1000, 1000)",
        "float": "random.uniform(-1e6, 1e6)",
        "str": "''.join(random.choices(string.ascii_letters, k=random.randint(0, 100)))",
        "bool": "random.choice([True, False])",
        "list": "[random.randint(0, 100) for _ in range(random.randint(0, 50))]",
    }

    def generate_for_function(
        self,
        func_name: str,
        param_types: dict[str, str],
    ) -> list[str]:
        """関数に対するプロパティベーステストコードを生成する。

        Parameters
        ----------
        func_name:
            テスト対象関数名。
        param_types:
            パラメータ名 → 型名 のマッピング。

        Returns
        -------
        list[str]
            テストコード文字列のリスト。
        """
        tests: list[str] = []
        for param_name, param_type in param_types.items():
            generator = self._TYPE_GENERATORS.get(param_type, "None")
            test_code = (
                f"def test_{func_name}_{param_name}_property():\n"
                f"    import random, string\n"
                f"    for _ in range(100):\n"
                f"        val = {generator}\n"
                f"        result = {func_name}({param_name}=val)\n"
                f"        assert result is not None, "
                f"f\"{func_name}({param_name}={{val}}) returned None\"\n"
            )
            tests.append(test_code)

        logger.info(
            "プロパティテスト生成: %s → %d テスト",
            func_name,
            len(tests),
        )
        return tests

    def generate_null_tests(self, param_names: list[str]) -> list[str]:
        """各パラメータに None を渡すテストコードを生成する。

        Parameters
        ----------
        param_names:
            テスト対象パラメータ名のリスト。

        Returns
        -------
        list[str]
            テストコード文字列のリスト。
        """
        tests: list[str] = []
        for name in param_names:
            test_code = (
                f"def test_{name}_null():\n"
                f"    import pytest\n"
                f"    with pytest.raises((TypeError, ValueError)):\n"
                f"        func({name}=None)\n"
            )
            tests.append(test_code)
        return tests


# ============================================================
# EdgeCaseExplorer – メインオーケストレータ
# ============================================================


class EdgeCaseExplorer:
    """エッジケース探索のメインオーケストレータ。"""

    def __init__(
        self,
        boundary_analyzer: BoundaryValueAnalyzer,
        test_generator: PropertyTestGenerator,
    ) -> None:
        self._boundary_analyzer = boundary_analyzer
        self._test_generator = test_generator

    def _build_report(self, results: list[EdgeCaseResult]) -> ExplorationReport:
        """テスト結果からレポートを構築する。"""
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        coverage: dict[str, int] = {}
        for r in results:
            key = r.case_type.value
            coverage[key] = coverage.get(key, 0) + 1
        risk_score = failed / len(results) if results else 0.0
        return ExplorationReport(
            total_cases=len(results),
            passed=passed,
            failed=failed,
            results=results,
            coverage_by_type=coverage,
            risk_score=round(risk_score, 4),
        )

    def explore_numeric(
        self,
        params: dict[str, tuple[float, float]],
    ) -> ExplorationReport:
        """数値パラメータのエッジケースを探索する。"""
        results = self._boundary_analyzer.analyze_numeric_params(params)
        report = self._build_report(results)
        logger.info("数値探索完了: risk_score=%.4f", report.risk_score)
        return report

    def explore_strings(
        self,
        params: dict[str, int],
    ) -> ExplorationReport:
        """文字列パラメータのエッジケースを探索する。"""
        results = self._boundary_analyzer.analyze_string_params(params)
        report = self._build_report(results)
        logger.info("文字列探索完了: risk_score=%.4f", report.risk_score)
        return report

    def explore_all(
        self,
        numeric_params: dict[str, tuple[float, float]],
        string_params: dict[str, int],
    ) -> ExplorationReport:
        """数値・文字列パラメータを一括探索する。"""
        results: list[EdgeCaseResult] = []
        results.extend(self._boundary_analyzer.analyze_numeric_params(numeric_params))
        results.extend(self._boundary_analyzer.analyze_string_params(string_params))
        report = self._build_report(results)
        logger.info("一括探索完了: risk_score=%.4f", report.risk_score)
        return report

    def generate_report_markdown(self, report: ExplorationReport) -> str:
        """ExplorationReport を Markdown 形式で出力する。"""
        lines: list[str] = [
            "# エッジケース探索レポート\n",
            f"- **総テスト数:** {report.total_cases}",
            f"- **成功:** {report.passed}",
            f"- **失敗:** {report.failed}",
            f"- **リスクスコア:** {report.risk_score:.4f}\n",
            "## カバレッジ（タイプ別）\n",
            "| タイプ | 件数 |",
            "|--------|------|",
        ]
        for case_type, count in sorted(report.coverage_by_type.items()):
            lines.append(f"| {case_type} | {count} |")

        lines.append("\n## 失敗ケース\n")
        failed = [r for r in report.results if not r.passed]
        if not failed:
            lines.append("なし\n")
        else:
            for r in failed:
                lines.append(
                    f"- **{r.test_description}** ({r.case_type.value}): "
                    f"{r.input_description} → {r.expected_behavior}"
                )
                if r.error_message:
                    lines.append(f"  - エラー: {r.error_message}")

        return "\n".join(lines)
