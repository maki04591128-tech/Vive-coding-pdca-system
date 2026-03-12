"""ChatOps 自然言語インターフェース – 自然言語でPDCAサイクルを操作する。

Proposal 28: ChatOps Natural Language Interface。

入力: ユーザーの自然言語入力（日本語/英語）
出力: インテント分類・コマンド解析・応答生成
"""

from __future__ import annotations

import enum
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# 列挙型
# ============================================================


class IntentType(enum.StrEnum):
    """ユーザー入力のインテント種別。"""

    QUERY = "query"
    COMMAND = "command"
    FEEDBACK = "feedback"
    UNKNOWN = "unknown"


# ============================================================
# データクラス
# ============================================================


@dataclass
class ChatIntent:
    """分類済みチャットインテント。"""

    intent_type: IntentType
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    raw_input: str = ""


@dataclass
class ChatResponse:
    """チャット応答。"""

    message: str
    action_taken: str | None = None
    requires_confirmation: bool = False
    confirmation_prompt: str = ""


# ============================================================
# IntentClassifier – インテント分類
# ============================================================


class IntentClassifier:
    """キーワードベースのインテント分類器。"""

    _QUERY_KEYWORDS: list[str] = [
        "状態", "進捗", "結果", "見せて", "教えて",
        "status", "show", "list", "get", "what", "how",
    ]
    _COMMAND_KEYWORDS: list[str] = [
        "開始", "停止", "変更", "設定", "実行", "削除",
        "start", "stop", "change", "set", "run", "delete",
    ]
    _FEEDBACK_KEYWORDS: list[str] = [
        "評価", "フィードバック", "改善", "良い", "悪い",
        "feedback", "review", "rate", "good", "bad", "improve",
    ]

    def classify(self, user_input: str) -> ChatIntent:
        """ユーザー入力をインテントに分類する。

        Parameters
        ----------
        user_input : str
            ユーザーの自然言語入力。

        Returns
        -------
        ChatIntent
            分類結果。
        """
        lower = user_input.lower()

        query_score = self._match_score(lower, self._QUERY_KEYWORDS)
        command_score = self._match_score(lower, self._COMMAND_KEYWORDS)
        feedback_score = self._match_score(lower, self._FEEDBACK_KEYWORDS)

        scores = {
            IntentType.QUERY: query_score,
            IntentType.COMMAND: command_score,
            IntentType.FEEDBACK: feedback_score,
        }

        best_type = max(scores, key=lambda k: scores[k])
        best_score = scores[best_type]

        if best_score == 0:
            intent_type = IntentType.UNKNOWN
            confidence = 0.0
        else:
            intent_type = best_type
            total = sum(scores.values())
            confidence = best_score / total if total > 0 else 0.0

        action = self._extract_action(lower, intent_type)

        intent = ChatIntent(
            intent_type=intent_type,
            action=action,
            confidence=round(confidence, 4),
            raw_input=user_input,
        )
        logger.debug(
            "インテント分類: type=%s, action=%s, confidence=%.2f",
            intent_type.value,
            action,
            confidence,
        )
        return intent

    # ── 内部メソッド ──

    @staticmethod
    def _match_score(text: str, keywords: list[str]) -> int:
        """テキスト内のキーワード一致数を返す。"""
        return sum(1 for kw in keywords if kw in text)

    @staticmethod
    def _extract_action(text: str, intent_type: IntentType) -> str:
        """インテントタイプに応じたアクション名を推定する。"""
        if intent_type == IntentType.QUERY:
            if "status" in text or "状態" in text:
                return "check_status"
            if "進捗" in text or "progress" in text:
                return "check_progress"
            return "general_query"
        if intent_type == IntentType.COMMAND:
            if "start" in text or "開始" in text:
                return "start"
            if "stop" in text or "停止" in text:
                return "stop"
            if "change" in text or "変更" in text:
                return "modify"
            return "general_command"
        if intent_type == IntentType.FEEDBACK:
            if "良い" in text or "good" in text:
                return "positive_feedback"
            if "悪い" in text or "bad" in text:
                return "negative_feedback"
            return "general_feedback"
        return "unknown"


# ============================================================
# CommandParser – コマンド解析
# ============================================================


