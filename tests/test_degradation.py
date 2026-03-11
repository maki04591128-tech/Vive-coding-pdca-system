"""モデル劣化検知のテスト。"""

from vibe_pdca.engine.degradation import (
    TREND_DEGRADING,
    TREND_IMPROVING,
    TREND_INSUFFICIENT_DATA,
    TREND_STABLE,
    ModelDegradationDetector,
    ModelObservation,
    WeightAdjustmentResult,
)


class TestDegradationDetection:
    def test_insufficient_data(self):
        det = ModelDegradationDetector()
        det.record_observation(
            ModelObservation(model_name="claude", persona_role="PM", quality_score=0.8),
        )
        report = det.analyze("claude", "PM")
        assert report.trend == TREND_INSUFFICIENT_DATA

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
        assert report.trend == TREND_STABLE

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
        assert report.trend == TREND_DEGRADING

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
        assert report.trend == TREND_IMPROVING


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


class TestRunCycleAnalysis:
    """run_cycle_analysis のテスト。"""

    def test_empty_observations(self):
        """観測データなしの場合は空リストを返す。"""
        det = ModelDegradationDetector()
        results = det.run_cycle_analysis()
        assert results == []

    def test_stable_excluded(self):
        """安定トレンドのペルソナはサイクル分析結果から除外される。"""
        det = ModelDegradationDetector(window_size=10)
        for i in range(10):
            det.record_observation(ModelObservation(
                cycle_number=i + 1,
                model_name="claude",
                persona_role="PM",
                quality_score=0.8,
            ))
        results = det.run_cycle_analysis()
        assert len(results) == 0

    def test_degrading_included(self):
        """劣化トレンドのペルソナはサイクル分析結果に含まれる。"""
        det = ModelDegradationDetector(window_size=10)
        for i in range(10):
            det.record_observation(ModelObservation(
                cycle_number=i + 1,
                model_name="claude",
                persona_role="programmer",
                quality_score=0.9 - (i * 0.05),
            ))
        results = det.run_cycle_analysis()
        assert len(results) == 1
        assert results[0].trend == TREND_DEGRADING

    def test_multiple_personas(self):
        """複数ペルソナの同時分析が正しく動作する。"""
        det = ModelDegradationDetector(window_size=10)
        # プログラマ: 劣化
        for i in range(10):
            det.record_observation(ModelObservation(
                cycle_number=i + 1,
                model_name="claude",
                persona_role="programmer",
                quality_score=0.9 - (i * 0.05),
            ))
        # PM: 安定
        for i in range(10):
            det.record_observation(ModelObservation(
                cycle_number=i + 1,
                model_name="gpt",
                persona_role="PM",
                quality_score=0.8,
            ))
        results = det.run_cycle_analysis()
        assert len(results) == 1
        assert results[0].persona_role == "programmer"


class TestAutoAdjustWeights:
    """auto_adjust_weights のテスト。"""

    def test_no_adjustment_for_stable(self):
        """安定トレンドでは重み調整は行われない。"""
        det = ModelDegradationDetector(window_size=10)
        for i in range(10):
            det.record_observation(ModelObservation(
                cycle_number=i + 1,
                model_name="claude",
                persona_role="PM",
                quality_score=0.8,
            ))
        results = det.auto_adjust_weights()
        assert len(results) == 0

    def test_degrading_decreases_weight(self):
        """劣化トレンドでは重みが減少する。"""
        det = ModelDegradationDetector(window_size=10)
        for i in range(10):
            det.record_observation(ModelObservation(
                cycle_number=i + 1,
                model_name="claude",
                persona_role="programmer",
                quality_score=0.9 - (i * 0.05),
            ))
        results = det.auto_adjust_weights()
        assert len(results) == 1
        assert results[0].adjustment < 0
        assert results[0].new_weight < results[0].previous_weight
        assert results[0].governance_level == "B"

    def test_improving_increases_weight(self):
        """改善トレンドでは重みが増加する。"""
        det = ModelDegradationDetector(window_size=10)
        for i in range(10):
            det.record_observation(ModelObservation(
                cycle_number=i + 1,
                model_name="claude",
                persona_role="designer",
                quality_score=0.4 + (i * 0.05),
            ))
        results = det.auto_adjust_weights()
        assert len(results) == 1
        assert results[0].adjustment > 0
        assert results[0].new_weight > results[0].previous_weight

    def test_weight_adjustment_result_fields(self):
        """WeightAdjustmentResult の全フィールドが正しく設定される。"""
        result = WeightAdjustmentResult(
            persona_role="PM",
            previous_weight=1.0,
            new_weight=0.95,
            adjustment=-0.05,
            governance_level="B",
        )
        assert result.persona_role == "PM"
        assert result.governance_level == "B"
        assert result.adjustment == -0.05

    def test_get_all_reports(self):
        """get_all_reports が全観測モデルのレポートを返す。"""
        det = ModelDegradationDetector(window_size=5)
        for i in range(5):
            det.record_observation(ModelObservation(
                cycle_number=i + 1,
                model_name="claude",
                persona_role="programmer",
                quality_score=0.8,
            ))
            det.record_observation(ModelObservation(
                cycle_number=i + 1,
                model_name="gpt",
                persona_role="PM",
                quality_score=0.7,
            ))
        reports = det.get_all_reports()
        assert len(reports) == 2
        roles = {r.persona_role for r in reports}
        assert "programmer" in roles
        assert "PM" in roles

    def test_get_all_reports_malformed_key_skipped(self):
        """不正なキー形式が存在しても安全にスキップされること。"""
        det = ModelDegradationDetector()
        det.record_observation(ModelObservation(
            cycle_number=1,
            model_name="gpt",
            persona_role="programmer",
            quality_score=0.9,
        ))
        # 不正なキーを手動注入
        det._observations["malformed_no_colon"] = [
            ModelObservation(
                cycle_number=1,
                model_name="gpt",
                persona_role="programmer",
                quality_score=0.8,
            ),
        ]
        reports = det.get_all_reports()
        # 正常なキーの分だけレポートが生成される
        assert len(reports) == 1
        assert reports[0].model_name == "gpt"
