"""モデル劣化検知のテスト。"""

from vibe_pdca.engine.degradation import (
    ModelDegradationDetector,
    ModelObservation,
)


class TestDegradationDetection:
    def test_insufficient_data(self):
        det = ModelDegradationDetector()
        det.record_observation(
            ModelObservation(model_name="claude", persona_role="PM", quality_score=0.8),
        )
        report = det.analyze("claude", "PM")
        assert report.trend == "insufficient_data"

    def test_stable_trend(self):
        det = ModelDegradationDetector(window_size=10)
        for i in range(10):
            det.record_observation(ModelObservation(
                cycle_number=i + 1,
                model_name="claude",
                persona_role="PM",
                quality_score=0.8,
            ))
        report = det.analyze("claude", "PM")
        assert report.trend == "stable"

    def test_degrading_trend(self):
        det = ModelDegradationDetector(window_size=10)
        for i in range(10):
            score = 0.9 - (i * 0.05)
            det.record_observation(ModelObservation(
                cycle_number=i + 1,
                model_name="claude",
                persona_role="PM",
                quality_score=score,
            ))
        report = det.analyze("claude", "PM")
        assert report.trend == "degrading"

    def test_improving_trend(self):
        det = ModelDegradationDetector(window_size=10)
        for i in range(10):
            score = 0.4 + (i * 0.05)
            det.record_observation(ModelObservation(
                cycle_number=i + 1,
                model_name="claude",
                persona_role="PM",
                quality_score=score,
            ))
        report = det.analyze("claude", "PM")
        assert report.trend == "improving"


class TestWeightAdjustment:
    def test_apply_weight(self):
        det = ModelDegradationDetector()
        new_weight = det.apply_weight_adjustment("PM", 0.05)
        assert new_weight == 1.05

    def test_weight_clamped_min(self):
        det = ModelDegradationDetector()
        det._persona_weights["PM"] = 0.1
        new_weight = det.apply_weight_adjustment("PM", -0.05)
        assert new_weight == 0.1

    def test_weight_clamped_max(self):
        det = ModelDegradationDetector()
        det._persona_weights["PM"] = 2.0
        new_weight = det.apply_weight_adjustment("PM", 0.05)
        assert new_weight == 2.0

    def test_get_status(self):
        det = ModelDegradationDetector()
        status = det.get_status()
        assert "window_size" in status
