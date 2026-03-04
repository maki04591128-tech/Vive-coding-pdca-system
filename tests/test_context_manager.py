"""RAGコンテキスト管理のテスト。"""

import pytest

from vibe_pdca.engine.context_manager import (
    MAX_CONTEXT_FILES,
    MAX_TOTAL_TOKENS,
    ContextManager,
)

# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def ctx_mgr():
    return ContextManager()


@pytest.fixture
def sample_files():
    return [
        {"path": "src/main.py", "content": "x" * 2000, "score": 0.9},
        {"path": "src/utils.py", "content": "y" * 1500, "score": 0.8},
        {"path": "src/models.py", "content": "z" * 1000, "score": 0.7},
        {"path": "src/views.py", "content": "w" * 800, "score": 0.6},
        {"path": "src/tests.py", "content": "v" * 600, "score": 0.5},
        {"path": "src/extra.py", "content": "u" * 400, "score": 0.1},
    ]


# ============================================================
# テスト: トークン推定
# ============================================================


class TestTokenEstimation:
    def test_estimate_tokens(self, ctx_mgr):
        assert ctx_mgr.estimate_tokens("a" * 100) == 25

    def test_truncate_within_limit(self, ctx_mgr):
        text = "hello world"
        result = ctx_mgr.truncate_to_tokens(text, 100)
        assert result == text

    def test_truncate_over_limit(self, ctx_mgr):
        text = "x" * 10000
        result = ctx_mgr.truncate_to_tokens(text, 10)
        assert len(result) < len(text)
        assert "truncated" in result


# ============================================================
# テスト: コンテキスト構築
# ============================================================


class TestBuildContext:
    def test_max_5_files(self, ctx_mgr, sample_files):
        result = ctx_mgr.build_context("query", sample_files)
        assert result.file_count <= MAX_CONTEXT_FILES

    def test_sorted_by_score(self, ctx_mgr, sample_files):
        result = ctx_mgr.build_context("query", sample_files)
        scores = [c.relevance_score for c in result.chunks]
        assert scores == sorted(scores, reverse=True)

    def test_total_tokens_within_limit(self, ctx_mgr, sample_files):
        result = ctx_mgr.build_context("query", sample_files)
        assert result.total_tokens <= MAX_TOTAL_TOKENS

    def test_empty_files(self, ctx_mgr):
        result = ctx_mgr.build_context("query", [])
        assert result.file_count == 0
        assert result.total_tokens == 0


# ============================================================
# テスト: サイクル管理
# ============================================================


class TestCycleManagement:
    def test_summary_at_10_cycles(self, ctx_mgr):
        for _ in range(10):
            ctx_mgr.increment_cycle()
        assert ctx_mgr.should_summarize()

    def test_no_summary_before_10(self, ctx_mgr):
        for _ in range(9):
            ctx_mgr.increment_cycle()
        assert not ctx_mgr.should_summarize()

    def test_reset_at_100_cycles(self, ctx_mgr):
        for _ in range(100):
            ctx_mgr.increment_cycle()
        assert ctx_mgr.should_reset()

    def test_reset_clears_summaries(self, ctx_mgr):
        ctx_mgr.add_summary("test summary")
        assert len(ctx_mgr.summaries) == 1
        ctx_mgr.reset_context()
        assert len(ctx_mgr.summaries) == 0

    def test_get_status(self, ctx_mgr):
        status = ctx_mgr.get_status()
        assert status["max_files"] == MAX_CONTEXT_FILES
        assert status["max_tokens"] == MAX_TOTAL_TOKENS
