"""運用文書テンプレートのテスト。"""

from vibe_pdca.engine.ops_docs import get_template, list_templates


class TestOpsDocTemplates:
    def test_list_templates(self):
        templates = list_templates()
        assert "runbook" in templates
        assert "incident_playbook" in templates
        assert "approval_checklist" in templates
        assert "release_checklist" in templates

    def test_get_runbook(self):
        content = get_template("runbook")
        assert "Runbook" in content
        assert "日常運用" in content

    def test_get_incident_playbook(self):
        content = get_template("incident_playbook")
        assert "P0" in content
        assert "P1" in content

    def test_get_approval_checklist(self):
        content = get_template("approval_checklist")
        assert "A操作" in content
        assert "B操作" in content

    def test_get_release_checklist(self):
        content = get_template("release_checklist")
        assert "リリース前" in content
        assert "stg環境" in content
        assert "prod環境" in content

    def test_unknown_template(self):
        import pytest
        with pytest.raises(KeyError):
            get_template("unknown")
