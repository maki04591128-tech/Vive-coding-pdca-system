"""プラグイン基盤 – 拡張可能なプラグインインターフェース。

実装手順書 §4.9 / ギャップA6 準拠。

プラグインカテゴリ:
  - Notification: 通知先の交換（Discord / Slack / Email 等）
  - CI: CIプロバイダの交換（GitHub Actions / GitLab CI 等）
  - Knowledge: 知識ベースの交換（RAG / Vector DB 等）
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

__all__ = [
    "PluginCategory",
    "PluginStatus",
    "PluginMeta",
    "PluginInterface",
    "PluginManager",
]


# ============================================================
# プラグインカテゴリ
# ============================================================


class PluginCategory(StrEnum):
    """プラグインのカテゴリ。"""

    NOTIFICATION = "notification"
    CI = "ci"
    KNOWLEDGE = "knowledge"


class PluginStatus(StrEnum):
    """プラグインの状態。"""

    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


# ============================================================
# プラグインインターフェース
# ============================================================


class PluginMeta(BaseModel):
    """プラグインのメタデータ。"""

    name: str = Field(..., description="プラグイン名")
    version: str = Field(default="1.0.0", description="バージョン")
    category: PluginCategory = Field(..., description="カテゴリ")
    description: str = Field(default="", description="説明")
    author: str = Field(default="", description="作者")


class PluginInterface(ABC):
    """プラグイン基底クラス。

    すべてのプラグインはこのクラスを継承し、
    initialize / execute / shutdown を実装する。
    """

    def __init__(self, meta: PluginMeta, config: dict[str, Any] | None = None) -> None:
        self._meta = meta
        self._config = config or {}
        self._status = PluginStatus.DISABLED

    @property
    def meta(self) -> PluginMeta:
        """プラグインメタデータ。"""
        return self._meta

    @property
    def name(self) -> str:
        return self._meta.name

    @property
    def category(self) -> PluginCategory:
        return self._meta.category

    @property
    def status(self) -> PluginStatus:
        return self._status

    @abstractmethod
    def initialize(self) -> None:
        """プラグインを初期化する。

        設定の検証・外部接続の確立などを行う。
        """

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """プラグインのメイン処理を実行する。

        Parameters
        ----------
        **kwargs
            プラグイン固有のパラメータ。

        Returns
        -------
        Any
            実行結果。
        """

    @abstractmethod
    def shutdown(self) -> None:
        """プラグインを終了する。

        リソースの解放・接続のクローズなどを行う。
        """

    def get_status(self) -> dict[str, Any]:
        """プラグインの状態を返す。"""
        return {
            "name": self.name,
            "category": self.category.value,
            "version": self._meta.version,
            "status": self._status.value,
        }


# ============================================================
# プラグインマネージャー
# ============================================================


class PluginManager:
    """プラグインのライフサイクルを管理する。

    プラグインの登録・初期化・実行・無効化を一元管理する。
    """

    def __init__(self) -> None:
        self._plugins: dict[str, PluginInterface] = {}

    @property
    def plugin_count(self) -> int:
        return len(self._plugins)

    def register(self, plugin: PluginInterface) -> None:
        """プラグインを登録する。

        Parameters
        ----------
        plugin : PluginInterface
            登録するプラグイン。

        Raises
        ------
        ValueError
            同名のプラグインが既に登録されている場合。
        """
        if plugin.name in self._plugins:
            raise ValueError(f"プラグイン '{plugin.name}' は既に登録されています")
        self._plugins[plugin.name] = plugin
        logger.info(
            "プラグイン登録: %s (category=%s, version=%s)",
            plugin.name, plugin.category.value, plugin.meta.version,
        )

    def initialize(self, name: str) -> None:
        """プラグインを初期化する。

        Parameters
        ----------
        name : str
            プラグイン名。

        Raises
        ------
        KeyError
            プラグインが見つからない場合。
        """
        plugin = self._get_plugin(name)
        try:
            plugin.initialize()
            plugin._status = PluginStatus.ACTIVE
            logger.info("プラグイン初期化完了: %s", name)
        except Exception as e:
            plugin._status = PluginStatus.ERROR
            logger.error("プラグイン初期化失敗: %s - %s", name, e)
            raise

    def execute(self, name: str, **kwargs: Any) -> Any:
        """プラグインを実行する。

        Parameters
        ----------
        name : str
            プラグイン名。
        **kwargs
            プラグイン固有のパラメータ。

        Returns
        -------
        Any
            実行結果。

        Raises
        ------
        KeyError
            プラグインが見つからない場合。
        RuntimeError
            プラグインがアクティブでない場合。
        """
        plugin = self._get_plugin(name)
        if plugin.status != PluginStatus.ACTIVE:
            raise RuntimeError(
                f"プラグイン '{name}' はアクティブではありません "
                f"(status={plugin.status.value})"
            )
        return plugin.execute(**kwargs)

    def disable(self, name: str) -> None:
        """プラグインを無効化する。

        Parameters
        ----------
        name : str
            プラグイン名。
        """
        plugin = self._get_plugin(name)
        try:
            plugin.shutdown()
        except Exception as e:
            logger.warning("プラグインshutdown中にエラー: %s - %s", name, e)
        plugin._status = PluginStatus.DISABLED
        logger.info("プラグイン無効化: %s", name)

    def unregister(self, name: str) -> None:
        """プラグインを登録解除する。

        アクティブな場合は先にshutdownする。
        """
        plugin = self._get_plugin(name)
        if plugin.status == PluginStatus.ACTIVE:
            self.disable(name)
        del self._plugins[name]
        logger.info("プラグイン登録解除: %s", name)

    def get_plugin(self, name: str) -> PluginInterface | None:
        """プラグインを取得する（見つからなければNone）。"""
        return self._plugins.get(name)

    def list_plugins(
        self,
        category: PluginCategory | None = None,
        status: PluginStatus | None = None,
    ) -> list[PluginInterface]:
        """条件に一致するプラグインを一覧する。"""
        results: list[PluginInterface] = []
        for plugin in self._plugins.values():
            if category is not None and plugin.category != category:
                continue
            if status is not None and plugin.status != status:
                continue
            results.append(plugin)
        return results

    def initialize_all(self) -> dict[str, bool]:
        """全プラグインを初期化する。

        Returns
        -------
        dict[str, bool]
            プラグイン名→初期化成功フラグ。
        """
        results: dict[str, bool] = {}
        for name in self._plugins:
            try:
                self.initialize(name)
                results[name] = True
            except Exception:
                results[name] = False
        return results

    def shutdown_all(self) -> None:
        """全プラグインをシャットダウンする。"""
        for name in list(self._plugins.keys()):
            plugin = self._plugins[name]
            if plugin.status == PluginStatus.ACTIVE:
                self.disable(name)

    def get_status(self) -> dict[str, Any]:
        """プラグインマネージャーの状態を返す。"""
        return {
            "plugin_count": self.plugin_count,
            "plugins": {
                name: plugin.get_status()
                for name, plugin in self._plugins.items()
            },
        }

    def _get_plugin(self, name: str) -> PluginInterface:
        """プラグインを取得する（見つからなければKeyError）。"""
        if name not in self._plugins:
            raise KeyError(f"プラグイン '{name}' が見つかりません")
        return self._plugins[name]
