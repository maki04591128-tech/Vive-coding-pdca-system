"""クラウド / ローカル LLM プロバイダ実装。

ADR-001 のモデル選定に基づき、役割ごとに最適なプロバイダを提供する。
各プロバイダは共通の BaseLLMProvider インターフェースを実装する。
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from vibe_pdca.llm.models import (
    LLMRequest,
    LLMResponse,
    ProviderType,
)

logger = logging.getLogger(__name__)


# ============================================================
# 基底クラス
# ============================================================


# --- LLMプロバイダ基底クラス: すべてのAIサービス接続の共通インターフェース ---
class BaseLLMProvider(ABC):
    """LLMプロバイダの基底インターフェース。"""

    def __init__(self, name: str, provider_type: ProviderType) -> None:
        self.name = name
        self.provider_type = provider_type

    @abstractmethod
    def call(self, request: LLMRequest) -> LLMResponse:
        """LLM にリクエストを送信しレスポンスを返す。"""

    @abstractmethod
    def health_check(self) -> bool:
        """プロバイダが稼働中かどうかを返す。"""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


# ============================================================
# クラウド LLM プロバイダ
# ============================================================


# --- クラウドLLM: インターネット経由でAPIを呼び出すプロバイダ（OpenAI, Anthropic等） ---
class CloudLLMProvider(BaseLLMProvider):
    """クラウド LLM プロバイダ（OpenAI / Anthropic / Google / xAI 等）。

    Parameters
    ----------
    name : str
        プロバイダ識別名（例: "openai-gpt5.1", "anthropic-opus4"）。
    api_key : str
        API キー。
    model : str
        使用するモデル名。
    base_url : str | None
        API エンドポイント URL（OpenAI 互換の場合に指定）。
    cost_per_1k_input : float
        入力 1,000 トークンあたりのコスト (USD)。
    cost_per_1k_output : float
        出力 1,000 トークンあたりのコスト (USD)。
    timeout : float
        API 呼び出しタイムアウト（秒）。
    """

    def __init__(
        self,
        name: str,
        api_key: str,
        model: str,
        base_url: str | None = None,
        cost_per_1k_input: float = 0.0,
        cost_per_1k_output: float = 0.0,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(name=name, provider_type=ProviderType.CLOUD)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.timeout = timeout
        self._client: Any = None

    def _get_client(self) -> Any:
        """遅延初期化で API クライアントを取得する。"""
        if self._client is not None:
            return self._client

        # Anthropic SDK
        if "anthropic" in self.name.lower() or "claude" in self.name.lower():
            try:
                import anthropic

                self._client = anthropic.Anthropic(
                    api_key=self.api_key,
                    timeout=self.timeout,
                )
                return self._client
            except ImportError as e:
                raise RuntimeError(
                    "anthropic パッケージが必要です: pip install anthropic"
                ) from e

        # OpenAI 互換 SDK (OpenAI / xAI / その他)
        try:
            import openai

            if self.base_url:
                self._client = openai.OpenAI(
                    api_key=self.api_key,
                    timeout=self.timeout,
                    base_url=self.base_url,
                )
            else:
                self._client = openai.OpenAI(
                    api_key=self.api_key,
                    timeout=self.timeout,
                )
            return self._client
        except ImportError as e:
            raise RuntimeError(
                "openai パッケージが必要です: pip install openai"
            ) from e

    def call(self, request: LLMRequest) -> LLMResponse:
        """クラウド LLM に API 呼び出しを行う。"""
        client = self._get_client()
        start = time.monotonic()

        try:
            # Anthropic SDK
            if hasattr(client, "messages"):
                resp = client.messages.create(
                    model=self.model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    system=request.system_prompt,
                    messages=[{"role": "user", "content": request.user_prompt}],
                )
                content = resp.content[0].text
                input_tokens = resp.usage.input_tokens
                output_tokens = resp.usage.output_tokens

            # OpenAI 互換 SDK
            else:
                messages = []
                if request.system_prompt:
                    messages.append({"role": "system", "content": request.system_prompt})
                messages.append({"role": "user", "content": request.user_prompt})

                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                }
                if request.response_format == "json":
                    kwargs["response_format"] = {"type": "json_object"}

                resp = client.chat.completions.create(**kwargs)
                content = resp.choices[0].message.content
                input_tokens = resp.usage.prompt_tokens
                output_tokens = resp.usage.completion_tokens

            latency_ms = (time.monotonic() - start) * 1000
            cost_usd = (
                (input_tokens / 1000) * self.cost_per_1k_input
                + (output_tokens / 1000) * self.cost_per_1k_output
            )

            return LLMResponse(
                content=content,
                model=self.model,
                provider_type=ProviderType.CLOUD,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                role=request.role,
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            logger.error(
                "クラウドLLM呼び出し失敗 [%s]: %s (%.1fms)",
                self.name, e, latency_ms,
            )
            raise

    def health_check(self) -> bool:
        """軽量なヘルスチェック（API 疎通確認）。"""
        try:
            client = self._get_client()

            # Anthropic: メッセージ送信で確認
            if hasattr(client, "messages"):
                resp = client.messages.create(
                    model=self.model,
                    max_tokens=1,
                    messages=[{"role": "user", "content": "ping"}],
                )
                return resp is not None

            # OpenAI 互換: models.list で確認
            resp = client.models.list()
            return resp is not None

        except Exception as e:
            logger.debug("ヘルスチェック失敗 [%s]: %s", self.name, e)
            return False


# ============================================================
# ローカル LLM プロバイダ
# ============================================================


# --- ローカルLLM: 自前サーバーで動作するプロバイダ（vLLM, Ollama等） ---
class LocalLLMProvider(BaseLLMProvider):
    """ローカル LLM プロバイダ（Ollama / llama.cpp / vLLM 等）。

    OpenAI 互換 API を提供するローカルサーバーに接続する。

    Parameters
    ----------
    name : str
        プロバイダ識別名（例: "ollama-llama3"）。
    model : str
        使用するモデル名。
    base_url : str
        ローカルサーバーの URL（例: "http://localhost:11434/v1"）。
    timeout : float
        呼び出しタイムアウト（秒）。
    """

    def __init__(
        self,
        name: str,
        model: str,
        base_url: str = "http://localhost:11434/v1",
        timeout: float = 300.0,
    ) -> None:
        super().__init__(name=name, provider_type=ProviderType.LOCAL)
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self._client: Any = None

    def _get_client(self) -> Any:
        """遅延初期化で OpenAI 互換クライアントを取得する。"""
        if self._client is not None:
            return self._client

        try:
            import openai

            self._client = openai.OpenAI(
                api_key="not-needed",
                base_url=self.base_url,
                timeout=self.timeout,
            )
            return self._client
        except ImportError as e:
            raise RuntimeError(
                "openai パッケージが必要です: pip install openai"
            ) from e

    def call(self, request: LLMRequest) -> LLMResponse:
        """ローカル LLM に呼び出しを行う。"""
        client = self._get_client()
        start = time.monotonic()

        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.user_prompt})

            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
            }
            if request.response_format == "json":
                kwargs["response_format"] = {"type": "json_object"}

            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
            input_tokens = getattr(resp.usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(resp.usage, "completion_tokens", 0) or 0

            latency_ms = (time.monotonic() - start) * 1000

            return LLMResponse(
                content=content,
                model=self.model,
                provider_type=ProviderType.LOCAL,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=0.0,  # ローカルLLMはコスト0
                latency_ms=latency_ms,
                role=request.role,
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            logger.error(
                "ローカルLLM呼び出し失敗 [%s]: %s (%.1fms)",
                self.name, e, latency_ms,
            )
            raise

    def health_check(self) -> bool:
        """ローカルサーバーの疎通確認。"""
        try:
            import urllib.request

            req = urllib.request.Request(
                self.base_url.rstrip("/").replace("/v1", "") + "/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return bool(resp.status == 200)
        except Exception:
            # OpenAI 互換エンドポイントで /models を試す
            try:
                client = self._get_client()
                client.models.list()
                return True
            except Exception as e:
                logger.debug("ローカルLLMヘルスチェック失敗 [%s]: %s", self.name, e)
                return False
