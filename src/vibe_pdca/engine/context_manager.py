"""RAGコンテキスト管理 – GitHub Search + 5件/2000トークン上限。

M2 タスク 2-8: 要件定義書 §16.5 準拠。

| 項目             | 仕様                                        |
|-----------------|---------------------------------------------|
| 検索対象         | ファイル名・ファイルパス・ファイル内容の全文検索 |
| 取得件数         | 関連ファイル最大5件                           |
| コンテキスト形式  | 各ファイルの先頭200トークン + 関連セクション    |
| 合計トークン上限  | 2,000トークン以内                             |
| 統括要約         | 10サイクルごと / コンテキストリセット: 100サイクル |
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# §16.5 確定値
MAX_CONTEXT_FILES = 5
MAX_TOTAL_TOKENS = 2000
FILE_HEAD_TOKENS = 200
SUMMARY_INTERVAL_CYCLES = 10
CONTEXT_RESET_CYCLES = 100


@dataclass
class ContextChunk:
    """コンテキストチャンク1件。"""

    file_path: str
    content: str
    token_count: int = 0
    relevance_score: float = 0.0


@dataclass
class ContextResult:
    """コンテキスト検索結果。"""

    chunks: list[ContextChunk] = field(default_factory=list)
    total_tokens: int = 0
    query: str = ""
    truncated: bool = False

    @property
    def file_count(self) -> int:
        return len(self.chunks)


class ContextManager:
    """RAGコンテキスト管理。

    GitHub Search API（またはローカル検索）の結果を取得し、
    トークン上限内に収まるようコンテキストを構築する。
    """

    def __init__(
        self,
        max_files: int = MAX_CONTEXT_FILES,
        max_tokens: int = MAX_TOTAL_TOKENS,
        file_head_tokens: int = FILE_HEAD_TOKENS,
    ) -> None:
        self._max_files = max_files
        self._max_tokens = max_tokens
        self._file_head_tokens = file_head_tokens
        self._cycle_count = 0
        self._summaries: list[str] = []

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def summaries(self) -> list[str]:
        return list(self._summaries)

    def estimate_tokens(self, text: str) -> int:
        """トークン数を推定する（簡易: 4文字≒1トークン）。"""
        return max(1, len(text) // 4)

    def truncate_to_tokens(
        self,
        text: str,
        max_tokens: int,
    ) -> str:
        """テキストをトークン上限に切り詰める。"""
        estimated_chars = max_tokens * 4
        if len(text) <= estimated_chars:
            return text
        return text[:estimated_chars] + "\n... (truncated)"

    def build_context(
        self,
        query: str,
        files: list[dict[str, Any]],
    ) -> ContextResult:
        """検索結果からコンテキストを構築する。

        Parameters
        ----------
        query : str
            検索クエリ。
        files : list[dict]
            検索結果ファイルリスト。各要素は
            {"path": str, "content": str, "score": float} を含む。

        Returns
        -------
        ContextResult
            トークン上限内に収まったコンテキスト。
        """
        # スコア順に最大5件
        sorted_files = sorted(
            files, key=lambda f: f.get("score", 0.0), reverse=True,
        )[:self._max_files]

        chunks: list[ContextChunk] = []
        total_tokens = 0
        truncated = False

        for file_info in sorted_files:
            content = file_info.get("content", "")
            path = file_info.get("path", "unknown")
            score = file_info.get("score", 0.0)

            # ファイル先頭を取得
            head = self.truncate_to_tokens(content, self._file_head_tokens)
            token_count = self.estimate_tokens(head)

            # 合計トークン上限チェック
            if total_tokens + token_count > self._max_tokens:
                remaining = self._max_tokens - total_tokens
                if remaining > 0:
                    head = self.truncate_to_tokens(content, remaining)
                    token_count = self.estimate_tokens(head)
                    truncated = True
                else:
                    truncated = True
                    break

            chunks.append(ContextChunk(
                file_path=path,
                content=head,
                token_count=token_count,
                relevance_score=score,
            ))
            total_tokens += token_count

        return ContextResult(
            chunks=chunks,
            total_tokens=total_tokens,
            query=query,
            truncated=truncated,
        )

    def should_summarize(self) -> bool:
        """統括要約のタイミングか判定する（10サイクルごと）。"""
        return (
            self._cycle_count > 0
            and self._cycle_count % SUMMARY_INTERVAL_CYCLES == 0
        )

    def should_reset(self) -> bool:
        """コンテキストリセットのタイミングか判定する（100サイクルごと）。"""
        return (
            self._cycle_count > 0
            and self._cycle_count % CONTEXT_RESET_CYCLES == 0
        )

    def increment_cycle(self) -> None:
        """サイクルカウントを増加させる。"""
        self._cycle_count += 1

    def add_summary(self, summary: str) -> None:
        """統括要約を追加する。"""
        self._summaries.append(summary)
        logger.info("統括要約追加 (計%d件)", len(self._summaries))

    def reset_context(self) -> None:
        """コンテキストをリセットする。"""
        self._summaries.clear()
        logger.info("コンテキストリセット (サイクル %d)", self._cycle_count)

    def get_status(self) -> dict[str, Any]:
        """コンテキスト管理状態を返す。"""
        return {
            "cycle_count": self._cycle_count,
            "summary_count": len(self._summaries),
            "should_summarize": self.should_summarize(),
            "should_reset": self.should_reset(),
            "max_files": self._max_files,
            "max_tokens": self._max_tokens,
        }
