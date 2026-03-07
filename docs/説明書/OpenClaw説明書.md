# OpenClaw 説明書

**文書番号**：VCS-INFRA-003  
**版**：1.1  
**作成日**：2026-03-06  
**最終更新**：2026-03-06  
**関連文書**：[三層独立運用体制 アーキテクチャ設計書](../設計書/三層独立運用体制_アーキテクチャ設計書.md)、[AI推論サーバー説明書](AI推論サーバー説明書.md)、[02 システムセットアップ手順書](../手順書/02_システムセットアップ手順書.md)

---

## 📖 この文書について

> この文書は、**OpenClaw プラットフォーム自体の説明** と、本システムにおける **OpenClaw（ハードウェア監視層）の運用** の全体像をまとめた説明書です。  
> OpenClaw とはどのようなオープンソースプロジェクトなのか、本システムではどのように活用するのか、そして他の環境への流用可能性までを一冊にまとめています。  
> たとえるなら、「ビル管理会社の会社案内 + 業務マニュアル」のようなものです。まず管理会社（OpenClaw）がどんな会社なのかを紹介し、その後テナント（PDCA システム）のビルでどのように管理業務を行うかを解説します。

---

### 🔰 この文書で使われる主要な用語

| 用語 | かんたんな説明 |
|------|-------------|
| **OpenClaw** | オープンソースの自律型 AI エージェントプラットフォーム。本システムではハードウェア監視層として活用 |
| **スキル（Skill）** | OpenClaw のプラグイン機構。タスク自動化・ハードウェア制御・API 連携などの機能を追加できる |
| **Gateway** | OpenClaw のコア部分。LLM・スキル・チャットプラットフォームを橋渡しする中継役 |
| **三層独立運用体制** | OpenClaw（HW監視）・PDCAシステム（SW/AI）・人間（ガバナンス）の 3 つが互いに独立して動く運用体制 |
| **PDCA システム** | 第2層。PLAN→DO→CHECK→ACT を自律的に回すソフトウェア開発エンジン |
| **Discord Webhook** | Discord チャンネルに外部からメッセージを送るための URL。OpenClaw はこれを使って通知を行う |
| **nvidia-smi** | NVIDIA GPU の温度・VRAM 使用率・稼働率などを取得する公式コマンド |
| **vLLM** | GPU 上で大規模言語モデルを高速推論するサーバーソフトウェア |
| **cron** | Linux の定期実行スケジューラ。5 分ごと・1 時間ごとなどの間隔でスクリプトを自動実行できる |
| **Circuit Breaker** | PDCA システム側のフォールバック機構。LLM 呼び出しが連続失敗すると自動でクラウド LLM に切り替える |
| **UPS** | 無停電電源装置。停電時にサーバーを安全にシャットダウンするための予備電源 |
| **S.M.A.R.T.** | ストレージデバイスの健全性を自己診断する技術。故障の予兆を検出できる |

---

## 1. OpenClaw とは何か

### 1.1 OpenClaw プラットフォームの概要

**OpenClaw** は、オープンソースの **自律型 AI エージェントプラットフォーム** です。  
MIT ライセンスで公開されており、ローカル環境で動作するプライバシーファーストの設計が特徴です。

