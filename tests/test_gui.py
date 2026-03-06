"""GUI モジュールのユニットテスト。

Flet ウィジェットの構造・ロジックを検証する。
実際の画面描画は行わず、コントロール構成とコールバックを検証する。
"""

import time

import pytest

pytest.importorskip("flet", reason="flet が未インストールのためスキップ")

import flet as ft  # noqa: E402

from vibe_pdca.gui.app import APP_VERSION, create_app  # noqa: E402
from vibe_pdca.gui.components.alert_panel import AlertPanel  # noqa: E402
from vibe_pdca.gui.components.cost_chart_card import CostChartCard  # noqa: E402
from vibe_pdca.gui.components.pdca_card import PDCAStatusCard  # noqa: E402
from vibe_pdca.gui.components.radar_card import RadarCard  # noqa: E402
from vibe_pdca.gui.components.status_card import CostCard, StatusCard  # noqa: E402
from vibe_pdca.gui.components.timeline_card import TimelineCard  # noqa: E402
from vibe_pdca.gui.components.traceability_card import TraceabilityCard  # noqa: E402
from vibe_pdca.gui.dashboard import (  # noqa: E402
    AlertItem,
    CostDataPoint,
    RadarChartData,
    TimelineEntry,
    TraceLink,
)
from vibe_pdca.gui.views.dashboard import DashboardView  # noqa: E402
from vibe_pdca.gui.views.goal_input import GoalInputView  # noqa: E402
from vibe_pdca.gui.views.intervention_view import InterventionView  # noqa: E402
from vibe_pdca.gui.views.mode_settings import ModeSettingsView  # noqa: E402
from vibe_pdca.gui.views.progress_view import ProgressView  # noqa: E402

# ============================================================
# StatusCard テスト
# ============================================================


class TestStatusCard:
    def test_creates_with_title(self):
        card = StatusCard(title="テストカード")
        assert card._title == "テストカード"

    def test_update_items_populates_controls(self):
        card = StatusCard(title="クラウドLLM")
        card.update_items({
            "openai-gpt5.1": {
                "circuit_state": "closed",
                "consecutive_failures": 0,
                "total_fallbacks": 0,
            },
            "anthropic-opus4": {
                "circuit_state": "open",
                "consecutive_failures": 3,
                "total_fallbacks": 5,
            },
        })
        assert len(card._items_column.controls) == 2

    def test_status_icon_mapping(self):
        icon, color = StatusCard._status_icon("closed")
        assert icon == ft.Icons.CHECK_CIRCLE
        assert color == ft.Colors.GREEN

        icon, color = StatusCard._status_icon("open")
        assert icon == ft.Icons.ERROR
        assert color == ft.Colors.RED

        icon, color = StatusCard._status_icon("unknown_state")
        assert icon == ft.Icons.HELP
        assert color == ft.Colors.GREY


# ============================================================
# CostCard テスト
# ============================================================


class TestCostCard:
    def test_initial_state(self):
        card = CostCard()
        assert "$0.00" in card._cost_text.value
        assert card._progress.value == 0

    def test_update_cost_normal(self):
        card = CostCard()
        card.update_cost(
            {"daily_cost_usd": 5.0, "daily_calls": 100},
            {"daily_limit_usd": 30.0, "max_calls_per_day": 500},
        )
        assert "$5.00" in card._cost_text.value
        assert "100" in card._calls_text.value
        assert card._progress.color == ft.Colors.BLUE

    def test_update_cost_warning(self):
        card = CostCard()
        card.update_cost(
            {"daily_cost_usd": 22.0, "daily_calls": 350},
            {"daily_limit_usd": 30.0, "max_calls_per_day": 500},
        )
        assert card._progress.color == ft.Colors.ORANGE

    def test_update_cost_critical(self):
        card = CostCard()
        card.update_cost(
            {"daily_cost_usd": 28.0, "daily_calls": 480},
            {"daily_limit_usd": 30.0, "max_calls_per_day": 500},
        )
        assert card._progress.color == ft.Colors.RED


