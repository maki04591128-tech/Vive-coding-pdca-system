"""共有テストヘルパー – tests/fixtures/ のデータ読み込みユーティリティ。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict | list:
    """tests/fixtures/ 配下のJSONファイルを読み込む。"""
    path = FIXTURES_DIR / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


@pytest.fixture()
def sample_goal_data() -> dict:
    """sample_goal.json からゴールデータを読み込むフィクスチャ。"""
    data = load_fixture("sample_goal.json")
    assert isinstance(data, dict)
    return data


@pytest.fixture()
def sample_review_findings_data() -> list:
    """sample_review_findings.json からレビュー指摘データを読み込むフィクスチャ。"""
    data = load_fixture("sample_review_findings.json")
    assert isinstance(data, list)
    return data
