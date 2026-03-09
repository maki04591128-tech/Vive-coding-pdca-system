"""サーキットブレーカーのユニットテスト。"""

import threading
import time

import pytest

from vibe_pdca.llm.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)


@pytest.fixture
def cb():
    return CircuitBreaker(
        name="test",
        config=CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1.0,  # テスト用に短縮
            success_threshold=2,
        ),
    )


class TestCircuitBreakerState:
    """状態遷移のテスト。"""

    def test_initial_state_is_closed(self, cb):
        assert cb.state == CircuitState.CLOSED

    def test_stays_closed_below_threshold(self, cb):
        cb.record_failure("err1")
        cb.record_failure("err2")
        assert cb.state == CircuitState.CLOSED

    def test_opens_at_threshold(self, cb):
        for i in range(3):
            cb.record_failure(f"err{i}")
        assert cb.state == CircuitState.OPEN

    def test_transitions_to_half_open_after_timeout(self, cb):
        for i in range(3):
            cb.record_failure(f"err{i}")
        assert cb.state == CircuitState.OPEN

        time.sleep(1.1)  # recovery_timeout = 1.0
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_closes_on_success(self, cb):
        for i in range(3):
            cb.record_failure(f"err{i}")
        time.sleep(1.1)

        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_reopens_on_failure(self, cb):
        for i in range(3):
            cb.record_failure(f"err{i}")
        time.sleep(1.1)

        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure("err_again")
        assert cb.state == CircuitState.OPEN

    def test_success_resets_consecutive_failures(self, cb):
        cb.record_failure("err1")
        cb.record_failure("err2")
        cb.record_success()
        cb.record_failure("err3")
        # 1 failure after reset, should still be CLOSED
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerCallPermission:
    """呼び出し許可のテスト。"""

    def test_permits_when_closed(self, cb):
        assert cb.is_call_permitted is True

    def test_denies_when_open(self, cb):
        for i in range(3):
            cb.record_failure(f"err{i}")
        assert cb.is_call_permitted is False

    def test_permits_limited_when_half_open(self, cb):
        for i in range(3):
            cb.record_failure(f"err{i}")
        time.sleep(1.1)
        assert cb.is_call_permitted is True


class TestCircuitBreakerManualControl:
    """手動制御のテスト。"""

    def test_force_open(self, cb):
        cb.force_open(reason="テスト")
        assert cb.state == CircuitState.OPEN
        assert cb.is_call_permitted is False

    def test_force_close(self, cb):
        for i in range(3):
            cb.record_failure(f"err{i}")
        cb.force_close(reason="復旧確認")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_call_permitted is True


class TestCircuitBreakerMetrics:
    """メトリクスのテスト。"""

    def test_records_metrics(self, cb):
        cb.record_success()
        cb.record_failure("err")
        assert cb.metrics.total_calls == 2
        assert cb.metrics.total_failures == 1

    def test_records_fallback(self, cb):
        cb.record_fallback()
        cb.record_fallback()
        assert cb.metrics.total_fallbacks == 2

    def test_records_state_changes(self, cb):
        for i in range(3):
            cb.record_failure(f"err{i}")
        assert len(cb.metrics.state_changes) == 1
        assert cb.metrics.state_changes[0]["to"] == "open"

    def test_concurrent_record_fallback(self, cb):
        """複数スレッドから同時に record_fallback() してもカウントが正確なこと。"""
        n = 50

        def worker() -> None:
            cb.record_fallback()

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert cb.metrics.total_fallbacks == n
