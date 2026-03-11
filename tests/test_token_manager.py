"""token_manager モジュールのテスト。

提案20: GitHub App のスコープ動的管理とトークンローテーション。
"""

from __future__ import annotations

import time

import pytest

from vibe_pdca.github.token_manager import (
    AccessLogger,
    LeakDetection,
    PhaseScope,
    ScopeManager,
    TokenAccessLog,
    TokenLeakDetector,
    TokenRotationManager,
)
from vibe_pdca.models.pdca import PDCAPhase

# ============================================================
# TokenRotationManager
# ============================================================


class TestTokenRotationManager:
    """TokenRotationManager のテスト。"""

    def test_needs_rotation_when_no_token(self) -> None:
        """トークン未設定時はローテーション必要。"""
        mgr = TokenRotationManager()
        assert mgr.needs_rotation() is True

    def test_needs_rotation_false_after_set(self) -> None:
        """トークン設定直後はローテーション不要。"""
        mgr = TokenRotationManager()
        mgr.set_token("test_token")
        assert mgr.needs_rotation() is False

    def test_needs_rotation_true_near_expiry(self) -> None:
        """有効期限間近ではローテーション必要。"""
        mgr = TokenRotationManager(rotation_buffer_seconds=300)
        # 3400秒前（残り200秒 < バッファ300秒）に作成されたトークン
        mgr.set_token("test_token", created_at=time.time() - 3400)
        assert mgr.needs_rotation() is True

    def test_needs_rotation_false_well_before_expiry(self) -> None:
        """有効期限まで余裕がある場合はローテーション不要。"""
        mgr = TokenRotationManager(rotation_buffer_seconds=300)
        # 10分前に作成（残り50分）
        mgr.set_token("test_token", created_at=time.time() - 600)
        assert mgr.needs_rotation() is False

    def test_rotate_calls_factory(self) -> None:
        """rotate()がファクトリ関数を呼び出して新トークンを設定する。"""
        mgr = TokenRotationManager()
        new_token = mgr.rotate(lambda: "new_token_value")
        assert new_token == "new_token_value"
        assert mgr.token == "new_token_value"
        assert mgr.rotation_count == 1

    def test_rotate_increments_count(self) -> None:
        """ローテーション回数が正しくカウントされる。"""
        mgr = TokenRotationManager()
        mgr.rotate(lambda: "tok1")
        mgr.rotate(lambda: "tok2")
        mgr.rotate(lambda: "tok3")
        assert mgr.rotation_count == 3
        assert mgr.token == "tok3"

    def test_default_buffer(self) -> None:
        """デフォルトバッファは300秒。"""
        mgr = TokenRotationManager()
        assert mgr.rotation_buffer_seconds == 300

    def test_custom_buffer(self) -> None:
        """カスタムバッファを設定できる。"""
        mgr = TokenRotationManager(rotation_buffer_seconds=600)
        assert mgr.rotation_buffer_seconds == 600

    def test_token_initially_none(self) -> None:
        """初期状態でトークンはNone。"""
        mgr = TokenRotationManager()
        assert mgr.token is None


# ============================================================
# PhaseScope
# ============================================================


class TestPhaseScope:
    """PhaseScope のテスト。"""

    def test_frozen(self) -> None:
        """PhaseScope は不変。"""
        scope = PhaseScope(phase="plan", permissions=frozenset({"contents:read"}))
        with pytest.raises(AttributeError):
            scope.phase = "do"  # type: ignore[misc]

    def test_fields(self) -> None:
        """フィールドが正しく設定される。"""
        perms = frozenset({"contents:read", "issues:write"})
        scope = PhaseScope(phase="plan", permissions=perms)
        assert scope.phase == "plan"
        assert scope.permissions == perms


# ============================================================
# ScopeManager
# ============================================================


