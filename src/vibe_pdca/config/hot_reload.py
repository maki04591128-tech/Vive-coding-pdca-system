"""設定変更のホットリロードとバージョン管理。

§17 提案17準拠:
  - 設定ファイルの変更検知（mtime ポーリング）
  - 即時適用 / 次サイクル適用モードの切り替え
  - バージョン管理とロールバック
  - 変更差分の計算と通知
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ConfigVersion
# ---------------------------------------------------------------------------

# 設定ファイルのバージョン管理（変更のたびにバージョンが上がる）
@dataclass(frozen=True)
class ConfigVersion:
    """設定のバージョン情報を保持するデータクラス。"""

    version: int
    timestamp: float
    snapshot: dict[str, Any]
    description: str = ""


# ---------------------------------------------------------------------------
# ConfigDiff
# ---------------------------------------------------------------------------

# --- 設定差分: 変更前後の設定値の違いを検出する ---
@dataclass(frozen=True)
class ConfigDiff:
    """2つの設定バージョン間の差分を表現する。"""

    added: dict[str, Any]
    removed: dict[str, Any]
    changed: dict[str, tuple[Any, Any]]

    @classmethod
    def compute(cls, old: dict[str, Any], new: dict[str, Any]) -> ConfigDiff:
        """2つの設定辞書間の差分を計算する。

        Parameters
        ----------
        old : dict
            変更前の設定。
        new : dict
            変更後の設定。
        """
        added: dict[str, Any] = {}
        removed: dict[str, Any] = {}
        changed: dict[str, tuple[Any, Any]] = {}

        all_keys = set(old) | set(new)
        for key in sorted(all_keys):
            if key not in old:
                added[key] = new[key]
            elif key not in new:
                removed[key] = old[key]
            elif old[key] != new[key]:
                changed[key] = (old[key], new[key])

        return cls(added=added, removed=removed, changed=changed)

    @property
    def has_changes(self) -> bool:
        """差分が存在するかどうかを返す。"""
        return bool(self.added or self.removed or self.changed)

    def format(self) -> str:
        """差分を人間が読みやすい文字列に整形する。"""
        lines: list[str] = []
        for key, value in self.added.items():
            lines.append(f"+ {key}: {value!r}")
        for key, value in self.removed.items():
            lines.append(f"- {key}: {value!r}")
        for key, (old_val, new_val) in self.changed.items():
            lines.append(f"~ {key}: {old_val!r} -> {new_val!r}")
        return "\n".join(lines) if lines else "(変更なし)"


# ---------------------------------------------------------------------------
# ConfigValidator
# ---------------------------------------------------------------------------

class ConfigValidator:
    """設定適用前のバリデーションを行う。"""

    DEFAULT_REQUIRED_FIELDS: list[str] = ["llm"]

    def __init__(
        self,
        required_fields: list[str] | None = None,
        numeric_ranges: dict[str, tuple[float, float]] | None = None,
        provider_list_fields: list[str] | None = None,
    ) -> None:
        """バリデータを初期化する。

        Parameters
        ----------
        required_fields : list[str] | None
            存在が必須のトップレベルキー。
        numeric_ranges : dict[str, tuple[float, float]] | None
            数値フィールド名と (min, max) のマッピング。
            ドット区切りでネストキーを指定可能（例: ``"llm.cost.daily_limit_usd"``）。
        provider_list_fields : list[str] | None
            空でないことが必要なリスト型フィールド（ドット区切り）。
        """
        self.required_fields = (
            required_fields if required_fields is not None else self.DEFAULT_REQUIRED_FIELDS
        )
        self.numeric_ranges = numeric_ranges or {}
        self.provider_list_fields = provider_list_fields or []

    def validate(self, config: dict[str, Any]) -> list[str]:
        """設定を検証してエラーメッセージのリストを返す。

        空リストが返れば検証成功。
        """
        errors: list[str] = []
        errors.extend(self._check_required(config))
        errors.extend(self._check_numeric_ranges(config))
        errors.extend(self._check_provider_lists(config))
        return errors

    # -- internal helpers ----------------------------------------------------

    def _check_required(self, config: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for f in self.required_fields:
            if f not in config:
                errors.append(f"必須フィールド '{f}' が見つかりません")
        return errors

    def _check_numeric_ranges(self, config: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for path, (lo, hi) in self.numeric_ranges.items():
            value = self._resolve_dotted(config, path)
            if value is None:
                continue
            if not isinstance(value, (int, float)):
                errors.append(
                    f"'{path}' は数値である必要があります"
                    f"（実際: {type(value).__name__}）"
                )
                continue
            if not (lo <= value <= hi):
                errors.append(
                    f"'{path}' は {lo}〜{hi} の範囲内である必要があります"
                    f"（実際: {value}）"
                )
        return errors

    def _check_provider_lists(self, config: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for path in self.provider_list_fields:
            value = self._resolve_dotted(config, path)
            if value is None:
                continue
            if not isinstance(value, list) or len(value) == 0:
                errors.append(f"'{path}' は空でないリストである必要があります")
        return errors

    @staticmethod
    def _resolve_dotted(config: dict[str, Any], path: str) -> Any:
        """ドット区切りパスで辞書の値を取得する。"""
        current: Any = config
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current


# ---------------------------------------------------------------------------
# ConfigVersionStore
# ---------------------------------------------------------------------------

class ConfigVersionStore:
    """設定バージョンの履歴を管理する。"""

    def __init__(self, max_history: int = 50) -> None:
        """バージョンストアを初期化する。

        Parameters
        ----------
        max_history : int
            保持する最大バージョン数。
        """
        self._history: list[ConfigVersion] = []
        self._max_history = max_history
        self._next_version = 1

    @property
    def history(self) -> list[ConfigVersion]:
        """バージョン履歴のコピーを返す。"""
        return list(self._history)

    @property
    def current(self) -> ConfigVersion | None:
        """現在（最新）のバージョンを返す。"""
        return self._history[-1] if self._history else None

    def add(
        self,
        config: dict[str, Any],
        description: str = "",
        timestamp: float | None = None,
    ) -> ConfigVersion:
        """新しい設定バージョンを追加する。"""
        ts = timestamp if timestamp is not None else time.time()
        version = ConfigVersion(
            version=self._next_version,
            timestamp=ts,
            snapshot=copy.deepcopy(config),
            description=description,
        )
        self._next_version += 1
        self._history.append(version)

        # 最大履歴数を超えた場合、古いものを削除
        while len(self._history) > self._max_history:
            self._history.pop(0)

        logger.info("設定バージョン %d を保存: %s", version.version, description or "(説明なし)")
        return version

    def get(self, version: int) -> ConfigVersion | None:
        """指定バージョン番号の設定を取得する。"""
        for v in self._history:
            if v.version == version:
                return v
        return None

    def rollback(self, version: int) -> ConfigVersion | None:
        """指定バージョンの設定スナップショットを新しいバージョンとして復元する。

        Returns
        -------
        ConfigVersion | None
            復元された新しいバージョン。指定バージョンが見つからない場合は None。
        """
        target = self.get(version)
        if target is None:
            logger.warning("ロールバック先のバージョン %d が見つかりません", version)
            return None

        restored = self.add(
            config=target.snapshot,
            description=f"バージョン {version} からのロールバック",
        )
        logger.info(
            "バージョン %d にロールバックしました（新バージョン %d）",
            version, restored.version,
        )
        return restored


# ---------------------------------------------------------------------------
# ApplyMode
# ---------------------------------------------------------------------------

class ApplyMode(Enum):
    """設定変更の適用タイミング。"""

    IMMEDIATE = "immediate"
    DEFERRED = "deferred"


# ---------------------------------------------------------------------------
# HotReloadManager
# ---------------------------------------------------------------------------

# --- ホットリロード: アプリを再起動せずに設定ファイルの変更を即時反映 ---
class HotReloadManager:
    """設定ファイルのホットリロードを管理する。

    ファイルの mtime ポーリングで変更を検知し、
    バージョン管理付きで設定を適用する。
    """

    def __init__(
        self,
        config_path: str | Path,
        *,
        poll_interval: float = 2.0,
        apply_mode: ApplyMode = ApplyMode.IMMEDIATE,
        validator: ConfigValidator | None = None,
        max_history: int = 50,
    ) -> None:
        """ホットリロードマネージャを初期化する。

        Parameters
        ----------
        config_path : str | Path
            監視対象の設定ファイルパス。
        poll_interval : float
            ポーリング間隔（秒）。
        apply_mode : ApplyMode
            IMMEDIATE: 検知時に即時適用。DEFERRED: 次サイクル開始時に適用。
        validator : ConfigValidator | None
            設定バリデータ。None の場合はバリデーションをスキップ。
        max_history : int
            保持する設定バージョンの最大数。
        """
        self._config_path = Path(config_path)
        self._poll_interval = poll_interval
        self._apply_mode = apply_mode
        self._validator = validator
        self._version_store = ConfigVersionStore(max_history=max_history)
        self._callbacks: list[Callable[[dict[str, Any], ConfigDiff], None]] = []
        self._last_mtime: float = 0.0
        self._pending_config: dict[str, Any] | None = None
        self._running = False
        self._poll_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def version_store(self) -> ConfigVersionStore:
        """バージョンストアを返す。"""
        return self._version_store

    @property
    def apply_mode(self) -> ApplyMode:
        """現在の適用モードを返す。"""
        with self._lock:
            return self._apply_mode

    @apply_mode.setter
    def apply_mode(self, mode: ApplyMode) -> None:
        """適用モードを変更する。"""
        with self._lock:
            self._apply_mode = mode
        logger.info("適用モードを %s に変更しました", mode.value)

    @property
    def current_config(self) -> dict[str, Any] | None:
        """現在適用中の設定を返す。"""
        current = self._version_store.current
        return copy.deepcopy(current.snapshot) if current else None

    @property
    def has_pending(self) -> bool:
        """遅延適用待ちの設定があるかどうかを返す。"""
        with self._lock:
            return self._pending_config is not None

    def register_callback(
        self,
        callback: Callable[[dict[str, Any], ConfigDiff], None],
    ) -> None:
        """設定変更時のコールバックを登録する。

        コールバックは (new_config, diff) の引数で呼び出される。
        """
        self._callbacks.append(callback)

    def load_initial(self) -> dict[str, Any]:
        """初回の設定読み込みを行う。"""
        config = self._read_config()
        self._version_store.add(config, description="初期読み込み")
        self._update_mtime()
        logger.info("初期設定を読み込みました: %s", self._config_path)
        return copy.deepcopy(config)

    def check_for_changes(self) -> bool:
        """設定ファイルの変更を確認し、必要に応じて処理する。

        Returns
        -------
        bool
            変更が検知された場合 True。
        """
        if not self._config_path.exists():
            return False

        current_mtime = self._config_path.stat().st_mtime
        with self._lock:
            if current_mtime <= self._last_mtime:
                return False
            self._last_mtime = current_mtime

        logger.info("設定ファイルの変更を検知しました: %s", self._config_path)

        new_config = self._read_config()

        # バリデーション
        if self._validator:
            errors = self._validator.validate(new_config)
            if errors:
                logger.error("設定バリデーションエラー: %s", "; ".join(errors))
                return False

        with self._lock:
            mode = self._apply_mode
        if mode == ApplyMode.IMMEDIATE:
            self._apply_config(new_config, description="ファイル変更の即時適用")
        else:
            with self._lock:
                self._pending_config = new_config
            logger.info("設定変更を遅延適用キューに追加しました")

        return True

    def apply_pending(self) -> bool:
        """遅延適用待ちの設定を適用する（サイクル開始時に呼び出す）。

        Returns
        -------
        bool
            適用が行われた場合 True。
        """
        with self._lock:
            pending = self._pending_config
            self._pending_config = None

        if pending is None:
            return False

        self._apply_config(pending, description="遅延適用（サイクル開始時）")
        return True

    def start_polling(self) -> None:
        """バックグラウンドポーリングを開始する。"""
        if self._running:
            return
        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="config-hot-reload",
        )
        self._poll_thread.start()
        logger.info("設定ファイルのポーリングを開始しました（間隔: %.1f秒）", self._poll_interval)

    def stop_polling(self) -> None:
        """バックグラウンドポーリングを停止する。"""
        self._running = False
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=self._poll_interval * 2)
        self._poll_thread = None
        logger.info("設定ファイルのポーリングを停止しました")

    def rollback(self, version: int) -> dict[str, Any] | None:
        """指定バージョンにロールバックする。

        Returns
        -------
        dict | None
            復元された設定。失敗時は None。
        """
        restored = self._version_store.rollback(version)
        if restored is None:
            return None

        # コールバック通知
        prev = self._version_store.get(restored.version - 1)
        if prev:
            diff = ConfigDiff.compute(prev.snapshot, restored.snapshot)
            self._notify_callbacks(restored.snapshot, diff)

        return copy.deepcopy(restored.snapshot)

    # -- internal helpers ----------------------------------------------------

    def _read_config(self) -> dict[str, Any]:
        """設定ファイルを読み込んで辞書を返す。"""
        try:
            import yaml
        except ImportError as e:
            raise RuntimeError("PyYAML が必要です: pip install pyyaml") from e

        with open(self._config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _update_mtime(self) -> None:
        """現在のファイル mtime を記録する。"""
        if self._config_path.exists():
            mtime = self._config_path.stat().st_mtime
            with self._lock:
                self._last_mtime = mtime

    def _apply_config(self, config: dict[str, Any], description: str = "") -> None:
        """設定を適用しバージョンストアに記録する。"""
        prev = self._version_store.current
        new_version = self._version_store.add(config, description=description)

        if prev:
            diff = ConfigDiff.compute(prev.snapshot, new_version.snapshot)
        else:
            diff = ConfigDiff.compute({}, new_version.snapshot)

        if diff.has_changes:
            logger.info("設定変更を適用しました（v%d）:\n%s", new_version.version, diff.format())
        self._notify_callbacks(new_version.snapshot, diff)

    def _notify_callbacks(
        self,
        config: dict[str, Any],
        diff: ConfigDiff,
    ) -> None:
        """登録済みコールバックを呼び出す。"""
        for cb in self._callbacks:
            try:
                cb(copy.deepcopy(config), diff)
            except Exception:
                logger.exception("設定変更コールバックでエラーが発生しました")

    def _poll_loop(self) -> None:
        """ポーリングループ（バックグラウンドスレッドで実行）。"""
        while self._running:
            try:
                self.check_for_changes()
            except Exception:
                logger.exception("設定ファイルのポーリング中にエラーが発生しました")
            time.sleep(self._poll_interval)
