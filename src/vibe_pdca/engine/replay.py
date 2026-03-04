"""サイクルリプレイ・デバッグモード – 過去サイクルの再生・差分比較・ステップ実行。

Proposal 29: Cycle Replay and Debug Mode。

入力: 記録されたサイクルスナップショット
出力: リプレイ結果・差分・フェーズごとのデバッグ情報
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# データクラス
# ============================================================


@dataclass
class PhaseSnapshot:
    """フェーズ単位のスナップショット。"""

    phase: str  # PDCAPhase の値
    prompt: str = ""
    response: str = ""
    decision: str = ""
    ci_result: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class CycleSnapshot:
    """サイクル全体のスナップショット。"""

    cycle_number: int
    goal_id: str
    snapshots: list[PhaseSnapshot] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None


@dataclass
class ReplayResult:
    """リプレイ実行結果。"""

    cycle_number: int
    phase_results: list[dict[str, Any]] = field(default_factory=list)
    deviations: list[str] = field(default_factory=list)
    success: bool = True


# ============================================================
# SnapshotRecorder – スナップショット記録
# ============================================================


class SnapshotRecorder:
    """サイクル実行中の各フェーズ状態を記録する。"""

    def __init__(self) -> None:
        self._snapshots: dict[int, CycleSnapshot] = {}
        self._current: CycleSnapshot | None = None

    def start_cycle(self, cycle_number: int, goal_id: str) -> None:
        """新しいサイクルの記録を開始する。"""
        logger.info("サイクル %d の記録を開始 (goal=%s)", cycle_number, goal_id)
        self._current = CycleSnapshot(
            cycle_number=cycle_number,
            goal_id=goal_id,
            started_at=time.time(),
        )

    def record_phase(
        self,
        phase: str,
        prompt: str = "",
        response: str = "",
        decision: str = "",
        ci_result: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """フェーズの実行結果を記録する。"""
        if self._current is None:
            raise RuntimeError("サイクルが開始されていません")
        snapshot = PhaseSnapshot(
            phase=phase,
            prompt=prompt,
            response=response,
            decision=decision,
            ci_result=ci_result,
            metadata=metadata or {},
        )
        self._current.snapshots.append(snapshot)
        logger.info("フェーズ '%s' を記録", phase)

    def end_cycle(self) -> CycleSnapshot:
        """現在のサイクル記録を完了して返す。"""
        if self._current is None:
            raise RuntimeError("サイクルが開始されていません")
        self._current.completed_at = time.time()
        completed = self._current
        self._snapshots[completed.cycle_number] = completed
        self._current = None
        logger.info("サイクル %d の記録を完了", completed.cycle_number)
        return completed

    def get_snapshot(self, cycle_number: int) -> CycleSnapshot | None:
        """指定サイクルのスナップショットを取得する。"""
        return self._snapshots.get(cycle_number)

    def list_snapshots(self) -> list[int]:
        """記録済みサイクル番号の一覧を返す。"""
        return sorted(self._snapshots.keys())

    @property
    def snapshot_count(self) -> int:
        """記録済みスナップショット数。"""
        return len(self._snapshots)


# ============================================================
# ReplayEngine – サイクルリプレイ
# ============================================================


class ReplayEngine:
    """記録済みスナップショットを用いてサイクルを再生する。"""

    def __init__(self, recorder: SnapshotRecorder) -> None:
        self._recorder = recorder

    def replay(self, cycle_number: int) -> ReplayResult:
        """記録されたレスポンスを用いてサイクルをリプレイする。"""
        snapshot = self._recorder.get_snapshot(cycle_number)
        if snapshot is None:
            logger.warning("サイクル %d のスナップショットが見つかりません", cycle_number)
            return ReplayResult(
                cycle_number=cycle_number,
                success=False,
                deviations=[f"サイクル {cycle_number} のスナップショットが存在しません"],
            )

        phase_results: list[dict[str, Any]] = []
        for ps in snapshot.snapshots:
            phase_results.append(
                {
                    "phase": ps.phase,
                    "prompt": ps.prompt,
                    "response": ps.response,
                    "decision": ps.decision,
                    "ci_result": ps.ci_result,
                }
            )

        logger.info("サイクル %d のリプレイ完了 (%d フェーズ)", cycle_number, len(phase_results))
        return ReplayResult(
            cycle_number=cycle_number,
            phase_results=phase_results,
            success=True,
        )

    def replay_with_override(
        self,
        cycle_number: int,
        overrides: dict[str, str],
    ) -> ReplayResult:
        """What-if 分析: 指定フェーズのレスポンスを差し替えてリプレイする。"""
        snapshot = self._recorder.get_snapshot(cycle_number)
        if snapshot is None:
            return ReplayResult(
                cycle_number=cycle_number,
                success=False,
                deviations=[f"サイクル {cycle_number} のスナップショットが存在しません"],
            )

        phase_results: list[dict[str, Any]] = []
        deviations: list[str] = []
        for ps in snapshot.snapshots:
            response = ps.response
            if ps.phase in overrides:
                response = overrides[ps.phase]
                deviations.append(
                    f"フェーズ '{ps.phase}': レスポンスをオーバーライド"
                )
            phase_results.append(
                {
                    "phase": ps.phase,
                    "prompt": ps.prompt,
                    "response": response,
                    "decision": ps.decision,
                    "ci_result": ps.ci_result,
                }
            )

        logger.info(
            "サイクル %d の What-if リプレイ完了 (差分 %d 件)",
            cycle_number,
            len(deviations),
        )
        return ReplayResult(
            cycle_number=cycle_number,
            phase_results=phase_results,
            deviations=deviations,
            success=True,
        )

    def compare(self, cycle_a: int, cycle_b: int) -> list[str]:
        """2つのサイクルの差分を返す。"""
        snap_a = self._recorder.get_snapshot(cycle_a)
        snap_b = self._recorder.get_snapshot(cycle_b)
        differences: list[str] = []

        if snap_a is None:
            differences.append(f"サイクル {cycle_a} が見つかりません")
        if snap_b is None:
            differences.append(f"サイクル {cycle_b} が見つかりません")
        if snap_a is None or snap_b is None:
            return differences

        if snap_a.goal_id != snap_b.goal_id:
            differences.append(
                f"goal_id が異なる: '{snap_a.goal_id}' vs '{snap_b.goal_id}'"
            )

        len_a = len(snap_a.snapshots)
        len_b = len(snap_b.snapshots)
        if len_a != len_b:
            differences.append(f"フェーズ数が異なる: {len_a} vs {len_b}")

        for i, (pa, pb) in enumerate(zip(snap_a.snapshots, snap_b.snapshots, strict=False)):
            if pa.phase != pb.phase:
                differences.append(f"フェーズ[{i}] の種類が異なる: '{pa.phase}' vs '{pb.phase}'")
            if pa.response != pb.response:
                differences.append(f"フェーズ[{i}] ({pa.phase}) のレスポンスが異なる")
            if pa.decision != pb.decision:
                differences.append(f"フェーズ[{i}] ({pa.phase}) の判定が異なる")
            if pa.ci_result != pb.ci_result:
                differences.append(f"フェーズ[{i}] ({pa.phase}) の CI 結果が異なる")

        return differences


# ============================================================
# DebugSession – デバッグセッション
# ============================================================


class DebugSession:
    """ブレークポイント設定・ステップ実行によるデバッグ機能を提供する。"""

    def __init__(self, recorder: SnapshotRecorder) -> None:
        self._recorder = recorder
        self._breakpoints: set[str] = set()

    def set_breakpoint(self, phase: str) -> None:
        """指定フェーズにブレークポイントを設定する。"""
        self._breakpoints.add(phase)
        logger.info("ブレークポイント設定: '%s'", phase)

    def remove_breakpoint(self, phase: str) -> None:
        """指定フェーズのブレークポイントを解除する。"""
        self._breakpoints.discard(phase)
        logger.info("ブレークポイント解除: '%s'", phase)

    def get_breakpoints(self) -> list[str]:
        """設定済みブレークポイント一覧を返す。"""
        return sorted(self._breakpoints)

    def step_through(
        self,
        cycle_number: int,
    ) -> list[tuple[str, PhaseSnapshot]]:
        """サイクルをフェーズごとにステップ実行し、結果を返す。"""
        snapshot = self._recorder.get_snapshot(cycle_number)
        if snapshot is None:
            logger.warning("サイクル %d が見つかりません", cycle_number)
            return []

        steps: list[tuple[str, PhaseSnapshot]] = []
        for ps in snapshot.snapshots:
            label = f"[BREAK] {ps.phase}" if ps.phase in self._breakpoints else ps.phase
            steps.append((label, ps))

        logger.info("サイクル %d のステップ実行完了 (%d ステップ)", cycle_number, len(steps))
        return steps

    def get_state_at_phase(
        self,
        cycle_number: int,
        phase: str,
    ) -> PhaseSnapshot | None:
        """指定サイクル・フェーズのスナップショットを返す。"""
        snapshot = self._recorder.get_snapshot(cycle_number)
        if snapshot is None:
            return None
        for ps in snapshot.snapshots:
            if ps.phase == phase:
                return ps
        return None
