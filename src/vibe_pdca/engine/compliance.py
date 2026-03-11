"""コンプライアンステンプレート・ポリシーエンジン。

Proposal 25: コンプライアンステンプレートとポリシーエンジンの実装。

SOC2 / ISO27001 / GDPR / HIPAA などのフレームワークに基づくポリシールール管理、
違反検出、監査レポート生成を提供する。
"""

from __future__ import annotations

import copy
import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, cast

logger = logging.getLogger(__name__)


# ============================================================
# 列挙型
# ============================================================


class ComplianceFramework(enum.StrEnum):
    """対応するコンプライアンスフレームワーク。"""

    SOC2 = "SOC2"
    ISO27001 = "ISO27001"
    GDPR = "GDPR"
    HIPAA = "HIPAA"
    CUSTOM = "CUSTOM"


# ============================================================
# データクラス
# ============================================================


@dataclass
class PolicyRule:
    """ポリシールール定義。

    各コンプライアンスフレームワークの個別ルールを表す。
    """

    id: str
    name: str
    description: str
    framework: ComplianceFramework
    severity: str  # "critical", "warning", "info"
    condition: str  # 人間が読める条件の説明
    is_active: bool = True


@dataclass
class PolicyViolation:
    """ポリシー違反の検出結果。"""

    rule_id: str
    rule_name: str
    severity: str
    description: str
    resource_id: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class ComplianceCheckResult:
    """コンプライアンスチェック結果。"""

    framework: ComplianceFramework
    total_rules: int
    passed: int
    failed: int
    violations: list[PolicyViolation]
    compliance_rate: float  # 0.0 – 1.0
    checked_at: float = field(default_factory=time.time)


# ============================================================
# PolicyEngine – ルール管理
# ============================================================


class PolicyEngine:
    """ポリシールールを一元管理するエンジン。

    ルールの追加・削除・フレームワーク別取得を行う。
    """

    def __init__(self) -> None:
        self._rules: dict[str, PolicyRule] = {}
        self._lock = threading.Lock()

    # ---- ルール操作 ------------------------------------------------

    def add_rule(self, rule: PolicyRule) -> None:
        """ルールを追加する。

        Parameters
        ----------
        rule : PolicyRule
            追加するルール。
        """
        with self._lock:
            self._rules[rule.id] = rule
        logger.info("ルール追加: %s (%s)", rule.id, rule.name)

    def remove_rule(self, rule_id: str) -> bool:
        """ルールを削除する。

        Parameters
        ----------
        rule_id : str
            削除対象のルールID。

        Returns
        -------
        bool
            削除に成功した場合 True。
        """
        with self._lock:
            if rule_id in self._rules:
                removed = self._rules.pop(rule_id)
                logger.info("ルール削除: %s (%s)", rule_id, removed.name)
                return True
        logger.warning("ルール未検出: %s", rule_id)
        return False

    def get_rules(
        self,
        framework: ComplianceFramework | None = None,
    ) -> list[PolicyRule]:
        """ルール一覧を取得する。

        Parameters
        ----------
        framework : ComplianceFramework | None
            指定時はそのフレームワークのルールのみ返す。

        Returns
        -------
        list[PolicyRule]
            該当するルール一覧。
        """
        with self._lock:
            rules = list(self._rules.values())
        if framework is not None:
            rules = [r for r in rules if r.framework == framework]
        return rules

    @property
    def rule_count(self) -> int:
        """登録ルール数。"""
        with self._lock:
            return len(self._rules)


# ============================================================
# ComplianceChecker – 違反検出
# ============================================================


