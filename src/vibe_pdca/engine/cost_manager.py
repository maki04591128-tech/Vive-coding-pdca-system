"""コスト管理 – LLM呼び出し上限・日次コスト管理・異常検知。

M3 タスク 3-4: 要件定義書 §15 準拠。

| 単位      | 指標                    | 確定値                   |
|----------|------------------------|-------------------------|
| 1サイクル  | LLM呼び出し回数上限      | 最大80回                 |
| 日次      | LLM呼び出し回数上限      | 最大500回                |
| 日次      | コスト急増検知（警告）    | 直近7日平均の2倍超        |
| 日次      | コスト急増検知（停止）    | 直近7日平均の3倍超        |
| 日次      | 金額上限（USD）          | $30.00                  |
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# §15.1 確定値
CYCLE_LLM_CALL_LIMIT = 80
DAILY_LLM_CALL_LIMIT = 500
DAILY_COST_LIMIT_USD = 30.0
COST_SPIKE_WARNING_MULTIPLIER = 2.0
COST_SPIKE_STOP_MULTIPLIER = 3.0
REVIEW_RESUBMIT_LIMIT = 1


class CostAction(StrEnum):
    """コスト超過時のアクション。"""

    ALLOW = "allow"
    WARNING = "warning"
    STOP = "stop"


@dataclass
class DailyUsage:
    """1日の使用量。"""

    date: str = ""  # YYYY-MM-DD
    llm_calls: int = 0
    llm_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class CostCheckResult:
    """コストチェック結果。"""

    action: CostAction = CostAction.ALLOW
    reason: str = ""
    current_calls: int = 0
    current_cost_usd: float = 0.0
    limit_calls: int = 0
    limit_cost_usd: float = 0.0


class CostManager:
    """コスト管理。

    LLM呼び出し上限・日次コスト管理・異常検知を行う。
    """

    def __init__(
        self,
        cycle_call_limit: int = CYCLE_LLM_CALL_LIMIT,
        daily_call_limit: int = DAILY_LLM_CALL_LIMIT,
        daily_cost_limit_usd: float = DAILY_COST_LIMIT_USD,
        spike_warning_mult: float = COST_SPIKE_WARNING_MULTIPLIER,
        spike_stop_mult: float = COST_SPIKE_STOP_MULTIPLIER,
    ) -> None:
        self._cycle_call_limit = cycle_call_limit
        self._daily_call_limit = daily_call_limit
        self._daily_cost_limit_usd = daily_cost_limit_usd
        self._spike_warning_mult = spike_warning_mult
        self._spike_stop_mult = spike_stop_mult
        self._current_cycle_calls = 0
        self._daily_history: list[DailyUsage] = []
        self._today_usage = DailyUsage()

    @property
    def current_cycle_calls(self) -> int:
        return self._current_cycle_calls

    @property
    def today_usage(self) -> DailyUsage:
        return self._today_usage

    def record_call(
        self,
        tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> CostCheckResult:
        """LLM呼び出しを記録し、上限チェックを行う。

        Returns
        -------
        CostCheckResult
            チェック結果。STOPの場合は呼び出し元が停止すべき。
        """
        self._current_cycle_calls += 1
        self._today_usage.llm_calls += 1
        self._today_usage.llm_tokens += tokens
        self._today_usage.cost_usd += cost_usd

        return self.check_limits()

    def check_limits(self) -> CostCheckResult:
        """現在の使用量に対する上限チェックを行う。"""
        # サイクル呼び出し上限
        if self._current_cycle_calls > self._cycle_call_limit:
            return CostCheckResult(
                action=CostAction.STOP,
                reason=(
                    f"サイクルLLM呼び出し上限超過 "
                    f"({self._current_cycle_calls} > {self._cycle_call_limit})"
                ),
                current_calls=self._current_cycle_calls,
                limit_calls=self._cycle_call_limit,
            )

        # 日次呼び出し上限
        if self._today_usage.llm_calls > self._daily_call_limit:
            return CostCheckResult(
                action=CostAction.STOP,
                reason=(
                    f"日次LLM呼び出し上限超過 "
                    f"({self._today_usage.llm_calls} > {self._daily_call_limit})"
                ),
                current_calls=self._today_usage.llm_calls,
                limit_calls=self._daily_call_limit,
            )

        # 日次コスト上限
        if self._today_usage.cost_usd > self._daily_cost_limit_usd:
            return CostCheckResult(
                action=CostAction.STOP,
                reason=(
                    f"日次コスト上限超過 "
                    f"(${self._today_usage.cost_usd:.2f} > "
                    f"${self._daily_cost_limit_usd:.2f})"
                ),
                current_cost_usd=self._today_usage.cost_usd,
                limit_cost_usd=self._daily_cost_limit_usd,
            )

        # コスト急増検知
        spike_result = self._check_cost_spike()
        if spike_result.action != CostAction.ALLOW:
            return spike_result

        return CostCheckResult(action=CostAction.ALLOW)

    def reset_cycle(self) -> None:
        """サイクルカウンタをリセットする。"""
        self._current_cycle_calls = 0

    def close_day(self) -> None:
        """日次使用量を確定し履歴に追加する。"""
        self._daily_history.append(self._today_usage)
        # 直近30日分だけ保持
        if len(self._daily_history) > 30:
            self._daily_history = self._daily_history[-30:]
        self._today_usage = DailyUsage()

    def get_7day_average_cost(self) -> float:
        """直近7日の平均コストを返す。"""
        recent = self._daily_history[-7:]
        if not recent:
            return 0.0
        return sum(d.cost_usd for d in recent) / len(recent)

    def _check_cost_spike(self) -> CostCheckResult:
        """コスト急増を検知する。"""
        avg = self.get_7day_average_cost()
        if avg <= 0:
            return CostCheckResult(action=CostAction.ALLOW)

        today_cost = self._today_usage.cost_usd

        # 3倍超 → 停止
        if today_cost > avg * self._spike_stop_mult:
            return CostCheckResult(
                action=CostAction.STOP,
                reason=(
                    f"コスト急増検知（停止）: 本日${today_cost:.2f} > "
                    f"7日平均${avg:.2f}の{self._spike_stop_mult}倍"
                ),
                current_cost_usd=today_cost,
                limit_cost_usd=avg * self._spike_stop_mult,
            )

        # 2倍超 → 警告
        if today_cost > avg * self._spike_warning_mult:
            return CostCheckResult(
                action=CostAction.WARNING,
                reason=(
                    f"コスト急増検知（警告）: 本日${today_cost:.2f} > "
                    f"7日平均${avg:.2f}の{self._spike_warning_mult}倍"
                ),
                current_cost_usd=today_cost,
                limit_cost_usd=avg * self._spike_warning_mult,
            )

        return CostCheckResult(action=CostAction.ALLOW)

    def get_status(self) -> dict[str, Any]:
        """コスト管理状態を返す。"""
        return {
            "cycle_calls": self._current_cycle_calls,
            "cycle_call_limit": self._cycle_call_limit,
            "daily_calls": self._today_usage.llm_calls,
            "daily_call_limit": self._daily_call_limit,
            "daily_cost_usd": self._today_usage.cost_usd,
            "daily_cost_limit_usd": self._daily_cost_limit_usd,
            "7day_avg_cost_usd": self.get_7day_average_cost(),
        }
