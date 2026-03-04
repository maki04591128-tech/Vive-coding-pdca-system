"""GitHub連携基盤 – App認証・ステートストア。

M0 タスク 0-5: GitHub App認証（JWT→トークン→API操作）
M1 タスク 1-2: GitHubステートストア（Issue/PR/Milestone CRUD）

要件定義書 §4.2, §9, §9.6, ADR-005 準拠。
状態の永続化方式: GitHub Issues をステートストアとして使用する。
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

__all__ = [
    "LabelPrefix",
    "STANDARD_LABELS",
    "GitHubAppConfig",
    "GitHubAppAuth",
    "IssueState",
    "StateEntry",
    "GitHubStateStore",
]


# ============================================================
# ラベル体系（§4.2 GitHubステートストア設計）
# ============================================================


class LabelPrefix(StrEnum):
    """GitHub Issue/PRのラベルプレフィクス。"""

    PHASE = "phase/"
    STATUS = "status/"
    PRIORITY = "priority/"
    TYPE = "type/"
    SEVERITY = "severity/"
    CHANGE_TYPE = "change-type/"
    GOVERNANCE = "governance/"


# 標準ラベルセット
STANDARD_LABELS: dict[str, dict[str, str]] = {
    # フェーズラベル
    "phase/plan": {"color": "0075ca", "description": "PLANフェーズ"},
    "phase/do": {"color": "008672", "description": "DOフェーズ"},
    "phase/check": {"color": "e4e669", "description": "CHECKフェーズ"},
    "phase/act": {"color": "d876e3", "description": "ACTフェーズ"},
    # ステータスラベル
    "status/running": {"color": "0e8a16", "description": "実行中"},
    "status/completed": {"color": "5319e7", "description": "完了"},
    "status/stopped": {"color": "b60205", "description": "停止"},
    "status/blocked": {"color": "fbca04", "description": "ブロック中"},
    # 優先度ラベル
    "priority/high": {"color": "b60205", "description": "高優先度"},
    "priority/medium": {"color": "fbca04", "description": "中優先度"},
    "priority/low": {"color": "0e8a16", "description": "低優先度"},
    # ガバナンスラベル
    "governance/a": {"color": "b60205", "description": "A操作（人間承認必須）"},
    "governance/b": {"color": "fbca04", "description": "B操作（ペルソナ3承認）"},
    "governance/c": {"color": "0e8a16", "description": "C操作（自動実行可）"},
}


# ============================================================
# GitHub App認証（M0 タスク 0-5）
# ============================================================


@dataclass
class GitHubAppConfig:
    """GitHub App設定。ADR-005 準拠。"""

    app_id: str = ""
    private_key: str = ""          # PEMキー内容
    installation_id: str = ""
    webhook_secret: str = ""       # Webhook署名検証用


class GitHubAppAuth:
    """GitHub App認証: JWT→Installation Access Token→API操作。

    Parameters
    ----------
    config : GitHubAppConfig
        GitHub App設定。
    """

    def __init__(self, config: GitHubAppConfig) -> None:
        self._config = config
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def app_id(self) -> str:
        return self._config.app_id

    @property
    def installation_id(self) -> str:
        return self._config.installation_id

    def generate_jwt(self) -> str:
        """JWT（JSON Web Token）を生成する。

        GitHub App として認証するための JWT を生成する。
        有効期限は10分間。

        Returns
        -------
        str
            生成されたJWT文字列。

        Raises
        ------
        ValueError
            app_id または private_key が未設定の場合。
        """
        if not self._config.app_id or not self._config.private_key:
            raise ValueError("GitHub App ID と Private Key が必要です")

        now = int(time.time())
        payload = {
            # システム間のクロックスキューを吸収するため60秒前を発行時刻とする
            "iat": now - 60,
            "exp": now + (10 * 60),      # 有効期限（10分後）
            "iss": self._config.app_id,  # 発行者（App ID）
        }
        # NOTE: 本番ではPyJWTライブラリでRS256署名する。
        # 現在はスタブ実装（依存を最小化するため）。
        logger.info("JWT生成: app_id=%s, exp=%d", self._config.app_id, payload["exp"])
        return f"jwt-placeholder-{self._config.app_id}-{now}"

    def get_installation_token(self) -> str:
        """Installation Access Tokenを取得する。

        キャッシュされたトークンが有効な場合はそれを返す。
        期限切れの場合は新しいトークンを取得する。

        Returns
        -------
        str
            有効なInstallation Access Token。

        Raises
        ------
        ValueError
            installation_id が未設定の場合。
        """
        if not self._config.installation_id:
            raise ValueError("Installation ID が必要です")

        now = time.time()
        if self._token and now < self._token_expires_at:
            return self._token

        _jwt = self.generate_jwt()
        # NOTE: 本番ではGitHub APIを呼び出してトークンを取得する:
        #   POST /app/installations/{installation_id}/access_tokens
        #   Authorization: Bearer {_jwt}
        # 現在はスタブ実装。
        self._token = f"ghs_placeholder_{self._config.installation_id}_{int(now)}"
        self._token_expires_at = now + 3600  # 1時間有効
        logger.info(
            "Installation Token取得: installation_id=%s",
            self._config.installation_id,
        )
        return self._token

    def verify_webhook_signature(
        self, payload: bytes, signature: str,
    ) -> bool:
        """Webhook署名を検証する。

        Parameters
        ----------
        payload : bytes
            Webhookのリクエストボディ。
        signature : str
            X-Hub-Signature-256 ヘッダの値。

        Returns
        -------
        bool
            署名が有効な場合True。
        """
        if not self._config.webhook_secret:
            logger.warning("Webhook secret が未設定です")
            return False

        expected = "sha256=" + hmac.new(
            self._config.webhook_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


# ============================================================
# GitHubステートストア（M1 タスク 1-2）
# ============================================================


class IssueState(StrEnum):
    """Issue/PRの状態。"""

    OPEN = "open"
    CLOSED = "closed"


class StateEntry(BaseModel):
    """ステートストアのエントリ。"""

    number: int = Field(..., description="Issue/PR番号")
    title: str = Field(..., description="タイトル")
    state: IssueState = Field(default=IssueState.OPEN)
    labels: list[str] = Field(default_factory=list)
    body: str = Field(default="")
    resource_type: str = Field(
        default="issue", description="リソース種別（issue/pr/milestone）"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class GitHubStateStore:
    """GitHub Issues/PR/Milestoneをステートストアとして使用する。

    要件定義書 §4.2 準拠:
      - PDCAの状態はすべてGitHub上のデータとして表現・管理する
      - 外部DBは持たない
      - リカバリはGitHub上の最新状態を読み込むことで実現する

    Parameters
    ----------
    auth : GitHubAppAuth | None
        GitHub App認証（NoneならオフラインCRUDのみ）。
    owner : str
        リポジトリオーナー。
    repo : str
        リポジトリ名。
    """

    def __init__(
        self,
        auth: GitHubAppAuth | None = None,
        owner: str = "",
        repo: str = "",
    ) -> None:
        self._auth = auth
        self._owner = owner
        self._repo = repo
        # オフラインCRUD用のインメモリストア
        self._entries: dict[int, StateEntry] = {}
        self._next_number: int = 1

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def repo(self) -> str:
        return self._repo

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    # ── CRUD操作 ──

    def create_issue(
        self,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StateEntry:
        """Issueを作成する。

        Parameters
        ----------
        title : str
            Issueタイトル。
        body : str
            Issue本文。
        labels : list[str] | None
            付与するラベル。
        metadata : dict[str, Any] | None
            追加メタデータ。

        Returns
        -------
        StateEntry
            作成されたIssueエントリ。
        """
        entry = StateEntry(
            number=self._next_number,
            title=title,
            body=body,
            labels=labels or [],
            resource_type="issue",
            metadata=metadata or {},
        )
        self._entries[entry.number] = entry
        self._next_number += 1
        logger.info("Issue作成: #%d '%s'", entry.number, title)
        return entry

    def get_issue(self, number: int) -> StateEntry | None:
        """Issue番号でエントリを取得する。"""
        return self._entries.get(number)

    def update_issue(
        self,
        number: int,
        title: str | None = None,
        body: str | None = None,
        state: IssueState | None = None,
        labels: list[str] | None = None,
    ) -> StateEntry:
        """Issueを更新する。

        Parameters
        ----------
        number : int
            Issue番号。
        title : str | None
            新しいタイトル。
        body : str | None
            新しい本文。
        state : IssueState | None
            新しい状態。
        labels : list[str] | None
            新しいラベルリスト。

        Returns
        -------
        StateEntry
            更新されたエントリ。

        Raises
        ------
        KeyError
            Issue番号が見つからない場合。
        """
        entry = self._entries.get(number)
        if entry is None:
            raise KeyError(f"Issue #{number} が見つかりません")

        if title is not None:
            entry.title = title
        if body is not None:
            entry.body = body
        if state is not None:
            entry.state = state
        if labels is not None:
            entry.labels = labels
        entry.updated_at = time.time()
        logger.info("Issue更新: #%d", number)
        return entry

    def close_issue(self, number: int) -> StateEntry:
        """Issueをクローズする。"""
        return self.update_issue(number, state=IssueState.CLOSED)

    def list_issues(
        self,
        state: IssueState | None = None,
        labels: list[str] | None = None,
        resource_type: str | None = None,
    ) -> list[StateEntry]:
        """条件に一致するIssueを一覧する。

        Parameters
        ----------
        state : IssueState | None
            フィルタする状態。
        labels : list[str] | None
            すべて含むラベルでフィルタ。
        resource_type : str | None
            リソース種別でフィルタ。

        Returns
        -------
        list[StateEntry]
            条件に一致するエントリのリスト。
        """
        results: list[StateEntry] = []
        for entry in self._entries.values():
            if state is not None and entry.state != state:
                continue
            if labels and not all(lbl in entry.labels for lbl in labels):
                continue
            if resource_type and entry.resource_type != resource_type:
                continue
            results.append(entry)
        return results

    # ── ラベル自動適用 ──

    def apply_phase_label(self, number: int, phase: str) -> StateEntry:
        """PDCAフェーズラベルを適用する（排他的に切替）。

        Parameters
        ----------
        number : int
            Issue番号。
        phase : str
            PDCAフェーズ（plan/do/check/act）。

        Returns
        -------
        StateEntry
            更新されたエントリ。
        """
        entry = self._entries.get(number)
        if entry is None:
            raise KeyError(f"Issue #{number} が見つかりません")

        # 既存のphaseラベルを除去
        entry.labels = [
            lbl for lbl in entry.labels
            if not lbl.startswith(LabelPrefix.PHASE)
        ]
        # 新しいフェーズラベルを追加
        new_label = f"{LabelPrefix.PHASE}{phase}"
        entry.labels.append(new_label)
        entry.updated_at = time.time()
        logger.info("フェーズラベル適用: #%d → %s", number, new_label)
        return entry

    def apply_status_label(self, number: int, status: str) -> StateEntry:
        """ステータスラベルを適用する（排他的に切替）。"""
        entry = self._entries.get(number)
        if entry is None:
            raise KeyError(f"Issue #{number} が見つかりません")

        entry.labels = [
            lbl for lbl in entry.labels
            if not lbl.startswith(LabelPrefix.STATUS)
        ]
        new_label = f"{LabelPrefix.STATUS}{status}"
        entry.labels.append(new_label)
        entry.updated_at = time.time()
        logger.info("ステータスラベル適用: #%d → %s", number, new_label)
        return entry

    # ── 状態復元 ──

    def restore_state(self, entries: list[StateEntry]) -> int:
        """外部データから状態を復元する。

        Parameters
        ----------
        entries : list[StateEntry]
            復元するエントリのリスト。

        Returns
        -------
        int
            復元されたエントリ数。
        """
        count = 0
        for entry in entries:
            self._entries[entry.number] = entry
            if entry.number >= self._next_number:
                self._next_number = entry.number + 1
            count += 1
        logger.info("状態復元: %d件", count)
        return count

    # ── マイルストーン操作 ──

    def create_milestone(
        self,
        title: str,
        description: str = "",
    ) -> StateEntry:
        """マイルストーンを作成する。"""
        return self.create_issue(
            title=title,
            body=description,
            labels=["type/milestone"],
            metadata={"resource_type": "milestone"},
        )

    # ── ステータス ──

    def get_status(self) -> dict[str, Any]:
        """ステートストアの状態を返す。"""
        open_count = sum(
            1 for e in self._entries.values()
            if e.state == IssueState.OPEN
        )
        closed_count = sum(
            1 for e in self._entries.values()
            if e.state == IssueState.CLOSED
        )
        return {
            "owner": self._owner,
            "repo": self._repo,
            "total_entries": self.entry_count,
            "open": open_count,
            "closed": closed_count,
            "authenticated": self._auth is not None,
        }
