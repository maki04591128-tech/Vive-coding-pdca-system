"""監査ログ基盤 – 追記専用・チェーンハッシュ付き監査ログ。

M1 タスク 1-4: 要件定義書 §16.2 準拠。
- 追記専用（append-only）
- チェーンハッシュによる改ざん検知
- エントリごとのSHA-256ハッシュ
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from vibe_pdca.models.pdca import AuditEntry, GovernanceLevel

logger = logging.getLogger(__name__)

# チェーンの初期ハッシュ（ジェネシス）
GENESIS_HASH = hashlib.sha256(b"vibe-pdca-audit-genesis").hexdigest()


class AuditLogIntegrityError(Exception):
    """監査ログの整合性エラー（即停止トリガー）。"""


class AuditLog:
    """追記専用の監査ログ。

    各エントリはチェーンハッシュで連結される。
    改ざんを検知した場合は AuditLogIntegrityError を送出する。
    """

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._last_hash: str = GENESIS_HASH

    @property
    def entries(self) -> list[AuditEntry]:
        """全エントリ（読み取り専用）。"""
        return list(self._entries)

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def last_hash(self) -> str:
        return self._last_hash

    def append(
        self,
        actor: str,
        action: str,
        resource_type: str = "",
        resource_id: str = "",
        detail: dict[str, Any] | None = None,
        governance_level: GovernanceLevel = GovernanceLevel.C,
    ) -> AuditEntry:
        """新しいエントリを追記する。

        Parameters
        ----------
        actor : str
            操作者（ロール名 or "system"）。
        action : str
            操作内容の説明。
        resource_type : str
            対象リソースの種別。
        resource_id : str
            対象リソースのID。
        detail : dict | None
            追加情報。
        governance_level : GovernanceLevel
            操作の分類（A/B/C）。

        Returns
        -------
        AuditEntry
            追記されたエントリ。
        """
        entry = AuditEntry(
            sequence=len(self._entries),
            timestamp=time.time(),
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail or {},
            governance_level=governance_level,
            previous_hash=self._last_hash,
        )
        entry.entry_hash = entry.compute_hash()
        self._entries.append(entry)
        self._last_hash = entry.entry_hash

        logger.debug(
            "監査ログ追記: seq=%d actor=%s action=%s",
            entry.sequence, actor, action,
        )
        return entry

    def verify_integrity(self) -> bool:
        """全エントリのチェーンハッシュ整合性を検証する。

        Returns
        -------
        bool
            整合性が保たれていればTrue。

        Raises
        ------
        AuditLogIntegrityError
            不整合が見つかった場合。
        """
        expected_prev_hash = GENESIS_HASH

        for entry in self._entries:
            # previous_hash の検証
            if entry.previous_hash != expected_prev_hash:
                raise AuditLogIntegrityError(
                    f"チェーンハッシュ不整合 (seq={entry.sequence}): "
                    f"expected prev={expected_prev_hash[:12]}..., "
                    f"got={entry.previous_hash[:12]}..."
                )

            # entry_hash の再計算検証
            computed = entry.compute_hash()
            if entry.entry_hash != computed:
                raise AuditLogIntegrityError(
                    f"エントリハッシュ不整合 (seq={entry.sequence}): "
                    f"expected={computed[:12]}..., "
                    f"got={entry.entry_hash[:12]}..."
                )

            expected_prev_hash = entry.entry_hash

        return True

    def to_json_lines(self) -> str:
        """全エントリをJSON Lines形式で出力する。"""
        lines = []
        for entry in self._entries:
            lines.append(entry.model_dump_json())
        return "\n".join(lines)

    @classmethod
    def from_json_lines(cls, data: str) -> AuditLog:
        """JSON Lines形式からAuditLogを復元する。

        復元後に整合性を自動検証する。
        """
        log = cls()
        for line in data.strip().split("\n"):
            if not line.strip():
                continue
            entry = AuditEntry.model_validate_json(line)
            log._entries.append(entry)

        if log._entries:
            log._last_hash = log._entries[-1].entry_hash

        # 復元時に必ず整合性検証
        log.verify_integrity()
        return log

    def export(self) -> list[dict[str, Any]]:
        """エクスポート用にエントリをdict形式で返す。"""
        return [entry.model_dump() for entry in self._entries]
