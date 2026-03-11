"""プロンプト A/B テストのテスト。"""

import time

from vibe_pdca.engine.prompt_ab_test import (
    ABTestConfig,
    ABTestManager,
    ABTestResult,
    PromptVariant,
    StatisticalAnalyzer,
)

# ============================================================
# テスト: PromptVariant
# ============================================================


class TestPromptVariant:
    def test_default_created_at(self):
        before = time.time()
        v = PromptVariant(
            variant_id="v1", template_content="hello", version="1.0",
        )
        after = time.time()
        assert before <= v.created_at <= after

    def test_custom_values(self):
        v = PromptVariant(
            variant_id="v2",
            template_content="prompt text",
            version="2.0",
            created_at=100.0,
        )
        assert v.variant_id == "v2"
        assert v.template_content == "prompt text"
        assert v.version == "2.0"
        assert v.created_at == 100.0


# ============================================================
# テスト: ABTestConfig
# ============================================================


class TestABTestConfig:
    def test_default_split_ratio(self):
        va = PromptVariant("a", "tmpl_a", "1.0")
        vb = PromptVariant("b", "tmpl_b", "1.0")
        cfg = ABTestConfig(test_id="t1", variant_a=va, variant_b=vb)
        assert cfg.split_ratio == 0.5

    def test_custom_split_ratio(self):
        va = PromptVariant("a", "tmpl_a", "1.0")
        vb = PromptVariant("b", "tmpl_b", "1.0")
        cfg = ABTestConfig(
            test_id="t1", variant_a=va, variant_b=vb, split_ratio=0.7,
        )
        assert cfg.split_ratio == 0.7


# ============================================================
# テスト: ABTestResult
# ============================================================


class TestABTestResult:
    def test_creation(self):
        r = ABTestResult(
            test_id="t1",
            variant_id="v1",
            cycle_number=1,
            success=True,
            quality_score=0.85,
            cost_usd=0.05,
        )
        assert r.test_id == "t1"
        assert r.variant_id == "v1"
        assert r.cycle_number == 1
        assert r.success is True
        assert r.quality_score == 0.85
        assert r.cost_usd == 0.05


# ============================================================
# テスト: ABTestManager
# ============================================================


class TestABTestManager:
    def _make_manager(self) -> tuple[ABTestManager, ABTestConfig]:
        va = PromptVariant("va", "template A", "1.0")
        vb = PromptVariant("vb", "template B", "1.0")
        cfg = ABTestConfig(test_id="test-1", variant_a=va, variant_b=vb)
        mgr = ABTestManager()
        mgr.create_test(cfg)
        return mgr, cfg

    def test_create_test(self):
        mgr, cfg = self._make_manager()
        assert mgr.list_active_tests() == ["test-1"]

    def test_assign_variant_deterministic(self):
        mgr, cfg = self._make_manager()
        v1 = mgr.assign_variant("test-1", cycle_number=1)
        v2 = mgr.assign_variant("test-1", cycle_number=1)
        assert v1.variant_id == v2.variant_id

    def test_assign_variant_returns_valid_variant(self):
        mgr, cfg = self._make_manager()
        v = mgr.assign_variant("test-1", cycle_number=42)
        assert v.variant_id in {"va", "vb"}

    def test_record_and_get_results(self):
        mgr, _ = self._make_manager()
        r = ABTestResult("test-1", "va", 1, True, 0.9, 0.01)
        mgr.record_result(r)
        results = mgr.get_results("test-1")
        assert len(results) == 1
        assert results[0].quality_score == 0.9

    def test_get_results_empty(self):
        mgr, _ = self._make_manager()
        assert mgr.get_results("test-1") == []

    def test_get_results_unknown_test(self):
        mgr = ABTestManager()
        assert mgr.get_results("nonexistent") == []

    def test_get_winner_insufficient_samples(self):
        mgr, _ = self._make_manager()
        for i in range(3):
            mgr.record_result(
                ABTestResult("test-1", "va", i, True, 0.9, 0.01),
            )
        assert mgr.get_winner("test-1", min_samples=5) is None

    def test_get_winner_sufficient_samples(self):
        mgr, _ = self._make_manager()
        for i in range(5):
            mgr.record_result(
                ABTestResult("test-1", "va", i, True, 0.9, 0.01),
            )
            mgr.record_result(
                ABTestResult("test-1", "vb", i + 100, True, 0.7, 0.02),
            )
        winner = mgr.get_winner("test-1", min_samples=5)
        assert winner == "va"

    def test_get_winner_unknown_test(self):
        mgr = ABTestManager()
        assert mgr.get_winner("nonexistent") is None

    def test_list_active_tests_multiple(self):
        mgr = ABTestManager()
        va = PromptVariant("a", "A", "1.0")
        vb = PromptVariant("b", "B", "1.0")
        mgr.create_test(ABTestConfig("t1", va, vb))
        mgr.create_test(ABTestConfig("t2", va, vb))
        assert mgr.list_active_tests() == ["t1", "t2"]


# ============================================================
# テスト: StatisticalAnalyzer
# ============================================================


class TestStatisticalAnalyzer:
    def test_compare_means(self):
        analyzer = StatisticalAnalyzer()
        results_a = [
            ABTestResult("t", "a", i, True, 0.9, 0.01) for i in range(5)
        ]
        results_b = [
            ABTestResult("t", "b", i, True, 0.7, 0.01) for i in range(5)
        ]
        result = analyzer.compare(results_a, results_b)
        assert result["mean_a"] == 0.9
        assert result["mean_b"] == 0.7
        assert abs(result["difference"] - 0.2) < 1e-9

    def test_compare_empty_a(self):
        analyzer = StatisticalAnalyzer()
        results_b = [
            ABTestResult("t", "b", 0, True, 0.8, 0.01),
        ]
        result = analyzer.compare([], results_b)
        assert result["mean_a"] == 0.0
        assert result["significant"] is False

    def test_compare_significant(self):
        analyzer = StatisticalAnalyzer()
        results_a = [
            ABTestResult("t", "a", i, True, 0.95, 0.01)
            for i in range(10)
        ]
        results_b = [
            ABTestResult("t", "b", i, True, 0.50, 0.01)
            for i in range(10)
        ]
        result = analyzer.compare(results_a, results_b)
        assert result["significant"] is True

    def test_compare_not_significant_small_sample(self):
        analyzer = StatisticalAnalyzer()
        results_a = [
            ABTestResult("t", "a", 0, True, 0.8, 0.01),
        ]
        results_b = [
            ABTestResult("t", "b", 0, True, 0.7, 0.01),
        ]
        result = analyzer.compare(results_a, results_b)
        assert result["significant"] is False

    def test_compare_identical_scores_zero_variance(self):
        """両群のスコアが完全に同一の場合（分散ゼロ）でも安全に処理されること。"""
        analyzer = StatisticalAnalyzer()
        results_a = [
            ABTestResult("t", "a", i, True, 0.85, 0.01) for i in range(5)
        ]
        results_b = [
            ABTestResult("t", "b", i, True, 0.85, 0.01) for i in range(5)
        ]
        result = analyzer.compare(results_a, results_b)
        # 同一スコアなので有意差なし
        assert result["significant"] is False
