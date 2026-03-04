"""RBAC基盤のユニットテスト。

M1 タスク 1-8: 4ロール権限検証テスト。
"""

import pytest

from vibe_pdca.governance import (
    Permission,
    PermissionDeniedError,
    RBACManager,
    RoleName,
    RolePermission,
)


@pytest.fixture
def rbac():
    return RBACManager()


# ============================================================
# Owner 権限テスト（全権限保持）
# ============================================================


class TestOwnerPermissions:
    def test_owner_has_all_permissions(self, rbac):
        """Ownerは全権限を保持する（§2）。"""
        for perm in Permission:
            assert rbac.has_permission(RoleName.OWNER, perm) is True

    def test_owner_can_create_goal(self, rbac):
        rbac.check_permission(RoleName.OWNER, Permission.GOAL_CREATE)

    def test_owner_can_approve_a_operations(self, rbac):
        rbac.check_permission(RoleName.OWNER, Permission.GOVERNANCE_A_APPROVE)

    def test_owner_can_override_review(self, rbac):
        rbac.check_permission(RoleName.OWNER, Permission.REVIEW_OVERRIDE)


# ============================================================
# Maintainer 権限テスト
# ============================================================


class TestMaintainerPermissions:
    def test_maintainer_can_stop_pdca(self, rbac):
        rbac.check_permission(RoleName.MAINTAINER, Permission.PDCA_STOP)

    def test_maintainer_can_resume_pdca(self, rbac):
        rbac.check_permission(RoleName.MAINTAINER, Permission.PDCA_RESUME)

    def test_maintainer_can_switch_mode(self, rbac):
        rbac.check_permission(RoleName.MAINTAINER, Permission.PDCA_MODE_SWITCH)

    def test_maintainer_cannot_create_goal(self, rbac):
        assert rbac.has_permission(RoleName.MAINTAINER, Permission.GOAL_CREATE) is False

    def test_maintainer_cannot_approve_a_operations(self, rbac):
        assert rbac.has_permission(
            RoleName.MAINTAINER, Permission.GOVERNANCE_A_APPROVE
        ) is False

    def test_maintainer_cannot_override_review(self, rbac):
        assert rbac.has_permission(
            RoleName.MAINTAINER, Permission.REVIEW_OVERRIDE
        ) is False

    def test_maintainer_can_approve_b_operations(self, rbac):
        rbac.check_permission(RoleName.MAINTAINER, Permission.GOVERNANCE_B_APPROVE)


# ============================================================
# Reviewer 権限テスト
# ============================================================


class TestReviewerPermissions:
    def test_reviewer_can_read_reviews(self, rbac):
        rbac.check_permission(RoleName.REVIEWER, Permission.REVIEW_READ)

    def test_reviewer_can_comment(self, rbac):
        rbac.check_permission(RoleName.REVIEWER, Permission.REVIEW_COMMENT)

    def test_reviewer_cannot_stop_pdca(self, rbac):
        assert rbac.has_permission(RoleName.REVIEWER, Permission.PDCA_STOP) is False

    def test_reviewer_cannot_update_config(self, rbac):
        assert rbac.has_permission(RoleName.REVIEWER, Permission.CONFIG_UPDATE) is False


# ============================================================
# Auditor 権限テスト
# ============================================================


class TestAuditorPermissions:
    def test_auditor_can_read_audit(self, rbac):
        rbac.check_permission(RoleName.AUDITOR, Permission.AUDIT_READ)

    def test_auditor_can_export_audit(self, rbac):
        rbac.check_permission(RoleName.AUDITOR, Permission.AUDIT_EXPORT)

    def test_auditor_cannot_stop_pdca(self, rbac):
        assert rbac.has_permission(RoleName.AUDITOR, Permission.PDCA_STOP) is False

    def test_auditor_cannot_approve_governance(self, rbac):
        assert rbac.has_permission(
            RoleName.AUDITOR, Permission.GOVERNANCE_A_APPROVE
        ) is False
        assert rbac.has_permission(
            RoleName.AUDITOR, Permission.GOVERNANCE_B_APPROVE
        ) is False


# ============================================================
# RBACManager メソッドテスト
# ============================================================


class TestRBACManager:
    def test_check_permission_raises_on_denied(self, rbac):
        with pytest.raises(PermissionDeniedError) as exc_info:
            rbac.check_permission(RoleName.REVIEWER, Permission.PDCA_STOP)
        assert exc_info.value.role == RoleName.REVIEWER
        assert exc_info.value.permission == Permission.PDCA_STOP

    def test_get_role_permissions(self, rbac):
        perms = rbac.get_role_permissions(RoleName.AUDITOR)
        assert Permission.AUDIT_READ in perms
        assert Permission.AUDIT_EXPORT in perms
        assert Permission.PDCA_STOP not in perms

    def test_get_roles_with_permission(self, rbac):
        roles = rbac.get_roles_with_permission(Permission.AUDIT_READ)
        assert RoleName.OWNER in roles
        assert RoleName.MAINTAINER in roles
        assert RoleName.REVIEWER in roles
        assert RoleName.AUDITOR in roles

    def test_goal_create_only_owner(self, rbac):
        roles = rbac.get_roles_with_permission(Permission.GOAL_CREATE)
        assert roles == [RoleName.OWNER]

    def test_get_all_roles(self, rbac):
        all_roles = rbac.get_all_roles()
        assert len(all_roles) == 4

    def test_get_status(self, rbac):
        status = rbac.get_status()
        assert "owner" in status
        assert "maintainer" in status
        assert "reviewer" in status
        assert "auditor" in status
        assert status["owner"]["permission_count"] > status["reviewer"]["permission_count"]

    def test_empty_role_map_returns_empty_permissions(self):
        """空の権限マップで初期化した場合、権限チェックが正しく失敗する。"""
        role_perm = RolePermission(role=RoleName.OWNER, permissions=set())
        empty_rbac = RBACManager(role_permissions={RoleName.OWNER: role_perm})
        perms = empty_rbac.get_role_permissions(RoleName.OWNER)
        assert len(perms) == 0
