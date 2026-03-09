"""監査ログ保持期間管理 – 自動削除・保持ポリシー。

M3 タスク 3-1: 要件定義書 §16.4 準拠。

| 対象           | 保持期間 | 変更条件                 |
|---------------|---------|------------------------|
| 監査ログ       | 365日   | 短縮は人間承認            |
| 運用メトリクス  | 90日    | プロジェクト単位で変更可   |
| レビュー原本    | 180日   | プロジェクト単位で変更可   |
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class RetentionTarget(StrEnum):
    """保持対象の種別。"""

    AUDIT_LOG = "audit_log"
    OPERATION_METRICS = "operation_metrics"
    REVIEW_ORIGINAL = "review_original"


# §16.4 確定値
DEFAULT_RETENTION_DAYS: dict[RetentionTarget, int] = {
    RetentionTarget.AUDIT_LOG: 365,
    RetentionTarget.OPERATION_METRICS: 90,
    RetentionTarget.REVIEW_ORIGINAL: 180,
}


@dataclass
class RetentionPolicy:
    """保持ポリシー1件。"""

    target: RetentionTarget
    retention_days: int
    requires_approval_to_shorten: bool = False
    description: str = ""


@dataclass
class PurgeResult:
    """自動削除結果。"""

    target: RetentionTarget
    purged_count: int = 0
    remaining_count: int = 0
    cutoff_timestamp: float = 0.0


# --- 監査ログ保持: ログの保持期間・圧縮・自動削除ポリシーを管理 ---
# 監査ログは「誰が・いつ・何をしたか」の改ざん不能な記録
class RetentionManager:
    """保持期間管理。

    対象ごとの保持期間ポリシーに基づいて期限切れデータを特定し、
    自動削除を行う。
    """

    def __init__(
        self,
        custom_days: dict[RetentionTarget, int] | None = None,
    ) -> None:
        self._policies: dict[RetentionTarget, RetentionPolicy] = {}

        for target, days in DEFAULT_RETENTION_DAYS.items():
            actual_days = (custom_days or {}).get(target, days)
            self._policies[target] = RetentionPolicy(
                target=target,
                retention_days=actual_days,
                requires_approval_to_shorten=(
                    target == RetentionTarget.AUDIT_LOG
                ),
                description=f"{target.value}: {actual_days}日保持",
            )

    @property
    def policies(self) -> dict[RetentionTarget, RetentionPolicy]:
        return dict(self._policies)

    def get_cutoff_timestamp(
        self,
        target: RetentionTarget,
        now: float | None = None,
    ) -> float:
        """保持期限のカットオフタイムスタンプを返す。"""
        current = now if now is not None else time.time()
        policy = self._policies.get(target)
        if policy is None:
            raise KeyError(f"不明な保持対象: {target}")
        return current - (policy.retention_days * 86400)

    def identify_expired(
        self,
        target: RetentionTarget,
        items: list[dict[str, Any]],
        timestamp_key: str = "timestamp",
        now: float | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """期限切れと有効なアイテムを分離する。

        Parameters
        ----------
        target : RetentionTarget
            保持対象種別。
        items : list[dict]
            チェック対象アイテム（timestamp_keyフィールドを含む）。
        timestamp_key : str
            タイムスタンプフィールド名。
        now : float | None
            現在時刻（テスト用）。

        Returns
        -------
        tuple[list[dict], list[dict]]
            (期限切れリスト, 有効リスト)
        """
        cutoff = self.get_cutoff_timestamp(target, now=now)
        expired: list[dict[str, Any]] = []
        valid: list[dict[str, Any]] = []

        for item in items:
            ts = item.get(timestamp_key, 0.0)
            if ts < cutoff:
                expired.append(item)
            else:
                valid.append(item)

        return expired, valid

    def purge(
        self,
        target: RetentionTarget,
        items: list[dict[str, Any]],
        timestamp_key: str = "timestamp",
        now: float | None = None,
    ) -> PurgeResult:
        """期限切れアイテムを削除（パージ）する。

        Parameters
        ----------
        target : RetentionTarget
            保持対象種別。
        items : list[dict]
            チェック対象アイテム（in-placeで削除される）。
        timestamp_key : str
            タイムスタンプフィールド名。
        now : float | None
            現在時刻（テスト用）。

        Returns
        -------
        PurgeResult
            削除結果。
        """
        cutoff = self.get_cutoff_timestamp(target, now=now)
        expired, valid = self.identify_expired(
            target, items, timestamp_key, now=now,
        )
        purged_count = len(expired)

        # in-placeで置換（単一操作でアトミックに）
        items[:] = valid

        logger.info(
            "保持期間パージ: %s – %d件削除, %d件残存",
            target.value, purged_count, len(valid),
        )

        return PurgeResult(
            target=target,
            purged_count=purged_count,
            remaining_count=len(valid),
            cutoff_timestamp=cutoff,
        )

    def update_retention_days(
        self,
        target: RetentionTarget,
        new_days: int,
        approved: bool = False,
    ) -> bool:
        """保持期間を更新する。

        Parameters
        ----------
        target : RetentionTarget
            対象。
        new_days : int
            新しい保持日数。
        approved : bool
            人間承認済みかどうか（監査ログの短縮時に必要）。

        Returns
        -------
        bool
            更新に成功した場合True。
        """
        policy = self._policies.get(target)
        if policy is None:
            return False

        # 監査ログの短縮は人間承認が必要
        if (
            policy.requires_approval_to_shorten
            and new_days < policy.retention_days
            and not approved
        ):
            logger.warning(
                "保持期間短縮拒否: %s – 人間承認が必要",
                target.value,
            )
            return False

        policy.retention_days = new_days
        policy.description = f"{target.value}: {new_days}日保持"
        logger.info(
            "保持期間更新: %s → %d日", target.value, new_days,
        )
        return True

    def get_status(self) -> dict[str, Any]:
        """保持期間管理状態を返す。"""
        return {
            target.value: {
                "retention_days": p.retention_days,
                "requires_approval_to_shorten": p.requires_approval_to_shorten,
            }
            for target, p in self._policies.items()
        }
