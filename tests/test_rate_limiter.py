"""レート制限とスロットリングのテスト。"""

from __future__ import annotations

import pytest

from vibe_pdca.engine.rate_limiter import (
    BackoffStrategy,
    RateLimitConfig,
    RateLimitDashboard,
    RateLimitTracker,
    TokenBucket,
)

# ── RateLimitConfig ──


class TestRateLimitConfig:
    """RateLimitConfigデータクラスのテスト。"""

    def test_defaults(self) -> None:
        cfg = RateLimitConfig(
            provider="openai",
            requests_per_minute=60,
            tokens_per_minute=90000,
        )
        assert cfg.burst_size == 10

    def test_custom_burst(self) -> None:
        cfg = RateLimitConfig(
            provider="anthropic",
            requests_per_minute=30,
            tokens_per_minute=50000,
            burst_size=20,
        )
        assert cfg.burst_size == 20
        assert cfg.provider == "anthropic"


# ── TokenBucket ──


class TestTokenBucket:
    """TokenBucketのテスト。"""

    def test_initial_capacity(self) -> None:
        bucket = TokenBucket(capacity=10, rate=1.0)
        assert bucket.available == pytest.approx(10.0, abs=0.5)

    def test_consume_success(self) -> None:
        bucket = TokenBucket(capacity=10, rate=1.0)
        assert bucket.consume(1) is True

    def test_consume_depletes(self) -> None:
        bucket = TokenBucket(capacity=3, rate=0.0)
        assert bucket.consume(1) is True
        assert bucket.consume(1) is True
        assert bucket.consume(1) is True
        assert bucket.consume(1) is False

    def test_consume_multiple(self) -> None:
        bucket = TokenBucket(capacity=10, rate=0.0)
        assert bucket.consume(5) is True
        assert bucket.consume(5) is True
        assert bucket.consume(1) is False

    def test_reset(self) -> None:
        bucket = TokenBucket(capacity=5, rate=0.0)
        bucket.consume(5)
        bucket.reset()
        assert bucket.available == pytest.approx(5.0, abs=0.5)

    def test_consume_zero_rate_no_refill(self) -> None:
        bucket = TokenBucket(capacity=2, rate=0.0)
        bucket.consume(2)
        assert bucket.consume(1) is False


# ── RateLimitTracker ──


class TestRateLimitTracker:
    """RateLimitTrackerのテスト。"""

    def _make_tracker(self) -> RateLimitTracker:
        tracker = RateLimitTracker()
        tracker.add_provider(
            RateLimitConfig(
                provider="openai",
                requests_per_minute=60,
                tokens_per_minute=90000,
                burst_size=10,
            ),
        )
        return tracker

    def test_check_success(self) -> None:
        tracker = self._make_tracker()
        assert tracker.check("openai") is True

    def test_check_unknown_provider(self) -> None:
        tracker = self._make_tracker()
        assert tracker.check("unknown") is False

    def test_check_exhausted(self) -> None:
        tracker = RateLimitTracker()
        tracker.add_provider(
            RateLimitConfig(
                provider="limited",
                requests_per_minute=60,
                tokens_per_minute=1000,
                burst_size=2,
            ),
        )
        assert tracker.check("limited") is True
        assert tracker.check("limited") is True
        assert tracker.check("limited") is False

    def test_wait_time_available(self) -> None:
        tracker = self._make_tracker()
        assert tracker.wait_time("openai") == 0.0

    def test_wait_time_unknown(self) -> None:
        tracker = self._make_tracker()
        assert tracker.wait_time("unknown") == 0.0

    def test_get_usage(self) -> None:
        tracker = self._make_tracker()
        usage = tracker.get_usage("openai")
        assert usage["provider"] == "openai"
        assert usage["capacity"] == 10

    def test_get_usage_unknown(self) -> None:
        tracker = self._make_tracker()
        usage = tracker.get_usage("nope")
        assert usage["available"] == 0


# ── BackoffStrategy ──


class TestBackoffStrategy:
    """BackoffStrategyのテスト。"""

    def test_first_attempt(self) -> None:
        bs = BackoffStrategy(base_delay=1.0)
        assert bs.calculate(1) == 1.0

    def test_exponential_growth(self) -> None:
        bs = BackoffStrategy(base_delay=1.0)
        assert bs.calculate(1) == 1.0
        assert bs.calculate(2) == 2.0
        assert bs.calculate(3) == 4.0
        assert bs.calculate(4) == 8.0

    def test_exceeds_max_attempts(self) -> None:
        bs = BackoffStrategy(max_attempts=3)
        assert bs.calculate(4) == -1.0

    def test_properties(self) -> None:
        bs = BackoffStrategy(max_attempts=7, base_delay=2.0)
        assert bs.max_attempts == 7
        assert bs.base_delay == 2.0

    def test_custom_base_delay(self) -> None:
        bs = BackoffStrategy(base_delay=0.5)
        assert bs.calculate(1) == 0.5
        assert bs.calculate(2) == 1.0


# ── RateLimitDashboard ──


class TestRateLimitDashboard:
    """RateLimitDashboardのテスト。"""

    def _make_dashboard(self) -> RateLimitDashboard:
        tracker = RateLimitTracker()
        tracker.add_provider(
            RateLimitConfig(
                provider="openai",
                requests_per_minute=60,
                tokens_per_minute=90000,
            ),
        )
        tracker.add_provider(
            RateLimitConfig(
                provider="anthropic",
                requests_per_minute=30,
                tokens_per_minute=50000,
            ),
        )
        return RateLimitDashboard(tracker)

    def test_get_all_providers(self) -> None:
        dash = self._make_dashboard()
        providers = dash.get_all_providers()
        assert "openai" in providers
        assert "anthropic" in providers

    def test_get_status(self) -> None:
        dash = self._make_dashboard()
        status = dash.get_status()
        assert "openai" in status
        assert "anthropic" in status

    def test_utilization_fresh(self) -> None:
        dash = self._make_dashboard()
        util = dash.get_utilization("openai")
        assert 0.0 <= util <= 1.0

    def test_utilization_unknown(self) -> None:
        dash = self._make_dashboard()
        assert dash.get_utilization("missing") == 0.0


# ── TokenBucket スレッドセーフティ ──


class TestTokenBucketThreadSafety:
    """TokenBucket の並行アクセスで状態が壊れないことを検証する。"""

    def test_concurrent_consume(self) -> None:
        """複数スレッドが同時にconsumeしても合計消費数がcapacity以下。"""
        import threading

        bucket = TokenBucket(capacity=100, rate=0.0)  # 補充なし
        success_count = 0
        lock = threading.Lock()

        def consume_one() -> None:
            nonlocal success_count
            if bucket.consume(1):
                with lock:
                    success_count += 1

        threads = [threading.Thread(target=consume_one) for _ in range(200)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 補充なし100トークンに対して200スレッド → 100以下しか成功しない
        assert success_count <= 100