# ============================================================
# DashboardView テスト
# ============================================================


class TestDashboardView:
    def test_creates_without_errors(self):
        dashboard = DashboardView()
        assert isinstance(dashboard, ft.Column)
        assert len(dashboard.controls) > 0

    def test_update_status_sets_mode(self):
        dashboard = DashboardView()
        dashboard.update_status({
            "preferred_mode": "local",
            "auto_fallback_enabled": True,
            "cloud_providers": {},
            "local_providers": {},
            "cost": {},
        })
        assert dashboard._mode_toggle.value is True
        assert "local" in dashboard._mode_label.value

    def test_update_status_cloud_mode(self):
        dashboard = DashboardView()
        dashboard.update_status({
            "preferred_mode": "cloud",
            "auto_fallback_enabled": True,
            "cloud_providers": {},
            "local_providers": {},
            "cost": {},
        })
        assert dashboard._mode_toggle.value is False
        assert "cloud" in dashboard._mode_label.value

    def test_add_log(self):
        dashboard = DashboardView()
        dashboard.add_log("テストメッセージ", "INFO")
        dashboard.add_log("エラーメッセージ", "ERROR")
        assert len(dashboard._log_list.controls) == 2

    def test_mode_change_callback(self):
        captured = []
        dashboard = DashboardView(on_mode_change=lambda m: captured.append(m))
        # コールバック直接テスト
        event = type("Event", (), {"control": type("Ctrl", (), {"value": True})()})()
        dashboard._handle_mode_toggle(event)
        assert captured == ["local"]

    def test_update_pdca_status(self):
        dashboard = DashboardView()
        dashboard.update_pdca_status({
            "milestone_id": "ms-001",
            "milestone_status": "in_progress",
            "cycle_count": 3,
            "current_phase": "check",
            "current_cycle_number": 3,
            "current_cycle_status": "running",
            "is_stopped": False,
            "stop_reason": None,
        })
        assert "CHECK" in dashboard._pdca_card._phase_text.value

    def test_update_pdca_status_stopped(self):
        dashboard = DashboardView()
        dashboard.update_pdca_status({
            "milestone_id": "ms-002",
            "milestone_status": "in_progress",
            "cycle_count": 1,
            "current_phase": "do",
            "current_cycle_number": 1,
            "current_cycle_status": "stopped",
            "is_stopped": True,
            "stop_reason": "ci_consecutive_failure",
        })
        assert "停止中" in dashboard._pdca_card._status_text.value


# ============================================================
# PDCAStatusCard テスト
# ============================================================


class TestPDCAStatusCard:
    def test_creates_without_errors(self):
        card = PDCAStatusCard()
        assert isinstance(card, ft.Card)

    def test_update_plan_phase(self):
        card = PDCAStatusCard()
        card.update_pdca_status({
            "current_phase": "plan",
            "current_cycle_number": 1,
            "current_cycle_status": "running",
            "milestone_id": "ms-001",
            "milestone_status": "in_progress",
            "is_stopped": False,
            "stop_reason": None,
        })
        assert "PLAN" in card._phase_text.value
        assert "#1" in card._cycle_text.value

    def test_update_stopped_state(self):
        card = PDCAStatusCard()
        card.update_pdca_status({
            "current_phase": "do",
            "current_cycle_number": 2,
            "current_cycle_status": "stopped",
            "milestone_id": "ms-001",
            "milestone_status": "in_progress",
            "is_stopped": True,
            "stop_reason": "user_stop",
        })
        assert "停止中" in card._status_text.value
        assert card._status_text.color == ft.Colors.RED

    def test_update_not_started(self):
        card = PDCAStatusCard()
        card.update_pdca_status({
            "current_phase": None,
            "current_cycle_number": None,
            "current_cycle_status": None,
            "milestone_id": "ms-001",
            "milestone_status": "open",
            "is_stopped": False,
            "stop_reason": None,
        })
        assert "未開始" in card._phase_text.value


# ============================================================
# TimelineCard テスト
# ============================================================


