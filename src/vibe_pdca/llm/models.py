"""LLMリクエスト/レスポンスおよび関連データモデル定義。

ADR-001（マルチLLMモデル選定）§1.2, §5.1 準拠。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# --- ペルソナ役割: AIに割り当てる5つの役割＋DO（実装担当） ---
class Role(Enum):
    """ペルソナ役割定義（§5.1）。"""

    PM = "pm"
    SCRIBE = "scribe"
    PROGRAMMER = "programmer"
    DESIGNER = "designer"
    USER = "user"
    DO = "do"


# --- プロバイダ種別: クラウドAPI or ローカルサーバー ---
class ProviderType(Enum):
    """LLMプロバイダの種別。"""

    CLOUD = "cloud"
    LOCAL = "local"


# --- プロバイダ稼働状態: healthy(正常)→degraded(低下)→unhealthy(異常) ---
class ProviderStatus(Enum):
    """プロバイダの稼働状態。"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# --- LLMリクエスト: AIに送信するプロンプトと設定パラメータ ---
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


# --- LLMレスポンス: AIからの応答と利用統計（トークン数・コスト・遅延） ---
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


# --- ヘルスチェック結果: プロバイダの応答速度や連続失敗回数を記録 ---
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
