"""バックアップ管理のテスト。"""

import time

import pytest

from vibe_pdca.engine.backup import (
    BackupIntegrityError,
    BackupManager,
)


class TestBackupCreation:
    def test_create_backup(self):
        mgr = BackupManager()
        entry = mgr.create_backup(
            "op-1", "テスト操作", {"key": "value"},
        )
        assert entry.checksum
        assert mgr.backup_count == 1

    def test_restore(self):
        mgr = BackupManager()
        entry = mgr.create_backup(
            "op-1", "テスト操作", {"key": "value"},
        )
        state = mgr.restore(entry.id)
        assert state["key"] == "value"
        assert entry.restored

    def test_restore_returns_deep_copy(self):
        """restore()がdeep copyを返し、変更が元のバックアップに影響しないこと。"""
        mgr = BackupManager()
        nested = {"outer": {"inner": 1}}
        entry = mgr.create_backup("op-2", "ネスト操作", nested)
        restored = mgr.restore(entry.id)
        # 復元データを変更してもバックアップは不変
        restored["outer"]["inner"] = 999
        assert entry.state_snapshot["outer"]["inner"] == 1


class TestBackupIntegrity:
    def test_verify_integrity(self):
        mgr = BackupManager()
        entry = mgr.create_backup(
            "op-1", "テスト操作", {"key": "value"},
        )
        assert mgr.verify_integrity(entry.id)

    def test_tampered_backup(self):
        mgr = BackupManager()
        entry = mgr.create_backup(
            "op-1", "テスト操作", {"key": "value"},
        )
        entry.state_snapshot["key"] = "tampered"
        with pytest.raises(BackupIntegrityError):
            mgr.verify_integrity(entry.id)


class TestBackupExpiry:
    def test_purge_expired(self):
        mgr = BackupManager(retention_days=180)
        entry = mgr.create_backup(
            "op-1", "テスト操作", {"key": "value"},
        )
        entry.created_at = time.time() - 200 * 86400
        purged = mgr.purge_expired()
        assert purged == 1
        assert mgr.backup_count == 0

    def test_keep_valid(self):
        mgr = BackupManager()
        mgr.create_backup("op-1", "テスト操作", {"key": "value"})
        purged = mgr.purge_expired()
        assert purged == 0
        assert mgr.backup_count == 1

    def test_not_found(self):
        mgr = BackupManager()
        with pytest.raises(KeyError):
            mgr.verify_integrity("unknown")

    def test_get_status(self):
        mgr = BackupManager()
        status = mgr.get_status()
        assert status["retention_days"] == 180


# ── スレッドセーフティ ──


class TestBackupManagerThreadSafety:
    """BackupManager の並行アクセスでデータが壊れない。"""

    def test_concurrent_create_backup(self):
        import threading
        mgr = BackupManager()
        errors: list[str] = []

        def create_backups(tid: int):
            try:
                for i in range(25):
                    mgr.create_backup(
                        operation_id=f"op-{tid}-{i}",
                        operation_description=f"desc-{tid}-{i}",
                        state_snapshot={"key": f"value-{tid}-{i}"},
                    )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=create_backups, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert mgr.backup_count == 100


class TestBackupManagerBarrierThreadSafety:
    """BackupManager のBarrier同期スレッドセーフティテスト。"""

    def test_concurrent_create_backup_with_barrier(self) -> None:
        import threading

        mgr = BackupManager()
        n_threads = 10
        ops_per_thread = 20
        barrier = threading.Barrier(n_threads)

        def worker(tid: int) -> None:
            barrier.wait()
            for i in range(ops_per_thread):
                mgr.create_backup(
                    operation_id=f"op-{tid}-{i}",
                    operation_description=f"desc-{tid}-{i}",
                    state_snapshot={"key": f"value-{tid}-{i}"},
                )

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert mgr.backup_count == n_threads * ops_per_thread
