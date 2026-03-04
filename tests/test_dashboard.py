"""ダッシュボード拡張のテスト。"""

from __future__ import annotations

from vibe_pdca.gui.dashboard import (
    AlertItem,
    CostDataPoint,
    DashboardState,
    RadarChartData,
    TimelineEntry,
    TraceLink,
)

# ── TimelineEntry ──


class TestTimelineEntry:
    """TimelineEntryデータクラスのテスト。"""

    def test_defaults(self) -> None:
        entry = TimelineEntry(phase="plan", start_time=1000.0)
        assert entry.end_time is None
        assert entry.status == "running"

    def test_custom(self) -> None:
        entry = TimelineEntry(
            phase="do",
            start_time=1000.0,
            end_time=2000.0,
            status="completed",
        )
        assert entry.phase == "do"
        assert entry.end_time == 2000.0


# ── CostDataPoint ──


class TestCostDataPoint:
    """CostDataPointデータクラスのテスト。"""

    def test_fields(self) -> None:
        pt = CostDataPoint(
            timestamp=1000.0,
            cost_usd=0.05,
            model="gpt-4",
            cycle_number=1,
        )
        assert pt.cost_usd == 0.05
        assert pt.model == "gpt-4"
        assert pt.cycle_number == 1


# ── TraceLink ──


class TestTraceLink:
    """TraceLinkデータクラスのテスト。"""

    def test_fields(self) -> None:
        link = TraceLink(
            source_type="task",
            source_id="T-1",
            target_type="issue",
            target_id="I-1",
        )
        assert link.source_type == "task"
        assert link.target_id == "I-1"


# ── RadarChartData ──


class TestRadarChartData:
    """RadarChartDataデータクラスのテスト。"""

    def test_defaults(self) -> None:
        data = RadarChartData(persona="architect")
        assert data.scores == {}

    def test_with_scores(self) -> None:
        data = RadarChartData(
            persona="reviewer",
            scores={"quality": 0.9, "speed": 0.7},
        )
        assert data.scores["quality"] == 0.9
        assert len(data.scores) == 2


# ── AlertItem ──


class TestAlertItem:
    """AlertItemデータクラスのテスト。"""

    def test_defaults(self) -> None:
        alert = AlertItem(level="warning", message="テスト")
        assert alert.category == "general"
        assert alert.timestamp > 0

    def test_custom(self) -> None:
        alert = AlertItem(
            level="error",
            message="障害発生",
            timestamp=999.0,
            category="infra",
        )
        assert alert.level == "error"
        assert alert.category == "infra"


# ── DashboardState ──


class TestDashboardState:
    """DashboardStateのテスト。"""

    def _make_state(self) -> DashboardState:
        return DashboardState()

    def test_add_timeline_entry(self) -> None:
        state = self._make_state()
        entry = TimelineEntry(phase="plan", start_time=1000.0)
        state.add_timeline_entry(entry)
        assert len(state.get_timeline()) == 1

    def test_get_timeline_returns_copy(self) -> None:
        state = self._make_state()
        state.add_timeline_entry(
            TimelineEntry(phase="plan", start_time=1000.0),
        )
        tl = state.get_timeline()
        tl.clear()
        assert len(state.get_timeline()) == 1

    def test_add_cost_point(self) -> None:
        state = self._make_state()
        pt = CostDataPoint(
            timestamp=1000.0,
            cost_usd=0.1,
            model="gpt-4",
            cycle_number=1,
        )
        state.add_cost_point(pt)
        assert len(state.get_cost_history()) == 1

    def test_add_alert(self) -> None:
        state = self._make_state()
        state.add_alert(AlertItem(level="info", message="テスト"))
        assert len(state.get_alerts()) == 1

    def test_get_alerts_filtered(self) -> None:
        state = self._make_state()
        state.add_alert(AlertItem(level="info", message="情報"))
        state.add_alert(AlertItem(level="error", message="障害"))
        state.add_alert(AlertItem(level="info", message="情報2"))
        assert len(state.get_alerts(level="info")) == 2
        assert len(state.get_alerts(level="error")) == 1

    def test_get_alerts_no_filter(self) -> None:
        state = self._make_state()
        state.add_alert(AlertItem(level="info", message="a"))
        state.add_alert(AlertItem(level="error", message="b"))
        assert len(state.get_alerts()) == 2

    def test_add_radar_data(self) -> None:
        state = self._make_state()
        state.add_radar_data(
            RadarChartData(
                persona="arch",
                scores={"q": 0.8},
            ),
        )
        assert len(state.get_persona_radar_data()) == 1

    def test_clear(self) -> None:
        state = self._make_state()
        state.add_timeline_entry(
            TimelineEntry(phase="plan", start_time=1.0),
        )
        state.add_cost_point(
            CostDataPoint(
                timestamp=1.0,
                cost_usd=0.1,
                model="m",
                cycle_number=1,
            ),
        )
        state.add_alert(AlertItem(level="info", message="test"))
        state.add_radar_data(RadarChartData(persona="p"))
        state.clear()
        assert state.get_timeline() == []
        assert state.get_cost_history() == []
        assert state.get_alerts() == []
        assert state.get_persona_radar_data() == []

    def test_multiple_entries(self) -> None:
        state = self._make_state()
        for i in range(5):
            state.add_timeline_entry(
                TimelineEntry(
                    phase=f"phase-{i}",
                    start_time=float(i),
                ),
            )
        assert len(state.get_timeline()) == 5
