"""提案16: ロールバック戦略の体系化 – テスト。"""

import pytest

from vibe_pdca.engine.intervention import (
    RollbackCandidate,
    RollbackChainDetector,
    RollbackChainLink,
    RollbackLevel,
    RollbackPreview,
    StateConsistencyChecker,
)
from vibe_pdca.models.pdca import (
    AuditEntry,
    Cycle,
    CycleStatus,
    Decision,
    DecisionType,
    Milestone,
    PDCAPhase,
    Task,
    TaskStatus,
)

# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def simple_milestone():
    """完了済みサイクル1つを持つマイルストーン。"""
    return Milestone(
        id="ms-1",
        title="テストMS",
        cycles=[
            Cycle(
                cycle_number=1,
                phase=PDCAPhase.ACT,
                status=CycleStatus.COMPLETED,
                completed_at=1000.0,
                tasks=[
                    Task(
                        id="t-1",
                        title="タスク1",
                        status=TaskStatus.COMPLETED,
                        pr_number=101,
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def multi_cycle_milestone():
    """複数サイクル・依存関係を持つマイルストーン。"""
    return Milestone(
        id="ms-2",
        title="マルチサイクルMS",
        cycles=[
            Cycle(
                cycle_number=1,
                phase=PDCAPhase.ACT,
                status=CycleStatus.COMPLETED,
                completed_at=1000.0,
                tasks=[
                    Task(
                        id="t-1",
                        title="基盤タスク",
                        status=TaskStatus.COMPLETED,
                        pr_number=10,
                    ),
                ],
            ),
            Cycle(
                cycle_number=2,
                phase=PDCAPhase.ACT,
                status=CycleStatus.COMPLETED,
                completed_at=2000.0,
                tasks=[
                    Task(
                        id="t-2",
                        title="依存タスク",
                        status=TaskStatus.COMPLETED,
                        pr_number=20,
                        dependencies=["t-1"],
                    ),
                    Task(
                        id="t-3",
                        title="独立タスク",
                        status=TaskStatus.COMPLETED,
                        pr_number=30,
                    ),
                ],
            ),
            Cycle(
                cycle_number=3,
                phase=PDCAPhase.DO,
                status=CycleStatus.RUNNING,
                tasks=[
                    Task(
                        id="t-4",
                        title="進行中タスク",
                        status=TaskStatus.IN_PROGRESS,
                        pr_number=40,
                        dependencies=["t-2"],
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def checker():
    return StateConsistencyChecker()


@pytest.fixture
def chain_detector():
    return RollbackChainDetector()


# ============================================================
# テスト: RollbackLevel
# ============================================================


class TestRollbackLevel:
    def test_values(self):
        assert RollbackLevel.TASK == "task"
        assert RollbackLevel.CYCLE == "cycle"
        assert RollbackLevel.MILESTONE == "milestone"

    def test_is_str(self):
        assert isinstance(RollbackLevel.TASK, str)


# ============================================================
# テスト: RollbackCandidate (level フィールド追加)
# ============================================================


class TestRollbackCandidateLevel:
    def test_default_level_is_cycle(self):
        candidate = RollbackCandidate()
        assert candidate.level == RollbackLevel.CYCLE

    def test_explicit_level(self):
        candidate = RollbackCandidate(level=RollbackLevel.TASK)
        assert candidate.level == RollbackLevel.TASK

    def test_milestone_level(self):
        candidate = RollbackCandidate(level=RollbackLevel.MILESTONE)
        assert candidate.level == RollbackLevel.MILESTONE

    def test_id_prefix(self):
        candidate = RollbackCandidate()
        assert candidate.id.startswith("rb-")


# ============================================================
# テスト: RollbackPreview
# ============================================================


class TestRollbackPreview:
    def test_from_milestone_collects_prs(self, multi_cycle_milestone):
        candidate = RollbackCandidate(target_cycle=1)
        preview = RollbackPreview.from_milestone(
            candidate, multi_cycle_milestone,
        )
        assert 20 in preview.affected_pr_numbers
        assert 30 in preview.affected_pr_numbers
        assert 40 in preview.affected_pr_numbers
        assert 10 not in preview.affected_pr_numbers

    def test_from_milestone_collects_dependencies(self, multi_cycle_milestone):
        candidate = RollbackCandidate(target_cycle=1)
        preview = RollbackPreview.from_milestone(
            candidate, multi_cycle_milestone,
        )
        assert "t-1" in preview.dependent_task_ids
        assert "t-2" in preview.dependent_task_ids

    def test_risk_low_for_few_prs(self, simple_milestone):
        candidate = RollbackCandidate(target_cycle=0)
        preview = RollbackPreview.from_milestone(
            candidate, simple_milestone,
        )
        assert preview.estimated_risk == "low"

    def test_risk_medium(self, multi_cycle_milestone):
        candidate = RollbackCandidate(target_cycle=1)
        preview = RollbackPreview.from_milestone(
            candidate, multi_cycle_milestone,
        )
        assert preview.estimated_risk == "medium"

    def test_risk_high_for_many_prs(self):
        """PR数が5以上の場合はhighリスク。"""
        cycles = []
        for i in range(1, 7):
            cycles.append(Cycle(
                cycle_number=i,
                phase=PDCAPhase.ACT,
                status=CycleStatus.COMPLETED,
                completed_at=float(i * 1000),
                tasks=[
                    Task(
                        id=f"t-{i}",
                        title=f"タスク{i}",
                        status=TaskStatus.COMPLETED,
                        pr_number=i * 100,
                    ),
                ],
            ))
        ms = Milestone(id="ms-many", title="多PR", cycles=cycles)
        candidate = RollbackCandidate(target_cycle=0)
        preview = RollbackPreview.from_milestone(candidate, ms)
        assert preview.estimated_risk == "high"

    def test_empty_milestone(self):
        ms = Milestone(id="ms-empty", title="空")
        candidate = RollbackCandidate(target_cycle=0)
        preview = RollbackPreview.from_milestone(candidate, ms)
        assert preview.affected_pr_numbers == []
        assert preview.estimated_risk == "low"


# ============================================================
# テスト: StateConsistencyChecker
# ============================================================


class TestStateConsistencyChecker:
    def test_consistent_milestone(self, checker, simple_milestone):
        assert checker.check_all(simple_milestone) is True
        assert checker.is_consistent
        assert checker.errors == []

    def test_completed_without_timestamp(self, checker):
        ms = Milestone(
            id="ms-bad",
            title="不整合",
            cycles=[
                Cycle(
                    cycle_number=1,
                    phase=PDCAPhase.ACT,
                    status=CycleStatus.COMPLETED,
                    completed_at=None,
                ),
            ],
        )
        assert checker.check_all(ms) is False
        assert any("completed_at" in e for e in checker.errors)

    def test_cycle_numbering_gap(self, checker):
        ms = Milestone(
            id="ms-gap",
            title="番号飛び",
            cycles=[
                Cycle(
                    cycle_number=1,
                    phase=PDCAPhase.ACT,
                    status=CycleStatus.COMPLETED,
                    completed_at=1000.0,
                ),
                Cycle(
                    cycle_number=3,
                    phase=PDCAPhase.PLAN,
                    status=CycleStatus.RUNNING,
                ),
            ],
        )
        assert checker.check_all(ms) is False
        assert any("サイクル番号不整合" in e for e in checker.errors)

    def test_in_progress_task_in_completed_cycle(self, checker):
        ms = Milestone(
            id="ms-task",
            title="タスク不整合",
            cycles=[
                Cycle(
                    cycle_number=1,
                    phase=PDCAPhase.ACT,
                    status=CycleStatus.COMPLETED,
                    completed_at=1000.0,
                    tasks=[
                        Task(
                            id="t-1",
                            title="残留タスク",
                            status=TaskStatus.IN_PROGRESS,
                        ),
                    ],
                ),
            ],
        )
        assert checker.check_all(ms) is False
        assert any("IN_PROGRESS" in e for e in checker.errors)

    def test_audit_chain_valid(self, checker, simple_milestone):
        e1 = AuditEntry(
            sequence=0, actor="system", action="start",
            entry_hash="aaa",
        )
        e2 = AuditEntry(
            sequence=1, actor="system", action="stop",
            previous_hash="aaa", entry_hash="bbb",
        )
        assert checker.check_all(simple_milestone, [e1, e2]) is True

    def test_audit_chain_broken(self, checker, simple_milestone):
        e1 = AuditEntry(
            sequence=0, actor="system", action="start",
            entry_hash="aaa",
        )
        e2 = AuditEntry(
            sequence=1, actor="system", action="stop",
            previous_hash="WRONG", entry_hash="bbb",
        )
        assert checker.check_all(simple_milestone, [e1, e2]) is False
        assert any("previous_hash" in e for e in checker.errors)

    def test_check_all_resets_errors(self, checker):
        """check_allを再度呼ぶと前回のエラーがクリアされる。"""
        bad = Milestone(
            id="ms-bad", title="bad",
            cycles=[
                Cycle(
                    cycle_number=2,
                    phase=PDCAPhase.PLAN,
                    status=CycleStatus.RUNNING,
                ),
            ],
        )
        checker.check_all(bad)
        assert not checker.is_consistent

        good = Milestone(
            id="ms-good", title="good",
            cycles=[
                Cycle(
                    cycle_number=1,
                    phase=PDCAPhase.PLAN,
                    status=CycleStatus.RUNNING,
                ),
            ],
        )
        checker.check_all(good)
        assert checker.is_consistent


# ============================================================
# テスト: RollbackChainDetector
# ============================================================


class TestRollbackChainDetector:
    def test_no_chain_for_independent_task(
        self, chain_detector, multi_cycle_milestone,
    ):
        chain = chain_detector.detect("t-3", multi_cycle_milestone)
        assert chain == []

    def test_detects_direct_dependency(
        self, chain_detector, multi_cycle_milestone,
    ):
        chain = chain_detector.detect("t-1", multi_cycle_milestone)
        ids = [link.task_id for link in chain]
        assert "t-2" in ids

    def test_detects_transitive_chain(
        self, chain_detector, multi_cycle_milestone,
    ):
        chain = chain_detector.detect("t-1", multi_cycle_milestone)
        ids = [link.task_id for link in chain]
        assert "t-2" in ids
        assert "t-4" in ids

    def test_chain_links_have_reason(
        self, chain_detector, multi_cycle_milestone,
    ):
        chain = chain_detector.detect("t-1", multi_cycle_milestone)
        assert all(isinstance(link, RollbackChainLink) for link in chain)
        assert all(link.reason for link in chain)

    def test_no_duplicates_in_chain(self, chain_detector):
        """ダイヤモンド依存でも重複なし。"""
        ms = Milestone(
            id="ms-diamond",
            title="ダイヤモンド依存",
            cycles=[
                Cycle(
                    cycle_number=1,
                    phase=PDCAPhase.ACT,
                    status=CycleStatus.COMPLETED,
                    completed_at=1000.0,
                    tasks=[
                        Task(id="a", title="A", status=TaskStatus.COMPLETED),
                        Task(
                            id="b", title="B",
                            status=TaskStatus.COMPLETED,
                            dependencies=["a"],
                        ),
                        Task(
                            id="c", title="C",
                            status=TaskStatus.COMPLETED,
                            dependencies=["a"],
                        ),
                        Task(
                            id="d", title="D",
                            status=TaskStatus.COMPLETED,
                            dependencies=["b", "c"],
                        ),
                    ],
                ),
            ],
        )
        chain = chain_detector.detect("a", ms)
        ids = [link.task_id for link in chain]
        assert len(ids) == len(set(ids)), "重複があります"
        assert "b" in ids
        assert "c" in ids
        assert "d" in ids

    def test_empty_milestone(self, chain_detector):
        ms = Milestone(id="ms-empty", title="空")
        chain = chain_detector.detect("t-1", ms)
        assert chain == []
