"""コンプライアンステンプレート・ポリシーエンジンのテスト。

Proposal 25 の実装に対するユニットテスト。
"""

import pytest

from vibe_pdca.engine.compliance import (
    ComplianceCheckResult,
    ComplianceChecker,
    ComplianceFramework,
    ComplianceTemplateLoader,
    PolicyEngine,
    PolicyRule,
    PolicyVersionManager,
    PolicyViolation,
)

# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def engine():
    return PolicyEngine()


@pytest.fixture
def sample_rule():
    return PolicyRule(
        id="test-001",
        name="テストルール",
        description="テスト用のルール",
        framework=ComplianceFramework.SOC2,
        severity="critical",
        condition="governance レベル A が必要",
    )


@pytest.fixture
def encryption_rule():
    return PolicyRule(
        id="test-002",
        name="暗号化ルール",
        description="暗号化が必要",
        framework=ComplianceFramework.SOC2,
        severity="critical",
        condition="encryption が有効である",
    )


@pytest.fixture
def loaded_engine():
    """SOC2テンプレートが読み込まれたエンジン。"""
    eng = PolicyEngine()
    for rule in ComplianceTemplateLoader.load_soc2_template():
        eng.add_rule(rule)
    return eng


@pytest.fixture
def checker(loaded_engine):
    return ComplianceChecker(loaded_engine)


@pytest.fixture
def version_manager():
    return PolicyVersionManager()


# ============================================================
# テスト: ComplianceFramework 列挙型
# ============================================================


class TestComplianceFramework:
    def test_enum_values(self):
        assert ComplianceFramework.SOC2 == "SOC2"
        assert ComplianceFramework.ISO27001 == "ISO27001"
        assert ComplianceFramework.GDPR == "GDPR"
        assert ComplianceFramework.HIPAA == "HIPAA"
        assert ComplianceFramework.CUSTOM == "CUSTOM"

    def test_enum_from_value(self):
        assert ComplianceFramework("SOC2") is ComplianceFramework.SOC2


# ============================================================
# テスト: PolicyRule データクラス
# ============================================================


class TestPolicyRule:
    def test_default_is_active(self, sample_rule):
        assert sample_rule.is_active is True

    def test_fields(self, sample_rule):
        assert sample_rule.id == "test-001"
        assert sample_rule.framework == ComplianceFramework.SOC2
        assert sample_rule.severity == "critical"


# ============================================================
# テスト: PolicyViolation データクラス
# ============================================================


class TestPolicyViolation:
    def test_auto_timestamp(self):
        v = PolicyViolation(
            rule_id="r1",
            rule_name="名前",
            severity="warning",
            description="説明",
        )
        assert v.timestamp > 0
        assert v.resource_id == ""

    def test_custom_resource(self):
        v = PolicyViolation(
            rule_id="r1",
            rule_name="名前",
            severity="info",
            description="説明",
            resource_id="res-1",
        )
        assert v.resource_id == "res-1"


# ============================================================
# テスト: PolicyEngine
# ============================================================


class TestPolicyEngine:
    def test_add_rule(self, engine, sample_rule):
        engine.add_rule(sample_rule)
        assert engine.rule_count == 1

    def test_remove_rule_existing(self, engine, sample_rule):
        engine.add_rule(sample_rule)
        assert engine.remove_rule("test-001") is True
        assert engine.rule_count == 0

    def test_remove_rule_nonexistent(self, engine):
        assert engine.remove_rule("no-such-rule") is False

    def test_get_rules_all(self, engine, sample_rule, encryption_rule):
        engine.add_rule(sample_rule)
        engine.add_rule(encryption_rule)
        assert len(engine.get_rules()) == 2

    def test_get_rules_by_framework(self, engine, sample_rule):
        engine.add_rule(sample_rule)
        gdpr_rule = PolicyRule(
            id="gdpr-test",
            name="GDPRルール",
            description="GDPR用",
            framework=ComplianceFramework.GDPR,
            severity="warning",
            condition="テスト条件",
        )
        engine.add_rule(gdpr_rule)
        soc2_rules = engine.get_rules(ComplianceFramework.SOC2)
        assert len(soc2_rules) == 1
        assert soc2_rules[0].id == "test-001"

    def test_get_rules_empty_framework(self, engine, sample_rule):
        engine.add_rule(sample_rule)
        assert len(engine.get_rules(ComplianceFramework.HIPAA)) == 0

    def test_rule_count_property(self, engine):
        assert engine.rule_count == 0

    def test_overwrite_rule_same_id(self, engine, sample_rule):
        engine.add_rule(sample_rule)
        updated = PolicyRule(
            id="test-001",
            name="更新済み",
            description="更新",
            framework=ComplianceFramework.SOC2,
            severity="info",
            condition="更新条件",
        )
        engine.add_rule(updated)
        assert engine.rule_count == 1
        assert engine.get_rules()[0].name == "更新済み"


# ============================================================
# テスト: ComplianceChecker – ガバナンスチェック
# ============================================================


class TestComplianceCheckerGovernance:
    def test_no_violation_level_a(self, checker):
        violations = checker.check_governance_level("テスト操作", "A")
        assert len(violations) == 0

    def test_violation_level_c(self, checker):
        violations = checker.check_governance_level("テスト操作", "C")
        assert len(violations) > 0
        assert violations[0].severity == "critical"


# ============================================================
# テスト: ComplianceChecker – データ取り扱いチェック
# ============================================================


