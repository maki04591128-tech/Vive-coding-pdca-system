"""LLM ゲートウェイのユニットテスト（モックプロバイダ使用）。"""

import pytest

from vibe_pdca.llm.circuit_breaker import CircuitBreakerConfig
from vibe_pdca.llm.gateway import (
    CloudLLMUnavailableError,
    CostLimitExceededError,
    LLMGateway,
)
from vibe_pdca.llm.models import LLMRequest, LLMResponse, ProviderType, Role
from vibe_pdca.llm.providers import BaseLLMProvider, CloudLLMProvider, LocalLLMProvider

# ============================================================
# モックプロバイダ
# ============================================================


class MockCloudProvider(CloudLLMProvider):
    """テスト用クラウドプロバイダ。"""

    def __init__(self, name="mock-cloud", should_fail=False):
        # super().__init__ を回避して直接設定
        BaseLLMProvider.__init__(self, name=name, provider_type=ProviderType.CLOUD)
        self.model = "mock-cloud-model"
        self.should_fail = should_fail
        self.call_count = 0

    def call(self, request: LLMRequest) -> LLMResponse:
        self.call_count += 1
        if self.should_fail:
            raise ConnectionError("クラウドLLM接続エラー（テスト）")
        return LLMResponse(
            content="cloud response",
            model=self.model,
            provider_type=ProviderType.CLOUD,
            input_tokens=10,
            output_tokens=20,
            cost_usd=0.001,
            latency_ms=100.0,
            role=request.role,
        )

    def health_check(self) -> bool:
        return not self.should_fail


class MockLocalProvider(LocalLLMProvider):
    """テスト用ローカルプロバイダ。"""

    def __init__(self, name="mock-local", should_fail=False):
        BaseLLMProvider.__init__(self, name=name, provider_type=ProviderType.LOCAL)
        self.model = "mock-local-model"
        self.should_fail = should_fail
        self.call_count = 0

    def call(self, request: LLMRequest) -> LLMResponse:
        self.call_count += 1
        if self.should_fail:
            raise ConnectionError("ローカルLLM接続エラー（テスト）")
        return LLMResponse(
            content="local response",
            model=self.model,
            provider_type=ProviderType.LOCAL,
            input_tokens=10,
            output_tokens=20,
            cost_usd=0.0,
            latency_ms=500.0,
            role=request.role,
        )

    def health_check(self) -> bool:
        return not self.should_fail


# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def request_pm():
    return LLMRequest(
        role=Role.PM,
        system_prompt="テスト用システムプロンプト",
        user_prompt="テスト用ユーザープロンプト",
    )


@pytest.fixture
def gateway_with_providers():
    """クラウド・ローカル両方登録済みのゲートウェイ。"""
    gw = LLMGateway()
    cloud = MockCloudProvider("mock-cloud")
    local = MockLocalProvider("mock-local")

    gw.register_cloud_provider(
        cloud,
        roles=[Role.PM, Role.PROGRAMMER, Role.DO],
        circuit_breaker_config=CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=1.0,
        ),
    )
    gw.register_local_provider(
        local,
        roles=[Role.PM, Role.PROGRAMMER, Role.DO],
    )
    return gw, cloud, local


# ============================================================
# テスト: クラウドモード
# ============================================================


class TestCloudMode:
    def test_calls_cloud_provider(self, gateway_with_providers, request_pm):
        gw, cloud, local = gateway_with_providers
        gw.set_mode(ProviderType.CLOUD)

        resp = gw.call(request_pm)
        assert resp.provider_type == ProviderType.CLOUD
        assert resp.content == "cloud response"
        assert cloud.call_count == 1
        assert local.call_count == 0

    def test_tracks_cost(self, gateway_with_providers, request_pm):
        gw, _, _ = gateway_with_providers
        gw.call(request_pm)
        assert gw.cost_tracker.daily_calls == 1
        assert gw.cost_tracker.daily_cost_usd > 0


# ============================================================
# テスト: ローカルモード
# ============================================================


class TestLocalMode:
    def test_calls_local_provider(self, gateway_with_providers, request_pm):
        gw, cloud, local = gateway_with_providers
        gw.set_mode(ProviderType.LOCAL)

        resp = gw.call(request_pm)
        assert resp.provider_type == ProviderType.LOCAL
        assert resp.content == "local response"
        assert cloud.call_count == 0
        assert local.call_count == 1


# ============================================================
# テスト: 自動フォールバック
# ============================================================


class TestAutoFallback:
    def test_cloud_failure_falls_back_to_local(self, request_pm):
        gw = LLMGateway()
        cloud = MockCloudProvider("mock-cloud", should_fail=True)
        local = MockLocalProvider("mock-local")

        gw.register_cloud_provider(
            cloud, roles=[Role.PM],
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=1),
        )
        gw.register_local_provider(local, roles=[Role.PM])
        gw.set_mode(ProviderType.CLOUD)

        resp = gw.call(request_pm)
        assert resp.provider_type == ProviderType.LOCAL
        assert resp.fallback_used is True
        assert "障害" in resp.fallback_reason

    def test_no_fallback_when_disabled(self, request_pm):
        gw = LLMGateway()
        cloud = MockCloudProvider("mock-cloud", should_fail=True)

        gw.register_cloud_provider(
            cloud, roles=[Role.PM],
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=1),
        )
        gw.set_mode(ProviderType.CLOUD)
        gw.set_auto_fallback(False)

        with pytest.raises(CloudLLMUnavailableError):
            gw.call(request_pm)

    def test_local_failure_falls_back_to_cloud(self, request_pm):
        gw = LLMGateway()
        cloud = MockCloudProvider("mock-cloud")
        local = MockLocalProvider("mock-local", should_fail=True)

        gw.register_cloud_provider(
            cloud, roles=[Role.PM],
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=3),
        )
        gw.register_local_provider(local, roles=[Role.PM])
        gw.set_mode(ProviderType.LOCAL)

        resp = gw.call(request_pm)
        assert resp.provider_type == ProviderType.CLOUD


