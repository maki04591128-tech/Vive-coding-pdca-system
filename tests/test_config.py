"""設定ローダーのユニットテスト。"""



from vibe_pdca.config.loader import (
    build_gateway_from_config,
    deep_merge,
    load_config,
    resolve_env_vars,
)
from vibe_pdca.llm.models import ProviderType


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


class TestBuildGatewayEnvOverride:
    """環境変数によるモード切替のテスト。"""

    def test_env_var_overrides_config_to_local(self, monkeypatch):
        """VIBE_PDCA_LLM_MODE=local が設定ファイルの cloud を上書きする。"""
        monkeypatch.setenv("VIBE_PDCA_LLM_MODE", "local")
        config = {"llm": {"preferred_mode": "cloud"}}
        gw = build_gateway_from_config(config)
        assert gw.preferred_mode == ProviderType.LOCAL

    def test_env_var_overrides_config_to_cloud(self, monkeypatch):
        """VIBE_PDCA_LLM_MODE=cloud が設定ファイルの local を上書きする。"""
        monkeypatch.setenv("VIBE_PDCA_LLM_MODE", "cloud")
        config = {"llm": {"preferred_mode": "local"}}
        gw = build_gateway_from_config(config)
        assert gw.preferred_mode == ProviderType.CLOUD

    def test_config_used_when_no_env_var(self, monkeypatch):
        """環境変数未設定時は設定ファイルの値が使われる。"""
        monkeypatch.delenv("VIBE_PDCA_LLM_MODE", raising=False)
        config = {"llm": {"preferred_mode": "local"}}
        gw = build_gateway_from_config(config)
        assert gw.preferred_mode == ProviderType.LOCAL

    def test_env_var_overrides_auto_fallback_false(self, monkeypatch):
        """VIBE_PDCA_LLM_AUTO_FALLBACK=false が自動フォールバックを無効化する。"""
        monkeypatch.setenv("VIBE_PDCA_LLM_AUTO_FALLBACK", "false")
        config = {"llm": {"auto_fallback": True}}
        gw = build_gateway_from_config(config)
        assert gw.auto_fallback_enabled is False

    def test_env_var_overrides_auto_fallback_true(self, monkeypatch):
        """VIBE_PDCA_LLM_AUTO_FALLBACK=true が自動フォールバックを有効化する。"""
        monkeypatch.setenv("VIBE_PDCA_LLM_AUTO_FALLBACK", "true")
        config = {"llm": {"auto_fallback": False}}
        gw = build_gateway_from_config(config)
        assert gw.auto_fallback_enabled is True


class TestBuildGatewayLocalLLMOverride:
    """環境変数によるローカルLLMモデル差し替えのテスト。"""

    def _config_with_local_provider(self):
        return {
            "llm": {
                "local_providers": [
                    {
                        "name": "ollama-default",
                        "model": "llama3.3:70b",
                        "base_url": "http://localhost:11434/v1",
                        "timeout": 300.0,
                        "roles": ["pm"],
                    },
                ],
            },
        }

    def test_env_var_overrides_local_model(self, monkeypatch):
        """VIBE_PDCA_LOCAL_LLM_MODEL が全ローカルプロバイダのモデルを上書きする。"""
        monkeypatch.setenv("VIBE_PDCA_LOCAL_LLM_MODEL", "deepseek-r1:70b")
        config = self._config_with_local_provider()
        gw = build_gateway_from_config(config)
        provider = gw._local_providers["ollama-default"]
        assert provider.model == "deepseek-r1:70b"

    def test_env_var_overrides_local_base_url(self, monkeypatch):
        """VIBE_PDCA_LOCAL_LLM_BASE_URL が全ローカルプロバイダのURLを上書きする。"""
        monkeypatch.setenv("VIBE_PDCA_LOCAL_LLM_BASE_URL", "http://localhost:8000/v1")
        config = self._config_with_local_provider()
        gw = build_gateway_from_config(config)
        provider = gw._local_providers["ollama-default"]
        assert provider.base_url == "http://localhost:8000/v1"

    def test_config_used_when_no_env_var(self, monkeypatch):
        """環境変数未設定時は設定ファイルのモデル名が使われる。"""
        monkeypatch.delenv("VIBE_PDCA_LOCAL_LLM_MODEL", raising=False)
        monkeypatch.delenv("VIBE_PDCA_LOCAL_LLM_BASE_URL", raising=False)
        config = self._config_with_local_provider()
        gw = build_gateway_from_config(config)
        provider = gw._local_providers["ollama-default"]
        assert provider.model == "llama3.3:70b"
        assert provider.base_url == "http://localhost:11434/v1"

    def test_env_var_overrides_multiple_providers(self, monkeypatch):
        """複数ローカルプロバイダがある場合、全てのモデルが上書きされる。"""
        monkeypatch.setenv("VIBE_PDCA_LOCAL_LLM_MODEL", "qwen3:72b")
        config = {
            "llm": {
                "local_providers": [
                    {"name": "ollama-1", "model": "llama3.3:70b", "roles": ["pm"]},
                    {"name": "ollama-2", "model": "qwen2.5:32b", "roles": ["scribe"]},
                ],
            },
        }
        gw = build_gateway_from_config(config)
        assert gw._local_providers["ollama-1"].model == "qwen3:72b"
        assert gw._local_providers["ollama-2"].model == "qwen3:72b"


