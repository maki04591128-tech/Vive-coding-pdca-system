"""Suppress List – 既知誤検知登録・有効期限・A操作承認。

M3 タスク 3-9: 要件定義書 §26.10 準拠。

- Suppress Listに登録し、以降のサイクルでACTの採否判断から除外
- 登録はA操作扱い
- 有効期限付き
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SUPPRESS_DAYS = 90
# ※ 抑制エントリのデフォルト有効期間は90日。期限が切れると自動で無効になる


# 「この問題はわかっているが今は直さない」という登録1件分のデータ
@dataclass
class SuppressEntry:
    """Suppress List のエントリ。"""

    id: str = field(default_factory=lambda: f"sup-{uuid.uuid4().hex[:8]}")
    pattern: str = ""
    reason: str = ""
    registered_by: str = ""
    approved: bool = False
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    @property
    def is_expired(self) -> bool:
        return self.expires_at > 0 and time.time() > self.expires_at


# --- Suppress List 管理: AIが検出した「わかっている問題」を抑制するリスト ---
class SuppressList:
    """既知誤検知の Suppress List 管理。"""

    def __init__(
        self,
        default_days: int = DEFAULT_SUPPRESS_DAYS,
    ) -> None:
        self._entries: list[SuppressEntry] = []
        self._default_days = default_days
        self._lock = threading.Lock()

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._entries)

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(
                1 for e in self._entries if not e.is_expired and e.approved
            )

    def register(
        self,
        pattern: str,
        reason: str,
        registered_by: str,
        approved: bool = False,
        expires_days: int | None = None,
    ) -> SuppressEntry:
        """誤検知パターンを登録する（A操作）。

        Parameters
        ----------
        pattern : str
            抑制するパターン（指摘IDまたは説明の一部）。
        reason : str
            登録理由。
        registered_by : str
            登録者。
        approved : bool
            A操作承認済みかどうか。
        expires_days : int | None
            有効期限（日数）。

        Returns
        -------
        SuppressEntry
            登録されたエントリ。
        """
        # 有効期限を計算し、新しい抑制エントリを作成してリストに追加する
        days = expires_days or self._default_days
        now = time.time()
        entry = SuppressEntry(
            pattern=pattern,
            reason=reason,
            registered_by=registered_by,
            approved=approved,
            created_at=now,
            expires_at=now + (days * 86400),
        )
        with self._lock:
            self._entries.append(entry)

        logger.info(
            "Suppress登録: %s (パターン: %s, 承認: %s, 期限: %d日)",
            entry.id, pattern, approved, days,
        )
        return entry

    def is_suppressed(self, finding_text: str) -> bool:
        """指摘が抑制対象かどうか判定する。

        Parameters
        ----------
        finding_text : str
            指摘の説明テキスト。

        Returns
        -------
        bool
            抑制対象の場合True。
        """
        # 有効（承認済み＋期限内）な全エントリとパターンマッチで照合
        with self._lock:
            for entry in self._entries:
                if not entry.approved or entry.is_expired:
                    continue
                if entry.pattern.lower() in finding_text.lower():
                    return True
        return False

    def approve(self, entry_id: str) -> bool:
        """エントリを承認する（A操作完了）。

        Returns
        -------
        bool
            承認に成功した場合True。
        """
        with self._lock:
            for entry in self._entries:
                if entry.id == entry_id:
                    entry.approved = True
                    logger.info("Suppress承認: %s", entry_id)
                    return True
        return False

    def remove(self, entry_id: str) -> bool:
        """エントリを削除する。"""
        with self._lock:
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.id != entry_id]
            return len(self._entries) < before

    # 期限切れエントリを一括削除して、リストを最新状態に保つ
    def purge_expired(self) -> int:
        """期限切れエントリを削除する。"""
        with self._lock:
            before = len(self._entries)
            self._entries = [e for e in self._entries if not e.is_expired]
            purged = before - len(self._entries)
        if purged > 0:
            logger.info("Suppress期限切れ削除: %d件", purged)
        return purged

    def list_active(self) -> list[SuppressEntry]:
        """有効なエントリを返す。"""
        with self._lock:
            return [
                e for e in self._entries if not e.is_expired and e.approved
            ]

    def get_status(self) -> dict[str, Any]:
        """Suppress List 状態を返す。"""
        return {
            "total_entries": self.entry_count,
            "active_entries": self.active_count,
            "default_expire_days": self._default_days,
        }
