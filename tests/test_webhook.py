"""Webhook/イベント駆動アーキテクチャのテスト。"""

from __future__ import annotations

import pytest

from vibe_pdca.engine.webhook import (
    BackpressureController,
    EventFilter,
    EventQueue,
    WebhookEvent,
    WebhookEventType,
    WebhookRouter,
)

# ── WebhookEventType ──


class TestWebhookEventType:
    """WebhookEventType列挙型のテスト。"""

    def test_values(self) -> None:
        assert WebhookEventType.ISSUE_OPENED == "issue_opened"
        assert WebhookEventType.PR_REVIEW == "pr_review"
        assert WebhookEventType.CHECK_SUITE == "check_suite"
        assert WebhookEventType.ISSUE_COMMENT == "issue_comment"

    def test_member_count(self) -> None:
        assert len(WebhookEventType) == 4


# ── WebhookEvent ──


class TestWebhookEvent:
    """WebhookEventデータクラスのテスト。"""

    def test_defaults(self) -> None:
        evt = WebhookEvent(event_type=WebhookEventType.ISSUE_OPENED)
        assert evt.payload == {}
        assert evt.event_id
        assert evt.received_at > 0

    def test_custom_fields(self) -> None:
        evt = WebhookEvent(
            event_type=WebhookEventType.PR_REVIEW,
            payload={"action": "submitted"},
            received_at=1000.0,
            event_id="abc123",
        )
        assert evt.event_type == WebhookEventType.PR_REVIEW
        assert evt.payload == {"action": "submitted"}
        assert evt.received_at == 1000.0
        assert evt.event_id == "abc123"

    def test_unique_event_ids(self) -> None:
        e1 = WebhookEvent(event_type=WebhookEventType.ISSUE_OPENED)
        e2 = WebhookEvent(event_type=WebhookEventType.ISSUE_OPENED)
        assert e1.event_id != e2.event_id


# ── EventFilter ──


class TestEventFilter:
    """EventFilterのテスト。"""

    def test_empty_filter_matches_all(self) -> None:
        f = EventFilter()
        evt = WebhookEvent(event_type=WebhookEventType.ISSUE_OPENED)
        assert f.matches(evt)

    def test_type_filter(self) -> None:
        f = EventFilter(event_types=[WebhookEventType.PR_REVIEW])
        assert f.matches(
            WebhookEvent(event_type=WebhookEventType.PR_REVIEW),
        )
        assert not f.matches(
            WebhookEvent(event_type=WebhookEventType.CHECK_SUITE),
        )

    def test_repository_filter(self) -> None:
        f = EventFilter(repository="owner/repo")
        evt = WebhookEvent(
            event_type=WebhookEventType.ISSUE_OPENED,
            payload={"repository": "owner/repo"},
        )
        assert f.matches(evt)

    def test_repository_filter_mismatch(self) -> None:
        f = EventFilter(repository="owner/repo")
        evt = WebhookEvent(
            event_type=WebhookEventType.ISSUE_OPENED,
            payload={"repository": "other/repo"},
        )
        assert not f.matches(evt)


# ── EventQueue ──


