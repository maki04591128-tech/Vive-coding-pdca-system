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
