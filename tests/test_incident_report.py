"""インシデントレポートのテスト。"""

from vibe_pdca.engine.incident_report import (
    IncidentReport,
    IncidentReporter,
)
from vibe_pdca.engine.intervention import IncidentPriority


class TestP0Report:
    def test_generate_p0(self):
        reporter = IncidentReporter()
        report = reporter.generate_p0_report(
            title="重大障害",
            summary="システム停止",
            root_cause="監査ログ不整合",
        )
        assert report.priority == IncidentPriority.P0
        assert report.impact_scope == "全システム停止"
        assert len(report.remediation_steps) > 0
        assert len(report.resume_conditions) > 0

    def test_p0_markdown(self):
        reporter = IncidentReporter()
        report = reporter.generate_p0_report(
            title="テスト障害",
            summary="テスト停止",
        )
        md = report.to_markdown()
        assert "P0" in md
        assert "即停止" in md


class TestP1Report:
    def test_generate_p1(self):
        reporter = IncidentReporter()
        report = reporter.generate_p1_report(
            title="CI連続失敗",
            summary="5回連続失敗",
        )
        assert report.priority == IncidentPriority.P1
        assert "縮退" in report.impact_scope

    def test_p1_markdown(self):
        reporter = IncidentReporter()
        report = reporter.generate_p1_report(
            title="テスト",
            summary="テスト",
        )
        md = report.to_markdown()
        assert "P1" in md


class TestReportFiltering:
    def test_filter_by_priority(self):
        reporter = IncidentReporter()
        reporter.generate_p0_report("P0-1", "テスト")
        reporter.generate_p1_report("P1-1", "テスト")
        reporter.generate_p0_report("P0-2", "テスト")

        p0s = reporter.get_reports(IncidentPriority.P0)
        assert len(p0s) == 2

        p1s = reporter.get_reports(IncidentPriority.P1)
        assert len(p1s) == 1

        all_reports = reporter.get_reports()
        assert len(all_reports) == 3


class TestAffectedServicesMarkdown:
    """影響を受けたサービスのMarkdownレンダリングテスト。"""

    def test_p0_with_affected_services(self):
        reporter = IncidentReporter()
        report = reporter.generate_p0_report(
            title="LLMゲートウェイ障害",
            summary="ゲートウェイ停止",
            affected_services=["LLMゲートウェイ", "監査ログ"],
        )
        md = report.to_markdown()
        assert "影響を受けたサービス" in md
        assert "- LLMゲートウェイ" in md
        assert "- 監査ログ" in md


class TestTimelineMarkdown:
    """タイムラインのMarkdownレンダリングテスト。"""

    def test_report_with_timeline(self):
        report = IncidentReport(
            title="障害レポート",
            summary="テスト",
            timeline=[{"time": "12:00", "description": "障害発生"}],
        )
        md = report.to_markdown()
        assert "タイムライン" in md
        assert "**12:00**" in md
        assert "障害発生" in md


class TestReportCount:
    """report_countプロパティのテスト。"""

    def test_report_count(self):
        reporter = IncidentReporter()
        assert reporter.report_count == 0
        reporter.generate_p0_report("P0", "テスト")
        assert reporter.report_count == 1
        reporter.generate_p1_report("P1", "テスト")
        assert reporter.report_count == 2
