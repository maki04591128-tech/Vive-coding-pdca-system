"""E2E/シナリオテスト基盤のテスト。"""

from __future__ import annotations

from vibe_pdca.engine.e2e_scenario import (
    AnomalyScenario,
    AnomalySimulator,
    E2EScenarioRunner,
    MockLLMResponse,
    ScenarioContext,
)

# ── ScenarioContext ──


class TestScenarioContext:
    """ScenarioContextデータクラスのテスト。"""

    def test_defaults(self) -> None:
        ctx = ScenarioContext()
        assert ctx.goal == ""
        assert ctx.milestones == []
        assert ctx.tasks == []
        assert ctx.reviews == []
        assert ctx.decisions == []

    def test_custom_fields(self) -> None:
        ctx = ScenarioContext(
            goal="テスト目標",
            milestones=["M1"],
            tasks=["T1", "T2"],
            reviews=["pass"],
            decisions=["accept"],
        )
        assert ctx.goal == "テスト目標"
        assert len(ctx.tasks) == 2


# ── MockLLMResponse ──


class TestMockLLMResponse:
    """MockLLMResponseデータクラスのテスト。"""

    def test_defaults(self) -> None:
        resp = MockLLMResponse()
        assert resp.content == ""
        assert resp.model == "mock-gpt-4"
        assert resp.latency == 0.1

    def test_custom(self) -> None:
        resp = MockLLMResponse(
            content="hello",
            model="claude-3",
            latency=0.5,
        )
        assert resp.content == "hello"
        assert resp.model == "claude-3"


# ── AnomalyScenario ──


class TestAnomalyScenario:
    """AnomalyScenario列挙型のテスト。"""

    def test_values(self) -> None:
        assert AnomalyScenario.ALL_PROVIDERS_DOWN == "all_providers_down"
        assert AnomalyScenario.GITHUB_API_FAILURE == "github_api_failure"
        assert AnomalyScenario.COST_LIMIT_REACHED == "cost_limit_reached"
        assert AnomalyScenario.STUCK_TIMEOUT == "stuck_timeout"

    def test_member_count(self) -> None:
        assert len(AnomalyScenario) == 4


# ── E2EScenarioRunner ──


class TestE2EScenarioRunner:
    """E2EScenarioRunnerのテスト。"""

    def _make_context(self) -> ScenarioContext:
        return ScenarioContext(
            goal="ユニットテスト作成",
            milestones=["M1"],
            tasks=["T1", "T2"],
            reviews=["pass", "pass"],
            decisions=["accept"],
        )

    def test_run_plan_phase(self) -> None:
        runner = E2EScenarioRunner()
        result = runner.run_plan_phase(self._make_context())
        assert result["phase"] == "plan"
        assert result["goal"] == "ユニットテスト作成"
        assert "timestamp" in result

    def test_run_do_phase(self) -> None:
        runner = E2EScenarioRunner()
        result = runner.run_do_phase(self._make_context())
        assert result["phase"] == "do"
        assert result["tasks_executed"] == 2

    def test_run_check_phase_all_pass(self) -> None:
        runner = E2EScenarioRunner()
        result = runner.run_check_phase(self._make_context())
        assert result["phase"] == "check"
        assert result["all_passed"] is True

    def test_run_check_phase_with_failure(self) -> None:
        runner = E2EScenarioRunner()
        ctx = ScenarioContext(reviews=["pass", "fail"])
        result = runner.run_check_phase(ctx)
        assert result["all_passed"] is False

    def test_run_act_phase_accept(self) -> None:
        runner = E2EScenarioRunner()
        result = runner.run_act_phase(self._make_context())
        assert result["phase"] == "act"
        assert result["continue_cycle"] is False

    def test_run_act_phase_reject(self) -> None:
        runner = E2EScenarioRunner()
        ctx = ScenarioContext(decisions=["reject"])
        result = runner.run_act_phase(ctx)
        assert result["continue_cycle"] is True

    def test_run_full_cycle_success(self) -> None:
        runner = E2EScenarioRunner()
        result = runner.run_full_cycle(self._make_context())
        assert result["success"] is True
        assert "duration" in result
        assert "phases" in result

    def test_run_full_cycle_failure(self) -> None:
        runner = E2EScenarioRunner()
        ctx = ScenarioContext(
            goal="失敗シナリオ",
            tasks=["T1"],
            reviews=["fail"],
            decisions=["reject"],
        )
        result = runner.run_full_cycle(ctx)
        assert result["success"] is False

    def test_full_cycle_has_all_phases(self) -> None:
        runner = E2EScenarioRunner()
        result = runner.run_full_cycle(self._make_context())
        phases = result["phases"]
        assert "plan" in phases
        assert "do" in phases
        assert "check" in phases
        assert "act" in phases

    def test_run_check_empty_reviews(self) -> None:
        runner = E2EScenarioRunner()
        ctx = ScenarioContext(reviews=[])
        result = runner.run_check_phase(ctx)
        assert result["all_passed"] is True


# ── AnomalySimulator ──


class TestAnomalySimulator:
    """AnomalySimulatorのテスト。"""

    def test_all_providers_down(self) -> None:
        sim = AnomalySimulator()
        result = sim.simulate(AnomalyScenario.ALL_PROVIDERS_DOWN)
        assert result["scenario"] == "all_providers_down"
        assert "error" in result
        assert "recovery" in result

    def test_github_api_failure(self) -> None:
        sim = AnomalySimulator()
        result = sim.simulate(AnomalyScenario.GITHUB_API_FAILURE)
        assert result["scenario"] == "github_api_failure"

    def test_cost_limit_reached(self) -> None:
        sim = AnomalySimulator()
        result = sim.simulate(AnomalyScenario.COST_LIMIT_REACHED)
        assert result["scenario"] == "cost_limit_reached"

    def test_stuck_timeout(self) -> None:
        sim = AnomalySimulator()
        result = sim.simulate(AnomalyScenario.STUCK_TIMEOUT)
        assert result["scenario"] == "stuck_timeout"
