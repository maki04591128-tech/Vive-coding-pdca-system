"""タスク依存関係グラフとクリティカルパス分析のテスト。"""

import pytest

from vibe_pdca.engine.task_dependency import (
    BlockerDetector,
    BlockerWarning,
    CriticalPath,
    CriticalPathAnalyzer,
    DependencyGraph,
    TaskNode,
)

# ============================================================
# テスト: TaskNode
# ============================================================


class TestTaskNode:
    def test_default_values(self):
        node = TaskNode(task_id="t1", title="タスク1")
        assert node.task_id == "t1"
        assert node.title == "タスク1"
        assert node.estimated_duration == 3600.0
        assert node.dependencies == []
        assert node.status == "pending"

    def test_custom_values(self):
        node = TaskNode(
            task_id="t2",
            title="タスク2",
            estimated_duration=7200.0,
            dependencies=["t1"],
            status="in_progress",
        )
        assert node.task_id == "t2"
        assert node.estimated_duration == 7200.0
        assert node.dependencies == ["t1"]
        assert node.status == "in_progress"


# ============================================================
# テスト: CriticalPath
# ============================================================


class TestCriticalPath:
    def test_creation(self):
        cp = CriticalPath(
            path=["t1", "t2", "t3"],
            total_duration=10800.0,
            bottleneck_task_id="t2",
        )
        assert cp.path == ["t1", "t2", "t3"]
        assert cp.total_duration == 10800.0
        assert cp.bottleneck_task_id == "t2"


# ============================================================
# テスト: BlockerWarning
# ============================================================


class TestBlockerWarning:
    def test_creation(self):
        bw = BlockerWarning(
            task_id="t1",
            blocked_count=3,
            description="テスト警告",
        )
        assert bw.task_id == "t1"
        assert bw.blocked_count == 3
        assert bw.description == "テスト警告"


# ============================================================
# テスト: DependencyGraph
# ============================================================


class TestDependencyGraph:
    def _make_graph(self) -> DependencyGraph:
        """テスト用のシンプルなグラフを構築する。

        t1 → t2 → t4
        t1 → t3 → t4
        """
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="タスク1"))
        g.add_task(TaskNode(task_id="t2", title="タスク2", dependencies=["t1"]))
        g.add_task(TaskNode(task_id="t3", title="タスク3", dependencies=["t1"]))
        g.add_task(TaskNode(task_id="t4", title="タスク4", dependencies=["t2", "t3"]))
        return g

    def test_add_task(self):
        g = DependencyGraph()
        node = TaskNode(task_id="t1", title="タスク1")
        g.add_task(node)
        assert "t1" in g.nodes
        assert g.nodes["t1"].title == "タスク1"

    def test_add_duplicate_task_ignored(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="タスク1"))
        g.add_task(TaskNode(task_id="t1", title="重複タスク"))
        assert g.nodes["t1"].title == "タスク1"

    def test_add_dependency(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="タスク1"))
        g.add_task(TaskNode(task_id="t2", title="タスク2"))
        g.add_dependency("t2", "t1")
        assert "t1" in g.get_dependencies("t2")
        assert "t2" in g.get_dependents("t1")

    def test_get_dependencies(self):
        g = self._make_graph()
        assert g.get_dependencies("t4") == ["t2", "t3"]
        assert g.get_dependencies("t1") == []

    def test_get_dependents(self):
        g = self._make_graph()
        assert g.get_dependents("t1") == ["t2", "t3"]
        assert g.get_dependents("t4") == []

    def test_get_dependencies_unknown_task(self):
        g = DependencyGraph()
        assert g.get_dependencies("unknown") == []

    def test_get_dependents_unknown_task(self):
        g = DependencyGraph()
        assert g.get_dependents("unknown") == []

    def test_execution_order_simple(self):
        g = self._make_graph()
        order = g.get_execution_order()
        assert order.index("t1") < order.index("t2")
        assert order.index("t1") < order.index("t3")
        assert order.index("t2") < order.index("t4")
        assert order.index("t3") < order.index("t4")

    def test_execution_order_single_task(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="単独タスク"))
        assert g.get_execution_order() == ["t1"]

    def test_execution_order_no_dependencies(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="タスク1"))
        g.add_task(TaskNode(task_id="t2", title="タスク2"))
        g.add_task(TaskNode(task_id="t3", title="タスク3"))
        order = g.get_execution_order()
        assert len(order) == 3
        assert set(order) == {"t1", "t2", "t3"}

    def test_execution_order_circular_raises(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="タスク1"))
        g.add_task(TaskNode(task_id="t2", title="タスク2"))
        g.add_dependency("t1", "t2")
        g.add_dependency("t2", "t1")
        with pytest.raises(ValueError, match="循環依存"):
            g.get_execution_order()

    def test_validate_clean_graph(self):
        g = self._make_graph()
        errors = g.validate()
        assert errors == []

    def test_validate_missing_dependency(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="タスク1", dependencies=["missing"]))
        errors = g.validate()
        assert any("未登録" in e for e in errors)

    def test_validate_circular_dependency(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="タスク1"))
        g.add_task(TaskNode(task_id="t2", title="タスク2"))
        g.add_dependency("t1", "t2")
        g.add_dependency("t2", "t1")
        errors = g.validate()
        assert any("循環依存" in e for e in errors)

    def test_validate_self_dependency(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="タスク1"))
        g.add_dependency("t1", "t1")
        errors = g.validate()
        assert any("自己依存" in e for e in errors)

    def test_parallel_groups(self):
        g = self._make_graph()
        groups = g.get_parallel_groups()
        assert len(groups) == 3
        assert groups[0] == ["t1"]
        assert sorted(groups[1]) == ["t2", "t3"]
        assert groups[2] == ["t4"]

    def test_parallel_groups_empty_graph(self):
        g = DependencyGraph()
        assert g.get_parallel_groups() == []

    def test_parallel_groups_independent_tasks(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="a", title="A"))
        g.add_task(TaskNode(task_id="b", title="B"))
        g.add_task(TaskNode(task_id="c", title="C"))
        groups = g.get_parallel_groups()
        assert len(groups) == 1
        assert sorted(groups[0]) == ["a", "b", "c"]

    def test_nodes_property_returns_copy(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="タスク1"))
        nodes = g.nodes
        nodes["t99"] = TaskNode(task_id="t99", title="侵入")
        assert "t99" not in g.nodes


