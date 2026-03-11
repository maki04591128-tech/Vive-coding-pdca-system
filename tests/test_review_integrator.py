"""レビュー統合（ReviewIntegrator）のテスト。"""

import pytest

from vibe_pdca.engine.review_integrator import (
    ReviewIntegrator,
)
from vibe_pdca.models.pdca import (
    ReviewCategory,
    ReviewFinding,
    Severity,
)

# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture
def integrator():
    return ReviewIntegrator()


def _make_finding(
    *,
    reviewer: str = "programmer",
    severity: Severity = Severity.MAJOR,
    category: ReviewCategory = ReviewCategory.CORRECTNESS,
    description: str = "テスト指摘",
    confidence: float = 0.8,
    file_path: str | None = None,
    finding_id: str = "f-001",
) -> ReviewFinding:
    return ReviewFinding(
        id=finding_id,
        reviewer_role=reviewer,
        severity=severity,
        category=category,
        description=description,
        confidence=confidence,
        file_path=file_path,
    )


# ============================================================
# テスト: 基本統合
# ============================================================


class TestBasicIntegration:
    def test_empty_findings(self, integrator):
        result = integrator.integrate([])
        assert len(result.prioritized) == 0
        assert result.summary.blocker_count == 0

    def test_single_finding(self, integrator):
        finding = _make_finding()
        result = integrator.integrate([finding])
        assert len(result.prioritized) == 1
        assert result.prioritized[0].finding.id == finding.id

    def test_multiple_unique_findings(self, integrator):
        findings = [
            _make_finding(
                finding_id=f"f-{i}",
                reviewer=role,
                description=desc,
            )
            for i, (role, desc) in enumerate([
                ("programmer", "バッファオーバーフローの脆弱性が存在する"),
                ("pm", "タスクの依存関係が未定義である"),
                ("designer", "フォントサイズがアクセシビリティ基準を満たさない"),
                ("user", "エラーメッセージが不親切で意味不明"),
                ("scribe", "APIドキュメントに引数の説明が不足している"),
            ])
        ]
        result = integrator.integrate(findings)
        assert len(result.prioritized) == 5


# ============================================================
# テスト: 重複排除
# ============================================================


class TestDeduplication:
    def test_similar_findings_merged(self, integrator):
        """同一カテゴリ・類似説明の指摘がクラスタ化されること。"""
        findings = [
            _make_finding(
                finding_id="f-1",
                reviewer="programmer",
                description="nullチェックが不足しています",
            ),
            _make_finding(
                finding_id="f-2",
                reviewer="pm",
                description="nullチェックが不足している",
            ),
        ]
        result = integrator.integrate(findings)
        # クラスタ化されて1件に統合
        assert len(result.prioritized) == 1
        # 両方のレビュアが出典として記録
        assert len(result.prioritized[0].sources) == 2

    def test_different_categories_not_merged(self, integrator):
        """異なるカテゴリの指摘はマージされないこと。"""
        findings = [
            _make_finding(
                finding_id="f-1",
                category=ReviewCategory.CORRECTNESS,
                description="エラーが発生する",
            ),
            _make_finding(
                finding_id="f-2",
                category=ReviewCategory.PERFORMANCE,
                description="エラーが発生する",
            ),
        ]
        result = integrator.integrate(findings)
        assert len(result.prioritized) == 2

    def test_different_files_not_merged(self, integrator):
        """異なるファイルの指摘はマージされないこと。"""
        findings = [
            _make_finding(
                finding_id="f-1",
                file_path="src/a.py",
                description="同じ説明文",
            ),
            _make_finding(
                finding_id="f-2",
                file_path="src/b.py",
                description="同じ説明文",
            ),
        ]
        result = integrator.integrate(findings)
        assert len(result.prioritized) == 2


# ============================================================
# テスト: 優先度算出
# ============================================================


class TestPriorityCalculation:
    def test_blocker_has_highest_priority(self, integrator):
        """BLOCKERが最高優先度になること。"""
        findings = [
            _make_finding(
                finding_id="f-blocker",
                severity=Severity.BLOCKER,
                confidence=1.0,
                reviewer="programmer",
            ),
            _make_finding(
                finding_id="f-minor",
                severity=Severity.MINOR,
                confidence=1.0,
                reviewer="programmer",
                description="軽微な指摘",
            ),
        ]
        result = integrator.integrate(findings)
        assert result.prioritized[0].finding.id == "f-blocker"
        assert result.prioritized[0].priority_score > result.prioritized[1].priority_score

    def test_priority_formula(self, integrator):
        """優先度 = 重大度 × 確信度 × ペルソナ重み の計算が正しいこと。"""
        finding = _make_finding(
            severity=Severity.BLOCKER,  # 1.0
            confidence=0.9,
            reviewer="programmer",  # 1.0
        )
        result = integrator.integrate([finding])
        expected = round(1.0 * 0.9 * 1.0, 4)
        assert result.prioritized[0].priority_score == expected

    def test_persona_weight_affects_priority(self, integrator):
        """ペルソナ重みが優先度に反映されること。"""
        findings = [
            _make_finding(
                finding_id="f-prog",
                reviewer="programmer",  # 1.0
                confidence=0.8,
                description="programmer指摘",
            ),
            _make_finding(
                finding_id="f-scribe",
                reviewer="scribe",  # 0.80
                confidence=0.8,
                description="scribe指摘",
            ),
        ]
        result = integrator.integrate(findings)
        prog = next(p for p in result.prioritized if p.finding.id == "f-prog")
        scribe = next(p for p in result.prioritized if p.finding.id == "f-scribe")
        assert prog.priority_score > scribe.priority_score

    def test_sorted_by_priority_descending(self, integrator):
        """優先度の降順でソートされていること。"""
        findings = [
            _make_finding(
                finding_id="f-1",
                severity=Severity.MINOR,
                description="軽微",
            ),
            _make_finding(
                finding_id="f-2",
                severity=Severity.BLOCKER,
                description="重大",
            ),
            _make_finding(
                finding_id="f-3",
                severity=Severity.MAJOR,
                description="中程度",
            ),
        ]
        result = integrator.integrate(findings)
        scores = [p.priority_score for p in result.prioritized]
        assert scores == sorted(scores, reverse=True)


