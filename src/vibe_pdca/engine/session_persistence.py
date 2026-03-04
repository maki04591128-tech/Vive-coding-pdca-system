"""セッション永続化とクラッシュリカバリ。

提案2: セッション状態のチェックポイント保存と
ダーティシャットダウンからの自動復旧を提供する。

- チェックポイントデータの保存・読み込み・検証
- ダーティシャットダウンの検知
- 最新の有効チェックポイントからの復旧
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── CheckpointData ──


@dataclass
class CheckpointData:
    """チェックポイントデータ。

    Parameters
    ----------
    cycle_number : int
        サイクル番号。
    phase : str
        フェーズ名。
    state : dict
        保存対象の状態辞書。
    timestamp : float
        保存時刻 (epoch秒)。
    checksum : str
        状態のチェックサム (SHA-256)。
    """

    cycle_number: int
    phase: str
    state: dict[str, object] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    checksum: str = ""


# ── DirtyShutdownFlag ──


@dataclass
class DirtyShutdownFlag:
    """ダーティシャットダウン検知フラグ。

    Parameters
    ----------
    is_dirty : bool
        ダーティシャットダウン状態かどうか。
    last_clean_shutdown : float
        最後の正常シャットダウン時刻。
    process_id : str
        プロセス識別子。
    """

    is_dirty: bool = False
    last_clean_shutdown: float = 0.0
    process_id: str = ""


# ── CheckpointManager ──


class CheckpointManager:
    """チェックポイントの保存・読み込み・検証を管理する。

    インメモリでチェックポイントデータを保持し、
    チェックサムによる整合性検証を行う。
    """

    def __init__(self) -> None:
        self._checkpoints: list[CheckpointData] = []

    @staticmethod
    def compute_checksum(state: dict[str, object]) -> str:
        """状態辞書のSHA-256チェックサムを計算する。

        Parameters
        ----------
        state : dict
            チェックサム対象の辞書。

        Returns
        -------
        str
            SHA-256ハッシュ文字列。
        """
        serialized = json.dumps(state, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def save(self, data: CheckpointData) -> bool:
        """チェックポイントを保存する。

        チェックサムが未設定の場合は自動計算する。

        Returns
        -------
        bool
            保存に成功した場合True。
        """
        if not data.checksum:
            data.checksum = self.compute_checksum(data.state)
        self._checkpoints.append(data)
        logger.info(
            "チェックポイント保存: cycle=%d, phase=%s, checksum=%s",
            data.cycle_number,
            data.phase,
            data.checksum[:12],
        )
        return True

    def load(self) -> CheckpointData | None:
        """最新のチェックポイントを読み込む。

        Returns
        -------
        CheckpointData | None
            最新のチェックポイント。存在しない場合None。
        """
        if not self._checkpoints:
            logger.info("チェックポイントなし")
            return None
        latest = self._checkpoints[-1]
        logger.info(
            "チェックポイント読み込み: cycle=%d, phase=%s",
            latest.cycle_number,
            latest.phase,
        )
        return latest

    def list_checkpoints(self) -> list[CheckpointData]:
        """保存済みチェックポイントの一覧を返す。"""
        return list(self._checkpoints)

    def validate(self, data: CheckpointData) -> bool:
        """チェックポイントの整合性を検証する。

        Parameters
        ----------
        data : CheckpointData
            検証対象のチェックポイント。

        Returns
        -------
        bool
            チェックサムが一致する場合True。
        """
        expected = self.compute_checksum(data.state)
        is_valid = data.checksum == expected
        if not is_valid:
            logger.warning(
                "チェックサム不一致: expected=%s, actual=%s",
                expected[:12],
                data.checksum[:12],
            )
        return is_valid


# ── CrashRecoveryManager ──


class CrashRecoveryManager:
    """クラッシュリカバリを管理する。

    ダーティシャットダウンの検知と、最新の有効チェックポイント
    からの状態復旧を行う。
    """

    def detect_dirty_shutdown(self, flag: DirtyShutdownFlag) -> bool:
        """ダーティシャットダウンを検知する。

        Returns
        -------
        bool
            ダーティシャットダウンが検知された場合True。
        """
        if flag.is_dirty:
            logger.warning(
                "ダーティシャットダウン検知: process_id=%s",
                flag.process_id,
            )
            return True
        return False

    def recover(
        self,
        manager: CheckpointManager,
    ) -> CheckpointData | None:
        """最新の有効チェックポイントから復旧する。

        Parameters
        ----------
        manager : CheckpointManager
            チェックポイントマネージャ。

        Returns
        -------
        CheckpointData | None
            復旧に使用したチェックポイント。復旧不可の場合None。
        """
        checkpoints = manager.list_checkpoints()
        for cp in reversed(checkpoints):
            if manager.validate(cp):
                logger.info(
                    "復旧成功: cycle=%d, phase=%s",
                    cp.cycle_number,
                    cp.phase,
                )
                return cp
            logger.warning(
                "チェックポイント破損: cycle=%d をスキップ",
                cp.cycle_number,
            )
        logger.warning("有効なチェックポイントが見つかりません")
        return None

    def mark_clean_shutdown(
        self,
        flag: DirtyShutdownFlag,
    ) -> DirtyShutdownFlag:
        """正常シャットダウンを記録する。

        Returns
        -------
        DirtyShutdownFlag
            更新されたフラグ。
        """
        flag.is_dirty = False
        flag.last_clean_shutdown = time.time()
        logger.info("正常シャットダウン記録: process_id=%s", flag.process_id)
        return flag

    def mark_start(
        self,
        flag: DirtyShutdownFlag,
    ) -> DirtyShutdownFlag:
        """プロセス開始を記録する (ダーティフラグを立てる)。

        Returns
        -------
        DirtyShutdownFlag
            更新されたフラグ。
        """
        flag.is_dirty = True
        logger.info("プロセス開始記録: process_id=%s", flag.process_id)
        return flag
