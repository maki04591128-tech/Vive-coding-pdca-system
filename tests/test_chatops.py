"""Proposal 28: ChatOps Natural Language Interface のテスト。"""

from __future__ import annotations

from vibe_pdca.engine.chatops import (
    ChatIntent,
    ChatOpsHandler,
    CommandParser,
    ConversationContext,
    IntentClassifier,
    IntentType,
)

# ============================================================
# IntentType enum
# ============================================================


class TestIntentType:
    """IntentType のテスト。"""

    def test_values(self) -> None:
        assert IntentType.QUERY == "query"
        assert IntentType.COMMAND == "command"
        assert IntentType.FEEDBACK == "feedback"
        assert IntentType.UNKNOWN == "unknown"

    def test_is_str(self) -> None:
        assert isinstance(IntentType.QUERY, str)


# ============================================================
# IntentClassifier
# ============================================================


class TestIntentClassifier:
    """IntentClassifier のテスト。"""

    def setup_method(self) -> None:
        self.classifier = IntentClassifier()

    def test_classify_query_japanese(self) -> None:
        intent = self.classifier.classify("現在の状態を教えて")
        assert intent.intent_type == IntentType.QUERY

    def test_classify_query_english(self) -> None:
        intent = self.classifier.classify("show me the status")
        assert intent.intent_type == IntentType.QUERY

    def test_classify_command_japanese(self) -> None:
        intent = self.classifier.classify("サイクルを開始してください")
        assert intent.intent_type == IntentType.COMMAND

    def test_classify_command_english(self) -> None:
        intent = self.classifier.classify("start the cycle now")
        assert intent.intent_type == IntentType.COMMAND

    def test_classify_feedback_japanese(self) -> None:
        intent = self.classifier.classify("良い結果でした、評価します")
        assert intent.intent_type == IntentType.FEEDBACK

    def test_classify_feedback_english(self) -> None:
        intent = self.classifier.classify("this is good feedback")
        assert intent.intent_type == IntentType.FEEDBACK

    def test_classify_unknown(self) -> None:
        intent = self.classifier.classify("xyzzy")
        assert intent.intent_type == IntentType.UNKNOWN
        assert intent.confidence == 0.0

    def test_classify_preserves_raw_input(self) -> None:
        raw = "状態を見せて"
        intent = self.classifier.classify(raw)
        assert intent.raw_input == raw

    def test_classify_action_check_status(self) -> None:
        intent = self.classifier.classify("show status")
        assert intent.action == "check_status"


# ============================================================
# CommandParser
# ============================================================


class TestCommandParser:
    """CommandParser のテスト。"""

    def setup_method(self) -> None:
        self.parser = CommandParser()

    def test_parse_cost_change(self) -> None:
        assert self.parser.parse_cost_change("予算を $50.00 に変更") == 50.0

    def test_parse_cost_change_no_match(self) -> None:
        assert self.parser.parse_cost_change("予算なし") is None

    def test_parse_cycle_reference(self) -> None:
        assert self.parser.parse_cycle_reference("cycle #3 の結果") == 3

    def test_parse_cycle_reference_japanese(self) -> None:
        assert self.parser.parse_cycle_reference("サイクル 5 を確認") == 5

    def test_parse_cycle_reference_no_match(self) -> None:
        assert self.parser.parse_cycle_reference("何もない") is None

    def test_parse_priority_high(self) -> None:
        assert self.parser.parse_priority_directive("priority is high") == "high"

    def test_parse_priority_japanese(self) -> None:
        assert self.parser.parse_priority_directive("優先度を緊急に") == "high"

    def test_parse_priority_low(self) -> None:
        assert self.parser.parse_priority_directive("低い優先度") == "low"

    def test_parse_priority_no_match(self) -> None:
        assert self.parser.parse_priority_directive("特になし") is None


# ============================================================
# ChatOpsHandler
# ============================================================


class TestChatOpsHandler:
    """ChatOpsHandler のテスト。"""

    def setup_method(self) -> None:
        self.handler = ChatOpsHandler(
            intent_classifier=IntentClassifier(),
            command_parser=CommandParser(),
        )

    def test_handle_query(self) -> None:
        resp = self.handler.handle("状態を教えて")
        assert "クエリ" in resp.message
        assert resp.action_taken is not None

    def test_handle_command_safe(self) -> None:
        resp = self.handler.handle("サイクルを開始して")
        assert resp.action_taken is not None or resp.requires_confirmation

    def test_handle_destructive_command(self) -> None:
        resp = self.handler.handle("サイクルを停止してください")
        assert resp.requires_confirmation is True

    def test_handle_feedback(self) -> None:
        resp = self.handler.handle("良いフィードバックです")
        assert "フィードバック" in resp.message

    def test_handle_unknown(self) -> None:
        resp = self.handler.handle("xyzzy gibberish")
        assert "理解できません" in resp.message

    def test_is_destructive_stop(self) -> None:
        intent = ChatIntent(
            intent_type=IntentType.COMMAND,
            action="stop",
            confidence=0.9,
            raw_input="stop",
        )
        assert self.handler.is_destructive_command(intent)

    def test_is_not_destructive_start(self) -> None:
        intent = ChatIntent(
            intent_type=IntentType.COMMAND,
            action="start",
            confidence=0.9,
            raw_input="start",
        )
        assert not self.handler.is_destructive_command(intent)


# ============================================================
# ConversationContext
# ============================================================


class TestConversationContext:
    """ConversationContext のテスト。"""

    def setup_method(self) -> None:
        self.ctx = ConversationContext()

    def test_add_and_count(self) -> None:
        self.ctx.add_message("user", "hello")
        assert self.ctx.message_count == 1

    def test_get_history(self) -> None:
        self.ctx.add_message("user", "hello")
        self.ctx.add_message("assistant", "hi")
        history = self.ctx.get_history()
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["content"] == "hi"

    def test_get_history_last_n(self) -> None:
        for i in range(20):
            self.ctx.add_message("user", f"msg{i}")
        history = self.ctx.get_history(last_n=5)
        assert len(history) == 5
        assert history[0]["content"] == "msg15"

    def test_clear(self) -> None:
        self.ctx.add_message("user", "hello")
        self.ctx.clear()
        assert self.ctx.message_count == 0
        assert self.ctx.get_history() == []
