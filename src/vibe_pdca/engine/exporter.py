"""エクスポート機能 – 監査ログ・決定ログ・ドキュメントのエクスポート。

M3 タスク 3-12: 要件定義書 §26.4, ギャップA5 準拠。

- 監査ログ・決定ログ・ドキュメント・テンプレのエクスポート
- 移行可能な形式（JSON / Markdown）
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class ExportFormat(StrEnum):
    """エクスポート形式。"""

    JSON = "json"
    JSONL = "jsonl"
    MARKDOWN = "markdown"


@dataclass
class ExportResult:
    """エクスポート結果。"""

    format: ExportFormat
    content: str
    item_count: int = 0
    export_type: str = ""
    exported_at: float = field(default_factory=time.time)


class Exporter:
    """データエクスポート管理。"""

    def export_audit_log(
        self,
        entries: list[dict[str, Any]],
        fmt: ExportFormat = ExportFormat.JSONL,
    ) -> ExportResult:
        """監査ログをエクスポートする。

        Parameters
        ----------
        entries : list[dict]
            監査ログエントリ。
        fmt : ExportFormat
            出力形式。

        Returns
        -------
        ExportResult
            エクスポート結果。
        """
        content = self._format_data(entries, fmt)
        return ExportResult(
            format=fmt,
            content=content,
            item_count=len(entries),
            export_type="audit_log",
        )

    def export_decisions(
        self,
        decisions: list[dict[str, Any]],
        fmt: ExportFormat = ExportFormat.JSON,
    ) -> ExportResult:
        """決定ログをエクスポートする。"""
        content = self._format_data(decisions, fmt)
        return ExportResult(
            format=fmt,
            content=content,
            item_count=len(decisions),
            export_type="decisions",
        )

    def export_reviews(
        self,
        reviews: list[dict[str, Any]],
        fmt: ExportFormat = ExportFormat.JSON,
    ) -> ExportResult:
        """レビュー原本をエクスポートする。"""
        content = self._format_data(reviews, fmt)
        return ExportResult(
            format=fmt,
            content=content,
            item_count=len(reviews),
            export_type="reviews",
        )

    def export_as_markdown_report(
        self,
        title: str,
        sections: dict[str, str],
    ) -> ExportResult:
        """Markdownレポートをエクスポートする。"""
        lines = [f"# {title}", ""]
        for section_title, section_body in sections.items():
            lines.append(f"## {section_title}")
            lines.append(section_body)
            lines.append("")

        content = "\n".join(lines)
        return ExportResult(
            format=ExportFormat.MARKDOWN,
            content=content,
            item_count=len(sections),
            export_type="report",
        )

    @staticmethod
    def _format_data(
        data: list[dict[str, Any]],
        fmt: ExportFormat,
    ) -> str:
        """データを指定形式にフォーマットする。"""
        if fmt == ExportFormat.JSON:
            return json.dumps(data, ensure_ascii=False, indent=2)
        if fmt == ExportFormat.JSONL:
            return "\n".join(
                json.dumps(item, ensure_ascii=False) for item in data
            )
        if fmt == ExportFormat.MARKDOWN:
            lines = []
            for item in data:
                lines.append(f"- {json.dumps(item, ensure_ascii=False)}")
            return "\n".join(lines)
        return json.dumps(data, ensure_ascii=False)
