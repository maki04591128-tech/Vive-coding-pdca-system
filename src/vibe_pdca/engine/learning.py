"""学習フィードバック – 失敗パターン抽出→PLANプロンプト反映。

M3 タスク 3-10: 要件定義書 §26.8 準拠。

- 10サイクルごとに失敗パターンを抽出
- PLANプロンプトへ自動追記（B操作扱い）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

FEEDBACK_INTERVAL_CYCLES = 10
# ※ 10サイクルごとにAIが失敗パターンを自動学習し、次のPLANに反映する


# 失敗パターン1件分のデータ（種類・頻度・重大度・対策）
@dataclass
class FailurePattern:
    """失敗パターン。"""

    pattern_id: str = ""
    description: str = ""
    frequency: int = 0
    severity: str = ""
    mitigation: str = ""


@dataclass
class FeedbackReport:
    """学習フィードバックレポート。"""

    cycle_range: str = ""
    patterns: list[FailurePattern] = field(default_factory=list)
    prompt_additions: list[str] = field(default_factory=list)
    applied: bool = False


# --- 学習フィードバック: 失敗パターンの蓄積→分析→プロンプト自動改善 ---
class LearningFeedback:
    """学習フィードバック管理。

    失敗パターンを蓄積し、定期的にPLANプロンプトへ反映する。
    """

    def __init__(
        self,
        interval: int = FEEDBACK_INTERVAL_CYCLES,
    ) -> None:
        self._interval = interval
        self._failure_records: list[dict[str, Any]] = []
        self._reports: list[FeedbackReport] = []
        self._prompt_additions: list[str] = []

    @property
    def record_count(self) -> int:
        return len(self._failure_records)

    @property
    def report_count(self) -> int:
        return len(self._reports)

    @property
    def prompt_additions(self) -> list[str]:
        return list(self._prompt_additions)

    def record_failure(
        self,
        cycle_number: int,
        failure_type: str,
        description: str,
        severity: str = "medium",
    ) -> None:
        """失敗を記録する。"""
        self._failure_records.append({
            "cycle": cycle_number,
            "type": failure_type,
            "description": description,
            "severity": severity,
        })

    def should_analyze(self, cycle_number: int) -> bool:
        """フィードバック分析のタイミングか判定する。"""
        return (
            cycle_number > 0
            and cycle_number % self._interval == 0
        )

    def analyze(self, cycle_number: int) -> FeedbackReport:
        """失敗パターンを分析し、プロンプト追加を生成する。

        Parameters
        ----------
        cycle_number : int
            現在のサイクル番号。

        Returns
        -------
        FeedbackReport
            分析結果。
        """
        start = max(0, cycle_number - self._interval)
        relevant = [
            r for r in self._failure_records
            if start <= r["cycle"] <= cycle_number
        ]

        # 直近N サイクルの失敗記録を集計し、パターンとして抽出する
        pattern_counts: dict[str, int] = {}
        pattern_severity: dict[str, str] = {}
        for record in relevant:
            ft = record["type"]
            pattern_counts[ft] = pattern_counts.get(ft, 0) + 1
            pattern_severity[ft] = record.get("severity", "medium")

        patterns: list[FailurePattern] = []
        additions: list[str] = []

        for i, (ptype, count) in enumerate(
            sorted(pattern_counts.items(), key=lambda x: -x[1])
        ):
            pattern = FailurePattern(
                pattern_id=f"fp-{i + 1}",
                description=ptype,
                frequency=count,
                severity=pattern_severity.get(ptype, "medium"),
                mitigation=f"過去{count}回発生: {ptype}を回避すること",
            )
            patterns.append(pattern)

            # 2回以上発生したパターンはPLANプロンプトに警告を追加
            if count >= 2:
                additions.append(
                    f"注意: 過去{count}回「{ptype}」が発生。"
                    f"この失敗パターンを回避してください。"
                )

        report = FeedbackReport(
            cycle_range=f"{start}-{cycle_number}",
            patterns=patterns,
            prompt_additions=additions,
        )
        self._reports.append(report)

        logger.info(
            "学習フィードバック分析: サイクル%d-%d, %d件パターン, %d件追記",
            start, cycle_number, len(patterns), len(additions),
        )
        return report

    def apply_to_prompt(self, report: FeedbackReport) -> list[str]:
        """フィードバックをプロンプトに適用する（B操作）。

        Returns
        -------
        list[str]
            追加されたプロンプト文。
        """
        self._prompt_additions.extend(report.prompt_additions)
        report.applied = True
        logger.info(
            "PLANプロンプトへ%d件追記 (B操作)",
            len(report.prompt_additions),
        )
        return report.prompt_additions

    def get_status(self) -> dict[str, Any]:
        """学習フィードバック状態を返す。"""
        return {
            "failure_records": self.record_count,
            "reports_generated": self.report_count,
            "prompt_additions": len(self._prompt_additions),
            "interval_cycles": self._interval,
        }
