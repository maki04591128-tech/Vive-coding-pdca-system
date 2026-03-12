"""PDCAサイクルテンプレート管理。

提案10: サイクル種別ごとのテンプレート定義・フェーズ設定・
ペルソナ重み付け・レジストリ・エクスポートを提供する。

- サイクル種別（STANDARD / HOTFIX / REFACTORING 等）
- フェーズ設定（タイムアウト・ゲート条件）
- ペルソナ重み付け
- テンプレートレジストリ
- デフォルトテンプレートの定義
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# サイクル種別
# ============================================================


class CycleType(StrEnum):
    """PDCAサイクルの種別。"""

    STANDARD = "standard"
    HOTFIX = "hotfix"
    REFACTORING = "refactoring"
    SECURITY_PATCH = "security_patch"
    FEATURE = "feature"


# ============================================================
# フェーズ設定
# ============================================================


@dataclass
class PhaseConfig:
    """サイクル内の1フェーズの設定。"""

    phase_name: str
    timeout_minutes: int
    gate_conditions: list[str] = field(default_factory=list)
    enabled: bool = True


# ============================================================
# ペルソナ重み付け
# ============================================================


@dataclass
class PersonaWeight:
    """サイクル内でのペルソナの重み付け。"""

    persona_name: str
    weight: float = 1.0
    is_active: bool = True


# ============================================================
# サイクルテンプレート
# ============================================================


@dataclass
class CycleTemplate:
    """PDCAサイクルのテンプレート定義。"""

    template_id: str
    name: str
    cycle_type: CycleType
    phases: list[PhaseConfig] = field(default_factory=list)
    personas: list[PersonaWeight] = field(default_factory=list)
    max_tasks: int = 7
    description: str = ""


# ============================================================
# テンプレートレジストリ
# ============================================================


class TemplateRegistry:
    """サイクルテンプレートの登録・検索・管理を行うレジストリ。"""

    def __init__(self) -> None:
        self._templates: dict[str, CycleTemplate] = {}

    def register(self, template: CycleTemplate) -> None:
        """テンプレートを登録する。"""
        self._templates[template.template_id] = template
        logger.info(
            "テンプレート登録: %s (%s)",
            template.template_id, template.name,
        )

    def get(self, template_id: str) -> CycleTemplate | None:
        """テンプレートIDで取得する。見つからなければ None。"""
        return self._templates.get(template_id)

    def list_templates(self) -> list[CycleTemplate]:
        """全テンプレートをID順で返す。"""
        return sorted(
            self._templates.values(),
            key=lambda t: t.template_id,
        )

    def get_by_type(self, cycle_type: CycleType) -> list[CycleTemplate]:
        """指定種別のテンプレートを返す。"""
        return sorted(
            (
                t for t in self._templates.values()
                if t.cycle_type == cycle_type
            ),
            key=lambda t: t.template_id,
        )

    def unregister(self, template_id: str) -> bool:
        """テンプレートを削除する。存在した場合は True。"""
        if template_id in self._templates:
            del self._templates[template_id]
            logger.info("テンプレート削除: %s", template_id)
            return True
        return False

    @property
    def count(self) -> int:
        """登録済みテンプレート数を返す。"""
        return len(self._templates)


# ============================================================
# テンプレートエクスポーター
# ============================================================


class TemplateExporter:
    """テンプレートの辞書形式へのエクスポート・インポートを行う。"""

    def export_dict(self, template: CycleTemplate) -> dict[str, Any]:
        """テンプレートを辞書形式にエクスポートする。"""
        return {
            "template_id": template.template_id,
            "name": template.name,
            "cycle_type": template.cycle_type.value,
            "phases": [
                {
                    "phase_name": p.phase_name,
                    "timeout_minutes": p.timeout_minutes,
                    "gate_conditions": list(p.gate_conditions),
                    "enabled": p.enabled,
                }
                for p in template.phases
            ],
            "personas": [
                {
                    "persona_name": pw.persona_name,
                    "weight": pw.weight,
                    "is_active": pw.is_active,
                }
                for pw in template.personas
            ],
            "max_tasks": template.max_tasks,
            "description": template.description,
        }

    def import_dict(self, data: dict[str, Any]) -> CycleTemplate:
        """辞書形式からテンプレートをインポートする。"""
        for key in ("template_id", "name", "cycle_type"):
            if key not in data:
                raise ValueError(f"テンプレートに必須キー '{key}' がありません")
        try:
            cycle_type = CycleType(data["cycle_type"])
        except ValueError as err:
            raise ValueError(
                f"不正なサイクル種別: {data['cycle_type']!r}"
            ) from err
        phases = [
            PhaseConfig(
                phase_name=p["phase_name"],
                timeout_minutes=p["timeout_minutes"],
                gate_conditions=p.get("gate_conditions", []),
                enabled=p.get("enabled", True),
            )
            for p in data.get("phases", [])
        ]
        personas = [
            PersonaWeight(
                persona_name=pw["persona_name"],
                weight=pw.get("weight", 1.0),
                is_active=pw.get("is_active", True),
            )
            for pw in data.get("personas", [])
        ]
        return CycleTemplate(
            template_id=data["template_id"],
            name=data["name"],
            cycle_type=cycle_type,
            phases=phases,
            personas=personas,
            max_tasks=data.get("max_tasks", 7),
            description=data.get("description", ""),
        )


# ============================================================
# デフォルトテンプレート
# ============================================================


DEFAULT_TEMPLATES: list[CycleTemplate] = [
    CycleTemplate(
        template_id="standard-v1",
        name="標準PDCAサイクル",
        cycle_type=CycleType.STANDARD,
        phases=[
            PhaseConfig(
                phase_name="Plan",
                timeout_minutes=60,
                gate_conditions=["タスク一覧の確定"],
            ),
            PhaseConfig(
                phase_name="Do",
                timeout_minutes=120,
                gate_conditions=["全タスク実行完了"],
            ),
            PhaseConfig(
                phase_name="Check",
                timeout_minutes=30,
                gate_conditions=["品質スコア 0.7 以上"],
            ),
            PhaseConfig(
                phase_name="Act",
                timeout_minutes=30,
                gate_conditions=["改善提案の記録"],
            ),
        ],
        personas=[
            PersonaWeight(persona_name="planner", weight=1.0),
            PersonaWeight(persona_name="executor", weight=1.0),
            PersonaWeight(persona_name="reviewer", weight=1.0),
        ],
        max_tasks=7,
        description="標準的なPDCAサイクルテンプレート",
    ),
    CycleTemplate(
        template_id="hotfix-v1",
        name="ホットフィックスサイクル",
        cycle_type=CycleType.HOTFIX,
        phases=[
            PhaseConfig(
                phase_name="Plan",
                timeout_minutes=15,
                gate_conditions=["原因特定"],
            ),
            PhaseConfig(
                phase_name="Do",
                timeout_minutes=60,
                gate_conditions=["修正完了"],
            ),
            PhaseConfig(
                phase_name="Check",
                timeout_minutes=15,
                gate_conditions=["回帰テスト通過"],
            ),
            PhaseConfig(
                phase_name="Act",
                timeout_minutes=10,
                gate_conditions=["ポストモーテム記録"],
            ),
        ],
        personas=[
            PersonaWeight(persona_name="executor", weight=1.5),
            PersonaWeight(persona_name="reviewer", weight=1.0),
        ],
        max_tasks=3,
        description="緊急修正用の短縮サイクルテンプレート",
    ),
]
