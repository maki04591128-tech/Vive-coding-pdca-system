"""停止条件・縮退モード管理のテスト。"""

import time

from vibe_pdca.engine.stop_conditions import (
    DegradeAction,
    DegradeManager,
    DegradePriority,
    StackDetector,
)

# ============================================================
# テスト: スタック検知
# ============================================================


class TestStackDetector:
    def test_initial_not_stacked(self):
        detector = StackDetector()
        assert not detector.is_stacked()

    def test_heartbeat_resets(self):
        detector = StackDetector(timeout_seconds=10)
        now = time.time()
        detector.heartbeat(phase="DO")
        assert not detector.is_stacked(now=now + 5)

    def test_stacked_after_timeout(self):
        detector = StackDetector(timeout_seconds=10)
        old = time.time() - 20
        detector._last_heartbeat = old
        assert detector.is_stacked()

    def test_heartbeat_count(self):
        detector = StackDetector()
        detector.heartbeat(phase="PLAN")
        detector.heartbeat(phase="DO")
        assert detector.heartbeat_count == 2

    def test_elapsed_seconds(self):
        detector = StackDetector()
        now = time.time()
        detector._last_heartbeat = now - 100
        elapsed = detector.elapsed_seconds(now=now)
        assert abs(elapsed - 100) < 1

    def test_get_status(self):
        detector = StackDetector(timeout_seconds=60)
        status = detector.get_status()
        assert "is_stacked" in status
        assert "timeout_seconds" in status
        assert status["timeout_seconds"] == 60


# ============================================================
# テスト: 縮退モード管理
# ============================================================


class TestDegradeManager:
    def test_initial_not_degraded(self):
        mgr = DegradeManager()
        assert not mgr.is_degraded

    def test_report_failure_audit_log_stops(self):
        mgr = DegradeManager()
        action = mgr.report_failure(DegradePriority.AUDIT_LOG, "書き込み不能")
        assert action == DegradeAction.STOP
        assert mgr.is_degraded
        assert mgr.should_stop()

    def test_report_failure_notify_continues(self):
        mgr = DegradeManager()
        action = mgr.report_failure(DegradePriority.STOP_NOTIFY, "Discord障害")
        assert action == DegradeAction.CONTINUE
        assert mgr.is_degraded
        assert not mgr.should_stop()

    def test_report_failure_review_fallback(self):
        mgr = DegradeManager()
        action = mgr.report_failure(DegradePriority.CHECK_REPORT, "モデル障害")
        assert action == DegradeAction.FALLBACK

    def test_report_failure_review_reduce(self):
        mgr = DegradeManager()
        action = mgr.report_failure(DegradePriority.FULL_REVIEW, "2名不応答")
        assert action == DegradeAction.REDUCE

    def test_recover(self):
        mgr = DegradeManager()
        mgr.report_failure(DegradePriority.STOP_NOTIFY, "障害")
        assert mgr.is_degraded
        mgr.recover(DegradePriority.STOP_NOTIFY)
        assert not mgr.is_degraded

    def test_get_status(self):
        mgr = DegradeManager()
        status = mgr.get_status()
        assert "is_degraded" in status
        assert "rules" in status
        assert len(status["rules"]) == 5
