"""運転モード制御（ModeController）のテスト。"""

import pytest

from vibe_pdca.engine.mode_controller import ModeController, OperationMode
from vibe_pdca.models.pdca import GovernanceLevel, PDCAPhase

# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def manual_ctrl():
    return ModeController(initial_mode=OperationMode.MANUAL)


@pytest.fixture
def semi_auto_ctrl():
    return ModeController(initial_mode=OperationMode.SEMI_AUTO)


@pytest.fixture
def full_auto_ctrl():
    return ModeController(initial_mode=OperationMode.FULL_AUTO)


# ============================================================
# テスト: モード基本操作
# ============================================================


class TestModeBasics:
    def test_initial_mode(self, manual_ctrl):
        assert manual_ctrl.mode == OperationMode.MANUAL

    def test_set_mode(self, manual_ctrl):
        manual_ctrl.set_mode(OperationMode.SEMI_AUTO, reason="テスト切替")
        assert manual_ctrl.mode == OperationMode.SEMI_AUTO

    def test_mode_history(self, manual_ctrl):
        manual_ctrl.set_mode(OperationMode.SEMI_AUTO, reason="1回目")
        manual_ctrl.set_mode(OperationMode.FULL_AUTO, reason="2回目")
        history = manual_ctrl.mode_history
        assert len(history) == 2
        assert history[0]["from"] == "manual"
        assert history[0]["to"] == "semi_auto"
        assert history[1]["to"] == "full_auto"

    def test_get_status(self, manual_ctrl):
        status = manual_ctrl.get_status()
        assert status["mode"] == "manual"
        assert "auto_advance" in status
        assert "approval_required" in status


# ============================================================
# テスト: 手動モードの自動進行
# ============================================================


class TestManualMode:
    def test_no_auto_advance_any_phase(self, manual_ctrl):
        for phase in PDCAPhase:
            assert not manual_ctrl.can_auto_advance(phase)

    def test_all_require_approval(self, manual_ctrl):
        for level in GovernanceLevel:
            assert manual_ctrl.requires_approval(level)


# ============================================================
# テスト: 半自動モードの自動進行
# ============================================================


class TestSemiAutoMode:
    def test_auto_advance_plan_do_check(self, semi_auto_ctrl):
        assert semi_auto_ctrl.can_auto_advance(PDCAPhase.PLAN)
        assert semi_auto_ctrl.can_auto_advance(PDCAPhase.DO)
        assert semi_auto_ctrl.can_auto_advance(PDCAPhase.CHECK)

    def test_act_requires_approval(self, semi_auto_ctrl):
        assert not semi_auto_ctrl.can_auto_advance(PDCAPhase.ACT)

    def test_governance_a_requires_approval(self, semi_auto_ctrl):
        assert semi_auto_ctrl.requires_approval(GovernanceLevel.A)

    def test_governance_b_c_auto(self, semi_auto_ctrl):
        assert not semi_auto_ctrl.requires_approval(GovernanceLevel.B)
        assert not semi_auto_ctrl.requires_approval(GovernanceLevel.C)


# ============================================================
# テスト: 全自動モードの自動進行
# ============================================================


class TestFullAutoMode:
    def test_all_phases_auto_advance(self, full_auto_ctrl):
        for phase in PDCAPhase:
            assert full_auto_ctrl.can_auto_advance(phase)

    def test_governance_a_still_requires_approval(self, full_auto_ctrl):
        """全自動モードでもA操作は人間承認必須（§17）。"""
        assert full_auto_ctrl.requires_approval(GovernanceLevel.A)

    def test_governance_b_c_auto(self, full_auto_ctrl):
        assert not full_auto_ctrl.requires_approval(GovernanceLevel.B)
        assert not full_auto_ctrl.requires_approval(GovernanceLevel.C)
