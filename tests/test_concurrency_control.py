"""マルチユーザー同時アクセス制御のテスト。"""

import threading
import time

from vibe_pdca.engine.concurrency_control import (
    ApprovalGuard,
    ConflictInfo,
    ExclusiveLockManager,
    LockType,
    OptimisticLockManager,
    ResourceLock,
)

# ============================================================
# テスト: LockType
# ============================================================


class TestLockType:
    def test_values(self):
        assert LockType.OPTIMISTIC == "optimistic"
        assert LockType.EXCLUSIVE == "exclusive"


# ============================================================
# テスト: ResourceLock
# ============================================================


class TestResourceLock:
    def test_creation(self):
        lock = ResourceLock(
            resource_id="r1",
            lock_type=LockType.OPTIMISTIC,
            holder="user-a",
            version=1,
            acquired_at=100.0,
            expires_at=200.0,
        )
        assert lock.resource_id == "r1"
        assert lock.lock_type == LockType.OPTIMISTIC
        assert lock.holder == "user-a"
        assert lock.version == 1
        assert lock.expires_at == 200.0

    def test_default_expires_at(self):
        lock = ResourceLock(
            resource_id="r1",
            lock_type=LockType.EXCLUSIVE,
            holder="user-b",
            version=0,
        )
        assert lock.expires_at is None


# ============================================================
# テスト: ConflictInfo
# ============================================================


class TestConflictInfo:
    def test_creation(self):
        ci = ConflictInfo(
            resource_id="r1",
            holder_a="alice",
            holder_b="bob",
            description="concurrent edit",
        )
        assert ci.resource_id == "r1"
        assert ci.holder_a == "alice"
        assert ci.holder_b == "bob"


# ============================================================
# テスト: OptimisticLockManager
# ============================================================


class TestOptimisticLockManager:
    def test_acquire_new_resource(self):
        mgr = OptimisticLockManager()
        lock = mgr.acquire("res-1", "alice", version=0)
        assert lock is not None
        assert lock.version == 1
        assert lock.holder == "alice"

    def test_acquire_version_mismatch(self):
        mgr = OptimisticLockManager()
        mgr.acquire("res-1", "alice", version=0)
        lock = mgr.acquire("res-1", "bob", version=0)
        assert lock is None

    def test_acquire_version_match(self):
        mgr = OptimisticLockManager()
        mgr.acquire("res-1", "alice", version=0)
        lock = mgr.acquire("res-1", "bob", version=1)
        assert lock is not None
        assert lock.version == 2
        assert lock.holder == "bob"

    def test_acquire_unregistered_nonzero_version(self):
        mgr = OptimisticLockManager()
        lock = mgr.acquire("res-1", "alice", version=5)
        assert lock is None

    def test_release_success(self):
        mgr = OptimisticLockManager()
        mgr.acquire("res-1", "alice", version=0)
        assert mgr.release("res-1", "alice") is True
        assert mgr.get_lock("res-1") is None

    def test_release_wrong_holder(self):
        mgr = OptimisticLockManager()
        mgr.acquire("res-1", "alice", version=0)
        assert mgr.release("res-1", "bob") is False

    def test_release_nonexistent(self):
        mgr = OptimisticLockManager()
        assert mgr.release("res-1", "alice") is False

    def test_check_version(self):
        mgr = OptimisticLockManager()
        assert mgr.check_version("res-1", 0) is True
        mgr.acquire("res-1", "alice", version=0)
        assert mgr.check_version("res-1", 1) is True
        assert mgr.check_version("res-1", 0) is False

    def test_get_lock(self):
        mgr = OptimisticLockManager()
        assert mgr.get_lock("res-1") is None
        mgr.acquire("res-1", "alice", version=0)
        lock = mgr.get_lock("res-1")
        assert lock is not None
        assert lock.holder == "alice"

    def test_list_locks(self):
        mgr = OptimisticLockManager()
        mgr.acquire("b", "alice", version=0)
        mgr.acquire("a", "bob", version=0)
        locks = mgr.list_locks()
        assert len(locks) == 2
        assert locks[0].resource_id == "a"
        assert locks[1].resource_id == "b"


# ============================================================
# テスト: ExclusiveLockManager
# ============================================================


