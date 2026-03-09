"""PLANフェーズ（Planner）のテスト。"""

import pytest

from vibe_pdca.engine.planner import (
    MAX_TASKS_PER_CYCLE,
    Planner,
    PlanResult,
)
from vibe_pdca.models.pdca import (
    Cycle,
    DoDItem,
    Goal,
    Milestone,
    Task,
)

# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def planner():
    return Planner()


@pytest.fixture
def sample_goal():
    return Goal(
        id="goal-001",
        purpose="PDCA自動開発システムの実装",
        acceptance_criteria=[
            "PLAN→DO→CHECK→ACTの自動サイクルが動作すること",
            "5ペルソナレビューが統合されること",
            "監査ログが記録されること",
        ],
        constraints=["Python 3.12+のみ使用"],
    )


@pytest.fixture
def sample_milestone():
    return Milestone(
        id="ms-001",
        title="PDCA状態機械実装",
        description="テスト用マイルストーン",
        dod=[
            DoDItem(description="全状態遷移テストが通過すること"),
            DoDItem(description="停止条件が7つ全て動作すること"),
            DoDItem(description="監査ログが記録されること"),
        ],
    )


# ============================================================
# テスト: マイルストーン生成
# ============================================================


class TestMilestoneGeneration:
    def test_generates_milestones_from_acceptance_criteria(
        self, planner, sample_goal,
    ):
        milestones = planner.generate_milestones(sample_goal)
        assert len(milestones) == 3  # 受入条件の数
        assert all(isinstance(ms, Milestone) for ms in milestones)

    def test_milestones_have_dod(self, planner, sample_goal):
        milestones = planner.generate_milestones(sample_goal)
        for ms in milestones:
            assert len(ms.dod) >= 1

    def test_milestones_have_sequential_dependencies(
        self, planner, sample_goal,
    ):
        milestones = planner.generate_milestones(sample_goal)
        assert milestones[0].dependencies == []
        assert milestones[1].dependencies == [milestones[0].id]
        assert milestones[2].dependencies == [milestones[1].id]

    def test_milestones_assigned_to_goal(self, planner, sample_goal):
        milestones = planner.generate_milestones(sample_goal)
        assert sample_goal.milestones == milestones

    def test_max_milestones_limit(self, planner):
        goal = Goal(
            id="goal-big",
            purpose="大量の受入条件",
            acceptance_criteria=[f"条件{i}" for i in range(20)],
        )
        milestones = planner.generate_milestones(goal, max_milestones=3)
        assert len(milestones) == 3

    def test_empty_acceptance_criteria_raises(self, planner):
        goal = Goal(
            id="goal-empty",
            purpose="目的",
            acceptance_criteria=["dummy"],  # 最低1件必須
        )
        goal.acceptance_criteria = []  # テスト用に空にする
        with pytest.raises(ValueError, match="受入条件が空"):
            planner.generate_milestones(goal)


# ============================================================
# テスト: タスク生成
# ============================================================


class TestTaskGeneration:
    def test_generates_tasks_from_milestone(
        self, planner, sample_milestone,
    ):
        result = planner.generate_tasks(sample_milestone)
        assert isinstance(result, PlanResult)
        assert result.task_count > 0
        assert result.task_count <= MAX_TASKS_PER_CYCLE

    def test_tasks_have_dod(self, planner, sample_milestone):
        result = planner.generate_tasks(sample_milestone)
        for task in result.tasks:
            assert len(task.dod) >= 1

    def test_tasks_have_dependencies(self, planner, sample_milestone):
        result = planner.generate_tasks(sample_milestone)
        # 少なくとも一部のタスクは依存を持つ
        has_deps = any(t.dependencies for t in result.tasks)
        assert has_deps

    def test_max_tasks_per_cycle_enforced(self, planner):
        """1サイクルあたりのタスク数上限（7件）が守られること。"""
        milestone = Milestone(
            id="ms-big",
            title="大量DoD",
            dod=[
                DoDItem(description=f"条件{i}")
                for i in range(20)
            ],
        )
        result = planner.generate_tasks(milestone)
        assert result.task_count <= MAX_TASKS_PER_CYCLE

    def test_empty_dod_raises(self, planner):
        milestone = Milestone(
            id="ms-empty",
            title="DoDなし",
            dod=[],
        )
        with pytest.raises(ValueError, match="DoDがありません"):
            planner.generate_tasks(milestone)

    def test_milestone_task_limit_raises(self, planner):
        """マイルストーンのタスク上限（30件）に到達した場合エラー。"""
        milestone = Milestone(
            id="ms-full",
            title="満杯",
            dod=[DoDItem(description="test")],
            cycles=[
                Cycle(
                    cycle_number=i + 1,
                    tasks=[
                        Task(id=f"t-{i}-{j}", title=f"task-{j}")
                        for j in range(7)
                    ],
                )
                for i in range(5)
            ],
        )
        # 5サイクル × 7タスク = 35 > 30
        with pytest.raises(ValueError, match="タスク上限"):
            planner.generate_tasks(milestone)

    def test_previous_findings_become_tasks(self, planner, sample_milestone):
        """前回CHECKの未解決指摘がタスク化されること。"""
        context = {
            "previous_findings": [
                {
                    "description": "nullチェックが不足",
                    "suggestion": "入力値のnullチェックを追加",
                },
            ],
        }
        result = planner.generate_tasks(sample_milestone, context=context)
        fix_tasks = [t for t in result.tasks if "修正:" in t.title]
        assert len(fix_tasks) >= 1

    def test_non_dict_findings_skipped(self, planner, sample_milestone):
        """previous_findingsに辞書以外が含まれる場合、安全にスキップされること。"""
        context = {
            "previous_findings": [
                "これは文字列",
                {"description": "正しい指摘", "suggestion": "修正案"},
            ],
        }
        result = planner.generate_tasks(sample_milestone, context=context)
        fix_tasks = [t for t in result.tasks if "修正:" in t.title]
        assert len(fix_tasks) == 1  # 辞書のみがタスク化される

    def test_tasks_include_test_tasks(self, planner, sample_milestone):
        """テストタスクが生成されること。"""
        result = planner.generate_tasks(sample_milestone)
        test_tasks = [t for t in result.tasks if "テスト:" in t.title]
        assert len(test_tasks) >= 1

    def test_tasks_have_change_type(self, planner, sample_milestone):
        result = planner.generate_tasks(sample_milestone)
        for task in result.tasks:
            assert task.change_type is not None

    def test_achieved_dod_items_skipped(self, planner):
        """達成済みDoDは新規タスクとしてスキップされること。"""
        milestone = Milestone(
            id="ms-partial",
            title="一部達成済み",
            dod=[
                DoDItem(description="達成済み条件", achieved=True),
                DoDItem(description="未達成条件"),
            ],
        )
        result = planner.generate_tasks(milestone)
        titles = [t.title for t in result.tasks]
        assert not any("達成済み条件" in t for t in titles)


# ============================================================
# テスト: リスク分析
# ============================================================


class TestRiskAnalysis:
    def test_risks_included_in_result(self, planner, sample_milestone):
        result = planner.generate_tasks(sample_milestone)
        assert isinstance(result.risks, list)

    def test_constraint_risks(self, planner, sample_milestone):
        """制約がリスクとして報告されること。"""
        context = {"constraints": ["メモリ使用量100MB以下"]}
        result = planner.generate_tasks(sample_milestone, context=context)
        risk_texts = [r["risk"] for r in result.risks]
        assert any("メモリ使用量" in r for r in risk_texts)