class TestScopeManager:
    """ScopeManager のテスト。"""

    def test_plan_scopes(self) -> None:
        """PLANフェーズのスコープ。"""
        mgr = ScopeManager()
        scopes = mgr.get_required_scopes(PDCAPhase.PLAN)
        assert scopes == {"contents:read", "issues:write", "pull_requests:read"}

    def test_do_scopes(self) -> None:
        """DOフェーズのスコープ。"""
        mgr = ScopeManager()
        scopes = mgr.get_required_scopes(PDCAPhase.DO)
        assert scopes == {"contents:write", "issues:write", "pull_requests:write"}

    def test_check_scopes(self) -> None:
        """CHECKフェーズのスコープ。"""
        mgr = ScopeManager()
        scopes = mgr.get_required_scopes(PDCAPhase.CHECK)
        assert scopes == {
            "contents:read",
            "issues:read",
            "pull_requests:read",
            "checks:read",
        }

    def test_act_scopes(self) -> None:
        """ACTフェーズのスコープ。"""
        mgr = ScopeManager()
        scopes = mgr.get_required_scopes(PDCAPhase.ACT)
        assert scopes == {"contents:read", "issues:write", "pull_requests:write"}

    def test_invalid_phase_raises(self) -> None:
        """不明なフェーズでValueError。"""
        mgr = ScopeManager()
        with pytest.raises(ValueError, match="不明なPDCAフェーズ"):
            mgr.get_required_scopes("invalid")

    def test_validate_scopes_pass(self) -> None:
        """十分なスコープがある場合はTrue。"""
        mgr = ScopeManager()
        current = {"contents:read", "issues:write", "pull_requests:read", "extra:perm"}
        required = {"contents:read", "issues:write"}
        assert mgr.validate_scopes(current, required) is True

    def test_validate_scopes_fail(self) -> None:
        """スコープ不足の場合はFalse。"""
        mgr = ScopeManager()
        current = {"contents:read"}
        required = {"contents:read", "issues:write"}
        assert mgr.validate_scopes(current, required) is False

    def test_validate_scopes_exact_match(self) -> None:
        """スコープが完全一致の場合はTrue。"""
        mgr = ScopeManager()
        scopes = {"contents:read", "issues:write"}
        assert mgr.validate_scopes(scopes, scopes) is True

    def test_validate_empty_required(self) -> None:
        """空の要求は常にTrue。"""
        mgr = ScopeManager()
        assert mgr.validate_scopes({"contents:read"}, set()) is True


# ============================================================
# TokenLeakDetector / LeakDetection
# ============================================================


class TestLeakDetection:
    """LeakDetection のテスト。"""

    def test_frozen(self) -> None:
        """LeakDetection は不変。"""
        d = LeakDetection(pattern_name="test", position=0, redacted_value="ghp_***")
        with pytest.raises(AttributeError):
            d.pattern_name = "other"  # type: ignore[misc]