class TestComplianceCheckerDataHandling:
    def test_no_violation_encrypted(self, checker):
        violations = checker.check_data_handling(
            has_personal_data=True, has_encryption=True,
        )
        assert len(violations) == 0

    def test_violation_unencrypted(self, checker):
        violations = checker.check_data_handling(
            has_personal_data=True, has_encryption=False,
        )
        assert len(violations) > 0

    def test_no_personal_data(self, checker):
        violations = checker.check_data_handling(
            has_personal_data=False, has_encryption=False,
        )
        assert len(violations) == 0


# ============================================================
# テスト: ComplianceChecker – フルチェック
# ============================================================


class TestComplianceCheckerFullCheck:
    def test_full_check_clean(self, checker):
        result = checker.run_full_check({
            "framework": "SOC2",
            "governance_level": "A",
            "has_personal_data": False,
            "has_encryption": True,
        })
        assert isinstance(result, ComplianceCheckResult)
        assert result.framework == ComplianceFramework.SOC2
        assert result.failed == 0
        assert result.compliance_rate == 1.0

    def test_full_check_with_violations(self, checker):
        result = checker.run_full_check({
            "framework": "SOC2",
            "operation": "本番デプロイ",
            "governance_level": "C",
            "has_personal_data": True,
            "has_encryption": False,
        })
        assert result.failed > 0
        assert result.compliance_rate < 1.0

    def test_full_check_custom_framework(self, checker):
        result = checker.run_full_check({"framework": "UNKNOWN"})
        assert result.framework == ComplianceFramework.CUSTOM

    def test_full_check_empty_context(self, checker):
        result = checker.run_full_check({})
        assert isinstance(result, ComplianceCheckResult)


# ============================================================
# テスト: ComplianceChecker – 監査レポート
# ============================================================


class TestAuditReport:
    def test_report_contains_header(self, checker):
        result = checker.run_full_check({"framework": "SOC2"})
        report = checker.generate_audit_report([result])
        assert "# コンプライアンス監査レポート" in report

    def test_report_contains_framework(self, checker):
        result = checker.run_full_check({"framework": "SOC2"})
        report = checker.generate_audit_report([result])
        assert "SOC2" in report

    def test_report_violations_table(self, checker):
        result = checker.run_full_check({
            "framework": "SOC2",
            "operation": "操作",
            "governance_level": "C",
            "has_personal_data": True,
            "has_encryption": False,
        })
        report = checker.generate_audit_report([result])
        assert "### 違反一覧" in report
        assert "| ルールID" in report

    def test_report_empty_results(self, checker):
        report = checker.generate_audit_report([])
        assert "# コンプライアンス監査レポート" in report


# ============================================================
# テスト: ComplianceTemplateLoader
# ============================================================


class TestComplianceTemplateLoader:
    def test_soc2_template(self):
        rules = ComplianceTemplateLoader.load_soc2_template()
        assert 3 <= len(rules) <= 5
        assert all(r.framework == ComplianceFramework.SOC2 for r in rules)

    def test_iso27001_template(self):
        rules = ComplianceTemplateLoader.load_iso27001_template()
        assert 3 <= len(rules) <= 5
        assert all(r.framework == ComplianceFramework.ISO27001 for r in rules)

    def test_gdpr_template(self):
        rules = ComplianceTemplateLoader.load_gdpr_template()
        assert 3 <= len(rules) <= 5
        assert all(r.framework == ComplianceFramework.GDPR for r in rules)

    def test_hipaa_template(self):
        rules = ComplianceTemplateLoader.load_hipaa_template()
        assert 3 <= len(rules) <= 5
        assert all(r.framework == ComplianceFramework.HIPAA for r in rules)

    def test_unique_rule_ids(self):
        all_rules = (
            ComplianceTemplateLoader.load_soc2_template()
            + ComplianceTemplateLoader.load_iso27001_template()
            + ComplianceTemplateLoader.load_gdpr_template()
            + ComplianceTemplateLoader.load_hipaa_template()
        )
        ids = [r.id for r in all_rules]
        assert len(ids) == len(set(ids))


# ============================================================
# テスト: PolicyVersionManager
# ============================================================


class TestPolicyVersionManager:
    def test_add_version(self, version_manager):
        rules = ComplianceTemplateLoader.load_soc2_template()
        v = version_manager.add_version(rules, "初期バージョン")
        assert v == 1

    def test_get_version(self, version_manager):
        rules = ComplianceTemplateLoader.load_soc2_template()
        version_manager.add_version(rules, "v1")
        retrieved = version_manager.get_version(1)
        assert retrieved is not None
        assert len(retrieved) == len(rules)

    def test_get_version_nonexistent(self, version_manager):
        assert version_manager.get_version(99) is None

    def test_get_latest_version_empty(self, version_manager):
        assert version_manager.get_latest_version() == 0

    def test_get_latest_version(self, version_manager):
        rules = ComplianceTemplateLoader.load_soc2_template()
        version_manager.add_version(rules, "v1")
        version_manager.add_version(rules, "v2")
        assert version_manager.get_latest_version() == 2

    def test_get_history(self, version_manager):
        rules = ComplianceTemplateLoader.load_soc2_template()
        version_manager.add_version(rules, "初回リリース")
        version_manager.add_version(rules, "修正版")
        history = version_manager.get_history()
        assert len(history) == 2
        assert history[0]["version"] == 1
        assert history[1]["description"] == "修正版"
        assert "rule_count" in history[0]

    def test_deep_copy_isolation(self, version_manager):
        rules = ComplianceTemplateLoader.load_soc2_template()
        version_manager.add_version(rules, "v1")
        retrieved = version_manager.get_version(1)
        assert retrieved is not None
        retrieved[0].name = "改変"
        original = version_manager.get_version(1)
        assert original is not None
        assert original[0].name != "改変"
