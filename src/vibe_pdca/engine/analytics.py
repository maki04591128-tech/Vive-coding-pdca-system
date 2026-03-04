"""分析・レポーティングエンジン。

提案11: サイクルメトリクスの集計、トレンド分析、ボトルネック検出、
レポート生成を提供する。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


# ── ReportPeriod ──


class ReportPeriod(StrEnum):
    """レポート集計期間。"""

    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


# ── CycleSummary ──


@dataclass
class CycleSummary:
    """単一サイクルの実行サマリー。

    Parameters
    ----------
    cycle_number : int
        サイクル番号。
    success : bool
        サイクルが成功したかどうか。
    duration_seconds : float
        サイクル全体の所要時間（秒）。
    cost_usd : float
        サイクルの実行コスト（USD）。
    phase_durations : dict[str, float]
        フェーズ名をキー、所要時間（秒）を値とする辞書。
    """

    cycle_number: int
    success: bool
    duration_seconds: float
    cost_usd: float
    phase_durations: dict[str, float] = field(default_factory=dict)


# ── TrendData ──


@dataclass
class TrendData:
    """トレンド分析データ。

    Parameters
    ----------
    period : str
        集計期間の識別子（例: "2024-W01"）。
    success_rate : float
        成功率（0.0〜1.0）。
    avg_cost : float
        平均コスト（USD）。
    total_cycles : int
        サイクル総数。
    decisions : list[str]
        期間中の意思決定リスト。
    """

    period: str
    success_rate: float
    avg_cost: float
    total_cycles: int
    decisions: list[str] = field(default_factory=list)


# ── BottleneckInfo ──


@dataclass
class BottleneckInfo:
    """ボトルネック検出結果。

    Parameters
    ----------
    phase : str
        ボトルネックとなったフェーズ名。
    avg_duration : float
        平均所要時間（秒）。
    failure_count : int
        失敗回数。
    cost_concentration : float
        コスト集中度（0.0〜1.0）。
    """

    phase: str
    avg_duration: float
    failure_count: int
    cost_concentration: float


# ── AnalyticsEngine ──


class AnalyticsEngine:
    """サイクルメトリクスの集計・分析エンジン。"""

    def __init__(self) -> None:
        self._cycles: list[CycleSummary] = []
        self._custom_metrics: dict[str, float] = {}

    def add_cycle(self, summary: CycleSummary) -> None:
        """サイクルサマリーを追加する。

        Parameters
        ----------
        summary : CycleSummary
            追加するサイクルサマリー。
        """
        self._cycles.append(summary)
        logger.info("サイクル %d を追加しました", summary.cycle_number)

    def get_success_rate(self, last_n: int = 10) -> float:
        """直近 N サイクルの成功率を算出する。

        Parameters
        ----------
        last_n : int
            対象サイクル数（デフォルト 10）。

        Returns
        -------
        float
            成功率（0.0〜1.0）。サイクルが無い場合は 0.0。
        """
        if not self._cycles:
            return 0.0
        target = self._cycles[-last_n:]
        successes = sum(1 for c in target if c.success)
        return successes / len(target)

    def get_cost_trend(self, last_n: int = 10) -> list[float]:
        """直近 N サイクルのコスト推移を返す。

        Parameters
        ----------
        last_n : int
            対象サイクル数（デフォルト 10）。

        Returns
        -------
        list[float]
            コスト（USD）のリスト。古い順。
        """
        target = self._cycles[-last_n:]
        return [c.cost_usd for c in target]

    def detect_bottlenecks(self) -> list[BottleneckInfo]:
        """全サイクルのフェーズ所要時間を集計しボトルネックを検出する。

        Returns
        -------
        list[BottleneckInfo]
            平均所要時間の降順でソートされたボトルネック情報リスト。
        """
        if not self._cycles:
            return []

        phase_durations: dict[str, list[float]] = defaultdict(list)
        phase_failures: dict[str, int] = defaultdict(int)
        phase_costs: dict[str, float] = defaultdict(float)

        for cycle in self._cycles:
            for phase, dur in cycle.phase_durations.items():
                phase_durations[phase].append(dur)
                if not cycle.success:
                    phase_failures[phase] += 1
                ratio = len(cycle.phase_durations)
                if ratio > 0:
                    phase_costs[phase] += cycle.cost_usd / ratio

        total_cost = sum(phase_costs.values()) or 1.0

        bottlenecks: list[BottleneckInfo] = []
        for phase, durations in phase_durations.items():
            avg_dur = sum(durations) / len(durations)
            bottlenecks.append(
                BottleneckInfo(
                    phase=phase,
                    avg_duration=avg_dur,
                    failure_count=phase_failures[phase],
                    cost_concentration=phase_costs[phase] / total_cost,
                )
            )

        bottlenecks.sort(key=lambda b: b.avg_duration, reverse=True)
        return bottlenecks

    def generate_summary_report(self, period: ReportPeriod) -> str:
        """指定期間のサマリーレポートをMarkdown形式で生成する。

        Parameters
        ----------
        period : ReportPeriod
            レポート対象期間。

        Returns
        -------
        str
            Markdown 形式のレポート文字列。
        """
        total = len(self._cycles)
        success_rate = self.get_success_rate(total) if total else 0.0
        costs = self.get_cost_trend(total)
        avg_cost = sum(costs) / len(costs) if costs else 0.0
        total_cost = sum(costs)
        bottlenecks = self.detect_bottlenecks()

        lines: list[str] = [
            f"# サイクル分析レポート（{period.value}）",
            "",
            "## 概要",
            "",
            f"- 総サイクル数: {total}",
            f"- 成功率: {success_rate:.1%}",
            f"- 平均コスト: ${avg_cost:.4f}",
            f"- 合計コスト: ${total_cost:.4f}",
            "",
        ]

        if bottlenecks:
            lines.append("## ボトルネック分析")
            lines.append("")
            lines.append(
                "| フェーズ | 平均所要時間(秒) | 失敗回数 | コスト集中度 |"
            )
            lines.append("|---|---|---|---|")
            for bn in bottlenecks:
                lines.append(
                    f"| {bn.phase} "
                    f"| {bn.avg_duration:.2f} "
                    f"| {bn.failure_count} "
                    f"| {bn.cost_concentration:.1%} |"
                )
            lines.append("")

        lines.append("## コスト推移")
        lines.append("")
        for i, cost in enumerate(costs, 1):
            lines.append(f"- サイクル {i}: ${cost:.4f}")
        lines.append("")

        return "\n".join(lines)

    def get_custom_metric(self, name: str) -> float | None:
        """カスタムメトリクスの値を取得する。

        Parameters
        ----------
        name : str
            メトリクス名。

        Returns
        -------
        float | None
            メトリクスの値。未設定の場合は None。
        """
        return self._custom_metrics.get(name)

    def set_custom_metric(self, name: str, value: float) -> None:
        """カスタムメトリクスの値を設定する。

        Parameters
        ----------
        name : str
            メトリクス名。
        value : float
            設定する値。
        """
        self._custom_metrics[name] = value
        logger.debug("カスタムメトリクス '%s' = %f", name, value)


# ── ReportExporter ──


class ReportExporter:
    """レポートのエクスポートユーティリティ。"""

    def to_markdown(self, report: str) -> str:
        """レポート文字列をMarkdownドキュメントとして整形する。

        Parameters
        ----------
        report : str
            整形対象のレポート文字列。

        Returns
        -------
        str
            Markdownドキュメント文字列。
        """
        lines = [
            "---",
            "format: markdown",
            "---",
            "",
            report,
        ]
        return "\n".join(lines)

    def to_dict(self, summaries: list[CycleSummary]) -> dict:
        """サイクルサマリーのリストを辞書形式に変換する。

        Parameters
        ----------
        summaries : list[CycleSummary]
            変換対象のサマリーリスト。

        Returns
        -------
        dict
            サマリーデータを含む辞書。
        """
        return {
            "total_cycles": len(summaries),
            "cycles": [asdict(s) for s in summaries],
        }
