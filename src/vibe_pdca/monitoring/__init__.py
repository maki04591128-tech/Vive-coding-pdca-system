"""トレーサビリティ基盤 – Goal→Milestone→Task→PR→Review→Decision の双方向追跡。

M1 タスク 1-7: 要件定義書 §14.2 準拠。
TraceLinkモデルを使用して、成果物間の追跡リンクを管理する。
"""

from __future__ import annotations

import logging
from typing import Any

from vibe_pdca.models.pdca import TraceLink

logger = logging.getLogger(__name__)

__all__ = [
    "TraceLinkManager",
]


class TraceLinkManager:
    """追跡リンクの管理。

    Goal→Milestone→Task→PR→Review→Decision の双方向追跡を実現する。
    """

    # 有効なリソース種別
    VALID_TYPES = frozenset({
        "goal", "milestone", "task", "pr", "review", "decision",
        "issue", "cycle", "audit_entry",
    })

    def __init__(self) -> None:
        self._links: list[TraceLink] = []
        # インデックス: source_key → リンクインデックスのリスト
        self._by_source: dict[str, list[int]] = {}
        # インデックス: target_key → リンクインデックスのリスト
        self._by_target: dict[str, list[int]] = {}

    @property
    def link_count(self) -> int:
        return len(self._links)

    @staticmethod
    def _key(resource_type: str, resource_id: str) -> str:
        return f"{resource_type}:{resource_id}"

    def add_link(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        relationship: str = "related_to",
    ) -> TraceLink:
        """追跡リンクを追加する。

        Parameters
        ----------
        source_type : str
            リンク元リソース種別。
        source_id : str
            リンク元リソースID。
        target_type : str
            リンク先リソース種別。
        target_id : str
            リンク先リソースID。
        relationship : str
            関係の種類（例: has_milestone, implements, reviews）。

        Returns
        -------
        TraceLink
            追加されたリンク。
        """
        link = TraceLink(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relationship=relationship,
        )

        idx = len(self._links)
        self._links.append(link)

        src_key = self._key(source_type, source_id)
        tgt_key = self._key(target_type, target_id)
        self._by_source.setdefault(src_key, []).append(idx)
        self._by_target.setdefault(tgt_key, []).append(idx)

        logger.debug(
            "追跡リンク追加: %s:%s → %s:%s (%s)",
            source_type, source_id, target_type, target_id, relationship,
        )
        return link

    def get_forward_links(
        self,
        source_type: str,
        source_id: str,
    ) -> list[TraceLink]:
        """指定リソースから出ているリンク（順方向）を取得する。"""
        key = self._key(source_type, source_id)
        indices = self._by_source.get(key, [])
        return [self._links[i] for i in indices]

    def get_backward_links(
        self,
        target_type: str,
        target_id: str,
    ) -> list[TraceLink]:
        """指定リソースに入ってくるリンク（逆方向）を取得する。"""
        key = self._key(target_type, target_id)
        indices = self._by_target.get(key, [])
        return [self._links[i] for i in indices]

    def get_all_related(
        self,
        resource_type: str,
        resource_id: str,
    ) -> list[TraceLink]:
        """指定リソースに関連する全リンク（双方向）を取得する。"""
        # 重複除去
        seen: set[int] = set()
        result: list[TraceLink] = []
        key = self._key(resource_type, resource_id)
        for i in self._by_source.get(key, []) + self._by_target.get(key, []):
            if i not in seen:
                seen.add(i)
                result.append(self._links[i])
        return result

    def trace_chain(
        self,
        start_type: str,
        start_id: str,
        max_depth: int = 10,
    ) -> list[TraceLink]:
        """指定リソースから順方向にチェーンを辿る。

        Parameters
        ----------
        start_type : str
            開始リソース種別。
        start_id : str
            開始リソースID。
        max_depth : int
            最大追跡深度。

        Returns
        -------
        list[TraceLink]
            辿ったリンクのチェーン。
        """
        chain: list[TraceLink] = []
        visited: set[str] = set()
        queue: list[tuple[str, str, int]] = [(start_type, start_id, 0)]

        while queue:
            src_type, src_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            key = self._key(src_type, src_id)
            if key in visited:
                continue
            visited.add(key)

            for link in self.get_forward_links(src_type, src_id):
                chain.append(link)
                queue.append((link.target_type, link.target_id, depth + 1))

        return chain

    def export(self) -> list[dict[str, Any]]:
        """全リンクをエクスポート用dict形式で返す。"""
        return [link.model_dump() for link in self._links]
