"""HealthChecker のユニットテスト（モックプロバイダ使用）。"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from vibe_pdca.llm.health import HealthChecker
from vibe_pdca.llm.models import (
    LLMRequest,
    LLMResponse,
    ProviderHealthStatus,
    ProviderStatus,
    ProviderType,
)
from vibe_pdca.llm.providers import BaseLLMProvider, CloudLLMProvider, LocalLLMProvider

# ============================================================
# モックプロバイダ
# ============================================================


class MockCloudProvider(CloudLLMProvider):
    """テスト用クラウドプロバイダ。"""

    def __init__(self, name: str = "mock-cloud", should_fail: bool = False):
        BaseLLMProvider.__init__(self, name=name, provider_type=ProviderType.CLOUD)
        self.model = "mock-cloud-model"
        self.should_fail = should_fail

    def call(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError

    def health_check(self) -> bool:
        return not self.should_fail


class MockLocalProvider(LocalLLMProvider):
    """テスト用ローカルプロバイダ。"""

    def __init__(self, name: str = "mock-local", should_fail: bool = False):
        BaseLLMProvider.__init__(self, name=name, provider_type=ProviderType.LOCAL)
        self.model = "mock-local-model"
        self.should_fail = should_fail

    def call(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError

    def health_check(self) -> bool:
        return not self.should_fail


class ExceptionProvider(CloudLLMProvider):
    """health_check で例外を送出するプロバイダ。"""

    def __init__(self, name: str = "exception-provider"):
        BaseLLMProvider.__init__(self, name=name, provider_type=ProviderType.CLOUD)
        self.model = "err-model"

    def call(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError

    def health_check(self) -> bool:
        raise ConnectionError("テスト用接続エラー")


# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def healthy_providers() -> dict[str, BaseLLMProvider]:
    """全プロバイダが正常なセット。"""
    return {
        "cloud": MockCloudProvider("cloud"),
        "local": MockLocalProvider("local"),
    }


@pytest.fixture
def mixed_providers() -> dict[str, BaseLLMProvider]:
    """クラウドが異常、ローカルが正常なセット。"""
    return {
        "cloud": MockCloudProvider("cloud", should_fail=True),
        "local": MockLocalProvider("local"),
    }


@pytest.fixture
def checker(healthy_providers) -> HealthChecker:
    """基本的な HealthChecker インスタンス。"""
    return HealthChecker(providers=healthy_providers, interval=0.1)


# ============================================================
# テスト: 初期化
# ============================================================


class TestHealthCheckerInit:
    """HealthChecker の初期化テスト。"""

    def test_default_interval(self, healthy_providers):
        """デフォルトのチェック間隔が 30 秒であること。"""
        hc = HealthChecker(providers=healthy_providers)
        assert hc._interval == 30.0

    def test_custom_interval(self, healthy_providers):
        """カスタムチェック間隔が設定されること。"""
        hc = HealthChecker(providers=healthy_providers, interval=5.0)
        assert hc._interval == 5.0

    def test_initial_statuses_empty(self, checker):
        """初期状態でステータスが空であること。"""
        assert checker.statuses == {}

    def test_not_running_initially(self, checker):
        """初期状態でバックグラウンドが停止中であること。"""
        assert checker._running is False


# ============================================================
# テスト: check_all
# ============================================================


class TestCheckAll:
    """check_all() メソッドのテスト。"""

    def test_all_healthy(self, checker):
        """全プロバイダが正常な場合。"""
        results = checker.check_all()

        assert len(results) == 2
        for _name, status in results.items():
            assert isinstance(status, ProviderHealthStatus)
            assert status.status == ProviderStatus.HEALTHY
            assert status.consecutive_failures == 0
            assert status.latency_ms >= 0

    def test_mixed_status(self, mixed_providers):
        """一部プロバイダが異常な場合。"""
        hc = HealthChecker(providers=mixed_providers)
        results = hc.check_all()

        assert results["cloud"].status == ProviderStatus.UNHEALTHY
        assert results["cloud"].consecutive_failures == 1
        assert results["local"].status == ProviderStatus.HEALTHY

    def test_all_unhealthy(self):
        """全プロバイダが異常な場合。"""
        providers = {
            "cloud": MockCloudProvider("cloud", should_fail=True),
            "local": MockLocalProvider("local", should_fail=True),
        }
        hc = HealthChecker(providers=providers)
        results = hc.check_all()

        for status in results.values():
            assert status.status == ProviderStatus.UNHEALTHY

    def test_consecutive_failures_increment(self):
        """連続失敗回数がインクリメントされること。"""
        providers = {"cloud": MockCloudProvider("cloud", should_fail=True)}
        hc = HealthChecker(providers=providers)

        hc.check_all()
        assert hc.statuses["cloud"].consecutive_failures == 1

        hc.check_all()
        assert hc.statuses["cloud"].consecutive_failures == 2

        hc.check_all()
        assert hc.statuses["cloud"].consecutive_failures == 3

    def test_consecutive_failures_reset_on_recovery(self):
        """復帰時に連続失敗回数がリセットされること。"""
        provider = MockCloudProvider("cloud", should_fail=True)
        providers = {"cloud": provider}
        hc = HealthChecker(providers=providers)

        # 2回失敗
        hc.check_all()
        hc.check_all()
        assert hc.statuses["cloud"].consecutive_failures == 2

        # 復帰
        provider.should_fail = False
        hc.check_all()
        assert hc.statuses["cloud"].consecutive_failures == 0

    def test_exception_in_health_check(self):
        """health_check() で例外が発生した場合に UNHEALTHY になること。"""
        providers = {"err": ExceptionProvider("err")}
        hc = HealthChecker(providers=providers)
        results = hc.check_all()

        assert results["err"].status == ProviderStatus.UNHEALTHY
        assert "テスト用接続エラー" in results["err"].error_message
        assert results["err"].consecutive_failures == 1

    def test_updates_statuses_property(self, checker):
        """check_all() 後に statuses プロパティが更新されること。"""
        assert checker.statuses == {}
        checker.check_all()
        assert len(checker.statuses) == 2

    def test_provider_name_in_status(self, checker):
        """ステータスにプロバイダ名が含まれること。"""
        results = checker.check_all()
        assert results["cloud"].provider_name == "cloud"
        assert results["local"].provider_name == "local"

    def test_provider_type_in_status(self, checker):
        """ステータスにプロバイダタイプが含まれること。"""
        results = checker.check_all()
        assert results["cloud"].provider_type == ProviderType.CLOUD
        assert results["local"].provider_type == ProviderType.LOCAL

    def test_last_checked_at_set(self, checker):
        """last_checked_at が設定されること。"""
        before = time.time()
        results = checker.check_all()
        after = time.time()

        for status in results.values():
            assert before <= status.last_checked_at <= after


# ============================================================
# テスト: ステータス変化コールバック
# ============================================================


class TestStatusChangeCallback:
    """on_status_change コールバックのテスト。"""

    def test_callback_on_status_change(self):
        """ステータスが変化した場合にコールバックが呼ばれること。"""
        callback = MagicMock()
        provider = MockCloudProvider("cloud")
        hc = HealthChecker(
            providers={"cloud": provider},
            on_status_change=callback,
        )

        # 初回チェック（前回ステータスなし → コールバックなし）
        hc.check_all()
        callback.assert_not_called()

        # 障害発生 → ステータス変化 → コールバック
        provider.should_fail = True
        hc.check_all()
        callback.assert_called_once()

        args = callback.call_args[0]
        assert args[0] == "cloud"  # プロバイダ名
        assert args[1].status == ProviderStatus.HEALTHY  # 旧ステータス
        assert args[2].status == ProviderStatus.UNHEALTHY  # 新ステータス

    def test_no_callback_on_same_status(self):
        """ステータスが変わらない場合にコールバックが呼ばれないこと。"""
        callback = MagicMock()
        hc = HealthChecker(
            providers={"cloud": MockCloudProvider("cloud")},
            on_status_change=callback,
        )

        hc.check_all()
        hc.check_all()  # 同じ HEALTHY ステータス
        callback.assert_not_called()

    def test_callback_on_recovery(self):
        """障害から復帰した場合にコールバックが呼ばれること。"""
        callback = MagicMock()
        provider = MockCloudProvider("cloud", should_fail=True)
        hc = HealthChecker(
            providers={"cloud": provider},
            on_status_change=callback,
        )

        hc.check_all()  # 初回: UNHEALTHY（前回なし → コールバックなし）
        provider.should_fail = False
        hc.check_all()  # 復帰: UNHEALTHY → HEALTHY
        callback.assert_called_once()

    def test_no_callback_when_not_set(self):
        """コールバック未設定時にエラーにならないこと。"""
        provider = MockCloudProvider("cloud")
        hc = HealthChecker(providers={"cloud": provider})

        hc.check_all()
        provider.should_fail = True
        hc.check_all()  # エラーが起きないことを確認


# ============================================================
# テスト: get_status
# ============================================================


class TestGetStatus:
    """get_status() メソッドのテスト。"""

    def test_get_existing_provider(self, checker):
        """存在するプロバイダのステータスを取得できること。"""
        checker.check_all()
        status = checker.get_status("cloud")
        assert status is not None
        assert status.provider_name == "cloud"

    def test_get_nonexistent_provider(self, checker):
        """存在しないプロバイダの場合に None を返すこと。"""
        assert checker.get_status("nonexistent") is None

    def test_get_status_before_check(self, checker):
        """チェック前にステータスが None であること。"""
        assert checker.get_status("cloud") is None


# ============================================================
# テスト: statuses プロパティ
# ============================================================


class TestStatusesProperty:
    """statuses プロパティのテスト。"""

    def test_returns_copy(self, checker):
        """statuses が内部辞書のコピーを返すこと。"""
        checker.check_all()
        s1 = checker.statuses
        s2 = checker.statuses
        assert s1 == s2
        assert s1 is not s2  # 別オブジェクト

    def test_empty_providers(self):
        """プロバイダが空の場合。"""
        hc = HealthChecker(providers={})
        results = hc.check_all()
        assert results == {}
        assert hc.statuses == {}


# ============================================================
# テスト: check_internet_connectivity
# ============================================================


class TestCheckInternetConnectivity:
    """check_internet_connectivity() のテスト。"""

    def test_connectivity_success(self, checker):
        """少なくとも1つのホストに接続できれば True。"""
        mock_sock = MagicMock()
        with patch("socket.create_connection", return_value=mock_sock):
            assert checker.check_internet_connectivity() is True
            mock_sock.close.assert_called_once()

    def test_connectivity_failure(self, checker):
        """全ホストへの接続失敗で False。"""
        with patch("socket.create_connection", side_effect=OSError("refused")):
            assert checker.check_internet_connectivity() is False

    def test_connectivity_partial_failure(self, checker):
        """一部失敗でも接続可能なホストがあれば True。"""
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise OSError("refused")
            return MagicMock()

        with patch("socket.create_connection", side_effect=side_effect):
            assert checker.check_internet_connectivity() is True

    def test_connectivity_timeout(self, checker):
        """タイムアウトで False。"""
        with patch("socket.create_connection", side_effect=TimeoutError("timeout")):
            assert checker.check_internet_connectivity() is False


# ============================================================
# テスト: バックグラウンド監視
# ============================================================


class TestBackgroundMonitoring:
    """start_background() / stop_background() のテスト。"""

    def test_start_and_stop(self, checker):
        """バックグラウンド開始・停止が正常に動作すること。"""
        checker.start_background()
        assert checker._running is True
        assert checker._thread is not None
        assert checker._thread.is_alive()

        checker.stop_background()
        assert checker._running is False
        assert checker._thread is None

    def test_double_start_ignored(self, checker):
        """二重開始が無視されること。"""
        checker.start_background()
        first_thread = checker._thread

        checker.start_background()  # 二重開始
        assert checker._thread is first_thread  # 同じスレッド

        checker.stop_background()

    def test_stop_when_not_running(self, checker):
        """停止中に stop_background() を呼んでもエラーにならないこと。"""
        checker.stop_background()  # エラーなし

    def test_background_executes_check_all(self, healthy_providers):
        """バックグラウンドスレッドが check_all() を実行すること。"""
        hc = HealthChecker(providers=healthy_providers, interval=0.05)
        hc.start_background()

        # スレッドが少なくとも1回チェックを実行するまで待機
        time.sleep(0.2)
        hc.stop_background()

        assert len(hc.statuses) == 2

    def test_thread_is_daemon(self, checker):
        """バックグラウンドスレッドがデーモンスレッドであること。"""
        checker.start_background()
        assert checker._thread.daemon is True
        checker.stop_background()

    def test_thread_name(self, checker):
        """バックグラウンドスレッドの名前が設定されていること。"""
        checker.start_background()
        assert checker._thread.name == "llm-health-checker"
        checker.stop_background()


# ============================================================
# テスト: HealthChecker スレッドセーフティ
# ============================================================


class TestHealthCheckerThreadSafety:
    """check_all()の並行呼び出しでstatusesが壊れないことを検証する。"""

    def test_concurrent_check_all(self):
        """複数スレッドがcheck_all()を同時に呼んでも例外が発生しないこと。"""
        import threading

        providers = {
            f"p{i}": MockCloudProvider(f"p{i}") for i in range(5)
        }
        checker = HealthChecker(providers=providers, interval=60.0)
        errors: list[Exception] = []
        lock = threading.Lock()

        def run_check() -> None:
            try:
                checker.check_all()
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=run_check) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        # 全プロバイダのステータスが記録されていること
        assert len(checker.statuses) == 5
