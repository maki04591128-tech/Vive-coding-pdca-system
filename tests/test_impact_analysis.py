"""Proposal 23: Change Impact Analysis のテスト。"""

from __future__ import annotations

from vibe_pdca.engine.impact_analysis import (
    BreakingChangeDetector,
    DependencyInfo,
    FileChange,
    ImpactAnalyzer,
    ImpactScore,
    StaticDependencyAnalyzer,
    TestTargetFinder,
)

# ============================================================
# FileChange dataclass
# ============================================================


class TestFileChange:
    """FileChange データクラスのテスト。"""

    def test_defaults(self) -> None:
        fc = FileChange(file_path="a.py", change_type="added")
        assert fc.file_path == "a.py"
        assert fc.change_type == "added"
        assert fc.lines_changed == 0

    def test_with_lines(self) -> None:
        fc = FileChange(file_path="b.py", change_type="modified", lines_changed=42)
        assert fc.lines_changed == 42


# ============================================================
# DependencyInfo dataclass
# ============================================================


class TestDependencyInfo:
    """DependencyInfo データクラスのテスト。"""

    def test_defaults(self) -> None:
        di = DependencyInfo(file_path="x.py")
        assert di.imports == []
        assert di.imported_by == []

    def test_with_values(self) -> None:
        di = DependencyInfo(
            file_path="x.py",
            imports=["os", "sys"],
            imported_by=["main.py"],
        )
        assert len(di.imports) == 2
        assert "main.py" in di.imported_by


# ============================================================
# ImpactScore dataclass
# ============================================================


class TestImpactScore:
    """ImpactScore データクラスのテスト。"""

    def test_defaults(self) -> None:
        score = ImpactScore(score=0.5)
        assert score.score == 0.5
        assert score.affected_files == []
        assert score.affected_tests == []
        assert score.breaking_changes == []
        assert score.description == ""


# ============================================================
# StaticDependencyAnalyzer
# ============================================================


class TestStaticDependencyAnalyzer:
    """StaticDependencyAnalyzer のテスト。"""

    def setup_method(self) -> None:
        self.analyzer = StaticDependencyAnalyzer()

    def test_analyze_imports_simple(self) -> None:
        content = "import os\nimport sys\n"
        result = self.analyzer.analyze_imports("test.py", content)
        assert "os" in result
        assert "sys" in result

    def test_analyze_imports_from(self) -> None:
        content = "from os.path import join\nfrom sys import argv\n"
        result = self.analyzer.analyze_imports("test.py", content)
        assert "os.path" in result
        assert "sys" in result

    def test_analyze_imports_syntax_error(self) -> None:
        content = "def broken(\n"
        result = self.analyzer.analyze_imports("bad.py", content)
        assert result == []

    def test_analyze_imports_empty(self) -> None:
        result = self.analyzer.analyze_imports("empty.py", "")
        assert result == []

    def test_analyze_imports_mixed(self) -> None:
        content = "import json\nfrom pathlib import Path\nx = 1\n"
        result = self.analyzer.analyze_imports("mix.py", content)
        assert "json" in result
        assert "pathlib" in result
        assert len(result) == 2

    def test_build_dependency_map_basic(self) -> None:
        files = {
            "pkg/a.py": "import os\n",
            "pkg/b.py": "import pkg.a\n",
        }
        dep_map = self.analyzer.build_dependency_map(files)
        assert "pkg/a.py" in dep_map
        assert "pkg/b.py" in dep_map
        assert "pkg/b.py" in dep_map["pkg/a.py"].imported_by

    def test_build_dependency_map_empty(self) -> None:
        dep_map = self.analyzer.build_dependency_map({})
        assert dep_map == {}

    def test_find_affected_files_direct(self) -> None:
        dep_map = {
            "a.py": DependencyInfo(file_path="a.py", imported_by=["b.py"]),
            "b.py": DependencyInfo(file_path="b.py"),
        }
        affected = self.analyzer.find_affected_files(["a.py"], dep_map)
        assert "b.py" in affected
        assert "a.py" not in affected

    def test_find_affected_files_transitive(self) -> None:
        dep_map = {
            "a.py": DependencyInfo(file_path="a.py", imported_by=["b.py"]),
            "b.py": DependencyInfo(file_path="b.py", imported_by=["c.py"]),
            "c.py": DependencyInfo(file_path="c.py"),
        }
        affected = self.analyzer.find_affected_files(["a.py"], dep_map)
        assert "b.py" in affected
        assert "c.py" in affected

    def test_find_affected_files_no_deps(self) -> None:
        dep_map = {
            "a.py": DependencyInfo(file_path="a.py"),
        }
        affected = self.analyzer.find_affected_files(["a.py"], dep_map)
        assert affected == []

    def test_module_matches_file(self) -> None:
        assert StaticDependencyAnalyzer._module_matches_file(
            "pkg.module", "src/pkg/module.py"
        )
        assert not StaticDependencyAnalyzer._module_matches_file(
            "pkg.other", "src/pkg/module.py"
        )


# ============================================================
# BreakingChangeDetector
# ============================================================


