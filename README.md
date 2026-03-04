# バイブコーディングPDCA自動開発システム

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)

## 概要

バイブコーディングPDCA自動開発システムは、**目標（最終到達点）を入力するだけで PLAN→DO→CHECK→ACT の自動PDCAサイクルを回し、ソフトウェアを自律的に開発**するシステムです。

5ペルソナ（PM/Architect/Security/QA/UX）による自動レビュー、ガバナンス承認ワークフロー、監査ログによる完全追跡、コスト管理、セキュリティ強化を備えています。

## システムアーキテクチャ

```
┌──────────────────────────────────────────────────────────────────────┐
│                    バイブコーディングPDCA                              │
│                                                                      │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐          │
│  │  PLAN   │───→│   DO    │───→│  CHECK  │───→│   ACT   │──→繰返  │
│  │ Planner │    │Executor │    │ Checker │    │Decision │          │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘          │
│       │              │              │              │                 │
│       ▼              ▼              ▼              ▼                 │
│  ┌──────────────────────────────────────────────────────┐           │
│  │              監査ログ + トレーサビリティ               │           │
│  └──────────────────────────────────────────────────────┘           │
│                                                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                   │
│  │ガバナンス    │ │コスト管理    │ │セキュリティ  │                   │
│  │A/B/C分類    │ │$30/日上限   │ │入力バリデ   │                   │
│  └─────────────┘ └─────────────┘ └─────────────┘                   │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │               LLMゲートウェイ（マルチモデル）               │     │
│  │  クラウドLLM ←→ サーキットブレーカー ←→ ローカルLLM       │     │
│  └────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
```

## 機能一覧

### M1: 基盤（データモデル・状態管理）
| 機能 | モジュール | 説明 |
|------|-----------|------|
| PDCAデータモデル | `models/pdca.py` | Goal/Milestone/Task/Cycle/Decision/AuditEntry |
| PDCA状態機械 | `engine/` | PLAN→DO→CHECK→ACT 自動遷移 |
| 監査ログ | `audit/` | 追記専用・チェーンハッシュ・改ざん検知 |
| プロンプト管理 | `prompts/` | 役割別テンプレート・バージョン管理 |
| トレーサビリティ | `monitoring/` | Goal→MS→Task→PR→Review→Decision 双方向追跡 |
| RBAC | `governance/` | Owner/Maintainer/Viewer ロール |
| 用語集 | `glossary/` | 統一用語・エイリアス自動変換 |

### M2: PDCAエンジン
| 機能 | モジュール | 説明 |
|------|-----------|------|
| PLANフェーズ | `engine/planner.py` | ゴール→マイルストーン→タスク自動分解 |
| DOフェーズ | `engine/executor.py` | タスク実行・変更種別分類・ゲート管理 |
| CHECKフェーズ | `engine/checker.py` | CI統合・DoD判定・5ペルソナレビュー |
| ACTフェーズ | `engine/decision.py` | 採否判定・次サイクル方針・進捗レポート |
| レビュー統合 | `engine/review_integrator.py` | 5ペルソナ統合・重複クラスタリング・優先度付け |
| ガバナンス | `engine/governance.py` | A/B/C操作分類・承認ワークフロー・代替案生成 |
| Discord連携 | `engine/discord_liaison.py` | A操作承認(4/4合意)・B通知・サイクル完了通知 |
| RAGコンテキスト | `engine/context_manager.py` | 5ファイル/2000トークン・10サイクル要約・100リセット |
| 停止条件 | `engine/stop_conditions.py` | 6hスタック検知・5段縮退・自動停止 |
| 要件確定 | `engine/requirements.py` | ギャップ検出→差分質問→5ペルソナレビュー→PDCA |
| 運転モード | `engine/mode_controller.py` | 手動/半自動/全自動 切替 |
| マルチプロジェクト | `engine/multi_project.py` | 物理隔離・重複検出・コスト上限 |
| 介入操作 | `engine/intervention.py` | P0/P1/P2分類・根本原因分析・ロールバック |

### M3: 品質と運用
| 機能 | モジュール | 説明 |
|------|-----------|------|
| 保持期間管理 | `audit/retention.py` | 監査365日/メトリクス90日/レビュー180日・自動パージ |
| 可観測性 | `monitoring/metrics.py` | サイクル成功率・CI率・モデル別メトリクス・アラート |
| セキュリティ | `engine/security.py` | プロンプトインジェクション対策・パストラバーサル防止 |
| コスト管理 | `engine/cost_manager.py` | 80回/サイクル・500回/日・$30/日・異常検知 |
| バックアップ | `engine/backup.py` | B操作前自動作成・SHA-256整合性・180日保持 |
| 劣化検知 | `engine/degradation.py` | 10サイクル連続観測・ペルソナ重み±0.05調整 |
| ドライラン | `engine/dry_run.py` | PLAN→CHECKシミュレーション・外部書込なし |
| コスト見積もり | `engine/cost_estimator.py` | MS/サイクル/タスク/LLMコスト推定 |
| Suppress List | `engine/suppress_list.py` | 誤検知登録・A操作承認・有効期限 |
| 学習FB | `engine/learning.py` | 10サイクルごと失敗パターン→PLANプロンプト |
| 運用文書 | `engine/ops_docs.py` | Runbook/Playbook/Checklist テンプレート |
| エクスポート | `engine/exporter.py` | JSON/JSONL/Markdown 監査/決定/レビュー |
| インシデント | `engine/incident_report.py` | P0/P1定型レポート・是正措置・再開条件 |

