"""レート制限とスロットリング。

提案3: LLMプロバイダ別のレート制限・トークンバケット・
指数バックオフによるリクエスト制御を提供する。

- プロバイダ別リクエスト/トークン制限
- トークンバケットアルゴリズムによる流量制御
- 指数バックオフによるリトライ間隔計算
- 利用状況のダッシュボード表示
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ── RateLimitConfig ──


# AIサービスへのリクエスト頻度を制限する設定（過剰なAPI呼び出しを防止）
@dataclass
class RateLimitConfig:
    """プロバイダ別レート制限設定。

    Parameters
    ----------
    provider : str
        プロバイダ名。
    requests_per_minute : int
        1分あたりの最大リクエスト数。
    tokens_per_minute : int
        1分あたりの最大トークン数。
    burst_size : int
        バーストサイズ (デフォルト10)。
    """

    provider: str
    requests_per_minute: int
    tokens_per_minute: int
    burst_size: int = 10


# ── TokenBucket ──


# --- トークンバケット: 「バケツに水が溜まる速度」でリクエスト頻度を制御 ---
# バケツが空になったらリクエストを待機させ、一定速度で補充される
class TokenBucket:
    """トークンバケットアルゴリズムによる流量制御。

    Parameters
    ----------
    capacity : int
        バケットの最大容量。
    rate : float
        1秒あたりの補充レート。
    """

    def __init__(self, capacity: int, rate: float) -> None:
        self._capacity = capacity
        self._rate = rate
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        """経過時間に基づいてトークンを補充する。"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self._capacity,
            self._tokens + elapsed * self._rate,
        )
        self._last_refill = now

    @property
    def available(self) -> float:
        """利用可能なトークン数を返す。"""
        self._refill()
        return self._tokens

    def consume(self, n: int = 1) -> bool:
        """トークンを消費する。

        Parameters
        ----------
        n : int
            消費するトークン数 (デフォルト1)。

        Returns
        -------
        bool
            消費に成功した場合True。
        """
        self._refill()
        if self._tokens >= n:
            self._tokens -= n
            return True
        logger.info(
            "トークン不足: 要求=%d, 残り=%.1f",
            n,
            self._tokens,
        )
        return False

    def reset(self) -> None:
        """バケットを最大容量にリセットする。"""
        self._tokens = float(self._capacity)
        self._last_refill = time.monotonic()


# ── RateLimitTracker ──


# --- レート制限マネージャー: プロバイダ別にリクエスト頻度を一元管理 ---
class RateLimitTracker:
    """プロバイダ別レート制限の追跡と制御。"""

    def __init__(self) -> None:
        self._configs: dict[str, RateLimitConfig] = {}
        self._buckets: dict[str, TokenBucket] = {}

    def add_provider(self, config: RateLimitConfig) -> None:
        """プロバイダのレート制限設定を追加する。"""
        self._configs[config.provider] = config
        rate = config.requests_per_minute / 60.0
        self._buckets[config.provider] = TokenBucket(
            capacity=config.burst_size,
            rate=rate,
        )
        logger.info(
            "プロバイダ追加: %s (rpm=%d, tpm=%d)",
            config.provider,
            config.requests_per_minute,
            config.tokens_per_minute,
        )

    def check(self, provider: str, tokens: int = 1) -> bool:
        """リクエスト送信可否を判定し、可能なら消費する。

        Parameters
        ----------
        provider : str
            プロバイダ名。
        tokens : int
            消費するトークン数。

        Returns
        -------
        bool
            送信可能な場合True。
        """
        bucket = self._buckets.get(provider)
        if bucket is None:
            logger.warning("未登録プロバイダ: %s", provider)
            return False
        return bucket.consume(tokens)

    def wait_time(self, provider: str) -> float:
        """次にリクエスト可能になるまでの待機時間 (秒) を返す。

        Returns
        -------
        float
            待機秒数。プロバイダ未登録の場合0.0。
        """
        bucket = self._buckets.get(provider)
        if bucket is None:
            return 0.0
        if bucket.available >= 1.0:
            return 0.0
        config = self._configs[provider]
        rate = config.requests_per_minute / 60.0
        if rate <= 0:
            return 0.0
        deficit = 1.0 - bucket.available
        return deficit / rate

    def get_usage(self, provider: str) -> dict[str, object]:
        """プロバイダの利用状況を返す。

        Returns
        -------
        dict
            available, capacity, provider を含む辞書。
        """
        bucket = self._buckets.get(provider)
        config = self._configs.get(provider)
        if bucket is None or config is None:
            return {"provider": provider, "available": 0, "capacity": 0}
        return {
            "provider": provider,
            "available": bucket.available,
            "capacity": config.burst_size,
        }

    def get_provider_names(self) -> list[str]:
        """登録済みプロバイダ名の一覧を返す。"""
        return list(self._configs.keys())


# ── BackoffStrategy ──


class BackoffStrategy:
    """指数バックオフによるリトライ間隔計算。

    Parameters
    ----------
    max_attempts : int
        最大リトライ回数 (デフォルト5)。
    base_delay : float
        基本待機時間 (秒, デフォルト1.0)。
    """

    def __init__(
        self,
        max_attempts: int = 5,
        base_delay: float = 1.0,
    ) -> None:
        self._max_attempts = max_attempts
        self._base_delay = base_delay

    @property
    def max_attempts(self) -> int:
        """最大リトライ回数を返す。"""
        return self._max_attempts

    @property
    def base_delay(self) -> float:
        """基本待機時間を返す。"""
        return self._base_delay

    # 指数バックオフ: エラー時の再試行間隔を 1秒→2秒→4秒... と倍々に増やす
    def calculate(self, attempt: int) -> float:
        """指数バックオフの待機時間を計算する。

        Parameters
        ----------
        attempt : int
            現在の試行回数 (1-indexed)。

        Returns
        -------
        float
            待機時間 (秒)。max_attempts超過時は-1.0。
        """
        if attempt > self._max_attempts:
            return -1.0
        return float(self._base_delay * (2 ** (attempt - 1)))


# ── RateLimitDashboard ──


class RateLimitDashboard:
    """レート制限の利用状況ダッシュボード。

    Parameters
    ----------
    tracker : RateLimitTracker
        追跡対象のトラッカー。
    """

    def __init__(self, tracker: RateLimitTracker) -> None:
        self._tracker = tracker

    def get_status(self) -> dict[str, object]:
        """全プロバイダのステータスを返す。"""
        providers = self.get_all_providers()
        statuses: dict[str, object] = {}
        for p in providers:
            statuses[p] = self._tracker.get_usage(p)
        return statuses

    def get_all_providers(self) -> list[str]:
        """登録済みプロバイダ名の一覧を返す。"""
        return self._tracker.get_provider_names()

    def get_utilization(self, provider: str) -> float:
        """プロバイダの利用率を返す (0.0〜1.0)。

        Returns
        -------
        float
            利用率。未登録プロバイダの場合0.0。
        """
        usage = self._tracker.get_usage(provider)
        capacity = usage.get("capacity", 0)
        if not capacity:
            return 0.0
        available = usage.get("available", 0)
        cap = float(capacity)  # type: ignore[arg-type]
        avail = float(available)  # type: ignore[arg-type]
        return 1.0 - (avail / cap) if cap > 0 else 0.0
