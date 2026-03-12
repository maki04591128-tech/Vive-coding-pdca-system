"""設定ホットリロードとバージョン管理のユニットテスト。"""

from __future__ import annotations

import time

import yaml

from vibe_pdca.config.hot_reload import (
    ApplyMode,
    ConfigDiff,
    ConfigValidator,
    ConfigVersion,
    ConfigVersionStore,
    HotReloadManager,
)


class TestConfigVersion:
    """ConfigVersion データクラスのテスト。"""

    def test_create_version(self):
        """バージョン情報が正しく保持されること。"""
        snapshot = {"llm": {"mode": "cloud"}}
        cv = ConfigVersion(version=1, timestamp=1000.0, snapshot=snapshot, description="初期")
        assert cv.version == 1
        assert cv.timestamp == 1000.0
        assert cv.snapshot == {"llm": {"mode": "cloud"}}
        assert cv.description == "初期"

    def test_frozen(self):
        """frozen=True により属性変更が禁止されること。"""
        cv = ConfigVersion(version=1, timestamp=0.0, snapshot={}, description="")
        try:
            cv.version = 2  # type: ignore[misc]
            raise AssertionError("FrozenInstanceError が発生するべき")
        except AttributeError:
            pass

    def test_default_description(self):
        """description のデフォルト値が空文字列であること。"""
        cv = ConfigVersion(version=1, timestamp=0.0, snapshot={})
        assert cv.description == ""


class TestConfigDiff:
    """ConfigDiff のテスト。"""

    def test_no_changes(self):
        """同一辞書なら変更なし。"""
        diff = ConfigDiff.compute({"a": 1}, {"a": 1})
        assert not diff.has_changes
        assert diff.added == {}
        assert diff.removed == {}
        assert diff.changed == {}

    def test_added_keys(self):
        """新規キーが added に含まれること。"""
        diff = ConfigDiff.compute({}, {"a": 1, "b": 2})
        assert diff.added == {"a": 1, "b": 2}
        assert diff.removed == {}
        assert diff.changed == {}

    def test_removed_keys(self):
        """削除されたキーが removed に含まれること。"""
        diff = ConfigDiff.compute({"a": 1, "b": 2}, {})
        assert diff.removed == {"a": 1, "b": 2}
        assert diff.added == {}
        assert diff.changed == {}

    def test_changed_keys(self):
        """値が変更されたキーが changed に含まれること。"""
        diff = ConfigDiff.compute({"a": 1, "b": "old"}, {"a": 2, "b": "new"})
        assert diff.changed == {"a": (1, 2), "b": ("old", "new")}

    def test_mixed_diff(self):
        """追加・削除・変更が混在する差分。"""
        old = {"keep": 1, "change": "a", "remove": True}
        new = {"keep": 1, "change": "b", "add": 42}
        diff = ConfigDiff.compute(old, new)
        assert diff.added == {"add": 42}
        assert diff.removed == {"remove": True}
        assert diff.changed == {"change": ("a", "b")}

    def test_format_no_changes(self):
        """変更なしのフォーマット。"""
        diff = ConfigDiff.compute({"a": 1}, {"a": 1})
        assert diff.format() == "(変更なし)"

    def test_format_with_changes(self):
        """差分フォーマットに +, -, ~ 記号が含まれること。"""
        diff = ConfigDiff.compute({"old": 1}, {"new": 2})
        fmt = diff.format()
        assert "+ new:" in fmt
        assert "- old:" in fmt

    def test_has_changes_true(self):
        diff = ConfigDiff.compute({"a": 1}, {"a": 2})
        assert diff.has_changes is True


