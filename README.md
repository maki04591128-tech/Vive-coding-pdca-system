# vibe-pdca-llm-gateway

バイブコーディングPDCA自動開発システムのドキュメントリポジトリです。
要件定義書・実装手順書・ADR・運用ドキュメント等の全ドキュメントを含みます。

## ドキュメント一覧（全24件）

### コアドキュメント
- `docs/バイブコーディングPDCAシステム_要件定義書_v6.md` — VCS-REQ-001（全27章）
- `docs/バイブコーディングPDCA_実装手順書_v3.md` — VCS-IMPL-001（全14章、22件のギャップ反映済み）

### ADR（docs/adr/）
ADR-001〜008：モデル選定、プロジェクト種別、脆弱性スキャン、RAG検索、GitHub App権限、マルチプロジェクト隔離、サンドボックス設計、クラウド/ローカルLLM切替

### 運用ドキュメント（docs/ops/）
Runbook、Incident Playbook、Approval Checklist、Release Checklist、Suppress List運用ルール、フォールバック運用ガイド

### 設計・仕様
システムアーキテクチャ図、ロール権限マトリクス、プロンプトテンプレート仕様、オンボーディングガイド、必要なドキュメント一覧、ドキュメント精査レポート

### テンプレート（docs/templates/）
フィードバックログ テンプレ、統括レビュー要約 テンプレ

## 概要

本モジュールは ADR-001（マルチLLMモデル選定）および要件定義書 §4.2 / §13.2 に基づき、以下の機能を実装します。

**手動切替**: 設定ファイル (`config/default.yml`) または実行時APIで、クラウドLLM ↔ ローカルLLMを切り替えられます。

**自動フォールバック**: クラウドLLMの接続障害・API障害を検知すると、サーキットブレーカーパターンにより自動でローカルLLMへ切り替わります。障害復旧後は自動的にクラウドLLMへ復帰します。

**役割別マルチモデル**: ADR-001 に従い、PM / 書記 / プログラマ / デザイナ / ユーザ / DO の各役割に最適なLLMモデルを割り当てます。

## 使用するローカルLLM

本システムでは、クラウドLLM障害時の自動フォールバック先および手動切替先として、以下のローカルLLMを使用します。

| プロバイダ名 | モデル | パラメータ数 | 用途 | 対応役割 |
|-------------|--------|------------|------|---------|
| ollama-llama3.3 | **llama3.3:70b** | 70B | 汎用フォールバック（メイン） | PM, 書記, プログラマ, デザイナ, ユーザ, DO |
| ollama-qwen2.5 | **qwen2.5:32b** | 32B | 軽量応急用 | PM, 書記, デザイナ, ユーザ |

