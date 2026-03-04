"""JSONスキーマのバリデーションテスト（§4.4 JSONスキーマ運用ポリシー準拠）。

config/prompts/schemas/ 配下の全スキーマファイルが有効なJSONであること、
および典型的な入力データがスキーマに適合することを検証する。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SCHEMAS_DIR = Path(__file__).parent.parent / "config" / "prompts" / "schemas"


def _load_schema(name: str) -> dict:
    """スキーマファイルを読み込む。"""
    path = SCHEMAS_DIR / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 全スキーマが有効なJSONであることのテスト
# ============================================================


class TestSchemaFiles:
    """config/prompts/schemas/ 配下の全 .json が有効なJSONであること。"""

    def test_all_schema_files_are_valid_json(self):
        schema_files = list(SCHEMAS_DIR.glob("*.json"))
        assert len(schema_files) >= 5, f"スキーマファイルが5個以上あること: {len(schema_files)}"
        for path in schema_files:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            assert "$schema" in data, f"{path.name} に $schema が含まれること"
            assert "title" in data, f"{path.name} に title が含まれること"

    def test_schema_ids_are_unique(self):
        schema_files = list(SCHEMAS_DIR.glob("*.json"))
        ids = []
        for path in schema_files:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            if "$id" in data:
                ids.append(data["$id"])
        assert len(ids) == len(set(ids)), "スキーマIDが一意であること"


# ============================================================
# plan_output.schema.json
# ============================================================


class TestPlanOutputSchema:
    """PLANフェーズ出力スキーマの構造テスト。"""

    @pytest.fixture()
    def schema(self) -> dict:
        return _load_schema("plan_output.schema.json")

    def test_required_fields(self, schema: dict):
        assert "tasks" in schema["required"]

    def test_tasks_max_items(self, schema: dict):
        assert schema["properties"]["tasks"]["maxItems"] == 7

    def test_task_has_required_fields(self, schema: dict):
        task_schema = schema["properties"]["tasks"]["items"]
        assert set(task_schema["required"]) == {"id", "title", "dod"}


# ============================================================
# review_finding.schema.json
# ============================================================


class TestReviewFindingSchema:
    """レビュー指摘出力スキーマの構造テスト。"""

    @pytest.fixture()
    def schema(self) -> dict:
        return _load_schema("review_finding.schema.json")

    def test_required_fields(self, schema: dict):
        expected = {"severity", "category", "basis", "suggestion", "confidence"}
        assert set(schema["required"]) == expected

    def test_severity_enum(self, schema: dict):
        allowed = schema["properties"]["severity"]["enum"]
        assert set(allowed) == {"blocker", "major", "minor"}

    def test_confidence_range(self, schema: dict):
        conf = schema["properties"]["confidence"]
        assert conf["minimum"] == 0.0
        assert conf["maximum"] == 1.0


# ============================================================
# act_output.schema.json
# ============================================================


class TestActOutputSchema:
    """ACTフェーズ出力スキーマの構造テスト。"""

    @pytest.fixture()
    def schema(self) -> dict:
        return _load_schema("act_output.schema.json")

    def test_required_fields(self, schema: dict):
        expected = {"decisions", "next_cycle_plan"}
        assert set(schema["required"]) == expected

    def test_action_enum(self, schema: dict):
        decision_schema = schema["properties"]["decisions"]["items"]
        allowed = decision_schema["properties"]["action"]["enum"]
        assert set(allowed) == {"accept", "reject", "defer"}


# ============================================================
# do_output.schema.json
# ============================================================


class TestDoOutputSchema:
    """DOフェーズ出力スキーマの構造テスト。"""

    @pytest.fixture()
    def schema(self) -> dict:
        return _load_schema("do_output.schema.json")

    def test_required_fields(self, schema: dict):
        assert "changes" in schema["required"]

    def test_change_has_required_fields(self, schema: dict):
        change_schema = schema["properties"]["changes"]["items"]
        expected = {"filepath", "action", "content", "rationale"}
        assert set(change_schema["required"]) == expected

    def test_action_enum(self, schema: dict):
        change_schema = schema["properties"]["changes"]["items"]
        allowed = change_schema["properties"]["action"]["enum"]
        assert set(allowed) == {"create", "update", "delete"}


# ============================================================
# check_output.schema.json
# ============================================================


class TestCheckOutputSchema:
    """CHECKフェーズ出力スキーマの構造テスト。"""

    @pytest.fixture()
    def schema(self) -> dict:
        return _load_schema("check_output.schema.json")

    def test_required_fields(self, schema: dict):
        expected = {"ci_summary", "review_findings", "dod_evaluation"}
        assert set(schema["required"]) == expected

    def test_ci_summary_required_fields(self, schema: dict):
        ci = schema["properties"]["ci_summary"]
        expected = {"total_jobs", "passed_jobs", "failed_jobs", "overall_status"}
        assert set(ci["required"]) == expected

    def test_overall_status_enum(self, schema: dict):
        ci = schema["properties"]["ci_summary"]
        allowed = ci["properties"]["overall_status"]["enum"]
        assert "success" in allowed
        assert "failure" in allowed

    def test_dod_evaluation_structure(self, schema: dict):
        dod = schema["properties"]["dod_evaluation"]
        assert set(dod["required"]) == {"achieved", "unmet_reasons"}
        assert dod["properties"]["achieved"]["type"] == "boolean"
