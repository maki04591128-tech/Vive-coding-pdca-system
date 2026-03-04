"""エクスポート機能のテスト。"""

import json

from vibe_pdca.engine.exporter import Exporter, ExportFormat


class TestAuditExport:
    def test_jsonl_format(self):
        exp = Exporter()
        entries = [
            {"sequence": 0, "action": "test"},
            {"sequence": 1, "action": "test2"},
        ]
        result = exp.export_audit_log(entries, ExportFormat.JSONL)
        assert result.item_count == 2
        lines = result.content.strip().split("\n")
        assert len(lines) == 2

    def test_json_format(self):
        exp = Exporter()
        entries = [{"action": "test"}]
        result = exp.export_audit_log(entries, ExportFormat.JSON)
        parsed = json.loads(result.content)
        assert len(parsed) == 1


class TestDecisionExport:
    def test_export_decisions(self):
        exp = Exporter()
        decisions = [
            {"type": "accept", "reason": "OK"},
        ]
        result = exp.export_decisions(decisions)
        assert result.export_type == "decisions"


class TestReviewExport:
    def test_export_reviews(self):
        exp = Exporter()
        reviews = [{"reviewer": "PM", "finding": "issue"}]
        result = exp.export_reviews(reviews)
        assert result.item_count == 1


class TestMarkdownFormatExport:
    """MARKDOWN形式でのデータエクスポートテスト。"""

    def test_audit_log_markdown(self):
        exp = Exporter()
        entries = [
            {"sequence": 0, "action": "start"},
            {"sequence": 1, "action": "end"},
        ]
        result = exp.export_audit_log(entries, ExportFormat.MARKDOWN)
        assert result.format == ExportFormat.MARKDOWN
        assert result.item_count == 2
        # 各エントリが "- " で始まるリスト形式であること
        lines = result.content.strip().split("\n")
        assert all(line.startswith("- ") for line in lines)

    def test_reviews_markdown(self):
        exp = Exporter()
        reviews = [{"reviewer": "PM", "finding": "issue"}]
        result = exp.export_reviews(reviews, ExportFormat.MARKDOWN)
        assert result.format == ExportFormat.MARKDOWN
        assert result.item_count == 1
        assert "PM" in result.content


class TestMarkdownReport:
    def test_markdown_report(self):
        exp = Exporter()
        result = exp.export_as_markdown_report(
            "テストレポート",
            {"概要": "テスト内容", "結論": "問題なし"},
        )
        assert "テストレポート" in result.content
        assert "概要" in result.content