class TestEventQueue:
    """EventQueueのテスト。"""

    def test_push_pop(self) -> None:
        q = EventQueue(max_size=10)
        evt = WebhookEvent(event_type=WebhookEventType.ISSUE_OPENED)
        assert q.push(evt)
        assert q.size == 1
        popped = q.pop()
        assert popped is evt
        assert q.size == 0

    def test_pop_empty(self) -> None:
        q = EventQueue()
        assert q.pop() is None

    def test_peek(self) -> None:
        q = EventQueue()
        evt = WebhookEvent(event_type=WebhookEventType.PR_REVIEW)
        q.push(evt)
        assert q.peek() is evt
        assert q.size == 1  # peekはサイズを変えない

    def test_peek_empty(self) -> None:
        q = EventQueue()
        assert q.peek() is None

    def test_is_full(self) -> None:
        q = EventQueue(max_size=2)
        q.push(WebhookEvent(event_type=WebhookEventType.ISSUE_OPENED))
        assert not q.is_full
        q.push(WebhookEvent(event_type=WebhookEventType.PR_REVIEW))
        assert q.is_full

    def test_push_when_full_returns_false(self) -> None:
        q = EventQueue(max_size=1)
        q.push(WebhookEvent(event_type=WebhookEventType.ISSUE_OPENED))
        result = q.push(
            WebhookEvent(event_type=WebhookEventType.PR_REVIEW),
        )
        assert result is False
        assert q.size == 1

    def test_clear(self) -> None:
        q = EventQueue()
        for _ in range(5):
            q.push(WebhookEvent(event_type=WebhookEventType.ISSUE_OPENED))
        q.clear()
        assert q.size == 0

    def test_fifo_order(self) -> None:
        q = EventQueue()
        e1 = WebhookEvent(
            event_type=WebhookEventType.ISSUE_OPENED,
            event_id="first",
        )
        e2 = WebhookEvent(
            event_type=WebhookEventType.PR_REVIEW,
            event_id="second",
        )
        q.push(e1)
        q.push(e2)
        assert q.pop() is e1
        assert q.pop() is e2

    def test_concurrent_push_respects_max_size(self) -> None:
        """複数スレッドからの同時pushでmax_sizeを超えないこと。"""
        import threading

        q = EventQueue(max_size=50)
        results: list[bool] = []
        lock = threading.Lock()

        def push_many() -> None:
            for _ in range(30):
                ok = q.push(WebhookEvent(event_type=WebhookEventType.ISSUE_OPENED))
                with lock:
                    results.append(ok)

        threads = [threading.Thread(target=push_many) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert q.size <= 50
        assert results.count(True) == q.size


# ── BackpressureController ──


class TestBackpressureController:
    """BackpressureControllerのテスト。"""

    def test_no_backpressure(self) -> None:
        q = EventQueue(max_size=10)
        ctrl = BackpressureController(threshold=0.8)
        assert not ctrl.check(q)

    def test_backpressure_triggered(self) -> None:
        q = EventQueue(max_size=10)
        for _ in range(8):
            q.push(WebhookEvent(event_type=WebhookEventType.ISSUE_OPENED))
        ctrl = BackpressureController(threshold=0.8)
        assert ctrl.check(q)

    def test_threshold_property(self) -> None:
        ctrl = BackpressureController(threshold=0.5)
        assert ctrl.threshold == 0.5

    def test_invalid_threshold(self) -> None:
        with pytest.raises(ValueError):
            BackpressureController(threshold=1.5)

    def test_strategy(self) -> None:
        ctrl = BackpressureController()
        assert ctrl.strategy() == "drop_oldest"


# ── WebhookRouter ──


class TestWebhookRouter:
    """WebhookRouterのテスト。"""

    def test_register_and_route(self) -> None:
        router = WebhookRouter()
        router.register_handler(
            WebhookEventType.ISSUE_OPENED,
            "handle_issue",
        )
        evt = WebhookEvent(event_type=WebhookEventType.ISSUE_OPENED)
        assert router.route(evt) == "handle_issue"

    def test_unhandled_event(self) -> None:
        router = WebhookRouter()
        evt = WebhookEvent(event_type=WebhookEventType.CHECK_SUITE)
        assert router.route(evt) == "unhandled"

    def test_list_handlers(self) -> None:
        router = WebhookRouter()
        router.register_handler(
            WebhookEventType.ISSUE_OPENED,
            "handle_issue",
        )
        router.register_handler(
            WebhookEventType.PR_REVIEW,
            "handle_pr",
        )
        handlers = router.list_handlers()
        assert handlers == {
            "issue_opened": "handle_issue",
            "pr_review": "handle_pr",
        }

    def test_overwrite_handler(self) -> None:
        router = WebhookRouter()
        router.register_handler(
            WebhookEventType.ISSUE_OPENED,
            "old_handler",
        )
        router.register_handler(
            WebhookEventType.ISSUE_OPENED,
            "new_handler",
        )
        evt = WebhookEvent(event_type=WebhookEventType.ISSUE_OPENED)
        assert router.route(evt) == "new_handler"


class TestEventQueueBarrierThreadSafety:
    """EventQueueのBarrierスレッドセーフティテスト。"""

    def test_concurrent_push(self) -> None:
        import threading

        queue = EventQueue(max_size=1000)
        n_threads = 10
        ops_per_thread = 50
        barrier = threading.Barrier(n_threads)

        def worker(tid: int) -> None:
            barrier.wait()
            for i in range(ops_per_thread):
                evt = WebhookEvent(
                    event_type=WebhookEventType.ISSUE_OPENED,
                    payload={"tid": tid, "i": i},
                )
                queue.push(evt)

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert queue.size == n_threads * ops_per_thread
