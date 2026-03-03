"""RBAC基盤 – ロールベースアクセス制御。

M1 タスク 1-8: 要件定義書 §2, §17, §18.2 準拠。
4ロール（Owner / Maintainer / Reviewer / Auditor）の権限管理。
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RoleName(StrEnum):
    """ユーザーロール名（§2）。"""

    OWNER = "owner"
    MAINTAINER = "maintainer"
    REVIEWER = "reviewer"
    AUDITOR = "auditor"


class Permission(StrEnum):
    """操作権限。"""

    # 目標管理
    GOAL_CREATE = "goal:create"
    GOAL_READ = "goal:read"
    GOAL_UPDATE = "goal:update"

    # PDCA制御
    PDCA_START = "pdca:start"
    PDCA_STOP = "pdca:stop"
    PDCA_RESUME = "pdca:resume"
    PDCA_MODE_SWITCH = "pdca:mode_switch"

    # レビュー
    REVIEW_READ = "review:read"
    REVIEW_COMMENT = "review:comment"
    REVIEW_OVERRIDE = "review:override"

    # 監査ログ
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"

    # 設定
    CONFIG_READ = "config:read"
    CONFIG_UPDATE = "config:update"

    # ガバナンス
    GOVERNANCE_A_APPROVE = "governance:a_approve"
    GOVERNANCE_B_APPROVE = "governance:b_approve"

    # マイルストーン
    MILESTONE_READ = "milestone:read"
    MILESTONE_UPDATE = "milestone:update"
    MILESTONE_REORDER = "milestone:reorder"


class RolePermission(BaseModel):
    """ロールの権限定義。"""

    role: RoleName
    permissions: set[Permission] = Field(default_factory=set)
    description: str = Field(default="")


# ── 権限マトリクス（§2, ロール権限マトリクス.md 準拠） ──

ROLE_PERMISSIONS: dict[RoleName, RolePermission] = {
    RoleName.OWNER: RolePermission(
        role=RoleName.OWNER,
        description="最終到達点の提示 / 重要な意思決定（A操作承認・停止解除など）",
        permissions={
            Permission.GOAL_CREATE,
            Permission.GOAL_READ,
            Permission.GOAL_UPDATE,
            Permission.PDCA_START,
            Permission.PDCA_STOP,
            Permission.PDCA_RESUME,
            Permission.PDCA_MODE_SWITCH,
            Permission.REVIEW_READ,
            Permission.REVIEW_COMMENT,
            Permission.REVIEW_OVERRIDE,
            Permission.AUDIT_READ,
            Permission.AUDIT_EXPORT,
            Permission.CONFIG_READ,
            Permission.CONFIG_UPDATE,
            Permission.GOVERNANCE_A_APPROVE,
            Permission.GOVERNANCE_B_APPROVE,
            Permission.MILESTONE_READ,
            Permission.MILESTONE_UPDATE,
            Permission.MILESTONE_REORDER,
        },
    ),
    RoleName.MAINTAINER: RolePermission(
        role=RoleName.MAINTAINER,
        description="日常運用（停止 / 再開 / モード切替）/ ポリシー変更（制限付き）",
        permissions={
            Permission.GOAL_READ,
            Permission.PDCA_STOP,
            Permission.PDCA_RESUME,
            Permission.PDCA_MODE_SWITCH,
            Permission.REVIEW_READ,
            Permission.REVIEW_COMMENT,
            Permission.AUDIT_READ,
            Permission.CONFIG_READ,
            Permission.GOVERNANCE_B_APPROVE,
            Permission.MILESTONE_READ,
            Permission.MILESTONE_UPDATE,
        },
    ),
    RoleName.REVIEWER: RolePermission(
        role=RoleName.REVIEWER,
        description="レビュー閲覧・コメント",
        permissions={
            Permission.GOAL_READ,
            Permission.REVIEW_READ,
            Permission.REVIEW_COMMENT,
            Permission.AUDIT_READ,
            Permission.CONFIG_READ,
            Permission.MILESTONE_READ,
        },
    ),
    RoleName.AUDITOR: RolePermission(
        role=RoleName.AUDITOR,
        description="監査ログ閲覧・エクスポート",
        permissions={
            Permission.GOAL_READ,
            Permission.REVIEW_READ,
            Permission.AUDIT_READ,
            Permission.AUDIT_EXPORT,
            Permission.CONFIG_READ,
            Permission.MILESTONE_READ,
        },
    ),
}


class PermissionDeniedError(Exception):
    """権限不足エラー。"""

    def __init__(self, role: RoleName, permission: Permission) -> None:
        self.role = role
        self.permission = permission
        super().__init__(
            f"権限不足: ロール '{role.value}' は '{permission.value}' の権限がありません"
        )


class RBACManager:
    """ロールベースアクセス制御マネージャー。"""

    def __init__(
        self,
        role_permissions: dict[RoleName, RolePermission] | None = None,
    ) -> None:
        self._role_permissions = role_permissions or dict(ROLE_PERMISSIONS)

    def has_permission(self, role: RoleName, permission: Permission) -> bool:
        """指定ロールが指定権限を持つか判定する。"""
        role_perm = self._role_permissions.get(role)
        if role_perm is None:
            return False
        return permission in role_perm.permissions

    def check_permission(self, role: RoleName, permission: Permission) -> None:
        """権限チェック。不足時はPermissionDeniedErrorを送出する。"""
        if not self.has_permission(role, permission):
            raise PermissionDeniedError(role, permission)

    def get_role_permissions(self, role: RoleName) -> set[Permission]:
        """指定ロールの全権限を返す。"""
        role_perm = self._role_permissions.get(role)
        if role_perm is None:
            return set()
        return set(role_perm.permissions)

    def get_roles_with_permission(self, permission: Permission) -> list[RoleName]:
        """指定権限を持つ全ロールを返す。"""
        return [
            role
            for role, rp in self._role_permissions.items()
            if permission in rp.permissions
        ]

    def get_all_roles(self) -> list[RolePermission]:
        """全ロールの権限定義を返す。"""
        return list(self._role_permissions.values())

    def get_status(self) -> dict[str, Any]:
        """RBAC設定の概要を返す。"""
        return {
            role.value: {
                "description": rp.description,
                "permission_count": len(rp.permissions),
            }
            for role, rp in self._role_permissions.items()
        }