- **公式サイト**: [https://docs.openclaw.ai/](https://docs.openclaw.ai/)
- **GitHub リポジトリ**: [https://github.com/openclaw/openclaw](https://github.com/openclaw/openclaw)
- **ライセンス**: MIT

> 💡 **かんたんに言うと**: OpenClaw は「自分のパソコンやサーバーで動く、何でもできる AI アシスタント基盤」です。チャットアプリとつなげて指示を出したり、決まった時間に自動でタスクを実行させたり、ハードウェアの状態を監視させたりできます。

### 1.2 OpenClaw の主な特徴

| 特徴 | 説明 |
|------|------|
| **🔒 プライバシーファースト** | すべてのデータがローカルに保持される。API キーも自分で管理し、会話履歴はクラウドに送信されない |
| **🔌 マルチチャンネル対応** | Discord・Slack・Telegram・WhatsApp・iMessage など **50 以上** のチャットプラットフォームと連携可能。1 つのエージェントから複数チャンネルに同時通知できる |
| **🧩 スキルエンジン** | 「スキル」と呼ばれるプラグインで機能を拡張できる。コミュニティ製スキルが多数公開されており、独自スキルも Markdown + YAML で簡単に作成可能 |
| **🤖 マルチ LLM 対応** | Anthropic（Claude）、OpenAI（GPT）、Google（Gemini）、xAI（Grok）、Ollama・vLLM 経由のローカルモデルなど、主要な LLM プロバイダーをすべてサポート |
| **⏰ スケジュール実行** | cron 式で定期タスクを設定可能。サーバー監視・バックアップ・レポート送信などを自動化できる |
| **🖥️ ハードウェア連携** | Raspberry Pi・Arduino・LattePanda などの IoT デバイスと連携し、センサー読み取り・GPIO 制御・ハードウェア監視が可能 |
| **🛡️ セキュリティ** | VirusTotal によるスキルスキャン、コード安全性チェッカー、サンドボックス実行などのセキュリティ機構を内蔵 |
| **🌐 クロスプラットフォーム** | macOS・Linux・Windows・Raspberry Pi OS で動作。npm / curl スクリプト / ソースビルド（Go / Node.js）でインストール可能 |

### 1.3 OpenClaw のアーキテクチャ

OpenClaw は **Gateway（ゲートウェイ）アーキテクチャ** を採用しています。

```
┌─────────────────────────────────────────────────────┐
│                  OpenClaw Agent                      │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ LLM      │  │ Skills   │  │ Persistent       │  │
│  │ Provider  │  │ Engine   │  │ Memory           │  │
│  │(Claude等) │  │(プラグイン)│  │(長期記憶)        │  │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│       └──────────┬──┘                  │            │
│            ┌─────┴─────┐               │            │
│            │  Gateway   ├──────────────┘            │
│            └─────┬─────┘                            │
│    ┌─────────────┼─────────────┐                    │
│    ▼             ▼             ▼                    │
│ Discord      Telegram      Slack   ... (50+)       │
└─────────────────────────────────────────────────────┘
```

- **LLM Provider**: AI の「頭脳」。クラウド API またはローカルモデルを選択
- **Skills Engine**: タスクを実行する「手足」。ファイル操作・API 呼び出し・ハードウェア制御など
- **Persistent Memory**: ユーザーの好みや過去の会話を記憶する「長期記憶」
- **Gateway**: 各チャットプラットフォームとの橋渡し役

### 1.4 本システムでの位置づけ

本システム（バイブコーディング PDCA システム）では、OpenClaw のスキルエンジンとスケジュール実行機能を活用して、**第1層（ハードウェア監視層）** を構築しています。

```
┌─────────────────────────────────────────────────────┐
│ 第3層：人間（ガバナンス層）                          │
│   Owner / Maintainer / Reviewer / Auditor           │
│   Discord・Web UI を通じて最終判断                   │
├─────────────────────────────────────────────────────┤
│ 第2層：PDCA システム（ソフトウェア / AI 層）         │
│   PLAN → DO → CHECK → ACT 自律サイクル              │
│   5 ペルソナ自動レビュー / CI 連携 / 監査ログ        │
├─────────────────────────────────────────────────────┤
│ 第1層：OpenClaw（ハードウェア監視層） ← ここ        │
│   GPU / CPU / メモリ / ディスク / 電源 / ネットワーク │
│   24 時間 365 日の自動監視 + Discord 通知             │
└─────────────────────────────────────────────────────┘
```

OpenClaw が持つ多数の機能のうち、本システムでは以下を重点的に活用しています。

| OpenClaw の機能 | 本システムでの活用 |
|---------------|-----------------|
| **スケジュール実行（cron）** | GPU 温度・ディスク使用率・vLLM ヘルスチェックの定期監視 |
| **Discord チャンネル連携** | hw-critical / hw-warning / hw-info / hw-status への通知 |
| **シェルスクリプト実行** | `nvidia-smi`・`df`・`free` 等のハードウェア情報取得 |
| **セキュリティ分離** | `openclaw-monitor` 専用ユーザーによる権限制限 |
| **ローカル実行** | クラウド非依存。ネットワーク断でもサーバー上で動き続ける |

> ⚠️ **重要**: 本システムでは OpenClaw を**ハードウェア監視専用**として運用します。PDCA システム（第2層）は OpenClaw とは完全に独立しており、OpenClaw が PDCA のソースコード・API キー・設定ファイルにアクセスすることは**ありません**。

### 1.5 設計思想

本システムにおける OpenClaw 活用の設計は **3 つの原則** に基づいています。

| 原則 | 説明 |
|------|------|
| **Read-First（読み取り優先）** | ハードウェア情報は読み取り専用で収集する。変更操作は最小限かつ安全なものに限定する |
| **通知 → 人間承認 → 実行** | システム変更は Discord 通知後に人間が承認してから実行する。安全な自動修復（プロセス再起動など）のみ自動実行 + 事後通知する |
| **PDCA システムとの完全独立** | PDCA の API・ファイル・データベースには一切アクセスしない。Discord 通知だけが唯一の接点 |

### 1.6 ビル管理のたとえ

OpenClaw の役割をビル管理に例えると、以下のようになります。

| ビル管理の世界 | 本システムの世界 |
|--------------|----------------|
| ビル管理会社 | **OpenClaw**（ハードウェア監視層） |
| テナント企業の IT 部門 | **PDCA システム**（ソフトウェア / AI 層） |
| ビルオーナー / 審査委員会 | **人間**（ガバナンス層） |
| 電気・空調・防災設備の監視 | GPU 温度・メモリ・ディスク・電源の監視 |
| 漏電ブレーカーの自動遮断 | vLLM プロセスの自動再起動 |
| オーナーへの月次報告 | Discord への 1 時間ごとの定時レポート |

---

## 2. OpenClaw でできること

### 2.1 ハードウェア監視

OpenClaw は以下のハードウェアリソースを **24 時間 365 日** 自動監視します。

| 監視対象 | 取得情報 | 使用コマンド | 監視間隔 |
|---------|---------|------------|---------|
| **GPU** | 温度、VRAM 使用量、使用率、ECC エラー | `nvidia-smi` | 5 分 |
| **CPU** | 温度、コア使用率、負荷平均 | `sensors` / `uptime` | 30 分 |
| **メモリ** | 物理メモリ使用量、スワップ使用量 | `free -h` | 30 分 |
| **ディスク** | 使用率、I/O エラー、S.M.A.R.T. 情報 | `df -h` / `smartctl` | 15 分（容量） / 1 日（SMART） |
| **電源** | UPS 残量、入力電圧、異常有無 | `apcaccess` 等 | 30 分 |
| **ネットワーク** | NIC リンク状態、パケットエラー率 | `ip link show` | 30 分 |

### 2.2 プロセスヘルスチェック

| チェック対象 | 方法 | 間隔 |
|------------|------|------|
| **vLLM** | `curl -s http://localhost:8000/health` でポート応答確認 | 5 分 |
| **rootless Docker** | プロセス存在確認のみ | 30 分 |

> ⚠️ **注意**: ヘルスチェックは「ポートが応答するか」「プロセスが存在するか」の **外形監視** のみです。PDCA システム内部のロジックには踏み込みません。

### 2.3 安全な自動修復

OpenClaw が **人間の承認なしに** 自動実行できる操作は、以下の 3 つに限定されています。

| 操作 | トリガー | 実行内容 | 通知先 |
|------|---------|---------|--------|
| **GPU ファン制御** | GPU 温度 85℃ 以上 | ファン回転数を最大に設定 | hw-warning |
| **vLLM 再起動** | ヘルスチェック 3 回連続失敗 | `systemctl restart vllm` | hw-info（成功時） / hw-critical（3 回失敗時） |
| **古いログの自動アーカイブ** | ディスク使用率 90% 以上 | 7 日以上前の vLLM ログを `/backup/logs/` へ移動 | hw-info |

### 2.4 Discord 通知

OpenClaw はすべての検出結果を **Discord Webhook 経由** で通知します。通知は **一方向（OpenClaw → Discord）** であり、Discord からの指示を受け取ることはありません。

| チャンネル | 重大度 | 通知内容の例 | 対応期限 |
|-----------|--------|------------|---------|
| 🔴 **hw-critical** | 緊急 | GPU 95℃ 超、ECC エラー検出、UPS 残量 15% 以下、vLLM 再起動 3 回失敗 | 1 時間以内 |
| 🟡 **hw-warning** | 警告 | GPU 85–94℃、VRAM 95% 超、ディスク 80% 超、UPS 30% 以下 | 24 時間以内 |
| 🟢 **hw-info** | 情報 | vLLM 再起動成功、パッチ適用可能、温度正常化 | 対応不要 |
| 📊 **hw-status** | 定時レポート | 1 時間ごとの総合ヘルスレポート（GPU / CPU / メモリ / ディスク / 電源） | 対応不要（1 週間で自動削除） |

### 2.5 定時ヘルスレポート

1 時間ごとに **hw-status** チャンネルへ以下のようなレポートを送信します。

```
📊 【OpenClaw 定時ヘルスレポート】2026-03-06 14:00 JST

🖥️ サーバー基本情報
  稼働時間: 15日 3時間 42分
  負荷平均: 2.4 / 2.1 / 1.8（1分/5分/15分）

🎮 GPU状態
  GPU0 (A100 40GB): 72℃ / VRAM 35.2GB/40GB (88%) / 使用率 94%
  ECC Uncorrected Error: 0件 ✅

💾 ストレージ
  OS NVMe:   234GB / 2TB (12%) ✅
  データSSD: 3.2TB / 4TB (80%) ⚠️ 残り800GB
  S.M.A.R.T.: 正常 ✅

🔌 電源・ネットワーク
  UPS残量: 100% / 入力電圧: 200V ✅
  NIC eth0: 1Gbps リンクアップ ✅

🤖 プロセス確認
  vLLM (localhost:8000): 応答あり ✅
  rootless Docker: 稼働中 ✅

⚠️ 要注意事項
  - データSSDの使用率が80%に達しました。
    2週間以内に容量対策を推奨します。

次回レポート: 15:00 JST
```

---

## 3. 本システムでの運用方法

### 3.1 インストールと設置

OpenClaw は **PDCA システムの外側** に設置します。Docker コンテナの中ではなく、**ホスト OS 上に直接** 配置します。

```
ホスト OS（Ubuntu Server）
├── /opt/openclaw/                  ← OpenClaw 本体（シェルスクリプト群）
│   ├── gpu_monitor.sh              # GPU 温度監視スクリプト
│   ├── disk_monitor.sh             # ディスク使用率監視スクリプト
│   ├── health_report.sh            # 定時ヘルスレポート生成スクリプト
│   └── allowed_commands.yml        # コマンドホワイトリスト設定
│
├── Docker (rootless)
│   └── PDCA システムコンテナ        ← 第2層（OpenClaw はここにアクセスしない）
│
└── cron                            ← 定期実行スケジューラ
    ├── */5 * * * * gpu_monitor.sh
    ├── */15 * * * * disk_monitor.sh
    └── 0 * * * * health_report.sh
```

#### セットアップ手順の概要

```bash
# 1. 監視ディレクトリの作成
sudo mkdir -p /opt/openclaw

# 2. 監視スクリプトの配置
sudo cp config/openclaw/* /opt/openclaw/
sudo chmod +x /opt/openclaw/*.sh

# 3. 専用ユーザーの作成（セキュリティ分離）
sudo useradd -m -s /bin/bash openclaw-monitor
sudo usermod -aG video openclaw-monitor   # GPU アクセスのみ許可

# 4. cron ジョブの登録
sudo -u openclaw-monitor crontab -e
# → スケジュールを記述（後述）

# 5. ネットワーク分離ルールの設定
sudo iptables -A OUTPUT -m owner --uid-owner openclaw-monitor \
  -d 127.0.0.1 -p tcp --dport 8080 -j REJECT   # PDCA Web UI ブロック
```

> 📌 詳細な手順は [02 システムセットアップ手順書 Phase 8](../手順書/02_システムセットアップ手順書.md) を参照してください。

### 3.2 監視スケジュール

| タスク | 実行間隔 | cron 式 | スクリプト |
|--------|---------|---------|-----------|
| GPU 温度・VRAM チェック | 5 分ごと | `*/5 * * * *` | `gpu_monitor.sh` |
| vLLM ヘルスチェック | 5 分ごと | `*/5 * * * *` | `gpu_monitor.sh`（内蔵） |
| ディスク使用率チェック | 15 分ごと | `*/15 * * * *` | `disk_monitor.sh` |
| CPU・メモリチェック | 30 分ごと | `*/30 * * * *` | `health_report.sh`（内蔵） |
| 定時ヘルスレポート | 1 時間ごと | `0 * * * *` | `health_report.sh` |
| S.M.A.R.T. チェック | 毎日 9:00 | `0 9 * * *` | `smart_check.sh` |
| セキュリティパッチ確認 | 毎週日曜 3:00 | `0 3 * * 0` | `patch_check.sh` |

### 3.3 セキュリティ分離

OpenClaw は PDCA システムとの **完全分離** を実現するため、以下の制限が適用されます。

#### OpenClaw 専用ユーザーの権限

```yaml
# /opt/openclaw/allowed_commands.yml

allowed_commands:
  # ハードウェア情報取得（読み取り専用）
  - nvidia-smi
  - nvidia-smi --query-gpu=* --format=csv
  - sensors
  - df -h
  - free -h
  - uptime
  - ip link show
  - smartctl --all /dev/nvme*

  # ヘルスチェック（GET のみ）
  - curl -s http://localhost:8000/health

  # 安全な自動修復
  - systemctl restart vllm
  - find /var/log/vllm -name '*.log.*' -mtime +7 -exec mv {} /backup/logs/

denied_paths:
  - /home/vibe-pdca/**       # PDCA ユーザーのホーム
  - /etc/vibe-pdca/**        # PDCA 設定ファイル
  - /var/lib/docker/**       # Docker データ
  - /root/**                 # root ディレクトリ

denied_network:
  - localhost:8080           # PDCA Web UI
  - localhost:5432           # データベース（将来用）
```

#### アクセス制限の図

```
OpenClaw ユーザー（openclaw-monitor）
  ✅ → nvidia-smi（GPU 情報の読み取り）
  ✅ → sensors / df / free / uptime（OS リソース情報の読み取り）
  ✅ → curl localhost:8000/health（vLLM の外形監視）
  ✅ → systemctl restart vllm（vLLM の再起動のみ）
  ✅ → Discord Webhook（通知の送信のみ）
  ❌ → PDCA ソースコード・設定ファイル
  ❌ → LLM API キー・GitHub トークン
  ❌ → Docker コンテナ内部
  ❌ → PDCA Web UI（ポート 8080）
  ❌ → PDCA データベース・ログファイル
```

### 3.4 障害発生時のシナリオ

#### シナリオ 1: GPU 過熱

```
[OpenClaw] nvidia-smi で 90℃ 検出
    ↓
[OpenClaw] hw-critical チャンネルへ @Owner メンション付き通知
    ↓
[人間] 室温・エアフローを確認
    ↓
判断分岐：
  → 室温が高い場合：エアコンを強設定
  → ファン故障の場合：PDCA 停止 → ファン交換
  → 一時的な負荷の場合：OpenClaw が継続監視
    ↓
[PDCA システム] この問題を認識しない（独立動作のため）
```

#### シナリオ 2: vLLM プロセスクラッシュ

```
[OpenClaw] ヘルスチェックタイムアウト検出
    ↓
[OpenClaw] hw-critical チャンネルへ「vLLM プロセスクラッシュ」通知
    ↓
[OpenClaw] 自動実行：systemctl restart vllm
    ↓
[OpenClaw] 成功/失敗を hw-info へ報告

同時進行（独立して発生）：
[PDCA] LLM 呼び出し失敗 → Circuit Breaker OPEN 状態に遷移
    ↓
[PDCA] 自動フォールバック：クラウド LLM へ切替
    ↓
[PDCA] pdca-warning チャンネルへ警告通知

結果：2 つの独立システムが同じ障害に別々に対応
```

#### シナリオ 3: ディスク容量逼迫

```
[OpenClaw] df で 95% 使用を検出
    ↓
[OpenClaw] hw-warning チャンネルへ「3.8TB/4TB」通知
    ↓
[OpenClaw] 自動修復：古い vLLM ログをアーカイブ
    ↓
[OpenClaw] 「200GB 解放、現在 80%」を hw-info へ報告
    ↓
[人間] 2 週間以内のストレージ増設を計画
```

### 3.5 PDCA システムとの責任分担

| インシデント種別 | OpenClaw | PDCA システム | 人間 |
|----------------|:--------:|:-----------:|:----:|
| **GPU 過熱** | 検出・通知・ファン制御 | 認識しない | 物理的対応 |
| **GPU ECC エラー** | 検出・通知 | 認識しない | GPU 交換判断 |
| **vLLM クラッシュ** | 検出・再起動・通知 | フォールバック自動発動 | 状況確認 |
| **ディスク逼迫** | 検出・ログアーカイブ・通知 | 認識しない | 増設計画 |
| **UPS 残量低下** | 検出・通知 | 認識しない | 電源対応 |
| **NIC ダウン** | 検出・通知 | API 失敗→停止 | ネットワーク復旧 |
| **LLM API 障害** | 認識しない | Circuit Breaker 発動 | 回復確認 |
| **CI 連続失敗** | 認識しない | 自動停止 | 再開承認 |
| **プロンプトインジェクション** | 認識しない | 即座停止 | 4/4 承認で再開 |

### 3.6 メリットとトレードオフ

#### メリット

| # | メリット | 説明 |
|---|---------|------|
| 1 | **障害の波及防止** | HW 障害で SW がクラッシュしても監視は継続。SW 障害で HW 監視が止まることもない |
| 2 | **セキュリティ強化** | OpenClaw は API キー・トークンに一切アクセスできない設計 |
| 3 | **監査の明確性** | HW ログと SW ログが完全に分離され、責任追跡が容易 |
| 4 | **段階的対応** | HW は OpenClaw、SW は PDCA、重要判断は人間——と段階的に対応できる |

#### トレードオフと緩和策

| # | トレードオフ | 緩和策 |
|---|------------|--------|
| 1 | **情報の断絶**: PDCA が GPU 温度を知らない（物理的不安定性を隠蔽する可能性） | 人間が hw-status と pdca-status の両チャンネルを定期確認する |
| 2 | **二重対応**: vLLM クラッシュ時に OpenClaw と PDCA が両方反応する | Circuit Breaker の HALF_OPEN 状態で graceful に合流する |
| 3 | **人間の監視負荷**: 2 系統の Discord チャンネルを確認する必要がある | hw-critical は @Owner メンション付き、hw-status は定時レポートにまとめて負荷軽減 |

---

## 4. 設定ファイルリファレンス

### 4.1 リポジトリ内の設定ファイル

本リポジトリの `config/openclaw/` ディレクトリに、運用環境へコピーするためのテンプレートファイルを配置しています。

```
config/openclaw/
├── gpu_monitor.sh           # GPU 温度監視スクリプト
├── disk_monitor.sh          # ディスク使用率監視スクリプト
├── health_report.sh         # 定時ヘルスレポート生成スクリプト
└── allowed_commands.yml     # コマンドホワイトリスト設定
```

### 4.2 環境変数

OpenClaw のスクリプトは以下の環境変数を使用します。

| 環境変数名 | 説明 | 設定例 |
|-----------|------|--------|
| `OPENCLAW_DISCORD_WEBHOOK` | Discord hw-warning / hw-info 用 Webhook URL | `https://discord.com/api/webhooks/xxxxx/xxxxx` |
| `OPENCLAW_DISCORD_WEBHOOK_CRITICAL` | Discord hw-critical 用 Webhook URL | `https://discord.com/api/webhooks/xxxxx/xxxxx` |
| `OPENCLAW_DISCORD_WEBHOOK_STATUS` | Discord hw-status 用 Webhook URL | `https://discord.com/api/webhooks/xxxxx/xxxxx` |
| `OPENCLAW_GPU_TEMP_WARN` | GPU 温度警告閾値（℃） | `85`（デフォルト: 85） |
| `OPENCLAW_GPU_TEMP_CRITICAL` | GPU 温度緊急閾値（℃） | `95`（デフォルト: 95） |
| `OPENCLAW_DISK_WARN` | ディスク使用率警告閾値（%） | `80`（デフォルト: 80） |
| `OPENCLAW_DISK_CRITICAL` | ディスク使用率緊急閾値（%） | `90`（デフォルト: 90） |

### 4.3 cron 設定テンプレート

```bash
# OpenClaw 監視スケジュール
# ※ OPENCLAW_DISCORD_WEBHOOK 等は /opt/openclaw/.env から読み込む

# GPU 温度 + vLLM ヘルスチェック（5 分ごと）
*/5 * * * * /opt/openclaw/gpu_monitor.sh >> /var/log/openclaw/gpu.log 2>&1

# ディスク使用率チェック（15 分ごと）
*/15 * * * * /opt/openclaw/disk_monitor.sh >> /var/log/openclaw/disk.log 2>&1

# 定時ヘルスレポート（1 時間ごと）
0 * * * * /opt/openclaw/health_report.sh >> /var/log/openclaw/report.log 2>&1
```

---

## 5. 他の環境への流用

OpenClaw はもともと汎用的な AI エージェントプラットフォームであるため、本システムで構築した監視のしくみは他の環境にも容易に応用できます。  
以下に、本システムの監視構成を流用する場合のいくつかの活用例を示します。

> 💡 **ポイント**: OpenClaw 自体がマルチプラットフォーム対応（Linux / macOS / Windows / Raspberry Pi OS）であるため、監視対象サーバーの OS を問わず導入できます。

### 5.1 汎用 GPU サーバー監視

**対象**: 機械学習・ディープラーニング用の GPU サーバー

OpenClaw の GPU 温度監視・VRAM 監視・vLLM ヘルスチェックのしくみは、そのまま以下の環境に流用できます。

- **機械学習の学習ジョブ実行サーバー**: 長時間のトレーニング中に GPU 過熱を検出
- **推論 API サーバー**: vLLM 以外（TGI、Triton Inference Server 等）のヘルスチェック
- **マルチ GPU クラスタ**: 複数ノードの GPU 状態を一元的に Discord 通知

```bash
# 例: Triton Inference Server 向けにヘルスチェック先を変更
# gpu_monitor.sh 内の vLLM ヘルスチェック URL を差し替えるだけ
HEALTH_URL="http://localhost:8000/v2/health/ready"   # Triton 向け
```

### 5.2 オンプレミス CI/CD サーバー監視

**対象**: Jenkins・GitLab Runner・GitHub Actions Self-Hosted Runner

CI/CD サーバーは長時間のビルドで CPU 温度が上昇し、ディスクも圧迫されやすい環境です。OpenClaw の監視スクリプトを以下のように活用できます。

| 流用コンポーネント | CI/CD サーバーでの活用 |
|-------------------|---------------------|
| `gpu_monitor.sh` | GPU ビルド（CUDA コンパイル等）時の温度監視 |
| `disk_monitor.sh` | ビルドキャッシュ・アーティファクトによるディスク逼迫の検出 |
| `health_report.sh` | CI サーバーの定期ヘルスレポート（稼働率・ジョブ数・リソース状況） |

### 5.3 ホームラボ / 小規模サーバー運用

**対象**: 個人やチームで運用する小規模な Linux サーバー

OpenClaw は公式に Raspberry Pi をサポートしており、小規模環境との相性が非常に良いです。本システムの監視スクリプトをそのまま活用して、以下のような環境を監視できます。

- **NAS / ファイルサーバー**: ディスク残量・SMART 監視
- **Minecraft / ゲームサーバー**: CPU 負荷・メモリ監視
- **自宅 AI サーバー**: GPU 温度・VRAM 監視
- **Raspberry Pi クラスタ**: CPU 温度・SD カード寿命監視

> 💡 Raspberry Pi での OpenClaw 導入は公式ガイド（[Raspberry Pi - OpenClaw](https://docs.openclaw.ai/platforms/raspberry-pi)）を参照してください。

### 5.4 クラウド VM 監視の補助

**対象**: AWS EC2 / GCP Compute Engine / Azure VM

クラウドにはCloudWatch / Cloud Monitoring などの監視サービスがありますが、OpenClaw のスクリプトは**追加コストなし**でクラウド VM 内から Discord に通知できます。

| クラウド監視 | OpenClaw の補完 |
|------------|---------------|
| CloudWatch アラーム（メトリクス蓄積型） | Discord へのリアルタイム通知（Webhook 即時送信） |
| 有料の詳細メトリクス | GPU 温度など無料で取得可能なメトリクスの活用 |
| ダッシュボード（ブラウザアクセス必要） | Discord アプリで外出先からも確認可能 |

### 5.5 流用時のカスタマイズポイント

OpenClaw を別の環境に流用する場合、変更すべき箇所を以下にまとめます。

| カスタマイズ項目 | 変更ファイル | 変更内容 |
|---------------|------------|---------|
| **監視対象のプロセス** | `gpu_monitor.sh` | ヘルスチェック URL を対象サービスに変更 |
| **閾値の調整** | 各 `.sh` + 環境変数 | 温度・ディスク使用率の閾値を環境に合わせて変更 |
| **通知先** | 環境変数 | Discord Webhook URL を別チャンネルに変更。Slack Webhook への差替えも容易 |
| **監視間隔** | cron 設定 | 負荷に応じて間隔を調整（本番 5 分 / 開発環境 30 分など） |
| **GPU 非搭載環境** | `gpu_monitor.sh` | GPU 監視部分を削除し、CPU / ディスクのみ監視に縮小 |
| **Windows 環境** | 各スクリプト | PowerShell スクリプトに書き換え + タスクスケジューラで実行 |

---

## 6. よくある質問（FAQ）

### Q1: OpenClaw は PDCA システムの一部ですか？

**A**: いいえ。OpenClaw は PDCA システムとは**完全に独立**しています。PDCA システムが停止しても OpenClaw は動き続け、逆に OpenClaw が停止しても PDCA システムは影響を受けません。これが「三層独立運用体制」の核心です。

### Q2: OpenClaw が送る通知に、PDCA システムが自動応答することはありますか？

**A**: ありません。OpenClaw → Discord → 人間 という一方向の通知のみです。PDCA システムは hw-* チャンネルを購読しておらず、OpenClaw の通知を認識しません。

### Q3: GPU を搭載していないサーバーでも使えますか？

**A**: はい。`gpu_monitor.sh` の GPU 監視部分を無効化（またはスクリプトごと除外）すれば、CPU・メモリ・ディスクの監視だけで運用できます。

### Q4: Discord 以外の通知先（Slack、Teams、メール）に変更できますか？

**A**: はい。各スクリプト内の `curl` コマンドの送信先 URL とペイロード形式を変更するだけで対応できます。Slack Incoming Webhook の場合はペイロードの `"content"` を `"text"` に変更するだけです。

### Q5: 本システムの監視スクリプトは OpenClaw のスキルとして実装されていますか？

**A**: 本システムでは、OpenClaw のスキルエンジンを活用しつつ、監視ロジック自体は **シェルスクリプト（Bash）** として実装しています。これは意図的な設計であり、Python ランタイムや pip パッケージへの依存を避けることで、PDCA システムの Python 環境と完全に分離しています。

### Q6: vLLM 以外の推論サーバー（Ollama、TGI 等）を使う場合は？

**A**: `gpu_monitor.sh` 内のヘルスチェック URL を変更してください。例えば Ollama の場合は `http://localhost:11434/api/tags` に変更します。

### Q7: OpenClaw 本体のバージョンアップはどうすればよいですか？

**A**: OpenClaw 公式ドキュメント（[https://docs.openclaw.ai/](https://docs.openclaw.ai/)）のアップグレードガイドに従ってください。本システムのカスタム監視スクリプト（`config/openclaw/` 配下）は OpenClaw のバージョンに依存しないため、OpenClaw 本体をアップグレードしても**監視スクリプトの修正は不要**です。

### Q8: OpenClaw の他の機能（チャットボット、スマートホーム制御等）は使えますか？

**A**: OpenClaw 自体は多機能なプラットフォームですが、本システムでは**ハードウェア監視に特化**して使用しています。セキュリティの観点から、`openclaw-monitor` ユーザーには最小限の権限のみを付与しており、チャットボットやスマートホーム制御などの機能は意図的に無効化しています。他の機能を使いたい場合は、PDCA システムとは別の OpenClaw インスタンスを立てることを推奨します。

---

## 7. まとめ

| 項目 | 内容 |
|------|------|
| **名称** | OpenClaw（オープンクロー） |
| **プラットフォーム** | オープンソース自律型 AI エージェント（MIT ライセンス、[GitHub](https://github.com/openclaw/openclaw)） |
| **本システムでの役割** | 三層独立運用体制の第1層：ハードウェア監視層 |
| **活用機能** | スケジュール実行（cron）、Discord 連携、シェルスクリプト実行、セキュリティ分離 |
| **監視対象** | GPU / CPU / メモリ / ディスク / 電源 / ネットワーク / vLLM プロセス |
| **実行環境** | ホスト OS 上（Docker 外）。OpenClaw のスキルエンジン + シェルスクリプト + cron |
| **通知方法** | Discord Webhook による一方向通知 |
| **PDCA との関係** | 完全独立（API・ファイル・ネットワークすべて分離） |
| **自動修復** | GPU ファン制御 / vLLM 再起動 / ログアーカイブの 3 操作のみ |
| **流用可能性** | GPU サーバー / CI サーバー / ホームラボ / クラウド VM など幅広く活用可能 |
| **設定ファイル** | `config/openclaw/`（テンプレート）→ `/opt/openclaw/`（運用環境） |
| **公式ドキュメント** | [https://docs.openclaw.ai/](https://docs.openclaw.ai/) |

---

> 📌 **関連ドキュメント**  
> - [三層独立運用体制 アーキテクチャ設計書](../設計書/三層独立運用体制_アーキテクチャ設計書.md) — 三層独立運用体制の詳細設計  
> - [AI推論サーバー説明書](AI推論サーバー説明書.md) — vLLM・Ollama 等の推論サーバーの説明  
> - [02 システムセットアップ手順書](../手順書/02_システムセットアップ手順書.md) — OpenClaw のインストール手順（Phase 8）  
> - [04 運用保守手順書](../手順書/04_運用保守手順書.md) — 日常のハードウェアメンテナンス手順  
> - [Discordチャンネル設計書](../設計書/Discordチャンネル設計書.md) — hw-critical / hw-warning / hw-info / hw-status の設計  
> - [フォールバック運用手順書](../運用/フォールバック運用手順書.md) — vLLM 障害時の PDCA 側フォールバック手順
