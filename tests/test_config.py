"""設定ローダーのユニットテスト。"""



from vibe_pdca.config.loader import deep_merge, load_config, resolve_env_vars


class TestDeepMerge:
    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        assert deep_merge(base, override) == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"llm": {"mode": "cloud", "cost": {"limit": 30}}}
        override = {"llm": {"mode": "local"}}
        result = deep_merge(base, override)
        assert result["llm"]["mode"] == "local"
        assert result["llm"]["cost"]["limit"] == 30

    def test_override_replaces_non_dict(self):
        base = {"a": [1, 2]}
        override = {"a": [3, 4]}
        assert deep_merge(base, override) == {"a": [3, 4]}


class TestResolveEnvVars:
    def test_resolves_env_var(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "secret123")
        result = resolve_env_vars({"api_key": "${TEST_KEY}"})
        assert result["api_key"] == "secret123"

    def test_keeps_placeholder_if_missing(self):
        result = resolve_env_vars({"api_key": "${NONEXISTENT_KEY}"})
        assert result["api_key"] == "${NONEXISTENT_KEY}"

    def test_resolves_nested(self, monkeypatch):
        monkeypatch.setenv("NESTED_VAL", "deep")
        result = resolve_env_vars({"outer": {"inner": "${NESTED_VAL}"}})
        assert result["outer"]["inner"] == "deep"


class TestLoadConfig:
    def test_loads_default_yml(self, tmp_path):
        (tmp_path / "default.yml").write_text("llm:\n  mode: cloud\n")
        config = load_config(config_dir=tmp_path)
        assert config["llm"]["mode"] == "cloud"

    def test_env_override(self, tmp_path):
        (tmp_path / "default.yml").write_text("llm:\n  mode: cloud\n")
        env_dir = tmp_path / "environments"
        env_dir.mkdir()
        (env_dir / "dev.yml").write_text("llm:\n  mode: local\n")
        config = load_config(config_dir=tmp_path, env="dev")
        assert config["llm"]["mode"] == "local"
