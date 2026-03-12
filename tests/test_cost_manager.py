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


class TestCostManagerThreadSafety:
    """CostManagerのスレッドセーフティテスト。"""

    def test_concurrent_record_call(self):
        import threading

        cm = CostManager(cycle_call_limit=10000, daily_call_limit=10000)
        n_threads = 10
        calls_per_thread = 100
        barrier = threading.Barrier(n_threads)

        def worker():
            barrier.wait()
            for _ in range(calls_per_thread):
                cm.record_call(tokens=1, cost_usd=0.01)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected = n_threads * calls_per_thread
        assert cm.current_cycle_calls == expected
        assert cm.today_usage.llm_calls == expected
        assert cm.today_usage.llm_tokens == expected


class TestCloseDayDate:
    """close_day()でDailyUsage.dateが自動設定されることをテスト。"""

    def test_close_day_sets_date(self):
        import datetime

        cm = CostManager()
        cm.record_call(cost_usd=1.0)
        cm.close_day()
        history = cm._daily_history
        assert len(history) == 1
        assert history[0].date == datetime.date.today().isoformat()

    def test_close_day_preserves_explicit_date(self):
        cm = CostManager()
        cm._today_usage = DailyUsage(date="2025-01-15", cost_usd=5.0)
        cm.close_day()
        history = cm._daily_history
        assert history[0].date == "2025-01-15"
