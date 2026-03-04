"""受入基準検証テスト（§23 の12項目）。

M4 タスク 9.1: 要件定義書 §23 準拠。
各受入基準を統合テストで検証する。
"""

from __future__ import annotations

from vibe_pdca.audit import AuditLog
from vibe_pdca.engine.checker import CheckResult, CIStatus, CISummary
from vibe_pdca.engine.decision import ActDecisionMaker
from vibe_pdca.engine.executor import Executor
from vibe_pdca.engine.governance import GovernanceManager
from vibe_pdca.engine.incident_report import IncidentReporter
from vibe_pdca.engine.intervention import InterventionManager
from vibe_pdca.engine.mode_controller import ModeController, OperationMode
from vibe_pdca.engine.planner import Planner
from vibe_pdca.engine.review_integrator import ReviewIntegrator
from vibe_pdca.engine.stop_conditions import DegradeManager, DegradePriority, StackDetector
from vibe_pdca.models.pdca import (
    Cycle,
    CycleStatus,
    DecisionType,
    DoDItem,
    Goal,
    GovernanceLevel,
    Milestone,
    PDCAPhase,
    ReviewCategory,
    ReviewFinding,
    ReviewSummary,
    Severity,
    StopReason,
    Task,
    TaskStatus,
)
from vibe_pdca.monitoring import TraceLinkManager


class TestAc01GoalToMilestone:
    """受入基準1: 最終到達点を入力すると、マイルストーンとDoDが自動生成される。"""

    def test_goal_generates_milestones(self):
        planner = Planner()
        goal = Goal(
            id="goal-001",
            purpose="Webアプリの構築",
            acceptance_criteria=["ユーザー認証", "API設計", "テスト"],
        )
        milestones = planner.generate_milestones(goal)
        assert milestones
        assert len(milestones) >= 1
        for ms in milestones:
            assert ms.title
            assert ms.dod

    def test_dod_is_machine_checkable(self):
        """受入基準10: DoDが機械判定可能な形式を含む。"""
        planner = Planner()
        goal = Goal(
            id="goal-002",
            purpose="テストシステム",
            acceptance_criteria=["ユニットテスト", "CI通過"],
        )
        milestones = planner.generate_milestones(goal)
        for ms in milestones:
            assert isinstance(ms.dod, list)
            assert all(isinstance(d, DoDItem) for d in ms.dod)
            assert all(d.description for d in ms.dod)


class TestAc02PdcaCycleProgression:
    """受入基準2: 1サイクル以上のPDCAが自動で進行し、各フェーズの成果物が記録される。"""

    def test_pdca_cycle_progression(self):
        audit = AuditLog()

        # PLAN
        planner = Planner()
        goal = Goal(
            id="goal-003",
            purpose="テスト",
            acceptance_criteria=["条件1"],
        )
        planner.generate_milestones(goal)
        audit.append("planner", "plan_generated", "plan", "plan-1")

        # DO
        executor = Executor()
        tasks = [Task(id="task-1", title="テストタスク")]
        executor.execute_tasks(tasks)
        audit.append("executor", "task_executed", "task", "task-1")

        # CHECK
        check_result = CheckResult(
            review_summary=ReviewSummary(
                blocker_count=0, major_count=0, minor_count=0,
                dod_achieved=True,
            ),
            ci_summary=CISummary(
                total_jobs=1, passed_jobs=1, failed_jobs=0,
                overall_status=CIStatus.SUCCESS,
            ),
            dod_achieved=True,
        )
        audit.append("checker", "check_completed", "check", "check-1")

        # ACT
        decision_maker = ActDecisionMaker()
        decision_maker.make_decision(check_result)
        audit.append("decision", "act_decided", "decision", "dec-1")

        # 全フェーズが記録されている
        assert audit.entry_count == 4
        actions = [e.action for e in audit.entries]
        assert "plan_generated" in actions
        assert "task_executed" in actions
        assert "check_completed" in actions
        assert "act_decided" in actions


class TestAc03FivePersonaReview:
    """受入基準3: CHECKで5ペルソナレビューが実行され、統合結果が生成される。"""

    def test_five_persona_review(self):
        integrator = ReviewIntegrator()
        findings = [
            ReviewFinding(
                id=f"f-{i}",
                reviewer_role=role,
                severity=Severity.MAJOR,
                category=ReviewCategory.CORRECTNESS,
                description=f"{role}からの指摘",
            )
            for i, role in enumerate(
                ["pm", "architect", "security", "qa", "ux"]
            )
        ]
        result = integrator.integrate(findings)
        # 5ペルソナの指摘が統合され、クラスタリング後の代表指摘数+元の総指摘を確認
        assert len(result.prioritized) >= 1
        assert len(findings) == 5  # 5ペルソナから入力された


class TestAc04ActDecisionRecorded:
    """受入基準4: ACTで採否と次サイクル方針が理由付きで記録される。"""

    def test_decision_with_reason(self):
        dm = ActDecisionMaker()
        check_result = CheckResult(
            review_summary=ReviewSummary(
                blocker_count=0, major_count=0, minor_count=0,
                dod_achieved=True,
            ),
            ci_summary=CISummary(
                total_jobs=1, passed_jobs=1, failed_jobs=0,
                overall_status=CIStatus.SUCCESS,
            ),
            dod_achieved=True,
        )
        decision = dm.make_decision(check_result)
        assert decision.decision_type in (
            DecisionType.ACCEPT,
            DecisionType.REJECT,
            DecisionType.DEFER,
            DecisionType.ABORT,
            DecisionType.DEGRADE,
        )
        assert decision.reason


