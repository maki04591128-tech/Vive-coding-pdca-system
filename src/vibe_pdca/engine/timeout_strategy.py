"""PDCAサイクルのタイムアウト戦略の精緻化。

提案18: フェーズ別タイムアウト・複雑度ベース調整・進捗ベース延長。

- フェーズごとのタイムアウト設定
- 複雑度スコアに基づくタイムアウト調整
- 進捗検知による自動延長
- エスカレーション管理
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum

from vibe_pdca.models.pdca import PDCAPhase

logger = logging.getLogger(__name__)


# ============================================================
# フェーズ別タイムアウト
# ============================================================


@dataclass
class PhaseTimeout:
    """フェーズごとのタイムアウト設定（秒単位）。"""

    plan: float = 30 * 60       # PLAN: 30分
    do: float = 3 * 3600        # DO: 3時間
    check: float = 1 * 3600     # CHECK: 1時間
    act: float = 30 * 60        # ACT: 30分

    def get(self, phase: PDCAPhase) -> float:
        """指定フェーズのタイムアウト秒数を返す。"""
        mapping = {
            PDCAPhase.PLAN: self.plan,
            PDCAPhase.DO: self.do,
            PDCAPhase.CHECK: self.check,
            PDCAPhase.ACT: self.act,
        }
        return mapping[phase]


# ============================================================
# エスカレーション
# ============================================================


class TimeoutEscalation(IntEnum):
    """タイムアウトのエスカレーションレベル。

    パーセンテージは経過時間のしきい値を表す。
    """

    WARNING = 50                # 50%経過: 警告
    INTERVENTION_REQUEST = 75   # 75%経過: 介入要求
    STOP = 100                  # 100%経過: 停止


@dataclass
class EscalationEvent:
    """エスカレーション発生の記録。"""

    level: TimeoutEscalation
    phase: PDCAPhase
    elapsed_seconds: float
    timeout_seconds: float
    message: str


# ============================================================
# 複雑度ベースタイムアウト調整
# ============================================================


class ComplexityBasedTimeout:
    """タスク複雑度に基づくタイムアウト調整。

    complexity_score (0.0–1.0) に応じてベースタイムアウトを乗算する。
    乗算係数は 1.0 + complexity_score * (max_multiplier - 1.0) で線形補間。
    例: complexity=0.0 → 1.0x, complexity=0.5 → 2.0x, complexity=1.0 → 3.0x
    """

    def __init__(
        self,
        complexity_score: float = 0.0,
        max_multiplier: float = 3.0,
    ) -> None:
        if not 0.0 <= complexity_score <= 1.0:
            raise ValueError(
                f"complexity_score は 0.0–1.0 の範囲: {complexity_score}"
            )
        if max_multiplier < 1.0:
            raise ValueError(
                f"max_multiplier は 1.0 以上: {max_multiplier}"
            )
        self._score = complexity_score
        self._max_multiplier = max_multiplier

    @property
    def complexity_score(self) -> float:
        return self._score

    @property
    def max_multiplier(self) -> float:
        return self._max_multiplier

    @property
    def multiplier(self) -> float:
        """現在の複雑度に基づく乗算係数を返す。"""
        return 1.0 + self._score * (self._max_multiplier - 1.0)

    def adjust(self, base_timeout: float) -> float:
        """ベースタイムアウトを複雑度で調整した値を返す。"""
        return base_timeout * self.multiplier


# ============================================================
# 進捗ベース延長
# ============================================================


class ProgressBasedExtension:
    """進捗検知による自動タイムアウト延長。

    ハートビート（progress=True）受信時に延長を適用する。
    max_extensions 回まで延長可能。
    """

    def __init__(
        self,
        per_extension_seconds: float = 600.0,
        max_extensions: int = 3,
    ) -> None:
        self._per_extension = per_extension_seconds
        self._max_extensions = max_extensions
        self._extensions_used: int = 0

    @property
    def per_extension_seconds(self) -> float:
        return self._per_extension

    @property
    def max_extensions(self) -> int:
        return self._max_extensions

    @property
    def extensions_used(self) -> int:
        return self._extensions_used

    @property
    def remaining_extensions(self) -> int:
        return self._max_extensions - self._extensions_used

    @property
    def total_extension_seconds(self) -> float:
        """これまでに適用された延長秒数の合計を返す。"""
        return self._extensions_used * self._per_extension

    def record_progress(self, progress: bool = True) -> float:
        """進捗を記録し、延長された秒数を返す（0なら延長なし）。"""
        if not progress:
            return 0.0
        if self._extensions_used >= self._max_extensions:
            logger.info("延長上限到達: %d/%d", self._extensions_used, self._max_extensions)
            return 0.0
        self._extensions_used += 1
        logger.info(
            "タイムアウト延長: +%ss (回数 %d/%d)",
            self._per_extension,
            self._extensions_used,
            self._max_extensions,
        )
        return self._per_extension

    def reset(self) -> None:
        """延長カウンタをリセットする。"""
        self._extensions_used = 0


# ============================================================
# タイムアウトマネージャ
# ============================================================


class TimeoutManager:
    """タイムアウト統合管理。

    フェーズ別タイムアウト・複雑度調整・進捗延長を統合し、
    エスカレーション判定と統計追跡を行う。
    """

    def __init__(
        self,
        phase_timeout: PhaseTimeout | None = None,
        complexity: ComplexityBasedTimeout | None = None,
        extension: ProgressBasedExtension | None = None,
    ) -> None:
        self._phase_timeout = phase_timeout or PhaseTimeout()
        self._complexity = complexity or ComplexityBasedTimeout()
        self._extension = extension or ProgressBasedExtension()
        self._phase_start_times: dict[PDCAPhase, float] = {}
        self._phase_actual_times: dict[PDCAPhase, list[float]] = {
            p: [] for p in PDCAPhase
        }
        self._fired_escalations: dict[PDCAPhase, set[TimeoutEscalation]] = {}

    @property
    def phase_timeout(self) -> PhaseTimeout:
        return self._phase_timeout

    @property
    def complexity(self) -> ComplexityBasedTimeout:
        return self._complexity

    @property
    def extension(self) -> ProgressBasedExtension:
        return self._extension

    def start_phase(self, phase: PDCAPhase, now: float | None = None) -> None:
        """フェーズの計測を開始する。"""
        current = now if now is not None else time.time()
        self._phase_start_times[phase] = current
        self._fired_escalations[phase] = set()
        self._extension.reset()
        logger.info("フェーズ開始: %s (実効タイムアウト: %.0f秒)", phase.value, self.get_effective_timeout(phase))

    def end_phase(self, phase: PDCAPhase, now: float | None = None) -> None:
        """フェーズの計測を終了し、実績時間を記録する。"""
        current = now if now is not None else time.time()
        start = self._phase_start_times.get(phase)
        if start is not None:
            actual = current - start
            self._phase_actual_times[phase].append(actual)
            logger.info("フェーズ終了: %s (実績: %.1fs)", phase.value, actual)

    def get_effective_timeout(self, phase: PDCAPhase) -> float:
        """複雑度調整＋進捗延長を反映した実効タイムアウトを返す。"""
        base = self._phase_timeout.get(phase)
        adjusted = self._complexity.adjust(base)
        extended = adjusted + self._extension.total_extension_seconds
        return extended

    def check_escalations(
        self,
        phase: PDCAPhase,
        now: float | None = None,
    ) -> list[EscalationEvent]:
        """現在の経過時間に基づきエスカレーションイベントを返す。

        同一フェーズで同一レベルのエスカレーションは1度だけ発火する。
        """
        current = now if now is not None else time.time()
        start = self._phase_start_times.get(phase)
        if start is None:
            return []

        elapsed = current - start
        effective = self.get_effective_timeout(phase)
        if effective <= 0:
            return []

        ratio = (elapsed / effective) * 100
        fired = self._fired_escalations.setdefault(phase, set())
        events: list[EscalationEvent] = []

        for level in sorted(TimeoutEscalation, key=lambda l: l.value):
            if level in fired:
                continue
            if ratio >= level.value:
                msg = self._escalation_message(level, phase, elapsed, effective)
                event = EscalationEvent(
                    level=level,
                    phase=phase,
                    elapsed_seconds=elapsed,
                    timeout_seconds=effective,
                    message=msg,
                )
                events.append(event)
                fired.add(level)
                logger.warning("エスカレーション: %s – %s", level.name, msg)

        return events

    def get_statistics(self) -> dict[PDCAPhase, dict[str, float]]:
        """フェーズごとの実績統計（平均・最小・最大）を返す。"""
        stats: dict[PDCAPhase, dict[str, float]] = {}
        for phase, times in self._phase_actual_times.items():
            if not times:
                continue
            stats[phase] = {
                "count": float(len(times)),
                "average": sum(times) / len(times),
                "min": min(times),
                "max": max(times),
            }
        return stats

    @staticmethod
    def _escalation_message(
        level: TimeoutEscalation,
        phase: PDCAPhase,
        elapsed: float,
        effective: float,
    ) -> str:
        """エスカレーションメッセージを生成する。"""
        pct = (elapsed / effective) * 100 if effective > 0 else 0
        labels = {
            TimeoutEscalation.WARNING: "警告",
            TimeoutEscalation.INTERVENTION_REQUEST: "介入要求",
            TimeoutEscalation.STOP: "停止",
        }
        label = labels.get(level, level.name)
        return (
            f"[{label}] {phase.value}フェーズ: "
            f"経過 {elapsed:.0f}s / 制限 {effective:.0f}s ({pct:.0f}%)"
        )
