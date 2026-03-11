"""config/loader.py のテスト。"""

from __future__ import annotations

import pytest

from vibe_pdca.config.loader import load_config


class TestPathTraversalPrevention:
    """env パラメータのパストラバーサル防止。"""

    def test_normal_env_name(self, tmp_path):
        """通常の環境名は問題なく通る。"""
        # config ディレクトリが存在しないだけで空 dict が返る
        result = load_config(config_dir=tmp_path, env="dev")
        assert isinstance(result, dict)

    def test_path_traversal_rejected(self, tmp_path):
        """../を含む環境名は ValueError。"""
        with pytest.raises(ValueError, match="無効な環境名"):
            load_config(config_dir=tmp_path, env="../../../etc/passwd")

    def test_slash_in_env_rejected(self, tmp_path):
        """スラッシュを含む環境名は ValueError。"""
        with pytest.raises(ValueError, match="無効な環境名"):
            load_config(config_dir=tmp_path, env="foo/bar")
