"""外部CI/CDサービス統合アダプター。

提案12: GitHub Actions・GitLab CI等の外部CIサービスからビルド結果を
取得・正規化し、PDCAサイクルへ統合する。
"""

from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# デフォルトのAPIタイムアウト（秒）
_DEFAULT_TIMEOUT = 30.0


# ── CIAdapterError ──


class CIAdapterError(Exception):
    """CIアダプターのエラー。

    API呼び出し失敗、認証エラー等で送出される。
    """


# ── CIProvider ──


class CIProvider(StrEnum):
    """対応CIプロバイダー。"""

    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"
    CIRCLECI = "circleci"
    JENKINS = "jenkins"


# ── CIBuildStatus ──


class CIBuildStatus(StrEnum):
    """CIビルドのステータス。"""

    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


# ── CIBuildResult ──


@dataclass
class CIBuildResult:
    """CIビルド結果の正規化データ。

    Parameters
    ----------
    provider : CIProvider
        CIプロバイダー種別。
    build_id : str
        ビルド識別子。
    status : CIBuildStatus
        ビルドステータス。
    duration_seconds : float
        ビルド所要時間（秒）。
    log_url : str
        ログURL。
    categories : list[str]
        ビルドカテゴリーのリスト。
    """

    provider: CIProvider
    build_id: str
    status: CIBuildStatus
    duration_seconds: float
    log_url: str = ""
    categories: list[str] = field(default_factory=list)


# ── CIAdapterBase ──


class CIAdapterBase(ABC):
    """CIアダプターの抽象基底クラス。

    各CIプロバイダーの具象アダプターはこのクラスを継承し、
    get_status / normalize_result を実装する。
    """

    @abstractmethod
    def get_status(self, build_id: str) -> CIBuildResult:
        """ビルドIDからビルド結果を取得する。

        Parameters
        ----------
        build_id : str
            ビルド識別子。

        Returns
        -------
        CIBuildResult
            正規化されたビルド結果。
        """
        ...

    @abstractmethod
    def normalize_result(self, raw: dict[str, Any]) -> CIBuildResult:
        """プロバイダー固有の生データを正規化する。

        Parameters
        ----------
        raw : dict[str, Any]
            CIサービスから返された生のレスポンス辞書。

        Returns
        -------
        CIBuildResult
            正規化されたビルド結果。
        """
        ...


# ── GitHubActionsAdapter ──


