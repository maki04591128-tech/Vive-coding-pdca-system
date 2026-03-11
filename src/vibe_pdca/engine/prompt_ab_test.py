"""プロンプト A/B テストによる品質・コスト比較。

提案6: プロンプトのバリアントを A/B テストで比較し、
統計的に優位なテンプレートを選択する仕組みを提供する。

- プロンプトバリアントの定義
- A/B テスト設定と結果記録
- 統計的な比較分析
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# プロンプトバリアント
# ============================================================


# A/Bテストで比較する2種類のプロンプト（指示文）のうちの1つ
@dataclass
class PromptVariant:
    """A/B テストで使用するプロンプトテンプレートの1バリアント。"""

    variant_id: str
    template_content: str
    version: str
    created_at: float = field(default_factory=time.time)


# ============================================================
# A/B テスト設定
# ============================================================


@dataclass
class ABTestConfig:
    """A/B テストの設定。"""

    test_id: str
    variant_a: PromptVariant
    variant_b: PromptVariant
    split_ratio: float = 0.5


# ============================================================
# A/B テスト結果
# ============================================================


@dataclass
class ABTestResult:
    """A/B テストの1回分の実行結果。"""

    test_id: str
    variant_id: str
    cycle_number: int
    success: bool
    quality_score: float
    cost_usd: float


# ============================================================
# A/B テストマネージャ
# ============================================================


# --- A/Bテストマネージャー: 2種類のプロンプトの効果を統計的に比較する仕組み ---
class ABTestManager:
    """A/B テストの作成・バリアント割当・結果記録を管理する。"""

    def __init__(self) -> None:
        self._configs: dict[str, ABTestConfig] = {}
        self._results: dict[str, list[ABTestResult]] = {}

    def create_test(self, config: ABTestConfig) -> str:
        """テストを作成し、テストIDを返す。"""
        self._configs[config.test_id] = config
        self._results.setdefault(config.test_id, [])
        logger.info("A/Bテスト作成: %s", config.test_id)
        return config.test_id

    def assign_variant(
        self, test_id: str, cycle_number: int,
    ) -> PromptVariant:
        """サイクル番号に基づいてバリアントを割り当てる。

        test_id と cycle_number のハッシュ値で決定的に振り分ける。
        """
        config = self._configs[test_id]
        # ハッシュ値で決定的に振り分け（同じサイクル番号なら常に同じバリアントが選ばれる）
        raw = f"{test_id}:{cycle_number}"
        digest = hashlib.sha256(raw.encode()).hexdigest()
        ratio = int(digest[:8], 16) / 0xFFFFFFFF
        chosen = config.variant_a if ratio < config.split_ratio else config.variant_b
        logger.info(
            "バリアント割当: test=%s cycle=%d → %s",
            test_id, cycle_number, chosen.variant_id,
        )
        return chosen

    def record_result(self, result: ABTestResult) -> None:
        """テスト結果を記録する。"""
        self._results.setdefault(result.test_id, []).append(result)
        logger.info(
            "結果記録: test=%s variant=%s score=%.2f",
            result.test_id, result.variant_id, result.quality_score,
        )

    def get_results(self, test_id: str) -> list[ABTestResult]:
        """指定テストの全結果を返す。"""
        return list(self._results.get(test_id, []))

    def get_winner(
        self, test_id: str, min_samples: int = 5,
    ) -> str | None:
        """統計的に優位なバリアントIDを返す。

        各バリアントの結果が min_samples 未満の場合は None を返す。
        """
        config = self._configs.get(test_id)
        if config is None:
            return None
        results = self._results.get(test_id, [])
        a_id = config.variant_a.variant_id
        b_id = config.variant_b.variant_id
        a_scores = [
            r.quality_score for r in results if r.variant_id == a_id
        ]
        b_scores = [
            r.quality_score for r in results if r.variant_id == b_id
        ]
        if len(a_scores) < min_samples or len(b_scores) < min_samples:
            return None
        mean_a = sum(a_scores) / len(a_scores)
        mean_b = sum(b_scores) / len(b_scores)
        winner = a_id if mean_a >= mean_b else b_id
        logger.info(
            "勝者判定: test=%s → %s (A=%.3f, B=%.3f)",
            test_id, winner, mean_a, mean_b,
        )
        return winner

    def list_active_tests(self) -> list[str]:
        """アクティブなテストIDのリストを返す。"""
        return sorted(self._configs.keys())


# ============================================================
# 統計分析
# ============================================================


# --- 統計分析: Welchのt検定でA/Bの品質スコアに有意差があるか判定 ---
class StatisticalAnalyzer:
    """A/B テスト結果の統計的比較を行う。"""

    def compare(
        self,
        results_a: list[ABTestResult],
        results_b: list[ABTestResult],
    ) -> dict[str, Any]:
        """2グループの品質スコアを比較し統計情報を返す。

        Returns
        -------
        dict
            mean_a, mean_b, difference, significant (bool) を含む辞書。
        """
        scores_a = [r.quality_score for r in results_a]
        scores_b = [r.quality_score for r in results_b]
        mean_a = sum(scores_a) / len(scores_a) if scores_a else 0.0
        mean_b = sum(scores_b) / len(scores_b) if scores_b else 0.0
        difference = mean_a - mean_b
        significant = self._is_significant(scores_a, scores_b)
        return {
            "mean_a": mean_a,
            "mean_b": mean_b,
            "difference": difference,
            "significant": significant,
        }

    @staticmethod
    def _is_significant(
        scores_a: list[float], scores_b: list[float],
    ) -> bool:
        """簡易的な有意差判定（Welch の t 検定近似）。"""
        if len(scores_a) < 2 or len(scores_b) < 2:
            return False
        mean_a = sum(scores_a) / len(scores_a)
        mean_b = sum(scores_b) / len(scores_b)
        var_a = sum((x - mean_a) ** 2 for x in scores_a) / (
            len(scores_a) - 1
        )
        var_b = sum((x - mean_b) ** 2 for x in scores_b) / (
            len(scores_b) - 1
        )
        # 標準誤差（SE）を計算し、t値が1.96を超えれば有意差あり（p < 0.05相当）
        se = math.sqrt(
            var_a / len(scores_a) + var_b / len(scores_b),
        )
        if se < 1e-12:
            return mean_a != mean_b
        t_stat = abs(mean_a - mean_b) / se
        # 自由度の近似値に基づく閾値（p < 0.05 相当: t > 1.96）
        return t_stat > 1.96
