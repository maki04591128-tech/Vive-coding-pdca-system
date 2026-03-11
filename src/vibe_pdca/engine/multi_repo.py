"""マルチリポジトリ / モノレポサポート – 複数リポジトリの協調PDCAサイクル管理。

Proposal 26: Multi-Repository / Monorepo Support。

入力: リポジトリ定義・依存関係・同期モード
出力: 実行計画・リリース順序・影響パッケージ一覧
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import PurePosixPath

logger = logging.getLogger(__name__)


# ============================================================
# データクラス
# ============================================================


@dataclass
class RepoScope:
    """リポジトリスコープ定義。"""

    repo_url: str
    name: str
    scope_path: str = ""  # モノレポ内のサブパス
    branch: str = "main"


@dataclass
class CrossRepoDependency:
    """リポジトリ間依存関係。"""

    source_repo: str
    target_repo: str
    dependency_type: str  # "api", "library", "config"
    description: str = ""


@dataclass
class CoordinatedCycleConfig:
    """協調サイクル設定。"""

    goal_id: str
    repos: list[RepoScope] = field(default_factory=list)
    dependencies: list[CrossRepoDependency] = field(default_factory=list)
    sync_mode: str = "parallel"  # "parallel", "sequential"


# ============================================================
# MonorepoScopeResolver – モノレポスコープ解決
# ============================================================


class MonorepoScopeResolver:
    """モノレポ内のスコープ解決とパッケージ影響検出を行う。"""

    def resolve_scope(self, repo_path: str, scope_path: str) -> list[str]:
        """スコープパスを元に影響パスのリストを返す。

        Parameters
        ----------
        repo_path : str
            リポジトリのルートパス。
        scope_path : str
            スコープのサブパス（空文字の場合はリポジトリ全体）。

        Returns
        -------
        list[str]
            影響を受けるパスのリスト。
        """
        if not scope_path:
            logger.debug("スコープ指定なし: リポジトリ全体を対象 (%s)", repo_path)
            return [repo_path]

        base = repo_path.rstrip("/")
        clean_scope = scope_path.strip("/")
        resolved = f"{base}/{clean_scope}"
        # パストラバーサル防止: 解決後パスがベースパス配下にあることを確認
        if ".." in PurePosixPath(clean_scope).parts:
            logger.warning("パストラバーサル検出: scope_path=%s", scope_path)
            return [repo_path]
        logger.debug("スコープ解決: %s", resolved)
        return [resolved]

    def detect_affected_packages(
        self,
        changed_files: list[str],
        package_paths: list[str],
    ) -> list[str]:
        """変更ファイルから影響を受けるパッケージを検出する。

        Parameters
        ----------
        changed_files : list[str]
            変更されたファイルパスのリスト。
        package_paths : list[str]
            パッケージのルートパスのリスト。

        Returns
        -------
        list[str]
            影響を受けるパッケージパスのリスト。
        """
        affected: list[str] = []
        for pkg_path in package_paths:
            normalized_pkg = pkg_path.rstrip("/")
            for changed in changed_files:
                normalized_changed = changed.replace("\\", "/")
                is_match = (
                    normalized_changed.startswith(normalized_pkg + "/")
                    or normalized_changed == normalized_pkg
                )
                if is_match and normalized_pkg not in affected:
                    affected.append(normalized_pkg)
                    break
        if affected:
            logger.info("影響パッケージを %d 件検出", len(affected))
        return affected


# ============================================================
# CrossRepoCoordinator – クロスリポジトリ協調
# ============================================================


class CrossRepoCoordinator:
    """複数リポジトリの依存関係を管理し、実行計画を生成する。"""

    def __init__(self) -> None:
        self._repos: dict[str, RepoScope] = {}
        self._dependencies: list[CrossRepoDependency] = []

    def register_repos(self, repos: list[RepoScope]) -> None:
        """リポジトリを登録する。

        Parameters
        ----------
        repos : list[RepoScope]
            登録するリポジトリのリスト。
        """
        for repo in repos:
            self._repos[repo.name] = repo
            logger.debug("リポジトリ登録: %s", repo.name)

    def add_dependency(self, dep: CrossRepoDependency) -> None:
        """依存関係を追加する。

        Parameters
        ----------
        dep : CrossRepoDependency
            追加する依存関係。
        """
        self._dependencies.append(dep)
        logger.debug(
            "依存関係追加: %s → %s (%s)",
            dep.source_repo,
            dep.target_repo,
            dep.dependency_type,
        )

    def get_execution_plan(
        self, config: CoordinatedCycleConfig
    ) -> list[list[str]]:
        """依存関係に基づいた実行計画（トポロジカル順序のグループ）を返す。

        Parameters
        ----------
        config : CoordinatedCycleConfig
            協調サイクル設定。

        Returns
        -------
        list[list[str]]
            実行順序のグループリスト。各グループ内は並列実行可能。
        """
        if config.sync_mode == "sequential":
            return [[r.name] for r in config.repos]

        # トポロジカルソートで実行グループを決定
        repo_names = {r.name for r in config.repos}
        in_degree: dict[str, int] = {name: 0 for name in repo_names}
        adj: dict[str, list[str]] = {name: [] for name in repo_names}

        for dep in config.dependencies:
            if dep.source_repo in repo_names and dep.target_repo in repo_names:
                adj[dep.target_repo].append(dep.source_repo)
                in_degree[dep.source_repo] = in_degree.get(dep.source_repo, 0) + 1

        groups: list[list[str]] = []
        remaining = dict(in_degree)

        while remaining:
            # 入次数 0 のノードを次のグループとする
            ready = sorted([n for n, d in remaining.items() if d == 0])
            if not ready:
                # 循環依存: 残りを一括グループに
                logger.warning("循環依存を検出: 残りのリポジトリを一括実行")
                groups.append(sorted(remaining.keys()))
                break
            groups.append(ready)
            for node in ready:
                del remaining[node]
                for neighbor in adj.get(node, []):
                    if neighbor in remaining:
                        remaining[neighbor] -= 1

        logger.info("実行計画: %d グループ", len(groups))
        return groups

    def validate_dependencies(self) -> list[str]:
        """登録済み依存関係の妥当性を検証する。

        Returns
        -------
        list[str]
            エラーメッセージのリスト。空なら問題なし。
        """
        errors: list[str] = []
        valid_types = {"api", "library", "config"}

        for dep in self._dependencies:
            if dep.source_repo not in self._repos:
                errors.append(
                    f"依存元リポジトリ '{dep.source_repo}' が未登録です"
                )
            if dep.target_repo not in self._repos:
                errors.append(
                    f"依存先リポジトリ '{dep.target_repo}' が未登録です"
                )
            if dep.dependency_type not in valid_types:
                errors.append(
                    f"不正な依存タイプ '{dep.dependency_type}'"
                    f" (有効値: {', '.join(sorted(valid_types))})"
                )
            if dep.source_repo == dep.target_repo:
                errors.append(
                    f"自己依存は許可されていません: '{dep.source_repo}'"
                )

        if errors:
            logger.warning("依存関係の検証エラー: %d 件", len(errors))
        return errors


# ============================================================
# ReleaseCoordinator – リリース協調
# ============================================================


class ReleaseCoordinator:
    """複数リポジトリのリリース判定と順序決定を行う。"""

    def should_release_together(
        self,
        repos: list[str],
        dependencies: list[CrossRepoDependency],
    ) -> bool:
        """指定リポジトリ群を同時リリースすべきか判定する。

        Parameters
        ----------
        repos : list[str]
            リポジトリ名のリスト。
        dependencies : list[CrossRepoDependency]
            依存関係のリスト。

        Returns
        -------
        bool
            同時リリースが推奨される場合 True。
        """
        repo_set = set(repos)
        for dep in dependencies:
            if (
                dep.source_repo in repo_set
                and dep.target_repo in repo_set
                and dep.dependency_type == "api"
            ):
                    logger.info(
                        "API 依存のため同時リリース推奨: %s ↔ %s",
                        dep.source_repo,
                        dep.target_repo,
                    )
                    return True
        return False

    def get_release_order(
        self,
        repos: list[str],
        dependencies: list[CrossRepoDependency],
    ) -> list[str]:
        """依存関係に基づいたリリース順序を返す。

        Parameters
        ----------
        repos : list[str]
            リポジトリ名のリスト。
        dependencies : list[CrossRepoDependency]
            依存関係のリスト。

        Returns
        -------
        list[str]
            リリース順序のリスト（依存先が先）。
        """
        repo_set = set(repos)
        in_degree: dict[str, int] = {r: 0 for r in repos}
        adj: dict[str, list[str]] = {r: [] for r in repos}

        for dep in dependencies:
            if dep.source_repo in repo_set and dep.target_repo in repo_set:
                adj[dep.target_repo].append(dep.source_repo)
                in_degree[dep.source_repo] += 1

        order: list[str] = []
        remaining = dict(in_degree)

        while remaining:
            ready = sorted([n for n, d in remaining.items() if d == 0])
            if not ready:
                # 循環依存: 残りをアルファベット順で追加
                logger.warning("循環依存を検出: 残りをアルファベット順でリリース")
                order.extend(sorted(remaining.keys()))
                break
            for node in ready:
                order.append(node)
                del remaining[node]
                for neighbor in adj.get(node, []):
                    if neighbor in remaining:
                        remaining[neighbor] -= 1

        logger.info("リリース順序: %s", " → ".join(order))
        return order