# ============================================================
# テスト: CriticalPathAnalyzer
# ============================================================


class TestCriticalPathAnalyzer:
    def _make_graph(self) -> DependencyGraph:
        """テスト用グラフ:
        t1(1h) → t2(2h) → t4(1h)
        t1(1h) → t3(0.5h) → t4(1h)

        クリティカルパス: t1 → t2 → t4 = 4h
        """
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="タスク1", estimated_duration=3600))
        g.add_task(TaskNode(
            task_id="t2", title="タスク2", estimated_duration=7200, dependencies=["t1"],
        ))
        g.add_task(TaskNode(
            task_id="t3", title="タスク3", estimated_duration=1800, dependencies=["t1"],
        ))
        g.add_task(TaskNode(
            task_id="t4", title="タスク4", estimated_duration=3600, dependencies=["t2", "t3"],
        ))
        return g

    def test_find_critical_path(self):
        g = self._make_graph()
        analyzer = CriticalPathAnalyzer(g)
        cp = analyzer.find_critical_path()
        assert cp.path == ["t1", "t2", "t4"]
        assert cp.total_duration == 3600 + 7200 + 3600  # 14400秒 = 4時間
        assert cp.bottleneck_task_id == "t2"

    def test_find_critical_path_empty_graph(self):
        g = DependencyGraph()
        analyzer = CriticalPathAnalyzer(g)
        cp = analyzer.find_critical_path()
        assert cp.path == []
        assert cp.total_duration == 0.0
        assert cp.bottleneck_task_id == ""

    def test_find_critical_path_single_task(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="単独", estimated_duration=5000))
        analyzer = CriticalPathAnalyzer(g)
        cp = analyzer.find_critical_path()
        assert cp.path == ["t1"]
        assert cp.total_duration == 5000.0
        assert cp.bottleneck_task_id == "t1"

    def test_find_critical_path_linear_chain(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="a", title="A", estimated_duration=100))
        g.add_task(TaskNode(task_id="b", title="B", estimated_duration=200, dependencies=["a"]))
        g.add_task(TaskNode(task_id="c", title="C", estimated_duration=300, dependencies=["b"]))
        analyzer = CriticalPathAnalyzer(g)
        cp = analyzer.find_critical_path()
        assert cp.path == ["a", "b", "c"]
        assert cp.total_duration == 600.0
        assert cp.bottleneck_task_id == "c"

    def test_estimate_total_duration(self):
        g = self._make_graph()
        analyzer = CriticalPathAnalyzer(g)
        assert analyzer.estimate_total_duration() == 14400.0

    def test_find_blockers(self):
        g = self._make_graph()
        analyzer = CriticalPathAnalyzer(g)
        blockers = analyzer.find_blockers()
        # t1 は t2, t3 をブロック (2件)
        # t2 は t4 をブロック (1件)
        # t3 は t4 をブロック (1件)
        assert blockers[0] == "t1"
        assert len(blockers) == 3  # t1, t2, t3 (各1件以上)

    def test_find_blockers_empty_graph(self):
        g = DependencyGraph()
        analyzer = CriticalPathAnalyzer(g)
        assert analyzer.find_blockers() == []

    def test_find_blockers_no_dependencies(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="独立1"))
        g.add_task(TaskNode(task_id="t2", title="独立2"))
        analyzer = CriticalPathAnalyzer(g)
        assert analyzer.find_blockers() == []


