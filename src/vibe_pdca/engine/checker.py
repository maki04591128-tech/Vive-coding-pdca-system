"""CHECKフェーズ実行 – CI結果収集・5ペルソナレビュー・DoD判定。

M2 タスク 2-3: 要件定義書 §6.4, §8 準拠。

入力: PR差分・CI結果・DoD・関連ドキュメント差分
実施: 自動チェック（CI結果の収集と要約）、5ペルソナレビュー、指摘の重複排除と優先度付け
出力: 統合レビューサマリ（重大度別の指摘一覧）、DoD達成判定
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from vibe_pdca.models.pdca import (
    DoDItem,
    ReviewSummary,
    Task,
    TaskStatus,
)

logger = logging.getLogger(__name__)


class CIStatus(StrEnum):
    """CI実行結果のステータス。"""

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    CANCELLED = "cancelled"
    PENDING = "pending"


class CIFailureCategory(StrEnum):
    """CI失敗の分類（§A7 CI失敗分類ロジック）。"""

    LINT = "lint"
    TYPE_CHECK = "type_check"
    UNIT_TEST = "unit_test"
    INTEGRATION_TEST = "integration_test"
    SECURITY_SCAN = "security_scan"
    BUILD = "build"
    DEPENDENCY = "dependency"
    INFRASTRUCTURE = "infrastructure"
    UNKNOWN = "unknown"


@dataclass
class CIResult:
    """CI実行結果の1件。"""

    job_name: str
    status: CIStatus
    failure_category: CIFailureCategory | None = None
    error_message: str = ""
    duration_seconds: float = 0.0
    log_url: str = ""


@dataclass
class CheckContext:
    """CHECKフェーズの入力コンテキスト。"""

    tasks: list[Task]
    ci_results: list[CIResult] = field(default_factory=list)
    diff_summary: str = ""
    dod_items: list[DoDItem] = field(default_factory=list)


@dataclass
class CheckResult:
    """CHECKフェーズの出力。"""

    review_summary: ReviewSummary
    ci_summary: CISummary
    dod_achieved: bool
    dod_unmet_reasons: list[str] = field(default_factory=list)


@dataclass
class CISummary:
    """CI結果の要約。"""

    total_jobs: int = 0
    passed_jobs: int = 0
    failed_jobs: int = 0
    failure_categories: dict[str, int] = field(default_factory=dict)
    overall_status: CIStatus = CIStatus.PENDING

    @property
    def all_passed(self) -> bool:
        return self.failed_jobs == 0 and self.total_jobs > 0


def classify_ci_failure(
    job_name: str,
    error_message: str,
) -> CIFailureCategory:
    """CI失敗を分類する（§A7）。

    Parameters
    ----------
    job_name : str
        CIジョブ名。
    error_message : str
        エラーメッセージ。

    Returns
    -------
    CIFailureCategory
        分類された失敗カテゴリ。
    """
    combined = f"{job_name} {error_message}".lower()

    if any(kw in combined for kw in ("lint", "ruff", "flake8", "eslint", "style")):
        return CIFailureCategory.LINT
    if any(kw in combined for kw in ("type", "mypy", "pyright", "typescript")):
        return CIFailureCategory.TYPE_CHECK
    if any(kw in combined for kw in ("unit", "pytest", "jest", "test_")):
        return CIFailureCategory.UNIT_TEST
    if any(kw in combined for kw in ("integration", "e2e", "selenium")):
        return CIFailureCategory.INTEGRATION_TEST
    if any(kw in combined for kw in ("security", "vulnerability", "cve", "bandit", "safety")):
        return CIFailureCategory.SECURITY_SCAN
    if any(kw in combined for kw in ("build", "compile", "package")):
        return CIFailureCategory.BUILD
    if any(kw in combined for kw in ("dependency", "install", "pip", "npm")):
        return CIFailureCategory.DEPENDENCY
    if any(kw in combined for kw in ("timeout", "infrastructure", "runner", "network")):
        return CIFailureCategory.INFRASTRUCTURE

    return CIFailureCategory.UNKNOWN


# --- CHECKフェーズ: 5つのAIペルソナがDOの成果物をレビューする ---
# CI結果の解析・DoD（完了条件）の自動判定も行う
class Checker:
    """CHECKフェーズを実行する。

    CI結果の収集・要約、DoD達成判定、レビュー統合を行う。
    5ペルソナレビューの実際のLLM呼び出しは外部から注入する。
    """

    def __init__(self, review_integrator: Any | None = None) -> None:
        self._integrator = review_integrator

    def summarize_ci(self, ci_results: list[CIResult]) -> CISummary:
        """CI結果を要約する。

        Parameters
        ----------
        ci_results : list[CIResult]
            CI実行結果リスト。

        Returns
        -------
        CISummary
            CI要約。
        """
        total = len(ci_results)
        passed = sum(1 for r in ci_results if r.status == CIStatus.SUCCESS)
        failed = sum(
            1 for r in ci_results
            if r.status in (CIStatus.FAILURE, CIStatus.ERROR)
        )

        # 失敗カテゴリ集計
        categories: dict[str, int] = {}
        for result in ci_results:
            if result.status in (CIStatus.FAILURE, CIStatus.ERROR):
                cat = result.failure_category or classify_ci_failure(
                    result.job_name, result.error_message,
                )
                categories[cat.value] = categories.get(cat.value, 0) + 1

        overall = CIStatus.SUCCESS if failed == 0 and total > 0 else CIStatus.FAILURE

        return CISummary(
            total_jobs=total,
            passed_jobs=passed,
            failed_jobs=failed,
            failure_categories=categories,
            overall_status=overall,
        )

    def evaluate_dod(
        self,
        dod_items: list[DoDItem],
        tasks: list[Task],
        ci_summary: CISummary,
    ) -> tuple[bool, list[str]]:
        """DoD達成を判定する。

        Parameters
        ----------
        dod_items : list[DoDItem]
            マイルストーンレベルのDoD。
        tasks : list[Task]
            サイクル内タスク。
        ci_summary : CISummary
            CI要約結果。

        Returns
        -------
        tuple[bool, list[str]]
            (DoD達成かどうか, 未達理由リスト)
        """
        unmet_reasons: list[str] = []

        # CIが全て通過していること
        if not ci_summary.all_passed:
            unmet_reasons.append(
                f"CI失敗: {ci_summary.failed_jobs}/{ci_summary.total_jobs}ジョブが失敗"
            )

        # 全タスクが完了していること
        pending_tasks = [
            t for t in tasks
            if t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
        ]
        if pending_tasks:
            unmet_reasons.append(
                f"未完了タスク: {len(pending_tasks)}件"
            )

        # DoD個別項目の確認
        for item in dod_items:
            if not item.achieved:
                unmet_reasons.append(f"DoD未達: {item.description}")

        achieved = len(unmet_reasons) == 0
        return achieved, unmet_reasons

    def run_check(self, context: CheckContext) -> CheckResult:
        """CHECKフェーズを実行する。

        Parameters
        ----------
        context : CheckContext
            CHECKフェーズの入力。

        Returns
        -------
        CheckResult
            CHECK結果。
        """
        # CI結果の要約
        ci_summary = self.summarize_ci(context.ci_results)

        # DoD判定
        dod_achieved, dod_unmet = self.evaluate_dod(
            context.dod_items, context.tasks, ci_summary,
        )

        # レビューサマリの構築
        review_summary = ReviewSummary(
            dod_achieved=dod_achieved,
            dod_unmet_reasons=dod_unmet,
        )

        logger.info(
            "CHECK完了: CI=%s, DoD=%s, 未達理由=%d件",
            ci_summary.overall_status.value,
            "達成" if dod_achieved else "未達",
            len(dod_unmet),
        )

        return CheckResult(
            review_summary=review_summary,
            ci_summary=ci_summary,
            dod_achieved=dod_achieved,
            dod_unmet_reasons=dod_unmet,
        )
