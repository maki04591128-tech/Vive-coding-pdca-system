"""Proposal 26: Multi-Repository / Monorepo Support のテスト。"""

from __future__ import annotations

from vibe_pdca.engine.multi_repo import (
    CoordinatedCycleConfig,
    CrossRepoDependency,
    CrossRepoCoordinator,
    MonorepoScopeResolver,
    ReleaseCoordinator,
    RepoScope,
)


# ============================================================
# RepoScope dataclass
# ============================================================


class TestRepoScope:
    """RepoScope データクラスのテスト。"""

    def test_defaults(self) -> None:
        rs = RepoScope(repo_url="https://example.com/repo", name="repo")
        assert rs.repo_url == "https://example.com/repo"
        assert rs.name == "repo"
        assert rs.scope_path == ""
        assert rs.branch == "main"

    def test_with_scope(self) -> None:
        rs = RepoScope(
            repo_url="https://example.com/mono",
            name="mono",
            scope_path="packages/core",
            branch="develop",
        )
        assert rs.scope_path == "packages/core"
        assert rs.branch == "develop"


# ============================================================
# CrossRepoDependency dataclass
# ============================================================


class TestCrossRepoDependency:
    """CrossRepoDependency データクラスのテスト。"""

    def test_creation(self) -> None:
        dep = CrossRepoDependency(
            source_repo="frontend",
            target_repo="backend",
            dependency_type="api",
            description="REST API 依存",
        )
        assert dep.source_repo == "frontend"
        assert dep.target_repo == "backend"
        assert dep.dependency_type == "api"

    def test_default_description(self) -> None:
        dep = CrossRepoDependency(
            source_repo="a", target_repo="b", dependency_type="library"
        )
        assert dep.description == ""


# ============================================================
# MonorepoScopeResolver
# ============================================================


class TestMonorepoScopeResolver:
    """MonorepoScopeResolver のテスト。"""

    def setup_method(self) -> None:
        self.resolver = MonorepoScopeResolver()

    def test_resolve_scope_empty(self) -> None:
        result = self.resolver.resolve_scope("/repo", "")
        assert result == ["/repo"]

    def test_resolve_scope_with_path(self) -> None:
        result = self.resolver.resolve_scope("/repo", "packages/core")
        assert result == ["/repo/packages/core"]

    def test_resolve_scope_trailing_slash(self) -> None:
        result = self.resolver.resolve_scope("/repo/", "packages/core/")
        assert result == ["/repo/packages/core"]

    def test_detect_affected_packages_single(self) -> None:
        changed = ["packages/core/src/main.py"]
        packages = ["packages/core", "packages/utils"]
        affected = self.resolver.detect_affected_packages(changed, packages)
        assert affected == ["packages/core"]

    def test_detect_affected_packages_multiple(self) -> None:
        changed = [
            "packages/core/src/main.py",
            "packages/utils/helper.py",
        ]
        packages = ["packages/core", "packages/utils", "packages/web"]
        affected = self.resolver.detect_affected_packages(changed, packages)
        assert "packages/core" in affected
        assert "packages/utils" in affected
        assert "packages/web" not in affected

    def test_detect_affected_packages_none(self) -> None:
        changed = ["docs/README.md"]
        packages = ["packages/core"]
        affected = self.resolver.detect_affected_packages(changed, packages)
        assert affected == []


# ============================================================
# CrossRepoCoordinator
# ============================================================


