"""監査ログ基盤のユニットテスト。

M1 タスク 1-4: 追記専用 + チェーンハッシュのテスト。
"""

import pytest

from vibe_pdca.audit import (
    GENESIS_HASH,
    AuditLog,
    AuditLogIntegrityError,
)
from vibe_pdca.models.pdca import GovernanceLevel


class TestAuditLogAppend:
    def test_append_single_entry(self):
        log = AuditLog()
        entry = log.append(actor="system", action="test_action")
        assert entry.sequence == 0
        assert entry.actor == "system"
        assert entry.previous_hash == GENESIS_HASH
        assert entry.entry_hash != ""

    def test_append_multiple_entries(self):
        log = AuditLog()
        e1 = log.append(actor="system", action="action_1")
        e2 = log.append(actor="owner", action="action_2")
        e3 = log.append(actor="maintainer", action="action_3")

        assert e1.sequence == 0
        assert e2.sequence == 1
        assert e3.sequence == 2

        # チェーンの検証
        assert e1.previous_hash == GENESIS_HASH
        assert e2.previous_hash == e1.entry_hash
        assert e3.previous_hash == e2.entry_hash

    def test_append_with_detail(self):
        log = AuditLog()
        entry = log.append(
            actor="owner",
            action="goal_create",
            resource_type="goal",
            resource_id="G-001",
            detail={"purpose": "テスト"},
            governance_level=GovernanceLevel.A,
        )
        assert entry.resource_type == "goal"
        assert entry.detail["purpose"] == "テスト"
        assert entry.governance_level == GovernanceLevel.A

    def test_entry_count(self):
        log = AuditLog()
        assert log.entry_count == 0
        log.append(actor="a", action="b")
        log.append(actor="c", action="d")
        assert log.entry_count == 2


class TestAuditLogIntegrity:
    def test_verify_empty_log(self):
        log = AuditLog()
        assert log.verify_integrity() is True

    def test_verify_valid_chain(self):
        log = AuditLog()
        log.append(actor="system", action="start")
        log.append(actor="owner", action="goal_create")
        log.append(actor="system", action="cycle_start")
        assert log.verify_integrity() is True

    def test_detect_tampered_entry_hash(self):
        log = AuditLog()
        log.append(actor="system", action="start")
        log.append(actor="owner", action="goal_create")

        # エントリのハッシュを改ざん
        log._entries[1].entry_hash = "tampered_hash"

        with pytest.raises(AuditLogIntegrityError, match="エントリハッシュ不整合"):
            log.verify_integrity()

    def test_detect_tampered_chain(self):
        log = AuditLog()
        log.append(actor="system", action="start")
        log.append(actor="owner", action="goal_create")

        # チェーンハッシュを改ざん
        log._entries[1].previous_hash = "tampered_prev_hash"

        with pytest.raises(AuditLogIntegrityError, match="チェーンハッシュ不整合"):
            log.verify_integrity()


class TestAuditLogSerialization:
    def test_json_lines_roundtrip(self):
        log = AuditLog()
        log.append(actor="system", action="start")
        log.append(actor="owner", action="goal_create", detail={"goal_id": "G-001"})

        json_lines = log.to_json_lines()
        restored = AuditLog.from_json_lines(json_lines)

        assert restored.entry_count == 2
        assert restored.entries[0].actor == "system"
        assert restored.entries[1].detail["goal_id"] == "G-001"
        assert restored.verify_integrity() is True

    def test_from_json_lines_validates_integrity(self):
        log = AuditLog()
        log.append(actor="system", action="start")

        # 正常なJSON Linesを取得
        json_lines = log.to_json_lines()

        # 改ざんしたデータから復元を試みる
        # entry_hashを書き換え
        import json
        data = json.loads(json_lines)
        data["entry_hash"] = "tampered"
        tampered_json = json.dumps(data)

        with pytest.raises(AuditLogIntegrityError):
            AuditLog.from_json_lines(tampered_json)

    def test_export(self):
        log = AuditLog()
        log.append(actor="system", action="start")
        exported = log.export()
        assert len(exported) == 1
        assert exported[0]["actor"] == "system"
        assert isinstance(exported[0], dict)
