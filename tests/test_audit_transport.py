"""監査ログ外部転送・改ざん検知のテスト。"""

import pytest

from vibe_pdca.engine.audit_transport import (
    AuditLogEntry,
    IntegrityAuditor,
    LogSigner,
    TransportConfig,
    TransportManager,
    TransportTarget,
)

# ============================================================
# テスト: TransportTarget
# ============================================================


class TestTransportTarget:
    def test_enum_values(self):
        assert TransportTarget.CLOUDWATCH == "cloudwatch"
        assert TransportTarget.DATADOG == "datadog"
        assert TransportTarget.ELASTICSEARCH == "elasticsearch"
        assert TransportTarget.S3 == "s3"
        assert TransportTarget.LOCAL_BACKUP == "local_backup"


# ============================================================
# テスト: TransportConfig
# ============================================================


class TestTransportConfig:
    def test_defaults(self):
        config = TransportConfig(target=TransportTarget.S3)
        assert config.target == TransportTarget.S3
        assert config.endpoint == ""
        assert config.api_key == ""
        assert config.is_enabled is True
        assert config.batch_size == 100

    def test_custom(self):
        config = TransportConfig(
            target=TransportTarget.DATADOG,
            endpoint="https://api.datadog.com",
            api_key="secret-key",
            is_enabled=False,
            batch_size=50,
        )
        assert config.target == TransportTarget.DATADOG
        assert config.endpoint == "https://api.datadog.com"
        assert config.api_key == "secret-key"
        assert config.is_enabled is False
        assert config.batch_size == 50


# ============================================================
# テスト: AuditLogEntry
# ============================================================


class TestAuditLogEntry:
    def test_creation(self):
        entry = AuditLogEntry(
            entry_id="entry-001",
            timestamp=1700000000.0,
            event_type="cycle_start",
            payload={"cycle": 1},
            signature="abc123",
        )
        assert entry.entry_id == "entry-001"
        assert entry.timestamp == 1700000000.0
        assert entry.event_type == "cycle_start"
        assert entry.payload == {"cycle": 1}
        assert entry.signature == "abc123"

    def test_defaults(self):
        entry = AuditLogEntry(
            entry_id="entry-002",
            timestamp=1700000001.0,
            event_type="cycle_end",
        )
        assert entry.payload == {}
        assert entry.signature == ""


# ============================================================
# テスト: LogSigner
# ============================================================


class TestLogSigner:
    @pytest.fixture()
    def entry(self) -> AuditLogEntry:
        return AuditLogEntry(
            entry_id="e1",
            timestamp=1700000000.0,
            event_type="test_event",
            payload={"key": "value"},
        )

    def test_sign_produces_string(self, entry: AuditLogEntry):
        sig = LogSigner.sign(entry, "my-secret")
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA-256 hex digest length

    def test_sign_deterministic(self, entry: AuditLogEntry):
        sig1 = LogSigner.sign(entry, "my-secret")
        sig2 = LogSigner.sign(entry, "my-secret")
        assert sig1 == sig2

    def test_verify_valid(self, entry: AuditLogEntry):
        secret = "my-secret"
        sig = LogSigner.sign(entry, secret)
        assert LogSigner.verify(entry, sig, secret) is True

    def test_verify_invalid(self, entry: AuditLogEntry):
        assert LogSigner.verify(entry, "invalid-sig", "my-secret") is False

    def test_verify_wrong_secret(self, entry: AuditLogEntry):
        sig = LogSigner.sign(entry, "correct-secret")
        assert LogSigner.verify(entry, sig, "wrong-secret") is False


# ============================================================
# テスト: TransportManager
# ============================================================