### M4: リリース
| 機能 | テスト | 説明 |
|------|-------|------|
| 受入基準検証 | `tests/test_acceptance.py` | §23の12項目すべてを統合テストで検証 |
| セキュリティ検証 | `tests/test_security_redteam.py` | プロンプト注入5パターン（Issue/PR/README/CI/依存） |

### LLMゲートウェイ
| 機能 | モジュール | 説明 |
|------|-----------|------|
| 統一ゲートウェイ | `llm/gateway.py` | 役割→プロバイダマッピング・コスト追跡 |
| サーキットブレーカー | `llm/circuit_breaker.py` | CLOSED→OPEN→HALF_OPEN 自動フォールバック |
| ヘルスチェック | `llm/health.py` | 定期死活監視 |
| プロバイダ | `llm/providers.py` | クラウド(OpenAI/Anthropic/Google) + ローカル(Ollama) |

## セットアップ

### 1. インストール

```bash
# 基本（バックエンドのみ）
pip install -e ".[dev]"

# GUI 付き（デスクトップ / モバイルアプリ対応）
pip install -e ".[dev,gui]"
```

### 2. 環境変数

`.env.example` を `.env` にコピーして API キーを設定してください。

```bash
cp .env.example .env
# .env を編集して各プロバイダの API キーを設定
```

### 3. ローカルLLM（Ollama）のセットアップ

```bash
# Ollama インストール
curl -fsSL https://ollama.com/install.sh | sh

# 役割別デフォルトモデルのダウンロード
ollama pull qwen3:72b       # PM・書記用
ollama pull codestral:22b   # プログラマ・DO用
ollama pull llama3.3:70b    # デザイナ用
ollama pull gemma3:27b      # ユーザ用
```

### 4. テスト実行

```bash
pytest tests/ -v
```

## 使い方

### 基本的な使用例

```python
from vibe_pdca.config import load_config, build_gateway_from_config
from vibe_pdca.llm.models import LLMRequest, Role

# 設定ファイルからゲートウェイを構築
config = load_config(config_dir="config", env="dev")
gateway = build_gateway_from_config(config)

# LLM 呼び出し
request = LLMRequest(
    role=Role.PM,
    system_prompt="あなたはプロジェクトマネージャーです。",
    user_prompt="このタスクを分解してください。",
)
response = gateway.call(request)
print(response.content)
```

### PDCAサイクルの実行例

```python
from vibe_pdca.engine.planner import Planner
from vibe_pdca.engine.executor import Executor
from vibe_pdca.engine.checker import Checker
from vibe_pdca.engine.decision import ActDecisionMaker
from vibe_pdca.models.pdca import Goal

# 1. PLAN: ゴール → マイルストーン → タスク
planner = Planner()
goal = Goal(id="g-1", purpose="REST APIサーバー構築",
            acceptance_criteria=["認証", "CRUD", "テスト"])
milestones = planner.generate_milestones(goal)

# 2. DO: タスク実行
executor = Executor()
tasks = planner.generate_tasks(milestones[0])
result = executor.execute_tasks(tasks)

# 3. CHECK: CI + レビュー + DoD判定
checker = Checker()
check_result = checker.run_check(context)

# 4. ACT: 採否判定 → 次サイクル
decision_maker = ActDecisionMaker()
decision = decision_maker.make_decision(check_result)
```

### コスト管理

```python
from vibe_pdca.engine.cost_manager import CostManager, CostAction

cm = CostManager(daily_cost_limit_usd=30.0)
result = cm.record_call(tokens=500, cost_usd=0.15)
if result.action == CostAction.STOP:
    print(result.reason)
```

### ドライラン（外部書込なし）

```python
from vibe_pdca.engine.dry_run import DryRunExecutor

dr = DryRunExecutor()
result = dr.execute("APIサーバー構築", ["認証", "CRUD", "テスト"])
print(result.to_markdown())
```

## 設定

### 設定ファイル階層（§17.5 準拠）

```
config/default.yml              ← グローバルデフォルト
config/environments/dev.yml     ← 開発環境（ローカル優先）
config/environments/prod.yml    ← 本番環境（クラウド優先）
.vibe-pdca/config.yml           ← プロジェクト固有設定
```

