# テストフィクスチャ

テスト戦略（実装手順書 §10）に準拠し、共有テストデータを管理するディレクトリ。

## ファイル一覧

| ファイル | 用途 |
|---------|------|
| `sample_goal.json` | Goalモデルのサンプルデータ |
| `sample_review_findings.json` | ReviewFindingモデルのサンプルデータ |

## 使用方法

### pytestフィクスチャとして使用（推奨）

`tests/conftest.py` にて定義済みのpytestフィクスチャを利用する。

```python
def test_example(sample_goal_data: dict) -> None:
    goal = Goal(**sample_goal_data)
    assert goal.id == "G-001"
```

### 直接読み込み

```python
from tests.conftest import load_fixture

data = load_fixture("sample_goal.json")
```