class TestTokenLeakDetector:
    """TokenLeakDetector のテスト。"""

    def test_detect_ghp_token(self) -> None:
        """ghp_ トークンを検出する。"""
        detector = TokenLeakDetector()
        text = "token is ghp_ABCDEFghijklmnop1234567890ABCDEFGHIJKL"
        results = detector.scan_text(text)
        assert len(results) == 1
        assert results[0].pattern_name == "github_personal_access_token"
        assert results[0].redacted_value == "ghp_***"
        assert results[0].position == 9

    def test_detect_ghs_token(self) -> None:
        """ghs_ トークンを検出する。"""
        detector = TokenLeakDetector()
        text = "ghs_ABCDEFghijklmnop1234567890ABCDEFGHIJKL here"
        results = detector.scan_text(text)
        assert len(results) == 1
        assert results[0].pattern_name == "github_installation_token"

    def test_detect_github_pat(self) -> None:
        """github_pat_ トークンを検出する。"""
        detector = TokenLeakDetector()
        text = "github_pat_ABCDEFGHIJKLMNOPQRSTUV_extra1234567890"
        results = detector.scan_text(text)
        assert len(results) == 1
        assert results[0].pattern_name == "github_fine_grained_pat"
        assert results[0].redacted_value == "gith***"

    def test_detect_bearer_token(self) -> None:
        """Bearer トークンを検出する。"""
        detector = TokenLeakDetector()
        text = "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.test"
        results = detector.scan_text(text)
        assert len(results) >= 1
        bearer_results = [r for r in results if r.pattern_name == "bearer_token"]
        assert len(bearer_results) == 1
        assert bearer_results[0].redacted_value == "Bear***"

    def test_no_leak(self) -> None:
        """トークンがない場合は空リスト。"""
        detector = TokenLeakDetector()
        text = "This is a safe text with no tokens"
        results = detector.scan_text(text)
        assert results == []

    def test_multiple_leaks(self) -> None:
        """複数のトークンを検出する。"""
        detector = TokenLeakDetector()
        text = (
            "ghp_ABCDEFghijklmnop1234567890ABCDEFGHIJKLx "
            "ghs_ABCDEFghijklmnop1234567890ABCDEFGHIJKLy"
        )
        results = detector.scan_text(text)
        assert len(results) == 2
        names = {r.pattern_name for r in results}
        assert "github_personal_access_token" in names
        assert "github_installation_token" in names

    def test_detect_gho_token(self) -> None:
        """gho_ トークンを検出する。"""
        detector = TokenLeakDetector()
        text = "gho_ABCDEFghijklmnop1234567890ABCDEFGHIJKL"
        results = detector.scan_text(text)
        assert len(results) == 1
        assert results[0].pattern_name == "github_oauth_token"

    def test_detect_ghu_token(self) -> None:
        """ghu_ トークンを検出する。"""
        detector = TokenLeakDetector()
        text = "ghu_ABCDEFghijklmnop1234567890ABCDEFGHIJKL"
        results = detector.scan_text(text)
        assert len(results) == 1
        assert results[0].pattern_name == "github_user_to_server_token"

    def test_detect_ghr_token(self) -> None:
        """ghr_ トークンを検出する。"""
        detector = TokenLeakDetector()
        text = "ghr_ABCDEFghijklmnop1234567890ABCDEFGHIJKL"
        results = detector.scan_text(text)
        assert len(results) == 1
        assert results[0].pattern_name == "github_server_to_server_token"

    def test_short_value_redaction(self) -> None:
        """短い値のマスク処理。"""
        # _redact は staticmethod なので直接テスト
        assert TokenLeakDetector._redact("abc") == "***"
        assert TokenLeakDetector._redact("abcd") == "***"
        assert TokenLeakDetector._redact("abcde") == "abcd***"


# ============================================================
# AccessLogger / TokenAccessLog
# ============================================================


class TestTokenAccessLog:
    """TokenAccessLog のテスト。"""

    def test_fields(self) -> None:
        """フィールドが正しく設定される。"""
        entry = TokenAccessLog(
            endpoint="/repos/owner/repo",
            method="GET",
            status_code=200,
            timestamp=1000.0,
            duration_ms=42.5,
        )
        assert entry.endpoint == "/repos/owner/repo"
        assert entry.method == "GET"
        assert entry.status_code == 200
        assert entry.timestamp == 1000.0
        assert entry.duration_ms == 42.5


