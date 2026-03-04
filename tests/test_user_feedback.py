"""ユーザーフィードバック収集・満足度トラッキングのテスト。"""

import time

import pytest

from vibe_pdca.engine.user_feedback import (
    DEFAULT_MIN_ENTRIES,
    LOW_SATISFACTION_THRESHOLD,
    FeedbackCategory,
    FeedbackCollector,
    FeedbackEntry,
    FeedbackLearningBridge,
    SatisfactionScore,
    SatisfactionTracker,
)


# ============================================================
# helpers
# ============================================================


def _make_entry(
    cycle: int = 1,
    rating: int = 4,
    category: FeedbackCategory = FeedbackCategory.CODE_QUALITY,
    comment: str = "",
    submitted_by: str = "",
) -> FeedbackEntry:
    return FeedbackEntry(
        cycle_number=cycle,
        rating=rating,
        category=category,
        comment=comment,
        submitted_by=submitted_by,
    )


def _populated_collector(
    ratings: list[int] | None = None,
    category: FeedbackCategory = FeedbackCategory.CODE_QUALITY,
) -> FeedbackCollector:
    """指定 rating リストでエントリを登録済みの collector を返す。"""
    collector = FeedbackCollector()
    for i, r in enumerate(ratings or [4, 3, 5, 2, 4]):
        collector.submit_feedback(
            _make_entry(cycle=i + 1, rating=r, category=category)
        )
    return collector


# ============================================================
# FeedbackCategory
# ============================================================


class TestFeedbackCategory:
    def test_members(self):
        names = [c.name for c in FeedbackCategory]
        assert "CODE_QUALITY" in names
        assert "DESIGN" in names
        assert "TEST" in names
        assert "DOCUMENTATION" in names
        assert "PERFORMANCE" in names
        assert "USABILITY" in names

    def test_values_are_str(self):
        for cat in FeedbackCategory:
            assert isinstance(cat.value, str)


# ============================================================
# FeedbackEntry
# ============================================================


class TestFeedbackEntry:
    def test_defaults(self):
        entry = _make_entry()
        assert entry.id  # auto-generated, non-empty
        assert entry.timestamp > 0
        assert entry.comment == ""
        assert entry.submitted_by == ""

    def test_rating_lower_bound(self):
        with pytest.raises(ValueError):
            _make_entry(rating=0)

    def test_rating_upper_bound(self):
        with pytest.raises(ValueError):
            _make_entry(rating=6)

    def test_valid_ratings(self):
        for r in range(1, 6):
            entry = _make_entry(rating=r)
            assert entry.rating == r

    def test_custom_fields(self):
        entry = _make_entry(
            cycle=5,
            rating=3,
            category=FeedbackCategory.DESIGN,
            comment="改善希望",
            submitted_by="tester",
        )
        assert entry.cycle_number == 5
        assert entry.category == FeedbackCategory.DESIGN
        assert entry.comment == "改善希望"
        assert entry.submitted_by == "tester"


# ============================================================
# SatisfactionScore
# ============================================================


class TestSatisfactionScore:
    def test_defaults(self):
        score = SatisfactionScore()
        assert score.average_rating == 0.0
        assert score.total_responses == 0
        assert score.category_scores == {}
        assert score.nps_score == 0.0
        assert score.trend == "stable"


# ============================================================
# FeedbackCollector
# ============================================================


class TestFeedbackCollector:
    def test_submit_and_count(self):
        collector = FeedbackCollector()
        assert collector.feedback_count == 0
        collector.submit_feedback(_make_entry())
        assert collector.feedback_count == 1

    def test_get_all_feedback(self):
        collector = _populated_collector([3, 4, 5])
        assert len(collector.get_feedback()) == 3

    def test_get_feedback_by_cycle(self):
        collector = FeedbackCollector()
        collector.submit_feedback(_make_entry(cycle=1))
        collector.submit_feedback(_make_entry(cycle=2))
        collector.submit_feedback(_make_entry(cycle=1))
        assert len(collector.get_feedback(cycle_number=1)) == 2
        assert len(collector.get_feedback(cycle_number=2)) == 1

    def test_get_feedback_empty_cycle(self):
        collector = _populated_collector([3])
        assert collector.get_feedback(cycle_number=999) == []

    def test_get_category_feedback(self):
        collector = FeedbackCollector()
        collector.submit_feedback(
            _make_entry(category=FeedbackCategory.TEST)
        )
        collector.submit_feedback(
            _make_entry(category=FeedbackCategory.DESIGN)
        )
        collector.submit_feedback(
            _make_entry(category=FeedbackCategory.TEST)
        )
        result = collector.get_category_feedback(FeedbackCategory.TEST)
        assert len(result) == 2


# ============================================================
# SatisfactionTracker
# ============================================================


