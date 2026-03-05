"""国際化（i18n）サポート。

提案8: 多言語対応のための翻訳ストア・ロケール解決・
プロンプトローカライズ・用語集翻訳を提供する。

- ロケールと翻訳エントリの管理
- デフォルトロケールの解決
- テンプレート内の {key} パターンの置換
- 用語集の管理と翻訳
- YAMLメッセージカタログからの一括読み込み
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# ============================================================
# ロケール
# ============================================================


class Locale(StrEnum):
    """サポートされるロケール。"""

    JA = "ja"
    EN = "en"
    ZH = "zh"
    KO = "ko"


# ============================================================
# 翻訳エントリ
# ============================================================


@dataclass
class TranslationEntry:
    """1件の翻訳エントリ。"""

    key: str
    locale: Locale
    value: str


# ============================================================
# 翻訳ストア
# ============================================================


class TranslationStore:
    """キーとロケールに基づく翻訳データの管理。"""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, Locale], str] = {}

    def add(self, entry: TranslationEntry) -> None:
        """翻訳エントリを追加する。"""
        self._entries[(entry.key, entry.locale)] = entry.value
        logger.info(
            "翻訳追加: key=%s locale=%s", entry.key, entry.locale,
        )

    def get(self, key: str, locale: Locale) -> str | None:
        """翻訳値を取得する。見つからない場合は None。"""
        return self._entries.get((key, locale))

    def get_or_default(
        self, key: str, locale: Locale, default: str = "",
    ) -> str:
        """翻訳値を取得する。見つからない場合はデフォルト値。"""
        return self._entries.get((key, locale), default)

    def list_keys(self, locale: Locale | None = None) -> list[str]:
        """登録済みキーの一覧を返す。

        locale を指定した場合はそのロケールのキーのみ返す。
        """
        if locale is not None:
            keys = {k for k, loc in self._entries if loc == locale}
        else:
            keys = {k for k, _ in self._entries}
        return sorted(keys)

    def list_locales(self) -> list[Locale]:
        """登録済みロケールの一覧を返す。"""
        locales = {loc for _, loc in self._entries}
        return sorted(locales, key=lambda x: x.value)

    @property
    def count(self) -> int:
        """登録済みエントリ数を返す。"""
        return len(self._entries)


# ============================================================
# ロケール解決
# ============================================================


class LocaleResolver:
    """デフォルトロケールの管理と解決。"""

    def __init__(self) -> None:
        self._default: Locale = Locale.JA

    def set_default(self, locale: Locale) -> None:
        """デフォルトロケールを設定する。"""
        self._default = locale
        logger.info("デフォルトロケール設定: %s", locale)

    def get_default(self) -> Locale:
        """デフォルトロケールを返す。"""
        return self._default

    def resolve(self, preferred: Locale | None = None) -> Locale:
        """優先ロケールがあればそれを、なければデフォルトを返す。"""
        if preferred is not None:
            return preferred
        return self._default


# ============================================================
# プロンプトローカライザ
# ============================================================


_KEY_PATTERN = re.compile(r"\{(\w+)\}")


class PromptLocalizer:
    """テンプレート中の {key} を翻訳値で置換する。"""

    def __init__(self) -> None:
        self._store: TranslationStore | None = None

    def set_translations(self, store: TranslationStore) -> None:
        """使用する翻訳ストアを設定する。"""
        self._store = store

    def localize_prompt(
        self,
        template: str,
        locale: Locale,
        context: dict[str, Any] | None = None,
    ) -> str:
        """テンプレート内の {key} パターンを翻訳値で置換する。

        context が与えられた場合はそちらを優先し、
        見つからなければ翻訳ストアを参照する。
        未解決のキーはそのまま残す。
        """
        ctx = context or {}

        def _replacer(match: re.Match[str]) -> str:
            key = match.group(1)
            if key in ctx:
                return str(ctx[key])
            if self._store is not None:
                val = self._store.get(key, locale)
                if val is not None:
                    return val
            return str(match.group(0))

        result = _KEY_PATTERN.sub(_replacer, template)
        logger.info(
            "プロンプトローカライズ: locale=%s len=%d",
            locale, len(result),
        )
        return result


# ============================================================
# 用語集翻訳
# ============================================================


class GlossaryTranslator:
    """ドメイン用語の翻訳管理。"""

    def __init__(self) -> None:
        self._glossary: dict[tuple[str, Locale], str] = {}

    def add_term(
        self, term: str, locale: Locale, translation: str,
    ) -> None:
        """用語の翻訳を追加する。"""
        self._glossary[(term, locale)] = translation
        logger.info(
            "用語追加: term=%s locale=%s", term, locale,
        )

    def translate_term(
        self, term: str, locale: Locale,
    ) -> str | None:
        """用語の翻訳を取得する。見つからない場合は None。"""
        return self._glossary.get((term, locale))

    def list_terms(self, locale: Locale) -> list[str]:
        """指定ロケールの登録済み用語の一覧を返す。"""
        terms = {t for t, loc in self._glossary if loc == locale}
        return sorted(terms)


# ============================================================
# YAML メッセージカタログローダー
# ============================================================


def _flatten_dict(
    data: dict[str, Any],
    prefix: str = "",
    sep: str = ".",
) -> dict[str, str]:
    """ネストされた辞書をドット区切りのフラットキーに展開する。

    Parameters
    ----------
    data : dict[str, Any]
        ネストされた辞書。
    prefix : str
        キーの接頭辞。
    sep : str
        キー区切り文字。

    Returns
    -------
    dict[str, str]
        フラット化されたキーと値のマッピング。
    """
    items: dict[str, str] = {}
    for key, value in data.items():
        full_key = f"{prefix}{sep}{key}" if prefix else key
        if isinstance(value, dict):
            items.update(_flatten_dict(value, full_key, sep))
        else:
            items[full_key] = str(value)
    return items


def load_messages_from_yaml(
    yaml_path: str | Path,
    locale: Locale,
) -> TranslationStore:
    """YAMLメッセージカタログを読み込み、TranslationStore を返す。

    YAMLファイルのネスト構造はドット区切りキーに展開される。
    例: ``pdca.phase.plan`` → ``"計画"``

    Parameters
    ----------
    yaml_path : str | Path
        メッセージカタログファイルのパス。
    locale : Locale
        このカタログのロケール。

    Returns
    -------
    TranslationStore
        読み込まれた翻訳データを格納したストア。

    Raises
    ------
    FileNotFoundError
        ファイルが存在しない場合。
    ValueError
        YAMLの内容が辞書でない場合。
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(
            f"メッセージカタログが見つかりません: {path}"
        )

    with path.open(encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"メッセージカタログの形式が不正です（辞書が必要）: {path}"
        )

    store = TranslationStore()
    flat = _flatten_dict(data)
    for key, value in flat.items():
        store.add(TranslationEntry(key=key, locale=locale, value=value))

    logger.info(
        "メッセージカタログ読み込み: locale=%s, %d件, path=%s",
        locale.value, store.count, path,
    )
    return store


