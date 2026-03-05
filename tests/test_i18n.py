"""国際化（i18n）サポートのテスト。"""

from vibe_pdca.engine.i18n import (
    GlossaryTranslator,
    Locale,
    LocaleResolver,
    PromptLocalizer,
    TranslationEntry,
    TranslationStore,
)

# ============================================================
# テスト: Locale
# ============================================================


class TestLocale:
    def test_values(self):
        assert Locale.JA == "ja"
        assert Locale.EN == "en"
        assert Locale.ZH == "zh"
        assert Locale.KO == "ko"


# ============================================================
# テスト: TranslationEntry
# ============================================================


class TestTranslationEntry:
    def test_creation(self):
        entry = TranslationEntry(
            key="greeting", locale=Locale.JA, value="こんにちは",
        )
        assert entry.key == "greeting"
        assert entry.locale == Locale.JA
        assert entry.value == "こんにちは"


# ============================================================
# テスト: TranslationStore
# ============================================================


class TestTranslationStore:
    def _make_store(self) -> TranslationStore:
        store = TranslationStore()
        store.add(TranslationEntry("greeting", Locale.JA, "こんにちは"))
        store.add(TranslationEntry("greeting", Locale.EN, "Hello"))
        store.add(TranslationEntry("farewell", Locale.JA, "さようなら"))
        return store

    def test_add_and_get(self):
        store = self._make_store()
        assert store.get("greeting", Locale.JA) == "こんにちは"
        assert store.get("greeting", Locale.EN) == "Hello"

    def test_get_missing(self):
        store = self._make_store()
        assert store.get("greeting", Locale.ZH) is None

    def test_get_or_default(self):
        store = self._make_store()
        assert store.get_or_default(
            "missing", Locale.JA, "fallback",
        ) == "fallback"

    def test_get_or_default_found(self):
        store = self._make_store()
        assert store.get_or_default(
            "greeting", Locale.JA, "fallback",
        ) == "こんにちは"

    def test_list_keys_all(self):
        store = self._make_store()
        keys = store.list_keys()
        assert keys == ["farewell", "greeting"]

    def test_list_keys_by_locale(self):
        store = self._make_store()
        keys = store.list_keys(locale=Locale.EN)
        assert keys == ["greeting"]

    def test_list_locales(self):
        store = self._make_store()
        locales = store.list_locales()
        assert Locale.JA in locales
        assert Locale.EN in locales

    def test_count(self):
        store = self._make_store()
        assert store.count == 3

    def test_overwrite_entry(self):
        store = TranslationStore()
        store.add(TranslationEntry("key", Locale.JA, "old"))
        store.add(TranslationEntry("key", Locale.JA, "new"))
        assert store.get("key", Locale.JA) == "new"
        assert store.count == 1


# ============================================================
# テスト: LocaleResolver
# ============================================================


class TestLocaleResolver:
    def test_default_is_ja(self):
        resolver = LocaleResolver()
        assert resolver.get_default() == Locale.JA

    def test_set_default(self):
        resolver = LocaleResolver()
        resolver.set_default(Locale.EN)
        assert resolver.get_default() == Locale.EN

    def test_resolve_with_preferred(self):
        resolver = LocaleResolver()
        assert resolver.resolve(Locale.KO) == Locale.KO

    def test_resolve_without_preferred(self):
        resolver = LocaleResolver()
        resolver.set_default(Locale.ZH)
        assert resolver.resolve(None) == Locale.ZH

    def test_resolve_none_uses_default(self):
        resolver = LocaleResolver()
        assert resolver.resolve() == Locale.JA


# ============================================================
# テスト: PromptLocalizer
# ============================================================


class TestPromptLocalizer:
    def _make_localizer(self) -> PromptLocalizer:
        store = TranslationStore()
        store.add(TranslationEntry("role", Locale.JA, "レビュアー"))
        store.add(TranslationEntry("role", Locale.EN, "Reviewer"))
        store.add(TranslationEntry("action", Locale.JA, "確認"))
        localizer = PromptLocalizer()
        localizer.set_translations(store)
        return localizer

    def test_localize_from_store(self):
        loc = self._make_localizer()
        result = loc.localize_prompt(
            "あなたは{role}です", Locale.JA,
        )
        assert result == "あなたはレビュアーです"

    def test_localize_from_context(self):
        loc = self._make_localizer()
        result = loc.localize_prompt(
            "Hello {name}", Locale.EN, context={"name": "Alice"},
        )
        assert result == "Hello Alice"

    def test_localize_context_overrides_store(self):
        loc = self._make_localizer()
        result = loc.localize_prompt(
            "{role}として{action}",
            Locale.JA,
            context={"role": "管理者"},
        )
        assert result == "管理者として確認"

    def test_localize_unresolved_key_remains(self):
        loc = self._make_localizer()
        result = loc.localize_prompt(
            "{unknown}テスト", Locale.JA,
        )
        assert result == "{unknown}テスト"

    def test_localize_without_store(self):
        loc = PromptLocalizer()
        result = loc.localize_prompt(
            "{key}value", Locale.EN,
        )
        assert result == "{key}value"


# ============================================================
# テスト: GlossaryTranslator
# ============================================================


class TestGlossaryTranslator:
    def test_add_and_translate(self):
        gt = GlossaryTranslator()
        gt.add_term("PDCA", Locale.JA, "PDCAサイクル")
        assert gt.translate_term("PDCA", Locale.JA) == "PDCAサイクル"

    def test_translate_missing(self):
        gt = GlossaryTranslator()
        assert gt.translate_term("PDCA", Locale.EN) is None

    def test_list_terms(self):
        gt = GlossaryTranslator()
        gt.add_term("alpha", Locale.JA, "アルファ")
        gt.add_term("beta", Locale.JA, "ベータ")
        gt.add_term("gamma", Locale.EN, "Gamma")
        terms = gt.list_terms(Locale.JA)
        assert terms == ["alpha", "beta"]

    def test_list_terms_empty(self):
        gt = GlossaryTranslator()
        assert gt.list_terms(Locale.KO) == []
