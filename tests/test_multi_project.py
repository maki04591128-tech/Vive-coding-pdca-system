"""マルチプロジェクト管理のテスト。"""

import pytest

from vibe_pdca.engine.multi_project import (
    MultiProjectManager,
    ProjectConfig,
    ProjectIsolationError,
)

# ============================================================
# Fixtures
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
        mgr.verify_isolation("proj-a", "proj-a")  # Should not raise

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
