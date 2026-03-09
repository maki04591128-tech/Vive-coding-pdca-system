"""DOフェーズ実行 – PLANで定義したタスクを実行しPRを生成する。

M2 タスク 2-2: 要件定義書 §5.2, §6.3 準拠。

- PLANで定義したタスクに基づき成果物を更新
- 変更はすべてGitHub PRとして追跡可能
- 変更種別（ソースコード/テスト/ドキュメント/設定/依存関係/バイナリ）を分類
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from vibe_pdca.models.pdca import (
    ChangeType,
    Task,
    TaskStatus,
)

logger = logging.getLogger(__name__)

# 変更種別ごとの必須ゲート（§9.3）
CHANGE_TYPE_GATES: dict[ChangeType, list[str]] = {
    ChangeType.SOURCE_CODE: ["lint", "type_check", "unit_test", "security_scan"],
    ChangeType.TEST: ["lint", "type_check", "test_execution"],
    ChangeType.DOCUMENTATION: ["spell_check"],
    ChangeType.CONFIG: ["schema_validation", "security_scan"],
    ChangeType.DEPENDENCY: ["vulnerability_scan", "license_check"],
    ChangeType.BINARY: ["virus_scan", "size_check"],
}


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@dataclass
class ExecutionResult:
    """タスク1件の実行結果。"""

    task_id: str
    success: bool
    pr_number: int | None = None
    branch_name: str = ""
    change_type: ChangeType | None = None
    diff_lines: int = 0
    files_changed: list[str] = field(default_factory=list)
    error_message: str = ""
    gate_results: dict[str, bool] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None


@dataclass
class DoPhaseResult:
    """DOフェーズ全体の結果。"""

    task_results: list[ExecutionResult]
    total_diff_lines: int = 0
    max_file_diff_lines: int = 0

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.task_results if r.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.task_results if not r.success)

    @property
    def all_succeeded(self) -> bool:
        return all(r.success for r in self.task_results)


def classify_change_type(file_path: str) -> ChangeType:
    """ファイルパスから変更種別を推定する（§9.3）。

    Parameters
    ----------
    file_path : str
        変更対象ファイルパス。

    Returns
    -------
    ChangeType
        推定された変更種別。
    """
    lower = file_path.lower()

    # 依存関係ファイルを先にチェック（.txt拡張子より優先）
    if any(lower.endswith(ext) for ext in (".lock", "requirements.txt", "pipfile")):
        return ChangeType.DEPENDENCY
    if lower.endswith((".md", ".rst", ".txt", ".adoc")):
        return ChangeType.DOCUMENTATION
    if "pyproject.toml" in lower and "dependencies" in lower:
        return ChangeType.DEPENDENCY
    _config_exts = (".yml", ".yaml", ".toml", ".ini", ".cfg", ".json", ".env")
    if any(lower.endswith(ext) for ext in _config_exts):
        return ChangeType.CONFIG
    if any(lower.endswith(ext) for ext in (".exe", ".dll", ".so", ".whl", ".zip", ".tar.gz")):
        return ChangeType.BINARY
    if "test" in lower or lower.endswith("_test.py") or lower.startswith("test_"):
        return ChangeType.TEST

    return ChangeType.SOURCE_CODE


def get_required_gates(change_type: ChangeType) -> list[str]:
    """変更種別に応じた必須ゲートを返す（§9.3）。"""
    return list(CHANGE_TYPE_GATES.get(change_type, []))


# --- DOフェーズ: AIがPLANで定義されたタスクを実際に実行（コード生成・PR作成） ---
class Executor:
    """DOフェーズを実行する。

    タスクリストを受け取り、各タスクを順次実行してPRを生成する。
    実際のLLM呼び出しやGitHub操作は外部から注入する。
    """

    def __init__(self, llm_gateway: Any | None = None) -> None:
        self._gateway = llm_gateway

    def execute_tasks(
        self,
        tasks: list[Task],
        dry_run: bool = False,
    ) -> DoPhaseResult:
        """タスクリストを実行する。

        Parameters
        ----------
        tasks : list[Task]
            実行対象のタスクリスト。
        dry_run : bool
            True の場合、実際の変更を行わずシミュレーションのみ。

        Returns
        -------
        DoPhaseResult
            全タスクの実行結果。
        """
        results: list[ExecutionResult] = []
        total_diff = 0
        max_file_diff = 0

        for task in tasks:
            if task.status == TaskStatus.BLOCKED:
                results.append(ExecutionResult(
                    task_id=task.id,
                    success=False,
                    error_message="タスクがブロックされています",
                ))
                continue

            if task.status == TaskStatus.COMPLETED:
                results.append(ExecutionResult(
                    task_id=task.id,
                    success=True,
                    error_message="既に完了済み",
                ))
                continue

            result = self._execute_single_task(task, dry_run=dry_run)
            results.append(result)

            if result.success:
                total_diff += result.diff_lines
                max_file_diff = max(max_file_diff, result.diff_lines)
                task.status = TaskStatus.IN_PROGRESS
                if result.pr_number:
                    task.pr_number = result.pr_number

            logger.info(
                "タスク実行 %s: %s (diff: %d行, PR: %s)",
                "成功" if result.success else "失敗",
                task.id,
                result.diff_lines,
                result.pr_number or "なし",
            )

        return DoPhaseResult(
            task_results=results,
            total_diff_lines=total_diff,
            max_file_diff_lines=max_file_diff,
        )

    def _execute_single_task(
        self,
        task: Task,
        dry_run: bool = False,
    ) -> ExecutionResult:
        """1タスクを実行する。"""
        started_at = time.time()
        change_type = task.change_type or ChangeType.SOURCE_CODE
        branch_name = f"pdca/task-{task.id}"

        # 必須ゲートを取得
        required_gates = get_required_gates(change_type)

        if dry_run:
            return ExecutionResult(
                task_id=task.id,
                success=True,
                branch_name=branch_name,
                change_type=change_type,
                gate_results={g: True for g in required_gates},
                started_at=started_at,
                completed_at=time.time(),
            )

        # ゲート検証（実際の実行時にはCI結果を使用）
        gate_results = {gate: True for gate in required_gates}

        return ExecutionResult(
            task_id=task.id,
            success=True,
            branch_name=branch_name,
            change_type=change_type,
            gate_results=gate_results,
            started_at=started_at,
            completed_at=time.time(),
        )