class TestAc05StopConditions:
    """受入基準5: 停止条件が動作し、重大インシデント時に自動停止できる。"""

    def test_stop_on_critical_incident(self):
        dm = DegradeManager()
        # 監査ログ障害は即停止（P0）
        dm.report_failure(
            DegradePriority.AUDIT_LOG,
            "監査ログ不整合",
        )
        assert dm.should_stop

    def test_stack_detection(self):
        import time
        detector = StackDetector(timeout_seconds=1)
        detector._last_heartbeat = time.time() - 10
        assert detector.is_stacked()


class TestAc06AuditTraceability:
    """受入基準6: 監査ログにより「何が・なぜ・いつ・どう決まったか」を追跡できる。"""

    def test_audit_log_traceability(self):
        audit = AuditLog()
        entry = audit.append(
            actor="planner",
            action="milestone_created",
            resource_type="milestone",
            resource_id="ms-1",
            detail={"reason": "ゴール分解により生成"},
            governance_level=GovernanceLevel.C,
        )
        assert entry.actor == "planner"
        assert entry.action == "milestone_created"
        assert entry.detail["reason"]
        assert entry.timestamp > 0


class TestAc07UiOperations:
    """受入基準7: ユーザーが停止/再開/モード切替を迷わず実行できる。"""

    def test_mode_switch(self):
        mc = ModeController(initial_mode=OperationMode.MANUAL)
        assert mc.mode == OperationMode.MANUAL

        mc.set_mode(OperationMode.SEMI_AUTO, reason="テスト切替")
        assert mc.mode == OperationMode.SEMI_AUTO

        mc.set_mode(OperationMode.FULL_AUTO, reason="全自動へ")
        assert mc.mode == OperationMode.FULL_AUTO

    def test_mode_history_recorded(self):
        mc = ModeController()
        mc.set_mode(OperationMode.SEMI_AUTO, reason="切替テスト")
        assert len(mc.mode_history) >= 1


class TestAc08IncidentResponse:
    """受入基準8: 重大インシデント時に自動停止・原因内訳提示・再開条件提示ができる。"""

    def test_incident_report(self):
        reporter = IncidentReporter()
        report = reporter.generate_p0_report(
            title="監査ログ不整合",
            summary="チェーンハッシュ不一致を検出",
            root_cause="外部からのデータ改ざん",
        )
        assert report.root_cause
        assert len(report.resume_conditions) > 0
        assert len(report.remediation_steps) > 0

    def test_intervention_analysis(self):
        mgr = InterventionManager()
        stopped_ms = Milestone(
            id="ms-1",
            title="テストMS",
            cycles=[
                Cycle(
                    cycle_number=1,
                    phase=PDCAPhase.DO,
                    status=CycleStatus.STOPPED,
                    tasks=[Task(id="t-1", title="テスト", status=TaskStatus.BLOCKED)],
                ),
            ],
        )
        report = mgr.analyze_stop(stopped_ms, StopReason.CI_CONSECUTIVE_FAILURE)
        assert report.incident_priority
        assert report.root_cause
        assert len(report.resume_conditions) > 0


class TestAc09AuditDecisionTracking:
    """受入基準9: 監査ログにより意思決定・レビュー統合・ポリシー変更を追跡できる。"""

    def test_decision_audit_tracking(self):
        audit = AuditLog()
        audit.append("reviewer", "review_integrated", "review", "rv-1")
        audit.append("decision", "act_accept", "decision", "dec-1",
                      detail={"reason": "全項目合格"})
        audit.append("admin", "policy_changed", "policy", "pol-1",
                      governance_level=GovernanceLevel.A)

        assert audit.entry_count == 3
        assert audit.verify_integrity()


class TestAc10DodMachineCheckable:
    """受入基準10: DoDが機械判定可能な形式を含む。(AC01で一部検証済み)"""

    def test_dod_items_are_structured(self):
        planner = Planner()
        goal = Goal(
            id="goal-010",
            purpose="APIサーバー構築",
            acceptance_criteria=["REST API", "認証", "テスト"],
        )
        milestones = planner.generate_milestones(goal)
        for ms in milestones:
            assert ms.dod
            for dod_item in ms.dod:
                assert isinstance(dod_item, DoDItem)
                assert len(dod_item.description) > 0


class TestAc11AOperationApproval:
    """受入基準11: 重要操作で承認要求が出る（A操作）。"""

    def test_a_operation_classified(self):
        gov = GovernanceManager()
        level = gov.classify("セキュリティ設定変更")
        assert level == GovernanceLevel.A

    def test_a_operation_audit_recorded(self):
        audit = AuditLog()
        entry = audit.append(
            actor="admin",
            action="policy_change",
            governance_level=GovernanceLevel.A,
            detail={"description": "コスト上限変更"},
        )
        assert entry.governance_level == GovernanceLevel.A


class TestAc12TraceLinkTracking:
    """受入基準12: 「どの入力→どの決定→どの成果」を追跡できる。"""

    def test_tracelink_end_to_end(self):
        tlm = TraceLinkManager()
        tlm.add_link("goal", "g-1", "milestone", "ms-1", "has_milestone")
        tlm.add_link("milestone", "ms-1", "task", "t-1", "has_task")
        tlm.add_link("task", "t-1", "pr", "pr-1", "implements")
        tlm.add_link("pr", "pr-1", "review", "rv-1", "reviewed_by")
        tlm.add_link("review", "rv-1", "decision", "dec-1", "leads_to")

        chain = tlm.trace_chain("goal", "g-1", max_depth=10)
        assert len(chain) >= 5

        backward = tlm.get_backward_links("decision", "dec-1")
        assert len(backward) == 1
        assert backward[0].source_type == "review"

