"""通知チャネルの多様化とルーティング。

提案7: 複数の通知チャネル（Discord / Slack / Email / Teams）への
メッセージルーティングと優先度ベースの振り分けを提供する。

- 通知チャネル・優先度の定義
- ルーティングルールの管理
- メッセージディスパッチと履歴管理
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


# ============================================================
# 通知チャネル
# ============================================================


class NotificationChannel(StrEnum):
    """サポートされる通知チャネル。"""

    DISCORD = "discord"
    SLACK = "slack"
    EMAIL = "email"
    TEAMS = "teams"


# ============================================================
# 通知優先度
# ============================================================


class NotificationPriority(StrEnum):
    """通知の優先度レベル。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_PRIORITY_ORDER: dict[NotificationPriority, int] = {
    NotificationPriority.LOW: 0,
    NotificationPriority.MEDIUM: 1,
    NotificationPriority.HIGH: 2,
    NotificationPriority.CRITICAL: 3,
}


# ============================================================
# 通知メッセージ
# ============================================================


@dataclass
class NotificationMessage:
    """送信対象の通知メッセージ。"""

    title: str
    body: str
    priority: NotificationPriority
    channel: NotificationChannel | None = None
    metadata: dict = field(default_factory=dict)


# ============================================================
# チャネル設定
# ============================================================


@dataclass
class ChannelConfig:
    """通知チャネルの設定情報。"""

    channel: NotificationChannel
    webhook_url: str = ""
    is_enabled: bool = True


# ============================================================
# ルーティングルール
# ============================================================


@dataclass
class RoutingRule:
    """通知のルーティングルール。"""

    event_type: str
    min_priority: NotificationPriority
    channels: list[NotificationChannel] = field(default_factory=list)


# ============================================================
# 通知ルーター
# ============================================================


class NotificationRouter:
    """メッセージの優先度とイベント種別に基づき通知先を決定する。"""

    def __init__(self) -> None:
        self._rules: list[RoutingRule] = []
        self._channels: dict[NotificationChannel, ChannelConfig] = {}

    def add_rule(self, rule: RoutingRule) -> None:
        """ルーティングルールを追加する。"""
        self._rules.append(rule)
        logger.info(
            "ルール追加: event=%s min_priority=%s channels=%s",
            rule.event_type,
            rule.min_priority,
            [str(c) for c in rule.channels],
        )

    def add_channel(self, config: ChannelConfig) -> None:
        """チャネル設定を追加する。"""
        self._channels[config.channel] = config
        logger.info(
            "チャネル追加: %s (enabled=%s)",
            config.channel, config.is_enabled,
        )

    def route(self, message: NotificationMessage) -> list[NotificationChannel]:
        """メッセージに適合するチャネルのリストを返す。

        明示的にチャネルが指定されている場合はそれを優先する。
        """
        if message.channel is not None:
            cfg = self._channels.get(message.channel)
            if cfg and cfg.is_enabled:
                return [message.channel]
            return []

        msg_level = _PRIORITY_ORDER.get(message.priority, 0)
        matched: set[NotificationChannel] = set()
        for rule in self._rules:
            rule_level = _PRIORITY_ORDER.get(rule.min_priority, 0)
            if msg_level >= rule_level:
                for ch in rule.channels:
                    cfg = self._channels.get(ch)
                    if cfg and cfg.is_enabled:
                        matched.add(ch)
        return sorted(matched, key=lambda c: c.value)

    def list_rules(self) -> list[RoutingRule]:
        """登録済みルールのリストを返す。"""
        return list(self._rules)

    def list_channels(self) -> list[ChannelConfig]:
        """登録済みチャネル設定のリストを返す。"""
        return sorted(
            self._channels.values(), key=lambda c: c.channel.value,
        )


# ============================================================
# 通知ディスパッチャ
# ============================================================


class NotificationDispatcher:
    """通知メッセージを対象チャネルへ送信（シミュレーション）する。"""

    def __init__(self) -> None:
        self._history: list[dict] = []

    def dispatch(
        self,
        message: NotificationMessage,
        channels: list[NotificationChannel],
    ) -> dict[str, bool]:
        """メッセージを各チャネルへ送信し、結果を返す。

        実際の外部送信は行わず、成功として記録する。
        """
        results: dict[str, bool] = {}
        for ch in channels:
            results[ch.value] = True
            logger.info(
                "通知送信: channel=%s title=%s",
                ch.value, message.title,
            )
        self._history.append({
            "title": message.title,
            "priority": message.priority.value,
            "channels": [ch.value for ch in channels],
            "timestamp": time.time(),
        })
        return results

    def get_history(self, limit: int = 10) -> list[dict]:
        """送信履歴を最新順に返す。"""
        return list(reversed(self._history[-limit:]))
