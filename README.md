# バイブコーディングPDCA自動開発システム

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)
[![CI](https://github.com/maki04591128-tech/Vive-coding-pdca-system/actions/workflows/ci.yml/badge.svg)](https://github.com/maki04591128-tech/Vive-coding-pdca-system/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 概要

バイブコーディングPDCA自動開発システムは、**目標（最終到達点）を入力するだけで PLAN→DO→CHECK→ACT の自動PDCAサイクルを回し、ソフトウェアを自律的に開発**するシステムです。

5ペルソナ（PM/書記/プログラマ/デザイナ/ユーザ）による自動レビュー、ガバナンス承認ワークフロー、監査ログによる完全追跡、コスト管理、セキュリティ強化を備えています。

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
| RBAC | `governance/` | Owner/Maintainer/Reviewer/Auditor の4ロール（詳細は[ロール権限マトリクス](docs/設計書/ロール権限マトリクス.md)参照） |
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

> 🔰 **はじめての方へ**  
> ターミナル（黒い画面）の開き方や基本操作がわからない場合は、まず [手順書 — パソコン初心者の方へ](docs/手順書/00_はじめに.md#-パソコン初心者の方へ--基礎知識ガイド) をお読みください。  
> 詳しいステップバイステップの手順は [03 ローカルセットアップ手順書](docs/手順書/03_ローカルセットアップ手順書.md) にまとめています。

### 1. インストール

> **前提**: Python 3.12 以上 と Git がインストールされている必要があります。  
> - Python のインストール → [python.org/downloads](https://www.python.org/downloads/)  
> - Git のインストール → [git-scm.com](https://git-scm.com/)  
> - `pip` は Python に同梱されるパッケージ管理ツールです。以下のコマンドをターミナルにコピー＆貼り付けして実行してください。

```bash
# 基本（バックエンドのみ）
pip install -e ".[dev]"

# GUI 付き（デスクトップ / モバイルアプリ対応）
pip install -e ".[dev,gui]"

# Google Gemini LLM を使用する場合
pip install -e ".[dev,google]"
```

### 2. 環境変数

`.env.example` を `.env` にコピーして API キーを設定してください。

> 💡 **`.env` ファイルとは？** アプリケーションの秘密の設定値（APIキーなど）を保管するファイルです。`.gitignore` で Git の管理対象から除外されているため、各自が手元で作成します。

```bash
cp .env.example .env
# .env をテキストエディタで開いて、各プロバイダの API キーを設定
```

### 3. ローカルLLM（Ollama）のセットアップ

> 💡 **Ollama とは？** パソコン上で AI モデルを動かすためのツールです。クラウド API を使わずに、ローカル環境だけで LLM を利用できます。

```bash
# Ollama インストール（Linux / macOS）
curl -fsSL https://ollama.com/install.sh | sh
# Windows の場合は https://ollama.com/download からインストーラーをダウンロード

# 役割別デフォルトモデルのダウンロード（各数十GB — ディスク容量に注意）
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
│   ├── 設計書/                     # 要件定義・設計書・仕様書
│   │   └── バイブコーディングPDCAシステム_要件定義書.md
│   ├── 手順書/                     # セットアップ・ビルド・実装手順（番号順に実施）
│   │   ├── 00_はじめに.md          # 手順書ガイド（どこから始めるか）
│   │   ├── 01_ハードウェア構築手順書.md
│   │   ├── 02_システムセットアップ手順書.md
│   │   ├── 03_ローカルセットアップ手順書.md
│   │   ├── 04_運用保守手順書.md
│   │   ├── 05_バイブコーディングPDCA_実装手順書.md
│   │   └── 06_インストーラービルド手順書.md
│   ├── 説明書/                     # 説明・解説ドキュメント
│   ├── 運用/                       # 運用 Runbook, Playbook 等
│   ├── adr/                        # ADR-001〜008
│   ├── 提案書/                     # 機能提案書
│   ├── 管理/                       # 変更履歴・管理文書
│   └── テンプレート/               # テンプレート
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
├── tests/                          # ユニット・統合テスト
│   ├── test_acceptance.py          # 受入基準12項目
│   ├── test_security_redteam.py    # セキュリティ検証5パターン
│   └── ...                         # 各モジュールのユニットテスト
├── .env.example
├── CHANGELOG.md                    # 変更履歴（リダイレクト）
├── CONTRIBUTING.md                 # コントリビューションガイド（リダイレクト）
├── LICENSE                         # MIT License
├── Makefile                        # 開発コマンド集（make help で一覧表示）
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

## 📚 ドキュメント一覧

| カテゴリ | 内容 | パス |
|---------|------|------|
| **手順書** | 環境構築・運用の具体的な手順（[はじめに](docs/手順書/00_はじめに.md)から開始） | `docs/手順書/` |
| **説明書** | 用語解説・システムの仕組みの解説 | `docs/説明書/` |
| **設計書** | 要件定義・アーキテクチャ・仕様書 | `docs/設計書/` |
| **ADR** | アーキテクチャ決定記録（ADR-001〜008） | `docs/adr/` |
| **運用** | インシデント対応・チェックリスト・フォールバック手順 | `docs/運用/` |
| **提案書** | 機能提案（提案1〜30、全件実装済み） | `docs/提案書/` |
| **テンプレート** | フィードバックログ・統括レビュー要約のテンプレート | `docs/テンプレート/` |
| **管理** | 変更履歴・ドキュメント一覧・残タスク・セキュリティポリシー | `docs/管理/` |

> 📌 全ドキュメントの索引は [必要なドキュメント一覧](docs/管理/必要なドキュメント一覧.md) を参照してください。

### 🔗 クイックリンク

| ドキュメント | 説明 |
|-------------|------|
| [FAQ（よくある質問）](docs/説明書/FAQ.md) | セットアップ・運用・トラブルに関するQ&A |
| [トラブルシューティングガイド](docs/運用/トラブルシューティングガイド.md) | 問題発生時の対処手順 |
| [APIリファレンス](docs/設計書/APIリファレンス.md) | REST API全8エンドポイントの仕様 |

## 関連ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| `docs/設計書/バイブコーディングPDCAシステム_要件定義書.md` | 全27章の要件定義 |
| `docs/手順書/00_はじめに.md` | 手順書ガイド（どこから始めるか） |
| `docs/手順書/05_バイブコーディングPDCA_実装手順書.md` | M0〜M4の実装手順 |
| `docs/adr/` | ADR-001〜008（設計判断記録） |
| `docs/運用/` | Runbook, インシデント対応手順書, チェックリスト |
| `docs/説明書/FAQ.md` | よくある質問と回答 |
| `docs/運用/トラブルシューティングガイド.md` | 問題発生時の対処ガイド |
| `docs/設計書/APIリファレンス.md` | REST API仕様書 |

## 開発コマンド（Makefile）

```bash
make install      # 開発用インストール
make lint         # Lintチェック
make type-check   # 型チェック
make test         # テスト実行（GUI除外）
make test-cov     # カバレッジ付きテスト
make check        # Lint + 型チェック + テスト 一括
make help         # 全コマンド一覧
```

## ライセンス

MIT