class TestAccessLogger:
    """AccessLogger のテスト。"""

    @staticmethod
    def _make_entry(
        status_code: int = 200,
        duration_ms: float = 50.0,
        endpoint: str = "/test",
    ) -> TokenAccessLog:
        return TokenAccessLog(
            endpoint=endpoint,
            method="GET",
            status_code=status_code,
            timestamp=time.time(),
            duration_ms=duration_ms,
        )

    def test_log_and_get_recent(self) -> None:
        """ログ記録と直近取得。"""
        logger = AccessLogger()
        e1 = self._make_entry(endpoint="/a")
        e2 = self._make_entry(endpoint="/b")
        e3 = self._make_entry(endpoint="/c")
        logger.log(e1)
        logger.log(e2)
        logger.log(e3)

        recent = logger.get_recent(2)
        assert len(recent) == 2
        # 新しい順
        assert recent[0].endpoint == "/c"
        assert recent[1].endpoint == "/b"

    def test_get_recent_more_than_available(self) -> None:
        """要求件数がログ数を超える場合。"""
        al = AccessLogger()
        al.log(self._make_entry())
        recent = al.get_recent(100)
        assert len(recent) == 1

    def test_summary_empty(self) -> None:
        """ログ空のサマリー。"""
        al = AccessLogger()
        summary = al.get_summary()
        assert summary["total_calls"] == 0
        assert summary["error_count"] == 0
        assert summary["error_rate"] == 0.0
        assert summary["avg_duration_ms"] == 0.0

    def test_summary_with_entries(self) -> None:
        """エントリありのサマリー。"""
        al = AccessLogger()
        al.log(self._make_entry(status_code=200, duration_ms=100.0))
        al.log(self._make_entry(status_code=201, duration_ms=200.0))
        al.log(self._make_entry(status_code=404, duration_ms=50.0))
        al.log(self._make_entry(status_code=500, duration_ms=150.0))

        summary = al.get_summary()
        assert summary["total_calls"] == 4
        assert summary["error_count"] == 2  # 404, 500
        assert summary["error_rate"] == 0.5
        assert summary["avg_duration_ms"] == 125.0

    def test_summary_no_errors(self) -> None:
        """エラーなしのサマリー。"""
        al = AccessLogger()
        al.log(self._make_entry(status_code=200, duration_ms=10.0))
        al.log(self._make_entry(status_code=201, duration_ms=20.0))

        summary = al.get_summary()
        assert summary["error_count"] == 0
        assert summary["error_rate"] == 0.0
        assert summary["avg_duration_ms"] == 15.0


class TestAccessLoggerThreadSafety:
    """AccessLogger の並行アクセステスト。"""

    @staticmethod
    def _make_entry(**kwargs: object) -> TokenAccessLog:
        defaults: dict[str, object] = {
            "method": "GET",
            "endpoint": "/repos",
            "status_code": 200,
            "timestamp": 1.0,
            "duration_ms": 10.0,
        }
        defaults.update(kwargs)
        return TokenAccessLog(**defaults)  # type: ignore[arg-type]

    def test_concurrent_log_no_data_loss(self) -> None:
        """複数スレッドからの同時logでデータが欠落しないこと。"""
        import threading

        al = AccessLogger()
        count_per_thread = 50

        def worker() -> None:
            for _ in range(count_per_thread):
                al.log(self._make_entry())

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        summary = al.get_summary()
        assert summary["total_calls"] == count_per_thread * 10


# ── スレッドセーフティ ──


class TestTokenRotationManagerThreadSafety:
    """TokenRotationManager の並行アクセスでデータが壊れない。"""

    def test_concurrent_set_token(self):
        import threading
        mgr = TokenRotationManager()
        errors: list[str] = []

        def set_tokens(tid: int):
            try:
                for i in range(50):
                    mgr.set_token(f"token-{tid}-{i}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=set_tokens, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # 最終的にトークンが設定されていること
        assert mgr.token is not None
        assert mgr.token.startswith("token-")

    def test_concurrent_rotate(self):
        import threading
        counter = {"value": 0}
        counter_lock = threading.Lock()
        mgr = TokenRotationManager()

        def factory():
            with counter_lock:
                counter["value"] += 1
                return f"token-{counter['value']}"

        errors: list[str] = []

        def rotate(tid: int):
            try:
                for _ in range(10):
                    mgr.rotate(factory)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=rotate, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert mgr.rotation_count == 40
