# API リファレンス

**文書番号**：VCS-API-001  
**版**：1.0  
**作成日**：2026-03-06  
**対象モジュール**：`src/vibe_pdca/engine/api_server.py`

---

## 📖 この文書について

> この文書は、Vibe Coding PDCAシステムの **REST API** の仕様をまとめたリファレンスです。  
> たとえるなら、「レストランのメニュー表」のようなものです。どのURLに何を送ると何が返ってくるかを確認できます。

### 🔰 この文書で使われる主要な用語

| 用語 | かんたんな説明 |
|------|-------------|
| **REST API** | HTTPリクエストでシステムを操作するインターフェース |
| **エンドポイント** | APIの「窓口」となるURL（例: `/api/v1/goals`） |
| **認証（Auth）** | APIを利用する権限があるか確認する仕組み |
| **APIキー** | API利用に必要な「パスワード」のような文字列 |
| **スコープ** | APIキーに付与された権限の範囲（read/write/admin） |
| **ステータスコード** | HTTPレスポンスの結果番号（200=成功、401=認証エラー、404=見つからない） |

> 📌 **関連ドキュメント**  
> - システム設計 → [システムアーキテクチャ図](システムアーキテクチャ図.md)  
> - 要件定義 → [要件定義書](バイブコーディングPDCAシステム_要件定義書.md)  
> - 認証・権限 → [ロール権限マトリクス](ロール権限マトリクス.md)

---

## 概要

本システムは、PDCAサイクルの管理・実行を外部から操作するための REST API を提供しています。

- **ベースパス**: `/api/v1/`
- **認証方式**: APIキー認証（`X-API-Key` ヘッダー）
- **データ形式**: JSON

---

## 認証

### APIキー認証

すべてのAPIエンドポイントは認証が必要です（`auth_required=True`）。

リクエストヘッダーに APIキーを含めてください：

```
X-API-Key: your-api-key-here
```

### スコープ

APIキーには以下のスコープ（権限範囲）を設定できます：

| スコープ | 説明 | 利用可能なエンドポイント |
|---------|------|---------------------|
| `read` | 読み取り専用 | GET系（`/status`, `/metrics`, `/export`） |
| `write` | 読み取り＋書き込み | POST系（`/goals`, `/cycles`, `/approve`, `/reject`） |
| `admin` | 全権限 | 全エンドポイント＋管理操作 |

### 認証エラー

APIキーが無効または未指定の場合、以下のレスポンスが返ります：

```json
{
  "status_code": 401,
  "body": {
    "error": "Unauthorized"
  }
}
```

---

## エンドポイント一覧

| # | メソッド | パス | 説明 | 認証 |
|---|---------|------|------|:----:|
| 1 | POST | `/api/v1/goals` | 新しいゴール（目標）を設定 | ✅ |
| 2 | POST | `/api/v1/cycles` | PDCAサイクルを開始 | ✅ |
| 3 | GET | `/api/v1/status` | 現在のサイクル状態を取得 | ✅ |
| 4 | GET | `/api/v1/metrics` | メトリクス（コスト・品質等）を取得 | ✅ |
| 5 | POST | `/api/v1/approve` | ガバナンス承認を実行 | ✅ |
| 6 | POST | `/api/v1/reject` | ガバナンス却下を実行 | ✅ |
| 7 | GET | `/api/v1/export` | サイクル結果をエクスポート | ✅ |
| 8 | POST | `/api/v1/cycles/stop` | 実行中のサイクルを停止 | ✅ |

---

## エンドポイント詳細

### 1. POST `/api/v1/goals` — ゴール設定

新しいPDCAサイクルのゴール（目標）を設定します。

**リクエスト例:**
```json
{
  "goal": "Webアプリケーションのログイン機能を実装する",
  "constraints": ["Python 3.12+", "FastAPI使用"],
  "priority": "high"
}
```

**レスポンス例（200 OK）:**
```json
{
  "status_code": 200,
  "body": {
    "goal_id": "goal-2026-001",
    "status": "created"
  }
}
```

---

### 2. POST `/api/v1/cycles` — サイクル開始

ゴールに基づいてPDCAサイクルを開始します。

