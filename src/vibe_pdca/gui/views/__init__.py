"""GUI ビュー – 画面単位のレイアウトを定義するモジュール群。

このパッケージには、アプリケーションの各画面（ページ）の
レイアウトと表示ロジックが含まれています。

含まれるビュー:
  - DashboardView    : メインダッシュボード画面（ステータス・PDCA・ログ・コスト表示）
  - GoalInputView    : 最終到達点入力画面（§10.1）
  - ProgressView     : 進捗閲覧画面（§10.3）
  - InterventionView : 介入操作画面（§10.4）
  - ModeSettingsView : 運転モード設定画面（§10.2）
"""

import contextlib

__all__ = [
    "DashboardView",
    "GoalInputView",
    "ProgressView",
    "InterventionView",
    "ModeSettingsView",
]

with contextlib.suppress(ImportError):  # flet が未インストールの場合
    from vibe_pdca.gui.views.dashboard import DashboardView
    from vibe_pdca.gui.views.goal_input import GoalInputView
    from vibe_pdca.gui.views.intervention_view import InterventionView
    from vibe_pdca.gui.views.mode_settings import ModeSettingsView
    from vibe_pdca.gui.views.progress_view import ProgressView
