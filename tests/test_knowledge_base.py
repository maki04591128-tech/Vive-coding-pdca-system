"""ナレッジベース蓄積・検索エンジンのテスト。"""

from __future__ import annotations

import pytest

from vibe_pdca.engine.knowledge_base import (
    KnowledgeCategory,
    KnowledgeEntry,
    KnowledgeStore,
    PatternExtractor,
    SimilarityFinder,
)

# ============================================================
# テスト: KnowledgeCategory
# ============================================================


class TestKnowledgeCategory:
    """KnowledgeCategory列挙型のテスト。"""

    def test_enum_values(self) -> None:
        assert KnowledgeCategory.DECISION == "decision"
        assert KnowledgeCategory.PATTERN == "pattern"
        assert KnowledgeCategory.BEST_PRACTICE == "best_practice"
        assert KnowledgeCategory.FAILURE == "failure"
        assert KnowledgeCategory.ARCHITECTURE == "architecture"
        assert len(KnowledgeCategory) == 5


# ============================================================
# テスト: KnowledgeEntry
# ============================================================


class TestKnowledgeEntry:
    """KnowledgeEntryデータクラスのテスト。"""

    def test_defaults(self) -> None:
        entry = KnowledgeEntry(
            entry_id="e1",
            category=KnowledgeCategory.DECISION,
            title="タイトル",
            content="本文",
        )
        assert entry.entry_id == "e1"
        assert entry.category == KnowledgeCategory.DECISION
        assert entry.tags == []
        assert entry.created_at == 0.0
        assert entry.cycle_number is None
        assert entry.relevance_score == 0.0

    def test_custom(self) -> None:
        entry = KnowledgeEntry(
            entry_id="e2",
            category=KnowledgeCategory.FAILURE,
            title="障害",
            content="詳細",
            tags=["db", "timeout"],
            created_at=100.0,
            cycle_number=3,
            relevance_score=0.85,
        )
        assert entry.tags == ["db", "timeout"]
        assert entry.created_at == 100.0
        assert entry.cycle_number == 3
        assert entry.relevance_score == pytest.approx(0.85)


# ============================================================
# テスト: KnowledgeStore
# ============================================================


class TestKnowledgeStore:
    """KnowledgeStoreのテスト。"""

    @pytest.fixture()
    def store(self) -> KnowledgeStore:
        return KnowledgeStore()

    @pytest.fixture()
    def sample_entry(self) -> KnowledgeEntry:
        return KnowledgeEntry(
            entry_id="s1",
            category=KnowledgeCategory.PATTERN,
            title="retry pattern",
            content="exponential backoff strategy",
            tags=["retry", "resilience"],
        )

    def test_add_and_get(
        self, store: KnowledgeStore, sample_entry: KnowledgeEntry
    ) -> None:
        store.add(sample_entry)
        result = store.get("s1")
        assert result is not None
        assert result.title == "retry pattern"

    def test_get_missing(self, store: KnowledgeStore) -> None:
        assert store.get("nonexistent") is None

    def test_search_by_keyword(
        self, store: KnowledgeStore, sample_entry: KnowledgeEntry
    ) -> None:
        store.add(sample_entry)
        results = store.search("retry")
        assert len(results) == 1
        assert results[0].relevance_score > 0.0

    def test_search_by_category(
        self, store: KnowledgeStore
    ) -> None:
        store.add(
            KnowledgeEntry(
                entry_id="c1",
                category=KnowledgeCategory.PATTERN,
                title="pattern one",
                content="content",
            )
        )
        store.add(
            KnowledgeEntry(
                entry_id="c2",
                category=KnowledgeCategory.FAILURE,
                title="failure one",
                content="content",
            )
        )
        results = store.search(
            "one", category=KnowledgeCategory.FAILURE
        )
        assert len(results) == 1
        assert results[0].entry_id == "c2"

    def test_list_by_category(
        self, store: KnowledgeStore
    ) -> None:
        store.add(
            KnowledgeEntry(
                entry_id="l1",
                category=KnowledgeCategory.ARCHITECTURE,
                title="arch",
                content="details",
            )
        )
        store.add(
            KnowledgeEntry(
                entry_id="l2",
                category=KnowledgeCategory.DECISION,
                title="dec",
                content="details",
            )
        )
        items = store.list_by_category(
            KnowledgeCategory.ARCHITECTURE
        )
        assert len(items) == 1
        assert items[0].entry_id == "l1"

    def test_count(
        self, store: KnowledgeStore, sample_entry: KnowledgeEntry
    ) -> None:
        assert store.count == 0
        store.add(sample_entry)
        assert store.count == 1

    def test_remove(
        self, store: KnowledgeStore, sample_entry: KnowledgeEntry
    ) -> None:
        store.add(sample_entry)
        assert store.remove("s1") is True
        assert store.get("s1") is None
        assert store.count == 0

    def test_remove_missing(self, store: KnowledgeStore) -> None:
        assert store.remove("nonexistent") is False


