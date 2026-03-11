"""通知チャネルルーティングのテスト。"""

from vibe_pdca.engine.notification_router import (
    ChannelConfig,
    NotificationChannel,
    NotificationDispatcher,
    NotificationMessage,
    NotificationPriority,
    NotificationRouter,
    RoutingRule,
)

# ============================================================
# テスト: NotificationChannel / NotificationPriority
# ============================================================


class TestEnums:
    def test_channel_values(self):
        assert NotificationChannel.DISCORD == "discord"
        assert NotificationChannel.SLACK == "slack"
        assert NotificationChannel.EMAIL == "email"
        assert NotificationChannel.TEAMS == "teams"

    def test_priority_values(self):
        assert NotificationPriority.LOW == "low"
        assert NotificationPriority.MEDIUM == "medium"
        assert NotificationPriority.HIGH == "high"
        assert NotificationPriority.CRITICAL == "critical"


# ============================================================
# テスト: NotificationMessage
# ============================================================


class TestNotificationMessage:
    def test_defaults(self):
        msg = NotificationMessage(
            title="Test",
            body="Body",
            priority=NotificationPriority.LOW,
        )
        assert msg.channel is None
        assert msg.metadata == {}

    def test_with_channel(self):
        msg = NotificationMessage(
            title="Alert",
            body="Something happened",
            priority=NotificationPriority.HIGH,
            channel=NotificationChannel.SLACK,
            metadata={"source": "ci"},
        )
        assert msg.channel == NotificationChannel.SLACK
        assert msg.metadata["source"] == "ci"


# ============================================================
# テスト: ChannelConfig / RoutingRule
# ============================================================


class TestConfigs:
    def test_channel_config_defaults(self):
        cfg = ChannelConfig(channel=NotificationChannel.DISCORD)
        assert cfg.webhook_url == ""
        assert cfg.is_enabled is True

    def test_routing_rule(self):
        rule = RoutingRule(
            event_type="build_failure",
            min_priority=NotificationPriority.HIGH,
            channels=[NotificationChannel.SLACK],
        )
        assert rule.event_type == "build_failure"
        assert rule.channels == [NotificationChannel.SLACK]


# ============================================================
# テスト: NotificationRouter
# ============================================================


class TestNotificationRouter:
    def _make_router(self) -> NotificationRouter:
        router = NotificationRouter()
        router.add_channel(ChannelConfig(
            NotificationChannel.SLACK, "https://hooks/slack",
        ))
        router.add_channel(ChannelConfig(
            NotificationChannel.DISCORD, "https://hooks/discord",
        ))
        router.add_channel(ChannelConfig(
            NotificationChannel.EMAIL, "smtp://mail",
        ))
        router.add_rule(RoutingRule(
            event_type="alert",
            min_priority=NotificationPriority.HIGH,
            channels=[
                NotificationChannel.SLACK,
                NotificationChannel.DISCORD,
            ],
        ))
        router.add_rule(RoutingRule(
            event_type="info",
            min_priority=NotificationPriority.LOW,
            channels=[NotificationChannel.EMAIL],
        ))
        return router

    def test_route_high_priority(self):
        router = self._make_router()
        msg = NotificationMessage(
            title="Alert", body="Error",
            priority=NotificationPriority.HIGH,
        )
        channels = router.route(msg)
        assert NotificationChannel.SLACK in channels
        assert NotificationChannel.DISCORD in channels

    def test_route_low_priority(self):
        router = self._make_router()
        msg = NotificationMessage(
            title="Info", body="OK",
            priority=NotificationPriority.LOW,
        )
        channels = router.route(msg)
        assert NotificationChannel.EMAIL in channels

    def test_route_explicit_channel(self):
        router = self._make_router()
        msg = NotificationMessage(
            title="Direct", body="msg",
            priority=NotificationPriority.LOW,
            channel=NotificationChannel.SLACK,
        )
        channels = router.route(msg)
        assert channels == [NotificationChannel.SLACK]

    def test_route_explicit_disabled_channel(self):
        router = NotificationRouter()
        router.add_channel(ChannelConfig(
            NotificationChannel.TEAMS, is_enabled=False,
        ))
        msg = NotificationMessage(
            title="X", body="Y",
            priority=NotificationPriority.LOW,
            channel=NotificationChannel.TEAMS,
        )
        assert router.route(msg) == []

    def test_route_no_matching_rules(self):
        router = NotificationRouter()
        msg = NotificationMessage(
            title="X", body="Y",
            priority=NotificationPriority.LOW,
        )
        assert router.route(msg) == []

    def test_list_rules(self):
        router = self._make_router()
        rules = router.list_rules()
        assert len(rules) == 2

    def test_list_channels(self):
        router = self._make_router()
        channels = router.list_channels()
        assert len(channels) == 3
        # ソート順確認: discord < email < slack
        assert channels[0].channel == NotificationChannel.DISCORD

    def test_critical_matches_high_rule(self):
        router = self._make_router()
        msg = NotificationMessage(
            title="Critical", body="Down",
            priority=NotificationPriority.CRITICAL,
        )
        channels = router.route(msg)
        assert NotificationChannel.SLACK in channels


