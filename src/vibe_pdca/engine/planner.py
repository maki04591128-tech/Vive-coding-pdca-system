"""PLANフェーズ実行 – ゴールからマイルストーン・タスクを自動生成する。

M2 タスク 2-1: 要件定義書 §6.2, §7.1 準拠。

入力: 最終到達点・現マイルストーン・既知の制約・直近のCHECK結果
出力: 直近1サイクルのタスク（最大7件）、各タスクのDoD、リスクと回避策、依存関係
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from vibe_pdca.models.pdca import (
    ChangeType,
    DoDItem,
    Goal,
    Milestone,
    MilestoneStatus,
    Task,
    TaskStatus,
)

logger = logging.getLogger(__name__)

# タスク生成の制約（§7.1）
MAX_TASKS_PER_CYCLE = 7
MAX_TASKS_PER_MILESTONE = 30


def _generate_id(prefix: str) -> str:
    """短いランダムIDを生成する。"""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class PlanResult:
    """PLANフェーズの実行結果。"""

    def __init__(
        self,
        tasks: list[Task],
        risks: list[dict[str, str]] | None = None,
        rationale: str = "",
    ) -> None:
        self.tasks = tasks
        self.risks = risks or []
        self.rationale = rationale

    @property
    def task_count(self) -> int:
        return len(self.tasks)


class Planner:
    """PLANフェーズを実行してタスクを生成する。

    LLMを使用してゴール→マイルストーン→タスクの分解を行う。
    LLMが利用できない場合はルールベースのフォールバックを提供する。
    """

    def __init__(self, llm_gateway: Any | None = None) -> None:
        self._gateway = llm_gateway

    def generate_milestones(
        self,
        goal: Goal,
        max_milestones: int = 5,
    ) -> list[Milestone]:
        """ゴールからマイルストーンを自動生成する（§7.1）。

        Parameters
        ----------
        goal : Goal
            最終到達点の定義。
        max_milestones : int
            生成するマイルストーンの最大数。

        Returns
        -------
        list[Milestone]
            生成されたマイルストーン（依存順）。
        """
        if not goal.acceptance_criteria:
            raise ValueError("受入条件が空です。マイルストーンを生成できません。")

        milestones: list[Milestone] = []
        prev_id: str | None = None

        for i, criterion in enumerate(goal.acceptance_criteria[:max_milestones]):
            ms_id = _generate_id("ms")
            milestone = Milestone(
                id=ms_id,
                title=f"マイルストーン {i + 1}: {criterion[:60]}",
                description=f"受入条件「{criterion}」の達成",
                status=MilestoneStatus.OPEN,
                dod=[
                    DoDItem(
                        description=criterion,
                        is_machine_checkable=True,
                    ),
                ],
                dependencies=[prev_id] if prev_id else [],
            )
            milestones.append(milestone)
            prev_id = ms_id

        goal.milestones = milestones

        logger.info(
            "マイルストーン生成: %d件 (目標: %s)",
            len(milestones), goal.id,
        )
        return milestones

    def generate_tasks(
        self,
        milestone: Milestone,
        context: dict[str, Any] | None = None,
    ) -> PlanResult:
        """マイルストーンから1サイクル分のタスクを生成する（§6.2）。

        Parameters
        ----------
        milestone : Milestone
            対象マイルストーン。
        context : dict | None
            追加コンテキスト（直近のCHECK結果等）。

        Returns
        -------
        PlanResult
            生成されたタスクリスト・リスク・根拠。

        Raises
        ------
        ValueError
            マイルストーンのDoDが空の場合。
        """
        if not milestone.dod:
            raise ValueError(
                f"マイルストーン {milestone.id} にDoDがありません"
            )

        ctx = context or {}
        previous_findings = ctx.get("previous_findings", [])
        constraints = ctx.get("constraints", [])

        # 既存タスク数の上限チェック
        existing_count = sum(
            len(c.tasks) for c in milestone.cycles
        )
        remaining = MAX_TASKS_PER_MILESTONE - existing_count
        if remaining <= 0:
            raise ValueError(
                f"マイルストーンのタスク上限({MAX_TASKS_PER_MILESTONE}件)に到達"
            )

        max_tasks = min(MAX_TASKS_PER_CYCLE, remaining)

        # タスク生成（DoDベースの分解）
        tasks = self._decompose_dod_to_tasks(
            milestone, max_tasks, previous_findings,
        )

        # リスク分析
        risks = self._analyze_risks(tasks, constraints)

        result = PlanResult(
            tasks=tasks,
            risks=risks,
            rationale=f"DoDベースの分解により{len(tasks)}件のタスクを生成",
        )

        logger.info(
            "タスク生成: %d件 (マイルストーン: %s, リスク: %d件)",
            result.task_count, milestone.id, len(risks),
        )
        return result

    def _decompose_dod_to_tasks(
        self,
        milestone: Milestone,
        max_tasks: int,
        previous_findings: list[dict[str, Any]],
    ) -> list[Task]:
        """DoDをタスクに分解する。"""
        tasks: list[Task] = []
        prev_task_id: str | None = None

        # 前回のCHECK結果で未解決の指摘があればタスク化
        for finding in previous_findings[:2]:
            if len(tasks) >= max_tasks:
                break
            task_id = _generate_id("task")
            tasks.append(Task(
                id=task_id,
                title=f"修正: {finding.get('description', '指摘対応')[:50]}",
                description=finding.get("suggestion", ""),
                status=TaskStatus.PENDING,
                dod=[DoDItem(
                    description=f"指摘「{finding.get('description', '')}」の解消",
                    is_machine_checkable=True,
                )],
                dependencies=[prev_task_id] if prev_task_id else [],
                change_type=ChangeType.SOURCE_CODE,
                assignee_role="programmer",
            ))
            prev_task_id = task_id

        # DoDごとにタスクを生成
        for dod_item in milestone.dod:
            if len(tasks) >= max_tasks:
                break
            if dod_item.achieved:
                continue

            task_id = _generate_id("task")

            # 実装タスク
            tasks.append(Task(
                id=task_id,
                title=f"実装: {dod_item.description[:50]}",
                description=f"DoD達成: {dod_item.description}",
                status=TaskStatus.PENDING,
                dod=[DoDItem(
                    description=dod_item.description,
                    is_machine_checkable=dod_item.is_machine_checkable,
                )],
                dependencies=[prev_task_id] if prev_task_id else [],
                change_type=ChangeType.SOURCE_CODE,
                assignee_role="programmer",
            ))
            prev_task_id = task_id

            # テストタスク（実装タスクに対応）
            if len(tasks) < max_tasks:
                test_task_id = _generate_id("task")
                tasks.append(Task(
                    id=test_task_id,
                    title=f"テスト: {dod_item.description[:50]}",
                    description=f"実装のテスト: {dod_item.description}",
                    status=TaskStatus.PENDING,
                    dod=[DoDItem(
                        description=f"テストが通過すること: {dod_item.description}",
                        is_machine_checkable=True,
                    )],
                    dependencies=[task_id],
                    change_type=ChangeType.TEST,
                    assignee_role="programmer",
                ))
                prev_task_id = test_task_id

        return tasks[:max_tasks]

    def _analyze_risks(
        self,
        tasks: list[Task],
        constraints: list[str],
    ) -> list[dict[str, str]]:
        """タスクに関するリスクを分析する。"""
        risks: list[dict[str, str]] = []

        # 依存チェーン長のリスク
        if len(tasks) > 5:
            risks.append({
                "risk": "タスク数が多い（依存チェーンが長くなる可能性）",
                "mitigation": "並列実行可能なタスクの特定と依存の整理",
            })

        # ブロッカーリスク
        blocked_tasks = [t for t in tasks if t.status == TaskStatus.BLOCKED]
        if blocked_tasks:
            risks.append({
                "risk": f"ブロックされたタスクが{len(blocked_tasks)}件存在",
                "mitigation": "ブロッカーの解消を優先、代替案の検討",
            })

        # 制約関連リスク
        for constraint in constraints:
            risks.append({
                "risk": f"制約: {constraint}",
                "mitigation": "制約に適合する設計の確認",
            })

        return risks
