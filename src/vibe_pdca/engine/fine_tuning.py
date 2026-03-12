"""ファインチューニングパイプライン – PDCAサイクルの学習データ収集とモデル微調整管理。

Proposal 27: Fine-Tuning Pipeline。

入力: 承認済みPR・成功プラン・高評価レビューなどの学習データ
出力: JSONL データセット・ジョブ管理・モデル比較結果
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# データクラス
# ============================================================


@dataclass
class TrainingExample:
    """学習データの1例。"""

    input_text: str
    output_text: str
    source: str  # "approved_pr", "successful_plan", "high_rating_review"
    quality_score: float = 0.0
    created_at: float = 0.0


@dataclass
class DatasetStats:
    """データセットの統計情報。"""

    total_examples: int
    source_distribution: dict[str, int] = field(default_factory=dict)
    avg_quality: float = 0.0
    oldest: float = 0.0
    newest: float = 0.0


@dataclass
class FineTuneConfig:
    """ファインチューニング設定。"""

    base_model: str
    dataset_min_size: int = 100
    learning_rate: float = 2e-5
    epochs: int = 3
    lora_rank: int = 16
    validation_split: float = 0.1


@dataclass
class FineTuneJob:
    """ファインチューニングジョブ。"""

    job_id: str
    status: str  # "pending", "running", "completed", "failed"
    config: FineTuneConfig
    started_at: float | None = None
    completed_at: float | None = None
    metrics: dict[str, float] = field(default_factory=dict)


# ============================================================
# TrainingDataCollector – 学習データ収集
# ============================================================


class TrainingDataCollector:
    """PDCAサイクルから学習データを収集・管理する。"""

    def __init__(self) -> None:
        self._examples: list[TrainingExample] = []
        self._lock = threading.Lock()

    def add_example(self, example: TrainingExample) -> None:
        """学習データを追加する。

        Parameters
        ----------
        example : TrainingExample
            追加する学習データ。
        """
        with self._lock:
            self._examples.append(example)
        logger.debug(
            "学習データ追加: source=%s, quality=%.2f",
            example.source,
            example.quality_score,
        )

    def get_examples(
        self,
        source: str | None = None,
        min_quality: float = 0.0,
    ) -> list[TrainingExample]:
        """条件に一致する学習データを取得する。

        Parameters
        ----------
        source : str | None
            フィルタするソース名。None で全ソース。
        min_quality : float
            最低品質スコア。

        Returns
        -------
        list[TrainingExample]
            条件に一致する学習データのリスト。
        """
        with self._lock:
            results: list[TrainingExample] = []
            for ex in self._examples:
                if source is not None and ex.source != source:
                    continue
                if ex.quality_score < min_quality:
                    continue
                results.append(ex)
            return results

    def get_stats(self) -> DatasetStats:
        """データセットの統計情報を返す。

        Returns
        -------
        DatasetStats
            統計情報。
        """
        with self._lock:
            if not self._examples:
                return DatasetStats(total_examples=0)

            source_dist: dict[str, int] = {}
            total_quality = 0.0
            oldest = self._examples[0].created_at
            newest = self._examples[0].created_at

            for ex in self._examples:
                source_dist[ex.source] = source_dist.get(ex.source, 0) + 1
                total_quality += ex.quality_score
                if ex.created_at < oldest:
                    oldest = ex.created_at
                if ex.created_at > newest:
                    newest = ex.created_at

            return DatasetStats(
                total_examples=len(self._examples),
                source_distribution=source_dist,
                avg_quality=total_quality / len(self._examples),
                oldest=oldest,
                newest=newest,
            )

    def export_jsonl(self, min_quality: float = 0.5) -> list[dict[str, str]]:
        """JSONL互換の辞書リストをエクスポートする。

        Parameters
        ----------
        min_quality : float
            エクスポート対象の最低品質スコア。

        Returns
        -------
        list[dict[str, str]]
            JSONL互換の辞書リスト。
        """
        filtered = self.get_examples(min_quality=min_quality)
        result: list[dict[str, str]] = []
        for ex in filtered:
            result.append({
                "input": ex.input_text,
                "output": ex.output_text,
            })
        logger.info("JSONL エクスポート: %d 件", len(result))
        return result

    @property
    def example_count(self) -> int:
        """登録済み学習データ数。"""
        with self._lock:
            return len(self._examples)


# ============================================================
# FineTuneManager – ファインチューニングジョブ管理
# ============================================================


class FineTuneManager:
    """ファインチューニングジョブのライフサイクルを管理する。"""

    def __init__(self, collector: TrainingDataCollector) -> None:
        self._collector = collector
        self._jobs: dict[str, FineTuneJob] = {}
        self._lock = threading.Lock()

    def is_ready(self, min_examples: int = 100) -> bool:
        """ファインチューニングに十分なデータがあるか判定する。

        Parameters
        ----------
        min_examples : int
            必要最低限の学習データ数。

        Returns
        -------
        bool
            十分なデータがある場合 True。
        """
        count = self._collector.example_count
        ready = count >= min_examples
        if not ready:
            logger.info(
                "データ不足: %d / %d 件", count, min_examples
            )
        return ready

    def create_job(self, config: FineTuneConfig) -> FineTuneJob:
        """新しいファインチューニングジョブを作成する。

        Parameters
        ----------
        config : FineTuneConfig
            ジョブの設定。

        Returns
        -------
        FineTuneJob
            作成されたジョブ。
        """
        job_id = uuid.uuid4().hex[:12]
        job = FineTuneJob(
            job_id=job_id,
            status="pending",
            config=config,
            started_at=time.time(),
        )
        with self._lock:
            self._jobs[job_id] = job
        logger.info("ジョブ作成: %s (model=%s)", job_id, config.base_model)
        return job

    def get_job(self, job_id: str) -> FineTuneJob | None:
        """ジョブIDでジョブを取得する。

        Parameters
        ----------
        job_id : str
            ジョブID。

        Returns
        -------
        FineTuneJob | None
            ジョブが存在しない場合は None。
        """
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[FineTuneJob]:
        """全ジョブを返す。

        Returns
        -------
        list[FineTuneJob]
            ジョブのリスト。
        """
        with self._lock:
            return list(self._jobs.values())

    def validate_dataset(
        self, min_quality: float = 0.5
    ) -> dict[str, Any]:
        """データセットの妥当性を検証する。

        Parameters
        ----------
        min_quality : float
            最低品質スコア。

        Returns
        -------
        dict[str, Any]
            検証レポート。
        """
        stats = self._collector.get_stats()
        qualified = self._collector.get_examples(min_quality=min_quality)
        qualified_count = len(qualified)

        issues: list[str] = []
        if stats.total_examples == 0:
            issues.append("学習データが存在しません")
        if qualified_count < 10:
            issues.append(
                f"品質基準を満たすデータが少なすぎます ({qualified_count} 件)"
            )
        if stats.source_distribution:
            sources = list(stats.source_distribution.keys())
            if len(sources) < 2:
                issues.append("データソースが単一です。多様なソースを推奨します")

        report: dict[str, Any] = {
            "total_examples": stats.total_examples,
            "qualified_examples": qualified_count,
            "avg_quality": round(stats.avg_quality, 4),
            "source_distribution": stats.source_distribution,
            "issues": issues,
            "is_valid": len(issues) == 0,
        }
        logger.info("データセット検証完了: valid=%s", report["is_valid"])
        return report


# ============================================================
# ModelComparator – モデル比較
# ============================================================


class ModelComparator:
    """複数モデルの性能を比較する。"""

    def __init__(self) -> None:
        self._results: dict[str, dict[str, list[float]]] = {}
        self._lock = threading.Lock()

    def add_result(
        self, model_name: str, task_type: str, score: float
    ) -> None:
        """評価結果を追加する。

        Parameters
        ----------
        model_name : str
            モデル名。
        task_type : str
            タスクタイプ。
        score : float
            スコア。
        """
        with self._lock:
            if model_name not in self._results:
                self._results[model_name] = {}
            if task_type not in self._results[model_name]:
                self._results[model_name][task_type] = []
            self._results[model_name][task_type].append(score)
        logger.debug(
            "結果追加: model=%s, task=%s, score=%.4f",
            model_name,
            task_type,
            score,
        )

    def compare(
        self, model_a: str, model_b: str
    ) -> dict[str, Any]:
        """2つのモデルの性能を比較する。

        Parameters
        ----------
        model_a : str
            比較対象モデルA。
        model_b : str
            比較対象モデルB。

        Returns
        -------
        dict[str, Any]
            比較サマリー。
        """
        scores_a = self._results.get(model_a, {})
        scores_b = self._results.get(model_b, {})
        all_tasks = sorted(set(list(scores_a.keys()) + list(scores_b.keys())))

        task_comparison: dict[str, dict[str, float]] = {}
        wins_a = 0
        wins_b = 0

        for task in all_tasks:
            avg_a = self._avg(scores_a.get(task, []))
            avg_b = self._avg(scores_b.get(task, []))
            task_comparison[task] = {
                model_a: round(avg_a, 4),
                model_b: round(avg_b, 4),
            }
            if avg_a > avg_b:
                wins_a += 1
            elif avg_b > avg_a:
                wins_b += 1

        winner = model_a if wins_a > wins_b else model_b if wins_b > wins_a else "tie"
        return {
            "model_a": model_a,
            "model_b": model_b,
            "task_comparison": task_comparison,
            "wins": {model_a: wins_a, model_b: wins_b},
            "winner": winner,
        }

    def get_best_model(self, task_type: str) -> str | None:
        """指定タスクタイプで最も高性能なモデルを返す。

        Parameters
        ----------
        task_type : str
            タスクタイプ。

        Returns
        -------
        str | None
            最高スコアのモデル名。データがない場合は None。
        """
        best_model: str | None = None
        best_avg = -1.0

        for model_name, tasks in self._results.items():
            if task_type in tasks:
                avg = self._avg(tasks[task_type])
                if avg > best_avg:
                    best_avg = avg
                    best_model = model_name

        return best_model

    # ── 内部メソッド ──

    @staticmethod
    def _avg(values: list[float]) -> float:
        """リストの平均値を返す（空なら 0.0）。"""
        if not values:
            return 0.0
        return sum(values) / len(values)
