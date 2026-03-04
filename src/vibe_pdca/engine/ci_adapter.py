"""外部CI/CDサービス統合アダプター。

提案12: GitHub Actions・GitLab CI等の外部CIサービスからビルド結果を
取得・正規化し、PDCAサイクルへ統合する。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


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


class CIAdapterBase:
    """CIアダプターの基底クラス。

    各CIプロバイダーの具象アダプターはこのクラスを継承し、
    get_status / normalize_result を実装する。
    """

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
        raise NotImplementedError

    def normalize_result(self, raw: dict) -> CIBuildResult:
        """プロバイダー固有の生データを正規化する。

        Parameters
        ----------
        raw : dict
            CIサービスから返された生のレスポンス辞書。

        Returns
        -------
        CIBuildResult
            正規化されたビルド結果。
        """
        raise NotImplementedError


# ── GitHubActionsAdapter ──


class GitHubActionsAdapter(CIAdapterBase):
    """GitHub Actions 用アダプター。"""

    _STATUS_MAP: dict[str, CIBuildStatus] = {
        "success": CIBuildStatus.SUCCESS,
        "failure": CIBuildStatus.FAILURE,
        "cancelled": CIBuildStatus.CANCELLED,
        "skipped": CIBuildStatus.SKIPPED,
    }

    def normalize_result(self, raw: dict) -> CIBuildResult:
        """GitHub Actions のワークフロー実行結果を正規化する。

        Parameters
        ----------
        raw : dict
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
        """ビルドIDからビルド結果を取得する。

        Parameters
        ----------
        build_id : str
            ワークフロー実行ID。

        Returns
        -------
        CIBuildResult
            正規化されたビルド結果。

        Raises
        ------
        NotImplementedError
            実際のAPI呼び出しは未実装。
        """
        raise NotImplementedError(
            "GitHub Actions API 呼び出しは未実装です。"
        )


# ── GitLabCIAdapter ──


class GitLabCIAdapter(CIAdapterBase):
    """GitLab CI 用アダプター。"""

    _STATUS_MAP: dict[str, CIBuildStatus] = {
        "success": CIBuildStatus.SUCCESS,
        "failed": CIBuildStatus.FAILURE,
        "canceled": CIBuildStatus.CANCELLED,
        "skipped": CIBuildStatus.SKIPPED,
    }

    def normalize_result(self, raw: dict) -> CIBuildResult:
        """GitLab CI のパイプライン結果を正規化する。

        Parameters
        ----------
        raw : dict
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
        """ビルドIDからビルド結果を取得する。

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
        NotImplementedError
            実際のAPI呼び出しは未実装。
        """
        raise NotImplementedError(
            "GitLab CI API 呼び出しは未実装です。"
        )


# ── CIAdapterRegistry ──


class CIAdapterRegistry:
    """CIアダプターのレジストリ。

    プロバイダーごとのアダプターを登録・取得し、
    生データの正規化を一元的に実行する。
    """

    def __init__(self) -> None:
        self._adapters: dict[CIProvider, CIAdapterBase] = {}

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
        return self._adapters.get(provider)

    def list_providers(self) -> list[CIProvider]:
        """登録済みプロバイダー一覧を返す。

        Returns
        -------
        list[CIProvider]
            登録済みプロバイダーのリスト。
        """
        return list(self._adapters.keys())

    def normalize(
        self, provider: CIProvider, raw: dict,
    ) -> CIBuildResult:
        """指定プロバイダーで生データを正規化する。

        Parameters
        ----------
        provider : CIProvider
            CIプロバイダー種別。
        raw : dict
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
        adapter = self._adapters.get(provider)
        if adapter is None:
            msg = f"未登録のCIプロバイダー: {provider.value}"
            raise KeyError(msg)
        return adapter.normalize_result(raw)
