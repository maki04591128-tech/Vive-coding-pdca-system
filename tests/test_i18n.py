"""国際化（i18n）サポートのテスト。"""

from pathlib import Path

import pytest

from vibe_pdca.engine.i18n import (
    GlossaryTranslator,
    Locale,
    LocaleResolver,
    PromptLocalizer,
    TranslationEntry,
    TranslationStore,
    _flatten_dict,
    load_messages_dir,
    load_messages_from_yaml,
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


# ============================================================
# テスト: _flatten_dict
# ============================================================


class TestFlattenDict:
    def test_flat_dict(self):
        result = _flatten_dict({"a": "1", "b": "2"})
        assert result == {"a": "1", "b": "2"}

    def test_nested_dict(self):
        result = _flatten_dict({"x": {"y": {"z": "deep"}}})
        assert result == {"x.y.z": "deep"}

    def test_mixed_dict(self):
        result = _flatten_dict({
            "pdca": {"phase": {"plan": "計画", "do": "実行"}},
            "top": "value",
        })
        assert result == {
            "pdca.phase.plan": "計画",
            "pdca.phase.do": "実行",
            "top": "value",
        }

    def test_empty_dict(self):
        result = _flatten_dict({})
        assert result == {}


# ============================================================
# テスト: load_messages_from_yaml
# ============================================================


class TestLoadMessagesFromYaml:
    def test_load_ja_catalog(self, tmp_path: Path):
        yml = tmp_path / "test_ja.yml"
        yml.write_text(
            "pdca:\n  phase:\n    plan: 計画\n    do: 実行\n",
            encoding="utf-8",
        )
        store = load_messages_from_yaml(yml, Locale.JA)
        assert store.get("pdca.phase.plan", Locale.JA) == "計画"
        assert store.get("pdca.phase.do", Locale.JA) == "実行"
        assert store.count == 2

    def test_load_en_catalog(self, tmp_path: Path):
        yml = tmp_path / "test_en.yml"
        yml.write_text(
            "pdca:\n  phase:\n    plan: Plan\n    do: Do\n",
            encoding="utf-8",
        )
        store = load_messages_from_yaml(yml, Locale.EN)
        assert store.get("pdca.phase.plan", Locale.EN) == "Plan"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_messages_from_yaml("/nonexistent/path.yml", Locale.JA)

    def test_invalid_format(self, tmp_path: Path):
        yml = tmp_path / "bad.yml"
        yml.write_text("- list\n- items\n", encoding="utf-8")
        with pytest.raises(ValueError, match="辞書が必要"):
            load_messages_from_yaml(yml, Locale.JA)

    def test_real_ja_catalog(self):
        """config/i18n/messages_ja.yml が正しく読み込めること。"""
        catalog_path = (
            Path(__file__).parent.parent / "config" / "i18n" / "messages_ja.yml"
        )
        if not catalog_path.exists():
            pytest.skip("messages_ja.yml が存在しません")
        store = load_messages_from_yaml(catalog_path, Locale.JA)
        assert store.count > 0
        assert store.get("pdca.phase.plan", Locale.JA) == "計画"
        assert store.get("persona.pm", Locale.JA) == "プロジェクトマネージャー"

    def test_real_en_catalog(self):
        """config/i18n/messages_en.yml が正しく読み込めること。"""
        catalog_path = (
            Path(__file__).parent.parent / "config" / "i18n" / "messages_en.yml"
        )
        if not catalog_path.exists():
            pytest.skip("messages_en.yml が存在しません")
        store = load_messages_from_yaml(catalog_path, Locale.EN)
        assert store.count > 0
        assert store.get("pdca.phase.plan", Locale.EN) == "Plan"
        assert store.get("persona.pm", Locale.EN) == "Project Manager"


# ============================================================
# テスト: load_messages_dir
# ============================================================


class TestLoadMessagesDir:
    def test_load_dir(self, tmp_path: Path):
        (tmp_path / "messages_ja.yml").write_text(
            "greeting: こんにちは\nfarewell: さようなら\n",
            encoding="utf-8",
        )
        (tmp_path / "messages_en.yml").write_text(
            "greeting: Hello\nfarewell: Goodbye\n",
            encoding="utf-8",
        )
        store = load_messages_dir(tmp_path)
        assert store.get("greeting", Locale.JA) == "こんにちは"
        assert store.get("greeting", Locale.EN) == "Hello"
        assert store.get("farewell", Locale.JA) == "さようなら"
        assert store.get("farewell", Locale.EN) == "Goodbye"
        assert store.count == 4

    def test_dir_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_messages_dir("/nonexistent/dir")

    def test_skip_unsupported_locale(self, tmp_path: Path):
        (tmp_path / "messages_fr.yml").write_text(
            "greeting: Bonjour\n", encoding="utf-8",
        )
        store = load_messages_dir(tmp_path)
        assert store.count == 0

    def test_skip_malformed_file(self, tmp_path: Path):
        (tmp_path / "messages_ja.yml").write_text(
            "- list\n- items\n", encoding="utf-8",
        )
        store = load_messages_dir(tmp_path)
        assert store.count == 0

    def test_real_i18n_dir(self):
        """config/i18n/ ディレクトリが正しく読み込めること。"""
        dir_path = (
            Path(__file__).parent.parent / "config" / "i18n"
        )
        if not dir_path.is_dir():
            pytest.skip("config/i18n/ が存在しません")
        store = load_messages_dir(dir_path)
        # JA + EN の両カタログが読み込まれていること
        locales = store.list_locales()
        assert Locale.JA in locales
        assert Locale.EN in locales
        # 各ロケールにエントリが存在すること
        ja_keys = store.list_keys(Locale.JA)
        en_keys = store.list_keys(Locale.EN)
        assert len(ja_keys) > 0
        assert len(en_keys) > 0


class TestTranslationStoreBarrierThreadSafety:
    """TranslationStoreのBarrierスレッドセーフティテスト。"""

    def test_concurrent_add(self) -> None:
        import threading

        store = TranslationStore()
        n_threads = 10
        ops_per_thread = 50
        barrier = threading.Barrier(n_threads)

        def worker(tid: int) -> None:
            barrier.wait()
            for i in range(ops_per_thread):
                entry = TranslationEntry(
                    key=f"key-{tid}-{i}",
                    locale=Locale.JA,
                    value=f"value-{tid}-{i}",
                )
                store.add(entry)

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert store.count == n_threads * ops_per_thread
