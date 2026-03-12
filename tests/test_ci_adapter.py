"""外部CI/CDサービス統合アダプターのテスト。"""

from unittest.mock import patch

import httpx
import pytest

from vibe_pdca.engine.ci_adapter import (
    CIAdapterBase,
    CIAdapterError,
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

    def test_get_status_no_token_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            adapter = GitHubActionsAdapter(
                token="", owner="test-owner", repo="test-repo",
            )
        with pytest.raises(CIAdapterError, match="トークンが未設定"):
            adapter.get_status("123")

    def test_get_status_no_owner_raises(self):
        adapter = GitHubActionsAdapter(
            token="fake-token", owner="", repo="test-repo",
        )
        with pytest.raises(CIAdapterError, match="owner と repo が必要"):
            adapter.get_status("123")

    def test_get_status_success(self):
        adapter = GitHubActionsAdapter(
            token="fake-token", owner="test-owner", repo="test-repo",
        )
        mock_response = httpx.Response(
            200,
            json={
                "conclusion": "success",
                "run_id": 12345,
                "html_url": "https://github.com/runs/12345",
                "duration_seconds": 42.0,
            },
            request=httpx.Request("GET", "https://api.github.com"),
        )
        with patch.object(httpx, "get", return_value=mock_response):
            result = adapter.get_status("12345")
        assert result.status == CIBuildStatus.SUCCESS
        assert result.build_id == "12345"
        assert result.provider == CIProvider.GITHUB_ACTIONS

    def test_get_status_api_error(self):
        adapter = GitHubActionsAdapter(
            token="fake-token", owner="test-owner", repo="test-repo",
        )
        mock_response = httpx.Response(
            404,
            json={"message": "Not Found"},
            request=httpx.Request("GET", "https://api.github.com"),
        )
        with (
            patch.object(httpx, "get", return_value=mock_response),
            pytest.raises(CIAdapterError, match="API エラー"),
        ):
            adapter.get_status("99999")

    def test_get_status_connection_error(self):
        adapter = GitHubActionsAdapter(
            token="fake-token", owner="test-owner", repo="test-repo",
        )
        with patch.object(
            httpx, "get",
            side_effect=httpx.ConnectError("接続失敗"),
        ), pytest.raises(CIAdapterError, match="接続エラー"):
            adapter.get_status("123")

    def test_get_status_uses_env_token(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env-token"}):
            adapter = GitHubActionsAdapter(
                owner="test-owner", repo="test-repo",
            )
        assert adapter._token == "env-token"


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

    def test_get_status_no_token_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            adapter = GitLabCIAdapter(
                token="", project_id="123",
            )
        with pytest.raises(CIAdapterError, match="トークンが未設定"):
            adapter.get_status("10")

    def test_get_status_no_project_id_raises(self):
        adapter = GitLabCIAdapter(
            token="fake-token", project_id="",
        )
        with pytest.raises(CIAdapterError, match="project_id が必要"):
            adapter.get_status("10")

    def test_get_status_success(self):
        adapter = GitLabCIAdapter(
            token="fake-token", project_id="42",
        )
        mock_response = httpx.Response(
            200,
            json={
                "status": "success",
                "id": 10,
                "web_url": "https://gitlab.com/pipelines/10",
                "duration": 55.0,
            },
            request=httpx.Request("GET", "https://gitlab.com/api/v4"),
        )
        with patch.object(httpx, "get", return_value=mock_response):
            result = adapter.get_status("10")
        assert result.status == CIBuildStatus.SUCCESS
        assert result.build_id == "10"
        assert result.provider == CIProvider.GITLAB_CI

    def test_get_status_api_error(self):
        adapter = GitLabCIAdapter(
            token="fake-token", project_id="42",
        )
        mock_response = httpx.Response(
            403,
            json={"message": "Forbidden"},
            request=httpx.Request("GET", "https://gitlab.com/api/v4"),
        )
        with (
            patch.object(httpx, "get", return_value=mock_response),
            pytest.raises(CIAdapterError, match="API エラー"),
        ):
            adapter.get_status("10")

    def test_get_status_uses_env_token(self):
        with patch.dict("os.environ", {"GITLAB_TOKEN": "gl-env-token"}):
            adapter = GitLabCIAdapter(project_id="42")
        assert adapter._token == "gl-env-token"


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


# ── スレッドセーフティ ──


class TestCIAdapterRegistryThreadSafety:
    """CIAdapterRegistry の並行アクセスでデータが壊れない。"""

    def test_concurrent_register(self):
        import threading
        registry = CIAdapterRegistry()
        errors: list[str] = []

        def register_adapter(tid: int):
            try:
                adapter = GitHubActionsAdapter()
                # 同じプロバイダに複数スレッドが同時に登録
                registry.register(CIProvider.GITHUB_ACTIONS, adapter)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=register_adapter, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert CIProvider.GITHUB_ACTIONS in registry.list_providers()


class TestCIAdapterRegistryBarrierThreadSafety:
    """CIAdapterRegistry のBarrier同期スレッドセーフティテスト。"""

    def test_concurrent_register_with_barrier(self) -> None:
        import threading

        registry = CIAdapterRegistry()
        n_threads = 10
        barrier = threading.Barrier(n_threads)

        def worker(tid: int) -> None:
            barrier.wait()
            adapter = GitHubActionsAdapter()
            registry.register(CIProvider.GITHUB_ACTIONS, adapter)

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert CIProvider.GITHUB_ACTIONS in registry.list_providers()