class ComplianceChecker:
    """ポリシーエンジンを用いてコンプライアンスチェックを実行する。"""

    def __init__(self, engine: PolicyEngine) -> None:
        self._engine = engine

    # ---- 個別チェック -----------------------------------------------

    def check_governance_level(
        self,
        operation: str,
        governance_level: str,
    ) -> list[PolicyViolation]:
        """ガバナンスレベルに関するチェック。

        Parameters
        ----------
        operation : str
            操作の説明。
        governance_level : str
            現在のガバナンスレベル (A / B / C)。

        Returns
        -------
        list[PolicyViolation]
            検出された違反。
        """
        violations: list[PolicyViolation] = []
        active_rules = [
            r for r in self._engine.get_rules()
            if r.is_active and "governance" in r.condition.lower()
        ]
        for rule in active_rules:
            if rule.severity == "critical" and governance_level not in ("A",):
                violations.append(PolicyViolation(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    severity=rule.severity,
                    description=(
                        f"操作 '{operation}' にはガバナンスレベル A が"
                        f"必要ですが、現在は '{governance_level}' です"
                    ),
                    resource_id=operation,
                ))
        logger.info(
            "ガバナンスチェック完了: 操作='%s', 違反=%d件",
            operation, len(violations),
        )
        return violations

    def check_data_handling(
        self,
        has_personal_data: bool,
        has_encryption: bool,
    ) -> list[PolicyViolation]:
        """データ取り扱いチェック。

        Parameters
        ----------
        has_personal_data : bool
            個人データを含むかどうか。
        has_encryption : bool
            暗号化されているかどうか。

        Returns
        -------
        list[PolicyViolation]
            検出された違反。
        """
        violations: list[PolicyViolation] = []
        active_rules = [
            r for r in self._engine.get_rules()
            if r.is_active and "encryption" in r.condition.lower()
        ]
        if has_personal_data and not has_encryption:
            for rule in active_rules:
                violations.append(PolicyViolation(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    severity=rule.severity,
                    description="個人データが暗号化されていません",
                    resource_id="data_handling",
                ))
        logger.info(
            "データ取り扱いチェック完了: 個人データ=%s, 暗号化=%s, 違反=%d件",
            has_personal_data, has_encryption, len(violations),
        )
        return violations

    # ---- フルチェック -----------------------------------------------

    def run_full_check(
        self,
        context: dict[str, Any],
    ) -> ComplianceCheckResult:
        """全ルールに対するフルチェックを実行する。

        Parameters
        ----------
        context : dict[str, Any]
            チェック対象のコンテキスト情報。
            - ``framework``: 対象フレームワーク (str)
            - ``operation``: 操作名 (str, optional)
            - ``governance_level``: ガバナンスレベル (str, optional)
            - ``has_personal_data``: 個人データ有無 (bool, optional)
            - ``has_encryption``: 暗号化有無 (bool, optional)

        Returns
        -------
        ComplianceCheckResult
            チェック結果。
        """
        framework_str = context.get("framework", "CUSTOM")
        try:
            framework = ComplianceFramework(framework_str)
        except ValueError:
            framework = ComplianceFramework.CUSTOM

        rules = self._engine.get_rules(framework)
        active_rules = [r for r in rules if r.is_active]
        total = len(active_rules)

        all_violations: list[PolicyViolation] = []

        # ガバナンスチェック
        operation = context.get("operation", "")
        governance_level = context.get("governance_level", "C")
        if operation:
            all_violations.extend(
                self.check_governance_level(operation, governance_level),
            )

        # データ取り扱いチェック
        has_personal_data = context.get("has_personal_data", False)
        has_encryption = context.get("has_encryption", False)
        all_violations.extend(
            self.check_data_handling(has_personal_data, has_encryption),
        )

        # 対象フレームワーク以外の違反を除外
        rule_ids = {r.id for r in active_rules}
        violations = [v for v in all_violations if v.rule_id in rule_ids]

        failed = len(violations)
        passed = max(total - failed, 0)
        rate = passed / total if total > 0 else 1.0

        result = ComplianceCheckResult(
            framework=framework,
            total_rules=total,
            passed=passed,
            failed=failed,
            violations=violations,
            compliance_rate=rate,
        )
        logger.info(
            "フルチェック完了: framework=%s, 合格=%d/%d (%.1f%%)",
            framework.value, passed, total, rate * 100,
        )
        return result

    # ---- 監査レポート生成 -------------------------------------------

    def generate_audit_report(
        self,
        results: list[ComplianceCheckResult],
    ) -> str:
        """Markdown形式の監査レポートを生成する。

        Parameters
        ----------
        results : list[ComplianceCheckResult]
            チェック結果のリスト。

        Returns
        -------
        str
            Markdown形式の監査レポート。
        """
        lines: list[str] = []
        lines.append("# コンプライアンス監査レポート")
        lines.append("")

        for result in results:
            lines.append(f"## {result.framework.value}")
            lines.append("")
            lines.append(f"- **総ルール数**: {result.total_rules}")
            lines.append(f"- **合格**: {result.passed}")
            lines.append(f"- **不合格**: {result.failed}")
            lines.append(
                f"- **準拠率**: {result.compliance_rate:.1%}",
            )
            lines.append("")

            if result.violations:
                lines.append("### 違反一覧")
                lines.append("")
                lines.append("| ルールID | ルール名 | 重大度 | 説明 |")
                lines.append("|----------|----------|--------|------|")
                for v in result.violations:
                    lines.append(
                        f"| {v.rule_id} | {v.rule_name} "
                        f"| {v.severity} | {v.description} |",
                    )
                lines.append("")

        logger.info("監査レポート生成完了: %d件のチェック結果", len(results))
        return "\n".join(lines)


