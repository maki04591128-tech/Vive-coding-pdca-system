"""GUI コンポーネント – ダッシュボードに表示するカード型ウィジェット群。

このパッケージには、ダッシュボード画面を構成する再利用可能な
UI部品（ウィジェット）が含まれています。

含まれるコンポーネント:
  - StatusCard      : LLMプロバイダの状態表示カード（正常/障害/フォールバック）
  - CostCard        : API利用コストの表示カード
  - PDCAStatusCard  : PDCAサイクルの進行状況を表示するカード
  - TimelineCard    : PDCAタイムラインの時系列表示カード
  - CostChartCard   : コスト推移のバーチャート表示カード
  - TraceabilityCard: アーティファクト間トレーサビリティ表示カード
  - RadarCard       : ペルソナ別スコアのレーダーチャート風カード
  - AlertPanel      : レベル別フィルタ付きアラート通知パネル
"""

import contextlib

__all__ = [
    "StatusCard",
    "CostCard",
    "PDCAStatusCard",
    "TimelineCard",
    "CostChartCard",
    "TraceabilityCard",
    "RadarCard",
    "AlertPanel",
]

with contextlib.suppress(ImportError):  # flet が未インストールの場合
    from vibe_pdca.gui.components.alert_panel import AlertPanel
    from vibe_pdca.gui.components.cost_chart_card import CostChartCard
    from vibe_pdca.gui.components.pdca_card import PDCAStatusCard
    from vibe_pdca.gui.components.radar_card import RadarCard
    from vibe_pdca.gui.components.status_card import CostCard, StatusCard
    from vibe_pdca.gui.components.timeline_card import TimelineCard
    from vibe_pdca.gui.components.traceability_card import TraceabilityCard
