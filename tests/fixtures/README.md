# テストフィクスチャ

テスト戦略（実装手順書 §10）に準拠し、共有テストデータを管理するディレクトリ。

## ファイル一覧

| ファイル | 用途 |
|---------|------|
| `sample_goal.json` | ゴールオブジェクトのサンプルデータ |
| `sample_review_findings.json` | レビュー指摘のサンプルデータ |

## 使用方法

```python
from tests.conftest import load_fixture

data = load_fixture("sample_goal.json")
```