class TestSatisfactionTracker:
    def test_empty_collector(self):
        tracker = SatisfactionTracker(FeedbackCollector())
        score = tracker.calculate_satisfaction()
        assert score.average_rating == 0.0
        assert score.total_responses == 0

    def test_calculate_satisfaction_basic(self):
        collector = _populated_collector([4, 4, 4])
        tracker = SatisfactionTracker(collector)
        score = tracker.calculate_satisfaction()
        assert score.average_rating == 4.0
        assert score.total_responses == 3

    def test_nps_all_promoters(self):
        collector = _populated_collector([5, 5, 5, 5])
        tracker = SatisfactionTracker(collector)
        assert tracker.calculate_nps() == 100.0

    def test_nps_all_detractors(self):
        collector = _populated_collector([1, 1, 2, 2])
        tracker = SatisfactionTracker(collector)
        assert tracker.calculate_nps() == -100.0

    def test_nps_mixed(self):
        # 2 promoters (4,5), 1 detractor (1), 1 passive (3) → (2-1)/4*100=25
        collector = _populated_collector([4, 5, 1, 3])
        tracker = SatisfactionTracker(collector)
        assert tracker.calculate_nps() == 25.0

    def test_nps_empty(self):
        tracker = SatisfactionTracker(FeedbackCollector())
        assert tracker.calculate_nps() == 0.0

    def test_trend_improving(self):
        # first half low, second half high → improving
        collector = _populated_collector([1, 1, 1, 5, 5, 5])
        tracker = SatisfactionTracker(collector)
        assert tracker.get_trend() == "improving"

    def test_trend_declining(self):
        collector = _populated_collector([5, 5, 5, 1, 1, 1])
        tracker = SatisfactionTracker(collector)
        assert tracker.get_trend() == "declining"

    def test_trend_stable(self):
        collector = _populated_collector([3, 3, 3, 3])
        tracker = SatisfactionTracker(collector)
        assert tracker.get_trend() == "stable"

    def test_trend_single_entry(self):
        collector = _populated_collector([5])
        tracker = SatisfactionTracker(collector)
        assert tracker.get_trend() == "stable"

    def test_category_breakdown(self):
        collector = FeedbackCollector()
        collector.submit_feedback(
            _make_entry(rating=4, category=FeedbackCategory.TEST)
        )
        collector.submit_feedback(
            _make_entry(rating=2, category=FeedbackCategory.TEST)
        )
        collector.submit_feedback(
            _make_entry(rating=5, category=FeedbackCategory.DESIGN)
        )
        tracker = SatisfactionTracker(collector)
        breakdown = tracker.get_category_breakdown()
        assert breakdown["test"] == 3.0
        assert breakdown["design"] == 5.0


# ============================================================
# FeedbackLearningBridge
# ============================================================


class TestFeedbackLearningBridge:
    def test_extract_improvement_areas_below_threshold(self):
        # 5 entries all rating 2 → below threshold
        collector = _populated_collector(
            [2, 2, 2, 2, 2], category=FeedbackCategory.PERFORMANCE
        )
        bridge = FeedbackLearningBridge(collector)
        areas = bridge.extract_improvement_areas(min_entries=5)
        assert "performance" in areas

    def test_extract_no_improvement_areas(self):
        collector = _populated_collector(
            [4, 5, 4, 5, 4], category=FeedbackCategory.CODE_QUALITY
        )
        bridge = FeedbackLearningBridge(collector)
        areas = bridge.extract_improvement_areas(min_entries=5)
        assert areas == []

    def test_extract_skips_insufficient_entries(self):
        collector = _populated_collector(
            [1, 1], category=FeedbackCategory.USABILITY
        )
        bridge = FeedbackLearningBridge(collector)
        areas = bridge.extract_improvement_areas(min_entries=5)
        assert areas == []

    def test_generate_learning_input_empty(self):
        bridge = FeedbackLearningBridge(FeedbackCollector())
        result = bridge.generate_learning_input()
        assert result["source"] == "user_feedback"
        assert result["total_entries"] == 0

    def test_generate_learning_input_populated(self):
        collector = _populated_collector([3, 4, 5, 2, 4])
        bridge = FeedbackLearningBridge(collector)
        result = bridge.generate_learning_input()
        assert result["source"] == "user_feedback"
        assert result["total_entries"] == 5
        assert result["average_rating"] > 0

    def test_low_satisfaction_patterns(self):
        collector = _populated_collector(
            [1, 2, 1, 2, 1], category=FeedbackCategory.DOCUMENTATION
        )
        bridge = FeedbackLearningBridge(collector)
        patterns = bridge.get_low_satisfaction_patterns()
        assert len(patterns) == 1
        assert patterns[0]["category"] == "documentation"
        assert patterns[0]["average_rating"] < LOW_SATISFACTION_THRESHOLD

    def test_low_satisfaction_patterns_with_comments(self):
        collector = FeedbackCollector()
        for i in range(5):
            collector.submit_feedback(
                _make_entry(
                    cycle=i + 1,
                    rating=1,
                    category=FeedbackCategory.USABILITY,
                    comment=f"問題{i}",
                )
            )
        bridge = FeedbackLearningBridge(collector)
        patterns = bridge.get_low_satisfaction_patterns()
        assert len(patterns) == 1
        assert len(patterns[0]["comments"]) == 5

    def test_no_low_satisfaction_patterns(self):
        collector = _populated_collector(
            [5, 5, 5], category=FeedbackCategory.DESIGN
        )
        bridge = FeedbackLearningBridge(collector)
        assert bridge.get_low_satisfaction_patterns() == []
