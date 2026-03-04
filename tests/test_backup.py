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
