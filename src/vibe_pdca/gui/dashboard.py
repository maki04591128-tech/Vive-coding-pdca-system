"""ダッシュボード拡張。

提案5: PDCAサイクルのタイムライン表示・コスト推移・
トレーサビリティリンク・レーダーチャート・アラート管理を提供する。

- タイムラインエントリによるフェーズ進行の可視化
- コストデータポイントの蓄積・履歴参照
- トレースリンクによるアーティファクト間の関連付け
- ペルソナ別レーダーチャートデータ
- アラート管理 (レベル別フィルタ)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── TimelineEntry ──


@dataclass
class TimelineEntry:
    """タイムラインのエントリ。

    Parameters
    ----------
    phase : str
        フェーズ名。
    start_time : float
        開始時刻 (epoch秒)。
    end_time : float | None
        終了時刻 (None=進行中)。
    status : str
        ステータス文字列。
    """

    phase: str
    start_time: float
    end_time: float | None = None
    status: str = "running"


# ── CostDataPoint ──


@dataclass
class CostDataPoint:
    """コストデータポイント。

    Parameters
    ----------
    timestamp : float
        記録時刻 (epoch秒)。
    cost_usd : float
        コスト (USD)。
    model : str
        使用モデル名。
    cycle_number : int
        サイクル番号。
    """

    timestamp: float
    cost_usd: float
    model: str
    cycle_number: int


# ── TraceLink ──


@dataclass
class TraceLink:
    """アーティファクト間のトレースリンク。

    Parameters
    ----------
    source_type : str
        ソース種別 (例: 'task', 'issue')。
    source_id : str
        ソースID。
    target_type : str
        ターゲット種別。
    target_id : str
        ターゲットID。
    """

    source_type: str
    source_id: str
    target_type: str
    target_id: str


# ── RadarChartData ──


@dataclass
class RadarChartData:
    """ペルソナ別レーダーチャートデータ。

    Parameters
    ----------
    persona : str
        ペルソナ名。
    scores : dict[str, float]
        評価軸ごとのスコア (0.0〜1.0)。
    """

    persona: str
    scores: dict[str, float] = field(default_factory=dict)


# ── AlertItem ──


@dataclass
class AlertItem:
    """アラート項目。

    Parameters
    ----------
    level : str
        アラートレベル (info, warning, error, critical)。
    message : str
        メッセージ本文。
    timestamp : float
        発生時刻 (epoch秒)。
    category : str
        カテゴリ文字列。
    """

    level: str
    message: str
    timestamp: float = field(default_factory=time.time)
    category: str = "general"


# ── DashboardState ──


class DashboardState:
    """ダッシュボードの状態管理。

    タイムライン・コスト履歴・アラート・レーダーチャートデータを
    集約して管理する。
    """

    def __init__(self) -> None:
        self._timeline: list[TimelineEntry] = []
        self._cost_history: list[CostDataPoint] = []
        self._alerts: list[AlertItem] = []
        self._radar_data: list[RadarChartData] = []

    def add_timeline_entry(self, entry: TimelineEntry) -> None:
        """タイムラインエントリを追加する。"""
        self._timeline.append(entry)
        logger.info(
            "タイムライン追加: phase=%s, status=%s",
            entry.phase,
            entry.status,
        )

    def add_cost_point(self, point: CostDataPoint) -> None:
        """コストデータポイントを追加する。"""
        self._cost_history.append(point)
        logger.info(
            "コスト記録: model=%s, cost=$%.4f",
            point.model,
            point.cost_usd,
        )

    def add_alert(self, alert: AlertItem) -> None:
        """アラートを追加する。"""
        self._alerts.append(alert)
        logger.info(
            "アラート追加: level=%s, message=%s",
            alert.level,
            alert.message[:50],
        )

    def add_radar_data(self, data: RadarChartData) -> None:
        """レーダーチャートデータを追加する。"""
        self._radar_data.append(data)
        logger.info(
            "レーダーデータ追加: persona=%s, axes=%d",
            data.persona,
            len(data.scores),
        )

    def get_timeline(self) -> list[TimelineEntry]:
        """タイムラインエントリの一覧を返す。"""
        return list(self._timeline)

    def get_cost_history(self) -> list[CostDataPoint]:
        """コスト履歴の一覧を返す。"""
        return list(self._cost_history)

    def get_alerts(
        self,
        level: str | None = None,
    ) -> list[AlertItem]:
        """アラートの一覧を返す。

        Parameters
        ----------
        level : str | None
            フィルタするレベル (None=全件)。
        """
        if level is None:
            return list(self._alerts)
        return [a for a in self._alerts if a.level == level]

    def get_persona_radar_data(self) -> list[RadarChartData]:
        """レーダーチャートデータの一覧を返す。"""
        return list(self._radar_data)

    def clear(self) -> None:
        """全データをクリアする。"""
        self._timeline.clear()
        self._cost_history.clear()
        self._alerts.clear()
        self._radar_data.clear()
        logger.info("ダッシュボード状態をクリア")
