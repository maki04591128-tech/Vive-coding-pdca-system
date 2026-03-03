"""LLMリクエスト/レスポンスおよび関連データモデル定義。

ADR-001（マルチLLMモデル選定）§1.2, §5.1 準拠。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(Enum):
    """ペルソナ役割定義（§5.1）。"""

    PM = "pm"
    SCRIBE = "scribe"
    PROGRAMMER = "programmer"
    DESIGNER = "designer"
    USER = "user"
    DO = "do"


class ProviderType(Enum):
    """LLMプロバイダの種別。"""

    CLOUD = "cloud"
    LOCAL = "local"


class ProviderStatus(Enum):
    """プロバイダの稼働状態。"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class LLMRequest:
    """LLM呼び出しリクエスト。"""

    role: Role
    system_prompt: str
    user_prompt: str
    max_tokens: int = 4096
    temperature: float = 0.3
    response_format: str | None = None  # "json" for structured output
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """LLM呼び出しレスポンス。"""

    content: str
    model: str
    provider_type: ProviderType
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    role: Role
    fallback_used: bool = False
    fallback_reason: str | None = None


@dataclass
class ProviderHealthStatus:
    """プロバイダのヘルスチェック結果。"""

    provider_name: str
    provider_type: ProviderType
    status: ProviderStatus
    latency_ms: float | None = None
    error_message: str | None = None
    last_checked_at: float = 0.0  # Unix timestamp
    consecutive_failures: int = 0
