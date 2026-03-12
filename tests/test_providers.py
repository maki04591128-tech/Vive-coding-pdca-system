"""LLMプロバイダのユニットテスト（モックSDK使用）。"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from vibe_pdca.llm.models import LLMRequest, LLMResponse, ProviderType, Role
from vibe_pdca.llm.providers import BaseLLMProvider, CloudLLMProvider, LocalLLMProvider

# ============================================================
# ヘルパー: テスト用モックプロバイダ
# ============================================================


class ConcreteProvider(BaseLLMProvider):
    """抽象メソッドを実装した具象テスト用プロバイダ。"""

    def __init__(self, name: str = "test", provider_type: ProviderType = ProviderType.CLOUD):
        super().__init__(name=name, provider_type=provider_type)

    def call(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="ok",
            model="test-model",
            provider_type=self.provider_type,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            latency_ms=0.0,
            role=request.role,
        )

    def health_check(self) -> bool:
        return True


def _make_request(**kwargs) -> LLMRequest:
    """テスト用LLMRequestを生成するヘルパー。"""
    defaults = {
        "role": Role.PM,
        "system_prompt": "システムプロンプト",
        "user_prompt": "ユーザープロンプト",
    }
    defaults.update(kwargs)
    return LLMRequest(**defaults)


# ============================================================
# OpenAI互換レスポンスのモック構造体
# ============================================================


def _openai_chat_response(
    content: str = "response",
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
):
    """OpenAI chat.completions.create の戻り値を模倣する。"""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def _anthropic_message_response(
    text: str = "response",
    input_tokens: int = 10,
    output_tokens: int = 20,
):
    """Anthropic messages.create の戻り値を模倣する。"""
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _make_openai_mock_client():
    """OpenAI パス用のモッククライアント（messages 属性なし）。"""
    client = SimpleNamespace(
        chat=MagicMock(),
        models=MagicMock(),
    )
    return client


def _make_anthropic_mock_client():
    """Anthropic パス用のモッククライアント（messages 属性あり）。"""
    return MagicMock()  # MagicMock は全属性に応答 → hasattr(client, "messages") == True


# ============================================================
# テスト: BaseLLMProvider（基底クラス）
# ============================================================


class TestBaseLLMProvider:
    """BaseLLMProvider の基本動作テスト。"""

    def test_init_sets_name_and_type(self):
        """名前とプロバイダタイプが正しく設定されること。"""
        p = ConcreteProvider(name="my-provider", provider_type=ProviderType.LOCAL)
        assert p.name == "my-provider"
        assert p.provider_type == ProviderType.LOCAL

    def test_repr(self):
        """__repr__ がクラス名と名前を含むこと。"""
        p = ConcreteProvider(name="repr-test")
        assert "ConcreteProvider" in repr(p)
        assert "repr-test" in repr(p)

    def test_call_returns_response(self):
        """call() が LLMResponse を返すこと。"""
        p = ConcreteProvider()
        resp = p.call(_make_request())
        assert isinstance(resp, LLMResponse)

    def test_health_check_returns_bool(self):
        """health_check() が bool を返すこと。"""
        p = ConcreteProvider()
        assert p.health_check() is True

    def test_cannot_instantiate_abstract(self):
        """抽象クラスを直接インスタンス化できないこと。"""
        with pytest.raises(TypeError):
            BaseLLMProvider(name="x", provider_type=ProviderType.CLOUD)  # type: ignore[abstract]


# ============================================================
# テスト: CloudLLMProvider
# ============================================================


class TestCloudLLMProvider:
    """CloudLLMProvider のテスト。"""

    def _make_cloud(self, name: str = "openai-test", **kwargs) -> CloudLLMProvider:
        """テスト用 CloudLLMProvider を生成する。"""
        defaults = {
            "name": name,
            "api_key": "test-key",
            "model": "gpt-4",
            "cost_per_1k_input": 0.03,
            "cost_per_1k_output": 0.06,
        }
        defaults.update(kwargs)
        return CloudLLMProvider(**defaults)

    # ── 初期化テスト ──

    def test_init_attributes(self):
        """初期化時に全属性が正しく設定されること。"""
        p = self._make_cloud(
            base_url="https://custom.api/v1",
            timeout=60.0,
        )
        assert p.name == "openai-test"
        assert p.api_key == "test-key"
        assert p.model == "gpt-4"
        assert p.base_url == "https://custom.api/v1"
        assert p.cost_per_1k_input == 0.03
        assert p.cost_per_1k_output == 0.06
        assert p.timeout == 60.0
        assert p.provider_type == ProviderType.CLOUD

    def test_default_timeout(self):
        """デフォルトのタイムアウトが 120 秒であること。"""
        p = self._make_cloud()
        assert p.timeout == 120.0

    def test_repr(self):
        """__repr__ にクラス名と名前が含まれること。"""
        p = self._make_cloud(name="cloud-repr")
        assert "CloudLLMProvider" in repr(p)
        assert "cloud-repr" in repr(p)

    # ── _get_client テスト ──

    def test_get_client_openai(self):
        """OpenAI 名のプロバイダが openai.OpenAI クライアントを返すこと。"""
        p = self._make_cloud(name="openai-test")
        mock_client = MagicMock()
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        with patch.dict(sys.modules, {"openai": mock_openai}):
            client = p._get_client()
            assert client is mock_client
            mock_openai.OpenAI.assert_called_once()

    def test_get_client_openai_with_base_url(self):
        """base_url 指定時に OpenAI クライアントへ渡されること。"""
        p = self._make_cloud(name="xai-test", base_url="https://xai.api/v1")
        mock_client = MagicMock()
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        with patch.dict(sys.modules, {"openai": mock_openai}):
            client = p._get_client()
            assert client is mock_client
            call_kwargs = mock_openai.OpenAI.call_args
            assert call_kwargs.kwargs.get("base_url") == "https://xai.api/v1"

    def test_get_client_anthropic(self):
        """Anthropic 名のプロバイダが anthropic.Anthropic クライアントを返すこと。"""
        p = self._make_cloud(name="anthropic-claude")
        mock_client = MagicMock()
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            p._client = None
            client = p._get_client()
            assert client is mock_client

    def test_get_client_cached(self):
        """一度取得したクライアントがキャッシュされること。"""
        p = self._make_cloud(name="openai-cache")
        mock_client = MagicMock()
        p._client = mock_client
        assert p._get_client() is mock_client

    # ── call テスト: OpenAI 互換 ──

    def test_call_openai_success(self):
        """OpenAI 互換プロバイダの正常呼び出し。"""
        p = self._make_cloud(name="openai-call")
        mock_client = _make_openai_mock_client()
        mock_client.chat.completions.create.return_value = _openai_chat_response(
            content="こんにちは", prompt_tokens=5, completion_tokens=15,
        )
        p._client = mock_client

        req = _make_request()
        resp = p.call(req)

        assert resp.content == "こんにちは"
        assert resp.model == "gpt-4"
        assert resp.provider_type == ProviderType.CLOUD
        assert resp.input_tokens == 5
        assert resp.output_tokens == 15
        assert resp.cost_usd > 0
        assert resp.latency_ms >= 0
        assert resp.role == Role.PM

    def test_call_openai_with_system_prompt(self):
        """システムプロンプト付きの呼び出しでメッセージが正しく構築されること。"""
        p = self._make_cloud(name="openai-sys")
        mock_client = _make_openai_mock_client()
        mock_client.chat.completions.create.return_value = _openai_chat_response()
        p._client = mock_client

        req = _make_request(system_prompt="あなたはPMです", user_prompt="計画して")
        p.call(req)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_call_openai_without_system_prompt(self):
        """システムプロンプトなしの呼び出し。"""
        p = self._make_cloud(name="openai-nosys")
        mock_client = _make_openai_mock_client()
        mock_client.chat.completions.create.return_value = _openai_chat_response()
        p._client = mock_client

        req = _make_request(system_prompt="")
        p.call(req)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_call_openai_json_format(self):
        """response_format="json" で JSON モードが設定されること。"""
        p = self._make_cloud(name="openai-json")
        mock_client = _make_openai_mock_client()
        mock_client.chat.completions.create.return_value = _openai_chat_response()
        p._client = mock_client

        req = _make_request(response_format="json")
        p.call(req)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_call_openai_cost_calculation(self):
        """コスト計算が正しいこと。"""
        p = self._make_cloud(
            name="openai-cost",
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.03,
        )
        mock_client = _make_openai_mock_client()
        mock_client.chat.completions.create.return_value = _openai_chat_response(
            prompt_tokens=1000, completion_tokens=2000,
        )
        p._client = mock_client

        resp = p.call(_make_request())
        # コスト = (1000/1000)*0.01 + (2000/1000)*0.03 = 0.01 + 0.06 = 0.07
        assert abs(resp.cost_usd - 0.07) < 1e-9

    # ── call テスト: Anthropic ──

    def test_call_anthropic_success(self):
        """Anthropic プロバイダの正常呼び出し。"""
        p = self._make_cloud(name="anthropic-call", model="claude-sonnet")
        mock_client = MagicMock()  # 'messages' 属性あり → Anthropic パス
        mock_client.messages.create.return_value = _anthropic_message_response(
            text="Anthropic応答", input_tokens=8, output_tokens=12,
        )
        p._client = mock_client

        resp = p.call(_make_request())

        assert resp.content == "Anthropic応答"
        assert resp.model == "claude-sonnet"
        assert resp.input_tokens == 8
        assert resp.output_tokens == 12

    # ── call テスト: エラー ──

    def test_call_raises_on_api_error(self):
        """API エラー時に例外が送出されること。"""
        p = self._make_cloud(name="openai-err")
        mock_client = _make_openai_mock_client()
        mock_client.chat.completions.create.side_effect = RuntimeError("API Error")
        p._client = mock_client

        with pytest.raises(RuntimeError, match="API Error"):
            p.call(_make_request())

    def test_call_openai_empty_choices_raises(self):
        """OpenAI API が空のchoicesを返した場合にRuntimeErrorが発生すること。"""
        p = self._make_cloud(name="openai-empty")
        mock_client = _make_openai_mock_client()
        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0),
        )
        p._client = mock_client

        with pytest.raises(RuntimeError, match="空のchoices"):
            p.call(_make_request())

    def test_call_openai_none_content_returns_empty_string(self):
        """OpenAI API がcontent=Noneを返した場合に空文字列になること。"""
        p = self._make_cloud(name="openai-none")
        mock_client = _make_openai_mock_client()
        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=10),
        )
        p._client = mock_client

        resp = p.call(_make_request())
        assert resp.content == ""

    def test_call_anthropic_empty_content_raises(self):
        """Anthropic API が空のコンテンツを返した場合にRuntimeErrorが発生すること。"""
        p = self._make_cloud(name="anthropic-empty", model="claude-3")
        mock_client = MagicMock()
        mock_client.messages.create.return_value = SimpleNamespace(
            content=[],
            usage=SimpleNamespace(input_tokens=0, output_tokens=0),
        )
        p._client = mock_client

        with pytest.raises(RuntimeError, match="空のコンテンツ"):
            p.call(_make_request())

    # ── health_check テスト ──

    def test_health_check_openai_success(self):
        """OpenAI 互換のヘルスチェック成功。"""
        p = self._make_cloud(name="openai-hc")
        mock_client = _make_openai_mock_client()
        mock_client.models.list.return_value = ["model1"]
        p._client = mock_client

        assert p.health_check() is True

    def test_health_check_anthropic_success(self):
        """Anthropic のヘルスチェック成功。"""
        p = self._make_cloud(name="anthropic-hc", model="claude-3")
        mock_client = MagicMock()  # 'messages' 属性あり
        mock_client.messages.create.return_value = SimpleNamespace()
        p._client = mock_client

        assert p.health_check() is True

    def test_health_check_failure(self):
        """ヘルスチェック失敗時に False を返すこと。"""
        p = self._make_cloud(name="openai-hc-fail")
        mock_client = _make_openai_mock_client()
        mock_client.models.list.side_effect = ConnectionError("timeout")
        p._client = mock_client

        assert p.health_check() is False


# ============================================================
# テスト: LocalLLMProvider
# ============================================================


class TestLocalLLMProvider:
    """LocalLLMProvider のテスト。"""

    def _make_local(self, name: str = "ollama-test", **kwargs) -> LocalLLMProvider:
        """テスト用 LocalLLMProvider を生成する。"""
        defaults = {
            "name": name,
            "model": "llama3",
        }
        defaults.update(kwargs)
        return LocalLLMProvider(**defaults)

    # ── 初期化テスト ──

    def test_init_attributes(self):
        """初期化時に全属性が正しく設定されること。"""
        p = self._make_local(
            base_url="http://localhost:8080/v1",
            timeout=60.0,
        )
        assert p.name == "ollama-test"
        assert p.model == "llama3"
        assert p.base_url == "http://localhost:8080/v1"
        assert p.timeout == 60.0
        assert p.provider_type == ProviderType.LOCAL

    def test_default_base_url(self):
        """デフォルトの base_url が Ollama エンドポイントであること。"""
        p = self._make_local()
        assert p.base_url == "http://localhost:11434/v1"

    def test_default_timeout(self):
        """デフォルトのタイムアウトが 300 秒であること。"""
        p = self._make_local()
        assert p.timeout == 300.0

    def test_repr(self):
        """__repr__ にクラス名と名前が含まれること。"""
        p = self._make_local(name="local-repr")
        assert "LocalLLMProvider" in repr(p)
        assert "local-repr" in repr(p)

    # ── _get_client テスト ──

    def test_get_client(self):
        """OpenAI 互換クライアントが生成されること。"""
        p = self._make_local()
        mock_client = MagicMock()
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        with patch.dict(sys.modules, {"openai": mock_openai}):
            client = p._get_client()
            assert client is mock_client
            call_kwargs = mock_openai.OpenAI.call_args.kwargs
            assert call_kwargs["base_url"] == "http://localhost:11434/v1"
            assert call_kwargs["api_key"] == "not-needed"

    def test_get_client_cached(self):
        """一度取得したクライアントがキャッシュされること。"""
        p = self._make_local()
        mock_client = MagicMock()
        p._client = mock_client
        assert p._get_client() is mock_client

    # ── call テスト ──

    def test_call_success(self):
        """正常呼び出しで LLMResponse が返ること。"""
        p = self._make_local()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _openai_chat_response(
            content="ローカル応答", prompt_tokens=5, completion_tokens=10,
        )
        p._client = mock_client

        resp = p.call(_make_request())

        assert resp.content == "ローカル応答"
        assert resp.model == "llama3"
        assert resp.provider_type == ProviderType.LOCAL
        assert resp.input_tokens == 5
        assert resp.output_tokens == 10
        assert resp.cost_usd == 0.0  # ローカルはコスト0
        assert resp.latency_ms >= 0

    def test_call_with_system_prompt(self):
        """システムプロンプト付きの呼び出し。"""
        p = self._make_local()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _openai_chat_response()
        p._client = mock_client

        req = _make_request(system_prompt="ローカルPM", user_prompt="計画")
        p.call(req)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert len(messages) == 2

    def test_call_without_system_prompt(self):
        """システムプロンプトなしの呼び出し。"""
        p = self._make_local()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _openai_chat_response()
        p._client = mock_client

        req = _make_request(system_prompt="")
        p.call(req)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert len(messages) == 1

    def test_call_json_format(self):
        """response_format="json" 指定時。"""
        p = self._make_local()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _openai_chat_response()
        p._client = mock_client

        req = _make_request(response_format="json")
        p.call(req)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_call_handles_none_usage(self):
        """usage が None のトークン値を 0 として処理すること。"""
        p = self._make_local()
        mock_client = MagicMock()
        mock_resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=SimpleNamespace(prompt_tokens=None, completion_tokens=None),
        )
        mock_client.chat.completions.create.return_value = mock_resp
        p._client = mock_client

        resp = p.call(_make_request())
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0

    def test_call_raises_on_error(self):
        """API エラー時に例外が送出されること。"""
        p = self._make_local()
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = ConnectionError("接続拒否")
        p._client = mock_client

        with pytest.raises(ConnectionError, match="接続拒否"):
            p.call(_make_request())

    def test_call_empty_choices_raises(self):
        """ローカルLLMが空のchoicesを返した場合にRuntimeErrorが発生すること。"""
        p = self._make_local()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0),
        )
        p._client = mock_client

        with pytest.raises(RuntimeError, match="空のchoices"):
            p.call(_make_request())

    def test_call_none_content_returns_empty_string(self):
        """ローカルLLMがcontent=Noneを返した場合に空文字列になること。"""
        p = self._make_local()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=10),
        )
        p._client = mock_client

        resp = p.call(_make_request())
        assert resp.content == ""

    # ── health_check テスト ──

    def test_health_check_via_api_tags(self):
        """Ollama /api/tags エンドポイントでのヘルスチェック成功。"""
        p = self._make_local()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            assert p.health_check() is True

    def test_health_check_fallback_to_models_list(self):
        """/api/tags 失敗時に models.list へフォールバックすること。"""
        p = self._make_local()
        mock_client = MagicMock()
        mock_client.models.list.return_value = ["model1"]
        p._client = mock_client

        with patch("urllib.request.urlopen", side_effect=ConnectionError("refused")):
            assert p.health_check() is True

    def test_health_check_all_fail(self):
        """全エンドポイント失敗時に False を返すこと。"""
        p = self._make_local()
        mock_client = MagicMock()
        mock_client.models.list.side_effect = ConnectionError("refused")
        p._client = mock_client

        with patch("urllib.request.urlopen", side_effect=ConnectionError("refused")):
            assert p.health_check() is False
