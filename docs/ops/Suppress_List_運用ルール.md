# Suppress List 運用ルール

**文書番号**：VCS-SUPPRESS-001  
**版**：1.0  
**作成日**：2026-02-27  
**関連要件**：§26.10, タスク3-9

---

## 1. 目的

レビュー指摘の中で「意図的に対処しない」と判断された既知の誤検知パターンを管理し、以降のサイクルでACT判断から自動的に除外する仕組みを定義する。

---

## 2. 登録フロー

1. OwnerまたはMaintainerが登録を申請（パターン・理由・有効期限を必須記載）
2. A操作として4/4承認を取得
3. 承認後 `suppress_list.json` に追記、監査ログに記録

---

## 3. エントリ形式

```json
{
  "id": "SUP-001",
  "pattern": {
    "category": "performance",
    "keyword": "N+1クエリ",
    "file_path_regex": "^src/legacy/.*",
    "severity": "major"
  },
  "reason": "レガシーモジュールは次マイルストーンでリプレース予定",
  "registered_by": "owner@example.com",
  "registered_at": "2026-03-15T10:00:00Z",
  "approved_by": ["owner", "maintainer", "reviewer", "auditor"],
  "expiry": { "type": "milestone", "value": "M3" },
  "status": "active"
}
```

status: `active` / `expired` / `revoked`（エントリのライフサイクル）

---

## 4. 有効期限管理

- **マイルストーン単位**：対象マイルストーン完了時に自動 `expired`
- **永続（permanent）**：四半期ごとに棚卸し（Ownerの責任）
- **手動取り消し**：OwnerがA操作として `revoked` に変更

---

## 5. ACTフェーズでの扱い

- パターンマッチした指摘は **レビュー指摘の判定結果** を `suppressed` とする（エントリstatusとは別）
- `suppressed` 指摘はACT採否判断から除外
- 統合レビューサマリに `suppressed` 件数を必ず表示（隠蔽防止）
- 件数急増時（前回比+5件以上）はDiscord警告通知

---

## 6. 保存場所

`{project_repo}/config/suppress_list.json` で版管理。変更はPRとして管理。

---

## 変更履歴

| 日付 | 変更内容 | 変更者 |
|------|---------|--------|
| 2026-02-27 | 初版作成 | 実装担当 |
