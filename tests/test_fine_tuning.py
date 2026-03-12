"""Proposal 27: Fine-Tuning Pipeline のテスト。"""

from __future__ import annotations

from vibe_pdca.engine.fine_tuning import (
    FineTuneConfig,
    FineTuneManager,
    ModelComparator,
    TrainingDataCollector,
    TrainingExample,
)

# ============================================================
# TrainingExample dataclass
# ============================================================


class TestTrainingExample:
    """TrainingExample データクラスのテスト。"""

    def test_defaults(self) -> None:
        ex = TrainingExample(
            input_text="入力", output_text="出力", source="approved_pr"
        )
        assert ex.quality_score == 0.0
        assert ex.created_at == 0.0

    def test_with_values(self) -> None:
        ex = TrainingExample(
            input_text="in",
            output_text="out",
            source="successful_plan",
            quality_score=0.9,
            created_at=1000.0,
        )
        assert ex.quality_score == 0.9
        assert ex.created_at == 1000.0


# ============================================================
# TrainingDataCollector
# ============================================================


class TestTrainingDataCollector:
    """TrainingDataCollector のテスト。"""

    def setup_method(self) -> None:
        self.collector = TrainingDataCollector()

    def test_add_and_count(self) -> None:
        ex = TrainingExample(
            input_text="a", output_text="b", source="approved_pr", created_at=1.0
        )
        self.collector.add_example(ex)
        assert self.collector.example_count == 1

    def test_get_examples_all(self) -> None:
        for i in range(5):
            self.collector.add_example(
                TrainingExample(
                    input_text=f"in{i}",
                    output_text=f"out{i}",
                    source="approved_pr",
                    quality_score=0.5,
                    created_at=float(i),
                )
            )
        assert len(self.collector.get_examples()) == 5

    def test_get_examples_by_source(self) -> None:
        self.collector.add_example(
            TrainingExample(
                input_text="a", output_text="b", source="approved_pr", created_at=1.0
            )
        )
        self.collector.add_example(
            TrainingExample(
                input_text="c", output_text="d", source="successful_plan", created_at=2.0
            )
        )
        result = self.collector.get_examples(source="approved_pr")
        assert len(result) == 1
        assert result[0].source == "approved_pr"

    def test_get_examples_min_quality(self) -> None:
        self.collector.add_example(
            TrainingExample(
                input_text="a", output_text="b", source="x",
                quality_score=0.3, created_at=1.0,
            )
        )
        self.collector.add_example(
            TrainingExample(
                input_text="c", output_text="d", source="x",
                quality_score=0.8, created_at=2.0,
            )
        )
        result = self.collector.get_examples(min_quality=0.5)
        assert len(result) == 1
        assert result[0].quality_score == 0.8

    def test_get_stats_empty(self) -> None:
        stats = self.collector.get_stats()
        assert stats.total_examples == 0

    def test_get_stats_with_data(self) -> None:
        self.collector.add_example(
            TrainingExample(
                input_text="a", output_text="b", source="approved_pr",
                quality_score=0.6, created_at=100.0,
            )
        )
        self.collector.add_example(
            TrainingExample(
                input_text="c", output_text="d", source="successful_plan",
                quality_score=0.8, created_at=200.0,
            )
        )
        stats = self.collector.get_stats()
        assert stats.total_examples == 2
        assert stats.source_distribution["approved_pr"] == 1
        assert stats.source_distribution["successful_plan"] == 1
        assert stats.avg_quality == 0.7
        assert stats.oldest == 100.0
        assert stats.newest == 200.0

    def test_export_jsonl(self) -> None:
        self.collector.add_example(
            TrainingExample(
                input_text="in1", output_text="out1", source="x",
                quality_score=0.3, created_at=1.0,
            )
        )
        self.collector.add_example(
            TrainingExample(
                input_text="in2", output_text="out2", source="x",
                quality_score=0.8, created_at=2.0,
            )
        )
        result = self.collector.export_jsonl(min_quality=0.5)
        assert len(result) == 1
        assert result[0]["input"] == "in2"
        assert result[0]["output"] == "out2"

    def test_export_jsonl_empty(self) -> None:
        result = self.collector.export_jsonl()
        assert result == []


# ============================================================
# FineTuneManager
# ============================================================


