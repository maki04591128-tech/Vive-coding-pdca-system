"""ドライランモード – PLAN→CHECKシミュレーション。

M3 タスク 3-7: 要件定義書 §26.7 準拠。

外部書き込みなしでPLAN → CHECKのシミュレーション結果のみを報告する。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DryRunResult:
    """ドライラン結果。"""

    plan_summary: str = ""
    estimated_tasks: int = 0
    estimated_cycles: int = 0
    check_preview: str = ""
    potential_blockers: list[str] = field(default_factory=list)
    estimated_cost_usd: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Markdown形式でレポートを生成する。"""
        lines = [
            "## 🔍 ドライラン結果",
            "",
            "### PLAN概要",
            self.plan_summary or "（なし）",
            "",
            f"**推定タスク数:** {self.estimated_tasks}",
            f"**推定サイクル数:** {self.estimated_cycles}",
            f"**推定コスト:** ${self.estimated_cost_usd:.2f}",
            "",
        ]

        if self.potential_blockers:
            lines.append("### 潜在ブロッカー")
            for b in self.potential_blockers:
                lines.append(f"- ⚠️ {b}")
            lines.append("")

        if self.warnings:
            lines.append("### 警告")
            for w in self.warnings:
                lines.append(f"- {w}")
            lines.append("")

        if self.check_preview:
            lines.append("### CHECKプレビュー")
            lines.append(self.check_preview)

        return "\n".join(lines)


class DryRunExecutor:
    """ドライラン実行器。

    外部への書き込み操作を行わず、PLAN→CHECKの
    シミュレーション結果のみを生成する。
    """

    def __init__(self) -> None:
        self._results: list[DryRunResult] = []

    @property
    def run_count(self) -> int:
        return len(self._results)

    def execute(
        self,
        goal_purpose: str,
        acceptance_criteria: list[str],
        constraints: list[str] | None = None,
    ) -> DryRunResult:
        """ドライランを実行する。

        Parameters
        ----------
        goal_purpose : str
            目標の目的。
        acceptance_criteria : list[str]
            受入条件。
        constraints : list[str] | None
            制約。

        Returns
        -------
        DryRunResult
            シミュレーション結果。
        """
        # PLANシミュレーション
        estimated_tasks = max(1, min(7, len(acceptance_criteria)))
        estimated_cycles = max(1, (estimated_tasks + 6) // 7)

        # コスト推定（タスクあたり約10回のLLM呼び出し想定）
        estimated_calls = estimated_tasks * 10
        estimated_cost = estimated_calls * 0.03  # 概算

        # 潜在ブロッカーの検出
        blockers: list[str] = []
        warnings: list[str] = []

        if len(acceptance_criteria) > 10:
            blockers.append("受入条件が多すぎます（10件超）– スコープ分割を推奨")

        if not constraints:
            warnings.append("制約が未定義です")

        if estimated_tasks > 5:
            warnings.append(
                f"タスク数が多い({estimated_tasks}件) – "
                f"サイクル分割を推奨"
            )

        # CHECKプレビュー
        check_preview = (
            f"推定{estimated_tasks}タスクに対するCI実行・"
            f"5ペルソナレビューを実施予定"
        )

        result = DryRunResult(
            plan_summary=(
                f"目標: {goal_purpose}\n"
                f"受入条件: {len(acceptance_criteria)}件\n"
                f"制約: {len(constraints or [])}件"
            ),
            estimated_tasks=estimated_tasks,
            estimated_cycles=estimated_cycles,
            check_preview=check_preview,
            potential_blockers=blockers,
            estimated_cost_usd=estimated_cost,
            warnings=warnings,
        )

        self._results.append(result)
        logger.info(
            "ドライラン完了: タスク=%d, サイクル=%d, コスト=$%.2f",
            estimated_tasks, estimated_cycles, estimated_cost,
        )
        return result