class TestConfigValidator:
    """ConfigValidator のテスト。"""

    def test_valid_config(self):
        """バリデーション成功時は空リストを返すこと。"""
        validator = ConfigValidator(required_fields=["llm"])
        errors = validator.validate({"llm": {"mode": "cloud"}})
        assert errors == []

    def test_missing_required_field(self):
        """必須フィールドが欠けている場合のエラー。"""
        validator = ConfigValidator(required_fields=["llm", "monitoring"])
        errors = validator.validate({"llm": {}})
        assert len(errors) == 1
        assert "monitoring" in errors[0]

    def test_numeric_range_valid(self):
        """数値範囲内の値は検証成功。"""
        validator = ConfigValidator(
            required_fields=[],
            numeric_ranges={"llm.cost.daily_limit_usd": (0.0, 100.0)},
        )
        config = {"llm": {"cost": {"daily_limit_usd": 30.0}}}
        assert validator.validate(config) == []

    def test_numeric_range_out_of_bounds(self):
        """数値が範囲外の場合のエラー。"""
        validator = ConfigValidator(
            required_fields=[],
            numeric_ranges={"llm.cost.daily_limit_usd": (0.0, 100.0)},
        )
        config = {"llm": {"cost": {"daily_limit_usd": 200.0}}}
        errors = validator.validate(config)
        assert len(errors) == 1
        assert "範囲" in errors[0]

    def test_numeric_range_wrong_type(self):
        """数値フィールドに文字列が入っている場合のエラー。"""
        validator = ConfigValidator(
            required_fields=[],
            numeric_ranges={"value": (0.0, 10.0)},
        )
        errors = validator.validate({"value": "not_a_number"})
        assert len(errors) == 1
        assert "数値" in errors[0]

    def test_numeric_range_missing_key(self):
        """数値フィールドが存在しない場合はスキップ。"""
        validator = ConfigValidator(
            required_fields=[],
            numeric_ranges={"missing.key": (0.0, 10.0)},
        )
        assert validator.validate({}) == []

    def test_provider_list_valid(self):
        """空でないリストは検証成功。"""
        validator = ConfigValidator(
            required_fields=[],
            provider_list_fields=["llm.cloud_providers"],
        )
        config = {"llm": {"cloud_providers": [{"name": "test"}]}}
        assert validator.validate(config) == []

    def test_provider_list_empty(self):
        """空リストの場合のエラー。"""
        validator = ConfigValidator(
            required_fields=[],
            provider_list_fields=["llm.cloud_providers"],
        )
        config = {"llm": {"cloud_providers": []}}
        errors = validator.validate(config)
        assert len(errors) == 1
        assert "空でないリスト" in errors[0]

    def test_provider_list_missing_key(self):
        """プロバイダリストが存在しない場合はスキップ。"""
        validator = ConfigValidator(
            required_fields=[],
            provider_list_fields=["llm.cloud_providers"],
        )
        assert validator.validate({}) == []

    def test_default_required_fields(self):
        """デフォルト必須フィールドが 'llm' であること。"""
        validator = ConfigValidator()
        errors = validator.validate({})
        assert len(errors) == 1
        assert "llm" in errors[0]

    def test_combined_validation(self):
        """複数のバリデーションルールの組み合わせ。"""
        validator = ConfigValidator(
            required_fields=["llm"],
            numeric_ranges={"llm.timeout": (1.0, 600.0)},
            provider_list_fields=["llm.providers"],
        )
        config = {"llm": {"timeout": 9999.0, "providers": []}}
        errors = validator.validate(config)
        assert len(errors) == 2


