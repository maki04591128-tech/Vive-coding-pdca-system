"""ユーザーフィードバック収集・満足度トラッキング。

Proposal 24: User Feedback Collection and Satisfaction Tracking。

- ユーザーからのフィードバックをカテゴリ別に収集
- 満足度スコア（NPS含む）を算出しトレンドを追跡
- 学習ループへのフィードバック統合ブリッジを提供
"""

from __future__ import annotations

import enum
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# 定数
# ============================================================

# --- フィードバック評価の範囲: 1（最低）〜 5（最高）の5段階 ---
RATING_MIN = 1
RATING_MAX = 5

# NPS（ネットプロモータースコア）: 推奨者(4-5) - 批判者(1-2) で満足度を測定
NPS_PROMOTER_THRESHOLD = 4  # 4-5 = promoter
NPS_DETRACTOR_THRESHOLD = 2  # 1-2 = detractor

DEFAULT_WINDOW = 10
DEFAULT_MIN_ENTRIES = 5

LOW_SATISFACTION_THRESHOLD = 3.0


# ============================================================
# Enum
# ============================================================


# フィードバックの分類カテゴリ（コード品質・デザイン・テスト・文書・性能・使いやすさ）
class FeedbackCategory(enum.StrEnum):
    """フィードバックカテゴリ。"""

    CODE_QUALITY = "code_quality"
    DESIGN = "design"
    TEST = "test"
    DOCUMENTATION = "documentation"
    PERFORMANCE = "performance"
    USABILITY = "usability"


# ============================================================
# データクラス
# ============================================================


@dataclass
class FeedbackEntry:
    """個別フィードバックエントリ。"""

    cycle_number: int
    rating: int
    category: FeedbackCategory
    comment: str = ""
    submitted_by: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not (RATING_MIN <= self.rating <= RATING_MAX):
            raise ValueError(
                f"rating は {RATING_MIN}〜{RATING_MAX} の範囲で指定してください: {self.rating}"
            )


@dataclass
class SatisfactionScore:
    """満足度スコア集計結果。"""

    average_rating: float = 0.0
    total_responses: int = 0
    category_scores: dict[str, float] = field(default_factory=dict)
    nps_score: float = 0.0
    trend: str = "stable"


# ============================================================
# FeedbackCollector – フィードバック収集
# ============================================================


# --- フィードバック収集: ユーザーの評価とコメントを記録・分析する仕組み ---
class FeedbackCollector:
    """フィードバック収集器。

    ユーザーからのフィードバックを蓄積し、サイクル・カテゴリ別に
    取得できるようにする。
    """

    def __init__(self) -> None:
        self._entries: list[FeedbackEntry] = []

    # ----- 登録 -----

    def submit_feedback(self, entry: FeedbackEntry) -> None:
        """フィードバックを登録する。"""
        self._entries.append(entry)
        logger.info(
            "フィードバック登録: id=%s, cycle=%d, category=%s, rating=%d",
            entry.id,
            entry.cycle_number,
            entry.category.value,
            entry.rating,
        )

    # ----- 取得 -----

    def get_feedback(
        self, cycle_number: int | None = None
    ) -> list[FeedbackEntry]:
        """フィードバック一覧を返す。

        Parameters
        ----------
        cycle_number : int | None
            指定時はそのサイクルのみ抽出。None で全件返却。
        """
        if cycle_number is None:
            return list(self._entries)
        return [e for e in self._entries if e.cycle_number == cycle_number]

    def get_category_feedback(
        self, category: FeedbackCategory
    ) -> list[FeedbackEntry]:
        """カテゴリ別フィードバック一覧を返す。"""
        return [e for e in self._entries if e.category == category]

    # ----- プロパティ -----

    @property
    def feedback_count(self) -> int:
        """登録済みフィードバック件数。"""
        return len(self._entries)


# ============================================================
# SatisfactionTracker – 満足度追跡
# ============================================================


