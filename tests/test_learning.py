"""学習フィードバックのテスト。"""

from vibe_pdca.engine.learning import LearningFeedback


class TestFailureRecording:
    def test_record_failure(self):
        fb = LearningFeedback()
        fb.record_failure(1, "ci_failure", "CIが失敗")
        assert fb.record_count == 1

    def test_should_analyze(self):
        fb = LearningFeedback(interval=10)
        assert not fb.should_analyze(9)
        assert fb.should_analyze(10)
        assert fb.should_analyze(20)


class TestAnalysis:
    def test_basic_analysis(self):
        fb = LearningFeedback(interval=10)
        for i in range(1, 11):
            fb.record_failure(i, "ci_failure", "CI失敗")
        report = fb.analyze(10)
        assert len(report.patterns) > 0

    def test_patterns_sorted_by_frequency(self):
        fb = LearningFeedback(interval=10)
        for i in range(1, 11):
            fb.record_failure(i, "ci_failure", "CI失敗")
        fb.record_failure(5, "timeout", "タイムアウト")
        report = fb.analyze(10)
        assert report.patterns[0].frequency >= report.patterns[-1].frequency

    def test_prompt_additions(self):
        fb = LearningFeedback(interval=10)
        for i in range(1, 11):
            fb.record_failure(i, "ci_failure", "CI失敗")
        report = fb.analyze(10)
        assert len(report.prompt_additions) > 0


class TestApplyToPrompt:
    def test_apply(self):
        fb = LearningFeedback(interval=10)
        for i in range(1, 11):
            fb.record_failure(i, "ci_failure", "CI失敗")
        report = fb.analyze(10)
        additions = fb.apply_to_prompt(report)
        assert len(additions) > 0
        assert report.applied
        assert len(fb.prompt_additions) > 0

    def test_get_status(self):
        fb = LearningFeedback()
        status = fb.get_status()
        assert "interval_cycles" in status


class TestLearningFeedbackThreadSafety:
    """LearningFeedbackのスレッドセーフティテスト。"""

    def test_concurrent_record_failure(self):
        import threading

        fb = LearningFeedback()
        n_threads = 10
        records_per_thread = 50
        barrier = threading.Barrier(n_threads)

        def worker(thread_id):
            barrier.wait()
            for i in range(records_per_thread):
                fb.record_failure(
                    cycle_number=i,
                    failure_type=f"type-{thread_id}",
                    description=f"desc-{thread_id}-{i}",
                )

        threads = [
            threading.Thread(target=worker, args=(tid,))
            for tid in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert fb.record_count == n_threads * records_per_thread
