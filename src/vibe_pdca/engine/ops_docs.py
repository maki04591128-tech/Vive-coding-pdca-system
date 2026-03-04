"""運用文書テンプレート – Runbook / Incident Playbook / Approval / Release Checklist。

M3 タスク 3-11: 要件定義書 §26.6 準拠。
"""

from __future__ import annotations

# ── Runbook テンプレート ──

RUNBOOK_TEMPLATE = """\
# Runbook: バイブコーディングPDCA運用手順

## 1. 日常運用

### 1.1 システム起動
1. 環境変数を確認（`.env` / `config/`）
2. `python -m vibe_pdca` を実行
3. ダッシュボードで状態を確認

### 1.2 PDCAサイクルの開始
1. Web UIで「最終到達点」を入力
2. 要件定義確定フローを完了（差分質問→5ペルソナレビュー）
3. 運転モードを選択（手動 / 半自動 / 全自動）
4. PDCA開始ボタンを押下

### 1.3 日次確認
- ダッシュボードで進捗・コスト・アラートを確認
- 未確認アラートがあれば対処
- コスト上限に近づいていないか確認

## 2. 停止・再開

### 2.1 手動停止
1. Web UIの停止ボタンを押下
2. 停止理由を記録
3. 介入操作レポートを確認

### 2.2 自動停止からの再開
1. 停止原因を確認（介入操作レポート参照）
2. 再開条件をすべて満たしていることを確認
3. 再開ボタンを押下（Owner承認が必要な場合あり）

## 3. 障害対応

### 3.1 P0インシデント
→ Incident Playbook §P0 を参照

### 3.2 P1インシデント
→ Incident Playbook §P1 を参照
"""

# ── Incident Playbook テンプレート ──

INCIDENT_PLAYBOOK_TEMPLATE = """\
# Incident Playbook: インシデント対応手順

## P0: 即停止

### トリガー
- 重大なセキュリティ侵害
- 監査ログの改ざん検知
- 本番環境への想定外の変更

### 対応手順
1. **即座に全サイクルを停止**
2. 影響範囲を特定（どのプロジェクト・マイルストーン・タスクに影響があるか）
3. Ownerに緊急通知（Discord）
4. 原因分析を実施（介入操作レポートを参照）
5. ロールバック候補を評価
6. 修正を適用
7. テストで検証
8. Ownerの承認を得て再開

### エスカレーション
- 30分以内に原因特定できない場合 → 外部支援を要請

## P1: 縮退 + 人間介入

### トリガー
- CI連続失敗（5回）
- diff超過
- サイクルタイムアウト（6時間）

### 対応手順
1. 縮退モードへ自動移行
2. 影響機能を特定
3. Maintainerに通知
4. 原因分析を実施
5. 修正方針を決定（ロールバック or 前進修正）
6. 修正を適用
7. Maintainerの承認を得て再開

## P2: 次サイクルで是正

### トリガー
- 軽微なテスト失敗
- パフォーマンス低下

### 対応手順
1. 次サイクルのPLANに是正タスクを自動追加
2. 学習フィードバックに記録
"""

# ── Approval Checklist テンプレート ──

APPROVAL_CHECKLIST_TEMPLATE = """\
# Approval Checklist: 承認チェックリスト

## A操作承認チェックリスト
- [ ] 操作内容を確認した
- [ ] 影響範囲を評価した
- [ ] ロールバック手順を確認した
- [ ] バックアップを確認した
- [ ] Discord上で4/4承認を得た
- [ ] 監査ログに記録されている

## B操作確認チェックリスト
- [ ] バックアップが自動作成されている
- [ ] 通知がDiscordに送信されている
- [ ] 監査ログに記録されている

## モード切替チェックリスト
- [ ] 現在のモードと切替先を確認
- [ ] 権限を確認（Owner/Maintainer）
- [ ] 進行中のサイクルがないか確認
"""

# ── Release Checklist テンプレート ──

RELEASE_CHECKLIST_TEMPLATE = """\
# Release Checklist: リリースチェックリスト

## リリース前
- [ ] 全テストが通過している
- [ ] ruff lint がクリーンである
- [ ] mypy 型チェックが通過している
- [ ] セキュリティスキャンが完了している
- [ ] ドキュメントが更新されている
- [ ] バックアップが作成されている

## stg環境検証
- [ ] stg環境でのドライラン成功
- [ ] stg環境でのPDCA1サイクル完了
- [ ] ダッシュボード表示が正常
- [ ] Discord通知が正常に配信

## prod環境デプロイ
- [ ] Ownerの承認を得ている
- [ ] デプロイ手順を確認
- [ ] ロールバック手順を確認
- [ ] デプロイ後の動作確認完了
"""


def get_template(name: str) -> str:
    """テンプレートを名前で取得する。"""
    templates: dict[str, str] = {
        "runbook": RUNBOOK_TEMPLATE,
        "incident_playbook": INCIDENT_PLAYBOOK_TEMPLATE,
        "approval_checklist": APPROVAL_CHECKLIST_TEMPLATE,
        "release_checklist": RELEASE_CHECKLIST_TEMPLATE,
    }
    if name not in templates:
        raise KeyError(
            f"テンプレート '{name}' が見つかりません。"
            f"利用可能: {list(templates.keys())}"
        )
    return templates[name]


def list_templates() -> list[str]:
    """利用可能なテンプレート名を返す。"""
    return [
        "runbook",
        "incident_playbook",
        "approval_checklist",
        "release_checklist",
    ]