def load_messages_dir(
    dir_path: str | Path,
) -> TranslationStore:
    """ディレクトリ内の全メッセージカタログを読み込む。

    ``messages_{locale}.yml`` のファイル名パターンを自動検出する。
    複数ロケールのメッセージを1つの TranslationStore に統合する。

    Parameters
    ----------
    dir_path : str | Path
        メッセージカタログのディレクトリパス。

    Returns
    -------
    TranslationStore
        全ロケールの翻訳データを格納したストア。

    Raises
    ------
    FileNotFoundError
        ディレクトリが存在しない場合。
    """
    path = Path(dir_path)
    if not path.is_dir():
        raise FileNotFoundError(
            f"メッセージカタログディレクトリが見つかりません: {path}"
        )

    locale_map: dict[str, Locale] = {loc.value: loc for loc in Locale}
    store = TranslationStore()

    for yml_file in sorted(path.glob("messages_*.yml")):
        # ファイル名から "messages_ja.yml" → "ja" を抽出
        stem = yml_file.stem  # "messages_ja"
        parts = stem.split("_", 1)
        if len(parts) != 2:
            continue
        locale_code = parts[1]
        locale = locale_map.get(locale_code)
        if locale is None:
            logger.warning(
                "未対応のロケール: %s (file=%s)", locale_code, yml_file,
            )
            continue

        with yml_file.open(encoding="utf-8") as f:
            data: Any = yaml.safe_load(f)

        if not isinstance(data, dict):
            logger.warning(
                "不正なカタログ形式をスキップ: %s", yml_file,
            )
            continue

        flat = _flatten_dict(data)
        for key, value in flat.items():
            store.add(TranslationEntry(key=key, locale=locale, value=value))

        logger.info(
            "カタログ読み込み: locale=%s, %d件, file=%s",
            locale.value, len(flat), yml_file.name,
        )

    logger.info(
        "メッセージカタログディレクトリ読み込み完了: 合計%d件",
        store.count,
    )
    return store