# ============================================================
# テスト: PatternExtractor
# ============================================================


class TestPatternExtractor:
    """PatternExtractorのテスト。"""

    @pytest.fixture()
    def extractor(self) -> PatternExtractor:
        return PatternExtractor()

    def test_extract_from_decisions(
        self, extractor: PatternExtractor
    ) -> None:
        decisions = [
            {
                "title": "DB選定",
                "content": "PostgreSQL採用",
                "cycle": 1,
                "tags": ["db"],
            },
        ]
        entries = extractor.extract_from_decisions(decisions)
        assert len(entries) == 1
        assert entries[0].category == KnowledgeCategory.DECISION
        assert entries[0].title == "DB選定"
        assert entries[0].cycle_number == 1
        assert entries[0].tags == ["db"]

    def test_extract_from_reviews(
        self, extractor: PatternExtractor
    ) -> None:
        reviews = [
            {
                "title": "コードレビュー",
                "content": "型ヒント徹底",
                "cycle": 2,
            },
        ]
        entries = extractor.extract_from_reviews(reviews)
        assert len(entries) == 1
        e = entries[0]
        assert e.category == KnowledgeCategory.BEST_PRACTICE
        assert e.cycle_number == 2

    def test_extract_empty(
        self, extractor: PatternExtractor
    ) -> None:
        assert extractor.extract_from_decisions([]) == []
        empty_items = [{"title": "", "content": ""}]
        assert extractor.extract_from_decisions(empty_items) == []


# ============================================================
# テスト: SimilarityFinder
# ============================================================


class TestSimilarityFinder:
    """SimilarityFinderのテスト。"""

    @pytest.fixture()
    def finder(self) -> SimilarityFinder:
        return SimilarityFinder()

    @pytest.fixture()
    def entries(self) -> list[KnowledgeEntry]:
        return [
            KnowledgeEntry(
                entry_id="sim1",
                category=KnowledgeCategory.PATTERN,
                title="retry backoff strategy",
                content="exponential backoff for retries",
            ),
            KnowledgeEntry(
                entry_id="sim2",
                category=KnowledgeCategory.FAILURE,
                title="database connection failure",
                content="timeout on connection pool",
            ),
        ]

    def test_find_similar(
        self,
        finder: SimilarityFinder,
        entries: list[KnowledgeEntry],
    ) -> None:
        results = finder.find_similar(
            "retry backoff", entries, threshold=0.1
        )
        assert len(results) >= 1
        assert results[0].entry_id == "sim1"
        assert results[0].relevance_score > 0.0

    def test_find_similar_no_match(
        self,
        finder: SimilarityFinder,
        entries: list[KnowledgeEntry],
    ) -> None:
        results = finder.find_similar(
            "zzzzz_unknown_zzzzz", entries, threshold=0.3
        )
        assert results == []

    def test_threshold(
        self,
        finder: SimilarityFinder,
        entries: list[KnowledgeEntry],
    ) -> None:
        low = finder.find_similar(
            "retry", entries, threshold=0.01
        )
        high = finder.find_similar(
            "retry", entries, threshold=0.99
        )
        assert len(low) >= len(high)


# ============================================================
# テスト: 検索スコア上限
# ============================================================


class TestSearchScoreCap:
    """search() のスコアが 1.0 を超えないこと。"""

    def test_score_capped_at_one(self):
        from vibe_pdca.engine.knowledge_base import (
            KnowledgeEntry,
            KnowledgeStore,
        )

        kb = KnowledgeStore()
        kb.add(KnowledgeEntry(
            entry_id="test-1",
            category="lesson",
            title="retry retry retry",
            content="retry retry retry",
            tags=["retry"],
        ))
        # 1キーワード "retry" で検索 → テキストにも含まれるが score は 1.0 以下
        results = kb.search("retry")
        assert len(results) >= 1
        for r in results:
            assert r.relevance_score <= 1.0
