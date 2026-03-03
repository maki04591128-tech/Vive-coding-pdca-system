"""LLM ゲートウェイ – クラウド / ローカル LLM の統一インターフェース。

本モジュールは以下の機能を提供する:
  1. 設定ベースのクラウド ↔ ローカル LLM 手動切替
  2. サーキットブレーカーによるクラウド障害時の自動ローカルフォールバック
  3. 役割 (Role) → プロバイダマッピング
  4. ヘルスチェックによる常時監視
  5. コスト追跡・監査ログ出力

ADR-001 / §4.2 / §13.2 / §26.1 準拠。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from vibe_pdca.llm.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from vibe_pdca.llm.health import HealthChecker
from vibe_pdca.llm.models import (
    LLMRequest,
    LLMResponse,
    ProviderStatus,
    ProviderType,
    Role,
)
from vibe_pdca.llm.providers import BaseLLMProvider, CloudLLMProvider, LocalLLMProvider

logger = logging.getLogger(__name__)


# ============================================================
# コスト追跡
# ============================================================


@dataclass
class CostTracker:
    """LLM 呼び出しコストの追跡。§15.1 準拠。"""

    daily_cost_usd: float = 0.0
    cycle_cost_usd: float = 0.0
    daily_calls: int = 0
    cycle_calls: int = 0
    daily_limit_usd: float = 30.0
    per_cycle_limit_usd: float = 5.0
    max_calls_per_cycle: int = 80
    max_calls_per_day: int = 500
    history: list[dict[str, Any]] = field(default_factory=list)

    def record(self, response: LLMResponse) -> None:
        self.daily_cost_usd += response.cost_usd
        self.cycle_cost_usd += response.cost_usd
        self.daily_calls += 1
        self.cycle_calls += 1
        self.history.append({
            "model": response.model,
            "provider_type": response.provider_type.value,
            "role": response.role.value,
            "cost_usd": response.cost_usd,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "latency_ms": response.latency_ms,
            "fallback_used": response.fallback_used,
            "timestamp": time.time(),
        })

    def check_limits(self) -> tuple[bool, str]:
        """コスト上限チェック。超過時は (False, 理由) を返す。"""
        if self.daily_cost_usd >= self.daily_limit_usd:
            return False, f"日次コスト上限超過: ${self.daily_cost_usd:.2f} >= ${self.daily_limit_usd:.2f}"
        if self.cycle_cost_usd >= self.per_cycle_limit_usd:
            return False, f"サイクルコスト上限超過: ${self.cycle_cost_usd:.2f} >= ${self.per_cycle_limit_usd:.2f}"
        if self.daily_calls >= self.max_calls_per_day:
            return False, f"日次呼び出し上限超過: {self.daily_calls} >= {self.max_calls_per_day}"
        if self.cycle_calls >= self.max_calls_per_cycle:
            return False, f"サイクル呼び出し上限超過: {self.cycle_calls} >= {self.max_calls_per_cycle}"
        return True, ""

    def reset_cycle(self) -> None:
        self.cycle_cost_usd = 0.0
        self.cycle_calls = 0

    def reset_daily(self) -> None:
        self.daily_cost_usd = 0.0
        self.daily_calls = 0


# ============================================================
# ゲートウェイ本体
# ============================================================


class LLMGateway:
    """統一 LLM 呼び出しインターフェース。

    Parameters
    ----------
    config : dict
        設定辞書（config/default.yml の llm セクション相当）。
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}

        # プロバイダ登録
        self._cloud_providers: dict[str, CloudLLMProvider] = {}
        self._local_providers: dict[str, LocalLLMProvider] = {}

        # 役割 → プロバイダ名マッピング（クラウド/ローカルそれぞれ）
        self._role_cloud_map: dict[Role, list[str]] = {}
        self._role_local_map: dict[Role, list[str]] = {}

        # サーキットブレーカー（クラウドプロバイダごと）
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

        # ヘルスチェッカー
        self._health_checker: HealthChecker | None = None

        # コスト追跡
        self.cost_tracker = CostTracker()

        # 動作モード
        self._preferred_mode: ProviderType = ProviderType.CLOUD
        self._auto_fallback_enabled: bool = True

    # ── プロバイダ登録 ──

    def register_cloud_provider(
        self,
        provider: CloudLLMProvider,
        roles: list[Role] | None = None,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
    ) -> None:
        """クラウド LLM プロバイダを登録する。"""
        self._cloud_providers[provider.name] = provider
        self._circuit_breakers[provider.name] = CircuitBreaker(
            name=provider.name,
            config=circuit_breaker_config or CircuitBreakerConfig(),
        )
        if roles:
            for role in roles:
                self._role_cloud_map.setdefault(role, []).append(provider.name)

        logger.info(
            "クラウドプロバイダ登録: %s (model=%s, roles=%s)",
            provider.name, provider.model,
            [r.value for r in (roles or [])],
        )

    def register_local_provider(
        self,
        provider: LocalLLMProvider,
        roles: list[Role] | None = None,
    ) -> None:
        """ローカル LLM プロバイダを登録する。"""
        self._local_providers[provider.name] = provider
        if roles:
            for role in roles:
                self._role_local_map.setdefault(role, []).append(provider.name)

        logger.info(
            "ローカルプロバイダ登録: %s (model=%s, roles=%s)",
            provider.name, provider.model,
            [r.value for r in (roles or [])],
        )

    # ── モード制御 ──

    @property
    def preferred_mode(self) -> ProviderType:
        """現在の優先モードを返す。"""
        return self._preferred_mode

    def set_mode(self, mode: ProviderType, reason: str = "") -> None:
        """手動で優先モードを切り替える。

        Parameters
        ----------
        mode : ProviderType
            CLOUD または LOCAL。
        reason : str
            切替理由（監査ログ用）。
        """
        old_mode = self._preferred_mode
        self._preferred_mode = mode
        logger.info(
            "LLMモード切替: %s → %s (理由: %s)",
            old_mode.value, mode.value, reason or "なし",
        )

    @property
    def auto_fallback_enabled(self) -> bool:
        return self._auto_fallback_enabled

    def set_auto_fallback(self, enabled: bool) -> None:
        """自動フォールバックの有効 / 無効を設定する。"""
        self._auto_fallback_enabled = enabled
        logger.info("自動フォールバック: %s", "有効" if enabled else "無効")

    # ── ヘルスチェック ──

    def init_health_checker(
        self,
        interval: float = 30.0,
        on_status_change: callable | None = None,
    ) -> HealthChecker:
        """ヘルスチェッカーを初期化する。"""
        all_providers: dict[str, BaseLLMProvider] = {}
        all_providers.update(self._cloud_providers)
        all_providers.update(self._local_providers)

        self._health_checker = HealthChecker(
            providers=all_providers,
            interval=interval,
            on_status_change=on_status_change or self._on_health_status_change,
        )
        return self._health_checker

    def _on_health_status_change(self, name, old_status, new_status) -> None:
        """ヘルスステータス変化時のデフォルトコールバック。"""
        logger.info(
            "ヘルスステータス変化 [%s]: %s → %s",
            name, old_status.status.value, new_status.status.value,
        )

        # クラウドプロバイダが UNHEALTHY になった場合、サーキットブレーカーに連動
        if (
            name in self._circuit_breakers
            and new_status.status == ProviderStatus.UNHEALTHY
        ):
            cb = self._circuit_breakers[name]
            cb.record_failure(
                error=new_status.error_message or "ヘルスチェック失敗",
            )

    # ── メイン呼び出し ──

    def call(self, request: LLMRequest) -> LLMResponse:
        """LLM 呼び出しを実行する。

        1. コスト上限チェック
        2. 優先モードのプロバイダで呼び出し
        3. 失敗時、auto_fallback が有効なら代替プロバイダで再試行
        """
        # コスト上限チェック
        within_limit, reason = self.cost_tracker.check_limits()
        if not within_limit:
            raise CostLimitExceededError(reason)

        # 優先モードに基づくプロバイダ解決
        if self._preferred_mode == ProviderType.CLOUD:
            return self._call_with_cloud_fallback(request)
        else:
            return self._call_with_local_fallback(request)

    def _call_with_cloud_fallback(self, request: LLMRequest) -> LLMResponse:
        """クラウド優先で呼び出し、失敗時はローカルへフォールバック。"""
        cloud_names = self._role_cloud_map.get(request.role, [])

        # クラウドプロバイダを順番に試行
        last_error: Exception | None = None
        for name in cloud_names:
            provider = self._cloud_providers[name]
            cb = self._circuit_breakers[name]

            if not cb.is_call_permitted:
                logger.info(
                    "サーキットOPEN: %s をスキップ (state=%s)",
                    name, cb.state.value,
                )
                continue

            try:
                response = provider.call(request)
                cb.record_success()
                self.cost_tracker.record(response)
                return response
            except Exception as e:
                last_error = e
                cb.record_failure(error=str(e))
                logger.warning(
                    "クラウドLLM呼び出し失敗 [%s]: %s → フォールバック候補を探索",
                    name, e,
                )

        # フォールバック: クラウドの代替プロバイダ（ADR-001 フォールバック順）
        for name in cloud_names:
            cb = self._circuit_breakers[name]
            if cb.is_call_permitted:
                provider = self._cloud_providers[name]
                try:
                    response = provider.call(request)
                    cb.record_success()
                    response.fallback_used = True
                    response.fallback_reason = f"主プロバイダ障害 → {name}でフォールバック"
                    self.cost_tracker.record(response)
                    return response
                except Exception as e:
                    cb.record_failure(error=str(e))

        # 自動フォールバック: ローカル LLM
        if self._auto_fallback_enabled:
            logger.warning(
                "全クラウドプロバイダ利用不可 → ローカルLLMへ自動フォールバック (role=%s)",
                request.role.value,
            )
            return self._call_local(request, fallback=True, fallback_reason="クラウドLLM全プロバイダ障害")

        raise CloudLLMUnavailableError(
            f"クラウドLLMが全て利用不可 (role={request.role.value}): {last_error}"
        )

    def _call_with_local_fallback(self, request: LLMRequest) -> LLMResponse:
        """ローカル優先で呼び出し、失敗時はクラウドへフォールバック。"""
        try:
            return self._call_local(request)
        except Exception as e:
            if self._auto_fallback_enabled:
                logger.warning(
                    "ローカルLLM利用不可 → クラウドLLMへフォールバック (role=%s): %s",
                    request.role.value, e,
                )
                return self._call_with_cloud_fallback(request)
            raise

    def _call_local(
        self,
        request: LLMRequest,
        fallback: bool = False,
        fallback_reason: str | None = None,
    ) -> LLMResponse:
        """ローカルプロバイダで呼び出す。"""
        local_names = self._role_local_map.get(request.role, [])

        # ロールに対応するローカルプロバイダがなければ全ローカルプロバイダから探す
        if not local_names:
            local_names = list(self._local_providers.keys())

        last_error: Exception | None = None
        for name in local_names:
            provider = self._local_providers[name]
            try:
                response = provider.call(request)
                response.fallback_used = fallback
                response.fallback_reason = fallback_reason
                self.cost_tracker.record(response)
                if fallback:
                    cb_names = self._role_cloud_map.get(request.role, [])
                    for cb_name in cb_names:
                        self._circuit_breakers[cb_name].record_fallback()
                return response
            except Exception as e:
                last_error = e
                logger.warning("ローカルLLM呼び出し失敗 [%s]: %s", name, e)

        raise LocalLLMUnavailableError(
            f"ローカルLLMが全て利用不可 (role={request.role.value}): {last_error}"
        )

    # ── ステータス ──

    def get_status(self) -> dict[str, Any]:
        """ゲートウェイの現在のステータスを返す。"""
        cloud_status = {}
        for name, cb in self._circuit_breakers.items():
            cloud_status[name] = {
                "circuit_state": cb.state.value,
                "consecutive_failures": cb.metrics.consecutive_failures,
                "total_fallbacks": cb.metrics.total_fallbacks,
            }

        local_status = {}
        if self._health_checker:
            for name in self._local_providers:
                hs = self._health_checker.get_status(name)
                local_status[name] = {
                    "status": hs.status.value if hs else "unknown",
                }

        return {
            "preferred_mode": self._preferred_mode.value,
            "auto_fallback_enabled": self._auto_fallback_enabled,
            "cloud_providers": cloud_status,
            "local_providers": local_status,
            "cost": {
                "daily_cost_usd": self.cost_tracker.daily_cost_usd,
                "cycle_cost_usd": self.cost_tracker.cycle_cost_usd,
                "daily_calls": self.cost_tracker.daily_calls,
                "cycle_calls": self.cost_tracker.cycle_calls,
            },
        }


# ============================================================
# 例外クラス
# ============================================================


class LLMGatewayError(Exception):
    """LLMゲートウェイの基底例外。"""


class CloudLLMUnavailableError(LLMGatewayError):
    """クラウドLLMが利用不可。"""


class LocalLLMUnavailableError(LLMGatewayError):
    """ローカルLLMが利用不可。"""


class CostLimitExceededError(LLMGatewayError):
    """コスト上限超過。"""
