"""サーキットブレーカー実装。

クラウドLLM障害時の自動ローカルLLMフォールバックを制御する。
ADR-001 フォールバック順、§13.2 縮退モード準拠。

状態遷移:
  CLOSED (正常) ──(連続失敗 >= threshold)──→ OPEN (遮断)
  OPEN ──(recovery_timeout 経過)──→ HALF_OPEN (試行)
  HALF_OPEN ──(成功)──→ CLOSED
  HALF_OPEN ──(失敗)──→ OPEN
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """サーキットブレーカーの状態。"""

    CLOSED = "closed"          # 正常: クラウドLLMへリクエスト送信
    OPEN = "open"              # 遮断: クラウドLLM呼び出しを停止し、ローカルへフォールバック
    HALF_OPEN = "half_open"    # 半開: クラウドLLMへ試行リクエストを1件送信


@dataclass
class CircuitBreakerConfig:
    """サーキットブレーカーの設定。"""

    failure_threshold: int = 3          # OPEN へ遷移する連続失敗回数
    recovery_timeout: float = 60.0      # OPEN→HALF_OPEN の待機秒数
    success_threshold: int = 2          # HALF_OPEN→CLOSED に必要な連続成功回数
    half_open_max_calls: int = 1        # HALF_OPEN 中の最大同時試行数


@dataclass
class CircuitBreakerMetrics:
    """サーキットブレーカーの計測値。"""

    total_calls: int = 0
    total_failures: int = 0
    total_fallbacks: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    state_changes: list[dict[str, Any]] = field(default_factory=list)


class CircuitBreaker:
    """クラウドLLM 用サーキットブレーカー。

    連続失敗がしきい値に達するとサーキットを OPEN にし、
    ローカルLLMへの自動フォールバックを誘発する。
    一定時間後に HALF_OPEN で復旧を試行する。
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._metrics = CircuitBreakerMetrics()
        self._last_open_time: float = 0.0
        self._half_open_calls: int = 0
        self._lock = threading.Lock()

    # ── プロパティ ──

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._evaluate_state_transition()
            return self._state

    @property
    def metrics(self) -> CircuitBreakerMetrics:
        return self._metrics

    @property
    def is_call_permitted(self) -> bool:
        """現在の状態でクラウドLLM呼び出しが許可されるか。"""
        with self._lock:
            self._evaluate_state_transition()
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.HALF_OPEN:
                return self._half_open_calls < self.config.half_open_max_calls
            return False  # OPEN

    # ── 結果記録 ──

    def record_success(self) -> None:
        """呼び出し成功を記録する。"""
        with self._lock:
            self._metrics.total_calls += 1
            self._metrics.consecutive_failures = 0
            self._metrics.consecutive_successes += 1
            self._metrics.last_success_time = time.monotonic()

            if (
                self._state == CircuitState.HALF_OPEN
                and self._metrics.consecutive_successes >= self.config.success_threshold
            ):
                self._transition_to(CircuitState.CLOSED)
                self._half_open_calls = 0

            logger.debug(
                "CircuitBreaker[%s] 成功記録: state=%s, consecutive_successes=%d",
                self.name, self._state.value, self._metrics.consecutive_successes,
            )

    def record_failure(self, error: str = "") -> None:
        """呼び出し失敗を記録する。"""
        with self._lock:
            self._metrics.total_calls += 1
            self._metrics.total_failures += 1
            self._metrics.consecutive_failures += 1
            self._metrics.consecutive_successes = 0
            self._metrics.last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
                self._half_open_calls = 0
            elif self._state == CircuitState.CLOSED:
                if self._metrics.consecutive_failures >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

            logger.warning(
                "CircuitBreaker[%s] 失敗記録: state=%s, consecutive_failures=%d, error=%s",
                self.name, self._state.value, self._metrics.consecutive_failures, error,
            )

    def record_fallback(self) -> None:
        """フォールバック発生を記録する。"""
        self._metrics.total_fallbacks += 1

    # ── 手動制御 ──

    def force_open(self, reason: str = "") -> None:
        """手動でサーキットを OPEN にする（縮退モード移行時など）。"""
        with self._lock:
            self._transition_to(CircuitState.OPEN)
            logger.info(
                "CircuitBreaker[%s] 手動OPEN: reason=%s", self.name, reason,
            )

    def force_close(self, reason: str = "") -> None:
        """手動でサーキットを CLOSED にする（障害復旧確認後）。"""
        with self._lock:
            self._metrics.consecutive_failures = 0
            self._metrics.consecutive_successes = 0
            self._transition_to(CircuitState.CLOSED)
            logger.info(
                "CircuitBreaker[%s] 手動CLOSED: reason=%s", self.name, reason,
            )

    def reset_metrics(self) -> None:
        """メトリクスをリセットする。"""
        with self._lock:
            self._metrics = CircuitBreakerMetrics()

    # ── 内部ロジック ──

    def _evaluate_state_transition(self) -> None:
        """時間経過による OPEN→HALF_OPEN 自動遷移を評価する。"""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_open_time
            if elapsed >= self.config.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                self._half_open_calls = 0
                self._metrics.consecutive_successes = 0

    def _transition_to(self, new_state: CircuitState) -> None:
        """状態遷移を実行し記録する。"""
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state
        now = time.monotonic()

        if new_state == CircuitState.OPEN:
            self._last_open_time = now

        self._metrics.state_changes.append({
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": now,
        })

        logger.info(
            "CircuitBreaker[%s] 状態遷移: %s → %s",
            self.name, old_state.value, new_state.value,
        )
