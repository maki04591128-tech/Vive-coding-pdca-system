"""コスト見積もりのテスト。"""

from vibe_pdca.engine.cost_estimator import CostEstimator


class TestCostEstimation:
    def test_basic_estimate(self):
        est = CostEstimator()
        result = est.estimate(acceptance_criteria_count=5)
        assert result.estimated_tasks >= 1
        assert result.estimated_cost_usd > 0
        assert result.estimated_milestones >= 1

    def test_high_complexity(self):
        est = CostEstimator()
        low = est.estimate(acceptance_criteria_count=5, complexity="low")
        high = est.estimate(acceptance_criteria_count=5, complexity="high")
        assert high.estimated_cost_usd > low.estimated_cost_usd

    def test_risks_for_large_scope(self):
        est = CostEstimator()
        result = est.estimate(acceptance_criteria_count=15)
        assert len(result.major_risks) > 0

    def test_breakdown(self):
        est = CostEstimator()
        result = est.estimate(acceptance_criteria_count=5)
        assert "PLAN" in result.breakdown
        assert "DO" in result.breakdown
        assert "CHECK" in result.breakdown
        assert "ACT" in result.breakdown

    def test_to_markdown(self):
        est = CostEstimator()
        result = est.estimate(acceptance_criteria_count=5)
        md = result.to_markdown()
        assert "コスト見積もり" in md


class TestCostEstimationEdgeCases:
    """コスト見積もりの辺境ケーステスト。"""

    def test_high_cost_risk_warning(self):
        """推定コストが$50超で警告が含まれること。"""
        est = CostEstimator(cost_per_call=0.10, calls_per_task=20)
        result = est.estimate(acceptance_criteria_count=30, complexity="high")
        risk_texts = " ".join(result.major_risks)
        assert "推定コストが高い" in risk_texts

    def test_high_complexity_multiplier(self):
        """高複雑度でリスク警告が含まれること。"""
        est = CostEstimator()
        result = est.estimate(
            acceptance_criteria_count=5, complexity="high",
        )
        risk_texts = " ".join(result.major_risks)
        assert "高複雑度" in risk_texts

    def test_unknown_complexity_defaults_to_medium(self):
        """未知の複雑度は medium (1.0倍) として扱われること。"""
        est = CostEstimator()
        medium = est.estimate(acceptance_criteria_count=5, complexity="medium")
        unknown = est.estimate(acceptance_criteria_count=5, complexity="unknown")
        assert medium.estimated_tasks == unknown.estimated_tasks
        assert medium.estimated_cost_usd == unknown.estimated_cost_usd

    def test_to_markdown_with_risks(self):
        """リスクありのMarkdownレポートが正しく生成されること。"""
        est = CostEstimator()
        result = est.estimate(acceptance_criteria_count=15, complexity="high")
        md = result.to_markdown()
        assert "主要リスク" in md
        assert "コスト内訳" in md

    def test_minimum_values(self):
        """受入条件1件でもマイルストーン/サイクル/タスクが最低1になること。"""
        est = CostEstimator()
        result = est.estimate(acceptance_criteria_count=1, complexity="low")
        assert result.estimated_milestones >= 1
        assert result.estimated_cycles >= 1
        assert result.estimated_tasks >= 1