# ============================================================
# ComplianceTemplateLoader – テンプレート読み込み
# ============================================================


class ComplianceTemplateLoader:
    """各フレームワークの定型ルールテンプレートを提供する。"""

    @staticmethod
    def load_soc2_template() -> list[PolicyRule]:
        """SOC 2 テンプレートルールを返す。"""
        return [
            PolicyRule(
                id="soc2-001",
                name="アクセス制御",
                description="システムへのアクセスは承認されたユーザーに限定する",
                framework=ComplianceFramework.SOC2,
                severity="critical",
                condition="governance レベル A が必要",
            ),
            PolicyRule(
                id="soc2-002",
                name="変更管理",
                description="システム変更は文書化され承認を受ける",
                framework=ComplianceFramework.SOC2,
                severity="warning",
                condition="変更管理プロセスが存在する",
            ),
            PolicyRule(
                id="soc2-003",
                name="データ暗号化",
                description="保存データおよび転送データを暗号化する",
                framework=ComplianceFramework.SOC2,
                severity="critical",
                condition="encryption が有効である",
            ),
            PolicyRule(
                id="soc2-004",
                name="インシデント対応",
                description="セキュリティインシデントに対する対応手順を維持する",
                framework=ComplianceFramework.SOC2,
                severity="warning",
                condition="インシデント対応計画が定義されている",
            ),
            PolicyRule(
                id="soc2-005",
                name="監査ログ",
                description="全操作の監査ログを保持する",
                framework=ComplianceFramework.SOC2,
                severity="info",
                condition="監査ログが有効である",
            ),
        ]

    @staticmethod
    def load_iso27001_template() -> list[PolicyRule]:
        """ISO 27001 テンプレートルールを返す。"""
        return [
            PolicyRule(
                id="iso-001",
                name="情報セキュリティポリシー",
                description="情報セキュリティポリシーを文書化し定期的にレビューする",
                framework=ComplianceFramework.ISO27001,
                severity="critical",
                condition="governance ポリシーが定義されている",
            ),
            PolicyRule(
                id="iso-002",
                name="リスクアセスメント",
                description="情報セキュリティリスクを定期的に評価する",
                framework=ComplianceFramework.ISO27001,
                severity="warning",
                condition="リスク評価プロセスが存在する",
            ),
            PolicyRule(
                id="iso-003",
                name="暗号化管理",
                description="暗号化技術の使用に関する方針を策定する",
                framework=ComplianceFramework.ISO27001,
                severity="critical",
                condition="encryption ポリシーが定義されている",
            ),
            PolicyRule(
                id="iso-004",
                name="アクセス制御方針",
                description="アクセス制御に関する要件を定義する",
                framework=ComplianceFramework.ISO27001,
                severity="warning",
                condition="アクセス制御ポリシーが存在する",
            ),
        ]

    @staticmethod
    def load_gdpr_template() -> list[PolicyRule]:
        """GDPR テンプレートルールを返す。"""
        return [
            PolicyRule(
                id="gdpr-001",
                name="データ処理の合法性",
                description="個人データの処理には法的根拠が必要",
                framework=ComplianceFramework.GDPR,
                severity="critical",
                condition="データ処理の法的根拠が明示されている",
            ),
            PolicyRule(
                id="gdpr-002",
                name="データ主体の権利",
                description="データ主体のアクセス・訂正・削除権を保証する",
                framework=ComplianceFramework.GDPR,
                severity="critical",
                condition="データ主体の権利行使プロセスが存在する",
            ),
            PolicyRule(
                id="gdpr-003",
                name="データ保護影響評価",
                description="高リスクの処理には影響評価を実施する",
                framework=ComplianceFramework.GDPR,
                severity="warning",
                condition="影響評価プロセスが定義されている",
            ),
            PolicyRule(
                id="gdpr-004",
                name="個人データの暗号化",
                description="個人データは適切な暗号化で保護する",
                framework=ComplianceFramework.GDPR,
                severity="critical",
                condition="encryption が個人データに適用されている",
            ),
        ]

    @staticmethod
    def load_hipaa_template() -> list[PolicyRule]:
        """HIPAA テンプレートルールを返す。"""
        return [
            PolicyRule(
                id="hipaa-001",
                name="PHI アクセス制御",
                description="保護対象保健情報へのアクセスを最小限にする",
                framework=ComplianceFramework.HIPAA,
                severity="critical",
                condition="governance レベル A が PHI アクセスに適用される",
            ),
            PolicyRule(
                id="hipaa-002",
                name="PHI 暗号化",
                description="保護対象保健情報を暗号化する",
                framework=ComplianceFramework.HIPAA,
                severity="critical",
                condition="encryption が PHI に適用されている",
            ),
            PolicyRule(
                id="hipaa-003",
                name="監査証跡",
                description="PHI へのアクセスと変更の監査証跡を維持する",
                framework=ComplianceFramework.HIPAA,
                severity="warning",
                condition="監査ログが PHI 操作に有効である",
            ),
        ]


