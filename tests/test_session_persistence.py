"""セッション永続化とクラッシュリカバリのテスト。"""

from __future__ import annotations

from vibe_pdca.engine.session_persistence import (
    CheckpointData,
    CheckpointManager,
    CrashRecoveryManager,
    DirtyShutdownFlag,
)

# ── CheckpointData ──


class TestCheckpointData:
    """CheckpointDataデータクラスのテスト。"""

    def test_defaults(self) -> None:
        cp = CheckpointData(cycle_number=1, phase="plan")
        assert cp.state == {}
        assert cp.timestamp > 0
        assert cp.checksum == ""

    def test_custom_fields(self) -> None:
        cp = CheckpointData(
            cycle_number=3,
            phase="check",
            state={"key": "value"},
            timestamp=1000.0,
            checksum="abc",
        )
        assert cp.cycle_number == 3
        assert cp.phase == "check"
        assert cp.state == {"key": "value"}
        assert cp.timestamp == 1000.0
        assert cp.checksum == "abc"


# ── DirtyShutdownFlag ──


class TestDirtyShutdownFlag:
    """DirtyShutdownFlagデータクラスのテスト。"""

    def test_defaults(self) -> None:
        flag = DirtyShutdownFlag()
        assert flag.is_dirty is False
        assert flag.last_clean_shutdown == 0.0
        assert flag.process_id == ""

    def test_custom_fields(self) -> None:
        flag = DirtyShutdownFlag(
            is_dirty=True,
            last_clean_shutdown=999.0,
            process_id="proc-1",
        )
        assert flag.is_dirty is True
        assert flag.last_clean_shutdown == 999.0
        assert flag.process_id == "proc-1"


# ── CheckpointManager ──


class TestCheckpointManager:
    """CheckpointManagerのテスト。"""

    def _make_manager(self) -> CheckpointManager:
        return CheckpointManager()

    def test_save_and_load(self) -> None:
        mgr = self._make_manager()
        cp = CheckpointData(
            cycle_number=1,
            phase="plan",
            state={"step": 1},
        )
        assert mgr.save(cp)
        loaded = mgr.load()
        assert loaded is cp
        assert loaded.checksum != ""

    def test_load_empty(self) -> None:
        mgr = self._make_manager()
        assert mgr.load() is None

    def test_list_checkpoints(self) -> None:
        mgr = self._make_manager()
        cp1 = CheckpointData(cycle_number=1, phase="plan")
        cp2 = CheckpointData(cycle_number=2, phase="do")
        mgr.save(cp1)
        mgr.save(cp2)
        cps = mgr.list_checkpoints()
        assert len(cps) == 2

    def test_load_returns_latest(self) -> None:
        mgr = self._make_manager()
        mgr.save(CheckpointData(cycle_number=1, phase="plan"))
        mgr.save(CheckpointData(cycle_number=2, phase="do"))
        loaded = mgr.load()
        assert loaded is not None
        assert loaded.cycle_number == 2

    def test_validate_valid(self) -> None:
        mgr = self._make_manager()
        cp = CheckpointData(
            cycle_number=1,
            phase="plan",
            state={"a": 1},
        )
        mgr.save(cp)
        assert mgr.validate(cp) is True

    def test_validate_corrupted(self) -> None:
        mgr = self._make_manager()
        cp = CheckpointData(
            cycle_number=1,
            phase="plan",
            state={"a": 1},
            checksum="bad_checksum",
        )
        assert mgr.validate(cp) is False

    def test_compute_checksum_deterministic(self) -> None:
        state = {"x": 1, "y": 2}
        c1 = CheckpointManager.compute_checksum(state)
        c2 = CheckpointManager.compute_checksum(state)
        assert c1 == c2

    def test_compute_checksum_key_order(self) -> None:
        c1 = CheckpointManager.compute_checksum({"a": 1, "b": 2})
        c2 = CheckpointManager.compute_checksum({"b": 2, "a": 1})
        assert c1 == c2

    def test_auto_checksum_on_save(self) -> None:
        mgr = self._make_manager()
        cp = CheckpointData(
            cycle_number=1,
            phase="plan",
            state={"key": "val"},
        )
        assert cp.checksum == ""
        mgr.save(cp)
        assert cp.checksum != ""


# ── CrashRecoveryManager ──


class TestCrashRecoveryManager:
    """CrashRecoveryManagerのテスト。"""

    def test_detect_dirty_true(self) -> None:
        rm = CrashRecoveryManager()
        flag = DirtyShutdownFlag(is_dirty=True, process_id="p-1")
        assert rm.detect_dirty_shutdown(flag) is True

    def test_detect_dirty_false(self) -> None:
        rm = CrashRecoveryManager()
        flag = DirtyShutdownFlag(is_dirty=False)
        assert rm.detect_dirty_shutdown(flag) is False

    def test_recover_success(self) -> None:
        mgr = CheckpointManager()
        cp = CheckpointData(
            cycle_number=1,
            phase="do",
            state={"s": 1},
        )
        mgr.save(cp)
        rm = CrashRecoveryManager()
        recovered = rm.recover(mgr)
        assert recovered is cp

    def test_recover_empty(self) -> None:
        mgr = CheckpointManager()
        rm = CrashRecoveryManager()
        assert rm.recover(mgr) is None

    def test_recover_skips_corrupted(self) -> None:
        mgr = CheckpointManager()
        cp1 = CheckpointData(
            cycle_number=1,
            phase="plan",
            state={"a": 1},
        )
        mgr.save(cp1)
        cp2 = CheckpointData(
            cycle_number=2,
            phase="do",
            state={"b": 2},
            checksum="corrupt",
        )
        mgr._checkpoints.append(cp2)
        rm = CrashRecoveryManager()
        recovered = rm.recover(mgr)
        assert recovered is not None
        assert recovered.cycle_number == 1

    def test_mark_clean_shutdown(self) -> None:
        rm = CrashRecoveryManager()
        flag = DirtyShutdownFlag(is_dirty=True, process_id="p-1")
        updated = rm.mark_clean_shutdown(flag)
        assert updated.is_dirty is False
        assert updated.last_clean_shutdown > 0

    def test_mark_start(self) -> None:
        rm = CrashRecoveryManager()
        flag = DirtyShutdownFlag(is_dirty=False, process_id="p-2")
        updated = rm.mark_start(flag)
        assert updated.is_dirty is True
