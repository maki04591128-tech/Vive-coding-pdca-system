"""GitHub App トークン動的管理・ローテーション。

提案20: GitHub App のスコープ動的管理とトークンローテーション。

機能:
  - TokenRotationManager: トークン自動ローテーション
  - ScopeManager / PhaseScope: PDCAフェーズ別スコープ管理
  - TokenLeakDetector / LeakDetection: トークン漏洩検知
  - AccessLogger / TokenAccessLog: APIアクセスログ
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from vibe_pdca.models.pdca import PDCAPhase

logger = logging.getLogger(__name__)

__all__ = [
    "TokenRotationManager",
    "PhaseScope",
    "ScopeManager",
    "TokenLeakDetector",
    "LeakDetection",
    "TokenAccessLog",
    "AccessLogger",
]

# GitHub Installation Token の有効期限（秒）
_TOKEN_LIFETIME_SECONDS = 3600


# ============================================================
# トークンローテーション管理
# ============================================================


# --- GitHub Appトークン管理: 短寿命トークンの自動生成・ローテーション ---
# GitHub Appの認証トークンは1時間で失効するため、自動更新が必要
class TokenRotationManager:
    """Installation Tokenの自動ローテーションを管理する。

    GitHubのInstallation Tokenは発行から1時間で失効するため、
    失効前に新しいトークンへ切り替える。
    """

    def __init__(self, rotation_buffer_seconds: int = 300) -> None:
        """初期化。

        Args:
            rotation_buffer_seconds: 失効何秒前にローテーションするか（デフォルト300秒=5分前）。
        """
        self.rotation_buffer_seconds = rotation_buffer_seconds
        self._token: str | None = None
        self._created_at: float | None = None
        self._expiry: float | None = None
        self._rotation_count: int = 0
        self._lock = threading.Lock()

    @property
    def token(self) -> str | None:
        """現在のトークンを返す。"""
        with self._lock:
            return self._token

    @property
    def rotation_count(self) -> int:
        """ローテーション実行回数を返す。"""
        with self._lock:
            return self._rotation_count

    def set_token(self, token: str, created_at: float | None = None) -> None:
        """トークンと発行時刻を設定する。

        Args:
            token: Installation Access Token。
            created_at: 発行時刻（Unixタイムスタンプ）。省略時は現在時刻。
        """
        now = time.time()
        with self._lock:
            self._token = token
            self._created_at = created_at if created_at is not None else now
            self._expiry = self._created_at + _TOKEN_LIFETIME_SECONDS
            remaining = self._expiry - now
        logger.info("トークン設定完了 (有効期限: %.0f秒後)", remaining)

    def needs_rotation(self) -> bool:
        """トークンのローテーションが必要かどうかを判定する。

        Returns:
            ローテーションが必要な場合True。
        """
        with self._lock:
            if self._token is None or self._expiry is None:
                return True
            remaining = self._expiry - time.time()
            return remaining <= self.rotation_buffer_seconds

    def rotate(self, token_factory: Callable[[], str]) -> str:
        """トークンをローテーションする。

        Args:
            token_factory: 新しいトークンを生成するコールバック関数。

        Returns:
            新しいトークン。
        """
        with self._lock:
            count = self._rotation_count + 1
        logger.info("トークンローテーション開始 (回数: %d)", count)
        new_token = token_factory()
        self.set_token(new_token)
        with self._lock:
            self._rotation_count += 1
            total = self._rotation_count
        logger.info("トークンローテーション完了 (累計: %d回)", total)
        return new_token


# ============================================================
# PDCAフェーズ別スコープ管理
# ============================================================


# PDCAフェーズごとに必要最小限のGitHub権限スコープを定義
@dataclass(frozen=True)
class PhaseScope:
    """PDCAフェーズに必要な最小限のGitHub権限を定義する。"""

    phase: str
    permissions: frozenset[str]


# フェーズ別の必要最小権限マッピング
_PHASE_SCOPES: dict[str, frozenset[str]] = {
    PDCAPhase.PLAN: frozenset({
        "contents:read",
        "issues:write",
        "pull_requests:read",
    }),
    PDCAPhase.DO: frozenset({
        "contents:write",
        "issues:write",
        "pull_requests:write",
    }),
    PDCAPhase.CHECK: frozenset({
        "contents:read",
        "issues:read",
        "pull_requests:read",
        "checks:read",
    }),
    PDCAPhase.ACT: frozenset({
        "contents:read",
        "issues:write",
        "pull_requests:write",
    }),
}


class ScopeManager:
    """PDCAフェーズに応じた動的スコープ管理を行う。"""

    def get_required_scopes(self, phase: str) -> set[str]:
        """指定フェーズに必要な権限セットを取得する。

        Args:
            phase: PDCAフェーズ名（"plan", "do", "check", "act"）。

        Returns:
            必要な権限の集合。

        Raises:
            ValueError: 不明なフェーズが指定された場合。
        """
        scopes = _PHASE_SCOPES.get(phase)
        if scopes is None:
            raise ValueError(f"不明なPDCAフェーズ: {phase}")
        return set(scopes)

    def validate_scopes(
        self,
        current_scopes: set[str],
        required_scopes: set[str],
    ) -> bool:
        """現在のスコープが要求を満たすか検証する。

        Args:
            current_scopes: 現在付与されている権限。
            required_scopes: 必要な権限。

        Returns:
            必要な権限がすべて含まれている場合True。
        """
        return required_scopes.issubset(current_scopes)


# ============================================================
# トークン漏洩検知
# ============================================================

# GitHub トークンパターン（コンパイル済み正規表現）
_TOKEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("github_personal_access_token", re.compile(r"ghp_[A-Za-z0-9]{36,}")),
    ("github_installation_token", re.compile(r"ghs_[A-Za-z0-9]{36,}")),
    ("github_fine_grained_pat", re.compile(r"github_pat_[A-Za-z0-9_]{22,}")),
    ("github_oauth_token", re.compile(r"gho_[A-Za-z0-9]{36,}")),
    ("github_user_to_server_token", re.compile(r"ghu_[A-Za-z0-9]{36,}")),
    ("github_server_to_server_token", re.compile(r"ghr_[A-Za-z0-9]{36,}")),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)),
]


@dataclass(frozen=True)
class LeakDetection:
    """トークン漏洩検知結果。"""

    pattern_name: str
    position: int
    redacted_value: str


class TokenLeakDetector:
    """テキスト中のGitHubトークン漏洩を検知する。"""

    def __init__(self) -> None:
        """初期化。コンパイル済みパターンを使用する。"""
        self._patterns = _TOKEN_PATTERNS

    def scan_text(self, text: str) -> list[LeakDetection]:
        """テキストをスキャンしてトークン漏洩を検出する。

        Args:
            text: スキャン対象のテキスト。

        Returns:
            検出されたトークン漏洩のリスト。
        """
        detections: list[LeakDetection] = []
        for pattern_name, pattern in self._patterns:
            for match in pattern.finditer(text):
                raw = match.group()
                redacted = self._redact(raw)
                detection = LeakDetection(
                    pattern_name=pattern_name,
                    position=match.start(),
                    redacted_value=redacted,
                )
                detections.append(detection)
                logger.warning(
                    "トークン漏洩検知: %s (位置: %d, 値: %s)",
                    pattern_name,
                    match.start(),
                    redacted,
                )
        return detections

    @staticmethod
    def _redact(value: str) -> str:
        """トークンをマスクする。4文字以下は全体を"***"に、5文字以上は先頭4文字を残す。"""
        if len(value) <= 4:
            return "***"
        return value[:4] + "***"


# ============================================================
# APIアクセスログ
# ============================================================


@dataclass
class TokenAccessLog:
    """GitHub APIアクセスログエントリ。"""

    endpoint: str
    method: str
    status_code: int
    timestamp: float
    duration_ms: float


class AccessLogger:
    """GitHub APIアクセスを記録・集計する。"""

    def __init__(self) -> None:
        """初期化。"""
        self._entries: list[TokenAccessLog] = []
        self._lock = threading.Lock()

    def log(self, entry: TokenAccessLog) -> None:
        """アクセスログを記録する。

        Args:
            entry: ログエントリ。
        """
        with self._lock:
            self._entries.append(entry)
        logger.debug(
            "API呼出: %s %s → %d (%.1fms)",
            entry.method,
            entry.endpoint,
            entry.status_code,
            entry.duration_ms,
        )

    def get_recent(self, count: int) -> list[TokenAccessLog]:
        """直近のアクセスログを取得する。

        Args:
            count: 取得件数。

        Returns:
            直近のログエントリ（新しい順）。
        """
        with self._lock:
            return list(reversed(self._entries[-count:]))

    def get_summary(self) -> dict[str, object]:
        """アクセスログのサマリーを取得する。

        Returns:
            総呼出回数、エラー率、平均応答時間などの集計情報。
        """
        with self._lock:
            total = len(self._entries)
            if total == 0:
                return {
                    "total_calls": 0,
                    "error_count": 0,
                    "error_rate": 0.0,
                    "avg_duration_ms": 0.0,
                }

            error_count = sum(1 for e in self._entries if e.status_code >= 400)
            avg_duration = sum(e.duration_ms for e in self._entries) / total

            return {
                "total_calls": total,
                "error_count": error_count,
                "error_rate": error_count / total,
                "avg_duration_ms": round(avg_duration, 2),
            }
