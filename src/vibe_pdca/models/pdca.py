"""PDCAコアデータモデル定義。

M1 タスク 1-1: 要件定義書 §3, §6, §7, §8 準拠。
Pydanticモデルでシリアライズ/デシリアライズ往復テストを保証する。

モデル階層:
  Goal → Milestone → Task → Cycle(PLAN/DO/CHECK/ACT) → Review → Decision
"""

from __future__ import annotations

import hashlib
import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ============================================================
# 列挙型
# ============================================================


class PDCAPhase(StrEnum):
    """PDCAフェーズ（§6.1）。"""

    PLAN = "plan"
    DO = "do"
    CHECK = "check"
    ACT = "act"


class CycleStatus(StrEnum):
    """サイクルの状態。"""

    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


class TaskStatus(StrEnum):
    """タスクの進捗状態。"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class MilestoneStatus(StrEnum):
    """マイルストーンの状態。"""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Severity(StrEnum):
    """レビュー指摘の重大度（§8.1）。"""

    BLOCKER = "blocker"
    MAJOR = "major"
    MINOR = "minor"


class ReviewCategory(StrEnum):
    """レビュー指摘のカテゴリ。"""

    CORRECTNESS = "correctness"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    UX = "ux"
    ACCESSIBILITY = "accessibility"
    CONSISTENCY = "consistency"
    DOCUMENTATION = "documentation"


class ChangeType(StrEnum):
    """変更種別（§9.3）。"""

    SOURCE_CODE = "source_code"
    TEST = "test"
    DOCUMENTATION = "documentation"
    CONFIG = "config"
    DEPENDENCY = "dependency"
    BINARY = "binary"


class StopReason(StrEnum):
    """停止条件（§6.6）。"""

    CRITICAL_INCIDENT = "critical_incident"
    CI_CONSECUTIVE_FAILURE = "ci_consecutive_failure"
    DIFF_SIZE_EXCEEDED = "diff_size_exceeded"
    AUDIT_LOG_INCONSISTENCY = "audit_log_inconsistency"
    SAME_ERROR_RETRY = "same_error_retry"
    CYCLE_TIMEOUT = "cycle_timeout"
    USER_STOP = "user_stop"


class GovernanceLevel(StrEnum):
    """操作の分類（§17）。"""

    A = "a"  # 人間承認必須
    B = "b"  # ペルソナ3承認
    C = "c"  # 自動実行可


class DecisionType(StrEnum):
    """ACT判定の種別（§6.5）。"""

    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"
    ABORT = "abort"
    DEGRADE = "degrade"


# ============================================================
# コアモデル
# ============================================================


class DoDItem(BaseModel):
    """DoD（Definition of Done）の1項目（§7.1）。

    機械判定可能な形式で記述する。
    """

    description: str = Field(..., description="達成条件の記述")
    is_machine_checkable: bool = Field(
        default=True, description="機械判定可能か"
    )
    achieved: bool = Field(default=False, description="達成済みか")
    evidence: str | None = Field(default=None, description="達成のエビデンス")


class Task(BaseModel):
    """PDCAサイクル内のタスク（§6.2: 最大7件/サイクル）。"""

    id: str = Field(..., description="タスクID")
    title: str = Field(..., description="タスク名")
    description: str = Field(default="", description="タスクの詳細")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    dod: list[DoDItem] = Field(default_factory=list, description="達成条件リスト")
    dependencies: list[str] = Field(
        default_factory=list, description="依存タスクIDリスト"
    )
    change_type: ChangeType | None = Field(default=None, description="変更種別")
    assignee_role: str | None = Field(default=None, description="担当ロール")
    issue_number: int | None = Field(
        default=None, description="対応するGitHub Issue番号"
    )
    pr_number: int | None = Field(
        default=None, description="対応するGitHub PR番号"
    )
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = Field(default=None)


class ReviewFinding(BaseModel):
    """レビュー指摘の1件（§8.2）。

    5ペルソナが出力するJSON形式に準拠。
    """

    id: str = Field(..., description="指摘ID")
    reviewer_role: str = Field(..., description="レビュアのロール名")
    severity: Severity
    category: ReviewCategory
    description: str = Field(..., description="指摘の詳細")
    basis: str = Field(default="", description="根拠")
    suggestion: str = Field(default="", description="改善提案")
    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="確信度"
    )
    file_path: str | None = Field(default=None, description="対象ファイルパス")
    line_range: str | None = Field(default=None, description="対象行範囲")


class ReviewSummary(BaseModel):
    """レビュー統合サマリ（§8.3）。"""

    findings: list[ReviewFinding] = Field(default_factory=list)
    blocker_count: int = Field(default=0)
    major_count: int = Field(default=0)
    minor_count: int = Field(default=0)
    dod_achieved: bool = Field(default=False, description="DoD達成判定")
    dod_unmet_reasons: list[str] = Field(
        default_factory=list, description="DoD未達理由"
    )


class Decision(BaseModel):
    """ACT判定の記録（§6.5）。"""

    decision_type: DecisionType
    reason: str = Field(..., description="判定理由")
    impact_scope: str = Field(default="", description="影響範囲")
    reconsider_condition: str = Field(default="", description="再検討条件")
    accepted_findings: list[str] = Field(
        default_factory=list, description="採択した指摘IDリスト"
    )
    rejected_findings: list[str] = Field(
        default_factory=list, description="却下した指摘IDリスト"
    )
    next_cycle_policy: str = Field(
        default="", description="次サイクルの方針"
    )
    created_at: float = Field(default_factory=time.time)


class Cycle(BaseModel):
    """PDCAの1サイクル（§6.1）。"""

    cycle_number: int = Field(..., ge=1, description="サイクル番号")
    phase: PDCAPhase = Field(default=PDCAPhase.PLAN, description="現在のフェーズ")
    status: CycleStatus = Field(default=CycleStatus.RUNNING)
    tasks: list[Task] = Field(
        default_factory=list, description="サイクル内タスク（最大7件）"
    )
    review_summary: ReviewSummary | None = Field(
        default=None, description="CHECKフェーズの結果"
    )
    decision: Decision | None = Field(
        default=None, description="ACTフェーズの判定"
    )
    stop_reason: StopReason | None = Field(
        default=None, description="停止原因（停止時のみ）"
    )
    started_at: float = Field(default_factory=time.time)
    completed_at: float | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Milestone(BaseModel):
    """マイルストーン（§7）。

    1マイルストーンあたり最大30タスク（§7.1）。
    """

    id: str = Field(..., description="マイルストーンID")
    title: str = Field(..., description="マイルストーン名")
    description: str = Field(default="", description="概要")
    status: MilestoneStatus = Field(default=MilestoneStatus.OPEN)
    dod: list[DoDItem] = Field(
        default_factory=list, description="マイルストーンレベルDoD"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="依存マイルストーンIDリスト"
    )
    cycles: list[Cycle] = Field(
        default_factory=list, description="実施済みサイクルリスト"
    )
    github_milestone_number: int | None = Field(
        default=None, description="GitHub Milestone番号"
    )
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = Field(default=None)


class Goal(BaseModel):
    """最終到達点（§7.3）。

    ユーザーが入力する完成状態の定義。
    """

    id: str = Field(..., description="目標ID")
    purpose: str = Field(..., description="目的（何を実現するか）")
    acceptance_criteria: list[str] = Field(
        ..., min_length=1, description="受入条件"
    )
    constraints: list[str] = Field(
        default_factory=list, description="制約"
    )
    prohibitions: list[str] = Field(
        default_factory=list, description="禁止事項"
    )
    priority: str = Field(default="medium", description="優先度")
    milestones: list[Milestone] = Field(
        default_factory=list, description="生成されたマイルストーン"
    )
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = Field(default=None)


# ============================================================
# トレーサビリティ（§14.2 / タスク1-7基礎）
# ============================================================


class TraceLink(BaseModel):
    """追跡リンク: Goal→Milestone→Task→PR→Review→Decision。"""

    source_type: str = Field(..., description="リンク元の種類")
    source_id: str = Field(..., description="リンク元ID")
    target_type: str = Field(..., description="リンク先の種類")
    target_id: str = Field(..., description="リンク先ID")
    relationship: str = Field(
        default="related_to", description="関係の種類"
    )
    created_at: float = Field(default_factory=time.time)


# ============================================================
# 監査ログ（§16.2 / タスク1-4基礎）
# ============================================================


class AuditEntry(BaseModel):
    """監査ログエントリ（追記専用・チェーンハッシュ付き）。"""

    sequence: int = Field(..., ge=0, description="連番")
    timestamp: float = Field(default_factory=time.time)
    actor: str = Field(..., description="操作者（ロール or system）")
    action: str = Field(..., description="操作内容")
    resource_type: str = Field(default="", description="対象リソース種別")
    resource_id: str = Field(default="", description="対象リソースID")
    detail: dict[str, Any] = Field(default_factory=dict)
    governance_level: GovernanceLevel = Field(default=GovernanceLevel.C)
    previous_hash: str = Field(default="", description="直前エントリのハッシュ")
    entry_hash: str = Field(default="", description="本エントリのハッシュ")

    def compute_hash(self) -> str:
        """エントリ内容からSHA-256ハッシュを計算する。"""
        payload = (
            f"{self.sequence}:{self.timestamp}:{self.actor}:{self.action}"
            f":{self.resource_type}:{self.resource_id}:{self.previous_hash}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
