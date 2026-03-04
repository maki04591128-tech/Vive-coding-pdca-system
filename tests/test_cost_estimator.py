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
