"""LLMレスポンスの品質スコアリングと自動リトライ。

提案22: LLMレスポンス品質の定量評価・自動リトライ機構。

入力: LLMレスポンステキスト・バリデーションコンテキスト
出力: 品質レポート（次元別スコア・総合スコア・リトライ推奨判定）
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


# ── QualityDimension ──

# AIレスポンスの品質を4つの観点（構造・完全性・一貫性・事実正確性）で評価
class QualityDimension(StrEnum):
    """品質評価の次元。"""

    STRUCTURAL_VALIDITY = "structural_validity"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    HALLUCINATION_FREE = "hallucination_free"


# ── QualityScore ──


@dataclass
class QualityScore:
    """単一次元の品質スコア。

    Parameters
    ----------
    dimension : QualityDimension
        評価次元。
    score : float
        0.0〜1.0 のスコア。
    issues : list[str]
        検出された問題の説明リスト。
    """

    dimension: QualityDimension
    score: float
    issues: list[str] = field(default_factory=list)


# ── QualityReport ──


@dataclass
class QualityReport:
    """品質評価の総合レポート。

    Parameters
    ----------
    scores : list[QualityScore]
        次元別スコアのリスト。
    overall_score : float
        加重平均による総合スコア。
    is_acceptable : bool
        総合スコアが閾値以上かどうか。
    threshold : float
        許容閾値（デフォルト 0.7）。
    retry_recommended : bool
        品質不足かつリトライ残回数ありの場合 True。
    timestamp : float
        レポート生成時刻。
    """

    scores: list[QualityScore]
    overall_score: float
    is_acceptable: bool
    threshold: float = 0.7
    retry_recommended: bool = False
    timestamp: float = field(default_factory=time.time)


# ── StructuralValidator ──

# --- 構造検証: JSON形式か、必須キーがあるか、Markdown見出しが揃っているか ---
class StructuralValidator:
    """LLMレスポンスの構造的妥当性を検証する。"""

    def validate_json(self, text: str) -> QualityScore:
        """テキストが有効なJSONかどうかを検証する。

        Parameters
        ----------
        text : str
            検証対象テキスト。

        Returns
        -------
        QualityScore
            STRUCTURAL_VALIDITY 次元のスコア。
        """
        issues: list[str] = []
        try:
            json.loads(text)
            score = 1.0
        except json.JSONDecodeError as e:
            issues.append(f"JSON解析エラー: {e}")
            score = 0.0
        return QualityScore(
            dimension=QualityDimension.STRUCTURAL_VALIDITY,
            score=score,
            issues=issues,
        )

    def validate_required_keys(
        self, data: dict[str, Any], required: list[str]
    ) -> QualityScore:
        """辞書に必須キーがすべて含まれているかを検証する。

        Parameters
        ----------
        data : dict
            検証対象の辞書。
        required : list[str]
            必須キーのリスト。

        Returns
        -------
        QualityScore
            STRUCTURAL_VALIDITY 次元のスコア。
        """
        issues: list[str] = []
        if not required:
            return QualityScore(
                dimension=QualityDimension.STRUCTURAL_VALIDITY,
                score=1.0,
                issues=issues,
            )
        missing = [k for k in required if k not in data]
        if missing:
            issues.append(f"必須キーが不足: {', '.join(missing)}")
        present = len(required) - len(missing)
        score = present / len(required)
        return QualityScore(
            dimension=QualityDimension.STRUCTURAL_VALIDITY,
            score=score,
            issues=issues,
        )

    def validate_markdown_structure(
        self, text: str, required_headings: list[str]
    ) -> QualityScore:
        """Markdownテキストに必須見出しが含まれているかを検証する。

        Parameters
        ----------
        text : str
            Markdownテキスト。
        required_headings : list[str]
            必須の見出しテキストリスト。

        Returns
        -------
        QualityScore
            STRUCTURAL_VALIDITY 次元のスコア。
        """
        issues: list[str] = []
        if not required_headings:
            return QualityScore(
                dimension=QualityDimension.STRUCTURAL_VALIDITY,
                score=1.0,
                issues=issues,
            )
        # Markdownの見出し行を抽出（#, ##, ### など）
        heading_pattern = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
        found_headings = {m.group(1).strip() for m in heading_pattern.finditer(text)}

        missing = [h for h in required_headings if h not in found_headings]
        if missing:
            issues.append(f"必須見出しが不足: {', '.join(missing)}")
        present = len(required_headings) - len(missing)
        score = present / len(required_headings)
        return QualityScore(
            dimension=QualityDimension.STRUCTURAL_VALIDITY,
            score=score,
            issues=issues,
        )


# ── CompletenessChecker ──

# --- 完全性検証: タスク数は適切か、レビュー指摘に必須フィールドがあるか ---
class CompletenessChecker:
    """レスポンスの完全性を検証する。"""

    def check_task_list(
        self,
        tasks: list[dict[str, Any]],
        min_tasks: int = 1,
        max_tasks: int = 7,
    ) -> QualityScore:
        """タスクリストの完全性を検証する。

        Parameters
        ----------
        tasks : list[dict]
            タスク辞書のリスト。
        min_tasks : int
            最小タスク数（デフォルト 1）。
        max_tasks : int
            最大タスク数（デフォルト 7）。

        Returns
        -------
        QualityScore
            COMPLETENESS 次元のスコア。
        """
        issues: list[str] = []
        count = len(tasks)
        if count < min_tasks:
            issues.append(f"タスク数が不足: {count} < {min_tasks}")
        if count > max_tasks:
            issues.append(f"タスク数が過多: {count} > {max_tasks}")

        if count == 0:
            score = 0.0
        elif count < min_tasks:
            score = count / min_tasks
        elif count > max_tasks:
            # 超過分に応じて減点
            score = max(0.0, 1.0 - (count - max_tasks) / max_tasks)
        else:
            score = 1.0

        return QualityScore(
            dimension=QualityDimension.COMPLETENESS,
            score=score,
            issues=issues,
        )

    def check_review_findings(
        self,
        findings: list[dict[str, Any]],
        required_fields: list[str],
    ) -> QualityScore:
        """レビュー指摘の完全性を検証する。

        Parameters
        ----------
        findings : list[dict]
            レビュー指摘辞書のリスト。
        required_fields : list[str]
            各指摘に必須のフィールド名リスト。

        Returns
        -------
        QualityScore
            COMPLETENESS 次元のスコア。
        """
        issues: list[str] = []
        if not findings:
            issues.append("レビュー指摘が空です")
            return QualityScore(
                dimension=QualityDimension.COMPLETENESS,
                score=0.0,
                issues=issues,
            )
        if not required_fields:
            return QualityScore(
                dimension=QualityDimension.COMPLETENESS,
                score=1.0,
                issues=issues,
            )
        total_fields = len(findings) * len(required_fields)
        missing_count = 0
        for i, finding in enumerate(findings):
            missing = [f for f in required_fields if f not in finding]
            if missing:
                missing_count += len(missing)
                issues.append(
                    f"指摘[{i}]にフィールド不足: {', '.join(missing)}"
                )
        present = total_fields - missing_count
        score = present / total_fields
        return QualityScore(
            dimension=QualityDimension.COMPLETENESS,
            score=score,
            issues=issues,
        )


# ── HallucinationDetector ──

# --- ハルシネーション検出: AIが実在しないファイルやAPIを参照していないかチェック ---
class HallucinationDetector:
    """基本的なハルシネーション検出を行う。"""

    # ファイルパスらしきパターン
    _FILE_REF_PATTERN = re.compile(
        r"(?:^|[\s`\"'])([a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+)(?:[\s`\"',:;)]|$)",
        re.MULTILINE,
    )

    def check_file_references(
        self, text: str, known_files: set[str]
    ) -> QualityScore:
        """テキスト中のファイル参照が既知のファイル集合に含まれるかを検証する。

        Parameters
        ----------
        text : str
            検証対象テキスト。
        known_files : set[str]
            既知のファイルパスの集合。

        Returns
        -------
        QualityScore
            HALLUCINATION_FREE 次元のスコア。
        """
        issues: list[str] = []
        if not known_files:
            return QualityScore(
                dimension=QualityDimension.HALLUCINATION_FREE,
                score=1.0,
                issues=issues,
            )
        refs = set(self._FILE_REF_PATTERN.findall(text))
        if not refs:
            return QualityScore(
                dimension=QualityDimension.HALLUCINATION_FREE,
                score=1.0,
                issues=issues,
            )
        unknown = refs - known_files
        if unknown:
            issues.append(
                f"不明なファイル参照: {', '.join(sorted(unknown))}"
            )
        known_count = len(refs) - len(unknown)
        score = known_count / len(refs) if refs else 1.0
        return QualityScore(
            dimension=QualityDimension.HALLUCINATION_FREE,
            score=score,
            issues=issues,
        )

    def check_api_references(
        self, text: str, known_apis: set[str]
    ) -> QualityScore:
        """テキスト中のAPI参照が既知のAPI集合に含まれるかを検証する。

        Parameters
        ----------
        text : str
            検証対象テキスト。
        known_apis : set[str]
            既知のAPI識別子の集合。

        Returns
        -------
        QualityScore
            HALLUCINATION_FREE 次元のスコア。
        """
        issues: list[str] = []
        if not known_apis:
            return QualityScore(
                dimension=QualityDimension.HALLUCINATION_FREE,
                score=1.0,
                issues=issues,
            )
        # API呼び出しパターン（関数呼び出し風: name(...)）
        api_pattern = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_.]*)\s*\(")
        refs = set(api_pattern.findall(text))
        if not refs:
            return QualityScore(
                dimension=QualityDimension.HALLUCINATION_FREE,
                score=1.0,
                issues=issues,
            )
        unknown = refs - known_apis
        if unknown:
            issues.append(
                f"不明なAPI参照: {', '.join(sorted(unknown))}"
            )
        known_count = len(refs) - len(unknown)
        score = known_count / len(refs) if refs else 1.0
        return QualityScore(
            dimension=QualityDimension.HALLUCINATION_FREE,
            score=score,
            issues=issues,
        )


# ── AutoRetryPolicy ──


@dataclass
class AutoRetryPolicy:
    """リトライポリシー設定。

    Parameters
    ----------
    max_retries : int
        最大リトライ回数（デフォルト 3）。
    quality_threshold : float
        品質閾値（デフォルト 0.7）。
    include_error_feedback : bool
        リトライ時に品質問題をプロンプトに追加するか（デフォルト True）。
    """

    max_retries: int = 3
    quality_threshold: float = 0.7
    include_error_feedback: bool = True


# ── QualityAwareRetrier ──

# --- 品質チェック付きリトライ: 品質が閾値未満なら自動でAIに再生成を依頼 ---
class QualityAwareRetrier:
    """品質チェックとリトライを統合的に制御する。

    Parameters
    ----------
    validators : list
        バリデータオブジェクトのリスト。
    policy : AutoRetryPolicy
        リトライポリシー。
    """

    def __init__(
        self,
        validators: list[Any],
        policy: AutoRetryPolicy | None = None,
    ) -> None:
        self._validators = validators
        self._policy = policy or AutoRetryPolicy()

    @property
    def policy(self) -> AutoRetryPolicy:
        """現在のリトライポリシーを返す。"""
        return self._policy

    def evaluate(self, response_text: str, context: dict[str, Any]) -> QualityReport:
        """レスポンスの品質を評価する。

        Parameters
        ----------
        response_text : str
            LLMレスポンステキスト。
        context : dict
            バリデーションに使用するコンテキスト情報。
            - ``required_keys``: JSON必須キー (list[str])
            - ``required_headings``: Markdown必須見出し (list[str])
            - ``tasks``: タスクリスト (list[dict])
            - ``min_tasks`` / ``max_tasks``: タスク数制約
            - ``findings``: レビュー指摘 (list[dict])
            - ``required_fields``: 指摘必須フィールド (list[str])
            - ``known_files``: 既知ファイル集合 (set[str])
            - ``known_apis``: 既知API集合 (set[str])

        Returns
        -------
        QualityReport
            品質レポート。
        """
        scores: list[QualityScore] = []
        for validator in self._validators:
            scores.extend(self._run_validator(validator, response_text, context))

        overall = self._calculate_average(scores)
        threshold = self._policy.quality_threshold
        is_acceptable = overall >= threshold

        return QualityReport(
            scores=scores,
            overall_score=overall,
            is_acceptable=is_acceptable,
            threshold=threshold,
            retry_recommended=not is_acceptable,
        )

    def should_retry(self, report: QualityReport, attempt: int) -> bool:
        """リトライすべきかを判定する。

        Parameters
        ----------
        report : QualityReport
            品質レポート。
        attempt : int
            現在の試行回数（1始まり）。

        Returns
        -------
        bool
            リトライすべき場合 True。
        """
        if report.is_acceptable:
            return False
        return attempt < self._policy.max_retries

    def build_retry_feedback(self, report: QualityReport) -> str:
        """リトライ用のフィードバックメッセージを構築する。

        Parameters
        ----------
        report : QualityReport
            品質レポート。

        Returns
        -------
        str
            LLMへ追加するフィードバック文字列。
        """
        if not self._policy.include_error_feedback:
            return ""

        lines: list[str] = []
        lines.append("以下の品質問題が検出されました。修正してください:")
        for qs in report.scores:
            if qs.issues:
                lines.append(f"\n[{qs.dimension.value}] (スコア: {qs.score:.2f})")
                for issue in qs.issues:
                    lines.append(f"  - {issue}")
        return "\n".join(lines)

    # ── 内部ヘルパー ──

    def _run_validator(
        self, validator: object, text: str, context: dict[str, Any]
    ) -> list[QualityScore]:
        """単一バリデータからスコアリストを取得する。"""
        scores: list[QualityScore] = []

        if isinstance(validator, StructuralValidator):
            # JSON検証
            json_score = validator.validate_json(text)
            scores.append(json_score)
            # 必須キー検証（JSONが有効で必須キー指定がある場合）
            required_keys = context.get("required_keys")
            if json_score.score == 1.0 and required_keys:
                data = json.loads(text)
                scores.append(
                    validator.validate_required_keys(data, required_keys)
                )
            # Markdown見出し検証
            required_headings = context.get("required_headings")
            if required_headings:
                scores.append(
                    validator.validate_markdown_structure(text, required_headings)
                )

        elif isinstance(validator, CompletenessChecker):
            tasks = context.get("tasks")
            if tasks is not None:
                scores.append(
                    validator.check_task_list(
                        tasks,
                        min_tasks=context.get("min_tasks", 1),
                        max_tasks=context.get("max_tasks", 7),
                    )
                )
            findings = context.get("findings")
            if findings is not None:
                required_fields = context.get("required_fields", [])
                scores.append(
                    validator.check_review_findings(findings, required_fields)
                )

        elif isinstance(validator, HallucinationDetector):
            known_files = context.get("known_files")
            if known_files is not None:
                scores.append(
                    validator.check_file_references(text, known_files)
                )
            known_apis = context.get("known_apis")
            if known_apis is not None:
                scores.append(
                    validator.check_api_references(text, known_apis)
                )

        return scores

    @staticmethod
    def _calculate_average(scores: list[QualityScore]) -> float:
        """スコアの均等加重平均を算出する。"""
        if not scores:
            return 1.0
        return sum(s.score for s in scores) / len(scores)


# ── ModelQualityTracker ──

# --- 品質トラッカー: モデル別・ロール別の品質統計を蓄積し、劣化を検知 ---
class ModelQualityTracker:
    """モデル別・ロール別の品質統計を追跡する。"""

    def __init__(self) -> None:
        # model_name -> list of (role, report)
        self._model_records: dict[str, list[tuple[str, QualityReport]]] = defaultdict(
            list
        )
        # role -> list of (model_name, report)
        self._role_records: dict[str, list[tuple[str, QualityReport]]] = defaultdict(
            list
        )

    def record(self, model_name: str, role: str, report: QualityReport) -> None:
        """品質レポートを記録する。

        Parameters
        ----------
        model_name : str
            モデル名。
        role : str
            ロール（例: "planner", "reviewer"）。
        report : QualityReport
            品質レポート。
        """
        self._model_records[model_name].append((role, report))
        self._role_records[role].append((model_name, report))
        logger.info(
            "品質記録: model=%s role=%s score=%.2f acceptable=%s",
            model_name,
            role,
            report.overall_score,
            report.is_acceptable,
        )

    def get_model_stats(self, model_name: str) -> dict[str, Any]:
        """モデル別の品質統計を取得する。

        Parameters
        ----------
        model_name : str
            モデル名。

        Returns
        -------
        dict
            統計情報。キー:
            - ``total_evaluations``: 評価回数
            - ``average_score``: 平均スコア
            - ``acceptance_rate``: 許容率
            - ``role_breakdown``: ロール別の平均スコア
        """
        records = self._model_records.get(model_name, [])
        if not records:
            return {
                "total_evaluations": 0,
                "average_score": 0.0,
                "acceptance_rate": 0.0,
                "role_breakdown": {},
            }
        scores = [r.overall_score for _, r in records]
        accepted = sum(1 for _, r in records if r.is_acceptable)

        # ロール別集計
        role_scores: dict[str, list[float]] = defaultdict(list)
        for role, report in records:
            role_scores[role].append(report.overall_score)
        role_breakdown = {
            role: sum(s) / len(s) for role, s in role_scores.items()
        }

        return {
            "total_evaluations": len(records),
            "average_score": sum(scores) / len(scores),
            "acceptance_rate": accepted / len(records),
            "role_breakdown": role_breakdown,
        }

    def get_role_stats(self, role: str) -> dict[str, Any]:
        """ロール別の品質統計を取得する。

        Parameters
        ----------
        role : str
            ロール名。

        Returns
        -------
        dict
            統計情報。キー:
            - ``total_evaluations``: 評価回数
            - ``average_score``: 平均スコア
            - ``acceptance_rate``: 許容率
            - ``model_breakdown``: モデル別の平均スコア
        """
        records = self._role_records.get(role, [])
        if not records:
            return {
                "total_evaluations": 0,
                "average_score": 0.0,
                "acceptance_rate": 0.0,
                "model_breakdown": {},
            }
        scores = [r.overall_score for _, r in records]
        accepted = sum(1 for _, r in records if r.is_acceptable)

        # モデル別集計
        model_scores: dict[str, list[float]] = defaultdict(list)
        for model_name, report in records:
            model_scores[model_name].append(report.overall_score)
        model_breakdown = {
            model: sum(s) / len(s) for model, s in model_scores.items()
        }

        return {
            "total_evaluations": len(records),
            "average_score": sum(scores) / len(scores),
            "acceptance_rate": accepted / len(records),
            "model_breakdown": model_breakdown,
        }