- **実行基盤**: [Ollama](https://ollama.com/)（OpenAI 互換 API: `http://localhost:11434/v1`）
- **選定理由**: llama3.3:70b は全役割をカバーできる汎用性と高い日本語能力を持つ。qwen2.5:32b は軽量で応急対応に適するが、コード生成精度の制約からプログラマ・DO担当には割り当てない（ADR-001 / ADR-008 参照）
- **コスト**: ローカル実行のため API 利用料 $0（ハードウェアコストは別途）
- **モデル差し替え**: 環境変数 `VIBE_PDCA_LOCAL_LLM_MODEL` で一括変更可能（[詳細](#ローカルllmのモデル差し替え)）

## アーキテクチャ

```
┌──────────────┐     ┌──────────────────────────────────────────┐
│  PDCA        │     │            LLM ゲートウェイ               │
│  オーケスト  │────→│                                          │
│  レータ      │     │  ┌─────────┐  ┌──────────────────────┐  │
│              │     │  │ コスト   │  │  役割→プロバイダ     │  │
│              │     │  │ 追跡     │  │  マッピング          │  │
│              │     │  └─────────┘  └──────────────────────┘  │
│              │     │                                          │
│              │     │  ┌──────────────────────────────────┐   │
│              │     │  │    サーキットブレーカー            │   │
│              │     │  │  CLOSED ←→ OPEN ←→ HALF_OPEN    │   │
│              │     │  └──────────────────────────────────┘   │
│              │     │          │                │              │
│              │     │    ┌─────┴──────┐  ┌─────┴──────┐      │
│              │     │    │ クラウドLLM │  │ ローカルLLM │      │
│              │     │    │ (優先)      │  │ (手動切替/  │      │
│              │     │    │            │  │  フォール   │      │
│              │     │    │            │  │  バック)    │      │
│              │     │    └────────────┘  └────────────┘      │
│              │     │          │                │              │
│              │     │  ┌───────┴────────────────┴──────┐      │
│              │     │  │      ヘルスチェッカー          │      │
│              │     │  │  (定期的な死活監視)            │      │
│              │     │  └───────────────────────────────┘      │
│              │     └──────────────────────────────────────────┘
└──────────────┘
         ↕                      ↕                    ↕
   ┌──────────┐         ┌────────────┐       ┌──────────────┐
   │ GitHub   │         │ OpenAI     │       │ Ollama       │
   │ API      │         │ Anthropic  │       │ llama.cpp    │
   │          │         │ Google     │       │ vLLM         │
   └──────────┘         └────────────┘       └──────────────┘
```

## セットアップ

### 1. インストール

```bash
pip install -e ".[dev]"
```

### 2. 環境変数

`.env.example` を `.env` にコピーして API キーを設定してください。

```bash
cp .env.example .env
# .env を編集して各プロバイダの API キーを設定
```

### 3. ローカルLLM（Ollama）のセットアップ

自動フォールバック先・手動切替先として Ollama を推奨します。

```bash
# Ollama インストール
curl -fsSL https://ollama.com/install.sh | sh

# デフォルトモデルのダウンロード
ollama pull llama3.3:70b
ollama pull qwen2.5:32b

# 高性能モデルへの差し替え（例）
ollama pull deepseek-r1:70b   # コード生成に強い
ollama pull codestral:22b     # 軽量コード特化
ollama pull qwen3:72b         # 日本語・推論に強い
```

### 4. 動作確認

```bash
pytest tests/ -v
```

## 設定

### 設定ファイル階層（§17.5 準拠）

```
config/default.yml              ← グローバルデフォルト
config/environments/dev.yml     ← 開発環境（ローカル優先）
config/environments/prod.yml    ← 本番環境（クラウド優先）
.vibe-pdca/config.yml           ← プロジェクト固有設定
```

下位の設定ファイルが上位を上書きします。ただしポリシーの「緩和」は人間承認が必要です（§17.5）。

### 主要な設定項目

| 項目 | 説明 | デフォルト | 環境変数オーバーライド |
|------|------|-----------|----------------------|
| `llm.preferred_mode` | 優先モード (`cloud` / `local`) | `cloud` | `VIBE_PDCA_LLM_MODE` |
| `llm.auto_fallback` | 自動フォールバック有効化 | `true` | `VIBE_PDCA_LLM_AUTO_FALLBACK` |
| `llm.local_providers[].model` | ローカルLLMモデル名 | `llama3.3:70b` | `VIBE_PDCA_LOCAL_LLM_MODEL` |
| `llm.local_providers[].base_url` | ローカルLLMサーバーURL | `http://localhost:11434/v1` | `VIBE_PDCA_LOCAL_LLM_BASE_URL` |
| `llm.circuit_breaker.failure_threshold` | OPEN遷移の連続失敗回数 | `3` | — |
| `llm.circuit_breaker.recovery_timeout` | OPEN→HALF_OPEN待機秒数 | `60.0` | — |
| `llm.cost.daily_limit_usd` | 日次コスト上限 (USD) | `30.0` | — |

> **優先順位**: 環境変数 > プロジェクト固有設定 > 環境別設定 > グローバルデフォルト

## 使い方

### 基本的な使用例

```python
from vibe_pdca.config import load_config, build_gateway_from_config
from vibe_pdca.llm.models import LLMRequest, ProviderType, Role

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
print(f"Provider: {response.provider_type.value}")
print(f"Fallback: {response.fallback_used}")
```

### 手動モード切替

#### 環境変数で切替（最も簡単）

```bash
# ローカルLLMモードで起動（設定ファイルの変更不要）
export VIBE_PDCA_LLM_MODE=local

# 自動フォールバックを無効化（ローカルのみで運用）
export VIBE_PDCA_LLM_AUTO_FALLBACK=false
```

#### 設定ファイルで切替

`config/default.yml` の `llm.preferred_mode` を `"local"` に変更するか、
`config/environments/dev.yml` のように環境別設定で上書きします。

#### Python API で実行時に切替

```python
# ローカルLLMモードへ切替
gateway.set_mode(ProviderType.LOCAL, reason="コスト削減のためローカルへ切替")

# クラウドLLMモードへ復帰
gateway.set_mode(ProviderType.CLOUD, reason="品質優先でクラウドへ復帰")
```

### CLI からのモード切替

```bash
# ローカルモードへ切替
python -m vibe_pdca.cli mode set \
  --project-id <PROJECT_ID> \
  --llm-mode local \
  --reason "オフライン作業のためローカルへ切替"
```

### ローカルLLMのモデル差し替え

環境変数でローカルLLMのモデルを差し替えできます（YAML 設定の編集不要）。

```bash
# 高性能モデルへ差し替え（Ollama でモデルを pull 済みであること）
export VIBE_PDCA_LOCAL_LLM_MODEL=deepseek-r1:70b

# vLLM / llama.cpp / LM Studio 等の別サーバーを使う場合
export VIBE_PDCA_LOCAL_LLM_BASE_URL=http://localhost:8000/v1
```

推奨モデル例：

| モデル | サイズ | 特徴 |
|--------|--------|------|
| `llama3.3:70b` | 70B | デフォルト。汎用性が高い |
| `deepseek-r1:70b` | 70B | コード生成・推論に優れる |
| `qwen3:72b` | 72B | 日本語・推論に強い |
| `codestral:22b` | 22B | 軽量・コード特化 |
| `gemma3:27b` | 27B | 軽量・高品質 |

### ステータス確認

```python
status = gateway.get_status()
# {
#   "preferred_mode": "cloud",
#   "auto_fallback_enabled": true,
#   "cloud_providers": {
#     "openai-gpt5.1": {"circuit_state": "closed", ...},
#     ...
#   },
#   "local_providers": {
#     "ollama-llama3.3": {"model": "llama3.3:70b", "base_url": "http://localhost:11434/v1"},
#     "ollama-qwen2.5": {"model": "qwen2.5:32b", "base_url": "http://localhost:11434/v1"},
#   },
#   "cost": {"daily_cost_usd": 1.23, ...}
# }
```

## 自動フォールバックの仕組み

### サーキットブレーカー状態遷移

```
[CLOSED 正常]
  │  クラウドLLMへリクエスト送信
  │
  ├──(連続失敗 >= failure_threshold)──→ [OPEN 遮断]
  │                                       │  ローカルLLMへ自動フォールバック
  │                                       │
  │                                       ├──(recovery_timeout 経過)──→ [HALF_OPEN 試行]
  │                                       │                              │  クラウドLLMへ試行
  │                                       │                              │
  │                                       │                   成功 ←─────┤
  │                                       │                              │
  ←────────(success_threshold 回成功)──────┘                   失敗 ──→ [OPEN へ戻る]
```

### 縮退モードとの連動（§13.2）

```
[正常]        ──(クラウドLLM 1障害)──→  [軽度縮退: フォールバック稼働]
[軽度縮退]    ──(クラウドLLM 3+障害)──→ [重度縮退: DOフェーズ停止]
[重度縮退]    ──(GitHub障害)──→         [全停止]
[全停止]      ──(手動再開)──→           [正常]
```

## ディレクトリ構造

```
vibe-pdca-llm-gateway/
├── config/
│   ├── default.yml                  # グローバルデフォルト設定
│   └── environments/
│       ├── dev.yml                  # 開発環境設定
│       └── prod.yml                 # 本番環境設定
├── docs/
│   ├── ADR-008_クラウドローカルLLM切替設計.md
│   └── フォールバック運用ガイド.md
├── src/
│   └── vibe_pdca/
│       ├── __init__.py
│       ├── config/
│       │   ├── __init__.py
│       │   └── loader.py            # 設定階層マージ・バリデーション
│       └── llm/
│           ├── __init__.py
│           ├── models.py            # データモデル定義
│           ├── providers.py         # クラウド/ローカルプロバイダ実装
│           ├── gateway.py           # 統一ゲートウェイ本体
│           ├── circuit_breaker.py   # サーキットブレーカー
│           └── health.py            # ヘルスチェッカー
├── tests/
│   ├── test_circuit_breaker.py
│   ├── test_gateway.py
│   └── test_config.py
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

## 関連ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| ADR-001 | マルチLLMモデル選定・フォールバック順 |
| ADR-008 | クラウド/ローカルLLM切替設計（本機能） |
| 要件定義書 §4.2 | LLMゲートウェイの統一インターフェース |
| 要件定義書 §13.2 | 信頼性・SLO・縮退モード |
| Runbook §8 | モード切替の運用手順 |

## ライセンス

MIT
