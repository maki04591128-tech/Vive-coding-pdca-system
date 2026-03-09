"""可観測性のテスト。"""

from vibe_pdca.monitoring.metrics import (
    AlertSeverity,
    AlertType,
    CycleMetrics,
    MetricsCollector,
)


class TestMetricsCollector:
    def test_record_cycle(self):
        mc = MetricsCollector()
        mc.record_cycle(CycleMetrics(cycle_number=1, success=True))
        assert mc.cycle_count == 1

    def test_cycle_success_rate(self):
        mc = MetricsCollector()
        mc.record_cycle(CycleMetrics(cycle_number=1, success=True))
        mc.record_cycle(CycleMetrics(cycle_number=2, success=False))
        assert mc.get_cycle_success_rate() == 0.5

    def test_average_cycle_time(self):
        mc = MetricsCollector()
        mc.record_cycle(CycleMetrics(duration_seconds=100))
        mc.record_cycle(CycleMetrics(duration_seconds=200))
        assert mc.get_average_cycle_time() == 150.0

    def test_ci_success_rate(self):
        mc = MetricsCollector()
        mc.record_cycle(CycleMetrics(ci_passed=True))
        mc.record_cycle(CycleMetrics(ci_passed=True))
        mc.record_cycle(CycleMetrics(ci_passed=False))
        assert abs(mc.get_ci_success_rate() - 2 / 3) < 0.01


class TestModelMetrics:
    def test_record_model_usage(self):
        mc = MetricsCollector()
        mc.record_model_usage("claude", calls=5, tokens=1000, cost_usd=0.5)
        mc.record_model_usage("claude", calls=3, tokens=500, error=True)
        dashboard = mc.get_dashboard_data()
        assert len(dashboard.model_metrics) == 1
        m = dashboard.model_metrics[0]
        assert m.total_calls == 8
        assert m.error_count == 1


class TestAlerts:
    def test_raise_alert(self):
        mc = MetricsCollector()
        alert = mc.raise_alert(
            AlertType.COST_SPIKE,
            AlertSeverity.WARNING,
            "コスト急増",
        )
        assert mc.alert_count == 1
        assert not alert.acknowledged

    def test_acknowledge_alert(self):
        mc = MetricsCollector()
        mc.raise_alert(AlertType.CI_FAILURE, AlertSeverity.CRITICAL, "CI失敗")
        assert mc.acknowledge_alert(0)
        assert len(mc.get_unacknowledged_alerts()) == 0

    def test_acknowledge_alert_invalid_index(self):
        """範囲外のインデックスでは False を返す。"""
        mc = MetricsCollector()
        mc.raise_alert(AlertType.CI_FAILURE, AlertSeverity.CRITICAL, "CI失敗")
        assert not mc.acknowledge_alert(-1)
        assert not mc.acknowledge_alert(99)

    def test_recent_alerts_capped_at_10(self):
        """ダッシュボードの recent_alerts は最新10件に制限される。"""
        mc = MetricsCollector()
        for i in range(15):
            mc.raise_alert(AlertType.CI_FAILURE, AlertSeverity.WARNING, f"alert-{i}")
        data = mc.get_dashboard_data()
        assert len(data.recent_alerts) == 10
        # _alertsはlist.append()で追加されるため挿入順序保持
        # [-10:]は最新10件(alert-5〜alert-14)を返す
        assert data.recent_alerts[0].message == "alert-5"
        assert data.recent_alerts[-1].message == "alert-14"


class TestDashboard:
    def test_get_dashboard_data(self):
        mc = MetricsCollector()
        mc.record_cycle(CycleMetrics(
            cycle_number=1, success=True, blocker_count=2,
        ))
        data = mc.get_dashboard_data(
            current_goal="テスト", progress_percent=50.0,
        )
        assert data.current_goal == "テスト"
        assert data.total_cycles == 1
        assert data.unresolved_blockers == 2

    def test_get_status(self):
        mc = MetricsCollector()
        status = mc.get_status()
        assert "cycle_count" in status