**リクエスト例:**
```json
{
  "goal_id": "goal-2026-001",
  "max_iterations": 5,
  "mode": "auto"
}
```

**レスポンス例（200 OK）:**
```json
{
  "status_code": 200,
  "body": {
    "cycle_id": "cycle-2026-001",
    "status": "running"
  }
}
```

---

### 3. GET `/api/v1/status` — 状態取得

現在のPDCAサイクルの実行状態を取得します。

**レスポンス例（200 OK）:**
```json
{
  "status_code": 200,
  "body": {
    "cycle_id": "cycle-2026-001",
    "phase": "CHECK",
    "iteration": 3,
    "status": "running",
    "progress": 0.6
  }
}
```

---

### 4. GET `/api/v1/metrics` — メトリクス取得

コスト、品質スコア、実行時間などのメトリクスを取得します。

**レスポンス例（200 OK）:**
```json
{
  "status_code": 200,
  "body": {
    "total_cost_usd": 1.25,
    "quality_score": 0.85,
    "iterations_completed": 3,
    "llm_calls": 42,
    "tokens_used": 15000
  }
}
```

---

### 5. POST `/api/v1/approve` — ガバナンス承認

B操作・C操作のガバナンス承認を実行します。

**リクエスト例:**
```json
{
  "cycle_id": "cycle-2026-001",
  "approver": "owner",
  "comment": "品質基準を満たしているため承認"
}
```

**レスポンス例（200 OK）:**
```json
{
  "status_code": 200,
  "body": {
    "approved": true,
    "timestamp": "2026-03-06T12:00:00Z"
  }
}
```

---

### 6. POST `/api/v1/reject` — ガバナンス却下

ガバナンス承認を却下します。

**リクエスト例:**
```json
{
  "cycle_id": "cycle-2026-001",
  "rejector": "owner",
  "reason": "セキュリティレビューが未完了"
}
```

---

### 7. GET `/api/v1/export` — エクスポート

サイクルの実行結果・レビュー結果をエクスポートします。

**レスポンス例（200 OK）:**
```json
{
  "status_code": 200,
  "body": {
    "format": "json",
    "data": {
      "cycle_id": "cycle-2026-001",
      "reviews": [...],
      "audit_log": [...]
    }
  }
}
```

---

### 8. POST `/api/v1/cycles/stop` — サイクル停止

実行中のPDCAサイクルを停止します。

**リクエスト例:**
```json
{
  "cycle_id": "cycle-2026-001",
  "reason": "手動停止"
}
```

---

## エラーレスポンス

### 共通エラー形式

```json
{
  "status_code": <HTTPステータスコード>,
  "body": {
    "error": "<エラーメッセージ>"
  }
}
```

### ステータスコード一覧

| コード | 意味 | 説明 |
|:------:|------|------|
| 200 | OK | リクエスト成功 |
| 401 | Unauthorized | APIキーが無効または未指定 |
| 404 | Not Found | エンドポイントが見つからない |
| 500 | Internal Server Error | サーバー内部エラー |

---

## データモデル

### APIRequest

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `method` | `APIMethod` | HTTPメソッド（GET/POST/PUT/DELETE） |
| `path` | `str` | リクエストパス |
| `headers` | `dict[str, str]` | リクエストヘッダー |
| `body` | `dict[str, Any]` | リクエストボディ |

### APIResponse

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `status_code` | `int` | HTTPステータスコード |
| `body` | `dict[str, Any]` | レスポンスボディ |
| `headers` | `dict[str, str]` | レスポンスヘッダー |

---

## 使い方の例

### Python（httpx）

```python
import httpx

# ゴール設定
response = httpx.post(
    "http://localhost:8000/api/v1/goals",
    headers={"X-API-Key": "your-api-key"},
    json={"goal": "ログイン機能の実装"}
)
print(response.json())

# 状態確認
response = httpx.get(
    "http://localhost:8000/api/v1/status",
    headers={"X-API-Key": "your-api-key"}
)
print(response.json())
```

### cURL

```bash
# ゴール設定
curl -X POST http://localhost:8000/api/v1/goals \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"goal": "ログイン機能の実装"}'

# 状態確認
curl -X GET http://localhost:8000/api/v1/status \
  -H "X-API-Key: your-api-key"
```
