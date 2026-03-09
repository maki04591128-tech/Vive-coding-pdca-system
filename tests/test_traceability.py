"""トレーサビリティ基盤のユニットテスト。

M1 タスク 1-7: TraceLink双方向追跡のテスト。
"""

import pytest

from vibe_pdca.monitoring import TraceLinkManager


@pytest.fixture
def manager():
    return TraceLinkManager()


class TestTraceLinkAdd:
    def test_add_single_link(self, manager):
        link = manager.add_link("goal", "G-001", "milestone", "M-001", "has_milestone")
        assert link.source_type == "goal"
        assert link.target_type == "milestone"
        assert link.relationship == "has_milestone"
        assert manager.link_count == 1

    def test_add_multiple_links(self, manager):
        manager.add_link("goal", "G-001", "milestone", "M-001")
        manager.add_link("milestone", "M-001", "task", "T-001")
        manager.add_link("task", "T-001", "pr", "PR-42")
        assert manager.link_count == 3


class TestForwardLinks:
    def test_get_forward_links(self, manager):
        manager.add_link("goal", "G-001", "milestone", "M-001")
        manager.add_link("goal", "G-001", "milestone", "M-002")
        links = manager.get_forward_links("goal", "G-001")
        assert len(links) == 2
        assert all(link.source_id == "G-001" for link in links)

    def test_no_forward_links(self, manager):
        links = manager.get_forward_links("goal", "nonexistent")
        assert links == []


class TestBackwardLinks:
    def test_get_backward_links(self, manager):
        manager.add_link("milestone", "M-001", "task", "T-001")
        manager.add_link("milestone", "M-001", "task", "T-002")
        links = manager.get_backward_links("task", "T-001")
        assert len(links) == 1
        assert links[0].source_id == "M-001"

    def test_multiple_backward_links(self, manager):
        manager.add_link("task", "T-001", "pr", "PR-1")
        manager.add_link("task", "T-002", "pr", "PR-1")
        links = manager.get_backward_links("pr", "PR-1")
        assert len(links) == 2


class TestBidirectionalSearch:
    def test_get_all_related(self, manager):
        manager.add_link("milestone", "M-001", "task", "T-001")
        manager.add_link("goal", "G-001", "milestone", "M-001")
        related = manager.get_all_related("milestone", "M-001")
        assert len(related) == 2  # 1 forward + 1 backward


class TestTraceChain:
    def test_simple_chain(self, manager):
        manager.add_link("goal", "G-001", "milestone", "M-001")
        manager.add_link("milestone", "M-001", "task", "T-001")
        manager.add_link("task", "T-001", "pr", "PR-42")

        chain = manager.trace_chain("goal", "G-001")
        assert len(chain) == 3
        assert chain[0].source_type == "goal"
        assert chain[-1].target_type == "pr"

    def test_chain_max_depth(self, manager):
        manager.add_link("goal", "1", "milestone", "2")
        manager.add_link("milestone", "2", "task", "3")
        manager.add_link("task", "3", "pr", "4")

        chain = manager.trace_chain("goal", "1", max_depth=2)
        assert len(chain) == 2  # depth制限で3番目は含まれない
        assert chain[0].source_type == "goal"
        assert chain[0].target_type == "milestone"
        assert chain[1].source_type == "milestone"
        assert chain[1].target_type == "task"

    def test_chain_no_cycle(self, manager):
        """循環参照でも無限ループしないこと。"""
        manager.add_link("goal", "1", "milestone", "2")
        manager.add_link("milestone", "2", "goal", "1")
        chain = manager.trace_chain("goal", "1", max_depth=10)
        assert len(chain) == 2  # visitedで打ち切り
        assert chain[0].source_type == "goal"
        assert chain[0].target_type == "milestone"
        assert chain[1].source_type == "milestone"
        assert chain[1].target_type == "goal"


class TestValidation:
    def test_invalid_source_type_raises(self, manager):
        with pytest.raises(ValueError, match="無効なリソース種別"):
            manager.add_link("invalid_type", "1", "goal", "2")

    def test_invalid_target_type_raises(self, manager):
        with pytest.raises(ValueError, match="無効なリソース種別"):
            manager.add_link("goal", "1", "unknown", "2")


class TestExport:
    def test_export(self, manager):
        manager.add_link("goal", "G-001", "milestone", "M-001")
        exported = manager.export()
        assert len(exported) == 1
        assert exported[0]["source_type"] == "goal"
        assert isinstance(exported[0], dict)