class TestConfigVersionStore:
    """ConfigVersionStore のテスト。"""

    def test_add_version(self):
        """バージョンの追加と取得。"""
        store = ConfigVersionStore()
        v = store.add({"key": "value"}, description="テスト")
        assert v.version == 1
        assert v.snapshot == {"key": "value"}
        assert v.description == "テスト"

    def test_current_returns_latest(self):
        """current が最新バージョンを返すこと。"""
        store = ConfigVersionStore()
        store.add({"v": 1})
        store.add({"v": 2})
        assert store.current is not None
        assert store.current.snapshot == {"v": 2}

    def test_current_returns_none_when_empty(self):
        """履歴が空の場合 current は None。"""
        store = ConfigVersionStore()
        assert store.current is None

    def test_get_version(self):
        """指定バージョンの取得。"""
        store = ConfigVersionStore()
        store.add({"v": 1})
        store.add({"v": 2})
        v1 = store.get(1)
        assert v1 is not None
        assert v1.snapshot == {"v": 1}

    def test_get_nonexistent_version(self):
        """存在しないバージョンは None を返す。"""
        store = ConfigVersionStore()
        assert store.get(999) is None

    def test_max_history(self):
        """max_history を超えた場合に古いバージョンが削除されること。"""
        store = ConfigVersionStore(max_history=3)
        for i in range(5):
            store.add({"v": i})
        assert len(store.history) == 3
        # 最古のバージョンが削除されている
        assert store.get(1) is None
        assert store.get(2) is None
        assert store.get(3) is not None

    def test_rollback(self):
        """ロールバックで過去のスナップショットが新バージョンとして復元されること。"""
        store = ConfigVersionStore()
        store.add({"mode": "cloud"}, description="v1")
        store.add({"mode": "local"}, description="v2")

        restored = store.rollback(1)
        assert restored is not None
        assert restored.snapshot == {"mode": "cloud"}
        assert restored.version == 3
        assert "ロールバック" in restored.description

    def test_rollback_nonexistent(self):
        """存在しないバージョンへのロールバックは None を返す。"""
        store = ConfigVersionStore()
        assert store.rollback(999) is None

    def test_history_returns_copy(self):
        """history プロパティがコピーを返すこと。"""
        store = ConfigVersionStore()
        store.add({"v": 1})
        h = store.history
        h.clear()
        assert len(store.history) == 1

    def test_snapshot_is_deep_copied(self):
        """保存されたスナップショットが元の辞書と独立していること。"""
        store = ConfigVersionStore()
        original = {"nested": {"key": "value"}}
        store.add(original)
        original["nested"]["key"] = "modified"
        assert store.current is not None
        assert store.current.snapshot["nested"]["key"] == "value"

    def test_custom_timestamp(self):
        """カスタムタイムスタンプが使用されること。"""
        store = ConfigVersionStore()
        v = store.add({"v": 1}, timestamp=12345.0)
        assert v.timestamp == 12345.0


