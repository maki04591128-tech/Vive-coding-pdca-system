"""コスト管理のテスト。"""

from vibe_pdca.engine.cost_manager import (
    CostAction,
    CostManager,
    DailyUsage,
)


class TestCycleLimits:
    def test_within_limit(self):
        cm = CostManager()
        for _ in range(80):
            result = cm.record_call()
        assert result.action == CostAction.ALLOW

    def test_exceeds_limit(self):
        cm = CostManager(cycle_call_limit=5)
        for _ in range(6):
            result = cm.record_call()
        assert result.action == CostAction.STOP

    def test_reset_cycle(self):
        cm = CostManager()
        for _ in range(10):
            cm.record_call()
        cm.reset_cycle()
        assert cm.current_cycle_calls == 0


class TestDailyLimits:
    def test_daily_call_limit(self):
        cm = CostManager(daily_call_limit=3)
        for _ in range(4):
            result = cm.record_call()
        assert result.action == CostAction.STOP

    def test_daily_cost_limit(self):
        cm = CostManager(daily_cost_limit_usd=1.0)
        result = cm.record_call(cost_usd=1.50)
        assert result.action == CostAction.STOP


class TestCostSpike:
    def test_spike_warning(self):
        cm = CostManager()
        # 7日分の履歴を作成（各$5）
        for _ in range(7):
            cm._today_usage = DailyUsage(cost_usd=5.0)
            cm.close_day()
        # 本日$11 → 7日平均$5の2倍超
        cm.record_call(cost_usd=11.0)
        result = cm.check_limits()
        assert result.action == CostAction.WARNING

    def test_spike_stop(self):
        cm = CostManager()
        for _ in range(7):
            cm._today_usage = DailyUsage(cost_usd=5.0)
            cm.close_day()
        # 本日$16 → 7日平均$5の3倍超
        cm.record_call(cost_usd=16.0)
        result = cm.check_limits()
        assert result.action == CostAction.STOP

    def test_no_spike_without_history(self):
        cm = CostManager()
        cm.record_call(cost_usd=1.0)
        result = cm.check_limits()
        assert result.action == CostAction.ALLOW


class TestCostStatus:
    def test_get_status(self):
        cm = CostManager()
        status = cm.get_status()
        assert "cycle_calls" in status
        assert "daily_cost_limit_usd" in status