class TestBuildGatewayLocalLLMPerRoleOverride:
    """役割別環境変数によるローカルLLMモデル差し替えのテスト。"""

    def _config_with_role_providers(self):
        return {
            "llm": {
                "local_providers": [
                    {"name": "ollama-pm", "model": "qwen3:72b", "roles": ["pm"]},
                    {
                        "name": "ollama-programmer",
                        "model": "codestral:22b",
                        "roles": ["programmer"],
                    },
                    {"name": "ollama-designer", "model": "llama3.3:70b", "roles": ["designer"]},
                ],
            },
        }

    def test_per_role_env_var_overrides_specific_provider(self, monkeypatch):
        """VIBE_PDCA_LOCAL_LLM_MODEL_PM がPM役割のプロバイダのみ上書きする。"""
        monkeypatch.setenv("VIBE_PDCA_LOCAL_LLM_MODEL_PM", "deepseek-r1:70b")
        config = self._config_with_role_providers()
        gw = build_gateway_from_config(config)
        assert gw._local_providers["ollama-pm"].model == "deepseek-r1:70b"
        assert gw._local_providers["ollama-programmer"].model == "codestral:22b"
        assert gw._local_providers["ollama-designer"].model == "llama3.3:70b"

    def test_per_role_env_var_overrides_multiple_roles(self, monkeypatch):
        """複数の役割別環境変数がそれぞれのプロバイダを上書きする。"""
        monkeypatch.setenv("VIBE_PDCA_LOCAL_LLM_MODEL_PM", "deepseek-r1:70b")
        monkeypatch.setenv("VIBE_PDCA_LOCAL_LLM_MODEL_PROGRAMMER", "qwen2.5-coder:32b")
        config = self._config_with_role_providers()
        gw = build_gateway_from_config(config)
        assert gw._local_providers["ollama-pm"].model == "deepseek-r1:70b"
        assert gw._local_providers["ollama-programmer"].model == "qwen2.5-coder:32b"
        assert gw._local_providers["ollama-designer"].model == "llama3.3:70b"

    def test_per_role_env_var_takes_precedence_over_global(self, monkeypatch):
        """役割別環境変数が一括環境変数より優先される。"""
        monkeypatch.setenv("VIBE_PDCA_LOCAL_LLM_MODEL", "gemma3:27b")
        monkeypatch.setenv("VIBE_PDCA_LOCAL_LLM_MODEL_PM", "deepseek-r1:70b")
        config = self._config_with_role_providers()
        gw = build_gateway_from_config(config)
        # PM: 役割別環境変数が優先
        assert gw._local_providers["ollama-pm"].model == "deepseek-r1:70b"
        # PROGRAMMER: 役割別未設定なので一括環境変数が適用
        assert gw._local_providers["ollama-programmer"].model == "gemma3:27b"
        # DESIGNER: 役割別未設定なので一括環境変数が適用
        assert gw._local_providers["ollama-designer"].model == "gemma3:27b"

    def test_global_env_var_used_when_no_per_role(self, monkeypatch):
        """役割別環境変数が未設定の場合、一括環境変数が適用される。"""
        monkeypatch.setenv("VIBE_PDCA_LOCAL_LLM_MODEL", "gemma3:27b")
        config = self._config_with_role_providers()
        gw = build_gateway_from_config(config)
        assert gw._local_providers["ollama-pm"].model == "gemma3:27b"
        assert gw._local_providers["ollama-programmer"].model == "gemma3:27b"
        assert gw._local_providers["ollama-designer"].model == "gemma3:27b"

    def test_config_used_when_no_env_vars(self, monkeypatch):
        """環境変数が未設定の場合、設定ファイルのモデル名が使われる。"""
        monkeypatch.delenv("VIBE_PDCA_LOCAL_LLM_MODEL", raising=False)
        monkeypatch.delenv("VIBE_PDCA_LOCAL_LLM_MODEL_PM", raising=False)
        monkeypatch.delenv("VIBE_PDCA_LOCAL_LLM_MODEL_PROGRAMMER", raising=False)
        monkeypatch.delenv("VIBE_PDCA_LOCAL_LLM_MODEL_DESIGNER", raising=False)
        config = self._config_with_role_providers()
        gw = build_gateway_from_config(config)
        assert gw._local_providers["ollama-pm"].model == "qwen3:72b"
        assert gw._local_providers["ollama-programmer"].model == "codestral:22b"
        assert gw._local_providers["ollama-designer"].model == "llama3.3:70b"
