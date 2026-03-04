"""Suppress Listのテスト。"""

import time

from vibe_pdca.engine.suppress_list import SuppressList


class TestSuppressRegistration:
    def test_register(self):
        sl = SuppressList()
        entry = sl.register(
            pattern="テスト誤検知",
            reason="既知の問題",
            registered_by="admin",
            approved=True,
        )
        assert entry.approved
        assert sl.entry_count == 1

    def test_unapproved_not_active(self):
        sl = SuppressList()
        sl.register(
            pattern="テスト",
            reason="未承認",
            registered_by="user",
            approved=False,
        )
        assert sl.active_count == 0


class TestSuppressCheck:
    def test_suppressed_finding(self):
        sl = SuppressList()
        sl.register(
            pattern="既知のバグ",
            reason="FP",
            registered_by="admin",
            approved=True,
        )
        assert sl.is_suppressed("この指摘は既知のバグです")

    def test_not_suppressed(self):
        sl = SuppressList()
        sl.register(
            pattern="別パターン",
            reason="FP",
            registered_by="admin",
            approved=True,
        )
        assert not sl.is_suppressed("新しい問題が発見されました")


class TestSuppressApproval:
    def test_approve(self):
        sl = SuppressList()
        entry = sl.register(
            pattern="テスト",
            reason="FP",
            registered_by="user",
        )
        assert sl.approve(entry.id)
        assert sl.active_count == 1

    def test_approve_unknown(self):
        sl = SuppressList()
        assert not sl.approve("unknown-id")


class TestSuppressExpiry:
    def test_expired_not_active(self):
        sl = SuppressList()
        entry = sl.register(
            pattern="テスト",
            reason="FP",
            registered_by="admin",
            approved=True,
            expires_days=1,
        )
        entry.expires_at = time.time() - 1000
        assert sl.active_count == 0

    def test_purge_expired(self):
        sl = SuppressList()
        entry = sl.register(
            pattern="テスト",
            reason="FP",
            registered_by="admin",
            approved=True,
            expires_days=1,
        )
        entry.expires_at = time.time() - 1000
        purged = sl.purge_expired()
        assert purged == 1

    def test_remove(self):
        sl = SuppressList()
        entry = sl.register(
            pattern="テスト",
            reason="FP",
            registered_by="admin",
        )
        assert sl.remove(entry.id)
        assert sl.entry_count == 0

    def test_get_status(self):
        sl = SuppressList()
        status = sl.get_status()
        assert "total_entries" in status
