"""タイムアウト戦略のテスト。"""

import time

from vibe_pdca.engine.timeout_strategy import (
    ComplexityBasedTimeout,
    EscalationEvent,
    PhaseTimeout,
    ProgressBasedExtension,
    TimeoutEscalation,
    TimeoutManager,
)
from vibe_pdca.models.pdca import PDCAPhase

# ============================================================
# テスト: PhaseTimeout
# ============================================================


class TestPhaseTimeout:
    def test_default_values(self):
        pt = PhaseTimeout()
        assert pt.plan == 30 * 60
        assert pt.do == 3 * 3600
        assert pt.check == 1 * 3600
        assert pt.act == 30 * 60

    def test_get_each_phase(self):
        pt = PhaseTimeout()
        assert pt.get(PDCAPhase.PLAN) == 30 * 60
        assert pt.get(PDCAPhase.DO) == 3 * 3600
        assert pt.get(PDCAPhase.CHECK) == 1 * 3600
        assert pt.get(PDCAPhase.ACT) == 30 * 60

    def test_custom_values(self):
        pt = PhaseTimeout(plan=600, do=7200, check=1800, act=300)
        assert pt.get(PDCAPhase.PLAN) == 600
        assert pt.get(PDCAPhase.DO) == 7200
        assert pt.get(PDCAPhase.CHECK) == 1800
        assert pt.get(PDCAPhase.ACT) == 300


# ============================================================
# テスト: TimeoutEscalation
# ============================================================


class TestTimeoutEscalation:
    def test_values(self):
        assert TimeoutEscalation.WARNING == 50
        assert TimeoutEscalation.INTERVENTION_REQUEST == 75
        assert TimeoutEscalation.STOP == 100

    def test_ordering(self):
        levels = sorted(TimeoutEscalation, key=lambda level: level.value)
        assert levels == [
            TimeoutEscalation.WARNING,
            TimeoutEscalation.INTERVENTION_REQUEST,
            TimeoutEscalation.STOP,
        ]


# ============================================================
# テスト: EscalationEvent
# ============================================================


class TestEscalationEvent:
    def test_creation(self):
        event = EscalationEvent(
            level=TimeoutEscalation.WARNING,
            phase=PDCAPhase.DO,
            elapsed_seconds=5400.0,
            timeout_seconds=10800.0,
            message="test",
        )
        assert event.level == TimeoutEscalation.WARNING
        assert event.phase == PDCAPhase.DO
        assert event.elapsed_seconds == 5400.0
        assert event.timeout_seconds == 10800.0
        assert event.message == "test"


# ============================================================
# テスト: ComplexityBasedTimeout
# ============================================================


class TestComplexityBasedTimeout:
    def test_no_complexity(self):
        cbt = ComplexityBasedTimeout(complexity_score=0.0)
        assert cbt.multiplier == 1.0
        assert cbt.adjust(1000) == 1000.0

    def test_half_complexity(self):
        cbt = ComplexityBasedTimeout(complexity_score=0.5, max_multiplier=3.0)
        assert cbt.multiplier == 2.0
        assert cbt.adjust(1000) == 2000.0

    def test_full_complexity(self):
        cbt = ComplexityBasedTimeout(complexity_score=1.0, max_multiplier=3.0)
        assert cbt.multiplier == 3.0
        assert cbt.adjust(1000) == 3000.0

    def test_custom_max_multiplier(self):
        cbt = ComplexityBasedTimeout(complexity_score=1.0, max_multiplier=5.0)
        assert cbt.multiplier == 5.0

    def test_invalid_score_raises(self):
        import pytest

        with pytest.raises(ValueError):
            ComplexityBasedTimeout(complexity_score=-0.1)
        with pytest.raises(ValueError):
            ComplexityBasedTimeout(complexity_score=1.1)

    def test_invalid_max_multiplier_raises(self):
        import pytest

        with pytest.raises(ValueError):
            ComplexityBasedTimeout(complexity_score=0.5, max_multiplier=0.5)

    def test_properties(self):
        cbt = ComplexityBasedTimeout(complexity_score=0.3, max_multiplier=4.0)
        assert cbt.complexity_score == 0.3
        assert cbt.max_multiplier == 4.0


# ============================================================
# テスト: ProgressBasedExtension
# ============================================================


