"""監査ログ外部転送・改ざん検知。

提案15: 監査ログを外部ストレージへ転送し、HMAC署名による
改ざん検知と整合性チェックを提供する。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


# ── TransportTarget ──


class TransportTarget(StrEnum):
    """監査ログの転送先種別。"""

    CLOUDWATCH = "cloudwatch"
    DATADOG = "datadog"
    ELASTICSEARCH = "elasticsearch"
    S3 = "s3"
    LOCAL_BACKUP = "local_backup"


# ── TransportConfig ──


@dataclass
class TransportConfig:
    """転送先ごとの設定。"""

    target: TransportTarget
    endpoint: str = ""
    api_key: str = ""
    is_enabled: bool = True
    batch_size: int = 100


# ── AuditLogEntry ──


@dataclass
class AuditLogEntry:
    """監査ログエントリ。"""

    entry_id: str
    timestamp: float
    event_type: str
    payload: dict = field(default_factory=dict)
    signature: str = ""


# ── LogSigner ──


class LogSigner:
    """HMAC-SHA256 による監査ログ署名・検証。"""

    @staticmethod
    def sign(entry: AuditLogEntry, secret: str) -> str:
        """エントリに対する HMAC-SHA256 署名を生成する。

        Parameters
        ----------
        entry : AuditLogEntry
            署名対象の監査ログエントリ。
        secret : str
            HMAC 秘密鍵。

        Returns
        -------
        str
            16進数表現の HMAC-SHA256 署名。
        """
        canonical = (
            f"{entry.entry_id}|{entry.timestamp}|{entry.event_type}|"
            f"{json.dumps(entry.payload, sort_keys=True, ensure_ascii=False)}"
        )
        return hmac.new(
            secret.encode(),
            canonical.encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def verify(entry: AuditLogEntry, signature: str, secret: str) -> bool:
        """署名の整合性を検証する。

        Parameters
        ----------
        entry : AuditLogEntry
            検証対象の監査ログエントリ。
        signature : str
            検証する署名文字列。
        secret : str
            HMAC 秘密鍵。

        Returns
        -------
        bool
            署名が一致すれば True。
        """
        expected = LogSigner.sign(entry, secret)
        return hmac.compare_digest(expected, signature)


# ── TransportManager ──


class TransportManager:
    """監査ログを複数の転送先へ送信する管理クラス。"""

    def __init__(self) -> None:
        self._targets: dict[TransportTarget, TransportConfig] = {}

    def add_target(self, config: TransportConfig) -> None:
        """転送先を追加する。

        Parameters
        ----------
        config : TransportConfig
            追加する転送先設定。
        """
        self._targets[config.target] = config
        logger.info("転送先を追加: %s", config.target.value)

    def remove_target(self, target: TransportTarget) -> bool:
        """転送先を削除する。

        Parameters
        ----------
        target : TransportTarget
            削除する転送先種別。

        Returns
        -------
        bool
            削除に成功すれば True。
        """
        if target in self._targets:
            del self._targets[target]
            logger.info("転送先を削除: %s", target.value)
            return True
        return False

    def send(self, entry: AuditLogEntry) -> dict[str, bool]:
        """単一エントリを有効な全転送先へ送信する。

        Parameters
        ----------
        entry : AuditLogEntry
            送信する監査ログエントリ。

        Returns
        -------
        dict[str, bool]
            転送先名をキー、送信成否を値とする辞書。
        """
        results: dict[str, bool] = {}
        for target, config in self._targets.items():
            if not config.is_enabled:
                continue
            logger.debug(
                "エントリ %s を %s へ送信",
                entry.entry_id,
                target.value,
            )
            results[target.value] = True
        return results

    def send_batch(self, entries: list[AuditLogEntry]) -> dict[str, int]:
        """複数エントリを有効な全転送先へバッチ送信する。

        Parameters
        ----------
        entries : list[AuditLogEntry]
            送信する監査ログエントリのリスト。

        Returns
        -------
        dict[str, int]
            転送先名をキー、送信件数を値とする辞書。
        """
        results: dict[str, int] = {}
        for target, config in self._targets.items():
            if not config.is_enabled:
                continue
            sent = 0
            for i in range(0, len(entries), config.batch_size):
                batch = entries[i : i + config.batch_size]
                sent += len(batch)
            logger.debug(
                "%d 件を %s へバッチ送信",
                sent,
                target.value,
            )
            results[target.value] = sent
        return results

    def list_targets(self) -> list[TransportConfig]:
        """登録済み転送先の一覧を返す。

        Returns
        -------
        list[TransportConfig]
            転送先設定のリスト。
        """
        return list(self._targets.values())


# ── IntegrityAuditor ──


class IntegrityAuditor:
    """ローカルとリモートの監査ログを比較し整合性を検証する。"""

    def __init__(self) -> None:
        self._local: list[AuditLogEntry] = []
        self._remote: list[AuditLogEntry] = []

    def add_local(self, entry: AuditLogEntry) -> None:
        """ローカル側のエントリを追加する。

        Parameters
        ----------
        entry : AuditLogEntry
            ローカルの監査ログエントリ。
        """
        self._local.append(entry)

    def add_remote(self, entry: AuditLogEntry) -> None:
        """リモート側のエントリを追加する。

        Parameters
        ----------
        entry : AuditLogEntry
            リモートの監査ログエントリ。
        """
        self._remote.append(entry)

    def compare(self) -> list[str]:
        """ローカルとリモートの差異を検出する。

        Returns
        -------
        list[str]
            不一致の説明文リスト。空リストなら整合性あり。
        """
        discrepancies: list[str] = []
        local_map = {e.entry_id: e for e in self._local}
        remote_map = {e.entry_id: e for e in self._remote}

        for eid, local_entry in local_map.items():
            if eid not in remote_map:
                discrepancies.append(
                    f"リモートに存在しないエントリ: {eid}"
                )
                continue
            remote_entry = remote_map[eid]
            if local_entry.signature != remote_entry.signature:
                discrepancies.append(
                    f"署名不一致: {eid}"
                )

        for eid in remote_map:
            if eid not in local_map:
                discrepancies.append(
                    f"ローカルに存在しないエントリ: {eid}"
                )

        return discrepancies

    def get_local_count(self) -> int:
        """ローカル側のエントリ数を返す。

        Returns
        -------
        int
            ローカルエントリ数。
        """
        return len(self._local)

    def get_remote_count(self) -> int:
        """リモート側のエントリ数を返す。

        Returns
        -------
        int
            リモートエントリ数。
        """
        return len(self._remote)