# ============================================================
# テスト: 対立検出
# ============================================================


class TestConflictDetection:
    def test_conflicting_severities_detected(self, integrator):
        """同一ファイル・カテゴリでBLOCKERとMINORの対立を検出すること。"""
        findings = [
            _make_finding(
                finding_id="f-1",
                severity=Severity.BLOCKER,
                file_path="src/main.py",
                description="重大な脆弱性",
                category=ReviewCategory.SECURITY,
            ),
            _make_finding(
                finding_id="f-2",
                severity=Severity.MINOR,
                file_path="src/main.py",
                description="軽微なスタイル問題",
                category=ReviewCategory.SECURITY,
            ),
        ]
        result = integrator.integrate(findings)
        assert result.has_conflicts
        assert result.escalation_needed

    def test_no_conflict_same_severity(self, integrator):
        """同一重大度の場合は対立なし。"""
        findings = [
            _make_finding(
                finding_id="f-1",
                severity=Severity.MAJOR,
                file_path="src/main.py",
                description="指摘A",
                category=ReviewCategory.CORRECTNESS,
            ),
            _make_finding(
                finding_id="f-2",
                severity=Severity.MAJOR,
                file_path="src/main.py",
                description="指摘B",
                category=ReviewCategory.CORRECTNESS,
            ),
        ]
        result = integrator.integrate(findings)
        assert not result.has_conflicts


# ============================================================
# テスト: ペルソナ重み調整
# ============================================================


class TestWeightAdjustment:
    def test_adjust_within_range(self, integrator):
        """±0.05以内の調整が反映されること。"""
        old = integrator.persona_weights["scribe"]
        new = integrator.adjust_weight("scribe", 0.05)
        assert new == old + 0.05

    def test_adjust_clamped_to_005(self, integrator):
        """±0.05を超える調整がクランプされること。"""
        old = integrator.persona_weights["scribe"]
        new = integrator.adjust_weight("scribe", 0.20)
        assert new == old + 0.05

    def test_minimum_weight_050(self, integrator):
        """最低保証0.50が維持されること。"""
        # scribe: 0.80 → -0.05を7回
        for _ in range(7):
            integrator.adjust_weight("scribe", -0.05)
        assert integrator.persona_weights["scribe"] >= 0.50

    def test_maximum_weight_100(self, integrator):
        """最大値1.00を超えないこと。"""
        integrator.adjust_weight("programmer", 0.05)
        assert integrator.persona_weights["programmer"] <= 1.00

    def test_unknown_persona_raises(self, integrator):
        with pytest.raises(ValueError, match="不明なペルソナ"):
            integrator.adjust_weight("unknown_role", 0.01)


# ============================================================
# テスト: サマリ生成
# ============================================================


class TestSummary:
    def test_summary_counts(self, integrator):
        findings = [
            _make_finding(finding_id="f-1", severity=Severity.BLOCKER, description="A"),
            _make_finding(finding_id="f-2", severity=Severity.MAJOR, description="B"),
            _make_finding(finding_id="f-3", severity=Severity.MINOR, description="C"),
        ]
        result = integrator.integrate(findings)
        assert result.summary.blocker_count == 1
        assert result.summary.major_count == 1
        assert result.summary.minor_count == 1

    def test_dod_not_achieved_with_blockers(self, integrator):
        findings = [
            _make_finding(severity=Severity.BLOCKER),
        ]
        result = integrator.integrate(findings)
        assert result.summary.dod_achieved is False
        assert len(result.summary.dod_unmet_reasons) > 0

    def test_dod_achieved_without_blockers(self, integrator):
        findings = [
            _make_finding(severity=Severity.MINOR),
        ]
        result = integrator.integrate(findings)
        assert result.summary.dod_achieved is True

    def test_to_dict(self, integrator):
        findings = [
            _make_finding(severity=Severity.BLOCKER),
        ]
        result = integrator.integrate(findings)
        d = result.to_dict()
        assert "finding_count" in d
        assert "blocker_count" in d
        assert "escalation_needed" in d


# ============================================================
# テスト: 入力バリデーション
# ============================================================


class TestReviewIntegratorValidation:
    """ReviewIntegrator の入力バリデーション。"""

    def test_negative_similarity_threshold_rejected(self):
        import pytest
        with pytest.raises(ValueError, match="similarity_threshold"):
            ReviewIntegrator(similarity_threshold=-0.1)

    def test_over_one_similarity_threshold_rejected(self):
        import pytest
        with pytest.raises(ValueError, match="similarity_threshold"):
            ReviewIntegrator(similarity_threshold=1.5)

    def test_valid_boundary_values(self):
        ri0 = ReviewIntegrator(similarity_threshold=0.0)
        ri1 = ReviewIntegrator(similarity_threshold=1.0)
        assert ri0._similarity_threshold == 0.0
        assert ri1._similarity_threshold == 1.0
