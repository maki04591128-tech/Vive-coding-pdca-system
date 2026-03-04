"""ガバナンス・承認ワークフローのテスト。"""

import pytest

from vibe_pdca.engine.governance import (
    GovernanceManager,
)
from vibe_pdca.models.pdca import GovernanceLevel

# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def gov():
    return GovernanceManager()


# ============================================================
# テスト: A/B/C分類
# ============================================================


class TestClassification:
    def test_classify_a_permission(self, gov):
        level = gov.classify("権限拡大のため設定変更")
        assert level == GovernanceLevel.A

    def test_classify_a_security(self, gov):
        level = gov.classify("セキュリティ設定変更")
        assert level == GovernanceLevel.A

    def test_classify_b_diff(self, gov):
        level = gov.classify("diff閾値超えのためバックアップ")
        assert level == GovernanceLevel.B

    def test_classify_b_ci(self, gov):
        level = gov.classify("CI設定変更")
        assert level == GovernanceLevel.B

    def test_classify_c_default(self, gov):
        level = gov.classify("軽微なコード修正")
        assert level == GovernanceLevel.C

    def test_explicit_level(self, gov):
        level = gov.classify("何でも", explicit_level=GovernanceLevel.A)
        assert level == GovernanceLevel.A


# ============================================================
# テスト: 代替案生成（§A4）
# ============================================================


class TestAlternatives:
    def test_generate_alternatives(self, gov):
        alts = gov.generate_alternatives("リスクの高い操作")
        assert len(alts) == 3
        assert all(a.original_operation for a in alts)

    def test_alternatives_have_trade_offs(self, gov):
        alts = gov.generate_alternatives("テスト操作")
        assert all(a.trade_off for a in alts)


# ============================================================
# テスト: 操作処理
# ============================================================


class TestProcessOperation:
    def test_c_operation_auto_approved(self, gov):
        decision = gov.process_operation(
            "op-1", "軽微な修正",
        )
        assert decision.approved
        assert decision.level == GovernanceLevel.C

    def test_b_operation_with_backup(self, gov):
        decision = gov.process_operation(
            "op-2", "diff閾値超えの大規模変更",
        )
        assert decision.backup_created

    def test_rejected_generates_alternatives(self, gov):
        decision = gov.process_operation(
            "op-3", "権限拡大リクエスト", approved=False,
        )
        assert not decision.approved
        assert len(decision.alternatives) == 3

    def test_decision_count(self, gov):
        gov.process_operation("op-1", "テスト1")
        gov.process_operation("op-2", "テスト2")
        assert gov.decision_count == 2

    def test_get_status(self, gov):
        status = gov.get_status()
        assert "a_pattern_count" in status
        assert "b_pattern_count" in status
