"""プラグイン基盤のユニットテスト。

実装手順書 §4.9 / ギャップA6: PluginInterface・PluginManagerテスト。
"""

from typing import Any

import pytest

from vibe_pdca.plugins import (
    PluginCategory,
    PluginInterface,
    PluginManager,
    PluginMeta,
    PluginStatus,
)

# ============================================================
# テスト用プラグイン実装
# ============================================================


class DummyNotificationPlugin(PluginInterface):
    """テスト用通知プラグイン。"""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            meta=PluginMeta(
                name="dummy-notification",
                version="1.0.0",
                category=PluginCategory.NOTIFICATION,
                description="テスト用通知プラグイン",
            ),
            config=config,
        )
        self.initialized = False
        self.executed = False
        self.shutdown_called = False

    def initialize(self) -> None:
        self.initialized = True

    def execute(self, **kwargs: Any) -> Any:
        self.executed = True
        return {"sent": True, "message": kwargs.get("message", "")}

    def shutdown(self) -> None:
        self.shutdown_called = True


class FailingPlugin(PluginInterface):
    """初期化に失敗するテスト用プラグイン。"""

    def __init__(self):
        super().__init__(
            meta=PluginMeta(
                name="failing-plugin",
                version="0.1.0",
                category=PluginCategory.CI,
            ),
        )

    def initialize(self) -> None:
        raise ConnectionError("接続失敗")

    def execute(self, **kwargs: Any) -> Any:
        return None

    def shutdown(self) -> None:
        pass


# ============================================================
# PluginInterface テスト
# ============================================================


class TestPluginInterface:
    def test_plugin_meta(self):
        plugin = DummyNotificationPlugin()
        assert plugin.name == "dummy-notification"
        assert plugin.category == PluginCategory.NOTIFICATION
        assert plugin.meta.version == "1.0.0"

    def test_initial_status_is_disabled(self):
        plugin = DummyNotificationPlugin()
        assert plugin.status == PluginStatus.DISABLED

    def test_get_status(self):
        plugin = DummyNotificationPlugin()
        status = plugin.get_status()
        assert status["name"] == "dummy-notification"
        assert status["status"] == "disabled"


# ============================================================
# PluginManager テスト
# ============================================================


@pytest.fixture
def manager():
    return PluginManager()


class TestPluginRegistration:
    def test_register_plugin(self, manager):
        plugin = DummyNotificationPlugin()
        manager.register(plugin)
        assert manager.plugin_count == 1

    def test_register_duplicate_raises(self, manager):
        manager.register(DummyNotificationPlugin())
        with pytest.raises(ValueError, match="既に登録"):
            manager.register(DummyNotificationPlugin())

    def test_get_plugin(self, manager):
        manager.register(DummyNotificationPlugin())
        plugin = manager.get_plugin("dummy-notification")
        assert plugin is not None
        assert plugin.name == "dummy-notification"

    def test_get_nonexistent_plugin(self, manager):
        assert manager.get_plugin("no-such-plugin") is None


class TestPluginLifecycle:
    def test_initialize_activates(self, manager):
        plugin = DummyNotificationPlugin()
        manager.register(plugin)
        manager.initialize("dummy-notification")
        assert plugin.status == PluginStatus.ACTIVE
        assert plugin.initialized is True

    def test_initialize_failure_sets_error(self, manager):
        plugin = FailingPlugin()
        manager.register(plugin)
        with pytest.raises(ConnectionError):
            manager.initialize("failing-plugin")
        assert plugin.status == PluginStatus.ERROR

    def test_execute_active_plugin(self, manager):
        plugin = DummyNotificationPlugin()
        manager.register(plugin)
        manager.initialize("dummy-notification")
        result = manager.execute("dummy-notification", message="hello")
        assert result["sent"] is True
        assert result["message"] == "hello"

    def test_execute_inactive_raises(self, manager):
        manager.register(DummyNotificationPlugin())
        with pytest.raises(RuntimeError, match="アクティブではありません"):
            manager.execute("dummy-notification")

    def test_disable_plugin(self, manager):
        plugin = DummyNotificationPlugin()
        manager.register(plugin)
        manager.initialize("dummy-notification")
        manager.disable("dummy-notification")
        assert plugin.status == PluginStatus.DISABLED
        assert plugin.shutdown_called is True

    def test_unregister_plugin(self, manager):
        manager.register(DummyNotificationPlugin())
        manager.unregister("dummy-notification")
        assert manager.plugin_count == 0

    def test_unregister_active_calls_shutdown(self, manager):
        plugin = DummyNotificationPlugin()
        manager.register(plugin)
        manager.initialize("dummy-notification")
        manager.unregister("dummy-notification")
        assert plugin.shutdown_called is True


class TestPluginListing:
    def test_list_by_category(self, manager):
        manager.register(DummyNotificationPlugin())
        manager.register(FailingPlugin())
        notifications = manager.list_plugins(category=PluginCategory.NOTIFICATION)
        assert len(notifications) == 1
        assert notifications[0].name == "dummy-notification"

    def test_list_by_status(self, manager):
        plugin = DummyNotificationPlugin()
        manager.register(plugin)
        manager.initialize("dummy-notification")
        active = manager.list_plugins(status=PluginStatus.ACTIVE)
        assert len(active) == 1


class TestPluginBulkOperations:
    def test_initialize_all(self, manager):
        manager.register(DummyNotificationPlugin())
        results = manager.initialize_all()
        assert results["dummy-notification"] is True

    def test_initialize_all_with_failure(self, manager):
        manager.register(DummyNotificationPlugin())
        manager.register(FailingPlugin())
        results = manager.initialize_all()
        assert results["dummy-notification"] is True
        assert results["failing-plugin"] is False

    def test_shutdown_all(self, manager):
        plugin = DummyNotificationPlugin()
        manager.register(plugin)
        manager.initialize("dummy-notification")
        manager.shutdown_all()
        assert plugin.status == PluginStatus.DISABLED

    def test_get_status(self, manager):
        manager.register(DummyNotificationPlugin())
        status = manager.get_status()
        assert status["plugin_count"] == 1
        assert "dummy-notification" in status["plugins"]
