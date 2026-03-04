"""REST API インターフェースのテスト。"""

from __future__ import annotations

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
