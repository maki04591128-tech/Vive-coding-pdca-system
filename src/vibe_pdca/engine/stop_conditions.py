"""停止条件・縮退モード管理 – スタック検知・ハートビート・縮退優先度。

M2 タスク 2-9: 要件定義書 §6.6, §13.2 準拠。

- 7つの停止条件（PDCAStateMachine が既に管理）を補完
- 6時間スタック検知（ハートビート機構）
- 縮退モード管理（優先度ベースの機能縮退）
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# 6時間タイムアウト（§13.1）
STACK_TIMEOUT_SECONDS: float = 6 * 3600
# ※ PDCAサイクルが6時間以上進行しない場合、「スタック（停滞）」と判断して停止する


# --- 縮退モード（一部機能を制限して動作を続ける仕組み）の優先度定義 ---
class DegradePriority(IntEnum):
    """縮退モードの機能優先度（§13.2）。

    数値が小さいほど優先。
    """

    AUDIT_LOG = 1       # 監査ログの記録（記録不能なら即停止）
    STOP_NOTIFY = 2     # 停止・Discord通知
    CHECK_REPORT = 3    # CHECKレポートの生成
    DO_PHASE = 4        # DOフェーズ（実装）
    FULL_REVIEW = 5     # ペルソナレビュー全5名


class DegradeAction(StrEnum):
    """縮退時のアクション。"""

    STOP = "stop"               # 即停止
    CONTINUE = "continue"       # 障害があっても継続
    FALLBACK = "fallback"       # 代替モデルで補完
    REDUCE = "reduce"           # 機能を縮小して継続


# 各機能が障害を起こしたとき、どう対処するかのルール（1件分）
@dataclass
class DegradeRule:
    """縮退ルール1件。"""

    priority: DegradePriority
    description: str
    action_on_failure: DegradeAction
    min_components: int = 0     # 最低維持コンポーネント数


# デフォルトの縮退ルール一覧（優先度が高い＝数字が小さい順に定義）
# §13.2 確定の縮退ポリシー
DEFAULT_DEGRADE_RULES: list[DegradeRule] = [
    DegradeRule(
        priority=DegradePriority.AUDIT_LOG,
        description="監査ログの記録",
        action_on_failure=DegradeAction.STOP,
    ),
    DegradeRule(
        priority=DegradePriority.STOP_NOTIFY,
        description="停止・Discord通知",
        action_on_failure=DegradeAction.CONTINUE,
    ),
    DegradeRule(
        priority=DegradePriority.CHECK_REPORT,
        description="CHECKレポートの生成",
        action_on_failure=DegradeAction.FALLBACK,
    ),
    DegradeRule(
        priority=DegradePriority.DO_PHASE,
        description="DOフェーズ（実装）",
        action_on_failure=DegradeAction.STOP,
    ),
    DegradeRule(
        priority=DegradePriority.FULL_REVIEW,
        description="ペルソナレビュー全5名",
        action_on_failure=DegradeAction.REDUCE,
        min_components=2,  # 最低PM+プログラマの2名
    ),
]


@dataclass
class HeartbeatRecord:
    """ハートビート記録。"""

    timestamp: float = field(default_factory=time.time)
    phase: str = ""
    detail: str = ""


# --- スタック検知: 一定時間ハートビート（生存信号）がなければ「停滞」と判定 ---
class StackDetector:
    """スタック検知 – 6時間タイムアウト判定。

    定期的にハートビートを受け取り、タイムアウトを検知する。
    """

    def __init__(
        self,
        timeout_seconds: float = STACK_TIMEOUT_SECONDS,
    ) -> None:
        self._timeout = timeout_seconds
        self._last_heartbeat: float = time.time()
        self._heartbeat_history: list[HeartbeatRecord] = []

    @property
    def last_heartbeat(self) -> float:
        return self._last_heartbeat

    @property
    def timeout_seconds(self) -> float:
        return self._timeout

    @property
    def heartbeat_count(self) -> int:
        return len(self._heartbeat_history)

    def heartbeat(self, phase: str = "", detail: str = "") -> None:
        """ハートビートを記録する。"""
        now = time.time()
        self._last_heartbeat = now
        self._heartbeat_history.append(
            HeartbeatRecord(timestamp=now, phase=phase, detail=detail)
        )

    def is_stacked(self, now: float | None = None) -> bool:
        """スタック状態（6時間タイムアウト）かどうか判定する。"""
        current = now if now is not None else time.time()
        # 最後のハートビートからの経過時間がタイムアウトを超えていれば停滞
        elapsed = current - self._last_heartbeat
        return elapsed > self._timeout

    def elapsed_seconds(self, now: float | None = None) -> float:
        """最後のハートビートからの経過秒数を返す。"""
        current = now if now is not None else time.time()
        return current - self._last_heartbeat

    def get_status(self, now: float | None = None) -> dict[str, Any]:
        """検知状態を返す。"""
        current = now if now is not None else time.time()
        elapsed = current - self._last_heartbeat
        return {
            "last_heartbeat": self._last_heartbeat,
            "elapsed_seconds": elapsed,
            "timeout_seconds": self._timeout,
            "is_stacked": elapsed > self._timeout,
            "heartbeat_count": len(self._heartbeat_history),
        }


# --- 縮退マネージャー: 障害発生時に「止める」「続ける」「代替に切替」を判定 ---
class DegradeManager:
    """縮退モード管理。

    機能障害発生時に、優先度に基づいたアクションを決定する。
    """

    def __init__(
        self,
        rules: list[DegradeRule] | None = None,
    ) -> None:
        self._rules = sorted(
            rules or list(DEFAULT_DEGRADE_RULES),
            key=lambda r: r.priority,
        )
        self._active_failures: dict[DegradePriority, str] = {}

    @property
    def active_failures(self) -> dict[DegradePriority, str]:
        return dict(self._active_failures)

    @property
    def is_degraded(self) -> bool:
        return len(self._active_failures) > 0

    def report_failure(
        self,
        priority: DegradePriority,
        detail: str = "",
    ) -> DegradeAction:
        """機能障害を報告し、取るべきアクションを返す。"""
        # この機能の障害を記録し、ルールに基づいてアクション（停止/続行/代替/縮小）を返す
        self._active_failures[priority] = detail
        rule = self._get_rule(priority)
        if rule is None:
            return DegradeAction.STOP

        logger.warning(
            "縮退: %s – %s (アクション: %s)",
            rule.description, detail, rule.action_on_failure.value,
        )
        return rule.action_on_failure

    def recover(self, priority: DegradePriority) -> None:
        """障害からの復旧を記録する。"""
        self._active_failures.pop(priority, None)
        logger.info("縮退解除: 優先度 %d", priority)

    def should_stop(self) -> bool:
        """即停止すべきかどうかを判定する。"""
        # 現在の障害一覧を確認し、1つでも「即停止」ルールに該当すれば True
        for priority in self._active_failures:
            rule = self._get_rule(priority)
            if rule and rule.action_on_failure == DegradeAction.STOP:
                return True
        return False

    def get_status(self) -> dict[str, Any]:
        """縮退状態を返す。"""
        return {
            "is_degraded": self.is_degraded,
            "should_stop": self.should_stop(),
            "active_failures": {
                p.value: detail
                for p, detail in self._active_failures.items()
            },
            "rules": [
                {
                    "priority": r.priority.value,
                    "description": r.description,
                    "action_on_failure": r.action_on_failure.value,
                }
                for r in self._rules
            ],
        }

    def _get_rule(self, priority: DegradePriority) -> DegradeRule | None:
        """優先度に対応するルールを取得する。"""
        for rule in self._rules:
            if rule.priority == priority:
                return rule
        return None
