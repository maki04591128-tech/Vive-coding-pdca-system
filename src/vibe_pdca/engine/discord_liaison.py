"""Discord連携 – A承認・B通知・サイクル完了通知。

M2 タスク 2-6: 要件定義書 §18 準拠。

- A操作: Discord上で承認/却下を完結（4/4承認、12時間タイムアウト）
- B操作: 通知のみ
- サイクル完了: 通知のみ
- 承認/却下は監査ログに保存
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from vibe_pdca.models.pdca import GovernanceLevel

logger = logging.getLogger(__name__)

# §18.1 確定値
APPROVAL_TIMEOUT_SECONDS = 12 * 3600  # 12時間
REQUIRED_APPROVALS = 4


class NotificationType(StrEnum):
    """通知種別。"""

    A_APPROVAL = "a_approval"
    B_NOTIFY = "b_notify"
    CYCLE_COMPLETE = "cycle_complete"
    STOP_ALERT = "stop_alert"
    PROGRESS_REPORT = "progress_report"


class ApprovalStatus(StrEnum):
    """承認ステータス。"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass
class ApprovalRequest:
    """A操作の承認リクエスト。"""

    id: str = field(default_factory=lambda: f"apr-{uuid.uuid4().hex[:8]}")
    operation_description: str = ""
    governance_level: GovernanceLevel = GovernanceLevel.A
    status: ApprovalStatus = ApprovalStatus.PENDING
    required_approvals: int = REQUIRED_APPROVALS
    approvals: list[dict[str, Any]] = field(default_factory=list)
    rejections: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    resolved_at: float | None = None
    timeout_seconds: float = APPROVAL_TIMEOUT_SECONDS

    @property
    def approval_count(self) -> int:
        return len(self.approvals)

    @property
    def is_resolved(self) -> bool:
        return self.status != ApprovalStatus.PENDING


@dataclass
class NotificationMessage:
    """Discord通知メッセージ。"""

    notification_type: NotificationType
    title: str
    body: str
    channel_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class DiscordLiaison:
    """Discord連携マネージャー。

    A操作の承認フロー、B操作の通知、サイクル完了通知を管理する。
    実際のDiscord API呼び出しは外部から注入する。
    """

    def __init__(
        self,
        webhook_url: str = "",
        channel_id: str = "",
    ) -> None:
        self._webhook_url = webhook_url
        self._channel_id = channel_id
        self._pending_approvals: dict[str, ApprovalRequest] = {}
        self._notification_history: list[NotificationMessage] = []

    @property
    def pending_approval_count(self) -> int:
        return len(self._pending_approvals)

    @property
    def notification_count(self) -> int:
        return len(self._notification_history)

    def create_approval_request(
        self,
        operation_description: str,
        governance_level: GovernanceLevel = GovernanceLevel.A,
    ) -> ApprovalRequest:
        """A操作の承認リクエストを作成する。

        Parameters
        ----------
        operation_description : str
            操作の説明。
        governance_level : GovernanceLevel
            操作分類。

        Returns
        -------
        ApprovalRequest
            作成された承認リクエスト。
        """
        request = ApprovalRequest(
            operation_description=operation_description,
            governance_level=governance_level,
        )
        self._pending_approvals[request.id] = request

        logger.info(
            "承認リクエスト作成: %s (%s)",
            request.id, operation_description,
        )
        return request

    def approve(
        self,
        request_id: str,
        approver: str,
        comment: str = "",
    ) -> ApprovalRequest:
        """承認する。

        Parameters
        ----------
        request_id : str
            承認リクエストID。
        approver : str
            承認者。
        comment : str
            コメント。

        Returns
        -------
        ApprovalRequest
            更新された承認リクエスト。
        """
        request = self._get_pending_request(request_id)
        request.approvals.append({
            "approver": approver,
            "comment": comment,
            "timestamp": time.time(),
        })

        # 必要承認数に達したら承認完了
        if request.approval_count >= request.required_approvals:
            request.status = ApprovalStatus.APPROVED
            request.resolved_at = time.time()
            del self._pending_approvals[request_id]
            logger.info("承認完了: %s", request_id)

        return request

    def reject(
        self,
        request_id: str,
        rejector: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """却下する。

        Parameters
        ----------
        request_id : str
            承認リクエストID。
        rejector : str
            却下者。
        reason : str
            却下理由。

        Returns
        -------
        ApprovalRequest
            更新された承認リクエスト。
        """
        request = self._get_pending_request(request_id)
        request.rejections.append({
            "rejector": rejector,
            "reason": reason,
            "timestamp": time.time(),
        })
        request.status = ApprovalStatus.REJECTED
        request.resolved_at = time.time()
        del self._pending_approvals[request_id]
        logger.info("承認却下: %s (理由: %s)", request_id, reason)
        return request

    def check_timeouts(self, now: float | None = None) -> list[ApprovalRequest]:
        """タイムアウトした承認リクエストを処理する。

        Returns
        -------
        list[ApprovalRequest]
            タイムアウトしたリクエスト。
        """
        current = now if now is not None else time.time()
        timed_out: list[ApprovalRequest] = []

        for request_id in list(self._pending_approvals.keys()):
            request = self._pending_approvals[request_id]
            elapsed = current - request.created_at
            if elapsed > request.timeout_seconds:
                request.status = ApprovalStatus.TIMEOUT
                request.resolved_at = current
                del self._pending_approvals[request_id]
                timed_out.append(request)
                logger.warning(
                    "承認タイムアウト: %s (経過: %.0f秒)",
                    request_id, elapsed,
                )

        return timed_out

    def send_notification(
        self,
        notification_type: NotificationType,
        title: str,
        body: str,
    ) -> NotificationMessage:
        """通知メッセージを送信する。

        Parameters
        ----------
        notification_type : NotificationType
            通知種別。
        title : str
            タイトル。
        body : str
            本文。

        Returns
        -------
        NotificationMessage
            送信されたメッセージ。
        """
        message = NotificationMessage(
            notification_type=notification_type,
            title=title,
            body=body,
            channel_id=self._channel_id,
        )
        self._notification_history.append(message)

        logger.info(
            "Discord通知: [%s] %s",
            notification_type.value, title,
        )
        return message

    def format_cycle_complete(
        self,
        milestone_title: str,
        cycle_number: int,
        decision: str,
    ) -> str:
        """サイクル完了通知のフォーマット（§B2）。"""
        return (
            f"📊 **サイクル完了通知**\n"
            f"マイルストーン: {milestone_title}\n"
            f"サイクル: #{cycle_number}\n"
            f"判定: {decision}\n"
        )

    def format_stop_alert(
        self,
        reason: str,
        detail: str,
    ) -> str:
        """停止アラートのフォーマット。"""
        return (
            f"🚨 **PDCA停止アラート**\n"
            f"停止理由: {reason}\n"
            f"詳細: {detail}\n"
        )

    def get_status(self) -> dict[str, Any]:
        """Discord連携状態を返す。"""
        return {
            "pending_approvals": self.pending_approval_count,
            "total_notifications": self.notification_count,
            "webhook_configured": bool(self._webhook_url),
        }

    def _get_pending_request(self, request_id: str) -> ApprovalRequest:
        """保留中の承認リクエストを取得する。"""
        if request_id not in self._pending_approvals:
            raise KeyError(f"保留中の承認リクエストが見つかりません: {request_id}")
        return self._pending_approvals[request_id]
