"""ACTフェーズ実行 – 採否判定・次サイクル方針決定・進捗レポート生成。

M2 タスク 2-4: 要件定義書 §6.5 準拠。

入力: 統合レビュー・DoD判定・失敗履歴
出力: 指摘の採否（理由付き）、次サイクルの方針、マイルストーン進捗の更新、進捗レポート
決定ログ必須項目: 決定（採否/延期/中止/縮退）・理由・影響範囲・再検討条件
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from vibe_pdca.engine.checker import CheckResult
from vibe_pdca.models.pdca import (
    Decision,
    DecisionType,
    Milestone,
)

logger = logging.getLogger(__name__)


@dataclass
class ProgressReport:
    """進捗レポート（§B1）。"""

    milestone_id: str
    milestone_title: str
    cycle_number: int
    decision_type: str
    dod_achieved: bool
    dod_progress: float  # 0.0 ~ 1.0
    completed_tasks: int
    total_tasks: int
    blocker_count: int
    summary: str
    next_action: str
    generated_at: float = field(default_factory=time.time)

    def to_markdown(self) -> str:
        """Markdown形式で進捗レポートを生成する。"""
        status_icon = "✅" if self.dod_achieved else "🔄"
        progress_bar = _progress_bar(self.dod_progress)

        return (
            f"## {status_icon} サイクル {self.cycle_number} 進捗レポート\n\n"
            f"**マイルストーン:** {self.milestone_title} (`{self.milestone_id}`)\n"
            f"**判定:** {self.decision_type}\n"
            f"**DoD達成:** {'はい' if self.dod_achieved else 'いいえ'}\n\n"
            f"### 進捗\n"
            f"- タスク: {self.completed_tasks}/{self.total_tasks} 完了\n"
            f"- DoD進捗: {progress_bar} {self.dod_progress:.0%}\n"
            f"- ブロッカー: {self.blocker_count}件\n\n"
            f"### サマリ\n{self.summary}\n\n"
            f"### 次のアクション\n{self.next_action}\n"
        )


def _progress_bar(ratio: float, width: int = 20) -> str:
    """テキストベースの進捗バーを生成する。"""
    filled = int(ratio * width)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"


# --- ACTフェーズ: レビュー結果を判断し、指摘の採否と次サイクルの方針を決定 ---
class ActDecisionMaker:
    """ACTフェーズの判定を行う。

    CHECKフェーズの結果を受けて、採否・次サイクル方針を決定する。
    """

    # ブロッカーがこの件数以上なら自動REJECT
    BLOCKER_THRESHOLD = 1
    # MAJOR指摘がこの件数以上なら自動DEFER
    MAJOR_THRESHOLD = 5
    # CI連続失敗がこの回数以上なら自動DEGRADE
    CI_FAILURE_THRESHOLD = 3

    def make_decision(
        self,
        check_result: CheckResult,
        failure_history: list[str] | None = None,
    ) -> Decision:
        """CHECKフェーズ結果に基づき判定を行う。

        Parameters
        ----------
        check_result : CheckResult
            CHECKフェーズの出力。
        failure_history : list[str] | None
            過去の失敗履歴（エラーキーのリスト）。

        Returns
        -------
        Decision
            ACT判定結果。
        """
        review = check_result.review_summary
        ci = check_result.ci_summary
        history = failure_history or []

        # 1. DoD達成 + CI通過 → ACCEPT
        if check_result.dod_achieved and ci.all_passed:
            return Decision(
                decision_type=DecisionType.ACCEPT,
                reason="DoD達成済み、CI全通過",
                impact_scope="マイルストーン進捗の更新",
                next_cycle_policy="次のマイルストーンへ進行",
            )

        # 2. ブロッカーあり → REJECT
        if review.blocker_count >= self.BLOCKER_THRESHOLD:
            return Decision(
                decision_type=DecisionType.REJECT,
                reason=f"ブロッカー{review.blocker_count}件が未解消",
                impact_scope="全ブロッカーの修正が必要",
                reconsider_condition="ブロッカーが0件になった場合",
                next_cycle_policy=(
                    f"ブロッカー{review.blocker_count}件の解消を最優先タスクとする"
                ),
            )

        # 3. CI失敗 + 同一エラー繰り返し → DEGRADE
        if not ci.all_passed and len(history) >= self.CI_FAILURE_THRESHOLD:
            return Decision(
                decision_type=DecisionType.DEGRADE,
                reason=f"CI失敗が継続（失敗履歴: {len(history)}件）",
                impact_scope="スコープ縮退を検討",
                reconsider_condition="CI安定化後",
                next_cycle_policy="スコープを縮小して安定性優先",
            )

        # 4. MAJOR指摘が多い → DEFER
        if review.major_count >= self.MAJOR_THRESHOLD:
            return Decision(
                decision_type=DecisionType.DEFER,
                reason=f"MAJOR指摘{review.major_count}件が残存",
                impact_scope="品質向上のための追加サイクル",
                reconsider_condition="MAJORが3件以下に減少した場合",
                next_cycle_policy="MAJOR指摘の優先対応",
            )

        # 5. CI失敗だが改善傾向 → REJECT（再試行）
        if not ci.all_passed:
            return Decision(
                decision_type=DecisionType.REJECT,
                reason=f"CI失敗: {ci.failed_jobs}ジョブ",
                impact_scope="CI修正",
                reconsider_condition="CI全通過後",
                next_cycle_policy="CI失敗の原因を解消",
            )

        # 6. DoD未達だがCI通過 → REJECT（改善継続）
        return Decision(
            decision_type=DecisionType.REJECT,
            reason=f"DoD未達: {', '.join(check_result.dod_unmet_reasons[:3])}",
            impact_scope="DoD未達項目の対応",
            reconsider_condition="全DoD項目達成後",
            next_cycle_policy="DoD未達項目の優先対応",
        )

    def generate_progress_report(
        self,
        milestone: Milestone,
        cycle_number: int,
        decision: Decision,
        check_result: CheckResult,
    ) -> ProgressReport:
        """進捗レポートを生成する（§B1）。

        Parameters
        ----------
        milestone : Milestone
            対象マイルストーン。
        cycle_number : int
            サイクル番号。
        decision : Decision
            判定結果。
        check_result : CheckResult
            CHECK結果。

        Returns
        -------
        ProgressReport
            進捗レポート。
        """
        # DoD進捗率の算出
        total_dod = len(milestone.dod)
        achieved_dod = sum(1 for d in milestone.dod if d.achieved)
        dod_progress = achieved_dod / total_dod if total_dod > 0 else 0.0

        # タスク集計
        cycle = next(
            (c for c in milestone.cycles if c.cycle_number == cycle_number),
            None,
        )
        total_tasks = len(cycle.tasks) if cycle else 0
        completed_tasks = sum(
            1 for t in (cycle.tasks if cycle else [])
            if t.status.value == "completed"
        )

        # サマリテキスト生成
        review = check_result.review_summary
        summary_parts = []
        if review.blocker_count:
            summary_parts.append(f"ブロッカー: {review.blocker_count}件")
        if review.major_count:
            summary_parts.append(f"MAJOR: {review.major_count}件")
        if review.minor_count:
            summary_parts.append(f"MINOR: {review.minor_count}件")
        summary = "指摘なし" if not summary_parts else "、".join(summary_parts)

        next_action = decision.next_cycle_policy or "次のサイクルへ"

        return ProgressReport(
            milestone_id=milestone.id,
            milestone_title=milestone.title,
            cycle_number=cycle_number,
            decision_type=decision.decision_type.value,
            dod_achieved=check_result.dod_achieved,
            dod_progress=dod_progress,
            completed_tasks=completed_tasks,
            total_tasks=total_tasks,
            blocker_count=review.blocker_count,
            summary=summary,
            next_action=next_action,
        )
