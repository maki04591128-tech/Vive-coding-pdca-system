"""分析・レポーティングエンジンのテスト。"""

import pytest

from vibe_pdca.engine.analytics import (
    AnalyticsEngine,
    BottleneckInfo,
    CycleSummary,
    ReportExporter,
    ReportPeriod,
    TrendData,
)

# ============================================================
# テスト: ReportPeriod
# ============================================================


class TestReportPeriod:
    def test_enum_values(self):
        assert ReportPeriod.WEEKLY == "weekly"
        assert ReportPeriod.MONTHLY == "monthly"
        assert ReportPeriod.QUARTERLY == "quarterly"


# ============================================================
# テスト: CycleSummary
# ============================================================


class TestCycleSummary:
    def test_default_values(self):
        summary = CycleSummary(
            cycle_number=1,
            success=True,
            duration_seconds=120.0,
            cost_usd=0.05,
        )
        assert summary.cycle_number == 1
        assert summary.success is True
        assert summary.duration_seconds == 120.0
        assert summary.cost_usd == 0.05
        assert summary.phase_durations == {}

    def test_custom_values(self):
        phases = {"plan": 30.0, "do": 60.0, "check": 20.0, "act": 10.0}
        summary = CycleSummary(
            cycle_number=5,
            success=False,
            duration_seconds=300.0,
            cost_usd=1.25,
            phase_durations=phases,
        )
        assert summary.cycle_number == 5
        assert summary.success is False
        assert summary.duration_seconds == 300.0
        assert summary.cost_usd == 1.25
        assert summary.phase_durations == phases


# ============================================================
# テスト: TrendData
# ============================================================


class TestTrendData:
    def test_creation(self):
        trend = TrendData(
            period="2024-W01",
            success_rate=0.8,
            avg_cost=0.5,
            total_cycles=10,
            decisions=["方針A採用", "方針B棄却"],
        )
        assert trend.period == "2024-W01"
        assert trend.success_rate == 0.8
        assert trend.avg_cost == 0.5
        assert trend.total_cycles == 10
        assert trend.decisions == ["方針A採用", "方針B棄却"]

    def test_default_decisions(self):
        trend = TrendData(
            period="2024-Q1",
            success_rate=0.9,
            avg_cost=0.3,
            total_cycles=30,
        )
        assert trend.decisions == []


# ============================================================
# テスト: BottleneckInfo
# ============================================================


class TestBottleneckInfo:
    def test_creation(self):
        bn = BottleneckInfo(
            phase="do",
            avg_duration=45.0,
            failure_count=3,
            cost_concentration=0.6,
        )
        assert bn.phase == "do"
        assert bn.avg_duration == 45.0
        assert bn.failure_count == 3
        assert bn.cost_concentration == 0.6


# ============================================================
# テスト: AnalyticsEngine
# ============================================================


