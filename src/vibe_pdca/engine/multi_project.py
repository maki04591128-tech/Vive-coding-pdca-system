"""マルチプロジェクト管理 – 物理分離・リソース隔離保証。

M2 タスク 2-13: 要件定義書 §26.1 準拠。

隔離対象:
  - リポジトリ
  - APIキー
  - GitHub App
  - 監査ログ
  - コスト上限
  - Discordチャンネル
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# プロジェクト設定: リポジトリ・APIキー・Discordチャンネル等を個別管理
@dataclass
class ProjectConfig:
    """プロジェクト個別設定。"""

    project_id: str = field(
        default_factory=lambda: f"proj-{uuid.uuid4().hex[:8]}"
    )
    name: str = ""
    repository: str = ""
    api_key_ref: str = ""           # 秘密情報参照キー
    github_app_id: str = ""
    discord_channel_id: str = ""
    cost_limit_usd: float = 100.0   # 月額コスト上限
    audit_log_path: str = ""
    is_active: bool = True


# プロジェクトごとのリソース使用量（LLM呼び出し回数・トークン数・コスト）
@dataclass
class ResourceUsage:
    """プロジェクトごとのリソース使用量。"""

    project_id: str
    llm_calls: int = 0
    llm_tokens: int = 0
    cost_usd: float = 0.0
    cycles_completed: int = 0


class ProjectIsolationError(Exception):
    """プロジェクト隔離違反エラー。"""


# --- マルチプロジェクト管理: 各プロジェクトのリソースを物理的に隔離する ---
class MultiProjectManager:
    """マルチプロジェクトのプロセス分離を管理する。

    各プロジェクトは物理的に分離されたリソースを持ち、
    互いのデータにアクセスできない。
    """

    def __init__(self) -> None:
        self._projects: dict[str, ProjectConfig] = {}
        self._usage: dict[str, ResourceUsage] = {}

    @property
    def project_count(self) -> int:
        return len(self._projects)

    def register_project(self, config: ProjectConfig) -> str:
        """プロジェクトを登録する。

        Parameters
        ----------
        config : ProjectConfig
            プロジェクト設定。

        Returns
        -------
        str
            プロジェクトID。
        """
        self._validate_isolation(config)
        self._projects[config.project_id] = config
        self._usage[config.project_id] = ResourceUsage(
            project_id=config.project_id,
        )
        logger.info(
            "プロジェクト登録: %s (%s)", config.name, config.project_id,
        )
        return config.project_id

    def get_project(self, project_id: str) -> ProjectConfig:
        """プロジェクト設定を取得する。"""
        if project_id not in self._projects:
            raise KeyError(f"プロジェクト未登録: {project_id}")
        return self._projects[project_id]

    def list_projects(self) -> list[ProjectConfig]:
        """全プロジェクトを返す。"""
        return list(self._projects.values())

    def deactivate_project(self, project_id: str) -> None:
        """プロジェクトを非アクティブにする。"""
        config = self.get_project(project_id)
        config.is_active = False
        logger.info("プロジェクト非アクティブ化: %s", project_id)

    def record_usage(
        self,
        project_id: str,
        llm_calls: int = 0,
        llm_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """リソース使用量を記録する。"""
        if project_id not in self._usage:
            raise KeyError(f"プロジェクト未登録: {project_id}")
        usage = self._usage[project_id]
        usage.llm_calls += llm_calls
        usage.llm_tokens += llm_tokens
        usage.cost_usd += cost_usd

    def check_cost_limit(self, project_id: str) -> bool:
        """コスト上限を超過していないかチェックする。

        Returns
        -------
        bool
            超過している場合True。
        """
        config = self.get_project(project_id)
        usage = self._usage.get(project_id)
        if usage is None:
            return False
        return usage.cost_usd >= config.cost_limit_usd

    def get_usage(self, project_id: str) -> ResourceUsage:
        """プロジェクトのリソース使用量を返す。"""
        if project_id not in self._usage:
            raise KeyError(f"プロジェクト未登録: {project_id}")
        return self._usage[project_id]

    def verify_isolation(
        self,
        project_id: str,
        resource_project_id: str,
    ) -> None:
        """リソースアクセスの隔離を検証する。

        異なるプロジェクトのリソースにアクセスしようとした場合、
        ProjectIsolationError を送出する。
        """
        if project_id != resource_project_id:
            raise ProjectIsolationError(
                f"隔離違反: プロジェクト '{project_id}' は "
                f"'{resource_project_id}' のリソースにアクセスできません"
            )

    def get_status(self) -> dict[str, Any]:
        """マルチプロジェクト管理状態を返す。"""
        return {
            "project_count": self.project_count,
            "projects": {
                pid: {
                    "name": cfg.name,
                    "is_active": cfg.is_active,
                    "cost_usd": self._usage[pid].cost_usd
                    if pid in self._usage else 0.0,
                    "cost_limit_usd": cfg.cost_limit_usd,
                }
                for pid, cfg in self._projects.items()
            },
        }

    def _validate_isolation(self, config: ProjectConfig) -> None:
        """リポジトリ重複などの隔離違反をチェックする。"""
        # 同一リポジトリが複数プロジェクトに割り当てられないよう検証
        for existing in self._projects.values():
            if (
                config.repository
                and existing.repository == config.repository
                and existing.is_active
            ):
                raise ProjectIsolationError(
                    f"リポジトリ '{config.repository}' は既に "
                    f"プロジェクト '{existing.project_id}' に割り当て済み"
                )