class GitHubActionsAdapter(CIAdapterBase):
    """GitHub Actions 用アダプター。

    Parameters
    ----------
    token : str | None
        GitHub APIトークン。未指定時は環境変数 ``GITHUB_TOKEN`` を使用する。
    owner : str
        リポジトリオーナー。
    repo : str
        リポジトリ名。
    api_base : str
        GitHub API のベースURL。
    timeout : float
        HTTPリクエストのタイムアウト秒。
    """

    _STATUS_MAP: dict[str, CIBuildStatus] = {
        "success": CIBuildStatus.SUCCESS,
        "failure": CIBuildStatus.FAILURE,
        "cancelled": CIBuildStatus.CANCELLED,
        "skipped": CIBuildStatus.SKIPPED,
    }

    def __init__(
        self,
        token: str | None = None,
        owner: str = "",
        repo: str = "",
        api_base: str = "https://api.github.com",
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._owner = owner
        self._repo = repo
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout

    def normalize_result(self, raw: dict[str, Any]) -> CIBuildResult:
        """GitHub Actions のワークフロー実行結果を正規化する。

        Parameters
        ----------
        raw : dict[str, Any]
            GitHub Actions API レスポンス辞書。
            想定キー: ``conclusion``, ``run_id``, ``html_url``,
            ``run_started_at``, ``updated_at``。

        Returns
        -------
        CIBuildResult
            正規化されたビルド結果。
        """
        conclusion = raw.get("conclusion", "")
        status = self._STATUS_MAP.get(
            conclusion, CIBuildStatus.RUNNING,
        )
        build_id = str(raw.get("run_id", raw.get("id", "")))
        log_url = str(raw.get("html_url", ""))
        duration = float(raw.get("duration_seconds", 0.0))

        logger.debug(
            "GitHub Actions 正規化: build_id=%s, status=%s",
            build_id,
            status.value,
        )
        return CIBuildResult(
            provider=CIProvider.GITHUB_ACTIONS,
            build_id=build_id,
            status=status,
            duration_seconds=duration,
            log_url=log_url,
        )

    def get_status(self, build_id: str) -> CIBuildResult:
        """GitHub Actions API からワークフロー実行結果を取得する。

        Parameters
        ----------
        build_id : str
            ワークフロー実行ID（run_id）。

        Returns
        -------
        CIBuildResult
            正規化されたビルド結果。

        Raises
        ------
        CIAdapterError
            APIトークン未設定、または API 呼び出しに失敗した場合。
        """
        if not self._token:
            raise CIAdapterError(
                "GitHub API トークンが未設定です。"
                "環境変数 GITHUB_TOKEN を設定するか、"
                "コンストラクタの token 引数で指定してください。"
            )
        if not self._owner or not self._repo:
            raise CIAdapterError(
                "owner と repo が必要です。コンストラクタで指定してください。"
            )

        url = (
            f"{self._api_base}/repos/{self._owner}/{self._repo}"
            f"/actions/runs/{build_id}"
        )
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            response = httpx.get(
                url, headers=headers, timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise CIAdapterError(
                f"GitHub Actions API エラー: "
                f"status={exc.response.status_code}, url={url}"
            ) from exc
        except httpx.RequestError as exc:
            raise CIAdapterError(
                f"GitHub Actions API 接続エラー: {exc}"
            ) from exc

        raw = response.json()
        logger.info(
            "GitHub Actions API 取得成功: run_id=%s", build_id,
        )
        return self.normalize_result(raw)


# ── GitLabCIAdapter ──


class GitLabCIAdapter(CIAdapterBase):
    """GitLab CI 用アダプター。

    Parameters
    ----------
    token : str | None
        GitLab APIトークン。未指定時は環境変数 ``GITLAB_TOKEN`` を使用する。
    project_id : str
        GitLabプロジェクトID。
    api_base : str
        GitLab API のベースURL。
    timeout : float
        HTTPリクエストのタイムアウト秒。
    """

    _STATUS_MAP: dict[str, CIBuildStatus] = {
        "success": CIBuildStatus.SUCCESS,
        "failed": CIBuildStatus.FAILURE,
        "canceled": CIBuildStatus.CANCELLED,
        "skipped": CIBuildStatus.SKIPPED,
    }

    def __init__(
        self,
        token: str | None = None,
        project_id: str = "",
        api_base: str = "https://gitlab.com/api/v4",
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._token = token or os.environ.get("GITLAB_TOKEN", "")
        self._project_id = project_id
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout

    def normalize_result(self, raw: dict[str, Any]) -> CIBuildResult:
        """GitLab CI のパイプライン結果を正規化する。

        Parameters
        ----------
        raw : dict[str, Any]
            GitLab CI API レスポンス辞書。
            想定キー: ``status``, ``id``, ``web_url``,
            ``duration``。

        Returns
        -------
        CIBuildResult
            正規化されたビルド結果。
        """
        gl_status = raw.get("status", "")
        status = self._STATUS_MAP.get(
            gl_status, CIBuildStatus.RUNNING,
        )
        build_id = str(raw.get("id", ""))
        log_url = str(raw.get("web_url", ""))
        duration = float(raw.get("duration", 0.0))

        logger.debug(
            "GitLab CI 正規化: build_id=%s, status=%s",
            build_id,
            status.value,
        )
        return CIBuildResult(
            provider=CIProvider.GITLAB_CI,
            build_id=build_id,
            status=status,
            duration_seconds=duration,
            log_url=log_url,
        )

    def get_status(self, build_id: str) -> CIBuildResult:
        """GitLab CI API からパイプライン結果を取得する。

        Parameters
        ----------
        build_id : str
            パイプラインID。

        Returns
        -------
        CIBuildResult
            正規化されたビルド結果。

        Raises
        ------
        CIAdapterError
            APIトークン未設定、または API 呼び出しに失敗した場合。
        """
        if not self._token:
            raise CIAdapterError(
                "GitLab API トークンが未設定です。"
                "環境変数 GITLAB_TOKEN を設定するか、"
                "コンストラクタの token 引数で指定してください。"
            )
        if not self._project_id:
            raise CIAdapterError(
                "project_id が必要です。コンストラクタで指定してください。"
            )

        url = (
            f"{self._api_base}/projects/{self._project_id}"
            f"/pipelines/{build_id}"
        )
        headers = {
            "PRIVATE-TOKEN": self._token,
        }

        try:
            response = httpx.get(
                url, headers=headers, timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise CIAdapterError(
                f"GitLab CI API エラー: "
                f"status={exc.response.status_code}, url={url}"
            ) from exc
        except httpx.RequestError as exc:
            raise CIAdapterError(
                f"GitLab CI API 接続エラー: {exc}"
            ) from exc

        raw = response.json()
        logger.info(
            "GitLab CI API 取得成功: pipeline_id=%s", build_id,
        )
        return self.normalize_result(raw)


# ── CIAdapterRegistry ──


class CIAdapterRegistry:
    """CIアダプターのレジストリ。

    プロバイダーごとのアダプターを登録・取得し、
    生データの正規化を一元的に実行する。
    """

    def __init__(self) -> None:
        self._adapters: dict[CIProvider, CIAdapterBase] = {}
        self._lock = threading.Lock()

    def register(
        self, provider: CIProvider, adapter: CIAdapterBase,
    ) -> None:
        """アダプターを登録する。

        Parameters
        ----------
        provider : CIProvider
            CIプロバイダー種別。
        adapter : CIAdapterBase
            対応するアダプターインスタンス。
        """
        with self._lock:
            self._adapters[provider] = adapter
        logger.info("CIアダプター登録: %s", provider.value)

    def get(self, provider: CIProvider) -> CIAdapterBase | None:
        """登録済みアダプターを取得する。

        Parameters
        ----------
        provider : CIProvider
            CIプロバイダー種別。

        Returns
        -------
        CIAdapterBase | None
            登録済みアダプター。未登録の場合は None。
        """
        with self._lock:
            return self._adapters.get(provider)

    def list_providers(self) -> list[CIProvider]:
        """登録済みプロバイダー一覧を返す。

        Returns
        -------
        list[CIProvider]
            登録済みプロバイダーのリスト。
        """
        with self._lock:
            return list(self._adapters.keys())

    def normalize(
        self, provider: CIProvider, raw: dict[str, Any],
    ) -> CIBuildResult:
        """指定プロバイダーで生データを正規化する。

        Parameters
        ----------
        provider : CIProvider
            CIプロバイダー種別。
        raw : dict[str, Any]
            CIサービスから返された生のレスポンス辞書。

        Returns
        -------
        CIBuildResult
            正規化されたビルド結果。

        Raises
        ------
        KeyError
            指定プロバイダーが未登録の場合。
        """
        with self._lock:
            adapter = self._adapters.get(provider)
        if adapter is None:
            msg = f"未登録のCIプロバイダー: {provider.value}"
            raise KeyError(msg)
        return adapter.normalize_result(raw)
