"""CHECKフェーズ（Checker）のテスト。"""

import pytest

from vibe_pdca.engine.checker import (
    CheckContext,
    Checker,
    CheckResult,
    CIFailureCategory,
    CIResult,
    CIStatus,
    CISummary,
    classify_ci_failure,
)
from vibe_pdca.models.pdca import DoDItem, Task, TaskStatus

# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def checker():
    return Checker()


@pytest.fixture
def passing_ci():
    return [
        CIResult(job_name="lint", status=CIStatus.SUCCESS),
        CIResult(job_name="test", status=CIStatus.SUCCESS),
        CIResult(job_name="type-check", status=CIStatus.SUCCESS),
    ]


@pytest.fixture
def failing_ci():
    return [
        CIResult(job_name="lint", status=CIStatus.SUCCESS),
        CIResult(
            job_name="pytest",
            status=CIStatus.FAILURE,
            error_message="2 tests failed",
        ),
        CIResult(
            job_name="mypy",
            status=CIStatus.FAILURE,
            error_message="type error in main.py",
        ),
    ]


# ============================================================
# テスト: CI失敗分類
# ============================================================


class TestCIFailureClassification:
    def test_classify_lint(self):
        assert classify_ci_failure("lint", "ruff error") == CIFailureCategory.LINT

    def test_classify_type_check(self):
        assert classify_ci_failure("mypy", "type error") == CIFailureCategory.TYPE_CHECK

    def test_classify_unit_test(self):
        assert classify_ci_failure("pytest", "1 failed") == CIFailureCategory.UNIT_TEST

    def test_classify_security(self):
        assert classify_ci_failure("security-scan", "CVE found") == CIFailureCategory.SECURITY_SCAN

    def test_classify_build(self):
        assert classify_ci_failure("build", "compile error") == CIFailureCategory.BUILD

    def test_classify_dependency(self):
        assert classify_ci_failure("install", "pip error") == CIFailureCategory.DEPENDENCY

    def test_classify_infrastructure(self):
        assert classify_ci_failure("runner", "timeout") == CIFailureCategory.INFRASTRUCTURE

    def test_classify_unknown(self):
        assert classify_ci_failure("unknown-job", "something") == CIFailureCategory.UNKNOWN


# ============================================================
# テスト: CI要約
# ============================================================


class TestCISummary:
    def test_all_passing(self, checker, passing_ci):
        summary = checker.summarize_ci(passing_ci)
        assert summary.total_jobs == 3
        assert summary.passed_jobs == 3
        assert summary.failed_jobs == 0
        assert summary.all_passed

    def test_with_failures(self, checker, failing_ci):
        summary = checker.summarize_ci(failing_ci)
        assert summary.total_jobs == 3
        assert summary.passed_jobs == 1
        assert summary.failed_jobs == 2
        assert not summary.all_passed

    def test_failure_categories(self, checker, failing_ci):
        summary = checker.summarize_ci(failing_ci)
        assert len(summary.failure_categories) > 0

    def test_empty_results(self, checker):
        summary = checker.summarize_ci([])
        assert summary.total_jobs == 0
        assert not summary.all_passed


# ============================================================
# テスト: DoD判定
# ============================================================


class TestDoDEvaluation:
    def test_all_achieved(self, checker):
        dod = [DoDItem(description="テスト通過", achieved=True)]
        tasks = [Task(id="t-1", title="Done", status=TaskStatus.COMPLETED)]
        ci = CISummary(total_jobs=1, passed_jobs=1, failed_jobs=0, overall_status=CIStatus.SUCCESS)
        achieved, reasons = checker.evaluate_dod(dod, tasks, ci)
        assert achieved
        assert reasons == []

    def test_ci_failure_blocks_dod(self, checker):
        dod = [DoDItem(description="テスト通過", achieved=True)]
        tasks = [Task(id="t-1", title="Done", status=TaskStatus.COMPLETED)]
        ci = CISummary(total_jobs=2, passed_jobs=1, failed_jobs=1, overall_status=CIStatus.FAILURE)
        achieved, reasons = checker.evaluate_dod(dod, tasks, ci)
        assert not achieved
        assert any("CI失敗" in r for r in reasons)

    def test_pending_tasks_block_dod(self, checker):
        dod = [DoDItem(description="完了", achieved=True)]
        tasks = [Task(id="t-1", title="WIP", status=TaskStatus.IN_PROGRESS)]
        ci = CISummary(total_jobs=1, passed_jobs=1, failed_jobs=0, overall_status=CIStatus.SUCCESS)
        achieved, reasons = checker.evaluate_dod(dod, tasks, ci)
        assert not achieved
        assert any("未完了タスク" in r for r in reasons)

    def test_unmet_dod_item(self, checker):
        dod = [DoDItem(description="未達成の項目", achieved=False)]
        tasks = [Task(id="t-1", title="Done", status=TaskStatus.COMPLETED)]
        ci = CISummary(total_jobs=1, passed_jobs=1, failed_jobs=0, overall_status=CIStatus.SUCCESS)
        achieved, reasons = checker.evaluate_dod(dod, tasks, ci)
        assert not achieved
        assert any("DoD未達" in r for r in reasons)


# ============================================================
# テスト: CHECKフェーズ統合実行
# ============================================================


class TestCheckRun:
    def test_full_check_pass(self, checker, passing_ci):
        context = CheckContext(
            tasks=[Task(id="t-1", title="Done", status=TaskStatus.COMPLETED)],
            ci_results=passing_ci,
            dod_items=[DoDItem(description="テスト", achieved=True)],
        )
        result = checker.run_check(context)
        assert isinstance(result, CheckResult)
        assert result.dod_achieved

    def test_full_check_fail(self, checker, failing_ci):
        context = CheckContext(
            tasks=[Task(id="t-1", title="WIP", status=TaskStatus.IN_PROGRESS)],
            ci_results=failing_ci,
            dod_items=[DoDItem(description="テスト", achieved=False)],
        )
        result = checker.run_check(context)
        assert not result.dod_achieved
        assert len(result.dod_unmet_reasons) > 0
