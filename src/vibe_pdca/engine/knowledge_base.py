"""ナレッジベース蓄積・検索エンジン。

提案13: PDCAサイクルで得られた意思決定・パターン・ベストプラクティスを
蓄積し、類似検索・カテゴリ分類によって再利用可能にする。
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


# ── KnowledgeCategory ──


class KnowledgeCategory(StrEnum):
    """ナレッジのカテゴリ分類。"""

    DECISION = "decision"
    PATTERN = "pattern"
    BEST_PRACTICE = "best_practice"
    FAILURE = "failure"
    ARCHITECTURE = "architecture"


# ── KnowledgeEntry ──


@dataclass
class KnowledgeEntry:
    """ナレッジベースの個別エントリ。

    Parameters
    ----------
    entry_id : str
        エントリの一意識別子。
    category : KnowledgeCategory
        ナレッジのカテゴリ。
    title : str
        エントリのタイトル。
    content : str
        エントリの本文。
    tags : list[str]
        検索用タグのリスト。
    created_at : float
        作成日時（UNIXタイムスタンプ）。
    cycle_number : int | None
        関連するPDCAサイクル番号。
    relevance_score : float
        検索時の関連度スコア（0.0〜1.0）。
    """

    entry_id: str
    category: KnowledgeCategory
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: float = 0.0
    cycle_number: int | None = None
    relevance_score: float = 0.0


# ── KnowledgeStore ──


class KnowledgeStore:
    """ナレッジエントリの蓄積・検索ストア。"""

    def __init__(self) -> None:
        self._entries: dict[str, KnowledgeEntry] = {}

    def add(self, entry: KnowledgeEntry) -> None:
        """エントリをストアに追加する。

        Parameters
        ----------
        entry : KnowledgeEntry
            追加するナレッジエントリ。
        """
        self._entries[entry.entry_id] = entry
        logger.info("ナレッジ '%s' を追加しました", entry.title)

    def get(self, entry_id: str) -> KnowledgeEntry | None:
        """IDでエントリを取得する。

        Parameters
        ----------
        entry_id : str
            取得するエントリのID。

        Returns
        -------
        KnowledgeEntry | None
            該当エントリ。存在しない場合は None。
        """
        return self._entries.get(entry_id)

    def search(
        self,
        query: str,
        category: KnowledgeCategory | None = None,
        limit: int = 10,
    ) -> list[KnowledgeEntry]:
        """キーワードでナレッジを検索する。

        タイトル・本文・タグに対して大文字小文字を区別しない
        キーワードマッチングを行う。

        Parameters
        ----------
        query : str
            検索クエリ文字列。
        category : KnowledgeCategory | None
            カテゴリで絞り込む場合に指定。
        limit : int
            返却する最大件数（デフォルト 10）。

        Returns
        -------
        list[KnowledgeEntry]
            関連度スコア降順でソートされたエントリリスト。
        """
        keywords = query.lower().split()
        if not keywords:
            return []

        candidates: list[KnowledgeEntry] = list(self._entries.values())
        if category is not None:
            candidates = [
                e for e in candidates if e.category == category
            ]

        scored: list[KnowledgeEntry] = []
        for entry in candidates:
            text = " ".join(
                [entry.title, entry.content, *entry.tags]
            ).lower()
            hits = sum(1 for kw in keywords if kw in text)
            if hits > 0:
                score = min(1.0, hits / len(keywords))
                scored.append(
                    KnowledgeEntry(
                        entry_id=entry.entry_id,
                        category=entry.category,
                        title=entry.title,
                        content=entry.content,
                        tags=entry.tags,
                        created_at=entry.created_at,
                        cycle_number=entry.cycle_number,
                        relevance_score=score,
                    )
                )

        scored.sort(key=lambda e: e.relevance_score, reverse=True)
        return scored[:limit]

    def list_by_category(
        self, category: KnowledgeCategory
    ) -> list[KnowledgeEntry]:
        """指定カテゴリのエントリ一覧を返す。

        Parameters
        ----------
        category : KnowledgeCategory
            取得対象のカテゴリ。

        Returns
        -------
        list[KnowledgeEntry]
            該当カテゴリのエントリリスト。
        """
        return [
            e for e in self._entries.values()
            if e.category == category
        ]

    @property
    def count(self) -> int:
        """ストア内のエントリ総数を返す。

        Returns
        -------
        int
            エントリ総数。
        """
        return len(self._entries)

    def remove(self, entry_id: str) -> bool:
        """IDでエントリを削除する。

        Parameters
        ----------
        entry_id : str
            削除するエントリのID。

        Returns
        -------
        bool
            削除に成功した場合は True。
        """
        if entry_id in self._entries:
            del self._entries[entry_id]
            logger.info("ナレッジ '%s' を削除しました", entry_id)
            return True
        return False


# ── PatternExtractor ──


class PatternExtractor:
    """意思決定やレビューからナレッジエントリを抽出する。"""

    def extract_from_decisions(
        self, decisions: list[dict[str, Any]]
    ) -> list[KnowledgeEntry]:
        """意思決定辞書のリストからナレッジエントリを抽出する。

        Parameters
        ----------
        decisions : list[dict]
            意思決定データのリスト。各辞書は ``title``, ``content``,
            ``cycle`` キーを想定する。

        Returns
        -------
        list[KnowledgeEntry]
            抽出されたナレッジエントリのリスト。
        """
        entries: list[KnowledgeEntry] = []
        for decision in decisions:
            title = decision.get("title", "")
            content = decision.get("content", "")
            cycle = decision.get("cycle")
            if not title and not content:
                continue
            entry = KnowledgeEntry(
                entry_id=uuid.uuid4().hex[:12],
                category=KnowledgeCategory.DECISION,
                title=title,
                content=content,
                tags=decision.get("tags", []),
                created_at=time.time(),
                cycle_number=cycle,
            )
            entries.append(entry)
            logger.debug("意思決定から抽出: %s", title)
        return entries

    def extract_from_reviews(
        self, reviews: list[dict[str, Any]]
    ) -> list[KnowledgeEntry]:
        """レビュー辞書のリストからナレッジエントリを抽出する。

        Parameters
        ----------
        reviews : list[dict]
            レビューデータのリスト。各辞書は ``title``, ``content``,
            ``cycle`` キーを想定する。

        Returns
        -------
        list[KnowledgeEntry]
            抽出されたナレッジエントリのリスト。
        """
        entries: list[KnowledgeEntry] = []
        for review in reviews:
            title = review.get("title", "")
            content = review.get("content", "")
            cycle = review.get("cycle")
            if not title and not content:
                continue
            entry = KnowledgeEntry(
                entry_id=uuid.uuid4().hex[:12],
                category=KnowledgeCategory.BEST_PRACTICE,
                title=title,
                content=content,
                tags=review.get("tags", []),
                created_at=time.time(),
                cycle_number=cycle,
            )
            entries.append(entry)
            logger.debug("レビューから抽出: %s", title)
        return entries


# ── SimilarityFinder ──


class SimilarityFinder:
    """単語集合のJaccard類似度によるナレッジ検索。"""

    def find_similar(
        self,
        query: str,
        entries: list[KnowledgeEntry],
        threshold: float = 0.3,
    ) -> list[KnowledgeEntry]:
        """クエリに類似するエントリを検索する。

        単語集合のJaccard係数を用いて類似度を算出し、
        閾値以上のエントリを返す。

        Parameters
        ----------
        query : str
            検索クエリ文字列。
        entries : list[KnowledgeEntry]
            検索対象のエントリリスト。
        threshold : float
            類似度の閾値（デフォルト 0.3）。

        Returns
        -------
        list[KnowledgeEntry]
            類似度スコア降順でソートされたエントリリスト。
        """
        query_words = set(query.lower().split())
        if not query_words:
            return []

        results: list[KnowledgeEntry] = []
        for entry in entries:
            entry_words = set(
                " ".join(
                    [entry.title, entry.content, *entry.tags]
                ).lower().split()
            )
            if not entry_words:
                continue

            intersection = len(query_words & entry_words)
            union = len(query_words | entry_words)
            similarity = intersection / union if union > 0 else 0.0

            if similarity >= threshold:
                results.append(
                    KnowledgeEntry(
                        entry_id=entry.entry_id,
                        category=entry.category,
                        title=entry.title,
                        content=entry.content,
                        tags=entry.tags,
                        created_at=entry.created_at,
                        cycle_number=entry.cycle_number,
                        relevance_score=similarity,
                    )
                )

        results.sort(
            key=lambda e: e.relevance_score, reverse=True
        )
        return results
