"""REST API インターフェースのテスト。"""

from __future__ import annotations

import pytest

from vibe_pdca.engine.api_server import (
    APIEndpoint,
    APIKeyAuth,
    APIMethod,
    APIRequest,
    APIResponse,
    APIRouter,
    EndpointRegistry,
)

# ============================================================
# テスト: APIMethod
# ============================================================


class TestAPIMethod:
    """APIMethod列挙型のテスト。"""

    def test_enum_values(self) -> None:
        assert APIMethod.GET == "GET"
        assert APIMethod.POST == "POST"
        assert APIMethod.PUT == "PUT"
        assert APIMethod.DELETE == "DELETE"


# ============================================================
# テスト: APIEndpoint
# ============================================================


class TestAPIEndpoint:
    """APIEndpointデータクラスのテスト。"""

    def test_creation(self) -> None:
        ep = APIEndpoint(
            path="/api/v1/status",
            method=APIMethod.GET,
            description="ステータス取得",
        )
        assert ep.path == "/api/v1/status"
        assert ep.method == APIMethod.GET
        assert ep.description == "ステータス取得"
        assert ep.requires_auth is True

    def test_defaults(self) -> None:
        ep = APIEndpoint(
            path="/health",
            method=APIMethod.GET,
            description="ヘルスチェック",
            requires_auth=False,
        )
        assert ep.requires_auth is False


# ============================================================
# テスト: APIRequest
# ============================================================


class TestAPIRequest:
    """APIRequestデータクラスのテスト。"""

    def test_creation(self) -> None:
        req = APIRequest(
            endpoint="/api/v1/goals",
            method=APIMethod.POST,
        )
        assert req.endpoint == "/api/v1/goals"
        assert req.method == APIMethod.POST
        assert req.params == {}
        assert req.headers == {}
        assert req.body is None


# ============================================================
# テスト: APIResponse
# ============================================================


class TestAPIResponse:
    """APIResponseデータクラスのテスト。"""

    def test_creation(self) -> None:
        resp = APIResponse(status_code=200)
        assert resp.status_code == 200
        assert resp.body == {}
        assert resp.headers == {}


# ============================================================
# テスト: APIKeyAuth
# ============================================================


class TestAPIKeyAuth:
    """APIKeyAuth認証マネージャーのテスト。"""

    def test_add_and_validate(self) -> None:
        auth = APIKeyAuth()
        auth.add_key("secret-key-1")
        assert auth.validate_key("secret-key-1") is True

    def test_invalid_key(self) -> None:
        auth = APIKeyAuth()
        assert auth.validate_key("nonexistent") is False

    def test_get_scope(self) -> None:
        auth = APIKeyAuth()
        auth.add_key("key-admin", scope="admin")
        assert auth.get_scope("key-admin") == "admin"
        assert auth.get_scope("missing") is None

    def test_revoke(self) -> None:
        auth = APIKeyAuth()
        auth.add_key("key-to-revoke")
        assert auth.revoke_key("key-to-revoke") is True
        assert auth.validate_key("key-to-revoke") is False
        assert auth.revoke_key("key-to-revoke") is False

    def test_list_keys(self) -> None:
        auth = APIKeyAuth()
        auth.add_key("k1", scope="read")
        auth.add_key("k2", scope="write")
        keys = auth.list_keys()
        assert set(keys) == {"k1", "k2"}

    def test_add_key_invalid_scope_raises(self) -> None:
        """無効なスコープを指定するとValueErrorが発生すること。"""
        auth = APIKeyAuth()
        with pytest.raises(ValueError, match="無効なスコープ"):
            auth.add_key("key-bad", scope="superadmin")

    def test_add_key_all_valid_scopes(self) -> None:
        """read / write / admin の3種類すべてが登録できること。"""
        auth = APIKeyAuth()
        for scope in ("read", "write", "admin"):
            auth.add_key(f"key-{scope}", scope=scope)
            assert auth.get_scope(f"key-{scope}") == scope


# ============================================================
# テスト: APIRouter
# ============================================================


