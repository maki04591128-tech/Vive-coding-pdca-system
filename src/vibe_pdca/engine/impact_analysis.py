"""変更影響分析 – 変更ファイルの依存関係・破壊的変更・テスト対象を分析する。

Proposal 23: Change Impact Analysis。

入力: 変更ファイル一覧・ファイル内容・テストファイル一覧
出力: 影響スコア（依存ファイル・テスト対象・破壊的変更・説明を含む）
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# データクラス
# ============================================================


@dataclass
class FileChange:
    """変更ファイル情報。"""

    file_path: str
    change_type: str  # "added", "modified", "deleted"
    lines_changed: int = 0


@dataclass
class DependencyInfo:
    """ファイルの依存関係情報。"""

    file_path: str
    imports: list[str] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)


@dataclass
class ImpactScore:
    """変更影響スコア（Proposal 23）。"""

    score: float  # 0.0 ~ 1.0（高い = 影響大）
    affected_files: list[str] = field(default_factory=list)
    affected_tests: list[str] = field(default_factory=list)
    breaking_changes: list[str] = field(default_factory=list)
    description: str = ""


# ============================================================
# StaticDependencyAnalyzer – 静的依存関係解析
# ============================================================


class StaticDependencyAnalyzer:
    """Python ソースの import 文を静的解析し依存マップを構築する。"""

    def analyze_imports(self, file_path: str, content: str) -> list[str]:
        """ファイル内容から import 文を抽出してモジュール名のリストを返す。

        Parameters
        ----------
        file_path : str
            解析対象のファイルパス。
        content : str
            ファイルの内容。

        Returns
        -------
        list[str]
            インポートされているモジュール名のリスト。
        """
        imports: list[str] = []
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError:
            logger.warning("構文エラーのため解析をスキップ: %s", file_path)
            return imports

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        return imports

    def build_dependency_map(
        self, files: dict[str, str]
    ) -> dict[str, DependencyInfo]:
        """全ファイルの依存マップを構築する。

        Parameters
        ----------
        files : dict[str, str]
            ファイルパス → 内容 の辞書。

        Returns
        -------
        dict[str, DependencyInfo]
            ファイルパス → DependencyInfo の辞書。
        """
        dep_map: dict[str, DependencyInfo] = {}

        for fpath, content in files.items():
            imported_modules = self.analyze_imports(fpath, content)
            dep_map[fpath] = DependencyInfo(
                file_path=fpath,
                imports=imported_modules,
            )

        # imported_by を構築
        for fpath, info in dep_map.items():
            for imp in info.imports:
                for other_path in dep_map:
                    if (
                        self._module_matches_file(imp, other_path)
                        and fpath not in dep_map[other_path].imported_by
                    ):
                        dep_map[other_path].imported_by.append(fpath)
        return dep_map

    def find_affected_files(
        self,
        changed_files: list[str],
        dep_map: dict[str, DependencyInfo],
    ) -> list[str]:
        """変更ファイルから推移的に影響を受けるファイルを全て探索する。

        Parameters
        ----------
        changed_files : list[str]
            変更されたファイル一覧。
        dep_map : dict[str, DependencyInfo]
            依存マップ。

        Returns
        -------
        list[str]
            影響を受けるファイルのリスト（変更ファイル自体は含まない）。
        """
        visited: set[str] = set()
        queue = list(changed_files)

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            if current in dep_map:
                for dependent in dep_map[current].imported_by:
                    if dependent not in visited:
                        queue.append(dependent)

        # 変更ファイル自体は除外
        affected = sorted(visited - set(changed_files))
        return affected

    # ── 内部メソッド ──

    @staticmethod
    def _module_matches_file(module_name: str, file_path: str) -> bool:
        """モジュール名がファイルパスに対応するか判定する。"""
        # "vibe_pdca.engine.decision" → "vibe_pdca/engine/decision"
        module_as_path = module_name.replace(".", "/")
        normalized = file_path.replace("\\", "/")
        # .py 拡張子を除去して比較
        without_ext = normalized.rsplit(".py", 1)[0] if normalized.endswith(".py") else normalized
        return without_ext.endswith(module_as_path)


# ============================================================
# BreakingChangeDetector – 破壊的変更検出
# ============================================================


class BreakingChangeDetector:
    """公開 API やスキーマの破壊的変更を検出する。"""

    _FUNC_RE = re.compile(r"^(?:def|class)\s+([A-Za-z_]\w*)", re.MULTILINE)

    def detect_api_changes(
        self, old_content: str, new_content: str
    ) -> list[str]:
        """旧コードと新コードを比較し、削除・リネームされた公開関数/クラスを検出する。

        Parameters
        ----------
        old_content : str
            変更前のファイル内容。
        new_content : str
            変更後のファイル内容。

        Returns
        -------
        list[str]
            破壊的変更の説明リスト。
        """
        old_names = self._extract_public_names(old_content)
        new_names = self._extract_public_names(new_content)
        removed = old_names - new_names
        changes: list[str] = []
        for name in sorted(removed):
            changes.append(f"公開シンボル '{name}' が削除またはリネームされました")
        if changes:
            logger.info("破壊的変更を %d 件検出", len(changes))
        return changes

    def detect_schema_changes(
        self, old_config: dict[str, Any], new_config: dict[str, Any]
    ) -> list[str]:
        """設定スキーマの差分を検出する。

        Parameters
        ----------
        old_config : dict
            変更前の設定辞書。
        new_config : dict
            変更後の設定辞書。

        Returns
        -------
        list[str]
            スキーマ変更の説明リスト。
        """
        changes: list[str] = []
        removed_keys = set(old_config.keys()) - set(new_config.keys())
        added_keys = set(new_config.keys()) - set(old_config.keys())

        for key in sorted(removed_keys):
            changes.append(f"設定キー '{key}' が削除されました")
        for key in sorted(added_keys):
            changes.append(f"設定キー '{key}' が追加されました")

        # 型変更の検出
        for key in sorted(set(old_config.keys()) & set(new_config.keys())):
            old_type = type(old_config[key]).__name__
            new_type = type(new_config[key]).__name__
            if old_type != new_type:
                changes.append(
                    f"設定キー '{key}' の型が {old_type} → {new_type} に変更されました"
                )
        return changes

    # ── 内部メソッド ──

    def _extract_public_names(self, content: str) -> set[str]:
        """ソースコードから公開関数/クラス名（先頭が _ でないもの）を抽出する。"""
        names: set[str] = set()
        for match in self._FUNC_RE.finditer(content):
            name = match.group(1)
            if not name.startswith("_"):
                names.add(name)
        return names


# ============================================================
# TestTargetFinder – テスト対象特定
# ============================================================


class TestTargetFinder:
    """変更ファイルに対応するテストファイルを特定する。"""

    def find_related_tests(
        self, changed_files: list[str], test_files: list[str]
    ) -> list[str]:
        """命名規約に基づき変更ファイルに対応するテストファイルを返す。

        ``module.py`` に対して ``test_module.py`` を対応させる。

        Parameters
        ----------
        changed_files : list[str]
            変更されたファイルのパス一覧。
        test_files : list[str]
            テストファイルのパス一覧。

        Returns
        -------
        list[str]
            関連するテストファイルのリスト。
        """
        related: list[str] = []
        for changed in changed_files:
            base = self._extract_base_name(changed)
            if not base:
                continue
            for test in test_files:
                test_base = self._extract_base_name(test)
                if not test_base:
                    continue
                # test_foo.py ↔ foo.py
                if (test_base == f"test_{base}" or test_base == base) and test not in related:
                        related.append(test)
        return sorted(related)

    # ── 内部メソッド ──

    @staticmethod
    def _extract_base_name(file_path: str) -> str:
        """ファイルパスから拡張子なしのベース名を取得する。"""
        normalized = file_path.replace("\\", "/")
        name = normalized.rsplit("/", 1)[-1]
        if name.endswith(".py"):
            return name[:-3]
        return name


# ============================================================
# ImpactAnalyzer – メインオーケストレータ
# ============================================================


class ImpactAnalyzer:
    """変更影響分析のメインオーケストレータ（Proposal 23）。

    StaticDependencyAnalyzer, BreakingChangeDetector, TestTargetFinder を
    統合し、総合的な影響スコアを算出する。
    """

    # スコア算出の重み
    _WEIGHT_DELETED = 0.3
    _WEIGHT_AFFECTED = 0.3
    _WEIGHT_BREAKING = 0.3
    _WEIGHT_TESTS = 0.1

    def __init__(
        self,
        dependency_analyzer: StaticDependencyAnalyzer | None = None,
        breaking_change_detector: BreakingChangeDetector | None = None,
        test_finder: TestTargetFinder | None = None,
    ) -> None:
        self._dep_analyzer = dependency_analyzer or StaticDependencyAnalyzer()
        self._breaking_detector = breaking_change_detector or BreakingChangeDetector()
        self._test_finder = test_finder or TestTargetFinder()

    def analyze(
        self,
        changes: list[FileChange],
        file_contents: dict[str, str],
        test_files: list[str],
    ) -> ImpactScore:
        """変更一覧を分析して影響スコアを返す。

        Parameters
        ----------
        changes : list[FileChange]
            変更ファイル情報のリスト。
        file_contents : dict[str, str]
            ファイルパス → 内容 の辞書。
        test_files : list[str]
            テストファイルパスの一覧。

        Returns
        -------
        ImpactScore
            影響スコアおよび詳細情報。
        """
        logger.info("変更影響分析を開始: %d ファイル", len(changes))

        changed_paths = [c.file_path for c in changes]

        # 依存マップ構築と影響ファイル探索
        dep_map = self._dep_analyzer.build_dependency_map(file_contents)
        affected_files = self._dep_analyzer.find_affected_files(
            changed_paths, dep_map
        )

        # 破壊的変更の検出
        breaking_changes: list[str] = []
        for change in changes:
            if change.change_type == "deleted":
                breaking_changes.append(
                    f"ファイル '{change.file_path}' が削除されました"
                )

        # テスト対象の特定
        related_tests = self._test_finder.find_related_tests(
            changed_paths, test_files
        )

        # スコア算出
        score = self._calculate_score(
            changes, affected_files, breaking_changes, related_tests
        )

        description = self._build_description(
            changes, affected_files, breaking_changes, related_tests
        )

        result = ImpactScore(
            score=score,
            affected_files=affected_files,
            affected_tests=related_tests,
            breaking_changes=breaking_changes,
            description=description,
        )
        logger.info("影響スコア: %.2f", result.score)
        return result

    def generate_report(self, score: ImpactScore) -> str:
        """影響スコアから Markdown レポートを生成する。

        Parameters
        ----------
        score : ImpactScore
            影響スコア。

        Returns
        -------
        str
            Markdown 形式のレポート文字列。
        """
        level = self._score_level(score.score)
        lines = [
            "# 変更影響分析レポート",
            "",
            f"**影響スコア:** {score.score:.2f} ({level})",
            "",
            f"**概要:** {score.description}",
            "",
        ]

        if score.affected_files:
            lines.append("## 影響ファイル")
            lines.append("")
            for f in score.affected_files:
                lines.append(f"- {f}")
            lines.append("")

        if score.affected_tests:
            lines.append("## 関連テスト")
            lines.append("")
            for t in score.affected_tests:
                lines.append(f"- {t}")
            lines.append("")

        if score.breaking_changes:
            lines.append("## ⚠️ 破壊的変更")
            lines.append("")
            for bc in score.breaking_changes:
                lines.append(f"- {bc}")
            lines.append("")

        return "\n".join(lines)

    # ── 内部メソッド ──

    def _calculate_score(
        self,
        changes: list[FileChange],
        affected_files: list[str],
        breaking_changes: list[str],
        related_tests: list[str],
    ) -> float:
        """各要素の重みから影響スコアを算出する（0.0 ~ 1.0）。"""
        if not changes:
            return 0.0

        deleted_ratio = (
            sum(1 for c in changes if c.change_type == "deleted") / len(changes)
        )
        affected_ratio = min(len(affected_files) / max(len(changes), 1), 1.0)
        breaking_ratio = min(len(breaking_changes) / max(len(changes), 1), 1.0)
        test_ratio = min(len(related_tests) / max(len(changes), 1), 1.0)

        raw = (
            self._WEIGHT_DELETED * deleted_ratio
            + self._WEIGHT_AFFECTED * affected_ratio
            + self._WEIGHT_BREAKING * breaking_ratio
            + self._WEIGHT_TESTS * test_ratio
        )
        return round(min(max(raw, 0.0), 1.0), 4)

    @staticmethod
    def _build_description(
        changes: list[FileChange],
        affected_files: list[str],
        breaking_changes: list[str],
        related_tests: list[str],
    ) -> str:
        """スコアの概要説明文を組み立てる。"""
        parts: list[str] = [f"{len(changes)} ファイル変更"]
        if affected_files:
            parts.append(f"{len(affected_files)} ファイルに波及")
        if breaking_changes:
            parts.append(f"{len(breaking_changes)} 件の破壊的変更")
        if related_tests:
            parts.append(f"{len(related_tests)} テスト要実行")
        return "、".join(parts)

    @staticmethod
    def _score_level(score: float) -> str:
        """スコアを人間向けのレベル表記に変換する。"""
        if score >= 0.7:
            return "高"
        if score >= 0.4:
            return "中"
        return "低"
