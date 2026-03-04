"""コスト見積もりモード – 推定マイルストーン数・サイクル数・LLMコスト。

M3 タスク 3-8: 要件定義書 §26.9 準拠。

ゴール入力後に推定マイルストーン数・サイクル数・LLMコスト・主要リスクを表示する。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# コスト推定の基準値
COST_PER_LLM_CALL_USD = 0.03
LLM_CALLS_PER_TASK = 10
TASKS_PER_CYCLE_AVG = 5
CYCLES_PER_MILESTONE_AVG = 3


@dataclass
class CostEstimate:
    """コスト見積もり結果。"""

    estimated_milestones: int = 0
    estimated_cycles: int = 0
    estimated_tasks: int = 0
    estimated_llm_calls: int = 0
    estimated_cost_usd: float = 0.0
    estimated_duration_days: int = 0
    major_risks: list[str] = field(default_factory=list)
    breakdown: dict[str, float] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Markdown形式でレポートを生成する。"""
        lines = [
            "## 💰 コスト見積もり",
            "",
            "| 項目 | 値 |",
            "|------|-----|",
            f"| 推定マイルストーン数 | {self.estimated_milestones} |",
            f"| 推定サイクル数 | {self.estimated_cycles} |",
            f"| 推定タスク数 | {self.estimated_tasks} |",
            f"| 推定LLM呼び出し数 | {self.estimated_llm_calls} |",
            f"| 推定コスト | ${self.estimated_cost_usd:.2f} |",
            f"| 推定期間 | {self.estimated_duration_days}日 |",
            "",
        ]

        if self.major_risks:
            lines.append("### 主要リスク")
            for risk in self.major_risks:
                lines.append(f"- ⚠️ {risk}")
            lines.append("")

        if self.breakdown:
            lines.append("### コスト内訳")
            for k, v in self.breakdown.items():
                lines.append(f"- {k}: ${v:.2f}")

        return "\n".join(lines)


class CostEstimator:
    """コスト見積もり。"""

    def __init__(
        self,
        cost_per_call: float = COST_PER_LLM_CALL_USD,
        calls_per_task: int = LLM_CALLS_PER_TASK,
    ) -> None:
        self._cost_per_call = cost_per_call
        self._calls_per_task = calls_per_task

    def estimate(
        self,
        acceptance_criteria_count: int,
        constraints_count: int = 0,
        complexity: str = "medium",
    ) -> CostEstimate:
        """コストを見積もる。

        Parameters
        ----------
        acceptance_criteria_count : int
            受入条件数。
        constraints_count : int
            制約数。
        complexity : str
            複雑度（low/medium/high）。

        Returns
        -------
        CostEstimate
            見積もり結果。
        """
        # 複雑度係数
        complexity_mult = {"low": 0.7, "medium": 1.0, "high": 1.5}.get(
            complexity, 1.0,
        )

        # 推定値算出
        est_tasks = max(1, int(acceptance_criteria_count * complexity_mult))
        est_cycles = max(1, (est_tasks + TASKS_PER_CYCLE_AVG - 1)
                         // TASKS_PER_CYCLE_AVG)
        est_milestones = max(1, (est_cycles + CYCLES_PER_MILESTONE_AVG - 1)
                            // CYCLES_PER_MILESTONE_AVG)
        est_llm_calls = est_tasks * self._calls_per_task
        est_cost = est_llm_calls * self._cost_per_call
        est_duration = est_cycles * 1  # 1日/サイクル概算

        # リスク分析
        risks: list[str] = []
        if acceptance_criteria_count > 10:
            risks.append("受入条件が多い – スコープ肥大化のリスク")
        if complexity == "high":
            risks.append("高複雑度 – 見積もり精度が低下する可能性")
        if est_cost > 50:
            risks.append(f"推定コストが高い (${est_cost:.2f}) – 段階的実施を推奨")

        # 内訳
        plan_cost = est_cycles * 5 * self._cost_per_call
        do_cost = est_tasks * 3 * self._cost_per_call
        check_cost = est_cycles * 10 * self._cost_per_call
        act_cost = est_cycles * 2 * self._cost_per_call

        return CostEstimate(
            estimated_milestones=est_milestones,
            estimated_cycles=est_cycles,
            estimated_tasks=est_tasks,
            estimated_llm_calls=est_llm_calls,
            estimated_cost_usd=est_cost,
            estimated_duration_days=est_duration,
            major_risks=risks,
            breakdown={
                "PLAN": plan_cost,
                "DO": do_cost,
                "CHECK": check_cost,
                "ACT": act_cost,
            },
        )
