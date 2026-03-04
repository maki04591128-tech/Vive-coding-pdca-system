"""Proposal 29: Cycle Replay and Debug Mode のテスト。"""

from __future__ import annotations

import time

import pytest

from vibe_pdca.engine.replay import (
    CycleSnapshot,
    DebugSession,
    PhaseSnapshot,
    ReplayEngine,
    ReplayResult,
    SnapshotRecorder,
)


# ============================================================
# PhaseSnapshot データクラス
# ============================================================


class TestPhaseSnapshot:
    """PhaseSnapshot データクラスのテスト。"""

    def test_defaults(self) -> None:
        ps = PhaseSnapshot(phase="plan")
        assert ps.phase == "plan"
        assert ps.prompt == ""
        assert ps.response == ""
        assert ps.decision == ""
        assert ps.ci_result == ""
        assert ps.metadata == {}
        assert ps.timestamp > 0

    def test_with_values(self) -> None:
        ps = PhaseSnapshot(
            phase="do",
            prompt="実装して",
            response="完了",
            decision="accept",
            ci_result="passed",
            metadata={"key": "value"},
        )
        assert ps.prompt == "実装して"
        assert ps.metadata["key"] == "value"


# ============================================================
# CycleSnapshot データクラス
# ============================================================


class TestCycleSnapshot:
    """CycleSnapshot データクラスのテスト。"""

    def test_defaults(self) -> None:
        cs = CycleSnapshot(cycle_number=1, goal_id="g-001")
        assert cs.cycle_number == 1
        assert cs.goal_id == "g-001"
        assert cs.snapshots == []
        assert cs.completed_at is None

    def test_with_snapshots(self) -> None:
        ps = PhaseSnapshot(phase="plan")
        cs = CycleSnapshot(cycle_number=2, goal_id="g-002", snapshots=[ps])
        assert len(cs.snapshots) == 1


# ============================================================
# ReplayResult データクラス
# ============================================================


class TestReplayResult:
    """ReplayResult データクラスのテスト。"""

    def test_defaults(self) -> None:
        rr = ReplayResult(cycle_number=1)
        assert rr.cycle_number == 1
        assert rr.phase_results == []
        assert rr.deviations == []
        assert rr.success is True


# ============================================================
# SnapshotRecorder
# ============================================================


class TestSnapshotRecorder:
    """SnapshotRecorder のテスト。"""

    def setup_method(self) -> None:
        self.recorder = SnapshotRecorder()

    def test_start_and_end_cycle(self) -> None:
        self.recorder.start_cycle(1, "goal-1")
        self.recorder.record_phase("plan", prompt="p", response="r")
        cs = self.recorder.end_cycle()
        assert cs.cycle_number == 1
        assert cs.completed_at is not None
        assert len(cs.snapshots) == 1

    def test_record_phase_without_start_raises(self) -> None:
        with pytest.raises(RuntimeError):
            self.recorder.record_phase("plan")

    def test_end_cycle_without_start_raises(self) -> None:
        with pytest.raises(RuntimeError):
            self.recorder.end_cycle()

    def test_get_snapshot(self) -> None:
        self.recorder.start_cycle(1, "goal-1")
        self.recorder.end_cycle()
        assert self.recorder.get_snapshot(1) is not None
        assert self.recorder.get_snapshot(999) is None

    def test_list_snapshots(self) -> None:
        for i in [3, 1, 2]:
            self.recorder.start_cycle(i, f"g-{i}")
            self.recorder.end_cycle()
        assert self.recorder.list_snapshots() == [1, 2, 3]

    def test_snapshot_count(self) -> None:
        assert self.recorder.snapshot_count == 0
        self.recorder.start_cycle(1, "g")
        self.recorder.end_cycle()
        assert self.recorder.snapshot_count == 1


# ============================================================
# ReplayEngine
# ============================================================