class TestProgressBasedExtension:
    def test_initial_state(self):
        ext = ProgressBasedExtension(per_extension_seconds=600, max_extensions=3)
        assert ext.extensions_used == 0
        assert ext.remaining_extensions == 3
        assert ext.total_extension_seconds == 0.0

    def test_record_progress_extends(self):
        ext = ProgressBasedExtension(per_extension_seconds=600, max_extensions=3)
        added = ext.record_progress(progress=True)
        assert added == 600.0
        assert ext.extensions_used == 1
        assert ext.total_extension_seconds == 600.0

    def test_no_progress_no_extension(self):
        ext = ProgressBasedExtension(per_extension_seconds=600, max_extensions=3)
        added = ext.record_progress(progress=False)
        assert added == 0.0
        assert ext.extensions_used == 0

    def test_max_extensions_limit(self):
        ext = ProgressBasedExtension(per_extension_seconds=300, max_extensions=2)
        ext.record_progress(progress=True)
        ext.record_progress(progress=True)
        added = ext.record_progress(progress=True)
        assert added == 0.0
        assert ext.extensions_used == 2
        assert ext.total_extension_seconds == 600.0

    def test_reset(self):
        ext = ProgressBasedExtension(per_extension_seconds=600, max_extensions=3)
        ext.record_progress(progress=True)
        ext.reset()
        assert ext.extensions_used == 0
        assert ext.remaining_extensions == 3

    def test_properties(self):
        ext = ProgressBasedExtension(per_extension_seconds=900, max_extensions=5)
        assert ext.per_extension_seconds == 900.0
        assert ext.max_extensions == 5


# ============================================================
# テスト: TimeoutManager
# ============================================================


