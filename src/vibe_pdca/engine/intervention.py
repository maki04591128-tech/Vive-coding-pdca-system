"""介入操作 – 原因分析レポート・ロールバック候補・再開条件提示。

M2 タスク 2-14: 要件定義書 §10.4, §19 準拠。

- いつでも停止できること
- 停止後に「原因分析レポート」「再開条件」「ロールバック候補」を提示
- ユーザーが採否の上書き / 優先度変更 / マイルストーン再編を行える
- P0（即停止）、P1（縮退+人間介入）、P2（次サイクルで是正）
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any

from vibe_pdca.models.pdca import (
    AuditEntry,
    Cycle,
    CycleStatus,
    Milestone,
    MilestoneStatus,
    PDCAPhase,
    StopReason,
    Task,
    TaskStatus,
)

logger = logging.getLogger(__name__)


class IncidentPriority(IntEnum):
    """インシデント優先度（§19）。"""

    P0 = 0  # 即停止
    P1 = 1  # 縮退 + 人間介入
    P2 = 2  # 次サイクルで是正


class InterventionAction(StrEnum):
    """介入アクション。"""

    STOP = "stop"
    RESUME = "resume"
    ROLLBACK = "rollback"
    OVERRIDE_DECISION = "override_decision"
    CHANGE_PRIORITY = "change_priority"
    REORDER_MILESTONES = "reorder_milestones"


class RollbackLevel(StrEnum):
    """ロールバック粒度レベル（提案16: §10.4）。"""

    TASK = "task"          # PR単位のリバート
    CYCLE = "cycle"        # サイクル状態のロールバック
    MILESTONE = "milestone"  # 複数サイクルの一括取消


@dataclass
class RollbackCandidate:
    """ロールバック候補。"""

    id: str = field(default_factory=lambda: f"rb-{uuid.uuid4().hex[:8]}")
    description: str = ""
    target_cycle: int = 0
    target_phase: str = ""
    impact_scope: str = ""
    risk_assessment: str = ""
    level: RollbackLevel = RollbackLevel.CYCLE


@dataclass
class RootCauseAnalysis:
    """原因分析レポート。"""

    stop_reason: StopReason | None = None
    summary: str = ""
    contributing_factors: list[str] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    affected_resources: list[str] = field(default_factory=list)


@dataclass
class ResumeCondition:
    """再開条件。"""

    description: str = ""
    is_met: bool = False
    evidence: str = ""


@dataclass
class InterventionReport:
    """介入操作レポート。"""

    id: str = field(default_factory=lambda: f"ir-{uuid.uuid4().hex[:8]}")
    incident_priority: IncidentPriority = IncidentPriority.P1
    root_cause: RootCauseAnalysis = field(default_factory=RootCauseAnalysis)
    rollback_candidates: list[RollbackCandidate] = field(default_factory=list)
    resume_conditions: list[ResumeCondition] = field(default_factory=list)
    recommended_action: InterventionAction = InterventionAction.STOP
    created_at: float = field(default_factory=time.time)

    def to_markdown(self) -> str:
        """Markdown形式でレポートを生成する。"""
        priority_icon = {
            IncidentPriority.P0: "🔴",
            IncidentPriority.P1: "🟡",
            IncidentPriority.P2: "🟢",
        }
        icon = priority_icon.get(self.incident_priority, "⚪")

        lines = [
            f"## {icon} 介入操作レポート ({self.id})",
            f"**優先度:** P{self.incident_priority.value}",
            f"**推奨アクション:** {self.recommended_action.value}",
            "",
            "### 原因分析",
            f"**概要:** {self.root_cause.summary}",
        ]

        if self.root_cause.contributing_factors:
            lines.append("**要因:**")
            for factor in self.root_cause.contributing_factors:
                lines.append(f"- {factor}")

        if self.rollback_candidates:
            lines.append("")
            lines.append("### ロールバック候補")
            for rb in self.rollback_candidates:
                lines.append(
                    f"- **{rb.id}**: {rb.description} "
                    f"(影響: {rb.impact_scope})"
                )

        if self.resume_conditions:
            lines.append("")
            lines.append("### 再開条件")
            for cond in self.resume_conditions:
                status = "✅" if cond.is_met else "❌"
                lines.append(f"- {status} {cond.description}")

        return "\n".join(lines)


class InterventionManager:
    """介入操作を管理する。

    停止後の原因分析、ロールバック候補、再開条件を提示し、
    ユーザーの介入操作を支援する。
    """

    def __init__(self) -> None:
        self._reports: list[InterventionReport] = []

    @property
    def report_count(self) -> int:
        return len(self._reports)

    def analyze_stop(
        self,
        milestone: Milestone,
        stop_reason: StopReason | None = None,
    ) -> InterventionReport:
        """停止時の原因分析レポートを生成する。

        Parameters
        ----------
        milestone : Milestone
            対象マイルストーン。
        stop_reason : StopReason | None
            停止理由。

        Returns
        -------
        InterventionReport
            介入操作レポート。
        """
        # インシデント優先度の判定
        priority = self._classify_priority(stop_reason)

        # 原因分析
        root_cause = self._analyze_root_cause(milestone, stop_reason)

        # ロールバック候補の生成
        rollback_candidates = self._generate_rollback_candidates(milestone)

        # 再開条件の生成
        resume_conditions = self._generate_resume_conditions(stop_reason)

        # 推奨アクションの決定
        recommended = self._recommend_action(priority, stop_reason)

        report = InterventionReport(
            incident_priority=priority,
            root_cause=root_cause,
            rollback_candidates=rollback_candidates,
            resume_conditions=resume_conditions,
            recommended_action=recommended,
        )
        self._reports.append(report)

        logger.info(
            "介入レポート生成: %s (P%d, 推奨: %s)",
            report.id, priority.value, recommended.value,
        )
        return report

    def get_reports(self) -> list[InterventionReport]:
        """全レポートを返す。"""
        return list(self._reports)

    def _classify_priority(
        self,
        stop_reason: StopReason | None,
    ) -> IncidentPriority:
        """停止理由からインシデント優先度を判定する。"""
        if stop_reason in (
            StopReason.CRITICAL_INCIDENT,
            StopReason.AUDIT_LOG_INCONSISTENCY,
        ):
            return IncidentPriority.P0

        if stop_reason in (
            StopReason.CI_CONSECUTIVE_FAILURE,
            StopReason.DIFF_SIZE_EXCEEDED,
            StopReason.CYCLE_TIMEOUT,
        ):
            return IncidentPriority.P1

        return IncidentPriority.P2

    def _analyze_root_cause(
        self,
        milestone: Milestone,
        stop_reason: StopReason | None,
    ) -> RootCauseAnalysis:
        """原因分析を実施する。"""
        factors: list[str] = []
        affected: list[str] = []
        timeline: list[dict[str, Any]] = []

        # サイクル履歴から要因を抽出
        for cycle in milestone.cycles:
            if cycle.decision and cycle.decision.decision_type.value == "reject":
                factors.append(
                    f"サイクル{cycle.cycle_number}: REJECT判定 – "
                    f"{cycle.decision.reason}"
                )
            if cycle.stop_reason:
                factors.append(
                    f"サイクル{cycle.cycle_number}: 停止 – "
                    f"{cycle.stop_reason.value}"
                )
            timeline.append({
                "cycle": cycle.cycle_number,
                "phase": cycle.phase.value,
                "status": cycle.status.value,
            })

        # 影響リソース
        current_cycle = milestone.cycles[-1] if milestone.cycles else None
        if current_cycle:
            for task in current_cycle.tasks:
                if task.status.value == "in_progress":
                    affected.append(f"タスク: {task.id} ({task.title})")

        summary = (
            f"停止理由: {stop_reason.value if stop_reason else '不明'}"
        )

        return RootCauseAnalysis(
            stop_reason=stop_reason,
            summary=summary,
            contributing_factors=factors or ["停止前の問題は検出されませんでした"],
            timeline=timeline,
            affected_resources=affected,
        )

    def _generate_rollback_candidates(
        self,
        milestone: Milestone,
    ) -> list[RollbackCandidate]:
        """ロールバック候補を生成する。"""
        candidates: list[RollbackCandidate] = []

        for cycle in reversed(milestone.cycles):
            if cycle.status.value == "completed":
                candidates.append(RollbackCandidate(
                    description=(
                        f"サイクル{cycle.cycle_number}完了時点にロールバック"
                    ),
                    target_cycle=cycle.cycle_number,
                    target_phase=cycle.phase.value,
                    impact_scope=f"サイクル{cycle.cycle_number}以降の変更を破棄",
                    risk_assessment="完了済みサイクルのため低リスク",
                ))
                if len(candidates) >= 3:
                    break

        if not candidates:
            candidates.append(RollbackCandidate(
                description="初期状態にロールバック",
                target_cycle=0,
                target_phase="",
                impact_scope="全変更を破棄",
                risk_assessment="全作業の損失",
            ))

        return candidates

    def _generate_resume_conditions(
        self,
        stop_reason: StopReason | None,
    ) -> list[ResumeCondition]:
        """再開条件を生成する。"""
        conditions: list[ResumeCondition] = []

        if stop_reason == StopReason.CI_CONSECUTIVE_FAILURE:
            conditions.append(ResumeCondition(
                description="CIが安定して通過すること",
            ))
        elif stop_reason == StopReason.DIFF_SIZE_EXCEEDED:
            conditions.append(ResumeCondition(
                description="変更量を閾値以内に縮小すること",
            ))
        elif stop_reason == StopReason.CYCLE_TIMEOUT:
            conditions.append(ResumeCondition(
                description="タイムアウトの原因を特定・解消すること",
            ))
        elif stop_reason == StopReason.CRITICAL_INCIDENT:
            conditions.append(ResumeCondition(
                description="インシデントの根本原因を特定・修正すること",
            ))
            conditions.append(ResumeCondition(
                description="修正後のテストが全通過すること",
            ))
        elif stop_reason == StopReason.AUDIT_LOG_INCONSISTENCY:
            conditions.append(ResumeCondition(
                description="監査ログの整合性を回復すること",
            ))

        # 共通再開条件
        conditions.append(ResumeCondition(
            description="運用担当者の承認を得ること",
        ))

        return conditions

    def _recommend_action(
        self,
        priority: IncidentPriority,
        stop_reason: StopReason | None,
    ) -> InterventionAction:
        """推奨アクションを決定する。"""
        if priority == IncidentPriority.P0:
            return InterventionAction.STOP
        if priority == IncidentPriority.P1:
            return InterventionAction.STOP
        return InterventionAction.RESUME


# ============================================================
# 提案16: ロールバック戦略の体系化
# ============================================================


@dataclass
class RollbackPreview:
    """ロールバック実行前の影響プレビュー（提案16）。

    ロールバック対象が及ぼす影響範囲を事前に可視化する。
    """

    candidate: RollbackCandidate
    affected_pr_numbers: list[int] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    dependent_task_ids: list[str] = field(default_factory=list)
    estimated_risk: str = "low"

    @staticmethod
    def from_milestone(
        candidate: RollbackCandidate,
        milestone: Milestone,
    ) -> RollbackPreview:
        """マイルストーン情報からプレビューを生成する。

        Parameters
        ----------
        candidate : RollbackCandidate
            対象ロールバック候補。
        milestone : Milestone
            対象マイルストーン。

        Returns
        -------
        RollbackPreview
            影響プレビュー。
        """
        pr_numbers: list[int] = []
        changed_files: list[str] = []
        dependent_ids: list[str] = []

        for cycle in milestone.cycles:
            if cycle.cycle_number > candidate.target_cycle:
                for task in cycle.tasks:
                    if task.pr_number is not None:
                        pr_numbers.append(task.pr_number)
                    if task.dependencies:
                        dependent_ids.extend(task.dependencies)

        # リスク推定: 影響PR数に基づく
        if len(pr_numbers) >= 5:
            risk = "high"
        elif len(pr_numbers) >= 2:
            risk = "medium"
        else:
            risk = "low"

        return RollbackPreview(
            candidate=candidate,
            affected_pr_numbers=pr_numbers,
            changed_files=changed_files,
            dependent_task_ids=dependent_ids,
            estimated_risk=risk,
        )


class StateConsistencyChecker:
    """ロールバック後の状態整合性を検証する（提案16）。

    PDCA状態機械・監査ログ・GitHub Issue の整合性を確認し、
    不整合があれば報告する。
    """

    def __init__(self) -> None:
        self._errors: list[str] = []

    @property
    def errors(self) -> list[str]:
        """検出された不整合の一覧。"""
        return list(self._errors)

    @property
    def is_consistent(self) -> bool:
        """全チェックに合格したか。"""
        return len(self._errors) == 0

    def check_all(
        self,
        milestone: Milestone,
        audit_entries: list[AuditEntry] | None = None,
    ) -> bool:
        """全整合性チェックを実行する。

        Parameters
        ----------
        milestone : Milestone
            対象マイルストーン。
        audit_entries : list[AuditEntry] | None
            監査ログエントリ（任意）。

        Returns
        -------
        bool
            全チェック合格なら True。
        """
        self._errors.clear()
        self._check_phase_consistency(milestone)
        self._check_cycle_numbering(milestone)
        self._check_task_status_consistency(milestone)
        if audit_entries is not None:
            self._check_audit_chain(audit_entries)
        return self.is_consistent

    def _check_phase_consistency(self, milestone: Milestone) -> None:
        """サイクルのフェーズ整合性を検証する。"""
        for cycle in milestone.cycles:
            if cycle.status == CycleStatus.RUNNING:
                valid_phases = {
                    PDCAPhase.PLAN, PDCAPhase.DO,
                    PDCAPhase.CHECK, PDCAPhase.ACT,
                }
                if cycle.phase not in valid_phases:
                    self._errors.append(
                        f"サイクル{cycle.cycle_number}: "
                        f"RUNNING状態で不正なフェーズ '{cycle.phase}'"
                    )
            if cycle.status == CycleStatus.COMPLETED and cycle.completed_at is None:
                self._errors.append(
                    f"サイクル{cycle.cycle_number}: "
                    f"COMPLETED状態だが completed_at が未設定"
                )

    def _check_cycle_numbering(self, milestone: Milestone) -> None:
        """サイクル番号の連続性を検証する。"""
        for i, cycle in enumerate(milestone.cycles):
            expected = i + 1
            if cycle.cycle_number != expected:
                self._errors.append(
                    f"サイクル番号不整合: 期待={expected}, "
                    f"実際={cycle.cycle_number}"
                )

    def _check_task_status_consistency(self, milestone: Milestone) -> None:
        """完了サイクル内のタスク状態を検証する。"""
        for cycle in milestone.cycles:
            if cycle.status != CycleStatus.COMPLETED:
                continue
            for task in cycle.tasks:
                if task.status == TaskStatus.IN_PROGRESS:
                    self._errors.append(
                        f"サイクル{cycle.cycle_number}: "
                        f"COMPLETED状態だがタスク '{task.id}' が IN_PROGRESS"
                    )

    def _check_audit_chain(self, entries: list[AuditEntry]) -> None:
        """監査ログのチェーンハッシュ整合性を検証する。"""
        for i, entry in enumerate(entries):
            if i == 0:
                continue
            prev = entries[i - 1]
            if entry.previous_hash and entry.previous_hash != prev.entry_hash:
                self._errors.append(
                    f"監査ログ seq={entry.sequence}: "
                    f"previous_hash 不整合 "
                    f"(期待={prev.entry_hash[:16]}…, "
                    f"実際={entry.previous_hash[:16]}…)"
                )


@dataclass
class RollbackChainLink:
    """ロールバック連鎖の1リンク。"""

    task_id: str
    reason: str


class RollbackChainDetector:
    """ロールバック連鎖を検出する（提案16）。

    あるタスクのロールバックが他のタスクに波及するかを分析し、
    連鎖的に必要となるロールバック対象を特定する。
    """

    def detect(
        self,
        target_task_id: str,
        milestone: Milestone,
    ) -> list[RollbackChainLink]:
        """指定タスクのロールバックで連鎖的に影響を受けるタスクを検出する。

        Parameters
        ----------
        target_task_id : str
            ロールバック対象タスクID。
        milestone : Milestone
            対象マイルストーン。

        Returns
        -------
        list[RollbackChainLink]
            連鎖的にロールバックが必要なタスクのリスト。
        """
        chain: list[RollbackChainLink] = []
        visited: set[str] = set()
        self._walk(target_task_id, milestone, chain, visited)
        return chain

    def _walk(
        self,
        task_id: str,
        milestone: Milestone,
        chain: list[RollbackChainLink],
        visited: set[str],
    ) -> None:
        """依存グラフを再帰的に辿る。"""
        if task_id in visited:
            return
        visited.add(task_id)

        for cycle in milestone.cycles:
            for task in cycle.tasks:
                if task_id in task.dependencies and task.id not in visited:
                    chain.append(RollbackChainLink(
                        task_id=task.id,
                        reason=(
                            f"タスク '{task.id}' は '{task_id}' に依存"
                        ),
                    ))
                    self._walk(task.id, milestone, chain, visited)