# ============================================================
# テスト: コスト制限
# ============================================================


class TestCostLimits:
    def test_raises_on_daily_cost_exceeded(self, gateway_with_providers, request_pm):
        gw, _, _ = gateway_with_providers
        gw.cost_tracker.daily_cost_usd = 30.0
        gw.cost_tracker.daily_limit_usd = 30.0

        with pytest.raises(CostLimitExceededError):
            gw.call(request_pm)


# ============================================================
# テスト: モード切替
# ============================================================


class TestModeSwitch:
    def test_switch_mode(self, gateway_with_providers):
        gw, _, _ = gateway_with_providers
        gw.set_mode(ProviderType.LOCAL, reason="テスト切替")
        assert gw.preferred_mode == ProviderType.LOCAL

        gw.set_mode(ProviderType.CLOUD, reason="テスト復帰")
        assert gw.preferred_mode == ProviderType.CLOUD


# ============================================================
# テスト: ステータス
# ============================================================


class TestGatewayStatus:
    def test_returns_status(self, gateway_with_providers):
        gw, _, _ = gateway_with_providers
        status = gw.get_status()

        assert "preferred_mode" in status
        assert "auto_fallback_enabled" in status
        assert "cloud_providers" in status
        assert "cost" in status

    def test_local_providers_include_model_info(self, gateway_with_providers):
        gw, _, _ = gateway_with_providers
        status = gw.get_status()

        assert "local_providers" in status
        assert "mock-local" in status["local_providers"]
        local_info = status["local_providers"]["mock-local"]
        assert local_info["model"] == "mock-local-model"

    def test_status_includes_response_language(self, gateway_with_providers):
        gw, _, _ = gateway_with_providers
        status = gw.get_status()
        assert "response_language" in status


# ============================================================
# テスト: 日本語応答強制（ゲートウェイレベル）
# ============================================================


class TestJapaneseEnforcementGateway:
    """ゲートウェイレベルでの日本語応答強制テスト。"""

    def test_injects_japanese_directive_by_default(self, request_pm):
        """デフォルト設定（response_language="ja"）で日本語指示が注入されること。"""
        gw = LLMGateway()
        cloud = MockCloudProvider("mock-cloud")
        gw.register_cloud_provider(
            cloud, roles=[Role.PM],
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=3),
        )
        gw.set_mode(ProviderType.CLOUD)

        # _inject_language_directiveを直接テストして注入を確認
        injected = gw._inject_language_directive(request_pm)
        assert "日本語" in injected.system_prompt
        assert injected.system_prompt.startswith("【重要】")

    def test_does_not_duplicate_directive(self, request_pm):
        """PromptBuilder経由で既に指示がある場合、重複注入しないこと。"""
        from vibe_pdca.prompts import JAPANESE_RESPONSE_DIRECTIVE

        gw = LLMGateway()
        # 既にJAPANESE_RESPONSE_DIRECTIVEが含まれるリクエスト
        request_with_directive = LLMRequest(
            role=Role.PM,
            system_prompt=f"{JAPANESE_RESPONSE_DIRECTIVE}\n\nPMとして計画を立案してください。",
            user_prompt="テスト",
        )
        injected = gw._inject_language_directive(request_with_directive)
        # 重複していないことを確認（出現回数が1回のみ）
        assert injected.system_prompt.count("【重要】") == 1

    def test_no_injection_when_disabled(self, request_pm):
        """response_language=Noneで注入が無効化されること。"""
        gw = LLMGateway()
        gw.set_response_language(None)

        injected = gw._inject_language_directive(request_pm)
        assert "【重要】" not in injected.system_prompt
        assert injected.system_prompt == request_pm.system_prompt

    def test_preserves_original_system_prompt(self, request_pm):
        """元のシステムプロンプトが保持されること。"""
        gw = LLMGateway()
        injected = gw._inject_language_directive(request_pm)
        assert request_pm.system_prompt in injected.system_prompt

    def test_handles_empty_system_prompt(self):
        """空のシステムプロンプトでも正しく注入されること。"""
        gw = LLMGateway()
        request = LLMRequest(
            role=Role.PM,
            system_prompt="",
            user_prompt="テスト",
        )
        injected = gw._inject_language_directive(request)
        assert "日本語" in injected.system_prompt

    def test_response_language_property(self):
        """response_languageプロパティのget/set。"""
        gw = LLMGateway()
        assert gw.response_language == "ja"

        gw.set_response_language(None)
        assert gw.response_language is None

        gw.set_response_language("ja")
        assert gw.response_language == "ja"

    def test_config_sets_response_language(self):
        """config辞書からresponse_languageが設定されること。"""
        gw = LLMGateway(config={"response_language": "ja"})
        assert gw.response_language == "ja"

        gw_none = LLMGateway(config={"response_language": None})
        assert gw_none.response_language is None
