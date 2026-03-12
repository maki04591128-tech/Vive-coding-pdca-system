"""Discord連携のテスト。"""

import time

import pytest

from vibe_pdca.engine.discord_liaison import (
    ApprovalStatus,
    DiscordLiaison,
    NotificationType,
)

# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def liaison():
    return DiscordLiaison(webhook_url="https://test.webhook", channel_id="ch-1")


# ============================================================
# テスト: 承認リクエスト
# ============================================================


class TestApprovalRequests:
    def test_create_request(self, liaison):
        req = liaison.create_approval_request("テスト操作")
        assert req.status == ApprovalStatus.PENDING
        assert req.approval_count == 0
        assert liaison.pending_approval_count == 1

    def test_approve_single(self, liaison):
        req = liaison.create_approval_request("テスト操作")
        liaison.approve(req.id, "user-1")
        assert req.approval_count == 1
        assert req.status == ApprovalStatus.PENDING  # 4/4未達

    def test_approve_completes_at_4(self, liaison):
        req = liaison.create_approval_request("テスト操作")
        for i in range(4):
            liaison.approve(req.id, f"user-{i}")
        assert req.status == ApprovalStatus.APPROVED
        assert liaison.pending_approval_count == 0

    def test_reject(self, liaison):
        req = liaison.create_approval_request("テスト操作")
        liaison.reject(req.id, "admin", reason="リスクが高い")
        assert req.status == ApprovalStatus.REJECTED
        assert liaison.pending_approval_count == 0

    def test_timeout(self, liaison):
        req = liaison.create_approval_request("テスト操作")
        req.created_at = time.time() - 13 * 3600  # 13時間前
        timed_out = liaison.check_timeouts()
        assert len(timed_out) == 1
        assert timed_out[0].status == ApprovalStatus.TIMEOUT

    def test_unknown_request_raises(self, liaison):
        with pytest.raises(KeyError):
            liaison.approve("unknown-id", "user")


# ============================================================
# テスト: 通知
# ============================================================


class TestNotifications:
    def test_send_notification(self, liaison):
        msg = liaison.send_notification(
            NotificationType.CYCLE_COMPLETE,
            "サイクル完了",
            "サイクル1が完了しました",
        )
        assert msg.notification_type == NotificationType.CYCLE_COMPLETE
        assert liaison.notification_count == 1

    def test_format_cycle_complete(self, liaison):
        text = liaison.format_cycle_complete("MS-1", 3, "accept")
        assert "サイクル完了" in text
        assert "#3" in text

    def test_format_stop_alert(self, liaison):
        text = liaison.format_stop_alert("CI連続失敗", "5回連続")
        assert "停止アラート" in text

    def test_get_status(self, liaison):
        status = liaison.get_status()
        assert status["webhook_configured"] is True


# ============================================================
# テスト: スレッドセーフティ
# ============================================================


class TestDiscordLiaisonThreadSafety:
    """DiscordLiaison のスレッドセーフティ検証。"""

    def test_concurrent_send_notification(self):
        """複数スレッドから同時に通知送信しても整合性が保たれる。"""
        import threading
        liaison = DiscordLiaison(webhook_url="https://example.com/wh")
        errors: list[str] = []

        def send(tid: int) -> None:
            try:
                for i in range(25):
                    liaison.send_notification(
                        NotificationType.B_NOTIFY,
                        f"T{tid}-{i}",
                        "body",
                    )
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=send, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert liaison.notification_count == 100


class TestDiscordLiaisonBarrierThreadSafety:
    """DiscordLiaison のBarrier同期スレッドセーフティテスト。"""

    def test_concurrent_send_notification_with_barrier(self) -> None:
        import threading

        liaison = DiscordLiaison(webhook_url="https://example.com/wh")
        n_threads = 10
        ops_per_thread = 25
        barrier = threading.Barrier(n_threads)

        def worker(tid: int) -> None:
            barrier.wait()
            for i in range(ops_per_thread):
                liaison.send_notification(
                    NotificationType.B_NOTIFY,
                    f"T{tid}-{i}",
                    "body",
                )

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert liaison.notification_count == n_threads * ops_per_thread