class TestBreakingChangeDetector:
    """BreakingChangeDetector のテスト。"""

    def setup_method(self) -> None:
        self.detector = BreakingChangeDetector()

    def test_detect_removed_function(self) -> None:
        old = "def foo():\n    pass\ndef bar():\n    pass\n"
        new = "def bar():\n    pass\n"
        changes = self.detector.detect_api_changes(old, new)
        assert len(changes) == 1
        assert "foo" in changes[0]

    def test_detect_removed_class(self) -> None:
        old = "class MyClass:\n    pass\n"
        new = ""
        changes = self.detector.detect_api_changes(old, new)
        assert any("MyClass" in c for c in changes)

    def test_no_breaking_changes(self) -> None:
        old = "def foo():\n    pass\n"
        new = "def foo():\n    return 1\n"
        changes = self.detector.detect_api_changes(old, new)
        assert changes == []

    def test_private_removal_not_breaking(self) -> None:
        old = "def _private():\n    pass\n"
        new = ""
        changes = self.detector.detect_api_changes(old, new)
        assert changes == []

    def test_detect_schema_removed_key(self) -> None:
        old = {"host": "localhost", "port": 8080}
        new = {"host": "localhost"}
        changes = self.detector.detect_schema_changes(old, new)
        assert any("port" in c for c in changes)

    def test_detect_schema_added_key(self) -> None:
        old = {"host": "localhost"}
        new = {"host": "localhost", "timeout": 30}
        changes = self.detector.detect_schema_changes(old, new)
        assert any("timeout" in c for c in changes)

    def test_detect_schema_type_change(self) -> None:
        old = {"port": 8080}
        new = {"port": "8080"}
        changes = self.detector.detect_schema_changes(old, new)
        assert len(changes) == 1
        assert "int" in changes[0]
        assert "str" in changes[0]

    def test_detect_schema_no_changes(self) -> None:
        cfg = {"host": "localhost", "port": 8080}
        changes = self.detector.detect_schema_changes(cfg, cfg)
        assert changes == []


# ============================================================
# TestTargetFinder
# ============================================================


class TestTestTargetFinder:
    """TestTargetFinder のテスト。"""

    def setup_method(self) -> None:
        self.finder = TestTargetFinder()

    def test_find_matching_test(self) -> None:
        changed = ["src/module.py"]
        tests = ["tests/test_module.py", "tests/test_other.py"]
        result = self.finder.find_related_tests(changed, tests)
        assert "tests/test_module.py" in result
        assert "tests/test_other.py" not in result

    def test_no_matching_test(self) -> None:
        changed = ["src/unique.py"]
        tests = ["tests/test_other.py"]
        result = self.finder.find_related_tests(changed, tests)
        assert result == []

    def test_multiple_changed_files(self) -> None:
        changed = ["src/foo.py", "src/bar.py"]
        tests = ["tests/test_foo.py", "tests/test_bar.py", "tests/test_baz.py"]
        result = self.finder.find_related_tests(changed, tests)
        assert "tests/test_foo.py" in result
        assert "tests/test_bar.py" in result
        assert "tests/test_baz.py" not in result


# ============================================================
# ImpactAnalyzer
# ============================================================


class TestImpactAnalyzer:
    """ImpactAnalyzer のテスト。"""

    def setup_method(self) -> None:
        self.analyzer = ImpactAnalyzer()

    def test_analyze_empty(self) -> None:
        result = self.analyzer.analyze([], {}, [])
        assert result.score == 0.0
        assert result.affected_files == []

    def test_analyze_single_added(self) -> None:
        changes = [FileChange("src/new.py", "added", 50)]
        contents = {"src/new.py": "x = 1\n"}
        result = self.analyzer.analyze(changes, contents, [])
        assert 0.0 <= result.score <= 1.0

    def test_analyze_deleted_file(self) -> None:
        changes = [FileChange("src/old.py", "deleted")]
        contents: dict[str, str] = {}
        result = self.analyzer.analyze(changes, contents, [])
        assert len(result.breaking_changes) == 1
        assert result.score > 0.0

    def test_analyze_with_tests(self) -> None:
        changes = [FileChange("src/module.py", "modified", 10)]
        contents = {"src/module.py": "def run(): pass\n"}
        tests = ["tests/test_module.py"]
        result = self.analyzer.analyze(changes, contents, tests)
        assert "tests/test_module.py" in result.affected_tests

    def test_generate_report_basic(self) -> None:
        score = ImpactScore(
            score=0.5,
            affected_files=["b.py"],
            affected_tests=["test_a.py"],
            breaking_changes=[],
            description="テスト",
        )
        report = self.analyzer.generate_report(score)
        assert "# 変更影響分析レポート" in report
        assert "0.50" in report
        assert "b.py" in report

    def test_generate_report_with_breaking(self) -> None:
        score = ImpactScore(
            score=0.8,
            affected_files=[],
            affected_tests=[],
            breaking_changes=["関数 foo が削除されました"],
            description="破壊的変更あり",
        )
        report = self.analyzer.generate_report(score)
        assert "⚠️" in report
        assert "foo" in report

    def test_generate_report_empty(self) -> None:
        score = ImpactScore(score=0.0, description="変更なし")
        report = self.analyzer.generate_report(score)
        assert "0.00" in report

    def test_score_level_high(self) -> None:
        score = ImpactScore(score=0.85, description="high")
        report = self.analyzer.generate_report(score)
        assert "高" in report

    def test_score_level_medium(self) -> None:
        score = ImpactScore(score=0.5, description="medium")
        report = self.analyzer.generate_report(score)
        assert "中" in report

    def test_score_level_low(self) -> None:
        score = ImpactScore(score=0.1, description="low")
        report = self.analyzer.generate_report(score)
        assert "低" in report

    def test_score_clamped_to_range(self) -> None:
        """スコアは 0.0 ~ 1.0 の範囲に収まること。"""
        changes = [
            FileChange(f"f{i}.py", "deleted") for i in range(20)
        ]
        result = self.analyzer.analyze(changes, {}, [])
        assert 0.0 <= result.score <= 1.0
