"""E2E/シナリオテスト基盤。

提案4: PDCAサイクル全体のEnd-to-Endシナリオ実行と
異常系シミュレーションを提供する。

- PDCAサイクル各フェーズのシナリオ実行
- LLMレスポンスのモック
- 異常系 (全プロバイダダウン, API障害等) のシミュレーション
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


# ── ScenarioContext ──


@dataclass
class ScenarioContext:
    """E2Eシナリオの実行コンテキスト。

    Parameters
    ----------
    goal : str
        シナリオの達成目標。
    milestones : list[str]
        マイルストーン名のリスト。
    tasks : list[str]
        タスク名のリスト。
    reviews : list[str]
        レビュー結果のリスト。
    decisions : list[str]
        判定結果のリスト。
    """

    goal: str = ""
    milestones: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    reviews: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)


# ── MockLLMResponse ──


@dataclass
class MockLLMResponse:
    """モックLLMレスポンス。

    Parameters
    ----------
    content : str
        レスポンス本文。
    model : str
        モデル名。
    latency : float
        シミュレートされたレイテンシ (秒)。
    """

    content: str = ""
    model: str = "mock-gpt-4"
    latency: float = 0.1


# ── AnomalyScenario ──


class AnomalyScenario(StrEnum):
    """異常系シナリオの種別。"""

    ALL_PROVIDERS_DOWN = "all_providers_down"
    GITHUB_API_FAILURE = "github_api_failure"
    COST_LIMIT_REACHED = "cost_limit_reached"
    STUCK_TIMEOUT = "stuck_timeout"


# ── E2EScenarioRunner ──


class E2EScenarioRunner:
    """PDCAサイクル全体のE2Eシナリオを実行する。

    各フェーズをシミュレートし、実行結果を辞書で返す。
    """

    def run_plan_phase(
        self,
        context: ScenarioContext,
    ) -> dict[str, object]:
        """Planフェーズをシミュレートする。

        Returns
        -------
        dict
            phase, goal, milestones, tasks, timestamp を含む結果。
        """
        logger.info("Plan フェーズ開始: goal=%s", context.goal)
        return {
            "phase": "plan",
            "goal": context.goal,
            "milestones": list(context.milestones),
            "tasks": list(context.tasks),
            "timestamp": time.time(),
        }

    def run_do_phase(
        self,
        context: ScenarioContext,
    ) -> dict[str, object]:
        """Doフェーズをシミュレートする。

        Returns
        -------
        dict
            phase, tasks_executed, timestamp を含む結果。
        """
        logger.info(
            "Do フェーズ開始: tasks=%d",
            len(context.tasks),
        )
        return {
            "phase": "do",
            "tasks_executed": len(context.tasks),
            "timestamp": time.time(),
        }

    def run_check_phase(
        self,
        context: ScenarioContext,
    ) -> dict[str, object]:
        """Checkフェーズをシミュレートする。

        Returns
        -------
        dict
            phase, reviews, all_passed, timestamp を含む結果。
        """
        logger.info(
            "Check フェーズ開始: reviews=%d",
            len(context.reviews),
        )
        all_passed = all(r == "pass" for r in context.reviews)
        return {
            "phase": "check",
            "reviews": list(context.reviews),
            "all_passed": all_passed,
            "timestamp": time.time(),
        }

    def run_act_phase(
        self,
        context: ScenarioContext,
    ) -> dict[str, object]:
        """Actフェーズをシミュレートする。

        Returns
        -------
        dict
            phase, decisions, continue_cycle, timestamp を含む結果。
        """
        logger.info(
            "Act フェーズ開始: decisions=%d",
            len(context.decisions),
        )
        continue_cycle = "reject" in context.decisions
        return {
            "phase": "act",
            "decisions": list(context.decisions),
            "continue_cycle": continue_cycle,
            "timestamp": time.time(),
        }

    def run_full_cycle(
        self,
        context: ScenarioContext,
    ) -> dict[str, object]:
        """PDCAサイクル全体をシミュレートする。

        Returns
        -------
        dict
            phases (各フェーズの結果), success, duration を含む結果。
        """
        start = time.time()
        plan = self.run_plan_phase(context)
        do = self.run_do_phase(context)
        check = self.run_check_phase(context)
        act = self.run_act_phase(context)
        duration = time.time() - start

        success = bool(check.get("all_passed")) and not act.get(
            "continue_cycle",
        )
        logger.info(
            "フルサイクル完了: success=%s, duration=%.3fs",
            success,
            duration,
        )
        return {
            "phases": {
                "plan": plan,
                "do": do,
                "check": check,
                "act": act,
            },
            "success": success,
            "duration": duration,
        }


# ── AnomalySimulator ──


class AnomalySimulator:
    """異常系シナリオのシミュレーション。

    各異常シナリオに対するエラー情報とリカバリ方法を返す。
    """

    _SCENARIOS: dict[AnomalyScenario, dict[str, str]] = {
        AnomalyScenario.ALL_PROVIDERS_DOWN: {
            "error": "全LLMプロバイダが応答不能",
            "recovery": "フォールバックプロバイダへ切替",
        },
        AnomalyScenario.GITHUB_API_FAILURE: {
            "error": "GitHub APIがHTTP 503を返却",
            "recovery": "指数バックオフで再試行",
        },
        AnomalyScenario.COST_LIMIT_REACHED: {
            "error": "コスト上限に到達",
            "recovery": "低コストモデルへ切替",
        },
        AnomalyScenario.STUCK_TIMEOUT: {
            "error": "処理がタイムアウト",
            "recovery": "タスクを中断し次フェーズへ遷移",
        },
    }

    def simulate(
        self,
        scenario: AnomalyScenario,
    ) -> dict[str, str]:
        """異常シナリオをシミュレートする。

        Parameters
        ----------
        scenario : AnomalyScenario
            シミュレート対象のシナリオ。

        Returns
        -------
        dict
            scenario, error, recovery を含む辞書。
        """
        info = self._SCENARIOS.get(
            scenario,
            {"error": "不明なエラー", "recovery": "手動介入"},
        )
        logger.warning(
            "異常シミュレーション: %s – %s",
            scenario,
            info["error"],
        )
        return {
            "scenario": scenario.value,
            "error": info["error"],
            "recovery": info["recovery"],
        }
