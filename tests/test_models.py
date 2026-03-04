"""PDCAコアデータモデルのユニットテスト。

M1 タスク 1-1: シリアライズ/デシリアライズ往復テスト含む。
"""


import pytest
from pydantic import ValidationError

from vibe_pdca.models.pdca import (
    AuditEntry,
    ChangeType,
    Cycle,
    CycleStatus,
    Decision,
    DecisionType,
    DoDItem,
    Goal,
    GovernanceLevel,
    Milestone,
    MilestoneStatus,
    PDCAPhase,
    ReviewCategory,
    ReviewFinding,
    ReviewSummary,
    Severity,
    StopReason,
    Task,
    TaskStatus,
    TraceLink,
)

# ============================================================
# DoDItem テスト
# ============================================================


class TestDoDItem:
    def test_creates_basic_item(self):
        item = DoDItem(description="テストが全て通過する")
        assert item.description == "テストが全て通過する"
        assert item.is_machine_checkable is True
        assert item.achieved is False

    def test_serialization_roundtrip(self):
        item = DoDItem(description="lint通過", achieved=True, evidence="CI green")
        json_str = item.model_dump_json()
        restored = DoDItem.model_validate_json(json_str)
        assert restored.description == item.description
        assert restored.achieved is True
        assert restored.evidence == "CI green"


# ============================================================
# Task テスト
# ============================================================


class TestTask:
    def test_creates_task_with_defaults(self):
        task = Task(id="T-001", title="テストタスク")
        assert task.status == TaskStatus.PENDING
        assert task.dependencies == []
        assert task.dod == []

    def test_task_with_dod(self):
        task = Task(
            id="T-001",
            title="CI設定",
            dod=[DoDItem(description="CIが自動実行される")],
            change_type=ChangeType.CONFIG,
        )
        assert len(task.dod) == 1
        assert task.change_type == ChangeType.CONFIG

    def test_serialization_roundtrip(self):
        task = Task(
            id="T-002",
            title="往復テスト",
            status=TaskStatus.IN_PROGRESS,
            dependencies=["T-001"],
        )
        json_str = task.model_dump_json()
        restored = Task.model_validate_json(json_str)
        assert restored.id == "T-002"
        assert restored.status == TaskStatus.IN_PROGRESS
        assert restored.dependencies == ["T-001"]


# ============================================================
# ReviewFinding テスト
# ============================================================


class TestReviewFinding:
    def test_creates_finding(self):
        finding = ReviewFinding(
            id="RF-001",
            reviewer_role="programmer",
            severity=Severity.BLOCKER,
            category=ReviewCategory.SECURITY,
            description="SQLインジェクションの可能性",
            confidence=0.95,
        )
        assert finding.severity == Severity.BLOCKER
        assert finding.confidence == 0.95

    def test_confidence_range_validation(self):
        with pytest.raises(ValidationError):
            ReviewFinding(
                id="RF-BAD",
                reviewer_role="pm",
                severity=Severity.MINOR,
                category=ReviewCategory.CORRECTNESS,
                description="test",
                confidence=1.5,  # 範囲外
            )

    def test_serialization_roundtrip(self):
        finding = ReviewFinding(
            id="RF-002",
            reviewer_role="designer",
            severity=Severity.MAJOR,
            category=ReviewCategory.UX,
            description="操作フロー不明確",
            file_path="src/gui/views.py",
            line_range="10-25",
        )
        json_str = finding.model_dump_json()
        restored = ReviewFinding.model_validate_json(json_str)
        assert restored.file_path == "src/gui/views.py"
        assert restored.line_range == "10-25"


# ============================================================
# ReviewSummary テスト
# ============================================================


class TestReviewSummary:
    def test_empty_summary(self):
        summary = ReviewSummary()
        assert summary.blocker_count == 0
        assert summary.dod_achieved is False

    def test_summary_with_findings(self):
        summary = ReviewSummary(
            findings=[
                ReviewFinding(
                    id="RF-1", reviewer_role="pm",
                    severity=Severity.BLOCKER,
                    category=ReviewCategory.CORRECTNESS,
                    description="重大問題",
                ),
            ],
            blocker_count=1,
            dod_achieved=False,
            dod_unmet_reasons=["blocker未解決"],
        )
        assert summary.blocker_count == 1
        assert len(summary.dod_unmet_reasons) == 1


# ============================================================
# Decision テスト
# ============================================================


class TestDecision:
    def test_accept_decision(self):
        decision = Decision(
            decision_type=DecisionType.ACCEPT,
            reason="全DoD達成",
        )
        assert decision.decision_type == DecisionType.ACCEPT

    def test_reject_with_policy(self):
        decision = Decision(
            decision_type=DecisionType.REJECT,
            reason="blocker未解決",
            next_cycle_policy="セキュリティ修正を優先",
            rejected_findings=["RF-001"],
        )
        assert decision.next_cycle_policy == "セキュリティ修正を優先"

    def test_serialization_roundtrip(self):
        decision = Decision(
            decision_type=DecisionType.DEFER,
            reason="外部依存の解決待ち",
            impact_scope="認証モジュール",
            reconsider_condition="依存ライブラリv2リリース後",
        )
        json_str = decision.model_dump_json()
        restored = Decision.model_validate_json(json_str)
        assert restored.decision_type == DecisionType.DEFER
        assert restored.reconsider_condition == "依存ライブラリv2リリース後"


# ============================================================
# Cycle テスト
# ============================================================


