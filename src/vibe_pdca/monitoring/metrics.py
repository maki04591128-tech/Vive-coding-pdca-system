"""可観測性 – メトリクス収集・アラート・ダッシュボードデータ。

M3 タスク 3-2: 要件定義書 §14 準拠。

メトリクス（§14.1）:
  サイクル成功率・平均サイクル時間・CI成功率・ブロッカー件数
  モデル別トークン / コスト / エラー率

アラート（§14.3）:
  停止条件発火時・CI連続失敗時・コスト急増時

ダッシュボード（§14.4）:
  現在の目標・進捗・未解決ブロッカーを常時可視化
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


# アラートの深刻度: critical(即対応) > warning(注意) > info(参考情報)
class AlertSeverity(StrEnum):
    """アラート重大度。"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(StrEnum):
    """アラート種別。"""

    STOP_CONDITION = "stop_condition"
    CI_FAILURE = "ci_failure"
    COST_SPIKE = "cost_spike"
    COST_LIMIT = "cost_limit"
    STACK_DETECTED = "stack_detected"
    INTEGRITY_ERROR = "integrity_error"


@dataclass
class Alert:
    """アラート1件。"""

    alert_type: AlertType
    severity: AlertSeverity
    message: str
    detail: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False


@dataclass
class CycleMetrics:
    """1サイクルのメトリクス。"""

    cycle_number: int = 0
    duration_seconds: float = 0.0
    success: bool = False
    ci_passed: bool = False
    blocker_count: int = 0
    llm_calls: int = 0
    llm_tokens: int = 0
    llm_cost_usd: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ModelMetrics:
    """モデル別メトリクス。"""

    model_name: str = ""
    total_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    error_count: int = 0

    @property
    def error_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.error_count / self.total_calls


@dataclass
class DashboardData:
    """ダッシュボード表示用データ。"""

    current_goal: str = ""
    progress_percent: float = 0.0
    total_cycles: int = 0
    successful_cycles: int = 0
    unresolved_blockers: int = 0
    daily_cost_usd: float = 0.0
    model_metrics: list[ModelMetrics] = field(default_factory=list)
    recent_alerts: list[Alert] = field(default_factory=list)


# --- メトリクス収集: サイクル実行時間・コスト・品質などの測定値を記録 ---
class MetricsCollector:
    """メトリクス収集・アラート管理。"""

    def __init__(self) -> None:
        self._cycle_metrics: list[CycleMetrics] = []
        self._model_metrics: dict[str, ModelMetrics] = {}
        self._alerts: list[Alert] = []
        self._lock = threading.Lock()

    @property
    def cycle_count(self) -> int:
        with self._lock:
            return len(self._cycle_metrics)

    @property
    def alert_count(self) -> int:
        with self._lock:
            return len(self._alerts)

    def record_cycle(self, metrics: CycleMetrics) -> None:
        """サイクルメトリクスを記録する。"""
        with self._lock:
            self._cycle_metrics.append(metrics)

    def record_model_usage(
        self,
        model_name: str,
        calls: int = 1,
        tokens: int = 0,
        cost_usd: float = 0.0,
        error: bool = False,
    ) -> None:
        """モデル別使用量を記録する。"""
        with self._lock:
            if model_name not in self._model_metrics:
                self._model_metrics[model_name] = ModelMetrics(
                    model_name=model_name,
                )
            m = self._model_metrics[model_name]
            m.total_calls += calls
            m.total_tokens += tokens
            m.total_cost_usd += cost_usd
            if error:
                m.error_count += 1

    def raise_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> Alert:
        """アラートを発行する。"""
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            detail=detail or {},
        )
        with self._lock:
            self._alerts.append(alert)
        logger.warning("アラート発行: [%s] %s", severity.value, message)
        return alert

    def get_cycle_success_rate(self) -> float:
        """サイクル成功率を返す。"""
        with self._lock:
            if not self._cycle_metrics:
                return 0.0
            successes = sum(1 for m in self._cycle_metrics if m.success)
            return successes / len(self._cycle_metrics)

    def get_average_cycle_time(self) -> float:
        """平均サイクル時間（秒）を返す。"""
        with self._lock:
            if not self._cycle_metrics:
                return 0.0
            total = sum(m.duration_seconds for m in self._cycle_metrics)
            return total / len(self._cycle_metrics)

    def get_ci_success_rate(self) -> float:
        """CI成功率を返す。"""
        with self._lock:
            if not self._cycle_metrics:
                return 0.0
            passed = sum(1 for m in self._cycle_metrics if m.ci_passed)
            return passed / len(self._cycle_metrics)

    def get_unresolved_blockers(self) -> int:
        """直近サイクルの未解決ブロッカー数を返す。"""
        with self._lock:
            if not self._cycle_metrics:
                return 0
            return self._cycle_metrics[-1].blocker_count

    def get_dashboard_data(
        self,
        current_goal: str = "",
        progress_percent: float = 0.0,
    ) -> DashboardData:
        """ダッシュボード用データを構築する。"""
        with self._lock:
            return DashboardData(
                current_goal=current_goal,
                progress_percent=progress_percent,
                total_cycles=len(self._cycle_metrics),
                successful_cycles=sum(
                    1 for m in self._cycle_metrics if m.success
                ),
                unresolved_blockers=(
                    self._cycle_metrics[-1].blocker_count
                    if self._cycle_metrics else 0
                ),
                daily_cost_usd=sum(
                    m.llm_cost_usd for m in self._cycle_metrics
                ),
                model_metrics=list(self._model_metrics.values()),
                recent_alerts=self._alerts[-10:],
            )

    def get_unacknowledged_alerts(self) -> list[Alert]:
        """未確認アラートを返す。"""
        with self._lock:
            return [a for a in self._alerts if not a.acknowledged]

    def acknowledge_alert(self, index: int) -> bool:
        """アラートを確認済みにする。"""
        with self._lock:
            if 0 <= index < len(self._alerts):
                self._alerts[index].acknowledged = True
                return True
            return False

    def get_status(self) -> dict[str, Any]:
        """可観測性の状態を返す。"""
        with self._lock:
            return {
                "cycle_count": len(self._cycle_metrics),
                "cycle_success_rate": (
                    sum(1 for m in self._cycle_metrics if m.success)
                    / len(self._cycle_metrics)
                    if self._cycle_metrics else 0.0
                ),
                "average_cycle_time": (
                    sum(m.duration_seconds for m in self._cycle_metrics)
                    / len(self._cycle_metrics)
                    if self._cycle_metrics else 0.0
                ),
                "ci_success_rate": (
                    sum(1 for m in self._cycle_metrics if m.ci_passed)
                    / len(self._cycle_metrics)
                    if self._cycle_metrics else 0.0
                ),
                "alert_count": len(self._alerts),
                "model_count": len(self._model_metrics),
            }
