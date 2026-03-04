"""インシデントレポート自動生成 – P0/P1定型レポート。

M3 タスク 3-13: 要件定義書 §19, ギャップB8 準拠。

- P0（即停止）/ P1（縮退 + 人間介入）の自動定型レポート
- 原因内訳提示・影響範囲推定・再開条件
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from vibe_pdca.engine.intervention import IncidentPriority

logger = logging.getLogger(__name__)


@dataclass
class IncidentReport:
    """インシデントレポート。"""

    id: str = field(default_factory=lambda: f"inc-{uuid.uuid4().hex[:8]}")
    priority: IncidentPriority = IncidentPriority.P1
    title: str = ""
    summary: str = ""
    root_cause: str = ""
    impact_scope: str = ""
    affected_services: list[str] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    remediation_steps: list[str] = field(default_factory=list)
    resume_conditions: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_markdown(self) -> str:
        """Markdown形式のインシデントレポートを生成する。"""
        priority_icon = {
            IncidentPriority.P0: "🔴 P0 (即停止)",
            IncidentPriority.P1: "🟡 P1 (縮退+介入)",
            IncidentPriority.P2: "🟢 P2 (次サイクル是正)",
        }

        lines = [
            f"# インシデントレポート: {self.id}",
            "",
            f"**優先度:** {priority_icon.get(self.priority, str(self.priority))}",
            f"**タイトル:** {self.title}",
            f"**発生時刻:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.created_at))}",
            "",
            "## 概要",
            self.summary or "（未記入）",
            "",
            "## 原因",
            self.root_cause or "（調査中）",
            "",
            "## 影響範囲",
            self.impact_scope or "（評価中）",
            "",
        ]

        if self.affected_services:
            lines.append("### 影響を受けたサービス")
            for svc in self.affected_services:
                lines.append(f"- {svc}")
            lines.append("")

        if self.timeline:
            lines.append("## タイムライン")
            for event in self.timeline:
                t = event.get("time", "")
                desc = event.get("description", "")
                lines.append(f"- **{t}**: {desc}")
            lines.append("")

        if self.remediation_steps:
            lines.append("## 是正措置")
            for i, step in enumerate(self.remediation_steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        if self.resume_conditions:
            lines.append("## 再開条件")
            for cond in self.resume_conditions:
                lines.append(f"- [ ] {cond}")

        return "\n".join(lines)


class IncidentReporter:
    """インシデントレポート自動生成。"""

    def __init__(self) -> None:
        self._reports: list[IncidentReport] = []

    @property
    def report_count(self) -> int:
        return len(self._reports)

    def generate_p0_report(
        self,
        title: str,
        summary: str,
        root_cause: str = "",
        affected_services: list[str] | None = None,
    ) -> IncidentReport:
        """P0インシデントレポートを生成する。"""
        report = IncidentReport(
            priority=IncidentPriority.P0,
            title=title,
            summary=summary,
            root_cause=root_cause,
            impact_scope="全システム停止",
            affected_services=affected_services or [],
            remediation_steps=[
                "即座に全PDCAサイクルを停止",
                "影響範囲を特定",
                "根本原因を調査",
                "修正を適用",
                "テストで検証",
            ],
            resume_conditions=[
                "根本原因が特定・修正されていること",
                "テストが全通過すること",
                "Ownerの承認を得ること",
            ],
        )
        self._reports.append(report)
        logger.warning("P0インシデントレポート生成: %s", report.id)
        return report

    def generate_p1_report(
        self,
        title: str,
        summary: str,
        root_cause: str = "",
        affected_services: list[str] | None = None,
    ) -> IncidentReport:
        """P1インシデントレポートを生成する。"""
        report = IncidentReport(
            priority=IncidentPriority.P1,
            title=title,
            summary=summary,
            root_cause=root_cause,
            impact_scope="一部機能の縮退",
            affected_services=affected_services or [],
            remediation_steps=[
                "縮退モードへ移行",
                "影響範囲を特定",
                "人間による介入判断を要求",
                "修正を適用",
            ],
            resume_conditions=[
                "原因が特定されていること",
                "縮退機能が復旧していること",
                "Maintainerの承認を得ること",
            ],
        )
        self._reports.append(report)
        logger.warning("P1インシデントレポート生成: %s", report.id)
        return report

    def get_reports(
        self,
        priority: IncidentPriority | None = None,
    ) -> list[IncidentReport]:
        """レポートを取得する。"""
        if priority is None:
            return list(self._reports)
        return [r for r in self._reports if r.priority == priority]