# ============================================================
# テスト: NotificationDispatcher
# ============================================================


class TestNotificationDispatcher:
    def test_dispatch_success(self):
        dispatcher = NotificationDispatcher()
        msg = NotificationMessage(
            title="Test", body="Body",
            priority=NotificationPriority.LOW,
        )
        result = dispatcher.dispatch(
            msg, [NotificationChannel.SLACK, NotificationChannel.EMAIL],
        )
        assert result["slack"] is True
        assert result["email"] is True

    def test_dispatch_empty_channels(self):
        dispatcher = NotificationDispatcher()
        msg = NotificationMessage(
            title="X", body="Y",
            priority=NotificationPriority.LOW,
        )
        result = dispatcher.dispatch(msg, [])
        assert result == {}

    def test_get_history(self):
        dispatcher = NotificationDispatcher()
        msg = NotificationMessage(
            title="H1", body="B",
            priority=NotificationPriority.LOW,
        )
        dispatcher.dispatch(msg, [NotificationChannel.SLACK])
        history = dispatcher.get_history()
        assert len(history) == 1
        assert history[0]["title"] == "H1"

    def test_get_history_limit(self):
        dispatcher = NotificationDispatcher()
        for i in range(5):
            msg = NotificationMessage(
                title=f"M{i}", body="B",
                priority=NotificationPriority.LOW,
            )
            dispatcher.dispatch(msg, [NotificationChannel.DISCORD])
        history = dispatcher.get_history(limit=3)
        assert len(history) == 3
        assert history[0]["title"] == "M4"

    def test_get_history_empty(self):
        dispatcher = NotificationDispatcher()
        assert dispatcher.get_history() == []


# ============================================================
# テスト: スレッドセーフティ
# ============================================================


class TestNotificationRouterThreadSafety:
    """NotificationRouter のスレッドセーフティ検証。"""

    def test_concurrent_add_rule(self):
        """複数スレッドからルール追加しても整合性が保たれる。"""
        import threading
        router = NotificationRouter()
        errors: list[str] = []

        def add(tid: int) -> None:
            try:
                for i in range(25):
                    router.add_rule(RoutingRule(
                        event_type=f"event-{tid}-{i}",
                        min_priority=NotificationPriority.LOW,
                        channels=[NotificationChannel.DISCORD],
                    ))
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=add, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(router.list_rules()) == 100


class TestNotificationDispatcherThreadSafety:
    """NotificationDispatcher のスレッドセーフティ検証。"""

    def test_concurrent_dispatch(self):
        """複数スレッドから同時にディスパッチしても整合性が保たれる。"""
        import threading
        dispatcher = NotificationDispatcher()
        errors: list[str] = []

        def dispatch(tid: int) -> None:
            try:
                for i in range(25):
                    msg = NotificationMessage(
                        title=f"M-{tid}-{i}",
                        body="body",
                        priority=NotificationPriority.LOW,
                    )
                    dispatcher.dispatch(msg, [NotificationChannel.DISCORD])
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=dispatch, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(dispatcher.get_history(limit=200)) == 100
