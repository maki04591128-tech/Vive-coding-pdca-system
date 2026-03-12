"""Webhook/イベント駆動アーキテクチャ。

提案1: Webhookイベントの受信・ルーティング・バックプレッシャー制御。

- GitHubイベント(Issue, PR, Check Suite等)の受信キュー管理
- イベントタイプ別のルーティング
- バックプレッシャー制御による過負荷防止
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


# ── WebhookEventType ──

# GitHubから送られてくるイベントの種類（Issue作成、PR レビュー、CI完了等）
class WebhookEventType(StrEnum):
    """Webhookイベントの種別。"""

    ISSUE_OPENED = "issue_opened"
    PR_REVIEW = "pr_review"
    CHECK_SUITE = "check_suite"
    ISSUE_COMMENT = "issue_comment"


# ── WebhookEvent ──


@dataclass
class WebhookEvent:
    """受信したWebhookイベント。

    Parameters
    ----------
    event_type : WebhookEventType
        イベント種別。
    payload : dict
        イベントペイロード。
    received_at : float
        受信タイムスタンプ (epoch秒)。
    event_id : str
        一意なイベントID。
    """

    event_type: WebhookEventType
    payload: dict[str, object] = field(default_factory=dict)
    received_at: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)


# ── EventFilter ──

# --- イベントフィルター: 受信したイベントを種別やペイロードで取捨選択 ---
@dataclass
class EventFilter:
    """イベントフィルタ条件。

    Parameters
    ----------
    event_types : list[WebhookEventType]
        対象イベント種別のリスト。
    repository : str | None
        リポジトリ名でのフィルタ (None=全リポジトリ)。
    """

    event_types: list[WebhookEventType] = field(default_factory=list)
    repository: str | None = None

    def matches(self, event: WebhookEvent) -> bool:
        """イベントがフィルタ条件に合致するか判定する。"""
        if self.event_types and event.event_type not in self.event_types:
            return False
        if self.repository is not None:
            repo = event.payload.get("repository", "")
            if repo != self.repository:
                return False
        return True


# ── EventQueue ──

# --- イベントキュー: 受信したイベントを順番に処理する待ち行列 ---
class EventQueue:
    """インメモリのイベントキュー。

    Parameters
    ----------
    max_size : int
        キューの最大サイズ。
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._max_size = max_size
        self._queue: deque[WebhookEvent] = deque()
        self._lock = threading.Lock()

    @property
    def max_size(self) -> int:
        """キューの最大サイズを返す。"""
        return self._max_size

    @property
    def size(self) -> int:
        """現在のキューサイズを返す。"""
        return len(self._queue)

    @property
    def is_full(self) -> bool:
        """キューが満杯かどうかを返す。"""
        return len(self._queue) >= self._max_size

    def push(self, event: WebhookEvent) -> bool:
        """イベントをキューに追加する。

        Returns
        -------
        bool
            追加に成功した場合True、キュー満杯の場合False。
        """
        with self._lock:
            if self.is_full:
                logger.warning(
                    "イベントキュー満杯 (max=%d), イベント破棄: %s",
                    self._max_size,
                    event.event_id,
                )
                return False
            self._queue.append(event)
            logger.info(
                "イベント追加: %s (type=%s, size=%d)",
                event.event_id,
                event.event_type,
                self.size,
            )
            return True

    def pop(self) -> WebhookEvent | None:
        """先頭のイベントを取り出す。空の場合None。"""
        with self._lock:
            if not self._queue:
                return None
            return self._queue.popleft()

    def peek(self) -> WebhookEvent | None:
        """先頭のイベントを参照する (取り出さない)。"""
        with self._lock:
            if not self._queue:
                return None
            return self._queue[0]

    def clear(self) -> None:
        """キューを空にする。"""
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            logger.info("イベントキューをクリア (削除件数=%d)", count)


# ── BackpressureController ──

# バックプレッシャー制御: キューが満杯に近づいたら新規イベントの受け入れを制限
class BackpressureController:
    """バックプレッシャー制御。

    キュー充填率が閾値を超えた場合にバックプレッシャーを通知する。

    Parameters
    ----------
    threshold : float
        バックプレッシャー発動の閾値 (0.0〜1.0, デフォルト0.8)。
    """

    def __init__(self, threshold: float = 0.8) -> None:
        if not 0.0 <= threshold <= 1.0:
            msg = f"閾値は0.0〜1.0の範囲: {threshold}"
            raise ValueError(msg)
        self._threshold = threshold

    @property
    def threshold(self) -> float:
        """閾値を返す。"""
        return self._threshold

    def check(self, queue: EventQueue) -> bool:
        """バックプレッシャーが必要かどうかを判定する。

        Returns
        -------
        bool
            閾値超過でTrue (バックプレッシャー発動)。
        """
        if queue.max_size == 0:
            return True
        ratio = queue.size / queue.max_size
        if ratio >= self._threshold:
            logger.warning(
                "バックプレッシャー発動: 充填率=%.1f%% (閾値=%.1f%%)",
                ratio * 100,
                self._threshold * 100,
            )
            return True
        return False

    def strategy(self) -> str:
        """現在のバックプレッシャー戦略名を返す。"""
        return "drop_oldest"


# ── WebhookRouter ──

# --- ルーター: イベント種別に応じて適切なハンドラ（処理関数）に振り分ける ---
class WebhookRouter:
    """イベントタイプ別のルーティング。

    イベントタイプにハンドラ名を登録し、受信イベントを適切な
    ハンドラにルーティングする。
    """

    def __init__(self) -> None:
        self._handlers: dict[WebhookEventType, str] = {}

    def register_handler(
        self,
        event_type: WebhookEventType,
        callback_name: str,
    ) -> None:
        """イベントタイプにハンドラを登録する。"""
        self._handlers[event_type] = callback_name
        logger.info(
            "ハンドラ登録: %s → %s",
            event_type,
            callback_name,
        )

    def route(self, event: WebhookEvent) -> str:
        """イベントを適切なハンドラにルーティングする。

        Returns
        -------
        str
            ハンドラ名。未登録の場合は 'unhandled'。
        """
        handler = self._handlers.get(event.event_type, "unhandled")
        if handler == "unhandled":
            logger.warning(
                "未登録イベントタイプ: %s (event_id=%s)",
                event.event_type,
                event.event_id,
            )
        return handler

    def list_handlers(self) -> dict[str, str]:
        """登録済みハンドラの一覧を返す。"""
        return {k.value: v for k, v in self._handlers.items()}
