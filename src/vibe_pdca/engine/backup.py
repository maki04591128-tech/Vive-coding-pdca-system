"""バックアップ管理 – B操作前バックアップ・整合性検証・半年保持。

M3 タスク 3-5: 要件定義書 §20 準拠。

- B操作の実行直前の状態をバックアップ
- 復元可能性・追跡可能性・改ざん検知可能性
- 保持期間は半年（180日）
"""

from __future__ import annotations

import copy
import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

BACKUP_RETENTION_DAYS = 180
# ※ B操作（バックアップ必須操作）の実行前に自動保存される


# バックアップ1件分のデータ（操作ID・状態スナップショット・チェックサム）
@dataclass
class BackupEntry:
    """バックアップエントリ。"""

    id: str = field(default_factory=lambda: f"bk-{uuid.uuid4().hex[:8]}")
    operation_id: str = ""
    operation_description: str = ""
    state_snapshot: dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    created_at: float = field(default_factory=time.time)
    restored: bool = False

    def compute_checksum(self) -> str:
        """状態のチェックサムを計算する。"""
        payload = str(sorted(self.state_snapshot.items()))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class BackupIntegrityError(Exception):
    """バックアップ整合性エラー。"""


# --- バックアップ管理: B操作前の状態保存、整合性検証（改ざん検知）、復元 ---
class BackupManager:
    """B操作前バックアップ管理。"""

    def __init__(
        self,
        retention_days: int = BACKUP_RETENTION_DAYS,
    ) -> None:
        self._backups: list[BackupEntry] = []
        self._retention_days = retention_days

    @property
    def backup_count(self) -> int:
        return len(self._backups)

    def create_backup(
        self,
        operation_id: str,
        operation_description: str,
        state_snapshot: dict[str, Any],
    ) -> BackupEntry:
        """バックアップを作成する。

        Parameters
        ----------
        operation_id : str
            操作ID。
        operation_description : str
            操作の説明。
        state_snapshot : dict
            バックアップ対象の状態。

        Returns
        -------
        BackupEntry
            作成されたバックアップ。
        """
        entry = BackupEntry(
            operation_id=operation_id,
            operation_description=operation_description,
            state_snapshot=copy.deepcopy(state_snapshot),
        )
        entry.checksum = entry.compute_checksum()
        self._backups.append(entry)

        logger.info(
            "バックアップ作成: %s (操作: %s)",
            entry.id, operation_description,
        )
        return entry

    def verify_integrity(self, backup_id: str) -> bool:
        """バックアップの整合性を検証する。

        Raises
        ------
        BackupIntegrityError
            整合性エラー。
        """
        entry = self._find(backup_id)
        # チェックサムを再計算し、保存時の値と一致するか確認（改ざん検知）
        computed = entry.compute_checksum()
        if computed != entry.checksum:
            raise BackupIntegrityError(
                f"バックアップ改ざん検知: {backup_id} "
                f"(expected={entry.checksum[:12]}..., got={computed[:12]}...)"
            )
        return True

    def restore(self, backup_id: str) -> dict[str, Any]:
        """バックアップから状態を復元する。

        Parameters
        ----------
        backup_id : str
            バックアップID。

        Returns
        -------
        dict
            復元された状態。
        """
        entry = self._find(backup_id)
        self.verify_integrity(backup_id)
        entry.restored = True
        logger.info("バックアップ復元: %s", backup_id)
        return copy.deepcopy(entry.state_snapshot)

    def purge_expired(self, now: float | None = None) -> int:
        """期限切れバックアップを削除する。

        Returns
        -------
        int
            削除件数。
        """
        current = now if now is not None else time.time()
        # 保持期限（180日）を超えたバックアップを自動削除
        cutoff = current - (self._retention_days * 86400)
        before = len(self._backups)
        self._backups = [b for b in self._backups if b.created_at >= cutoff]
        purged = before - len(self._backups)
        if purged > 0:
            logger.info("期限切れバックアップ削除: %d件", purged)
        return purged

    def list_backups(self) -> list[BackupEntry]:
        """全バックアップを返す。"""
        return list(self._backups)

    def get_status(self) -> dict[str, Any]:
        """バックアップ管理状態を返す。"""
        return {
            "backup_count": self.backup_count,
            "retention_days": self._retention_days,
        }

    def _find(self, backup_id: str) -> BackupEntry:
        """バックアップを検索する。"""
        for entry in self._backups:
            if entry.id == backup_id:
                return entry
        raise KeyError(f"バックアップが見つかりません: {backup_id}")