class TestTimelineCard:
    def test_creates_without_errors(self):
        card = TimelineCard()
        assert isinstance(card, ft.Card)

    def test_update_timeline_empty(self):
        card = TimelineCard()
        card.update_timeline([])
        assert len(card._entries_column.controls) == 1
        assert "なし" in card._entries_column.controls[0].value

    def test_update_timeline_with_entries(self):
        card = TimelineCard()
        now = time.time()
        entries = [
            TimelineEntry(
                phase="plan", start_time=now - 120,
                end_time=now - 60, status="completed",
            ),
            TimelineEntry(
                phase="do", start_time=now - 60,
                end_time=None, status="running",
            ),
        ]
        card.update_timeline(entries)
        assert len(card._entries_column.controls) == 2

    def test_format_duration_seconds(self):
        result = TimelineCard._format_duration(100.0, 130.0)
        assert "30秒" in result

    def test_format_duration_minutes(self):
        result = TimelineCard._format_duration(100.0, 400.0)
        assert "分" in result

    def test_format_duration_hours(self):
        result = TimelineCard._format_duration(100.0, 10000.0)
        assert "時間" in result

    def test_format_duration_ongoing(self):
        result = TimelineCard._format_duration(time.time() - 10, None)
        assert "進行中" in result


# ============================================================
# CostChartCard テスト
# ============================================================


class TestCostChartCard:
    def test_creates_without_errors(self):
        card = CostChartCard()
        assert isinstance(card, ft.Card)

    def test_update_chart_empty(self):
        card = CostChartCard()
        card.update_chart([])
        assert "なし" in card._chart_column.controls[0].value
        assert "$0.00" in card._total_text.value

    def test_update_chart_with_data(self):
        card = CostChartCard()
        data = [
            CostDataPoint(timestamp=time.time(), cost_usd=1.50, model="gpt-4", cycle_number=1),
            CostDataPoint(timestamp=time.time(), cost_usd=2.30, model="claude-3", cycle_number=2),
        ]
        card.update_chart(data)
        assert "$3.80" in card._total_text.value
        assert len(card._chart_column.controls) == 2

    def test_update_chart_limits_to_10(self):
        card = CostChartCard()
        data = [
            CostDataPoint(timestamp=time.time(), cost_usd=float(i), model="m", cycle_number=i)
            for i in range(1, 16)
        ]
        card.update_chart(data)
        assert len(card._chart_column.controls) == 10


# ============================================================
# TraceabilityCard テスト
# ============================================================


class TestTraceabilityCard:
    def test_creates_without_errors(self):
        card = TraceabilityCard()
        assert isinstance(card, ft.Card)

    def test_update_links_empty(self):
        card = TraceabilityCard()
        card.update_links([])
        assert "なし" in card._links_column.controls[0].value

    def test_update_links_with_data(self):
        card = TraceabilityCard()
        links = [
            TraceLink(
                source_type="goal", source_id="G-001",
                target_type="milestone", target_id="MS-001",
            ),
            TraceLink(
                source_type="task", source_id="T-001",
                target_type="pr", target_id="PR-42",
            ),
        ]
        card.update_links(links)
        assert len(card._links_column.controls) == 2


# ============================================================
# RadarCard テスト
# ============================================================


class TestRadarCard:
    def test_creates_without_errors(self):
        card = RadarCard()
        assert isinstance(card, ft.Card)

    def test_update_radar_empty(self):
        card = RadarCard()
        card.update_radar([])
        assert "なし" in card._data_column.controls[0].value

    def test_update_radar_with_data(self):
        card = RadarCard()
        data = [
            RadarChartData(persona="PM", scores={"品質": 0.8, "速度": 0.6}),
            RadarChartData(persona="Developer", scores={"品質": 0.9, "速度": 0.7}),
        ]
        card.update_radar(data)
        assert len(card._data_column.controls) == 2


# ============================================================
# AlertPanel テスト
# ============================================================