# ============================================================
# PolicyVersionManager – ルールバージョン管理
# ============================================================


class PolicyVersionManager:
    """ポリシールールのバージョン管理を行う。

    ルールセットのスナップショットを保存し、履歴を追跡する。
    """

    def __init__(self) -> None:
        self._versions: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def add_version(
        self,
        rules: list[PolicyRule],
        description: str,
    ) -> int:
        """新しいバージョンを追加する。

        Parameters
        ----------
        rules : list[PolicyRule]
            スナップショットするルール一覧。
        description : str
            バージョンの説明。

        Returns
        -------
        int
            追加されたバージョン番号 (1始まり)。
        """
        with self._lock:
            version_number = len(self._versions) + 1
            self._versions.append({
                "version": version_number,
                "rules": copy.deepcopy(rules),
                "description": description,
                "created_at": time.time(),
            })
        logger.info("ポリシーバージョン %d を追加: %s", version_number, description)
        return version_number

    def get_version(self, version: int) -> list[PolicyRule] | None:
        """指定バージョンのルール一覧を取得する。

        Parameters
        ----------
        version : int
            取得するバージョン番号。

        Returns
        -------
        list[PolicyRule] | None
            該当バージョンのルール一覧。存在しない場合は None。
        """
        with self._lock:
            idx = version - 1
            if 0 <= idx < len(self._versions):
                return cast(list[PolicyRule], copy.deepcopy(self._versions[idx]["rules"]))
        logger.warning("バージョン %d は存在しません", version)
        return None

    def get_latest_version(self) -> int:
        """最新バージョン番号を返す。

        Returns
        -------
        int
            最新バージョン番号。バージョンがない場合は 0。
        """
        with self._lock:
            return len(self._versions)

    def get_history(self) -> list[dict[str, Any]]:
        """バージョン履歴を返す。

        Returns
        -------
        list[dict[str, Any]]
            各バージョンの概要リスト。
        """
        with self._lock:
            return [
                {
                    "version": entry["version"],
                    "description": entry["description"],
                    "rule_count": len(entry["rules"]),
                    "created_at": entry["created_at"],
                }
                for entry in self._versions
            ]
