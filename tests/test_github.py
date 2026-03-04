"""GitHub連携基盤のユニットテスト。

M0 タスク 0-5: GitHub App認証テスト。
M1 タスク 1-2: GitHubステートストアCRUD・ラベル・状態復元テスト。
"""

import pytest

from vibe_pdca.github import (
    STANDARD_LABELS,
    GitHubAppAuth,
    GitHubAppConfig,
    GitHubStateStore,
    IssueState,
    LabelPrefix,
    StateEntry,
)

# ============================================================
# GitHub App認証テスト（M0 タスク 0-5）
# ============================================================


class TestGitHubAppAuth:
    def test_generate_jwt_requires_app_id(self):
        auth = GitHubAppAuth(GitHubAppConfig())
        with pytest.raises(ValueError, match="App ID"):
            auth.generate_jwt()

    def test_generate_jwt_requires_private_key(self):
        auth = GitHubAppAuth(GitHubAppConfig(app_id="123"))
        with pytest.raises(ValueError, match="Private Key"):
            auth.generate_jwt()

    def test_generate_jwt_returns_string(self):
        auth = GitHubAppAuth(
            GitHubAppConfig(app_id="123", private_key="test-key")
        )
        jwt = auth.generate_jwt()
        assert isinstance(jwt, str)
        assert "123" in jwt

    def test_get_installation_token_requires_id(self):
        auth = GitHubAppAuth(
            GitHubAppConfig(app_id="123", private_key="key")
        )
        with pytest.raises(ValueError, match="Installation ID"):
            auth.get_installation_token()

    def test_get_installation_token_caching(self):
        auth = GitHubAppAuth(
            GitHubAppConfig(
                app_id="123",
                private_key="key",
                installation_id="456",
            )
        )
        token1 = auth.get_installation_token()
        token2 = auth.get_installation_token()
        assert token1 == token2  # キャッシュされた同一トークン

    def test_app_id_property(self):
        auth = GitHubAppAuth(GitHubAppConfig(app_id="my-app"))
        assert auth.app_id == "my-app"

    def test_verify_webhook_without_secret(self):
        auth = GitHubAppAuth(GitHubAppConfig())
        assert auth.verify_webhook_signature(b"payload", "sig") is False


# ============================================================
# GitHubステートストア CRUD テスト（M1 タスク 1-2）
# ============================================================


@pytest.fixture
def store():
    return GitHubStateStore(owner="test-owner", repo="test-repo")


class TestStateStoreCreate:
    def test_create_issue(self, store):
        entry = store.create_issue("テストIssue", body="本文")
        assert entry.number == 1
        assert entry.title == "テストIssue"
        assert entry.body == "本文"
        assert entry.state == IssueState.OPEN
        assert store.entry_count == 1

    def test_create_multiple_issues(self, store):
        e1 = store.create_issue("Issue 1")
        e2 = store.create_issue("Issue 2")
        assert e1.number == 1
        assert e2.number == 2
        assert store.entry_count == 2

    def test_create_issue_with_labels(self, store):
        entry = store.create_issue(
            "Issue with labels",
            labels=["phase/plan", "priority/high"],
        )
        assert "phase/plan" in entry.labels
        assert "priority/high" in entry.labels

    def test_create_milestone(self, store):
        ms = store.create_milestone("M1: 仕様と骨格", description="M1の説明")
        assert ms.title == "M1: 仕様と骨格"
        assert "type/milestone" in ms.labels


class TestStateStoreRead:
    def test_get_existing_issue(self, store):
        store.create_issue("テスト")
        entry = store.get_issue(1)
        assert entry is not None
        assert entry.title == "テスト"

    def test_get_nonexistent_issue(self, store):
        assert store.get_issue(999) is None

    def test_list_all_issues(self, store):
        store.create_issue("Issue 1")
        store.create_issue("Issue 2")
        issues = store.list_issues()
        assert len(issues) == 2

    def test_list_issues_by_state(self, store):
        store.create_issue("Open Issue")
        store.create_issue("Closed Issue")
        store.close_issue(2)
        open_issues = store.list_issues(state=IssueState.OPEN)
        assert len(open_issues) == 1
        assert open_issues[0].title == "Open Issue"

    def test_list_issues_by_labels(self, store):
        store.create_issue("High", labels=["priority/high"])
        store.create_issue("Low", labels=["priority/low"])
        high = store.list_issues(labels=["priority/high"])
        assert len(high) == 1
        assert high[0].title == "High"