# --- 満足度トラッキング: 時系列の満足度変化を追跡しトレンドを検出 ---
class SatisfactionTracker:
    """満足度トラッカー。

    FeedbackCollector のデータを基に満足度スコアを算出し、
    NPSやトレンドを追跡する。
    """

    def __init__(self, collector: FeedbackCollector) -> None:
        self._collector = collector

    def calculate_satisfaction(
        self, window: int = DEFAULT_WINDOW
    ) -> SatisfactionScore:
        """直近 *window* 件のフィードバックから満足度スコアを算出する。

        Parameters
        ----------
        window : int
            直近何件を対象とするか。

        Returns
        -------
        SatisfactionScore
            算出された満足度スコア。
        """
        entries = self._collector.get_feedback()
        if not entries:
            return SatisfactionScore()

        recent = entries[-window:]
        avg = sum(e.rating for e in recent) / len(recent)
        cat_scores = self.get_category_breakdown()
        nps = self.calculate_nps()
        trend = self.get_trend(window)

        return SatisfactionScore(
            average_rating=round(avg, 2),
            total_responses=len(recent),
            category_scores=cat_scores,
            nps_score=nps,
            trend=trend,
        )

    def calculate_nps(self) -> float:
        """Net Promoter Score を算出する。

        promoter (rating >= 4) の割合 − detractor (rating <= 2) の割合を
        百分率 (-100〜100) で返す。
        """
        entries = self._collector.get_feedback()
        if not entries:
            return 0.0

        total = len(entries)
        promoters = sum(
            1 for e in entries if e.rating >= NPS_PROMOTER_THRESHOLD
        )
        detractors = sum(
            1 for e in entries if e.rating <= NPS_DETRACTOR_THRESHOLD
        )
        nps = ((promoters - detractors) / total) * 100
        return round(nps, 2)

    def get_trend(self, window: int = DEFAULT_WINDOW) -> str:
        """直近 *window* 件を前半・後半で比較しトレンドを判定する。

        Returns
        -------
        str
            ``"improving"`` / ``"declining"`` / ``"stable"``
        """
        entries = self._collector.get_feedback()
        if len(entries) < 2:
            return "stable"

        recent = entries[-window:]
        mid = len(recent) // 2
        if mid == 0:
            return "stable"

        first_half = recent[:mid]
        second_half = recent[mid:]

        avg_first = sum(e.rating for e in first_half) / len(first_half)
        avg_second = sum(e.rating for e in second_half) / len(second_half)

        diff = avg_second - avg_first
        if diff > 0.3:
            return "improving"
        if diff < -0.3:
            return "declining"
        return "stable"

    def get_category_breakdown(self) -> dict[str, float]:
        """カテゴリ別の平均スコアを返す。"""
        entries = self._collector.get_feedback()
        buckets: dict[str, list[int]] = {}
        for entry in entries:
            key = entry.category.value
            buckets.setdefault(key, []).append(entry.rating)

        return {
            cat: round(sum(ratings) / len(ratings), 2)
            for cat, ratings in buckets.items()
        }


# ============================================================
# FeedbackLearningBridge – 学習ループ統合
# ============================================================


class FeedbackLearningBridge:
    """フィードバックと学習ループの統合ブリッジ。

    収集したフィードバックを学習モジュール (learning.py) へ渡す
    形式に変換し、改善すべき領域を特定する。
    """

    def __init__(self, collector: FeedbackCollector) -> None:
        self._collector = collector

    def extract_improvement_areas(
        self, min_entries: int = DEFAULT_MIN_ENTRIES
    ) -> list[str]:
        """改善が必要なカテゴリを抽出する。

        平均スコアが *LOW_SATISFACTION_THRESHOLD* 未満のカテゴリを返す。
        十分なエントリ数がないカテゴリは除外する。

        Parameters
        ----------
        min_entries : int
            カテゴリごとの最低エントリ数。

        Returns
        -------
        list[str]
            改善が必要なカテゴリ名のリスト。
        """
        buckets: dict[str, list[int]] = {}
        for entry in self._collector.get_feedback():
            key = entry.category.value
            buckets.setdefault(key, []).append(entry.rating)

        areas: list[str] = []
        for cat, ratings in buckets.items():
            if len(ratings) >= min_entries:
                avg = sum(ratings) / len(ratings)
                if avg < LOW_SATISFACTION_THRESHOLD:
                    areas.append(cat)

        logger.info("改善領域抽出: %d 件", len(areas))
        return areas

    def generate_learning_input(self) -> dict[str, Any]:
        """学習モジュール向けの入力データを生成する。

        Returns
        -------
        dict[str, Any]
            learning.py が消費可能な辞書形式。
        """
        entries = self._collector.get_feedback()
        if not entries:
            return {
                "source": "user_feedback",
                "total_entries": 0,
                "average_rating": 0.0,
                "category_scores": {},
                "improvement_areas": [],
                "low_satisfaction_patterns": [],
            }

        avg = sum(e.rating for e in entries) / len(entries)
        tracker = SatisfactionTracker(self._collector)
        cat_scores = tracker.get_category_breakdown()
        areas = self.extract_improvement_areas()
        patterns = self.get_low_satisfaction_patterns()

        return {
            "source": "user_feedback",
            "total_entries": len(entries),
            "average_rating": round(avg, 2),
            "category_scores": cat_scores,
            "improvement_areas": areas,
            "low_satisfaction_patterns": patterns,
        }

    def get_low_satisfaction_patterns(self) -> list[dict[str, Any]]:
        """満足度の低いパターンを抽出する。

        カテゴリごとに平均スコアが *LOW_SATISFACTION_THRESHOLD* 未満の
        エントリを集約して返す。

        Returns
        -------
        list[dict[str, Any]]
            低満足度パターンのリスト。
        """
        buckets: dict[str, list[FeedbackEntry]] = {}
        for entry in self._collector.get_feedback():
            key = entry.category.value
            buckets.setdefault(key, []).append(entry)

        patterns: list[dict[str, Any]] = []
        for cat, cat_entries in buckets.items():
            avg = sum(e.rating for e in cat_entries) / len(cat_entries)
            if avg < LOW_SATISFACTION_THRESHOLD:
                patterns.append({
                    "category": cat,
                    "average_rating": round(avg, 2),
                    "entry_count": len(cat_entries),
                    "comments": [
                        e.comment for e in cat_entries if e.comment
                    ],
                })

        return patterns