> **優先順位**: 環境変数 > プロジェクト固有設定 > 環境別設定 > グローバルデフォルト

## ディレクトリ構造

```
vibe-pdca/
├── config/                         # 設定ファイル
│   ├── default.yml
│   └── environments/
├── docs/                           # ドキュメント
│   ├── バイブコーディングPDCAシステム_要件定義書_v6.md
│   ├── バイブコーディングPDCA_実装手順書_v3.md
│   ├── adr/                        # ADR-001〜008
│   ├── ops/                        # Runbook, Playbook 等
│   └── templates/                  # テンプレート
├── src/vibe_pdca/
│   ├── audit/                      # 監査ログ・保持期間管理
│   │   ├── __init__.py             # AuditLog (追記専用/チェーンハッシュ)
│   │   └── retention.py            # RetentionManager (365/90/180日)
│   ├── config/                     # 設定ロード
│   │   └── loader.py
│   ├── engine/                     # PDCAエンジン
│   │   ├── planner.py              # PLANフェーズ
│   │   ├── executor.py             # DOフェーズ
│   │   ├── checker.py              # CHECKフェーズ
│   │   ├── decision.py             # ACTフェーズ
│   │   ├── review_integrator.py    # 5ペルソナレビュー統合
│   │   ├── governance.py           # A/B/C操作分類
│   │   ├── discord_liaison.py      # Discord連携
│   │   ├── context_manager.py      # RAGコンテキスト
│   │   ├── stop_conditions.py      # 停止条件・縮退
│   │   ├── requirements.py         # 要件確定フロー
│   │   ├── mode_controller.py      # 運転モード制御
│   │   ├── multi_project.py        # マルチプロジェクト
│   │   ├── intervention.py         # 介入操作
│   │   ├── cost_manager.py         # コスト管理
│   │   ├── cost_estimator.py       # コスト見積もり
│   │   ├── backup.py               # バックアップ
│   │   ├── degradation.py          # モデル劣化検知
│   │   ├── dry_run.py              # ドライランモード
│   │   ├── security.py             # セキュリティ強化
│   │   ├── suppress_list.py        # Suppress List
│   │   ├── learning.py             # 学習フィードバック
│   │   ├── exporter.py             # エクスポート
│   │   ├── incident_report.py      # インシデントレポート
│   │   └── ops_docs.py             # 運用文書テンプレート
│   ├── glossary/                   # 用語集
│   ├── governance/                 # RBAC
│   ├── gui/                        # GUI (Flet)
│   │   ├── app.py
│   │   ├── views/dashboard.py
│   │   └── components/
│   ├── llm/                        # LLMゲートウェイ
│   │   ├── gateway.py
│   │   ├── circuit_breaker.py
│   │   ├── health.py
│   │   ├── models.py
│   │   └── providers.py
│   ├── models/pdca.py              # データモデル
│   ├── monitoring/                 # トレーサビリティ・メトリクス
│   │   ├── __init__.py             # TraceLinkManager
│   │   └── metrics.py              # MetricsCollector
│   └── prompts/                    # プロンプトテンプレート
├── tests/                          # 523テスト
│   ├── test_acceptance.py          # 受入基準12項目
│   ├── test_security_redteam.py    # セキュリティ検証5パターン
│   └── ...                         # 各モジュールのユニットテスト
├── .env.example
├── pyproject.toml
└── README.md
```

## 受入基準（§23）

| # | 基準 | 状態 |
|---|------|------|
| 1 | ゴール入力→マイルストーン+DoD自動生成 | ✅ |
| 2 | PDCAサイクル自動進行・成果物記録 | ✅ |
| 3 | 5ペルソナレビュー統合 | ✅ |
| 4 | ACT採否・次サイクル方針（理由付き） | ✅ |
| 5 | 停止条件動作・自動停止 | ✅ |
| 6 | 監査ログ追跡（何が・なぜ・いつ） | ✅ |
| 7 | 停止/再開/モード切替操作 | ✅ |
| 8 | インシデント時自動停止・原因・再開条件 | ✅ |
| 9 | 意思決定・レビュー統合・ポリシー変更追跡 | ✅ |
| 10 | DoD機械判定可能形式 | ✅ |
| 11 | A操作承認要求 | ✅ |
| 12 | 入力→決定→成果のTraceLink追跡 | ✅ |

## 関連ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| `docs/バイブコーディングPDCAシステム_要件定義書_v6.md` | 全27章の要件定義 |
| `docs/バイブコーディングPDCA_実装手順書_v3.md` | M0〜M4の実装手順 |
| `docs/adr/` | ADR-001〜008（設計判断記録） |
| `docs/ops/` | Runbook, Incident Playbook, Checklist |

## ライセンス

MIT