class TestAnalyticsEngine:
    def _make_engine_with_cycles(self) -> AnalyticsEngine:
        """テスト用のエンジンにサイクルデータを投入する。"""
        engine = AnalyticsEngine()
        engine.add_cycle(CycleSummary(
            cycle_number=1,
            success=True,
            duration_seconds=100.0,
            cost_usd=0.10,
            phase_durations={"plan": 20.0, "do": 50.0, "check": 30.0},
        ))
        engine.add_cycle(CycleSummary(
            cycle_number=2,
            success=False,
            duration_seconds=200.0,
            cost_usd=0.20,
            phase_durations={"plan": 40.0, "do": 100.0, "check": 60.0},
        ))
        engine.add_cycle(CycleSummary(
            cycle_number=3,
            success=True,
            duration_seconds=150.0,
            cost_usd=0.15,
            phase_durations={"plan": 30.0, "do": 80.0, "check": 40.0},
        ))
        return engine

    def test_add_cycle(self):
        engine = AnalyticsEngine()
        summary = CycleSummary(
            cycle_number=1,
            success=True,
            duration_seconds=60.0,
            cost_usd=0.01,
        )
        engine.add_cycle(summary)
        assert engine.get_success_rate(last_n=1) == 1.0

    def test_get_success_rate_empty(self):
        engine = AnalyticsEngine()
        assert engine.get_success_rate() == 0.0

    def test_get_success_rate(self):
        engine = self._make_engine_with_cycles()
        rate = engine.get_success_rate(last_n=10)
        assert rate == pytest.approx(2 / 3)

    def test_get_success_rate_with_last_n(self):
        engine = self._make_engine_with_cycles()
        rate = engine.get_success_rate(last_n=1)
        assert rate == 1.0

    def test_get_cost_trend(self):
        engine = self._make_engine_with_cycles()
        costs = engine.get_cost_trend(last_n=10)
        assert costs == [0.10, 0.20, 0.15]

    def test_get_cost_trend_with_last_n(self):
        engine = self._make_engine_with_cycles()
        costs = engine.get_cost_trend(last_n=2)
        assert costs == [0.20, 0.15]

    def test_detect_bottlenecks(self):
        engine = self._make_engine_with_cycles()
        bottlenecks = engine.detect_bottlenecks()
        assert len(bottlenecks) == 3
        # ボトルネックは平均所要時間の降順
        assert bottlenecks[0].phase == "do"
        assert bottlenecks[0].avg_duration == pytest.approx(
            (50.0 + 100.0 + 80.0) / 3
        )

    def test_detect_bottlenecks_empty(self):
        engine = AnalyticsEngine()
        assert engine.detect_bottlenecks() == []

    def test_detect_bottlenecks_empty_phase_durations(self):
        """phase_durationsが空のサイクルでもボトルネック検出が安全なこと。"""
        engine = AnalyticsEngine()
        engine.add_cycle(CycleSummary(
            cycle_number=1,
            success=True,
            duration_seconds=100.0,
            cost_usd=0.10,
            phase_durations={},
        ))
        assert engine.detect_bottlenecks() == []

    def test_generate_summary_report(self):
        engine = self._make_engine_with_cycles()
        report = engine.generate_summary_report(ReportPeriod.WEEKLY)
        assert "# サイクル分析レポート（weekly）" in report
        assert "総サイクル数: 3" in report
        assert "成功率: 66.7%" in report
        assert "ボトルネック分析" in report
        assert "コスト推移" in report

    def test_generate_summary_report_empty(self):
        engine = AnalyticsEngine()
        report = engine.generate_summary_report(ReportPeriod.MONTHLY)
        assert "総サイクル数: 0" in report
        assert "成功率: 0.0%" in report

    def test_custom_metrics_set_and_get(self):
        engine = AnalyticsEngine()
        engine.set_custom_metric("accuracy", 0.95)
        assert engine.get_custom_metric("accuracy") == 0.95

    def test_custom_metrics_missing_returns_none(self):
        engine = AnalyticsEngine()
        assert engine.get_custom_metric("unknown") is None


# ============================================================
# テスト: ReportExporter
# ============================================================


class TestReportExporter:
    def test_to_markdown(self):
        exporter = ReportExporter()
        report = "# テストレポート\n\n内容です。"
        result = exporter.to_markdown(report)
        assert result.startswith("---\nformat: markdown\n---\n")
        assert "# テストレポート" in result
        assert "内容です。" in result

    def test_to_dict(self):
        exporter = ReportExporter()
        summaries = [
            CycleSummary(
                cycle_number=1,
                success=True,
                duration_seconds=60.0,
                cost_usd=0.01,
            ),
            CycleSummary(
                cycle_number=2,
                success=False,
                duration_seconds=120.0,
                cost_usd=0.02,
                phase_durations={"plan": 50.0},
            ),
        ]
        result = exporter.to_dict(summaries)
        assert result["total_cycles"] == 2
        assert len(result["cycles"]) == 2
        assert result["cycles"][0]["cycle_number"] == 1
        assert result["cycles"][0]["success"] is True
        assert result["cycles"][1]["phase_durations"] == {"plan": 50.0}
