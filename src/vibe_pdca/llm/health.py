"""LLMプロバイダのヘルスチェック機構。

インターネット接続およびクラウドLLMの稼働状態を定期的に監視し、
障害検知時にサーキットブレーカーへ通知する。
§13.2 信頼性・SLO要件準拠。
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from vibe_pdca.llm.models import ProviderHealthStatus, ProviderStatus

if TYPE_CHECKING:
    from vibe_pdca.llm.providers import BaseLLMProvider

logger = logging.getLogger(__name__)


# --- ヘルスチェック: 各LLMプロバイダが正常に動作しているかを定期確認 ---
class HealthChecker:
    """LLMプロバイダのヘルスチェックを定期的に実行する。

    - インターネット接続の監視
    - 各クラウドLLMプロバイダのAPI疎通確認
    - ローカルLLMプロバイダの稼働確認
    - ヘルスステータスの集約・通知
    """

    DEFAULT_INTERVAL = 30.0   # ヘルスチェック間隔（秒）
    TIMEOUT_SECONDS = 10.0    # ヘルスチェック1回あたりのタイムアウト

    def __init__(
        self,
        providers: dict[str, BaseLLMProvider],
        interval: float = DEFAULT_INTERVAL,
        on_status_change: Callable[..., Any] | None = None,
    ) -> None:
        self._providers = providers
        self._interval = interval
        self._on_status_change = on_status_change
        self._statuses: dict[str, ProviderHealthStatus] = {}
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ── 公開 API ──

    @property
    def statuses(self) -> dict[str, ProviderHealthStatus]:
        """全プロバイダの最新ヘルスステータスを返す。"""
        return dict(self._statuses)

    def get_status(self, provider_name: str) -> ProviderHealthStatus | None:
        """特定プロバイダのヘルスステータスを返す。"""
        return self._statuses.get(provider_name)

    def check_all(self) -> dict[str, ProviderHealthStatus]:
        """全プロバイダのヘルスチェックを即座に実行する。"""
        # 各プロバイダに軽量なリクエストを送信し、応答があれば「正常」と判定
        results: dict[str, ProviderHealthStatus] = {}
        for name, provider in self._providers.items():
            result = self._check_provider(name, provider)
            old_status = self._statuses.get(name)
            self._statuses[name] = result
            results[name] = result

            # 状態変化コールバック
            if (
                self._on_status_change
                and old_status
                and old_status.status != result.status
            ):
                self._on_status_change(name, old_status, result)

        return results

    def check_internet_connectivity(self) -> bool:
        """インターネット接続の疎通を確認する。

        複数のエンドポイントに対して接続を試み、
        少なくとも1つに接続できれば True を返す。
        """
        import socket

        test_hosts = [
            ("8.8.8.8", 53),           # Google DNS
            ("1.1.1.1", 53),           # Cloudflare DNS
            ("api.openai.com", 443),   # OpenAI
            ("api.anthropic.com", 443),  # Anthropic
        ]

        for host, port in test_hosts:
            try:
                sock = socket.create_connection(
                    (host, port), timeout=5.0,
                )
                sock.close()
                return True
            except (OSError, TimeoutError):
                continue

        logger.warning("インターネット接続を確認できません")
        return False

    # ── バックグラウンド監視 ──

    def start_background(self) -> None:
        """バックグラウンドでの定期ヘルスチェックを開始する。"""
        if self._running:
            logger.warning("ヘルスチェックは既に実行中です")
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._background_loop,
            name="llm-health-checker",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "ヘルスチェックをバックグラウンドで開始しました (interval=%.1fs)",
            self._interval,
        )

    def stop_background(self) -> None:
        """バックグラウンドのヘルスチェックを停止する。"""
        if not self._running:
            return

        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=self._interval + 5)
            self._thread = None
        logger.info("ヘルスチェックを停止しました")

    # ── 内部ロジック ──

    def _background_loop(self) -> None:
        """定期ヘルスチェックのメインループ。"""
        while not self._stop_event.is_set():
            try:
                self.check_all()
            except Exception:
                logger.exception("ヘルスチェック中に予期しないエラー")
            self._stop_event.wait(timeout=self._interval)

    def _check_provider(
        self, name: str, provider: BaseLLMProvider,
    ) -> ProviderHealthStatus:
        """個別プロバイダのヘルスチェックを実行する。"""
        start = time.monotonic()
        try:
            is_healthy = provider.health_check()
            latency_ms = (time.monotonic() - start) * 1000

            old = self._statuses.get(name)
            consecutive_failures = 0 if is_healthy else (
                (old.consecutive_failures + 1) if old else 1
            )

            status = ProviderHealthStatus(
                provider_name=name,
                provider_type=provider.provider_type,
                status=ProviderStatus.HEALTHY if is_healthy else ProviderStatus.UNHEALTHY,
                latency_ms=latency_ms,
                last_checked_at=time.time(),
                consecutive_failures=consecutive_failures,
            )

            if is_healthy:
                logger.debug("ヘルスチェック OK: %s (%.1fms)", name, latency_ms)
            else:
                logger.warning(
                    "ヘルスチェック NG: %s (連続失敗: %d)",
                    name, consecutive_failures,
                )

            return status

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            old = self._statuses.get(name)
            consecutive_failures = (old.consecutive_failures + 1) if old else 1

            logger.error("ヘルスチェック例外: %s - %s", name, e)
            return ProviderHealthStatus(
                provider_name=name,
                provider_type=provider.provider_type,
                status=ProviderStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error_message=str(e),
                last_checked_at=time.time(),
                consecutive_failures=consecutive_failures,
            )