class TestAlertPanel:
    def test_creates_without_errors(self):
        panel = AlertPanel()
        assert isinstance(panel, ft.Card)

    def test_update_alerts_empty(self):
        panel = AlertPanel()
        panel.update_alerts([])
        assert "0件" in panel._count_text.value

    def test_update_alerts_with_data(self):
        panel = AlertPanel()
        alerts = [
            AlertItem(level="info", message="テスト情報", timestamp=time.time()),
            AlertItem(level="warning", message="テスト警告", timestamp=time.time()),
            AlertItem(level="error", message="テストエラー", timestamp=time.time()),
        ]
        panel.update_alerts(alerts)
        assert "3件" in panel._count_text.value

    def test_add_alert(self):
        panel = AlertPanel()
        panel.add_alert(AlertItem(level="info", message="テスト", timestamp=time.time()))
        assert "1件" in panel._count_text.value

    def test_filter_by_level(self):
        panel = AlertPanel()
        alerts = [
            AlertItem(level="info", message="情報", timestamp=time.time()),
            AlertItem(level="error", message="エラー", timestamp=time.time()),
            AlertItem(level="error", message="エラー2", timestamp=time.time()),
        ]
        panel.update_alerts(alerts)
        panel._set_filter("error")
        assert "2件" in panel._count_text.value

    def test_filter_all(self):
        panel = AlertPanel()
        alerts = [
            AlertItem(level="info", message="情報", timestamp=time.time()),
            AlertItem(level="error", message="エラー", timestamp=time.time()),
        ]
        panel.update_alerts(alerts)
        panel._set_filter("error")
        panel._set_filter(None)
        assert "2件" in panel._count_text.value


# ============================================================
# GoalInputView テスト
# ============================================================


class TestGoalInputView:
    def test_creates_without_errors(self):
        view = GoalInputView()
        assert isinstance(view, ft.Column)

    def test_submit_callback(self):
        captured = []
        view = GoalInputView(on_submit=lambda g: captured.append(g))
        view._goal_input.value = "テストゴール"
        view._submit_btn.disabled = False
        event = type("Event", (), {})()
        view._handle_submit(event)
        assert captured == ["テストゴール"]

    def test_back_callback(self):
        captured = []
        view = GoalInputView(on_back=lambda: captured.append("back"))
        event = type("Event", (), {})()
        view._handle_back(event)
        assert captured == ["back"]

    def test_set_questions(self):
        view = GoalInputView()
        view.set_questions(["質問1", "質問2"])
        assert view._questions_container.visible is True
        assert len(view._questions_column.controls) == 2

    def test_set_questions_empty(self):
        view = GoalInputView()
        view.set_questions([])
        assert view._questions_container.visible is False

    def test_set_estimate(self):
        view = GoalInputView()
        view.set_estimate(milestones=3, cycles=15, estimated_cost_usd=12.50)
        assert view._estimate_container.visible is True
        assert "$12.50" in view._estimate_text.value
        assert view._submit_btn.disabled is False

    def test_get_goal_text(self):
        view = GoalInputView()
        view._goal_input.value = "テスト"
        assert view.get_goal_text() == "テスト"

    def test_get_goal_text_empty(self):
        view = GoalInputView()
        assert view.get_goal_text() == ""


# ============================================================
# ProgressView テスト
# ============================================================


class TestProgressView:
    def test_creates_without_errors(self):
        view = ProgressView()
        assert isinstance(view, ft.Column)

    def test_update_milestone(self):
        view = ProgressView()
        view.update_milestone("ms-001", "in_progress", "ユーザー認証")
        assert "ms-001" in view._milestone_text.value
        assert "in_progress" in view._milestone_status.value

    def test_update_dod(self):
        view = ProgressView()
        view.update_dod([
            {"text": "テスト通過", "done": True},
            {"text": "レビュー完了", "done": False},
        ])
        assert len(view._dod_column.controls) == 2

    def test_update_dod_empty(self):
        view = ProgressView()
        view.update_dod([])
        assert "未定義" in view._dod_column.controls[0].value

    def test_update_recent_plan(self):
        view = ProgressView()
        view.update_recent_plan("タスク3件を計画")
        assert "タスク3件" in view._plan_text.value

    def test_update_recent_check(self):
        view = ProgressView()
        view.update_recent_check("品質スコア: 0.85")
        assert "0.85" in view._check_text.value

    def test_update_recent_act(self):
        view = ProgressView()
        view.update_recent_act("承認 → 次サイクルへ")
        assert "承認" in view._act_text.value

    def test_back_callback(self):
        captured = []
        view = ProgressView(on_back=lambda: captured.append("back"))
        event = type("Event", (), {})()
        view._handle_back(event)
        assert captured == ["back"]


