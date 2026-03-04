"""ガバナンス・承認ワークフロー – A/B/C分類・NO時代替案・12hタイムアウト。

M2 タスク 2-7: 要件定義書 §17, §18.2 準拠。

| 分類 | 内容                              | 承認方法                  |
|------|----------------------------------|--------------------------|
| A    | 権限拡大/ポリシー緩和/禁止領域変更 | Discord上で4/4承認        |
| B    | diff閾値超え/依存大規模更新       | バックアップ作成後自動進行 |
| C    | 既定ポリシー内の軽微変更          | 承認不要                  |
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from vibe_pdca.models.pdca import GovernanceLevel

logger = logging.getLogger(__name__)


class GovernanceClassificationError(Exception):
    """ガバナンス分類エラー。"""


@dataclass
class AlternativeProposal:
    """NO時の代替案（§A4）。"""

    id: str = field(default_factory=lambda: f"alt-{uuid.uuid4().hex[:8]}")
    original_operation: str = ""
    alternative_description: str = ""
    risk_reduction: str = ""
    trade_off: str = ""


@dataclass
class GovernanceDecision:
    """ガバナンス判定結果。"""

    operation_id: str
    level: GovernanceLevel
    approved: bool = False
    alternatives: list[AlternativeProposal] = field(default_factory=list)
    reason: str = ""
    backup_created: bool = False


# A操作のパターン（§17.1）
A_PATTERNS: list[str] = [
    "権限拡大",
    "ポリシー緩和",
    "禁止領域の変更",
    "セキュリティ設定変更",
    "本番環境デプロイ",
    "APIキー変更",
    "RBAC設定変更",
]

# B操作のパターン（§17.1）
B_PATTERNS: list[str] = [
    "diff閾値超え",
    "依存の大規模更新",
    "CI設定変更",
    "バイナリ更新",
    "設定ファイル大規模変更",
]


class GovernanceManager:
    """ガバナンス・承認ワークフローを管理する。

    操作をA/B/Cに分類し、適切な承認フローを実行する。
    NO時には代替案を生成する（§A4）。
    """

    def __init__(
        self,
        a_patterns: list[str] | None = None,
        b_patterns: list[str] | None = None,
    ) -> None:
        self._a_patterns = a_patterns or list(A_PATTERNS)
        self._b_patterns = b_patterns or list(B_PATTERNS)
        self._decisions: list[GovernanceDecision] = []

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    def classify(
        self,
        operation_description: str,
        explicit_level: GovernanceLevel | None = None,
    ) -> GovernanceLevel:
        """操作をA/B/Cに分類する。

        Parameters
        ----------
        operation_description : str
            操作の説明。
        explicit_level : GovernanceLevel | None
            明示的に指定するレベル。

        Returns
        -------
        GovernanceLevel
            分類結果。
        """
        if explicit_level is not None:
            return explicit_level

        desc_lower = operation_description.lower()

        # A操作チェック
        for pattern in self._a_patterns:
            if pattern.lower() in desc_lower:
                return GovernanceLevel.A

        # B操作チェック
        for pattern in self._b_patterns:
            if pattern.lower() in desc_lower:
                return GovernanceLevel.B

        # デフォルトはC
        return GovernanceLevel.C

    def generate_alternatives(
        self,
        operation_description: str,
        rejection_reason: str = "",
    ) -> list[AlternativeProposal]:
        """NO時の代替案を生成する（§A4）。

        Parameters
        ----------
        operation_description : str
            却下された操作の説明。
        rejection_reason : str
            却下理由。

        Returns
        -------
        list[AlternativeProposal]
            代替案リスト。
        """
        alternatives: list[AlternativeProposal] = []

        # スコープ縮小案
        alternatives.append(AlternativeProposal(
            original_operation=operation_description,
            alternative_description=f"スコープ縮小: {operation_description}の範囲を限定",
            risk_reduction="影響範囲を最小化",
            trade_off="完全な目標達成は延期",
        ))

        # 段階的実施案
        alternatives.append(AlternativeProposal(
            original_operation=operation_description,
            alternative_description=f"段階的実施: {operation_description}を複数フェーズに分割",
            risk_reduction="各フェーズで検証を挟む",
            trade_off="実施期間が延長",
        ))

        # 代替アプローチ案
        alternatives.append(AlternativeProposal(
            original_operation=operation_description,
            alternative_description=f"代替手法: {operation_description}の別実装方法",
            risk_reduction="リスクの高い手法を回避",
            trade_off="実装コストが変動する可能性",
        ))

        logger.info(
            "代替案生成: '%s' に対して %d件",
            operation_description, len(alternatives),
        )
        return alternatives

    def process_operation(
        self,
        operation_id: str,
        operation_description: str,
        approved: bool = True,
        explicit_level: GovernanceLevel | None = None,
    ) -> GovernanceDecision:
        """操作のガバナンス判定を行う。

        Parameters
        ----------
        operation_id : str
            操作ID。
        operation_description : str
            操作の説明。
        approved : bool
            承認されたかどうか。
        explicit_level : GovernanceLevel | None
            明示的なレベル指定。

        Returns
        -------
        GovernanceDecision
            判定結果。
        """
        level = self.classify(operation_description, explicit_level)

        decision = GovernanceDecision(
            operation_id=operation_id,
            level=level,
            approved=approved,
        )

        if level == GovernanceLevel.B:
            decision.backup_created = True
            decision.reason = "バックアップ作成後に自動進行"

        if level == GovernanceLevel.C:
            decision.approved = True
            decision.reason = "承認不要（C操作）"

        # 却下された場合は代替案を生成
        if not approved:
            decision.alternatives = self.generate_alternatives(
                operation_description,
            )
            decision.reason = "却下 – 代替案を提示"

        self._decisions.append(decision)
        return decision

    def get_status(self) -> dict[str, Any]:
        """ガバナンス管理状態を返す。"""
        return {
            "decision_count": self.decision_count,
            "a_pattern_count": len(self._a_patterns),
            "b_pattern_count": len(self._b_patterns),
        }