class CommandParser:
    """自然言語からコマンドパラメータを抽出する。"""

    _DOLLAR_RE = re.compile(r"\$\s*([\d.]+)")
    _CYCLE_RE = re.compile(r"(?:cycle|サイクル)\s*#?\s*(\d+)", re.IGNORECASE)
    _PRIORITY_RE = re.compile(
        r"(high|medium|low|高|中|低|urgent|緊急)", re.IGNORECASE
    )

    def parse_cost_change(self, text: str) -> float | None:
        """テキストからドル金額を抽出する。

        Parameters
        ----------
        text : str
            解析対象テキスト。

        Returns
        -------
        float | None
            抽出された金額。見つからない場合は None。
        """
        match = self._DOLLAR_RE.search(text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    def parse_cycle_reference(self, text: str) -> int | None:
        """テキストからサイクル番号を抽出する。

        Parameters
        ----------
        text : str
            解析対象テキスト。

        Returns
        -------
        int | None
            抽出されたサイクル番号。見つからない場合は None。
        """
        match = self._CYCLE_RE.search(text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def parse_priority_directive(self, text: str) -> str | None:
        """テキストから優先度キーワードを抽出する。

        Parameters
        ----------
        text : str
            解析対象テキスト。

        Returns
        -------
        str | None
            抽出された優先度。見つからない場合は None。
        """
        match = self._PRIORITY_RE.search(text)
        if match:
            raw = match.group(1).lower()
            mapping = {
                "high": "high", "高": "high", "urgent": "high", "緊急": "high",
                "medium": "medium", "中": "medium",
                "low": "low", "低": "low",
            }
            return mapping.get(raw)
        return None


# ============================================================
# ChatOpsHandler – メインハンドラ
# ============================================================


class ChatOpsHandler:
    """ChatOps の自然言語入力を処理するメインハンドラ。"""

    _DESTRUCTIVE_ACTIONS: set[str] = {"stop", "delete", "modify"}

    def __init__(
        self,
        intent_classifier: IntentClassifier,
        command_parser: CommandParser,
    ) -> None:
        self._classifier = intent_classifier
        self._parser = command_parser

    def handle(self, user_input: str) -> ChatResponse:
        """ユーザー入力を処理して応答を返す。

        Parameters
        ----------
        user_input : str
            ユーザーの自然言語入力。

        Returns
        -------
        ChatResponse
            応答。
        """
        intent = self._classifier.classify(user_input)
        logger.info(
            "入力処理: intent=%s, action=%s",
            intent.intent_type.value,
            intent.action,
        )

        if intent.intent_type == IntentType.QUERY:
            return self._handle_query(intent)
        if intent.intent_type == IntentType.COMMAND:
            return self._handle_command(intent)
        if intent.intent_type == IntentType.FEEDBACK:
            return self._handle_feedback(intent)

        return ChatResponse(
            message="入力を理解できませんでした。もう少し具体的にお願いします。"
        )

    def _handle_query(self, intent: ChatIntent) -> ChatResponse:
        """クエリインテントを処理する。"""
        return ChatResponse(
            message=f"クエリを受け付けました: {intent.action}",
            action_taken=intent.action,
        )

    def _handle_command(self, intent: ChatIntent) -> ChatResponse:
        """コマンドインテントを処理する。"""
        if self.is_destructive_command(intent):
            return ChatResponse(
                message=f"コマンド '{intent.action}' は破壊的操作です。確認してください。",
                action_taken=None,
                requires_confirmation=True,
                confirmation_prompt=f"'{intent.action}' を実行してよろしいですか？",
            )
        return ChatResponse(
            message=f"コマンドを実行しました: {intent.action}",
            action_taken=intent.action,
        )

    def _handle_feedback(self, intent: ChatIntent) -> ChatResponse:
        """フィードバックインテントを処理する。"""
        return ChatResponse(
            message=f"フィードバックを記録しました: {intent.action}",
            action_taken=intent.action,
        )

    def is_destructive_command(self, intent: ChatIntent) -> bool:
        """コマンドが破壊的操作か判定する。

        Parameters
        ----------
        intent : ChatIntent
            判定対象のインテント。

        Returns
        -------
        bool
            破壊的操作の場合 True。
        """
        return intent.action in self._DESTRUCTIVE_ACTIONS


# ============================================================
# ConversationContext – 会話コンテキスト管理
# ============================================================


class ConversationContext:
    """会話履歴を管理する。"""

    def __init__(self) -> None:
        self._history: list[dict[str, str]] = []
        self._lock = threading.Lock()

    def add_message(self, role: str, content: str) -> None:
        """メッセージを追加する。

        Parameters
        ----------
        role : str
            発話者ロール（"user", "assistant" など）。
        content : str
            メッセージ内容。
        """
        with self._lock:
            self._history.append({"role": role, "content": content})
        logger.debug("メッセージ追加: role=%s, length=%d", role, len(content))

    def get_history(self, last_n: int = 10) -> list[dict[str, str]]:
        """直近の会話履歴を取得する。

        Parameters
        ----------
        last_n : int
            取得するメッセージ数。

        Returns
        -------
        list[dict[str, str]]
            会話履歴。
        """
        with self._lock:
            return self._history[-last_n:]

    def clear(self) -> None:
        """会話履歴をクリアする。"""
        with self._lock:
            self._history.clear()
        logger.debug("会話履歴をクリア")

    @property
    def message_count(self) -> int:
        """メッセージ数。"""
        with self._lock:
            return len(self._history)