class TestFineTuneManager:
    """FineTuneManager のテスト。"""

    def setup_method(self) -> None:
        self.collector = TrainingDataCollector()
        self.manager = FineTuneManager(self.collector)

    def test_is_ready_false(self) -> None:
        assert not self.manager.is_ready(min_examples=10)

    def test_is_ready_true(self) -> None:
        for i in range(20):
            self.collector.add_example(
                TrainingExample(
                    input_text=f"in{i}", output_text=f"out{i}",
                    source="approved_pr", created_at=float(i),
                )
            )
        assert self.manager.is_ready(min_examples=20)

    def test_create_and_get_job(self) -> None:
        config = FineTuneConfig(base_model="gpt-4")
        job = self.manager.create_job(config)
        assert job.status == "pending"
        assert job.config.base_model == "gpt-4"
        fetched = self.manager.get_job(job.job_id)
        assert fetched is not None
        assert fetched.job_id == job.job_id

    def test_get_job_not_found(self) -> None:
        assert self.manager.get_job("nonexistent") is None

    def test_list_jobs(self) -> None:
        config = FineTuneConfig(base_model="model-a")
        self.manager.create_job(config)
        self.manager.create_job(config)
        jobs = self.manager.list_jobs()
        assert len(jobs) == 2

    def test_validate_dataset_empty(self) -> None:
        report = self.manager.validate_dataset()
        assert not report["is_valid"]
        assert report["total_examples"] == 0

    def test_validate_dataset_sufficient(self) -> None:
        for i in range(15):
            self.collector.add_example(
                TrainingExample(
                    input_text=f"in{i}", output_text=f"out{i}",
                    source="approved_pr" if i % 2 == 0 else "successful_plan",
                    quality_score=0.8,
                    created_at=float(i),
                )
            )
        report = self.manager.validate_dataset(min_quality=0.5)
        assert report["is_valid"]
        assert report["qualified_examples"] == 15


# ============================================================
# ModelComparator
# ============================================================


class TestModelComparator:
    """ModelComparator のテスト。"""

    def setup_method(self) -> None:
        self.comparator = ModelComparator()

    def test_add_result_and_compare(self) -> None:
        self.comparator.add_result("model-a", "planning", 0.8)
        self.comparator.add_result("model-b", "planning", 0.6)
        result = self.comparator.compare("model-a", "model-b")
        assert result["winner"] == "model-a"
        assert result["wins"]["model-a"] == 1

    def test_compare_tie(self) -> None:
        self.comparator.add_result("model-a", "planning", 0.7)
        self.comparator.add_result("model-b", "planning", 0.7)
        result = self.comparator.compare("model-a", "model-b")
        assert result["winner"] == "tie"

    def test_get_best_model(self) -> None:
        self.comparator.add_result("model-a", "coding", 0.9)
        self.comparator.add_result("model-b", "coding", 0.7)
        assert self.comparator.get_best_model("coding") == "model-a"

    def test_get_best_model_no_data(self) -> None:
        assert self.comparator.get_best_model("unknown") is None


# ============================================================
# テスト: データセット統計のタイムスタンプ
# ============================================================


class TestDatasetStatsTimestamp:
    """get_stats() の oldest/newest が正しく計算されること。"""

    def test_oldest_newest_correct(self):
        import time

        from vibe_pdca.engine.fine_tuning import (
            TrainingDataCollector,
            TrainingExample,
        )

        now = time.time()
        builder = TrainingDataCollector()
        builder.add_example(TrainingExample(
            input_text="p1",
            output_text="c1",
            source="test",
            quality_score=0.8,
            created_at=now - 100,
        ))
        builder.add_example(TrainingExample(
            input_text="p2",
            output_text="c2",
            source="test",
            quality_score=0.9,
            created_at=now,
        ))
        stats = builder.get_stats()
        assert stats.total_examples == 2
        assert stats.oldest <= stats.newest
        assert abs(stats.oldest - (now - 100)) < 1.0
        assert abs(stats.newest - now) < 1.0


class TestTrainingDataCollectorThreadSafety:
    """TrainingDataCollectorのスレッドセーフティテスト。"""

    def test_concurrent_add_example(self):
        import threading

        collector = TrainingDataCollector()
        n_threads = 10
        examples_per_thread = 50
        barrier = threading.Barrier(n_threads)

        def worker(thread_id):
            barrier.wait()
            for i in range(examples_per_thread):
                ex = TrainingExample(
                    input_text=f"input-{thread_id}-{i}",
                    output_text=f"output-{thread_id}-{i}",
                    source="test",
                    quality_score=0.8,
                )
                collector.add_example(ex)

        threads = [
            threading.Thread(target=worker, args=(tid,))
            for tid in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert collector.example_count == n_threads * examples_per_thread