class TestAPIRouter:
    """APIRouterルーターのテスト。"""

    def _make_endpoint(
        self,
        path: str = "/api/v1/status",
        method: APIMethod = APIMethod.GET,
        requires_auth: bool = True,
    ) -> APIEndpoint:
        return APIEndpoint(
            path=path,
            method=method,
            description="テスト用",
            requires_auth=requires_auth,
        )

    def test_register_and_get(self) -> None:
        router = APIRouter()
        ep = self._make_endpoint()
        router.register_endpoint(ep)
        found = router.get_endpoint("/api/v1/status", APIMethod.GET)
        assert found is ep

    def test_get_missing(self) -> None:
        router = APIRouter()
        assert router.get_endpoint("/missing", APIMethod.GET) is None

    def test_list_endpoints(self) -> None:
        router = APIRouter()
        ep1 = self._make_endpoint("/a", APIMethod.GET)
        ep2 = self._make_endpoint("/b", APIMethod.POST)
        router.register_endpoint(ep1)
        router.register_endpoint(ep2)
        endpoints = router.list_endpoints()
        assert len(endpoints) == 2
        assert ep1 in endpoints
        assert ep2 in endpoints

    def test_handle_request_success(self) -> None:
        router = APIRouter()
        ep = self._make_endpoint(requires_auth=False)
        router.register_endpoint(ep)
        req = APIRequest(
            endpoint="/api/v1/status",
            method=APIMethod.GET,
        )
        resp = router.handle_request(req)
        assert resp.status_code == 200
        assert resp.body["message"] == "OK"

    def test_handle_request_not_found(self) -> None:
        router = APIRouter()
        req = APIRequest(
            endpoint="/nonexistent",
            method=APIMethod.GET,
        )
        resp = router.handle_request(req)
        assert resp.status_code == 404
        assert resp.body["error"] == "Not Found"

    def test_handle_request_unauthorized(self) -> None:
        auth = APIKeyAuth()
        auth.add_key("valid-key")
        router = APIRouter(auth=auth)
        ep = self._make_endpoint(requires_auth=True)
        router.register_endpoint(ep)
        req = APIRequest(
            endpoint="/api/v1/status",
            method=APIMethod.GET,
            headers={"Authorization": "wrong-key"},
        )
        resp = router.handle_request(req)
        assert resp.status_code == 401
        assert resp.body["error"] == "Unauthorized"

    def test_handle_request_forbidden_when_auth_not_configured(self) -> None:
        """認証マネージャー未設定で認証必須エンドポイントへアクセスすると403。"""
        router = APIRouter(auth=None)
        ep = self._make_endpoint(requires_auth=True)
        router.register_endpoint(ep)
        req = APIRequest(
            endpoint="/api/v1/status",
            method=APIMethod.GET,
        )
        resp = router.handle_request(req)
        assert resp.status_code == 403
        assert resp.body["error"] == "Forbidden"


# ============================================================
# テスト: EndpointRegistry
# ============================================================


class TestEndpointRegistry:
    """EndpointRegistryのテスト。"""

    def test_create_default_endpoints(self) -> None:
        endpoints = EndpointRegistry.create_default_endpoints()
        assert len(endpoints) == 8
        paths = [ep.path for ep in endpoints]
        assert "/api/v1/goals" in paths
        assert "/api/v1/status" in paths
        assert "/api/v1/export" in paths


# ── スレッドセーフティ ──


class TestAPIKeyAuthThreadSafety:
    """APIKeyAuth の並行アクセスでデータが壊れない。"""

    def test_concurrent_add_and_validate(self):
        import threading
        auth = APIKeyAuth()
        errors: list[str] = []

        def add_keys(tid: int):
            try:
                for i in range(50):
                    auth.add_key(f"key-{tid}-{i}", "read")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=add_keys, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(auth.list_keys()) == 200


class TestAPIKeyAuthBarrierThreadSafety:
    """APIKeyAuth のBarrier同期スレッドセーフティテスト。"""

    def test_concurrent_add_key_with_barrier(self) -> None:
        import threading

        auth = APIKeyAuth()
        n_threads = 10
        ops_per_thread = 50
        barrier = threading.Barrier(n_threads)

        def worker(tid: int) -> None:
            barrier.wait()
            for i in range(ops_per_thread):
                auth.add_key(f"key-{tid}-{i}", "read")

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(auth.list_keys()) == n_threads * ops_per_thread