class TestTimeoutManager:
    def test_default_effective_timeout(self):
        mgr = TimeoutManager()
        assert mgr.get_effective_timeout(PDCAPhase.PLAN) == 30 * 60
        assert mgr.get_effective_timeout(PDCAPhase.DO) == 3 * 3600

    def test_effective_timeout_with_complexity(self):
        cbt = ComplexityBasedTimeout(complexity_score=0.5, max_multiplier=3.0)
        mgr = TimeoutManager(complexity=cbt)
        # DO: 3h * 2.0x = 6h = 21600s
        assert mgr.get_effective_timeout(PDCAPhase.DO) == 3 * 3600 * 2.0

    def test_effective_timeout_with_extension(self):
        ext = ProgressBasedExtension(per_extension_seconds=600, max_extensions=3)
        mgr = TimeoutManager(extension=ext)
        ext.record_progress(progress=True)
        # PLAN: 1800 + 600 = 2400
        assert mgr.get_effective_timeout(PDCAPhase.PLAN) == 1800 + 600

    def test_start_and_end_phase_records_stats(self):
        mgr = TimeoutManager()
        now = time.time()
        mgr.start_phase(PDCAPhase.PLAN, now=now)
        mgr.end_phase(PDCAPhase.PLAN, now=now + 500)
        stats = mgr.get_statistics()
        assert PDCAPhase.PLAN in stats
        assert stats[PDCAPhase.PLAN]["count"] == 1.0
        assert abs(stats[PDCAPhase.PLAN]["average"] - 500.0) < 1

    def test_check_escalations_no_start(self):
        mgr = TimeoutManager()
        events = mgr.check_escalations(PDCAPhase.PLAN)
        assert events == []

    def test_check_escalations_warning(self):
        pt = PhaseTimeout(plan=1000)
        mgr = TimeoutManager(phase_timeout=pt)
        now = time.time()
        mgr.start_phase(PDCAPhase.PLAN, now=now)
        # 55%経過 → WARNING のみ
        events = mgr.check_escalations(PDCAPhase.PLAN, now=now + 550)
        assert len(events) == 1
        assert events[0].level == TimeoutEscalation.WARNING

    def test_check_escalations_intervention(self):
        pt = PhaseTimeout(plan=1000)
        mgr = TimeoutManager(phase_timeout=pt)
        now = time.time()
        mgr.start_phase(PDCAPhase.PLAN, now=now)
        # 80%経過 → WARNING + INTERVENTION_REQUEST
        events = mgr.check_escalations(PDCAPhase.PLAN, now=now + 800)
        levels = {e.level for e in events}
        assert TimeoutEscalation.WARNING in levels
        assert TimeoutEscalation.INTERVENTION_REQUEST in levels

    def test_check_escalations_stop(self):
        pt = PhaseTimeout(plan=1000)
        mgr = TimeoutManager(phase_timeout=pt)
        now = time.time()
        mgr.start_phase(PDCAPhase.PLAN, now=now)
        # 100%経過 → 全レベル
        events = mgr.check_escalations(PDCAPhase.PLAN, now=now + 1000)
        levels = {e.level for e in events}
        assert TimeoutEscalation.WARNING in levels
        assert TimeoutEscalation.INTERVENTION_REQUEST in levels
        assert TimeoutEscalation.STOP in levels

    def test_escalation_fires_only_once(self):
        pt = PhaseTimeout(plan=1000)
        mgr = TimeoutManager(phase_timeout=pt)
        now = time.time()
        mgr.start_phase(PDCAPhase.PLAN, now=now)
        events1 = mgr.check_escalations(PDCAPhase.PLAN, now=now + 550)
        assert len(events1) == 1
        # 同じレベルは再発火しない
        events2 = mgr.check_escalations(PDCAPhase.PLAN, now=now + 600)
        assert len(events2) == 0

    def test_escalation_event_has_message(self):
        pt = PhaseTimeout(plan=1000)
        mgr = TimeoutManager(phase_timeout=pt)
        now = time.time()
        mgr.start_phase(PDCAPhase.PLAN, now=now)
        events = mgr.check_escalations(PDCAPhase.PLAN, now=now + 1000)
        for event in events:
            assert event.message
            assert "plan" in event.message

    def test_start_phase_resets_escalations(self):
        pt = PhaseTimeout(plan=1000)
        mgr = TimeoutManager(phase_timeout=pt)
        now = time.time()
        mgr.start_phase(PDCAPhase.PLAN, now=now)
        mgr.check_escalations(PDCAPhase.PLAN, now=now + 600)
        # 再開するとエスカレーションがリセット
        mgr.start_phase(PDCAPhase.PLAN, now=now + 700)
        events = mgr.check_escalations(PDCAPhase.PLAN, now=now + 700 + 550)
        assert len(events) == 1
        assert events[0].level == TimeoutEscalation.WARNING

    def test_statistics_multiple_cycles(self):
        mgr = TimeoutManager()
        now = time.time()
        mgr.start_phase(PDCAPhase.DO, now=now)
        mgr.end_phase(PDCAPhase.DO, now=now + 1000)
        mgr.start_phase(PDCAPhase.DO, now=now + 2000)
        mgr.end_phase(PDCAPhase.DO, now=now + 2000 + 2000)
        stats = mgr.get_statistics()
        assert stats[PDCAPhase.DO]["count"] == 2.0
        assert abs(stats[PDCAPhase.DO]["average"] - 1500.0) < 1
        assert abs(stats[PDCAPhase.DO]["min"] - 1000.0) < 1
        assert abs(stats[PDCAPhase.DO]["max"] - 2000.0) < 1

    def test_statistics_empty_phases(self):
        mgr = TimeoutManager()
        stats = mgr.get_statistics()
        assert stats == {}

    def test_properties_accessible(self):
        pt = PhaseTimeout()
        cbt = ComplexityBasedTimeout()
        ext = ProgressBasedExtension()
        mgr = TimeoutManager(phase_timeout=pt, complexity=cbt, extension=ext)
        assert mgr.phase_timeout is pt
        assert mgr.complexity is cbt
        assert mgr.extension is ext


# ============================================================
# テスト: スレッドセーフティ
# ============================================================


class TestTimeoutManagerThreadSafety:
    """TimeoutManager のスレッドセーフティ検証。"""

    def test_concurrent_start_end_phase(self):
        """複数スレッドからフェーズ開始・終了しても整合性が保たれる。"""
        import threading
        mgr = TimeoutManager()
        errors: list[str] = []

        def run_phases(tid: int) -> None:
            try:
                phase = list(PDCAPhase)[tid % len(PDCAPhase)]
                for _ in range(20):
                    mgr.start_phase(phase, now=float(tid * 1000))
                    mgr.end_phase(phase, now=float(tid * 1000 + 10))
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=run_phases, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        stats = mgr.get_statistics()
        assert len(stats) > 0

    def test_concurrent_get_effective_timeout_barrier(self):
        """Barrier同期で全スレッドが同時にget_effective_timeoutを呼び出す。"""
        import threading

        mgr = TimeoutManager()
        n_threads = 10
        ops_per_thread = 50
        barrier = threading.Barrier(n_threads)
        errors: list[Exception] = []

        def worker(tid: int) -> None:
            barrier.wait()
            try:
                for _ in range(ops_per_thread):
                    mgr.get_effective_timeout(PDCAPhase.PLAN)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(t,)) for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
