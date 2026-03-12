"""監査ログ保持期間管理のテスト。"""

import time

from vibe_pdca.audit.retention import (
    RetentionManager,
    RetentionTarget,
)


class TestRetentionPolicy:
    def test_default_days(self):
        mgr = RetentionManager()
        policies = mgr.policies
        assert policies[RetentionTarget.AUDIT_LOG].retention_days == 365
        assert policies[RetentionTarget.OPERATION_METRICS].retention_days == 90
        assert policies[RetentionTarget.REVIEW_ORIGINAL].retention_days == 180

    def test_custom_days(self):
        mgr = RetentionManager(
            custom_days={RetentionTarget.AUDIT_LOG: 730},
        )
        assert mgr.policies[RetentionTarget.AUDIT_LOG].retention_days == 730


class TestIdentifyExpired:
    def test_all_valid(self):
        mgr = RetentionManager()
        now = time.time()
        items = [{"timestamp": now - 1000}]
        expired, valid = mgr.identify_expired(
            RetentionTarget.AUDIT_LOG, items, now=now,
        )
        assert len(expired) == 0
        assert len(valid) == 1

    def test_some_expired(self):
        mgr = RetentionManager()
        now = time.time()
        items = [
            {"timestamp": now - 400 * 86400},  # 400日前 → 期限切れ
            {"timestamp": now - 100 * 86400},   # 100日前 → 有効
        ]
        expired, valid = mgr.identify_expired(
            RetentionTarget.AUDIT_LOG, items, now=now,
        )
        assert len(expired) == 1
        assert len(valid) == 1


class TestPurge:
    def test_purge_removes_expired(self):
        mgr = RetentionManager()
        now = time.time()
        items = [
            {"timestamp": now - 400 * 86400},
            {"timestamp": now - 100 * 86400},
        ]
        result = mgr.purge(RetentionTarget.AUDIT_LOG, items, now=now)
        assert result.purged_count == 1
        assert result.remaining_count == 1
        assert len(items) == 1


class TestUpdateRetention:
    def test_extend_no_approval_needed(self):
        mgr = RetentionManager()
        assert mgr.update_retention_days(RetentionTarget.AUDIT_LOG, 730)

    def test_shorten_audit_needs_approval(self):
        mgr = RetentionManager()
        assert not mgr.update_retention_days(
            RetentionTarget.AUDIT_LOG, 180, approved=False,
        )

    def test_shorten_audit_with_approval(self):
        mgr = RetentionManager()
        assert mgr.update_retention_days(
            RetentionTarget.AUDIT_LOG, 180, approved=True,
        )

    def test_shorten_metrics_no_approval_needed(self):
        mgr = RetentionManager()
        assert mgr.update_retention_days(
            RetentionTarget.OPERATION_METRICS, 30,
        )

    def test_get_status(self):
        mgr = RetentionManager()
        status = mgr.get_status()
        assert "audit_log" in status


# ============================================================
# テスト: 保持期間バリデーション
# ============================================================


class TestRetentionDaysValidation:
    """保持期間の値バリデーション。"""

    def test_reject_zero_days(self):
        from vibe_pdca.audit.retention import RetentionManager, RetentionTarget

        mgr = RetentionManager()
        assert not mgr.update_retention_days(
            RetentionTarget.OPERATION_METRICS, 0,
        )

    def test_reject_negative_days(self):
        from vibe_pdca.audit.retention import RetentionManager, RetentionTarget

        mgr = RetentionManager()
        assert not mgr.update_retention_days(
            RetentionTarget.OPERATION_METRICS, -5,
        )


class TestRetentionManagerBarrierThreadSafety:
    """RetentionManagerのスレッドセーフティテスト（Barrier同期）。"""

    def test_concurrent_get_status(self):
        import threading

        mgr = RetentionManager()
        n_threads = 10
        ops_per_thread = 50
        barrier = threading.Barrier(n_threads)
        errors: list[Exception] = []

        def worker(tid: int) -> None:
            barrier.wait()
            try:
                for _ in range(ops_per_thread):
                    mgr.get_status()
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(t,)) for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
