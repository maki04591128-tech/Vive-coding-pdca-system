"""設定管理 – YAML 階層マージ・バリデーション。

§17.5 ポリシー階層準拠:
  グローバル(config/default.yml)
    → 環境別(config/environments/{env}.yml)
      → プロジェクト固有(.vibe-pdca/config.yml)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 環境変数のプレフィックス
ENV_PREFIX = "VIBE_PDCA_"


def deep_merge(base: dict, override: dict) -> dict:
    """辞書の深いマージ。override が base を上書きする。"""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve_env_vars(config: dict) -> dict:
    """設定値内の ${ENV_VAR} を環境変数で解決する。"""
    resolved = {}
    for key, value in config.items():
        if isinstance(value, dict):
            resolved[key] = resolve_env_vars(value)
        elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_name = value[2:-1]
            env_value = os.environ.get(env_name)
            if env_value is None:
                logger.warning("環境変数 %s が未設定です", env_name)
            resolved[key] = env_value or value
        else:
            resolved[key] = value
    return resolved


def load_config(
    config_dir: str | Path = "config",
    env: str | None = None,
    project_config_path: str | Path | None = None,
) -> dict[str, Any]:
    """設定ファイルを階層マージして読み込む。

    Parameters
    ----------
    config_dir : str | Path
        設定ディレクトリのパス。
    env : str | None
        環境名（dev / stg / prod）。None の場合は VIBE_PDCA_ENV から取得。
    project_config_path : str | Path | None
        プロジェクト固有設定ファイルのパス。
    """
    try:
        import yaml
    except ImportError as e:
        raise RuntimeError("PyYAML が必要です: pip install pyyaml") from e

    config_dir = Path(config_dir)
    env = env or os.environ.get(f"{ENV_PREFIX}ENV", "dev")

    # 1. グローバルデフォルト
    default_path = config_dir / "default.yml"
    config: dict[str, Any] = {}
    if default_path.exists():
        with open(default_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        logger.info("設定読み込み: %s", default_path)

    # 2. 環境別
    env_path = config_dir / "environments" / f"{env}.yml"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            env_config = yaml.safe_load(f) or {}
        config = deep_merge(config, env_config)
        logger.info("環境別設定読み込み: %s", env_path)

    # 3. プロジェクト固有
    if project_config_path:
        proj_path = Path(project_config_path)
        if proj_path.exists():
            with open(proj_path, encoding="utf-8") as f:
                proj_config = yaml.safe_load(f) or {}
            config = deep_merge(config, proj_config)
            logger.info("プロジェクト固有設定読み込み: %s", proj_path)

    # 4. 環境変数解決
    config = resolve_env_vars(config)

    return config


def build_gateway_from_config(config: dict[str, Any]):
    """設定辞書から LLMGateway を構築する。"""
    from vibe_pdca.llm.circuit_breaker import CircuitBreakerConfig
    from vibe_pdca.llm.gateway import LLMGateway
    from vibe_pdca.llm.models import ProviderType, Role
    from vibe_pdca.llm.providers import CloudLLMProvider, LocalLLMProvider

    llm_config = config.get("llm", {})
    gateway = LLMGateway(config=llm_config)

    # 優先モード（環境変数 > 設定ファイル）
    mode_str = os.environ.get(
        f"{ENV_PREFIX}LLM_MODE",
        llm_config.get("preferred_mode", "cloud"),
    )
    mode_source = "環境変数" if f"{ENV_PREFIX}LLM_MODE" in os.environ else "設定ファイル"
    gateway.set_mode(
        ProviderType.CLOUD if mode_str == "cloud" else ProviderType.LOCAL,
        reason=f"{mode_source}による初期設定",
    )

    # 自動フォールバック（環境変数 > 設定ファイル）
    auto_fb_env = os.environ.get(f"{ENV_PREFIX}LLM_AUTO_FALLBACK")
    if auto_fb_env is not None:
        auto_fb = auto_fb_env.lower() not in ("false", "0", "no")
    else:
        auto_fb = llm_config.get("auto_fallback", True)
    gateway.set_auto_fallback(auto_fb)

    # サーキットブレーカー設定
    cb_conf = llm_config.get("circuit_breaker", {})
    cb_config = CircuitBreakerConfig(
        failure_threshold=cb_conf.get("failure_threshold", 3),
        recovery_timeout=cb_conf.get("recovery_timeout", 60.0),
        success_threshold=cb_conf.get("success_threshold", 2),
    )

    # コスト上限
    cost_conf = llm_config.get("cost", {})
    gateway.cost_tracker.daily_limit_usd = cost_conf.get("daily_limit_usd", 30.0)
    gateway.cost_tracker.per_cycle_limit_usd = cost_conf.get("per_cycle_limit_usd", 5.0)
    gateway.cost_tracker.max_calls_per_cycle = cost_conf.get("max_calls_per_cycle", 80)
    gateway.cost_tracker.max_calls_per_day = cost_conf.get("max_calls_per_day", 500)

    # クラウドプロバイダ登録
    for p_conf in llm_config.get("cloud_providers", []):
        provider = CloudLLMProvider(
            name=p_conf["name"],
            api_key=p_conf.get("api_key", ""),
            model=p_conf["model"],
            base_url=p_conf.get("base_url"),
            cost_per_1k_input=p_conf.get("cost_per_1k_input", 0.0),
            cost_per_1k_output=p_conf.get("cost_per_1k_output", 0.0),
            timeout=p_conf.get("timeout", 120.0),
        )
        roles = [Role(r) for r in p_conf.get("roles", [])]
        gateway.register_cloud_provider(
            provider, roles=roles, circuit_breaker_config=cb_config,
        )

    # ローカルプロバイダ登録
    for p_conf in llm_config.get("local_providers", []):
        provider = LocalLLMProvider(
            name=p_conf["name"],
            model=p_conf["model"],
            base_url=p_conf.get("base_url", "http://localhost:11434/v1"),
            timeout=p_conf.get("timeout", 300.0),
        )
        roles = [Role(r) for r in p_conf.get("roles", [])]
        gateway.register_local_provider(provider, roles=roles)

    # ヘルスチェッカー初期化
    hc_conf = llm_config.get("health_check", {})
    gateway.init_health_checker(
        interval=hc_conf.get("interval", 30.0),
    )

    return gateway