class TestExclusiveLockManager:
    def test_acquire_success(self):
        mgr = ExclusiveLockManager()
        lock = mgr.acquire("res-1", "alice", ttl_seconds=60)
        assert lock is not None
        assert lock.holder == "alice"
        assert lock.expires_at is not None

    def test_acquire_already_locked(self):
        mgr = ExclusiveLockManager()
        mgr.acquire("res-1", "alice", ttl_seconds=60)
        lock = mgr.acquire("res-1", "bob", ttl_seconds=60)
        assert lock is None

    def test_acquire_after_expiry(self):
        mgr = ExclusiveLockManager()
        mgr.acquire("res-1", "alice", ttl_seconds=0)
        time.sleep(0.01)
        lock = mgr.acquire("res-1", "bob", ttl_seconds=60)
        assert lock is not None
        assert lock.holder == "bob"

    def test_release_success(self):
        mgr = ExclusiveLockManager()
        mgr.acquire("res-1", "alice", ttl_seconds=60)
        assert mgr.release("res-1", "alice") is True

    def test_release_wrong_holder(self):
        mgr = ExclusiveLockManager()
        mgr.acquire("res-1", "alice", ttl_seconds=60)
        assert mgr.release("res-1", "bob") is False

    def test_is_locked(self):
        mgr = ExclusiveLockManager()
        assert mgr.is_locked("res-1") is False
        mgr.acquire("res-1", "alice", ttl_seconds=60)
        assert mgr.is_locked("res-1") is True

    def test_is_locked_expired(self):
        mgr = ExclusiveLockManager()
        mgr.acquire("res-1", "alice", ttl_seconds=0)
        time.sleep(0.01)
        assert mgr.is_locked("res-1") is False

    def test_cleanup_expired(self):
        mgr = ExclusiveLockManager()
        mgr.acquire("res-1", "alice", ttl_seconds=0)
        mgr.acquire("res-2", "bob", ttl_seconds=300)
        time.sleep(0.01)
        removed = mgr.cleanup_expired()
        assert removed == 1
        assert mgr.is_locked("res-2") is True


# ============================================================
# テスト: ApprovalGuard
# ============================================================


class TestApprovalGuard:
    def test_submit_approval(self):
        guard = ApprovalGuard()
        assert guard.submit_approval("res-1", "alice") is True
        assert guard.is_approved("res-1") is True

    def test_submit_duplicate(self):
        guard = ApprovalGuard()
        guard.submit_approval("res-1", "alice")
        assert guard.submit_approval("res-1", "bob") is False

    def test_is_approved_false(self):
        guard = ApprovalGuard()
        assert guard.is_approved("res-1") is False

    def test_get_approver(self):
        guard = ApprovalGuard()
        assert guard.get_approver("res-1") is None
        guard.submit_approval("res-1", "alice")
        assert guard.get_approver("res-1") == "alice"

    def test_reset(self):
        guard = ApprovalGuard()
        guard.submit_approval("res-1", "alice")
        guard.reset("res-1")
        assert guard.is_approved("res-1") is False
        assert guard.get_approver("res-1") is None

    def test_reset_nonexistent(self):
        guard = ApprovalGuard()
        guard.reset("res-99")  # エラーにならないことを確認
        assert guard.is_approved("res-99") is False


# ============================================================
# テスト: スレッドセーフティ
# ============================================================


class TestOptimisticLockManagerThreadSafety:
    """楽観的ロックマネージャの並行アクセステスト。"""

    def test_concurrent_acquire_no_corruption(self):
        """複数スレッドから同時に acquire しても内部状態が壊れないこと。"""
        mgr = OptimisticLockManager()
        errors: list[Exception] = []

        def worker(i: int) -> None:
            try:
                mgr.acquire(f"res-{i}", f"holder-{i}", version=0)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(mgr.list_locks()) == 20


class TestExclusiveLockManagerThreadSafety:
    """排他ロックマネージャの並行アクセステスト。"""

    def test_concurrent_acquire_same_resource(self):
        """同一リソースへの並行 acquire で正確に1つだけ成功すること。"""
        mgr = ExclusiveLockManager()
        results: list[ResourceLock | None] = []
        lock = threading.Lock()

        def worker(holder: str) -> None:
            result = mgr.acquire("shared-res", holder, ttl_seconds=60)
            with lock:
                results.append(result)

        threads = [
            threading.Thread(target=worker, args=(f"h-{i}",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [r for r in results if r is not None]
        failures = [r for r in results if r is None]
        assert len(successes) == 1  # 排他ロックは1つだけ成功
        assert len(failures) == 9   # 残りは全て失敗


class TestApprovalGuardThreadSafety:
    """承認ガードの並行アクセステスト。"""

    def test_concurrent_submit_same_resource(self):
        """同一リソースへの並行承認で正確に1つだけ成功すること。"""
        guard = ApprovalGuard()
        results: list[bool] = []
        lock = threading.Lock()

        def worker(approver: str) -> None:
            result = guard.submit_approval("shared-res", approver)
            with lock:
                results.append(result)

        threads = [
            threading.Thread(target=worker, args=(f"approver-{i}",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count(True) == 1
        assert results.count(False) == 9
        assert guard.is_approved("shared-res") is True


class TestOptimisticLockBarrierThreadSafety:
    """OptimisticLockManagerのBarrierスレッドセーフティテスト。"""

    def test_concurrent_acquire_release(self):
        import threading

        manager = OptimisticLockManager()
        n_threads = 10
        ops_per_thread = 50
        barrier = threading.Barrier(n_threads)

        def worker(tid: int) -> None:
            barrier.wait()
            for i in range(ops_per_thread):
                resource_id = f"res-{tid}-{i}"
                holder = f"holder-{tid}"
                lock = manager.acquire(resource_id, holder, 0)
                if lock is not None:
                    manager.release(resource_id, holder)

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(manager.list_locks()) == 0
