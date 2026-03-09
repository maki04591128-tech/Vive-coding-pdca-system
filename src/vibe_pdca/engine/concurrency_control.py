"""マルチユーザー同時アクセス制御。

提案9: 楽観的ロック・排他ロック・承認ガードによる
並行アクセス制御と競合検出を提供する。

- 楽観的ロック（バージョン管理ベース）
- 排他ロック（TTL付き）
- 承認ガード（重複承認防止）
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


# ============================================================
# ロック種別
# ============================================================


class LockType(StrEnum):
    """ロックの種別。"""

    OPTIMISTIC = "optimistic"
    EXCLUSIVE = "exclusive"


# ============================================================
# リソースロック
# ============================================================


@dataclass
class ResourceLock:
    """リソースに対するロック情報。"""

    resource_id: str
    lock_type: LockType
    holder: str
    version: int
    acquired_at: float = field(default_factory=time.time)
    expires_at: float | None = None


# ============================================================
# 競合情報
# ============================================================


@dataclass
class ConflictInfo:
    """リソースの競合情報。"""

    resource_id: str
    holder_a: str
    holder_b: str
    description: str


# ============================================================
# 楽観的ロックマネージャ
# ============================================================


class OptimisticLockManager:
    """バージョンベースの楽観的ロックを管理する。

    取得時のバージョンが一致する場合のみロックを取得でき、
    取得後にバージョンをインクリメントする。
    """

    def __init__(self) -> None:
        self._locks: dict[str, ResourceLock] = {}
        self._lock = threading.Lock()

    def acquire(
        self,
        resource_id: str,
        holder: str,
        version: int,
    ) -> ResourceLock | None:
        """楽観的ロックを取得する。

        現在のバージョンが expected version と一致する場合のみ成功し、
        バージョンをインクリメントして新しいロックを返す。
        リソースが未登録の場合は version=0 で初回取得として扱う。
        """
        with self._lock:
            existing = self._locks.get(resource_id)
            if existing is not None:
                if existing.version != version:
                    logger.warning(
                        "楽観的ロック失敗: resource=%s "
                        "expected_version=%d actual=%d",
                        resource_id, version, existing.version,
                    )
                    return None
            elif version != 0:
                logger.warning(
                    "楽観的ロック失敗: resource=%s は未登録 "
                    "(expected version=%d)",
                    resource_id, version,
                )
                return None

            new_lock = ResourceLock(
                resource_id=resource_id,
                lock_type=LockType.OPTIMISTIC,
                holder=holder,
                version=version + 1,
                acquired_at=time.time(),
            )
            self._locks[resource_id] = new_lock
        logger.info(
            "楽観的ロック取得: resource=%s holder=%s v=%d",
            resource_id, holder, new_lock.version,
        )
        return new_lock

    def release(self, resource_id: str, holder: str) -> bool:
        """ロックを解放する。保持者が一致する場合のみ成功。"""
        with self._lock:
            lock = self._locks.get(resource_id)
            if lock is None or lock.holder != holder:
                return False
            del self._locks[resource_id]
        logger.info(
            "楽観的ロック解放: resource=%s holder=%s",
            resource_id, holder,
        )
        return True

    def check_version(
        self, resource_id: str, expected_version: int,
    ) -> bool:
        """リソースの現在バージョンが期待値と一致するか確認する。"""
        with self._lock:
            lock = self._locks.get(resource_id)
            if lock is None:
                return expected_version == 0
            return lock.version == expected_version

    def get_lock(self, resource_id: str) -> ResourceLock | None:
        """リソースの現在のロック情報を取得する。"""
        with self._lock:
            return self._locks.get(resource_id)

    def list_locks(self) -> list[ResourceLock]:
        """全ロックのリストを返す。"""
        with self._lock:
            return sorted(
                self._locks.values(), key=lambda lk: lk.resource_id,
            )


# ============================================================
# 排他ロックマネージャ
# ============================================================


class ExclusiveLockManager:
    """TTL付き排他ロックを管理する。

    同一リソースに対して1人のみがロックを保持できる。
    TTL 経過後は自動的に期限切れとなる。
    """

    def __init__(self) -> None:
        self._locks: dict[str, ResourceLock] = {}
        self._lock = threading.Lock()

    def acquire(
        self,
        resource_id: str,
        holder: str,
        ttl_seconds: float = 300,
    ) -> ResourceLock | None:
        """排他ロックを取得する。

        既にロックされている場合（期限切れでなければ）は None を返す。
        """
        with self._lock:
            existing = self._locks.get(resource_id)
            if (
                existing is not None
                and existing.expires_at is not None
                and existing.expires_at > time.time()
            ):
                logger.warning(
                    "排他ロック失敗: resource=%s は %s が保持中",
                    resource_id, existing.holder,
                )
                return None

            now = time.time()
            lock = ResourceLock(
                resource_id=resource_id,
                lock_type=LockType.EXCLUSIVE,
                holder=holder,
                version=0,
                acquired_at=now,
                expires_at=now + ttl_seconds,
            )
            self._locks[resource_id] = lock
        logger.info(
            "排他ロック取得: resource=%s holder=%s ttl=%ds",
            resource_id, holder, int(ttl_seconds),
        )
        return lock

    def release(self, resource_id: str, holder: str) -> bool:
        """排他ロックを解放する。保持者が一致する場合のみ成功。"""
        with self._lock:
            lock = self._locks.get(resource_id)
            if lock is None or lock.holder != holder:
                return False
            del self._locks[resource_id]
        logger.info(
            "排他ロック解放: resource=%s holder=%s",
            resource_id, holder,
        )
        return True

    def is_locked(self, resource_id: str) -> bool:
        """リソースがロックされているか（期限内）確認する。"""
        with self._lock:
            lock = self._locks.get(resource_id)
            if lock is None:
                return False
            return (
                lock.expires_at is None or lock.expires_at > time.time()
            )

    def cleanup_expired(self) -> int:
        """期限切れのロックを除去し、除去数を返す。"""
        with self._lock:
            now = time.time()
            expired = [
                rid for rid, lk in self._locks.items()
                if lk.expires_at is not None and lk.expires_at <= now
            ]
            for rid in expired:
                del self._locks[rid]
        if expired:
            logger.info("期限切れロック除去: %d件", len(expired))
        return len(expired)


# ============================================================
# 承認ガード
# ============================================================


class ApprovalGuard:
    """リソースの承認状態を管理し、重複承認を防止する。"""

    def __init__(self) -> None:
        self._approvals: dict[str, str] = {}

    def submit_approval(
        self, resource_id: str, approver: str,
    ) -> bool:
        """承認を登録する。既に承認済みの場合は False。"""
        if resource_id in self._approvals:
            logger.warning(
                "承認重複: resource=%s は既に %s が承認済み",
                resource_id, self._approvals[resource_id],
            )
            return False
        self._approvals[resource_id] = approver
        logger.info(
            "承認登録: resource=%s approver=%s",
            resource_id, approver,
        )
        return True

    def is_approved(self, resource_id: str) -> bool:
        """リソースが承認済みかどうかを返す。"""
        return resource_id in self._approvals

    def get_approver(self, resource_id: str) -> str | None:
        """承認者を返す。未承認の場合は None。"""
        return self._approvals.get(resource_id)

    def reset(self, resource_id: str) -> None:
        """リソースの承認状態をリセットする。"""
        self._approvals.pop(resource_id, None)
        logger.info("承認リセット: resource=%s", resource_id)
