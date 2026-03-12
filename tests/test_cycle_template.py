"""PDCAサイクルテンプレート管理のテスト。"""

from vibe_pdca.engine.cycle_template import (
    DEFAULT_TEMPLATES,
    CycleTemplate,
    CycleType,
    PersonaWeight,
    PhaseConfig,
    TemplateExporter,
    TemplateRegistry,
)

# ============================================================
# テスト: CycleType
# ============================================================


class TestCycleType:
    def test_values(self):
        assert CycleType.STANDARD == "standard"
        assert CycleType.HOTFIX == "hotfix"
        assert CycleType.REFACTORING == "refactoring"
        assert CycleType.SECURITY_PATCH == "security_patch"
        assert CycleType.FEATURE == "feature"


# ============================================================
# テスト: PhaseConfig
# ============================================================


class TestPhaseConfig:
    def test_defaults(self):
        pc = PhaseConfig(phase_name="Plan", timeout_minutes=30)
        assert pc.gate_conditions == []
        assert pc.enabled is True

    def test_custom(self):
        pc = PhaseConfig(
            phase_name="Do",
            timeout_minutes=120,
            gate_conditions=["all tasks done"],
            enabled=False,
        )
        assert pc.phase_name == "Do"
        assert pc.timeout_minutes == 120
        assert pc.gate_conditions == ["all tasks done"]
        assert pc.enabled is False


# ============================================================
# テスト: PersonaWeight
# ============================================================


class TestPersonaWeight:
    def test_defaults(self):
        pw = PersonaWeight(persona_name="reviewer")
        assert pw.weight == 1.0
        assert pw.is_active is True

    def test_custom(self):
        pw = PersonaWeight(
            persona_name="planner", weight=2.0, is_active=False,
        )
        assert pw.weight == 2.0
        assert pw.is_active is False


# ============================================================
# テスト: CycleTemplate
# ============================================================


class TestCycleTemplate:
    def test_defaults(self):
        tmpl = CycleTemplate(
            template_id="t1",
            name="Test",
            cycle_type=CycleType.STANDARD,
        )
        assert tmpl.phases == []
        assert tmpl.personas == []
        assert tmpl.max_tasks == 7
        assert tmpl.description == ""

    def test_custom(self):
        tmpl = CycleTemplate(
            template_id="t2",
            name="Custom",
            cycle_type=CycleType.FEATURE,
            max_tasks=10,
            description="Feature cycle",
        )
        assert tmpl.max_tasks == 10
        assert tmpl.description == "Feature cycle"


# ============================================================
# テスト: TemplateRegistry
# ============================================================


class TestTemplateRegistry:
    def _make_template(
        self,
        tid: str = "tmpl-1",
        ctype: CycleType = CycleType.STANDARD,
    ) -> CycleTemplate:
        return CycleTemplate(
            template_id=tid, name=f"Template {tid}",
            cycle_type=ctype,
        )

    def test_register_and_get(self):
        reg = TemplateRegistry()
        tmpl = self._make_template()
        reg.register(tmpl)
        assert reg.get("tmpl-1") is not None
        assert reg.get("tmpl-1").name == "Template tmpl-1"

    def test_get_missing(self):
        reg = TemplateRegistry()
        assert reg.get("nonexistent") is None

    def test_list_templates(self):
        reg = TemplateRegistry()
        reg.register(self._make_template("b"))
        reg.register(self._make_template("a"))
        templates = reg.list_templates()
        assert len(templates) == 2
        assert templates[0].template_id == "a"

    def test_get_by_type(self):
        reg = TemplateRegistry()
        reg.register(self._make_template("s1", CycleType.STANDARD))
        reg.register(self._make_template("h1", CycleType.HOTFIX))
        reg.register(self._make_template("s2", CycleType.STANDARD))
        standards = reg.get_by_type(CycleType.STANDARD)
        assert len(standards) == 2
        assert all(
            t.cycle_type == CycleType.STANDARD for t in standards
        )

    def test_unregister(self):
        reg = TemplateRegistry()
        reg.register(self._make_template("t1"))
        assert reg.unregister("t1") is True
        assert reg.get("t1") is None
        assert reg.count == 0

    def test_unregister_nonexistent(self):
        reg = TemplateRegistry()
        assert reg.unregister("unknown") is False

    def test_count(self):
        reg = TemplateRegistry()
        assert reg.count == 0
        reg.register(self._make_template("a"))
        reg.register(self._make_template("b"))
        assert reg.count == 2


