"""GUI モジュールのユニットテスト。

Flet ウィジェットの構造・ロジックを検証する。
実際の画面描画は行わず、コントロール構成とコールバックを検証する。
"""

import flet as ft

from vibe_pdca.gui.app import APP_VERSION, create_app
from vibe_pdca.gui.components.pdca_card import PDCAStatusCard
from vibe_pdca.gui.components.status_card import CostCard, StatusCard
from vibe_pdca.gui.views.dashboard import DashboardView

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
# app モジュールテスト
# ============================================================


class TestApp:
    def test_version_defined(self):
        assert APP_VERSION == "0.1.0"

    def test_create_app_is_callable(self):
        assert callable(create_app)
