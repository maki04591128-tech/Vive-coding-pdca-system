"""マルチプロジェクト管理のテスト。"""

import pytest

from vibe_pdca.engine.multi_project import (
    MultiProjectManager,
    ProjectConfig,
    ProjectIsolationError,
)

# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def mgr():
    return MultiProjectManager()


@pytest.fixture
def project_a():
    return ProjectConfig(
        project_id="proj-a",
        name="Project A",
        repository="org/repo-a",
        cost_limit_usd=50.0,
    )


@pytest.fixture
def project_b():
    return ProjectConfig(
        project_id="proj-b",
        name="Project B",
        repository="org/repo-b",
        cost_limit_usd=100.0,
    )


# ============================================================
# テスト: プロジェクト登録
# ============================================================


class TestRegistration:
    def test_register(self, mgr, project_a):
        pid = mgr.register_project(project_a)
        assert pid == "proj-a"
        assert mgr.project_count == 1

    def test_register_multiple(self, mgr, project_a, project_b):
        mgr.register_project(project_a)
        mgr.register_project(project_b)
        assert mgr.project_count == 2

    def test_get_project(self, mgr, project_a):
        mgr.register_project(project_a)
        config = mgr.get_project("proj-a")
        assert config.name == "Project A"

    def test_get_unknown_project(self, mgr):
        with pytest.raises(KeyError):
            mgr.get_project("unknown")

    def test_list_projects(self, mgr, project_a, project_b):
        mgr.register_project(project_a)
        mgr.register_project(project_b)
        projects = mgr.list_projects()
        assert len(projects) == 2

    def test_deactivate(self, mgr, project_a):
        mgr.register_project(project_a)
        mgr.deactivate_project("proj-a")
        assert not mgr.get_project("proj-a").is_active


# ============================================================
# テスト: 隔離保証
# ============================================================


class TestIsolation:
    def test_duplicate_repo_rejected(self, mgr, project_a):
        mgr.register_project(project_a)
        duplicate = ProjectConfig(
            project_id="proj-dup",
            name="Duplicate",
            repository="org/repo-a",
        )
        with pytest.raises(ProjectIsolationError):
            mgr.register_project(duplicate)

    def test_verify_isolation_same_project(self, mgr, project_a):
        mgr.register_project(project_a)
        mgr.verify_isolation("proj-a", "proj-a")  # 例外が発生しないこと

    def test_verify_isolation_cross_project(self, mgr, project_a, project_b):
        mgr.register_project(project_a)
        mgr.register_project(project_b)
        with pytest.raises(ProjectIsolationError):
            mgr.verify_isolation("proj-a", "proj-b")


# ============================================================
# テスト: リソース使用量
# ============================================================


class TestResourceUsage:
    def test_record_usage(self, mgr, project_a):
        mgr.register_project(project_a)
        mgr.record_usage("proj-a", llm_calls=10, cost_usd=5.0)
        usage = mgr.get_usage("proj-a")
        assert usage.llm_calls == 10
        assert usage.cost_usd == 5.0

    def test_cost_limit_not_exceeded(self, mgr, project_a):
        mgr.register_project(project_a)
        mgr.record_usage("proj-a", cost_usd=10.0)
        assert not mgr.check_cost_limit("proj-a")

    def test_cost_limit_exceeded(self, mgr, project_a):
        mgr.register_project(project_a)
        mgr.record_usage("proj-a", cost_usd=50.0)
        assert mgr.check_cost_limit("proj-a")

    def test_get_status(self, mgr, project_a):
        mgr.register_project(project_a)
        status = mgr.get_status()
        assert status["project_count"] == 1
        assert "proj-a" in status["projects"]


# ============================================================
# テスト: スレッドセーフティ
# ============================================================


class TestMultiProjectManagerThreadSafety:
    """MultiProjectManager のスレッドセーフティ検証。"""

    def test_concurrent_record_usage(self):
        """複数スレッドから同時にリソース使用量を記録しても整合性が保たれる。"""
        import threading
        mgr = MultiProjectManager()
        config = ProjectConfig(
            project_id="proj-ts",
            name="Thread-Safe",
            repository="repo-ts",
        )
        mgr.register_project(config)
        errors: list[str] = []

        def record(tid: int) -> None:
            try:
                for _ in range(100):
                    mgr.record_usage("proj-ts", llm_calls=1, cost_usd=0.01)
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=record, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        usage = mgr.get_usage("proj-ts")
        assert usage.llm_calls == 400


class TestMultiProjectManagerBarrierThreadSafety:
    """MultiProjectManager のBarrier同期スレッドセーフティテスト。"""

    def test_concurrent_record_usage_with_barrier(self) -> None:
        import threading

        mgr = MultiProjectManager()
        config = ProjectConfig(
            project_id="proj-barrier",
            name="Barrier-Test",
            repository="repo-barrier",
        )
        mgr.register_project(config)
        n_threads = 10
        ops_per_thread = 50
        barrier = threading.Barrier(n_threads)

        def worker(tid: int) -> None:
            barrier.wait()
            for _ in range(ops_per_thread):
                mgr.record_usage("proj-barrier", llm_calls=1, cost_usd=0.01)

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        usage = mgr.get_usage("proj-barrier")
        assert usage.llm_calls == n_threads * ops_per_thread
