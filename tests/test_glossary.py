"""用語集管理基盤のユニットテスト。

M1 タスク 1-9: 用語CRUD・変更履歴のテスト。
"""

import pytest

from vibe_pdca.glossary import GlossaryManager


@pytest.fixture
def manager():
    return GlossaryManager()


class TestGlossaryAdd:
    def test_add_term(self, manager):
        entry = manager.add("PDCA", "Plan-Do-Check-Actサイクル", actor="owner")
        assert entry.term == "PDCA"
        assert entry.definition == "Plan-Do-Check-Actサイクル"
        assert manager.entry_count == 1

    def test_add_with_aliases(self, manager):
        entry = manager.add(
            "DoD",
            "Definition of Done。機械判定可能な達成条件",
            aliases=["Definition of Done", "達成条件"],
        )
        assert len(entry.aliases) == 2

    def test_add_duplicate_raises(self, manager):
        manager.add("PDCA", "定義1")
        with pytest.raises(ValueError, match="既に登録"):
            manager.add("PDCA", "定義2")

    def test_add_records_history(self, manager):
        entry = manager.add("PDCA", "定義", actor="owner")
        assert len(entry.history) == 1
        assert entry.history[0].action == "create"
        assert entry.history[0].actor == "owner"


class TestGlossaryGet:
    def test_get_by_term(self, manager):
        manager.add("PDCA", "サイクル定義")
        entry = manager.get("PDCA")
        assert entry is not None
        assert entry.definition == "サイクル定義"

    def test_get_by_alias(self, manager):
        manager.add("DoD", "達成条件", aliases=["Definition of Done"])
        entry = manager.get("Definition of Done")
        assert entry is not None
        assert entry.term == "DoD"

    def test_get_nonexistent(self, manager):
        assert manager.get("存在しない用語") is None

    def test_get_with_whitespace(self, manager):
        manager.add("PDCA", "定義")
        assert manager.get("  PDCA  ") is not None


class TestGlossaryUpdate:
    def test_update_definition(self, manager):
        manager.add("PDCA", "旧定義", actor="owner")
        entry = manager.update("PDCA", "新定義", actor="maintainer")
        assert entry.definition == "新定義"

    def test_update_records_history(self, manager):
        manager.add("PDCA", "旧定義", actor="owner")
        entry = manager.update("PDCA", "新定義", actor="maintainer")
        assert len(entry.history) == 2
        assert entry.history[1].action == "update"
        assert entry.history[1].old_definition == "旧定義"
        assert entry.history[1].new_definition == "新定義"

    def test_update_nonexistent_raises(self, manager):
        with pytest.raises(KeyError, match="見つかりません"):
            manager.update("存在しない", "定義")


class TestGlossaryDelete:
    def test_delete_term(self, manager):
        manager.add("PDCA", "定義")
        deleted = manager.delete("PDCA", actor="owner")
        assert deleted.term == "PDCA"
        assert manager.entry_count == 0

    def test_delete_records_history(self, manager):
        manager.add("PDCA", "定義")
        deleted = manager.delete("PDCA", actor="owner")
        assert deleted.history[-1].action == "delete"

    def test_delete_nonexistent_raises(self, manager):
        with pytest.raises(KeyError, match="見つかりません"):
            manager.delete("存在しない")


class TestGlossarySearch:
    def test_search_by_term(self, manager):
        manager.add("PDCA", "Plan-Do-Check-Actサイクル")
        manager.add("DoD", "Definition of Done")
        results = manager.search("PDCA")
        assert len(results) == 1
        assert results[0].term == "PDCA"

    def test_search_by_definition(self, manager):
        manager.add("PDCA", "Plan-Do-Check-Actサイクル")
        results = manager.search("サイクル")
        assert len(results) == 1

    def test_search_by_alias(self, manager):
        manager.add("DoD", "達成条件", aliases=["Definition of Done"])
        results = manager.search("Definition")
        assert len(results) == 1

    def test_search_case_insensitive(self, manager):
        manager.add("PDCA", "定義")
        results = manager.search("pdca")
        assert len(results) == 1


class TestGlossaryExport:
    def test_list_all(self, manager):
        manager.add("PDCA", "定義1")
        manager.add("DoD", "定義2")
        all_entries = manager.list_all()
        assert len(all_entries) == 2

    def test_export(self, manager):
        manager.add("PDCA", "定義")
        exported = manager.export()
        assert len(exported) == 1
        assert exported[0]["term"] == "PDCA"
        assert isinstance(exported[0], dict)