class TestHotReloadManager:
    """HotReloadManager のテスト。"""

    def test_load_initial(self, tmp_path):
        """初回読み込みが正しく動作すること。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"llm": {"mode": "cloud"}}))

        manager = HotReloadManager(cfg_file)
        config = manager.load_initial()
        assert config == {"llm": {"mode": "cloud"}}
        assert manager.version_store.current is not None
        assert manager.version_store.current.version == 1

    def test_check_no_change(self, tmp_path):
        """変更がない場合 False を返すこと。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"key": "value"}))

        manager = HotReloadManager(cfg_file)
        manager.load_initial()
        assert manager.check_for_changes() is False

    def test_check_detects_change(self, tmp_path):
        """ファイル変更を検知すること。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"key": "old"}))

        manager = HotReloadManager(cfg_file)
        manager.load_initial()

        # mtime を進めるために少し待ってから書き換え
        time.sleep(0.1)
        cfg_file.write_text(yaml.dump({"key": "new"}))

        assert manager.check_for_changes() is True
        assert manager.current_config == {"key": "new"}

    def test_immediate_apply(self, tmp_path):
        """IMMEDIATE モードで変更が即座に適用されること。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"v": 1}))

        manager = HotReloadManager(cfg_file, apply_mode=ApplyMode.IMMEDIATE)
        manager.load_initial()

        time.sleep(0.1)
        cfg_file.write_text(yaml.dump({"v": 2}))
        manager.check_for_changes()

        assert manager.current_config == {"v": 2}
        assert manager.version_store.current is not None
        assert manager.version_store.current.version == 2

    def test_deferred_apply(self, tmp_path):
        """DEFERRED モードで変更が遅延適用されること。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"v": 1}))

        manager = HotReloadManager(cfg_file, apply_mode=ApplyMode.DEFERRED)
        manager.load_initial()

        time.sleep(0.1)
        cfg_file.write_text(yaml.dump({"v": 2}))
        manager.check_for_changes()

        # まだ適用されていない
        assert manager.current_config == {"v": 1}
        assert manager.has_pending is True

        # サイクル開始時に適用
        assert manager.apply_pending() is True
        assert manager.current_config == {"v": 2}
        assert manager.has_pending is False

    def test_apply_pending_when_no_pending(self, tmp_path):
        """pending がない場合 apply_pending は False を返すこと。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"v": 1}))

        manager = HotReloadManager(cfg_file)
        manager.load_initial()
        assert manager.apply_pending() is False

    def test_callback_called_on_change(self, tmp_path):
        """変更時にコールバックが呼ばれること。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"v": 1}))

        received: list[tuple] = []

        def on_change(config, diff):
            received.append((config, diff))

        manager = HotReloadManager(cfg_file)
        manager.register_callback(on_change)
        manager.load_initial()

        time.sleep(0.1)
        cfg_file.write_text(yaml.dump({"v": 2}))
        manager.check_for_changes()

        assert len(received) == 1
        assert received[0][0] == {"v": 2}
        assert received[0][1].has_changes

    def test_callback_error_does_not_crash(self, tmp_path):
        """コールバックでエラーが発生してもクラッシュしないこと。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"v": 1}))

        def bad_callback(config, diff):
            raise RuntimeError("callback error")

        manager = HotReloadManager(cfg_file)
        manager.register_callback(bad_callback)
        manager.load_initial()

        time.sleep(0.1)
        cfg_file.write_text(yaml.dump({"v": 2}))
        # エラーが発生してもクラッシュしない
        manager.check_for_changes()

    def test_validation_rejects_invalid_config(self, tmp_path):
        """バリデーション失敗時に設定が適用されないこと。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"llm": {"mode": "cloud"}}))

        validator = ConfigValidator(required_fields=["llm", "monitoring"])
        manager = HotReloadManager(cfg_file, validator=validator)
        # 初回読み込みはバリデーションしない
        manager.load_initial()

        time.sleep(0.1)
        cfg_file.write_text(yaml.dump({"llm": {"mode": "local"}}))
        # monitoring が欠けているので適用されない
        result = manager.check_for_changes()
        assert result is False
        assert manager.current_config == {"llm": {"mode": "cloud"}}

    def test_rollback(self, tmp_path):
        """HotReloadManager 経由のロールバック。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"v": 1}))

        manager = HotReloadManager(cfg_file)
        manager.load_initial()

        time.sleep(0.1)
        cfg_file.write_text(yaml.dump({"v": 2}))
        manager.check_for_changes()

        restored = manager.rollback(1)
        assert restored == {"v": 1}

    def test_rollback_nonexistent(self, tmp_path):
        """存在しないバージョンへのロールバックは None。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"v": 1}))

        manager = HotReloadManager(cfg_file)
        manager.load_initial()
        assert manager.rollback(999) is None

    def test_missing_file_returns_false(self, tmp_path):
        """設定ファイルが存在しない場合 check_for_changes は False。"""
        cfg_file = tmp_path / "nonexistent.yml"
        manager = HotReloadManager(cfg_file)
        assert manager.check_for_changes() is False

    def test_apply_mode_property(self, tmp_path):
        """apply_mode の getter/setter。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"v": 1}))

        manager = HotReloadManager(cfg_file, apply_mode=ApplyMode.IMMEDIATE)
        assert manager.apply_mode == ApplyMode.IMMEDIATE
        manager.apply_mode = ApplyMode.DEFERRED
        assert manager.apply_mode == ApplyMode.DEFERRED

    def test_current_config_none_before_load(self, tmp_path):
        """load_initial 前は current_config が None であること。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"v": 1}))
        manager = HotReloadManager(cfg_file)
        assert manager.current_config is None

    def test_current_config_is_deep_copy(self, tmp_path):
        """current_config が深いコピーを返すこと。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"nested": {"key": "value"}}))

        manager = HotReloadManager(cfg_file)
        manager.load_initial()

        config = manager.current_config
        assert config is not None
        config["nested"]["key"] = "modified"
        assert manager.current_config == {"nested": {"key": "value"}}

    def test_start_stop_polling(self, tmp_path):
        """ポーリングの開始と停止が正常に動作すること。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"v": 1}))

        manager = HotReloadManager(cfg_file, poll_interval=0.05)
        manager.load_initial()
        manager.start_polling()

        # ポーリングスレッドが動作中であること
        assert manager._running is True
        assert manager._poll_thread is not None
        assert manager._poll_thread.is_alive()

        manager.stop_polling()
        assert manager._running is False

    def test_polling_detects_change(self, tmp_path):
        """ポーリングによるファイル変更検知。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"v": 1}))

        received: list[dict] = []

        def on_change(config, diff):
            received.append(config)

        manager = HotReloadManager(cfg_file, poll_interval=0.05)
        manager.register_callback(on_change)
        manager.load_initial()
        manager.start_polling()

        try:
            time.sleep(0.1)
            cfg_file.write_text(yaml.dump({"v": 2}))
            # ポーリングが検知するまで待つ
            time.sleep(0.3)
        finally:
            manager.stop_polling()

        assert len(received) >= 1
        assert received[-1] == {"v": 2}

    def test_rollback_triggers_callback(self, tmp_path):
        """ロールバック時にコールバックが呼ばれること。"""
        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"v": 1}))

        received: list[tuple] = []

        def on_change(config, diff):
            received.append((config, diff))

        manager = HotReloadManager(cfg_file)
        manager.register_callback(on_change)
        manager.load_initial()

        time.sleep(0.1)
        cfg_file.write_text(yaml.dump({"v": 2}))
        manager.check_for_changes()

        received.clear()
        manager.rollback(1)
        assert len(received) == 1
        assert received[0][0] == {"v": 1}


