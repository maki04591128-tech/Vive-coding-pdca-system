"""用語集管理基盤 – 用語CRUD・変更履歴。

M1 タスク 1-9: 要件定義書 §11.4 準拠。
プロジェクト内の用語定義を一元管理し、変更履歴を記録する。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

__all__ = [
    "GlossaryChange",
    "GlossaryEntry",
    "GlossaryManager",
]


class GlossaryChange(BaseModel):
    """用語の変更履歴エントリ。"""

    timestamp: float = Field(default_factory=time.time)
    actor: str = Field(..., description="変更者")
    action: str = Field(..., description="操作（create/update/delete）")
    old_definition: str | None = Field(default=None, description="変更前の定義")
    new_definition: str | None = Field(default=None, description="変更後の定義")


class GlossaryEntry(BaseModel):
    """用語集の1エントリ。"""

    term: str = Field(..., description="用語名")
    definition: str = Field(..., description="用語の定義")
    aliases: list[str] = Field(default_factory=list, description="別名・略称")
    category: str = Field(default="general", description="カテゴリ")
    source: str = Field(default="", description="定義の出典（要件定義書の章番号など）")
    history: list[GlossaryChange] = Field(
        default_factory=list, description="変更履歴"
    )
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class GlossaryManager:
    """用語集の管理マネージャー。

    用語のCRUD操作と変更履歴の管理を行う。
    """

    def __init__(self) -> None:
        self._entries: dict[str, GlossaryEntry] = {}

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def add(
        self,
        term: str,
        definition: str,
        actor: str = "system",
        aliases: list[str] | None = None,
        category: str = "general",
        source: str = "",
    ) -> GlossaryEntry:
        """用語を追加する。

        Parameters
        ----------
        term : str
            用語名。
        definition : str
            用語の定義。
        actor : str
            操作者。
        aliases : list[str] | None
            別名・略称。
        category : str
            カテゴリ。
        source : str
            定義の出典。

        Returns
        -------
        GlossaryEntry
            追加されたエントリ。

        Raises
        ------
        ValueError
            既に同名の用語が存在する場合。
        """
        normalized = term.strip()
        if not normalized:
            raise ValueError("用語名を空にすることはできません")
        if normalized in self._entries:
            raise ValueError(f"用語 '{normalized}' は既に登録されています")

        entry = GlossaryEntry(
            term=normalized,
            definition=definition,
            aliases=aliases or [],
            category=category,
            source=source,
            history=[
                GlossaryChange(
                    actor=actor,
                    action="create",
                    new_definition=definition,
                ),
            ],
        )
        self._entries[normalized] = entry
        logger.info("用語追加: '%s' (actor=%s)", normalized, actor)
        return entry

    def get(self, term: str) -> GlossaryEntry | None:
        """用語を取得する（別名でも検索可能）。"""
        normalized = term.strip()
        # 正式名で検索
        if normalized in self._entries:
            return self._entries[normalized]
        # 別名で検索
        for entry in self._entries.values():
            if normalized in entry.aliases:
                return entry
        return None

    def update(
        self,
        term: str,
        definition: str,
        actor: str = "system",
    ) -> GlossaryEntry:
        """用語の定義を更新する。

        Parameters
        ----------
        term : str
            用語名。
        definition : str
            新しい定義。
        actor : str
            操作者。

        Returns
        -------
        GlossaryEntry
            更新されたエントリ。

        Raises
        ------
        KeyError
            用語が見つからない場合。
        """
        normalized = term.strip()
        if normalized not in self._entries:
            raise KeyError(f"用語 '{normalized}' が見つかりません")

        entry = self._entries[normalized]
        old_def = entry.definition
        entry.definition = definition
        entry.updated_at = time.time()
        entry.history.append(
            GlossaryChange(
                actor=actor,
                action="update",
                old_definition=old_def,
                new_definition=definition,
            )
        )
        logger.info("用語更新: '%s' (actor=%s)", normalized, actor)
        return entry

    def delete(self, term: str, actor: str = "system") -> GlossaryEntry:
        """用語を削除する。

        Parameters
        ----------
        term : str
            用語名。
        actor : str
            操作者。

        Returns
        -------
        GlossaryEntry
            削除されたエントリ（履歴含む）。

        Raises
        ------
        KeyError
            用語が見つからない場合。
        """
        normalized = term.strip()
        if normalized not in self._entries:
            raise KeyError(f"用語 '{normalized}' が見つかりません")

        entry = self._entries.pop(normalized)
        entry.history.append(
            GlossaryChange(
                actor=actor,
                action="delete",
                old_definition=entry.definition,
            )
        )
        logger.info("用語削除: '%s' (actor=%s)", normalized, actor)
        return entry

    def search(self, query: str) -> list[GlossaryEntry]:
        """用語名・定義・別名にクエリを含むエントリを検索する。"""
        q = query.strip().lower()
        results: list[GlossaryEntry] = []
        for entry in self._entries.values():
            if (
                q in entry.term.lower()
                or q in entry.definition.lower()
                or any(q in a.lower() for a in entry.aliases)
            ):
                results.append(entry)
        return results

    def list_all(self) -> list[GlossaryEntry]:
        """全用語を返す。"""
        return list(self._entries.values())

    def export(self) -> list[dict[str, Any]]:
        """エクスポート用にdict形式で返す。"""
        return [entry.model_dump() for entry in self._entries.values()]