class TestReplayEngine:
    """ReplayEngine のテスト。"""

    def setup_method(self) -> None:
        self.recorder = SnapshotRecorder()
        self.engine = ReplayEngine(self.recorder)

    def _record_cycle(self, num: int) -> None:
        self.recorder.start_cycle(num, f"goal-{num}")
        self.recorder.record_phase("plan", prompt="p1", response="r1", decision="accept")
        self.recorder.record_phase("do", prompt="p2", response="r2", ci_result="pass")
        self.recorder.end_cycle()

    def test_replay_success(self) -> None:
        self._record_cycle(1)
        result = self.engine.replay(1)
        assert result.success is True
        assert len(result.phase_results) == 2
        assert result.phase_results[0]["phase"] == "plan"

    def test_replay_missing_cycle(self) -> None:
        result = self.engine.replay(99)
        assert result.success is False
        assert len(result.deviations) == 1

    def test_replay_with_override(self) -> None:
        self._record_cycle(1)
        result = self.engine.replay_with_override(1, {"plan": "new_response"})
        assert result.success is True
        assert result.phase_results[0]["response"] == "new_response"
        assert len(result.deviations) == 1

    def test_replay_with_override_missing(self) -> None:
        result = self.engine.replay_with_override(99, {})
        assert result.success is False

    def test_compare_same_cycle(self) -> None:
        self._record_cycle(1)
        diffs = self.engine.compare(1, 1)
        assert diffs == []

    def test_compare_different_cycles(self) -> None:
        self._record_cycle(1)
        self.recorder.start_cycle(2, "goal-2")
        self.recorder.record_phase("plan", prompt="p1", response="different")
        self.recorder.end_cycle()
        diffs = self.engine.compare(1, 2)
        assert len(diffs) > 0

    def test_compare_missing_cycle(self) -> None:
        diffs = self.engine.compare(1, 2)
        assert len(diffs) == 2


# ============================================================
# DebugSession
# ============================================================


class TestDebugSession:
    """DebugSession のテスト。"""

    def setup_method(self) -> None:
        self.recorder = SnapshotRecorder()
        self.debug = DebugSession(self.recorder)

    def _record_cycle(self) -> None:
        self.recorder.start_cycle(1, "goal-1")
        self.recorder.record_phase("plan", prompt="p1")
        self.recorder.record_phase("do", prompt="p2")
        self.recorder.record_phase("check", prompt="p3")
        self.recorder.end_cycle()

    def test_set_and_get_breakpoints(self) -> None:
        self.debug.set_breakpoint("plan")
        self.debug.set_breakpoint("check")
        assert self.debug.get_breakpoints() == ["check", "plan"]

    def test_remove_breakpoint(self) -> None:
        self.debug.set_breakpoint("plan")
        self.debug.remove_breakpoint("plan")
        assert self.debug.get_breakpoints() == []

    def test_remove_nonexistent_breakpoint(self) -> None:
        self.debug.remove_breakpoint("nonexistent")
        assert self.debug.get_breakpoints() == []

    def test_step_through(self) -> None:
        self._record_cycle()
        self.debug.set_breakpoint("do")
        steps = self.debug.step_through(1)
        assert len(steps) == 3
        assert steps[0][0] == "plan"
        assert steps[1][0] == "[BREAK] do"
        assert steps[2][0] == "check"

    def test_step_through_missing_cycle(self) -> None:
        steps = self.debug.step_through(99)
        assert steps == []

    def test_get_state_at_phase(self) -> None:
        self._record_cycle()
        ps = self.debug.get_state_at_phase(1, "do")
        assert ps is not None
        assert ps.phase == "do"
        assert ps.prompt == "p2"

    def test_get_state_at_phase_missing_cycle(self) -> None:
        assert self.debug.get_state_at_phase(99, "plan") is None

    def test_get_state_at_phase_missing_phase(self) -> None:
        self._record_cycle()
        assert self.debug.get_state_at_phase(1, "nonexistent") is None