class TestHotReloadThreadSafety:
    """HotReloadManager のスレッドセーフティテスト。"""

    def test_concurrent_apply_mode_toggle(self, tmp_path):
        """複数スレッドから apply_mode を同時切替しても例外が発生しないこと。"""
        import threading

        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"llm": {"mode": "local"}}))
        manager = HotReloadManager(cfg_file)
        manager.load_initial()

        errors: list[Exception] = []
        lock = threading.Lock()

        def toggle_mode() -> None:
            try:
                for _ in range(50):
                    manager.apply_mode = ApplyMode.DEFERRED
                    _ = manager.apply_mode
                    manager.apply_mode = ApplyMode.IMMEDIATE
                    _ = manager.apply_mode
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=toggle_mode) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert manager.apply_mode in (ApplyMode.IMMEDIATE, ApplyMode.DEFERRED)

    def test_concurrent_has_pending_and_apply_mode_barrier(self, tmp_path):
        """Barrier同期で全スレッドが同時にhas_pendingとapply_modeを呼び出す。"""
        import threading

        cfg_file = tmp_path / "config.yml"
        cfg_file.write_text(yaml.dump({"llm": {"mode": "local"}}))
        manager = HotReloadManager(cfg_file)
        manager.load_initial()
        n_threads = 10
        ops_per_thread = 10
        barrier = threading.Barrier(n_threads)
        errors: list[Exception] = []

        def worker(tid: int) -> None:
            barrier.wait()
            try:
                for _ in range(ops_per_thread):
                    _ = manager.has_pending
                    _ = manager.apply_mode
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(t,)) for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