class TestStateStoreUpdate:
    def test_update_title(self, store):
        store.create_issue("Old Title")
        updated = store.update_issue(1, title="New Title")
        assert updated.title == "New Title"

    def test_update_body(self, store):
        store.create_issue("Issue", body="old body")
        updated = store.update_issue(1, body="new body")
        assert updated.body == "new body"

    def test_update_nonexistent_raises(self, store):
        with pytest.raises(KeyError, match="#999"):
            store.update_issue(999, title="nope")

    def test_close_issue(self, store):
        store.create_issue("To Close")
        closed = store.close_issue(1)
        assert closed.state == IssueState.CLOSED


# ============================================================
# ラベル自動適用テスト
# ============================================================


class TestLabelApplication:
    def test_apply_phase_label(self, store):
        store.create_issue("Cycle Issue", labels=["phase/plan"])
        updated = store.apply_phase_label(1, "do")
        assert "phase/do" in updated.labels
        assert "phase/plan" not in updated.labels

    def test_apply_phase_label_exclusive(self, store):
        """フェーズラベルは排他的に切り替わる。"""
        store.create_issue("Issue", labels=["phase/plan", "priority/high"])
        store.apply_phase_label(1, "check")
        entry = store.get_issue(1)
        assert entry is not None
        phase_labels = [lbl for lbl in entry.labels if lbl.startswith("phase/")]
        assert len(phase_labels) == 1
        assert phase_labels[0] == "phase/check"
        assert "priority/high" in entry.labels  # 他のラベルは保持

    def test_apply_status_label(self, store):
        store.create_issue("Issue", labels=["status/running"])
        updated = store.apply_status_label(1, "completed")
        assert "status/completed" in updated.labels
        assert "status/running" not in updated.labels

    def test_apply_label_nonexistent_raises(self, store):
        with pytest.raises(KeyError):
            store.apply_phase_label(999, "plan")


# ============================================================
# 状態復元テスト
# ============================================================


class TestStateRestore:
    def test_restore_state(self, store):
        entries = [
            StateEntry(number=10, title="Restored 1"),
            StateEntry(number=20, title="Restored 2"),
        ]
        count = store.restore_state(entries)
        assert count == 2
        assert store.entry_count == 2
        assert store.get_issue(10) is not None

    def test_restore_updates_next_number(self, store):
        """復元後の次番号は、最大番号+1になる。"""
        store.restore_state([StateEntry(number=100, title="High Number")])
        new_entry = store.create_issue("New Issue After Restore")
        assert new_entry.number == 101


# ============================================================
# ステータス
# ============================================================


class TestStateStoreStatus:
    def test_get_status(self, store):
        store.create_issue("Open")
        store.create_issue("Closed")
        store.close_issue(2)
        status = store.get_status()
        assert status["owner"] == "test-owner"
        assert status["repo"] == "test-repo"
        assert status["total_entries"] == 2
        assert status["open"] == 1
        assert status["closed"] == 1

    def test_standard_labels_exist(self):
        """標準ラベルセットが定義されていること。"""
        assert "phase/plan" in STANDARD_LABELS
        assert "phase/do" in STANDARD_LABELS
        assert "phase/check" in STANDARD_LABELS
        assert "phase/act" in STANDARD_LABELS
        assert "governance/a" in STANDARD_LABELS

    def test_label_prefix_enum(self):
        assert LabelPrefix.PHASE == "phase/"
        assert LabelPrefix.STATUS == "status/"
        assert LabelPrefix.GOVERNANCE == "governance/"