class TestTransportManager:
    @pytest.fixture()
    def manager(self) -> TransportManager:
        return TransportManager()

    @pytest.fixture()
    def s3_config(self) -> TransportConfig:
        return TransportConfig(
            target=TransportTarget.S3,
            endpoint="s3://my-bucket",
        )

    @pytest.fixture()
    def dd_config(self) -> TransportConfig:
        return TransportConfig(
            target=TransportTarget.DATADOG,
            endpoint="https://api.datadog.com",
        )

    def test_add_and_list(
        self,
        manager: TransportManager,
        s3_config: TransportConfig,
        dd_config: TransportConfig,
    ):
        manager.add_target(s3_config)
        manager.add_target(dd_config)
        targets = manager.list_targets()
        assert len(targets) == 2
        assert s3_config in targets
        assert dd_config in targets

    def test_remove(
        self,
        manager: TransportManager,
        s3_config: TransportConfig,
    ):
        manager.add_target(s3_config)
        assert manager.remove_target(TransportTarget.S3) is True
        assert manager.list_targets() == []

    def test_send(
        self,
        manager: TransportManager,
        s3_config: TransportConfig,
    ):
        manager.add_target(s3_config)
        entry = AuditLogEntry(
            entry_id="e1",
            timestamp=1700000000.0,
            event_type="test",
        )
        results = manager.send(entry)
        assert results == {"s3": True}

    def test_send_batch(
        self,
        manager: TransportManager,
        s3_config: TransportConfig,
    ):
        manager.add_target(s3_config)
        entries = [
            AuditLogEntry(
                entry_id=f"e{i}",
                timestamp=1700000000.0 + i,
                event_type="test",
            )
            for i in range(3)
        ]
        results = manager.send_batch(entries)
        assert results == {"s3": 3}

    def test_remove_missing(self, manager: TransportManager):
        assert manager.remove_target(TransportTarget.S3) is False


# ============================================================
# テスト: IntegrityAuditor
# ============================================================


class TestIntegrityAuditor:
    @pytest.fixture()
    def auditor(self) -> IntegrityAuditor:
        return IntegrityAuditor()

    def test_add_and_count(self, auditor: IntegrityAuditor):
        entry = AuditLogEntry(
            entry_id="e1",
            timestamp=1700000000.0,
            event_type="test",
            signature="sig1",
        )
        auditor.add_local(entry)
        auditor.add_remote(entry)
        assert auditor.get_local_count() == 1
        assert auditor.get_remote_count() == 1

    def test_compare_matching(self, auditor: IntegrityAuditor):
        entry = AuditLogEntry(
            entry_id="e1",
            timestamp=1700000000.0,
            event_type="test",
            signature="sig1",
        )
        auditor.add_local(entry)
        auditor.add_remote(entry)
        assert auditor.compare() == []

    def test_compare_missing_remote(self, auditor: IntegrityAuditor):
        entry = AuditLogEntry(
            entry_id="e1",
            timestamp=1700000000.0,
            event_type="test",
            signature="sig1",
        )
        auditor.add_local(entry)
        discrepancies = auditor.compare()
        assert len(discrepancies) == 1
        assert "リモートに存在しないエントリ" in discrepancies[0]

    def test_compare_missing_local(self, auditor: IntegrityAuditor):
        entry = AuditLogEntry(
            entry_id="e1",
            timestamp=1700000000.0,
            event_type="test",
            signature="sig1",
        )
        auditor.add_remote(entry)
        discrepancies = auditor.compare()
        assert len(discrepancies) == 1
        assert "ローカルに存在しないエントリ" in discrepancies[0]


# ── スレッドセーフティ ──


class TestTransportManagerThreadSafety:
    """TransportManager の並行アクセスでデータが壊れない。"""

    def test_concurrent_add_target(self):
        import threading
        mgr = TransportManager()
        errors: list[str] = []

        def add_targets(tid: int):
            try:
                for i in range(20):
                    cfg = TransportConfig(
                        target=TransportTarget.CLOUDWATCH if (tid + i) % 2 == 0
                        else TransportTarget.DATADOG,
                        endpoint=f"ep-{tid}-{i}",
                    )
                    mgr.add_target(cfg)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=add_targets, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # 2種類のターゲットしかないので最大2
        assert len(mgr.list_targets()) <= 2


class TestIntegrityAuditorThreadSafety:
    """IntegrityAuditor の並行アクセスでデータが壊れない。"""

    def test_concurrent_add_entries(self):
        import threading
        auditor = IntegrityAuditor()
        errors: list[str] = []

        def add_entries(tid: int):
            try:
                for i in range(50):
                    entry = AuditLogEntry(
                        entry_id=f"e-{tid}-{i}",
                        timestamp=1700000000.0,
                        event_type="test",
                    )
                    auditor.add_local(entry)
                    auditor.add_remote(entry)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=add_entries, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert auditor.get_local_count() == 200
        assert auditor.get_remote_count() == 200
