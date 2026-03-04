"""共有テストヘルパー – tests/fixtures/ のデータ読み込みユーティリティ。"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict | list:
    """tests/fixtures/ 配下のJSONファイルを読み込む。"""
    path = FIXTURES_DIR / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]