# ============================================================
# テスト: BlockerDetector
# ============================================================


class TestBlockerDetector:
    def test_detect_blockers_above_threshold(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="base", title="基盤タスク"))
        g.add_task(TaskNode(task_id="d1", title="依存1", dependencies=["base"]))
        g.add_task(TaskNode(task_id="d2", title="依存2", dependencies=["base"]))
        g.add_task(TaskNode(task_id="d3", title="依存3", dependencies=["base"]))
        detector = BlockerDetector(g)
        warnings = detector.detect_blockers(threshold=2)
        assert len(warnings) == 1
        assert warnings[0].task_id == "base"
        assert warnings[0].blocked_count == 3

    def test_detect_blockers_below_threshold(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="t1", title="タスク1"))
        g.add_task(TaskNode(task_id="t2", title="タスク2", dependencies=["t1"]))
        detector = BlockerDetector(g)
        warnings = detector.detect_blockers(threshold=2)
        assert warnings == []

    def test_detect_blockers_empty_graph(self):
        g = DependencyGraph()
        detector = BlockerDetector(g)
        assert detector.detect_blockers() == []

    def test_detect_blockers_custom_threshold(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="base", title="基盤"))
        g.add_task(TaskNode(task_id="d1", title="依存1", dependencies=["base"]))
        g.add_task(TaskNode(task_id="d2", title="依存2", dependencies=["base"]))
        detector = BlockerDetector(g)
        # threshold=3 → ブロック数2では検出されない
        assert detector.detect_blockers(threshold=3) == []
        # threshold=1 → 検出される
        warnings = detector.detect_blockers(threshold=1)
        assert len(warnings) == 1

    def test_detect_blockers_multiple_blockers_sorted(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="a", title="A"))
        g.add_task(TaskNode(task_id="b", title="B"))
        g.add_task(TaskNode(task_id="c1", title="C1", dependencies=["a", "b"]))
        g.add_task(TaskNode(task_id="c2", title="C2", dependencies=["a", "b"]))
        g.add_task(TaskNode(task_id="c3", title="C3", dependencies=["a"]))
        detector = BlockerDetector(g)
        warnings = detector.detect_blockers(threshold=2)
        assert len(warnings) == 2
        # a blocks 3, b blocks 2
        assert warnings[0].task_id == "a"
        assert warnings[0].blocked_count == 3
        assert warnings[1].task_id == "b"
        assert warnings[1].blocked_count == 2

    def test_detect_blockers_warning_description(self):
        g = DependencyGraph()
        g.add_task(TaskNode(task_id="core", title="コアモジュール"))
        g.add_task(TaskNode(task_id="d1", title="派生1", dependencies=["core"]))
        g.add_task(TaskNode(task_id="d2", title="派生2", dependencies=["core"]))
        detector = BlockerDetector(g)
        warnings = detector.detect_blockers(threshold=2)
        assert len(warnings) == 1
        assert "コアモジュール" in warnings[0].description
        assert "core" in warnings[0].description
        assert "2" in warnings[0].description
