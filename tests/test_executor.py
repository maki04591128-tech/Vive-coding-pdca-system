"""DOフェーズ（Executor）のテスト。"""

import pytest

from vibe_pdca.engine.executor import (
    ChangeType,
    DoPhaseResult,
    Executor,
    classify_change_type,
    get_required_gates,
)
from vibe_pdca.models.pdca import Task, TaskStatus

# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def executor():
    return Executor()


@pytest.fixture
def sample_tasks():
    return [
        Task(id="task-1", title="実装タスク", change_type=ChangeType.SOURCE_CODE),
        Task(id="task-2", title="テストタスク", change_type=ChangeType.TEST),
        Task(id="task-3", title="ドキュメント更新", change_type=ChangeType.DOCUMENTATION),
    ]


# ============================================================
# テスト: 変更種別分類
# ============================================================


class TestChangeTypeClassification:
    def test_classify_python_source(self):
        assert classify_change_type("src/main.py") == ChangeType.SOURCE_CODE

    def test_classify_test_file(self):
        assert classify_change_type("tests/test_main.py") == ChangeType.TEST

    def test_classify_markdown_doc(self):
        assert classify_change_type("docs/README.md") == ChangeType.DOCUMENTATION

    def test_classify_config_yaml(self):
        assert classify_change_type("config/default.yml") == ChangeType.CONFIG

    def test_classify_config_json(self):
        assert classify_change_type("package.json") == ChangeType.CONFIG

    def test_classify_dependency_lock(self):
        assert classify_change_type("poetry.lock") == ChangeType.DEPENDENCY

    def test_classify_requirements_txt(self):
        assert classify_change_type("requirements.txt") == ChangeType.DEPENDENCY

    def test_classify_binary(self):
        assert classify_change_type("dist/app.exe") == ChangeType.BINARY

    def test_classify_unknown_defaults_to_source(self):
        assert classify_change_type("unknown_file") == ChangeType.SOURCE_CODE


# ============================================================
# テスト: ゲート取得
# ============================================================


class TestGates:
    def test_source_code_gates(self):
        gates = get_required_gates(ChangeType.SOURCE_CODE)
        assert "lint" in gates
        assert "security_scan" in gates

    def test_test_gates(self):
        gates = get_required_gates(ChangeType.TEST)
        assert "test_execution" in gates

    def test_documentation_gates(self):
        gates = get_required_gates(ChangeType.DOCUMENTATION)
        assert "spell_check" in gates


# ============================================================
# テスト: タスク実行
# ============================================================


class TestExecutor:
    def test_execute_dry_run(self, executor, sample_tasks):
        result = executor.execute_tasks(sample_tasks, dry_run=True)
        assert isinstance(result, DoPhaseResult)
        assert result.success_count == 3
        assert result.failure_count == 0

    def test_skips_blocked_tasks(self, executor):
        tasks = [Task(id="t-1", title="Blocked", status=TaskStatus.BLOCKED)]
        result = executor.execute_tasks(tasks)
        assert result.failure_count == 1
        assert not result.task_results[0].success

    def test_skips_completed_tasks(self, executor):
        tasks = [Task(id="t-1", title="Done", status=TaskStatus.COMPLETED)]
        result = executor.execute_tasks(tasks)
        assert result.success_count == 1
        assert result.task_results[0].success

    def test_all_succeeded_property(self, executor, sample_tasks):
        result = executor.execute_tasks(sample_tasks, dry_run=True)
        assert result.all_succeeded

    def test_execution_sets_in_progress(self, executor):
        tasks = [Task(id="t-1", title="Test")]
        result = executor.execute_tasks(tasks)
        assert result.all_succeeded
        assert tasks[0].status == TaskStatus.IN_PROGRESS

    def test_max_file_diff_lines_tracked(self, executor):
        """max_file_diff_lines が各タスクの diff_lines の最大値を追跡する。"""
        from unittest.mock import patch

        from vibe_pdca.engine.executor import ExecutionResult

        diff_values = [50, 200, 120]
        call_count = 0

        def fake_execute(task, dry_run=False):
            nonlocal call_count
            val = diff_values[call_count]
            call_count += 1
            return ExecutionResult(task_id=task.id, success=True, diff_lines=val)

        tasks = [
            Task(id="t-1", title="A"),
            Task(id="t-2", title="B"),
            Task(id="t-3", title="C"),
        ]

        with patch.object(executor, "_execute_single_task", side_effect=fake_execute):
            result = executor.execute_tasks(tasks)

        assert result.max_file_diff_lines == 200
        assert result.total_diff_lines == 370
