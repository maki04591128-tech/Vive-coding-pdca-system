"""外部CI/CDサービス統合アダプターのテスト。"""

import pytest

from vibe_pdca.engine.ci_adapter import (
    CIAdapterBase,
    CIAdapterRegistry,
    CIBuildResult,
    CIBuildStatus,
    CIProvider,
    GitHubActionsAdapter,
    GitLabCIAdapter,
)

# ============================================================
# テスト: CIProvider
# ============================================================


class TestCIProvider:
    def test_enum_values(self):
        assert CIProvider.GITHUB_ACTIONS == "github_actions"
        assert CIProvider.GITLAB_CI == "gitlab_ci"
        assert CIProvider.CIRCLECI == "circleci"
        assert CIProvider.JENKINS == "jenkins"


# ============================================================
# テスト: CIBuildStatus
# ============================================================


class TestCIBuildStatus:
    def test_enum_values(self):
        assert CIBuildStatus.SUCCESS == "success"
        assert CIBuildStatus.FAILURE == "failure"
        assert CIBuildStatus.RUNNING == "running"
        assert CIBuildStatus.CANCELLED == "cancelled"
        assert CIBuildStatus.SKIPPED == "skipped"


# ============================================================
# テスト: CIBuildResult
# ============================================================


class TestCIBuildResult:
    def test_default_values(self):
        result = CIBuildResult(
            provider=CIProvider.GITHUB_ACTIONS,
            build_id="123",
            status=CIBuildStatus.SUCCESS,
            duration_seconds=45.0,
        )
        assert result.provider == CIProvider.GITHUB_ACTIONS
        assert result.build_id == "123"
        assert result.status == CIBuildStatus.SUCCESS
        assert result.duration_seconds == 45.0
        assert result.log_url == ""
        assert result.categories == []

    def test_custom_values(self):
        result = CIBuildResult(
            provider=CIProvider.GITLAB_CI,
            build_id="456",
            status=CIBuildStatus.FAILURE,
            duration_seconds=120.5,
            log_url="https://example.com/build/456",
            categories=["lint", "test"],
        )
        assert result.provider == CIProvider.GITLAB_CI
        assert result.build_id == "456"
        assert result.status == CIBuildStatus.FAILURE
        assert result.duration_seconds == 120.5
        assert result.log_url == "https://example.com/build/456"
        assert result.categories == ["lint", "test"]


# ============================================================
# テスト: CIAdapterBase
# ============================================================


class TestCIAdapterBase:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            CIAdapterBase()  # type: ignore[abstract]


# ============================================================
# テスト: GitHubActionsAdapter
# ============================================================


class TestGitHubActionsAdapter:
    def test_normalize_success(self):
        adapter = GitHubActionsAdapter()
        result = adapter.normalize_result({
            "conclusion": "success",
            "run_id": 100,
            "html_url": "https://github.com/runs/100",
            "duration_seconds": 30.0,
        })
        assert result.status == CIBuildStatus.SUCCESS
        assert result.build_id == "100"
        assert result.provider == CIProvider.GITHUB_ACTIONS
        assert result.log_url == "https://github.com/runs/100"
        assert result.duration_seconds == 30.0

    def test_normalize_failure(self):
        adapter = GitHubActionsAdapter()
        result = adapter.normalize_result({
            "conclusion": "failure",
            "run_id": 200,
        })
        assert result.status == CIBuildStatus.FAILURE
        assert result.build_id == "200"

    def test_normalize_cancelled(self):
        adapter = GitHubActionsAdapter()
        result = adapter.normalize_result({
            "conclusion": "cancelled",
            "run_id": 300,
        })
        assert result.status == CIBuildStatus.CANCELLED

    def test_normalize_running(self):
        adapter = GitHubActionsAdapter()
        result = adapter.normalize_result({
            "conclusion": "",
            "run_id": 400,
        })
        assert result.status == CIBuildStatus.RUNNING

    def test_normalize_uses_id_fallback(self):
        adapter = GitHubActionsAdapter()
        result = adapter.normalize_result({
            "conclusion": "success",
            "id": 999,
        })
        assert result.build_id == "999"

    def test_get_status_not_implemented(self):
        adapter = GitHubActionsAdapter()
        with pytest.raises(NotImplementedError):
            adapter.get_status("123")


# ============================================================
# テスト: GitLabCIAdapter
# ============================================================


class TestGitLabCIAdapter:
    def test_normalize_success(self):
        adapter = GitLabCIAdapter()
        result = adapter.normalize_result({
            "status": "success",
            "id": 10,
            "web_url": "https://gitlab.com/pipelines/10",
            "duration": 60.0,
        })
        assert result.status == CIBuildStatus.SUCCESS
        assert result.build_id == "10"
        assert result.provider == CIProvider.GITLAB_CI
        assert result.log_url == "https://gitlab.com/pipelines/10"
        assert result.duration_seconds == 60.0

    def test_normalize_failed(self):
        adapter = GitLabCIAdapter()
        result = adapter.normalize_result({
            "status": "failed",
            "id": 20,
        })
        assert result.status == CIBuildStatus.FAILURE

    def test_normalize_canceled(self):
        adapter = GitLabCIAdapter()
        result = adapter.normalize_result({
            "status": "canceled",
            "id": 30,
        })
        assert result.status == CIBuildStatus.CANCELLED

    def test_normalize_unknown_status_defaults_to_running(self):
        adapter = GitLabCIAdapter()
        result = adapter.normalize_result({
            "status": "pending",
            "id": 40,
        })
        assert result.status == CIBuildStatus.RUNNING

    def test_get_status_not_implemented(self):
        adapter = GitLabCIAdapter()
        with pytest.raises(NotImplementedError):
            adapter.get_status("10")


# ============================================================
# テスト: CIAdapterRegistry
# ============================================================


class TestCIAdapterRegistry:
    def test_register_and_get(self):
        registry = CIAdapterRegistry()
        adapter = GitHubActionsAdapter()
        registry.register(CIProvider.GITHUB_ACTIONS, adapter)
        assert registry.get(CIProvider.GITHUB_ACTIONS) is adapter

    def test_get_unknown_returns_none(self):
        registry = CIAdapterRegistry()
        assert registry.get(CIProvider.JENKINS) is None

    def test_list_providers(self):
        registry = CIAdapterRegistry()
        registry.register(
            CIProvider.GITHUB_ACTIONS, GitHubActionsAdapter(),
        )
        registry.register(
            CIProvider.GITLAB_CI, GitLabCIAdapter(),
        )
        providers = registry.list_providers()
        assert CIProvider.GITHUB_ACTIONS in providers
        assert CIProvider.GITLAB_CI in providers
        assert len(providers) == 2

    def test_normalize(self):
        registry = CIAdapterRegistry()
        registry.register(
            CIProvider.GITHUB_ACTIONS, GitHubActionsAdapter(),
        )
        result = registry.normalize(
            CIProvider.GITHUB_ACTIONS,
            {"conclusion": "success", "run_id": 1},
        )
        assert result.status == CIBuildStatus.SUCCESS
        assert result.provider == CIProvider.GITHUB_ACTIONS

    def test_normalize_raises_for_unregistered_provider(self):
        registry = CIAdapterRegistry()
        with pytest.raises(KeyError, match=r"未登録のCIプロバイダー"):
            registry.normalize(CIProvider.CIRCLECI, {})
