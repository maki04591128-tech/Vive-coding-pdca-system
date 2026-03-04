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

from vibe_pdca.models.pdca import Milestone, StopReason

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


@dataclass
class RollbackCandidate:
    """ロールバック候補。"""

    id: str = field(default_factory=lambda: f"rb-{uuid.uuid4().hex[:8]}")
    description: str = ""
    target_cycle: int = 0
    target_phase: str = ""
    impact_scope: str = ""
    risk_assessment: str = ""


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