class TestCycle:
    def test_creates_cycle(self):
        cycle = Cycle(cycle_number=1)
        assert cycle.phase == PDCAPhase.PLAN
        assert cycle.status == CycleStatus.RUNNING

    def test_cycle_with_tasks(self):
        tasks = [Task(id=f"T-{i}", title=f"タスク{i}") for i in range(3)]
        cycle = Cycle(cycle_number=2, tasks=tasks)
        assert len(cycle.tasks) == 3

    def test_serialization_roundtrip(self):
        cycle = Cycle(
            cycle_number=1,
            phase=PDCAPhase.CHECK,
            status=CycleStatus.RUNNING,
            tasks=[Task(id="T-1", title="テスト")],
        )
        json_str = cycle.model_dump_json()
        restored = Cycle.model_validate_json(json_str)
        assert restored.cycle_number == 1
        assert restored.phase == PDCAPhase.CHECK
        assert len(restored.tasks) == 1


# ============================================================
# Milestone テスト
# ============================================================


class TestMilestone:
    def test_creates_milestone(self):
        ms = Milestone(id="M0", title="基盤構築")
        assert ms.status == MilestoneStatus.OPEN
        assert ms.cycles == []

    def test_milestone_with_dod(self):
        ms = Milestone(
            id="M1",
            title="仕様と骨格",
            dod=[
                DoDItem(description="全データモデル定義済み"),
                DoDItem(description="PDCA状態遷移テスト通過"),
            ],
            dependencies=["M0"],
        )
        assert len(ms.dod) == 2
        assert ms.dependencies == ["M0"]

    def test_serialization_roundtrip(self):
        ms = Milestone(
            id="M2",
            title="主要機能実装",
            status=MilestoneStatus.IN_PROGRESS,
            cycles=[Cycle(cycle_number=1)],
        )
        json_str = ms.model_dump_json()
        restored = Milestone.model_validate_json(json_str)
        assert restored.id == "M2"
        assert len(restored.cycles) == 1


# ============================================================
# Goal テスト
# ============================================================


class TestGoal:
    def test_creates_goal(self):
        goal = Goal(
            id="G-001",
            purpose="PDCA自動開発システムの構築",
            acceptance_criteria=["全テスト通過", "ドキュメント完備"],
        )
        assert goal.purpose == "PDCA自動開発システムの構築"
        assert len(goal.acceptance_criteria) == 2

    def test_acceptance_criteria_required(self):
        with pytest.raises(ValidationError):
            Goal(
                id="G-BAD",
                purpose="テスト",
                acceptance_criteria=[],  # 最低1件必須
            )

    def test_goal_with_milestones(self):
        goal = Goal(
            id="G-002",
            purpose="テスト",
            acceptance_criteria=["基準1"],
            constraints=["Python 3.12+"],
            prohibitions=["外部DB使用禁止"],
            milestones=[
                Milestone(id="M0", title="基盤"),
                Milestone(id="M1", title="骨格"),
            ],
        )
        assert len(goal.milestones) == 2
        assert goal.constraints == ["Python 3.12+"]

    def test_serialization_roundtrip(self):
        goal = Goal(
            id="G-003",
            purpose="往復テスト",
            acceptance_criteria=["テスト通過"],
            priority="high",
        )
        json_str = goal.model_dump_json()
        restored = Goal.model_validate_json(json_str)
        assert restored.id == "G-003"
        assert restored.priority == "high"


# ============================================================
# TraceLink テスト
# ============================================================


class TestTraceLink:
    def test_creates_link(self):
        link = TraceLink(
            source_type="goal",
            source_id="G-001",
            target_type="milestone",
            target_id="M0",
            relationship="has_milestone",
        )
        assert link.source_type == "goal"
        assert link.relationship == "has_milestone"

    def test_serialization_roundtrip(self):
        link = TraceLink(
            source_type="task",
            source_id="T-001",
            target_type="pr",
            target_id="PR-42",
        )
        json_str = link.model_dump_json()
        restored = TraceLink.model_validate_json(json_str)
        assert restored.target_id == "PR-42"


# ============================================================
# AuditEntry テスト
# ============================================================


class TestAuditEntry:
    def test_creates_entry(self):
        entry = AuditEntry(
            sequence=0,
            actor="system",
            action="cycle_start",
        )
        assert entry.sequence == 0
        assert entry.governance_level == GovernanceLevel.C

    def test_compute_hash_is_deterministic(self):
        entry = AuditEntry(
            sequence=0,
            timestamp=1000.0,
            actor="owner",
            action="goal_create",
            previous_hash="abc",
        )
        h1 = entry.compute_hash()
        h2 = entry.compute_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256

    def test_different_entries_have_different_hashes(self):
        e1 = AuditEntry(sequence=0, timestamp=1000.0, actor="a", action="x", previous_hash="z")
        e2 = AuditEntry(sequence=1, timestamp=1000.0, actor="a", action="x", previous_hash="z")
        assert e1.compute_hash() != e2.compute_hash()

    def test_serialization_roundtrip(self):
        entry = AuditEntry(
            sequence=5,
            actor="maintainer",
            action="pdca_stop",
            governance_level=GovernanceLevel.B,
            detail={"reason": "コスト超過"},
        )
        entry.entry_hash = entry.compute_hash()
        json_str = entry.model_dump_json()
        restored = AuditEntry.model_validate_json(json_str)
        assert restored.sequence == 5
        assert restored.detail["reason"] == "コスト超過"


# ============================================================
# Enum テスト
# ============================================================


class TestEnums:
    def test_pdca_phase_values(self):
        assert PDCAPhase.PLAN.value == "plan"
        assert PDCAPhase.DO.value == "do"
        assert PDCAPhase.CHECK.value == "check"
        assert PDCAPhase.ACT.value == "act"

    def test_stop_reasons(self):
        assert len(StopReason) == 7

    def test_severity_values(self):
        assert Severity.BLOCKER.value == "blocker"
        assert Severity.MAJOR.value == "major"
        assert Severity.MINOR.value == "minor"