class TestCrossRepoCoordinator:
    """CrossRepoCoordinator のテスト。"""

    def setup_method(self) -> None:
        self.coordinator = CrossRepoCoordinator()

    def test_register_repos(self) -> None:
        repos = [
            RepoScope(repo_url="url1", name="repo-a"),
            RepoScope(repo_url="url2", name="repo-b"),
        ]
        self.coordinator.register_repos(repos)
        assert len(self.coordinator._repos) == 2

    def test_add_dependency(self) -> None:
        dep = CrossRepoDependency(
            source_repo="a", target_repo="b", dependency_type="api"
        )
        self.coordinator.add_dependency(dep)
        assert len(self.coordinator._dependencies) == 1

    def test_execution_plan_sequential(self) -> None:
        repos = [
            RepoScope(repo_url="u1", name="a"),
            RepoScope(repo_url="u2", name="b"),
        ]
        config = CoordinatedCycleConfig(
            goal_id="g1", repos=repos, sync_mode="sequential"
        )
        plan = self.coordinator.get_execution_plan(config)
        assert plan == [["a"], ["b"]]

    def test_execution_plan_parallel_no_deps(self) -> None:
        repos = [
            RepoScope(repo_url="u1", name="a"),
            RepoScope(repo_url="u2", name="b"),
        ]
        config = CoordinatedCycleConfig(
            goal_id="g1", repos=repos, sync_mode="parallel"
        )
        plan = self.coordinator.get_execution_plan(config)
        assert len(plan) == 1
        assert sorted(plan[0]) == ["a", "b"]

    def test_execution_plan_with_deps(self) -> None:
        repos = [
            RepoScope(repo_url="u1", name="lib"),
            RepoScope(repo_url="u2", name="app"),
        ]
        deps = [
            CrossRepoDependency(
                source_repo="app",
                target_repo="lib",
                dependency_type="library",
            ),
        ]
        config = CoordinatedCycleConfig(
            goal_id="g1", repos=repos, dependencies=deps, sync_mode="parallel"
        )
        plan = self.coordinator.get_execution_plan(config)
        assert len(plan) == 2
        assert plan[0] == ["lib"]
        assert plan[1] == ["app"]

    def test_validate_dependencies_valid(self) -> None:
        repos = [
            RepoScope(repo_url="u1", name="a"),
            RepoScope(repo_url="u2", name="b"),
        ]
        self.coordinator.register_repos(repos)
        dep = CrossRepoDependency(
            source_repo="a", target_repo="b", dependency_type="api"
        )
        self.coordinator.add_dependency(dep)
        errors = self.coordinator.validate_dependencies()
        assert errors == []

    def test_validate_dependencies_unknown_repo(self) -> None:
        repos = [RepoScope(repo_url="u1", name="a")]
        self.coordinator.register_repos(repos)
        dep = CrossRepoDependency(
            source_repo="a", target_repo="unknown", dependency_type="api"
        )
        self.coordinator.add_dependency(dep)
        errors = self.coordinator.validate_dependencies()
        assert any("unknown" in e for e in errors)

    def test_validate_dependencies_invalid_type(self) -> None:
        repos = [
            RepoScope(repo_url="u1", name="a"),
            RepoScope(repo_url="u2", name="b"),
        ]
        self.coordinator.register_repos(repos)
        dep = CrossRepoDependency(
            source_repo="a", target_repo="b", dependency_type="invalid"
        )
        self.coordinator.add_dependency(dep)
        errors = self.coordinator.validate_dependencies()
        assert any("不正な依存タイプ" in e for e in errors)

    def test_validate_dependencies_self_dep(self) -> None:
        repos = [RepoScope(repo_url="u1", name="a")]
        self.coordinator.register_repos(repos)
        dep = CrossRepoDependency(
            source_repo="a", target_repo="a", dependency_type="api"
        )
        self.coordinator.add_dependency(dep)
        errors = self.coordinator.validate_dependencies()
        assert any("自己依存" in e for e in errors)


# ============================================================
# ReleaseCoordinator
# ============================================================


class TestReleaseCoordinator:
    """ReleaseCoordinator のテスト。"""

    def setup_method(self) -> None:
        self.coordinator = ReleaseCoordinator()

    def test_should_release_together_api(self) -> None:
        deps = [
            CrossRepoDependency(
                source_repo="a", target_repo="b", dependency_type="api"
            ),
        ]
        assert self.coordinator.should_release_together(["a", "b"], deps)

    def test_should_not_release_together_config(self) -> None:
        deps = [
            CrossRepoDependency(
                source_repo="a", target_repo="b", dependency_type="config"
            ),
        ]
        assert not self.coordinator.should_release_together(["a", "b"], deps)

    def test_should_not_release_together_no_deps(self) -> None:
        assert not self.coordinator.should_release_together(["a", "b"], [])

    def test_get_release_order_simple(self) -> None:
        deps = [
            CrossRepoDependency(
                source_repo="app", target_repo="lib", dependency_type="library"
            ),
        ]
        order = self.coordinator.get_release_order(["app", "lib"], deps)
        assert order.index("lib") < order.index("app")

    def test_get_release_order_no_deps(self) -> None:
        order = self.coordinator.get_release_order(["b", "a"], [])
        assert sorted(order) == ["a", "b"]
