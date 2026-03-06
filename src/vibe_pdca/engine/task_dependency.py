"""タスク依存関係グラフとクリティカルパス分析。

提案21: タスク間の依存関係をDAGで管理し、クリティカルパス分析と
ブロッカー検知による早期警告を提供する。

- タスク依存関係のDAG管理
- トポロジカルソートによる実行順序決定
- クリティカルパス分析による総所要時間の推定
- ブロッカー検知による早期警告
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_TASK_DURATION_SECONDS: float = 3600.0  # デフォルト所要時間: 1時間
# ※ 見積もり未設定のタスクは1時間を仮定して計算する


# ============================================================
# タスクノード
# ============================================================


@dataclass
class TaskNode:
    """依存関係グラフ内のタスクを表すノード。"""

    task_id: str
    title: str
    estimated_duration: float = DEFAULT_TASK_DURATION_SECONDS
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"


# ============================================================
# クリティカルパス結果
# ============================================================


@dataclass
class CriticalPath:
    """クリティカルパス分析の結果。"""

    path: list[str]
    total_duration: float
    bottleneck_task_id: str


# ============================================================
# ブロッカー警告
# ============================================================


@dataclass
class BlockerWarning:
    """ブロッカー検知の警告情報。"""

    task_id: str
    blocked_count: int
    description: str


# ============================================================
# 依存関係グラフ (DAG)
# ============================================================


# --- 依存関係グラフ: タスク間の「AはBの後にやる」関係をDAG（有向非巡回グラフ）で管理 ---
class DependencyGraph:
    """タスク間の依存関係を有向非巡回グラフ（DAG）で管理する。

    タスクの追加・依存関係の登録・トポロジカルソート・
    並列実行グループの算出・バリデーションを提供する。
    """

    def __init__(self) -> None:
        self._nodes: dict[str, TaskNode] = {}
        self._forward: dict[str, set[str]] = {}   # task_id → 依存先の集合
        self._reverse: dict[str, set[str]] = {}   # task_id → 依存元の集合
        # ※ forward = 「誰に依存しているか」
        # ※ reverse = 「誰がこのタスクに依存しているか」

    @property
    def nodes(self) -> dict[str, TaskNode]:
        """登録済みノードの辞書を返す。"""
        return dict(self._nodes)

    def add_task(self, node: TaskNode) -> None:
        """タスクノードをグラフに追加する。"""
        if node.task_id in self._nodes:
            logger.warning("タスク重複: %s は既に登録済み", node.task_id)
            return
        self._nodes[node.task_id] = node
        self._forward.setdefault(node.task_id, set())
        self._reverse.setdefault(node.task_id, set())
        # ノードに事前定義された依存関係を登録
        for dep_id in node.dependencies:
            self._forward[node.task_id].add(dep_id)
            self._reverse.setdefault(dep_id, set()).add(node.task_id)
        logger.info("タスク追加: %s (%s)", node.task_id, node.title)

    def add_dependency(self, task_id: str, depends_on: str) -> None:
        """task_id が depends_on に依存する関係を追加する。"""
        self._forward.setdefault(task_id, set()).add(depends_on)
        self._reverse.setdefault(depends_on, set()).add(task_id)
        # ノードの dependencies リストにも反映
        if task_id in self._nodes and depends_on not in self._nodes[task_id].dependencies:
            self._nodes[task_id].dependencies.append(depends_on)
        logger.info("依存関係追加: %s → %s", task_id, depends_on)

    def get_dependencies(self, task_id: str) -> list[str]:
        """指定タスクが依存するタスクIDのリストを返す。"""
        return sorted(self._forward.get(task_id, set()))

    def get_dependents(self, task_id: str) -> list[str]:
        """指定タスクに依存するタスクIDのリストを返す（逆引き）。"""
        return sorted(self._reverse.get(task_id, set()))

    def get_execution_order(self) -> list[str]:
        """トポロジカルソートによる実行順序を返す。

        循環依存がある場合は ValueError を送出する。
        """
        # トポロジカルソート: 依存関係を壊さない実行順序を求めるアルゴリズム
        # 入次数計算: tid が dep に依存 → dep → tid のエッジ
        in_degree: dict[str, int] = {tid: 0 for tid in self._nodes}
        for tid in self._nodes:
            for dep in self._forward.get(tid, set()):
                if dep in in_degree:
                    in_degree[tid] += 1

        queue: deque[str] = deque()
        for tid, deg in in_degree.items():
            if deg == 0:
                queue.append(tid)

        # 入次数（自分が依存している未完了タスクの数）が0のものから順に処理
        order: list[str] = []
        while queue:
            # 決定的な実行順序のためにソート済みキューから処理
            queue_sorted = sorted(queue)
            queue.clear()
            for current in queue_sorted:
                order.append(current)
                # current に依存しているタスクの入次数を減らす
                for dependent in self._reverse.get(current, set()):
                    if dependent in in_degree:
                        in_degree[dependent] -= 1
                        if in_degree[dependent] == 0:
                            queue.append(dependent)

        if len(order) != len(self._nodes):
            raise ValueError("循環依存が検出されました")

        return order

    def validate(self) -> list[str]:
        """グラフのバリデーションを行い、エラーメッセージのリストを返す。"""
        errors: list[str] = []

        # 存在しない依存先の検出
        for tid in self._nodes:
            for dep in self._forward.get(tid, set()):
                if dep not in self._nodes:
                    errors.append(
                        f"タスク '{tid}' の依存先 '{dep}' が未登録です"
                    )

        # 循環依存の検出
        try:
            self.get_execution_order()
        except ValueError:
            errors.append("循環依存が検出されました")

        # 自己依存の検出
        for tid in self._nodes:
            if tid in self._forward.get(tid, set()):
                errors.append(f"タスク '{tid}' が自己依存しています")

        return errors

    def get_parallel_groups(self) -> list[list[str]]:
        """並列実行可能なタスクグループのリストを返す。

        各グループ内のタスクは互いに依存関係がなく、同時実行可能。
        グループは実行順序に従って返される。
        """
        if not self._nodes:
            return []

        # 登録済みノードのみ対象とした入次数計算
        in_degree: dict[str, int] = {tid: 0 for tid in self._nodes}
        for tid in self._nodes:
            for dep in self._forward.get(tid, set()):
                if dep in in_degree:
                    in_degree[tid] += 1

        groups: list[list[str]] = []
        remaining = dict(in_degree)

        while remaining:
            # 入次数0のタスクは互いに依存がないので、同時に実行できるグループ
            # 入次数0のノードを1グループとする
            group = sorted(tid for tid, deg in remaining.items() if deg == 0)
            if not group:
                # 循環依存により処理不能
                break
            groups.append(group)
            # グループ内のノードを削除し、依存先の入次数を更新
            for tid in group:
                del remaining[tid]
                for dependent in self._reverse.get(tid, set()):
                    if dependent in remaining:
                        remaining[dependent] -= 1

        return groups


# ============================================================
# クリティカルパス分析
# ============================================================


# --- クリティカルパス: プロジェクト全体の最短完了時間を決める「最長経路」を特定 ---
class CriticalPathAnalyzer:
    """依存関係グラフに基づくクリティカルパス分析。

    最長経路（クリティカルパス）を特定し、
    プロジェクト全体の最短完了時間を推定する。
    """

    def __init__(self, graph: DependencyGraph) -> None:
        self._graph = graph

    def find_critical_path(self) -> CriticalPath:
        """クリティカルパス（最長経路）を算出する。

        グラフが空の場合は空のパスを返す。
        """
        nodes = self._graph.nodes
        if not nodes:
            return CriticalPath(path=[], total_duration=0.0, bottleneck_task_id="")

        order = self._graph.get_execution_order()

        # 各タスクの「最も早く終了できる時刻」を依存順に計算していく
        # 各タスクの最早開始時刻を計算
        earliest_finish: dict[str, float] = {}
        predecessor: dict[str, str | None] = {}

        for tid in order:
            node = nodes.get(tid)
            duration = node.estimated_duration if node else 0.0
            deps = self._graph.get_dependencies(tid)
            # 依存先のうち登録済みのもののみ考慮
            valid_deps = [d for d in deps if d in earliest_finish]
            if valid_deps:
                best_dep = max(valid_deps, key=lambda d: earliest_finish[d])
                earliest_finish[tid] = earliest_finish[best_dep] + duration
                predecessor[tid] = best_dep
            else:
                earliest_finish[tid] = duration
                predecessor[tid] = None

        if not earliest_finish:
            return CriticalPath(path=[], total_duration=0.0, bottleneck_task_id="")

        # 最も遅い終了時刻を持つタスクからパスを逆算
        end_task = max(earliest_finish, key=lambda t: earliest_finish[t])
        total_duration = earliest_finish[end_task]

        # パスを復元
        path: list[str] = []
        current: str | None = end_task
        while current is not None:
            path.append(current)
            current = predecessor.get(current)
        path.reverse()

        # ボトルネック（パス上で最も所要時間の長いタスク）
        bottleneck_id = ""
        max_duration = -1.0
        for tid in path:
            node = nodes.get(tid)
            d = node.estimated_duration if node else 0.0
            if d > max_duration:
                max_duration = d
                bottleneck_id = tid

        logger.info(
            "クリティカルパス: %s (総所要時間: %.0f秒, ボトルネック: %s)",
            " → ".join(path),
            total_duration,
            bottleneck_id,
        )

        return CriticalPath(
            path=path,
            total_duration=total_duration,
            bottleneck_task_id=bottleneck_id,
        )

    def estimate_total_duration(self) -> float:
        """プロジェクト全体の最短完了時間（秒）を推定する。"""
        cp = self.find_critical_path()
        return cp.total_duration

    def find_blockers(self) -> list[str]:
        """最も多くのタスクをブロックしているタスクIDを返す。

        ブロック数の降順でソートされたリスト。
        """
        nodes = self._graph.nodes
        if not nodes:
            return []

        block_counts: dict[str, int] = {}
        for tid in nodes:
            dependents = self._graph.get_dependents(tid)
            # 登録済みノードのみカウント
            count = len([d for d in dependents if d in nodes])
            block_counts[tid] = count

        # ブロック数の降順 → タスクID の昇順
        sorted_tasks = sorted(
            block_counts.items(),
            key=lambda x: (-x[1], x[0]),
        )

        return [tid for tid, count in sorted_tasks if count > 0]


# ============================================================
# ブロッカー検知
# ============================================================


# --- ブロッカー検知: 多くのタスクの進行を妨げている「ボトルネックタスク」を早期発見 ---
class BlockerDetector:
    """ブロッカーの早期検知と警告。

    指定しきい値以上の依存タスクをブロックしているタスクを検出する。
    """

    def __init__(self, graph: DependencyGraph) -> None:
        self._graph = graph

    def detect_blockers(self, threshold: int = 2) -> list[BlockerWarning]:
        """しきい値以上のタスクをブロックしているタスクを検出する。

        Parameters
        ----------
        threshold : int
            ブロッカーとみなす最小依存タスク数（デフォルト: 2）。

        Returns
        -------
        list[BlockerWarning]
            検出されたブロッカー警告のリスト（ブロック数の降順）。
        """
        nodes = self._graph.nodes
        warnings: list[BlockerWarning] = []

        for tid, node in sorted(nodes.items()):
            dependents = self._graph.get_dependents(tid)
            # 登録済みノードのみカウント
            blocked = [d for d in dependents if d in nodes]
            count = len(blocked)
            if count >= threshold:
                desc = (
                    f"タスク '{node.title}' ({tid}) は "
                    f"{count} 個のタスクをブロックしています"
                )
                warnings.append(
                    BlockerWarning(
                        task_id=tid,
                        blocked_count=count,
                        description=desc,
                    )
                )
                logger.warning("ブロッカー検知: %s", desc)

        # ブロック数の降順でソート
        warnings.sort(key=lambda w: (-w.blocked_count, w.task_id))

        return warnings
