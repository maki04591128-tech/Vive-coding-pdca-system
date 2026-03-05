"""REST API インターフェース定義。

提案14: PDCAシステムを外部から操作するためのAPIエンドポイント定義、
認証、ルーティング、リクエスト/レスポンスモデルを提供する。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


# ── APIMethod ──


class APIMethod(StrEnum):
    """HTTPメソッド。"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


# ── APIEndpoint ──


@dataclass
class APIEndpoint:
    """APIエンドポイント定義。

    Parameters
    ----------
    path : str
        エンドポイントのURLパス。
    method : APIMethod
        HTTPメソッド。
    description : str
        エンドポイントの説明。
    requires_auth : bool
        認証が必要かどうか。
    """

    path: str
    method: APIMethod
    description: str
    requires_auth: bool = True


# ── APIRequest ──


@dataclass
class APIRequest:
    """APIリクエストモデル。

    Parameters
    ----------
    endpoint : str
        リクエスト先のパス。
    method : APIMethod
        HTTPメソッド。
    params : dict
        クエリパラメータ。
    headers : dict
        HTTPヘッダー。
    body : dict | None
        リクエストボディ。
    """

    endpoint: str
    method: APIMethod
    params: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, object] | None = None


# ── APIResponse ──


@dataclass
class APIResponse:
    """APIレスポンスモデル。

    Parameters
    ----------
    status_code : int
        HTTPステータスコード。
    body : dict
        レスポンスボディ。
    headers : dict
        レスポンスヘッダー。
    """

    status_code: int
    body: dict[str, object] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


# ── APIKeyAuth ──


class APIKeyAuth:
    """APIキー認証マネージャー。

    シンプルなAPIキーベースの認証を提供する。
    各キーにはスコープ（read / write / admin）を割り当てられる。
    """

    def __init__(self) -> None:
        self._keys: dict[str, str] = {}

    def add_key(self, key: str, scope: str = "read") -> None:
        """APIキーを登録する。

        Parameters
        ----------
        key : str
            APIキー文字列。
        scope : str
            キーのスコープ（read / write / admin）。
        """
        self._keys[key] = scope
        logger.info("APIキーを追加しました: scope=%s", scope)

    def validate_key(self, key: str) -> bool:
        """APIキーが有効か検証する。

        Parameters
        ----------
        key : str
            検証するAPIキー。

        Returns
        -------
        bool
            キーが有効なら True。
        """
        return key in self._keys

    def get_scope(self, key: str) -> str | None:
        """APIキーのスコープを取得する。

        Parameters
        ----------
        key : str
            APIキー。

        Returns
        -------
        str | None
            スコープ文字列。キーが存在しない場合は None。
        """
        return self._keys.get(key)

    def revoke_key(self, key: str) -> bool:
        """APIキーを無効化する。

        Parameters
        ----------
        key : str
            無効化するAPIキー。

        Returns
        -------
        bool
            キーが存在して削除できた場合は True。
        """
        if key in self._keys:
            del self._keys[key]
            logger.info("APIキーを無効化しました")
            return True
        return False

    def list_keys(self) -> list[str]:
        """登録済みAPIキーの一覧を返す。

        Returns
        -------
        list[str]
            APIキー文字列のリスト。
        """
        return list(self._keys.keys())


# ── APIRouter ──


class APIRouter:
    """APIリクエストルーター。

    エンドポイントの登録・検索・リクエストディスパッチを行う。
    """

    def __init__(self, auth: APIKeyAuth | None = None) -> None:
        self._endpoints: list[APIEndpoint] = []
        self._handlers: dict[str, object] = {}
        self._auth = auth

    def register_endpoint(self, endpoint: APIEndpoint) -> None:
        """エンドポイントを登録する。

        Parameters
        ----------
        endpoint : APIEndpoint
            登録するエンドポイント定義。
        """
        self._endpoints.append(endpoint)
        route_key = f"{endpoint.method}:{endpoint.path}"
        self._handlers[route_key] = endpoint
        logger.info(
            "エンドポイントを登録: %s %s",
            endpoint.method,
            endpoint.path,
        )

    def get_endpoint(
        self, path: str, method: APIMethod
    ) -> APIEndpoint | None:
        """パスとメソッドからエンドポイントを検索する。

        Parameters
        ----------
        path : str
            URLパス。
        method : APIMethod
            HTTPメソッド。

        Returns
        -------
        APIEndpoint | None
            一致するエンドポイント。見つからない場合は None。
        """
        route_key = f"{method}:{path}"
        result = self._handlers.get(route_key)
        if isinstance(result, APIEndpoint):
            return result
        return None

    def list_endpoints(self) -> list[APIEndpoint]:
        """登録済みエンドポイントの一覧を返す。

        Returns
        -------
        list[APIEndpoint]
            エンドポイントのリスト。
        """
        return list(self._endpoints)

    def handle_request(self, request: APIRequest) -> APIResponse:
        """リクエストを処理してレスポンスを返す。

        エンドポイントの存在確認・認証チェックを行い、
        適切なステータスコードでレスポンスを生成する。

        Parameters
        ----------
        request : APIRequest
            処理するリクエスト。

        Returns
        -------
        APIResponse
            処理結果のレスポンス。
        """
        endpoint = self.get_endpoint(request.endpoint, request.method)

        if endpoint is None:
            logger.warning(
                "エンドポイントが見つかりません: %s %s",
                request.method,
                request.endpoint,
            )
            return APIResponse(
                status_code=404,
                body={"error": "Not Found"},
            )

        if endpoint.requires_auth and self._auth is not None:
            api_key = request.headers.get("Authorization", "")
            if not self._auth.validate_key(api_key):
                logger.warning("認証失敗: %s %s", request.method, request.endpoint)
                return APIResponse(
                    status_code=401,
                    body={"error": "Unauthorized"},
                )

        logger.info(
            "リクエスト処理完了: %s %s",
            request.method,
            request.endpoint,
        )
        return APIResponse(
            status_code=200,
            body={
                "message": "OK",
                "endpoint": endpoint.path,
                "description": endpoint.description,
            },
        )


# ── EndpointRegistry ──


class EndpointRegistry:
    """標準PDCAエンドポイントのレジストリ。

    デフォルトのAPIエンドポイント群を生成する。
    """

    @staticmethod
    def create_default_endpoints() -> list[APIEndpoint]:
        """標準PDCAエンドポイント一覧を生成する。

        Returns
        -------
        list[APIEndpoint]
            デフォルトのエンドポイントリスト。
        """
        return [
            APIEndpoint(
                path="/api/v1/goals",
                method=APIMethod.POST,
                description="新しいゴールを作成する",
            ),
            APIEndpoint(
                path="/api/v1/cycles",
                method=APIMethod.POST,
                description="PDCAサイクルを開始する",
            ),
            APIEndpoint(
                path="/api/v1/cycles/stop",
                method=APIMethod.POST,
                description="実行中のPDCAサイクルを停止する",
            ),
            APIEndpoint(
                path="/api/v1/status",
                method=APIMethod.GET,
                description="システムステータスを取得する",
            ),
            APIEndpoint(
                path="/api/v1/metrics",
                method=APIMethod.GET,
                description="メトリクスを取得する",
            ),
            APIEndpoint(
                path="/api/v1/approve",
                method=APIMethod.POST,
                description="レビュー結果を承認する",
            ),
            APIEndpoint(
                path="/api/v1/reject",
                method=APIMethod.POST,
                description="レビュー結果を却下する",
            ),
            APIEndpoint(
                path="/api/v1/export",
                method=APIMethod.GET,
                description="データをエクスポートする",
            ),
        ]
