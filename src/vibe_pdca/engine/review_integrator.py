"""レビュー統合 – 5ペルソナの指摘を重複排除・優先度算出・対立解消する。

M2 タスク 2-5: 要件定義書 §8.3 準拠。

統合ルール:
  - 重複排除: 近似一致でクラスタリング。統合後も出典を追跡可能
  - 優先度: 重大度 × 確信度 × ペルソナ重み で算出
  - 対立解消: 矛盾はPMにエスカレーション
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from vibe_pdca.models.pdca import ReviewFinding, ReviewSummary, Severity

logger = logging.getLogger(__name__)

# --- 5ペルソナの重み: 指摘の優先度計算に使用（1.0が最大） ---
# ペルソナ重み（§8.3 初期値）
DEFAULT_PERSONA_WEIGHTS: dict[str, float] = {
    "programmer": 1.00,
    "pm": 0.95,
    "designer": 0.85,
    "user": 0.85,
    "scribe": 0.80,
}

# 重大度のスコア変換: blocker（致命的）=1.0, major（重要）=0.7, minor（軽微）=0.3
# 重大度スコア
_SEVERITY_SCORES: dict[Severity, float] = {
    Severity.BLOCKER: 1.0,
    Severity.MAJOR: 0.7,
    Severity.MINOR: 0.3,
}

# 2つの指摘が65%以上類似していれば「重複」とみなしてクラスタリング
# 重複判定の類似度閾値
_SIMILARITY_THRESHOLD = 0.65


@dataclass
class PrioritizedFinding:
    """優先度付きレビュー指摘。"""

    finding: ReviewFinding
    priority_score: float
    cluster_id: int
    is_representative: bool = True
    sources: list[str] = field(default_factory=list)


@dataclass
class ConflictGroup:
    """対立している指摘グループ。"""

    findings: list[ReviewFinding]
    description: str
    escalation_required: bool = False


# --- レビュー統合エンジン: 5ペルソナの指摘を統合→重複排除→優先度付け→対立解消 ---
class ReviewIntegrator:
    """5ペルソナのレビュー指摘を統合する（§8.3）。

    Parameters
    ----------
    persona_weights : dict | None
        ペルソナ重み。Noneの場合はデフォルト値を使用。
    similarity_threshold : float
        重複判定の類似度閾値（0.0〜1.0）。
    """

    def __init__(
        self,
        persona_weights: dict[str, float] | None = None,
        similarity_threshold: float = _SIMILARITY_THRESHOLD,
    ) -> None:
        self._weights = dict(persona_weights or DEFAULT_PERSONA_WEIGHTS)
        self._similarity_threshold = similarity_threshold

    @property
    def persona_weights(self) -> dict[str, float]:
        """現在のペルソナ重みを返す。"""
        return dict(self._weights)

    def adjust_weight(
        self,
        persona: str,
        delta: float,
    ) -> float:
        """ペルソナ重みを調整する（§8.3: ±0.05以内、下限0.50）。

        Parameters
        ----------
        persona : str
            対象ペルソナ名。
        delta : float
            調整量（±0.05以内に制限される）。

        Returns
        -------
        float
            調整後の重み。

        Raises
        ------
        ValueError
            不明なペルソナの場合。
        """
        if persona not in self._weights:
            raise ValueError(f"不明なペルソナ: {persona}")

        # 調整幅を±0.05に制限
        clamped_delta = max(-0.05, min(0.05, delta))
        new_weight = self._weights[persona] + clamped_delta

        # 下限0.50を保証
        new_weight = max(0.50, min(1.00, new_weight))
        self._weights[persona] = new_weight

        logger.info(
            "ペルソナ重み調整: %s %.2f → %.2f (delta=%.3f)",
            persona, self._weights[persona] - clamped_delta, new_weight,
            clamped_delta,
        )
        return new_weight

    def integrate(
        self,
        findings: list[ReviewFinding],
    ) -> IntegrationResult:
        """レビュー指摘を統合する。

        Parameters
        ----------
        findings : list[ReviewFinding]
            5ペルソナからの全指摘。

        Returns
        -------
        IntegrationResult
            統合結果（重複排除済み・優先度付き）。
        """
        if not findings:
            return IntegrationResult(
                prioritized=[],
                conflicts=[],
                summary=ReviewSummary(),
            )

        # 1. 重複排除（クラスタリング）
        clusters = self._cluster_findings(findings)

        # 2. 優先度算出
        prioritized = self._calculate_priorities(clusters)

        # 3. 対立検出
        conflicts = self._detect_conflicts(clusters)

        # 4. サマリ生成
        summary = self._build_summary(prioritized)

        logger.info(
            "レビュー統合: 入力%d件 → %d件 (クラスタ%d, 対立%d件)",
            len(findings), len(prioritized), len(clusters),
            len(conflicts),
        )

        return IntegrationResult(
            prioritized=prioritized,
            conflicts=conflicts,
            summary=summary,
        )

    def _cluster_findings(
        self,
        findings: list[ReviewFinding],
    ) -> list[list[ReviewFinding]]:
        """指摘を類似度でクラスタリングする。"""
        used = [False] * len(findings)
        clusters: list[list[ReviewFinding]] = []

        for i, f1 in enumerate(findings):
            if used[i]:
                continue
            cluster = [f1]
            used[i] = True

            for j in range(i + 1, len(findings)):
                if used[j]:
                    continue
                if self._is_similar(f1, findings[j]):
                    cluster.append(findings[j])
                    used[j] = True

            clusters.append(cluster)

        return clusters

    def _is_similar(self, a: ReviewFinding, b: ReviewFinding) -> bool:
        """2つの指摘が類似しているかどうかを判定する。"""
        # 同じファイル・同じカテゴリの場合、説明の類似度を確認
        if a.category != b.category:
            return False

        # ファイルパスが指定されている場合、同じファイルであること
        if a.file_path and b.file_path and a.file_path != b.file_path:
            return False

        ratio = SequenceMatcher(
            None, a.description, b.description,
        ).ratio()
        return ratio >= self._similarity_threshold

    def _calculate_priorities(
        self,
        clusters: list[list[ReviewFinding]],
    ) -> list[PrioritizedFinding]:
        """クラスタごとに優先度スコアを算出する。

        優先度 = 重大度 × 確信度 × ペルソナ重み（§8.3）
        同一クラスタ内の最大スコアを代表値とする。
        """
        result: list[PrioritizedFinding] = []

        for cluster_idx, cluster in enumerate(clusters):
            best_score = 0.0
            best_finding: ReviewFinding | None = None

            for finding in cluster:
                severity_score = _SEVERITY_SCORES.get(
                    finding.severity, 0.5,
                )
                persona_weight = self._weights.get(
                    finding.reviewer_role, 0.80,
                )
                score = severity_score * finding.confidence * persona_weight

                if score > best_score:
                    best_score = score
                    best_finding = finding

            if best_finding:
                sources = [f.reviewer_role for f in cluster]
                result.append(PrioritizedFinding(
                    finding=best_finding,
                    priority_score=round(best_score, 4),
                    cluster_id=cluster_idx,
                    is_representative=True,
                    sources=sources,
                ))

        # 優先度降順ソート
        result.sort(key=lambda p: p.priority_score, reverse=True)
        return result

    def _detect_conflicts(
        self,
        clusters: list[list[ReviewFinding]],
    ) -> list[ConflictGroup]:
        """対立する指摘を検出する。

        同一ファイル・同一カテゴリで重大度が大きく異なる指摘を対立と判定。
        """
        conflicts: list[ConflictGroup] = []

        # ファイルパス × カテゴリでグルーピング
        by_file_cat: dict[tuple[str, str], list[ReviewFinding]] = defaultdict(list)
        for cluster in clusters:
            for finding in cluster:
                key = (finding.file_path or "", finding.category.value)
                by_file_cat[key].append(finding)

        for (file_path, category), group in by_file_cat.items():
            if len(group) < 2:
                continue

            # 重大度の差異を確認
            severities = {f.severity for f in group}
            if Severity.BLOCKER in severities and Severity.MINOR in severities:
                conflicts.append(ConflictGroup(
                    findings=group,
                    description=(
                        f"ファイル「{file_path or '不明'}」の"
                        f"「{category}」カテゴリで"
                        f"重大度が大きく異なる指摘が存在"
                    ),
                    escalation_required=True,
                ))

        return conflicts

    def _build_summary(
        self,
        prioritized: list[PrioritizedFinding],
    ) -> ReviewSummary:
        """統合結果のサマリを構築する。"""
        findings = [p.finding for p in prioritized]
        blocker_count = sum(
            1 for f in findings if f.severity == Severity.BLOCKER
        )
        major_count = sum(
            1 for f in findings if f.severity == Severity.MAJOR
        )
        minor_count = sum(
            1 for f in findings if f.severity == Severity.MINOR
        )

        return ReviewSummary(
            findings=findings,
            blocker_count=blocker_count,
            major_count=major_count,
            minor_count=minor_count,
            dod_achieved=blocker_count == 0,
            dod_unmet_reasons=(
                [f"ブロッカー{blocker_count}件未解消"]
                if blocker_count > 0 else []
            ),
        )


@dataclass
class IntegrationResult:
    """レビュー統合の結果。"""

    prioritized: list[PrioritizedFinding]
    conflicts: list[ConflictGroup]
    summary: ReviewSummary

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    @property
    def escalation_needed(self) -> bool:
        return any(c.escalation_required for c in self.conflicts)

    def to_dict(self) -> dict[str, Any]:
        """辞書に変換する（監査ログ用）。"""
        return {
            "finding_count": len(self.prioritized),
            "conflict_count": len(self.conflicts),
            "escalation_needed": self.escalation_needed,
            "blocker_count": self.summary.blocker_count,
            "major_count": self.summary.major_count,
            "minor_count": self.summary.minor_count,
            "dod_achieved": self.summary.dod_achieved,
        }
