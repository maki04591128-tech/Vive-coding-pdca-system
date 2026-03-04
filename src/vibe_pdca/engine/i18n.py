"""国際化（i18n）サポート。

提案8: 多言語対応のための翻訳ストア・ロケール解決・
プロンプトローカライズ・用語集翻訳を提供する。

- ロケールと翻訳エントリの管理
- デフォルトロケールの解決
- テンプレート内の {key} パターンの置換
- 用語集の管理と翻訳
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import StrEnum

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
        context: dict | None = None,
    ) -> str:
        """テンプレート内の {key} パターンを翻訳値で置換する。

        context が与えられた場合はそちらを優先し、
        見つからなければ翻訳ストアを参照する。
        未解決のキーはそのまま残す。
        """
        ctx = context or {}

        def _replacer(match: re.Match) -> str:
            key = match.group(1)
            if key in ctx:
                return str(ctx[key])
            if self._store is not None:
                val = self._store.get(key, locale)
                if val is not None:
                    return val
            return match.group(0)

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
