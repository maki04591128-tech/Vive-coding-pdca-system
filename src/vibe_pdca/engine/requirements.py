"""要件定義確定フロー – 欠落検出・差分質問・5ペルソナレビュー→PDCA開始。

M2 タスク 2-10: 要件定義書 §10.1, §7.3 準拠。

フロー:
  ユーザーが入力 → システムが欠落検出・差分質問 →
  ユーザーが「要件定義完了」ボタン → 5ペルソナレビュー →
  blockerなければPDCA開始
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from vibe_pdca.models.pdca import Goal, ReviewFinding, Severity

logger = logging.getLogger(__name__)


class RequirementStatus(StrEnum):
    """要件定義の状態。"""

    DRAFT = "draft"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"


class GapCategory(StrEnum):
    """欠落カテゴリ。"""

    MISSING_ACCEPTANCE = "missing_acceptance"
    AMBIGUOUS_CONSTRAINT = "ambiguous_constraint"
    MISSING_PROHIBITION = "missing_prohibition"
    MISSING_PRIORITY = "missing_priority"
    SCOPE_TOO_LARGE = "scope_too_large"
    MISSING_DEPENDENCY = "missing_dependency"


@dataclass
class GapItem:
    """欠落検出の1件。"""

    category: GapCategory
    description: str
    suggestion: str = ""
    resolved: bool = False


@dataclass
class DiffQuestion:
    """差分質問の1件。"""

    id: str = field(default_factory=lambda: f"dq-{uuid.uuid4().hex[:8]}")
    question: str = ""
    context: str = ""
    answer: str | None = None
    resolved: bool = False


@dataclass
class RequirementReviewResult:
    """要件レビューの結果。"""

    status: RequirementStatus
    findings: list[ReviewFinding] = field(default_factory=list)
    blocker_count: int = 0
    can_start_pdca: bool = False
    unresolved_gaps: list[GapItem] = field(default_factory=list)


class RequirementFinalizer:
    """要件定義確定フローを管理する。

    ゴール入力を受け取り、欠落検出・差分質問を生成し、
    5ペルソナレビュー後にPDCA開始可否を判定する。
    """

    def __init__(self) -> None:
        self._status = RequirementStatus.DRAFT
        self._gaps: list[GapItem] = []
        self._questions: list[DiffQuestion] = []

    @property
    def status(self) -> RequirementStatus:
        return self._status

    @property
    def gaps(self) -> list[GapItem]:
        return list(self._gaps)

    @property
    def questions(self) -> list[DiffQuestion]:
        return list(self._questions)

    def detect_gaps(self, goal: Goal) -> list[GapItem]:
        """ゴール入力から欠落を検出する（§B4: 差分質問）。

        Parameters
        ----------
        goal : Goal
            ユーザーが入力したゴール。

        Returns
        -------
        list[GapItem]
            検出された欠落リスト。
        """
        gaps: list[GapItem] = []

        # 受入条件が少なすぎる
        if len(goal.acceptance_criteria) < 3:
            gaps.append(GapItem(
                category=GapCategory.MISSING_ACCEPTANCE,
                description="受入条件が3件未満です",
                suggestion="受入条件を追加してください（推奨: 3件以上）",
            ))

        # 制約が空
        if not goal.constraints:
            gaps.append(GapItem(
                category=GapCategory.AMBIGUOUS_CONSTRAINT,
                description="制約が未定義です",
                suggestion="技術スタック・パフォーマンス要件・セキュリティ要件を記述してください",
            ))

        # 禁止事項が空
        if not goal.prohibitions:
            gaps.append(GapItem(
                category=GapCategory.MISSING_PROHIBITION,
                description="禁止事項が未定義です",
                suggestion="やってはいけないことを明記してください",
            ))

        # 受入条件が曖昧（機械判定不能な記述の検出）
        for i, criterion in enumerate(goal.acceptance_criteria):
            if len(criterion) < 10:
                gaps.append(GapItem(
                    category=GapCategory.AMBIGUOUS_CONSTRAINT,
                    description=f"受入条件 {i + 1} が短すぎます: '{criterion}'",
                    suggestion="具体的で機械判定可能な記述にしてください",
                ))

        self._gaps = gaps
        if gaps:
            self._status = RequirementStatus.NEEDS_REVISION
        return gaps

    def generate_diff_questions(
        self,
        goal: Goal,
    ) -> list[DiffQuestion]:
        """欠落に基づく差分質問を生成する。

        Parameters
        ----------
        goal : Goal
            対象ゴール。

        Returns
        -------
        list[DiffQuestion]
            差分質問リスト。
        """
        questions: list[DiffQuestion] = []

        for gap in self._gaps:
            if gap.resolved:
                continue
            questions.append(DiffQuestion(
                question=f"{gap.description} — {gap.suggestion}",
                context=f"カテゴリ: {gap.category.value}",
            ))

        self._questions = questions
        return questions

    def answer_question(
        self,
        question_id: str,
        answer: str,
    ) -> bool:
        """差分質問に回答する。

        Returns
        -------
        bool
            回答が受理された場合True。
        """
        for q in self._questions:
            if q.id == question_id:
                q.answer = answer
                q.resolved = True
                return True
        return False

    def finalize(
        self,
        goal: Goal,
        review_findings: list[ReviewFinding] | None = None,
    ) -> RequirementReviewResult:
        """要件定義を確定する（5ペルソナレビュー後）。

        Parameters
        ----------
        goal : Goal
            確定対象のゴール。
        review_findings : list[ReviewFinding] | None
            5ペルソナレビューの指摘。

        Returns
        -------
        RequirementReviewResult
            確定結果。blockerがなければPDCA開始可。
        """
        findings = review_findings or []
        blocker_count = sum(
            1 for f in findings if f.severity == Severity.BLOCKER
        )
        unresolved = [g for g in self._gaps if not g.resolved]

        can_start = blocker_count == 0 and len(unresolved) == 0

        if can_start:
            self._status = RequirementStatus.APPROVED
        else:
            self._status = RequirementStatus.NEEDS_REVISION

        logger.info(
            "要件定義確定: status=%s, blockers=%d, unresolved_gaps=%d",
            self._status.value, blocker_count, len(unresolved),
        )

        return RequirementReviewResult(
            status=self._status,
            findings=findings,
            blocker_count=blocker_count,
            can_start_pdca=can_start,
            unresolved_gaps=unresolved,
        )