# ============================================================
# テスト: TemplateExporter
# ============================================================


class TestTemplateExporter:
    def _make_full_template(self) -> CycleTemplate:
        return CycleTemplate(
            template_id="exp-1",
            name="Export Test",
            cycle_type=CycleType.REFACTORING,
            phases=[
                PhaseConfig("Plan", 30, ["review ready"]),
                PhaseConfig("Do", 60, ["code complete"], enabled=False),
            ],
            personas=[
                PersonaWeight("planner", 1.5, True),
                PersonaWeight("executor", 1.0, False),
            ],
            max_tasks=5,
            description="for export",
        )

    def test_export_dict(self):
        exporter = TemplateExporter()
        tmpl = self._make_full_template()
        data = exporter.export_dict(tmpl)
        assert data["template_id"] == "exp-1"
        assert data["cycle_type"] == "refactoring"
        assert len(data["phases"]) == 2
        assert data["phases"][0]["phase_name"] == "Plan"
        assert len(data["personas"]) == 2
        assert data["max_tasks"] == 5

    def test_import_dict(self):
        exporter = TemplateExporter()
        data = {
            "template_id": "imp-1",
            "name": "Imported",
            "cycle_type": "hotfix",
            "phases": [
                {
                    "phase_name": "Plan",
                    "timeout_minutes": 15,
                    "gate_conditions": ["identified"],
                },
            ],
            "personas": [
                {"persona_name": "dev", "weight": 2.0},
            ],
            "max_tasks": 3,
            "description": "imported template",
        }
        tmpl = exporter.import_dict(data)
        assert tmpl.template_id == "imp-1"
        assert tmpl.cycle_type == CycleType.HOTFIX
        assert len(tmpl.phases) == 1
        assert tmpl.phases[0].enabled is True
        assert tmpl.personas[0].weight == 2.0
        assert tmpl.max_tasks == 3

    def test_roundtrip(self):
        exporter = TemplateExporter()
        original = self._make_full_template()
        data = exporter.export_dict(original)
        restored = exporter.import_dict(data)
        assert restored.template_id == original.template_id
        assert restored.name == original.name
        assert restored.cycle_type == original.cycle_type
        assert len(restored.phases) == len(original.phases)
        assert len(restored.personas) == len(original.personas)
        assert restored.max_tasks == original.max_tasks
        assert restored.description == original.description


# ============================================================
# テスト: DEFAULT_TEMPLATES
# ============================================================


class TestDefaultTemplates:
    def test_default_templates_exist(self):
        assert len(DEFAULT_TEMPLATES) >= 2

    def test_standard_template(self):
        standards = [
            t for t in DEFAULT_TEMPLATES
            if t.cycle_type == CycleType.STANDARD
        ]
        assert len(standards) >= 1
        std = standards[0]
        assert len(std.phases) == 4
        phase_names = [p.phase_name for p in std.phases]
        assert "Plan" in phase_names
        assert "Do" in phase_names
        assert "Check" in phase_names
        assert "Act" in phase_names

    def test_hotfix_template(self):
        hotfixes = [
            t for t in DEFAULT_TEMPLATES
            if t.cycle_type == CycleType.HOTFIX
        ]
        assert len(hotfixes) >= 1
        hf = hotfixes[0]
        assert hf.max_tasks < 7
        assert len(hf.phases) == 4


# ============================================================
# テスト: import_dict バリデーション
# ============================================================


class TestTemplateImportValidation:
    """import_dict の入力バリデーション。"""

    def test_missing_template_id(self):
        import pytest
        exporter = TemplateExporter()
        with pytest.raises(ValueError, match="template_id"):
            exporter.import_dict({"name": "t", "cycle_type": "standard"})

    def test_missing_name(self):
        import pytest
        exporter = TemplateExporter()
        with pytest.raises(ValueError, match="name"):
            exporter.import_dict({
                "template_id": "x", "cycle_type": "standard",
            })

    def test_missing_cycle_type(self):
        import pytest
        exporter = TemplateExporter()
        with pytest.raises(ValueError, match="cycle_type"):
            exporter.import_dict({"template_id": "x", "name": "t"})

    def test_invalid_cycle_type(self):
        import pytest
        exporter = TemplateExporter()
        with pytest.raises(ValueError, match="不正なサイクル種別"):
            exporter.import_dict({
                "template_id": "x",
                "name": "t",
                "cycle_type": "invalid_type",
            })
