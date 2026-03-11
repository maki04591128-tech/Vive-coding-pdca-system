"""モデル劣化検知 – 10サイクル連続観測・ペルソナ重み調整。

M3 タスク 3-6: 要件定義書 §26.8, ギャップB5 準拠。

- 10サイクル連続観測で劣化トレンドを検知
- ペルソナ重み調整（±0.05）はB操作扱い
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# --- モデル劣化検知のパラメータ ---
OBSERVATION_WINDOW = 10
WEIGHT_ADJUSTMENT_STEP = 0.05
MIN_WEIGHT = 0.1
MAX_WEIGHT = 2.0

# トレンド識別子
TREND_DEGRADING = "degrading"
TREND_STABLE = "stable"
TREND_IMPROVING = "improving"
TREND_INSUFFICIENT_DATA = "insufficient_data"
# ※ トレンド判定: 前半5サイクルと後半5サイクルの品質スコアを比較

# サイクル分析で除外するトレンド（調整不要）
_SKIP_TRENDS = frozenset({TREND_STABLE, TREND_INSUFFICIENT_DATA})


# モデル観測データ1件（サイクル番号・モデル名・品質スコア・エラー有無）
@dataclass
class ModelObservation:
    """モデル観測データ1件。"""

    cycle_number: int = 0
    model_name: str = ""
    persona_role: str = ""
    quality_score: float = 0.0  # 0.0〜1.0
    error_occurred: bool = False
    response_time_seconds: float = 0.0


@dataclass
class DegradationReport:
    """劣化レポート。"""

    model_name: str = ""
    persona_role: str = ""
    trend: str = ""  # "degrading", "stable", "improving"
    avg_quality: float = 0.0
    observation_count: int = 0
    recommended_weight_change: float = 0.0


@dataclass
class WeightAdjustmentResult:
    """ペルソナ重み調整結果（B操作）。"""

    persona_role: str = ""
    previous_weight: float = 1.0
    new_weight: float = 1.0
    adjustment: float = 0.0
    governance_level: str = "B"  # B操作扱い（§17.1）


# --- 劣化検知エンジン: 10サイクル連続観測で品質低下トレンドを自動検出 ---
class ModelDegradationDetector:
    """モデル劣化検知。

    10サイクル連続観測で品質トレンドを分析し、
    ペルソナ重みの調整を提案する。
    """

    def __init__(
        self,
        window_size: int = OBSERVATION_WINDOW,
        weight_step: float = WEIGHT_ADJUSTMENT_STEP,
    ) -> None:
        self._window_size = window_size
        self._weight_step = weight_step
        self._observations: dict[str, list[ModelObservation]] = {}
        self._persona_weights: dict[str, float] = {}

    @property
    def persona_weights(self) -> dict[str, float]:
        return dict(self._persona_weights)

    def record_observation(self, obs: ModelObservation) -> None:
        """観測データを記録する。"""
        key = f"{obs.model_name}:{obs.persona_role}"
        if key not in self._observations:
            self._observations[key] = []
        self._observations[key].append(obs)

        # ウィンドウサイズに制限
        if len(self._observations[key]) > self._window_size * 2:
            self._observations[key] = self._observations[key][-self._window_size * 2:]

    def analyze(self, model_name: str, persona_role: str) -> DegradationReport:
        """劣化を分析する。

        Parameters
        ----------
        model_name : str
            モデル名。
        persona_role : str
            ペルソナロール。

        Returns
        -------
        DegradationReport
            分析結果。
        """
        key = f"{model_name}:{persona_role}"
        observations = self._observations.get(key, [])

        if len(observations) < self._window_size:
            return DegradationReport(
                model_name=model_name,
                persona_role=persona_role,
                trend=TREND_INSUFFICIENT_DATA,
                observation_count=len(observations),
            )

        recent = observations[-self._window_size:]
        avg_quality = sum(o.quality_score for o in recent) / len(recent)

        # 前半と後半を比較
        half = len(recent) // 2
        first_half_avg = sum(
            o.quality_score for o in recent[:half]
        ) / max(half, 1)
        second_half_avg = sum(
            o.quality_score for o in recent[half:]
        ) / max(len(recent) - half, 1)

        # 前半と後半の品質スコア平均を比較し、劣化/安定/改善を判定
        diff = second_half_avg - first_half_avg

        if diff < -0.1:
            trend = TREND_DEGRADING
            weight_change = -self._weight_step
        elif diff > 0.1:
            trend = TREND_IMPROVING
            weight_change = self._weight_step
        else:
            trend = TREND_STABLE
            weight_change = 0.0

        return DegradationReport(
            model_name=model_name,
            persona_role=persona_role,
            trend=trend,
            avg_quality=avg_quality,
            observation_count=len(recent),
            recommended_weight_change=weight_change,
        )

    def apply_weight_adjustment(
        self,
        persona_role: str,
        adjustment: float,
    ) -> float:
        """ペルソナ重みを調整する（B操作扱い）。

        Parameters
        ----------
        persona_role : str
            ペルソナロール。
        adjustment : float
            調整値（±0.05）。

        Returns
        -------
        float
            調整後の重み。
        """
        current = self._persona_weights.get(persona_role, 1.0)
        new_weight = max(MIN_WEIGHT, min(MAX_WEIGHT, current + adjustment))
        self._persona_weights[persona_role] = new_weight

        logger.info(
            "ペルソナ重み調整: %s %.2f → %.2f (B操作)",
            persona_role, current, new_weight,
        )
        return new_weight

    def get_all_reports(self) -> list[DegradationReport]:
        """全モデル/ペルソナの劣化レポートを返す。"""
        reports: list[DegradationReport] = []
        for key in self._observations:
            parts = key.split(":", 1)
            if len(parts) != 2:
                logger.warning("不正なキー形式をスキップ: %s", key)
                continue
            model_name, persona_role = parts
            reports.append(self.analyze(model_name, persona_role))
        return reports

    def get_status(self) -> dict[str, Any]:
        """劣化検知状態を返す。"""
        return {
            "observed_models": len(self._observations),
            "persona_weights": dict(self._persona_weights),
            "window_size": self._window_size,
        }

    def run_cycle_analysis(self) -> list[DegradationReport]:
        """全モデル/ペルソナの劣化を一括分析する。

        §14「継続的改善スケジュール」に基づき、10サイクルごとに
        全ペルソナの品質トレンドを分析する。

        Returns
        -------
        list[DegradationReport]
            調整が推奨されるレポート（trend が stable 以外）のリスト。
        """
        reports = self.get_all_reports()
        return [r for r in reports if r.trend not in _SKIP_TRENDS]

    # ペルソナ重みを劣化/改善に応じて自動調整する（B操作＝バックアップ必須）
    def auto_adjust_weights(self) -> list[WeightAdjustmentResult]:
        """分析結果に基づきペルソナ重みを一括自動調整する（B操作）。

        run_cycle_analysis() の結果をもとに、劣化・改善が検出された
        ペルソナの重みを ±0.05 で調整する。

        Returns
        -------
        list[WeightAdjustmentResult]
            実行された調整結果のリスト。
        """
        reports = self.get_all_reports()
        results: list[WeightAdjustmentResult] = []

        for report in reports:
            if report.recommended_weight_change == 0.0:
                continue

            previous = self._persona_weights.get(report.persona_role, 1.0)
            new_weight = self.apply_weight_adjustment(
                report.persona_role,
                report.recommended_weight_change,
            )
            results.append(WeightAdjustmentResult(
                persona_role=report.persona_role,
                previous_weight=previous,
                new_weight=new_weight,
                adjustment=report.recommended_weight_change,
                governance_level="B",
            ))

        if results:
            logger.info(
                "ペルソナ重み一括調整完了: %d件 (B操作)",
                len(results),
            )

        return results