# ============================================================
# InterventionView テスト
# ============================================================


class TestInterventionView:
    def test_creates_without_errors(self):
        view = InterventionView()
        assert isinstance(view, ft.Column)

    def test_stop_callback(self):
        captured = []
        view = InterventionView(on_stop=lambda: captured.append("stopped"))
        event = type("Event", (), {})()
        view._handle_stop(event)
        assert captured == ["stopped"]
        assert view.is_stopped is True
        assert view._stop_btn.disabled is True

    def test_set_analysis_report(self):
        view = InterventionView()
        view.set_analysis_report("CI連続失敗（3回）")
        assert view._analysis_container.visible is True
        assert "CI連続失敗" in view._analysis_text.value

    def test_set_restart_conditions(self):
        view = InterventionView()
        view.set_restart_conditions("CIを修正後にリトライ")
        assert view._restart_container.visible is True
        assert "修正後" in view._restart_text.value

    def test_set_rollback_candidates(self):
        view = InterventionView()
        view.set_rollback_candidates([
            {"id": "PR-42", "description": "認証モジュール変更"},
            {"id": "PR-40", "description": "DB スキーマ変更"},
        ])
        assert view._rollback_container.visible is True
        assert len(view._rollback_column.controls) == 2

    def test_set_rollback_candidates_empty(self):
        view = InterventionView()
        view.set_rollback_candidates([])
        assert view._rollback_container.visible is False

    def test_override_callback(self):
        captured = []
        view = InterventionView(on_override=lambda d: captured.append(d))
        view._override_dropdown.value = "approve"
        event = type("Event", (), {})()
        view._handle_override(event)
        assert captured == ["approve"]

    def test_back_callback(self):
        captured = []
        view = InterventionView(on_back=lambda: captured.append("back"))
        event = type("Event", (), {})()
        view._handle_back(event)
        assert captured == ["back"]


# ============================================================
# ModeSettingsView テスト
# ============================================================


class TestModeSettingsView:
    def test_creates_without_errors(self):
        view = ModeSettingsView()
        assert isinstance(view, ft.Column)

    def test_initial_mode(self):
        view = ModeSettingsView()
        assert view.get_current_mode() == "manual"

    def test_set_mode(self):
        view = ModeSettingsView()
        view.set_mode("semi_auto")
        assert view.get_current_mode() == "semi_auto"
        assert "半自動" in view._current_mode_text.value

    def test_set_mode_full_auto(self):
        view = ModeSettingsView()
        view.set_mode("full_auto")
        assert view.get_current_mode() == "full_auto"
        assert "全自動" in view._current_mode_text.value

    def test_mode_change_callback(self):
        captured = []
        view = ModeSettingsView(on_mode_change=lambda m: captured.append(m))
        event = type("Event", (), {"control": type("Ctrl", (), {"value": "semi_auto"})()})()
        view._handle_mode_change(event)
        assert captured == ["semi_auto"]
        assert view.get_current_mode() == "semi_auto"

    def test_back_callback(self):
        captured = []
        view = ModeSettingsView(on_back=lambda: captured.append("back"))
        event = type("Event", (), {})()
        view._handle_back(event)
        assert captured == ["back"]

    def test_invalid_mode_ignored(self):
        view = ModeSettingsView()
        view.set_mode("invalid_mode")
        assert view.get_current_mode() == "manual"


# ============================================================
# app モジュールテスト
# ============================================================


class TestApp:
    def test_version_defined(self):
        assert APP_VERSION == "0.2.0"

    def test_create_app_is_callable(self):
        assert callable(create_app)
