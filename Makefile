# Makefile — 開発者向けコマンド集
# ※ 初心者向け: make <コマンド名> で各操作を実行できます
# たとえるなら、家電のリモコンのボタンのようなものです

.PHONY: help install install-gui lint type-check test test-all test-verbose test-cov security clean

# デフォルトターゲット: ヘルプを表示
help: ## ヘルプを表示
	@echo ""
	@echo "バイブコーディングPDCA開発コマンド"
	@echo "=================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# --- セットアップ ---

install: ## 開発用にインストール（pip install -e ".[dev]"）
	pip install -e ".[dev]"

install-gui: ## GUI込みでインストール（pip install -e ".[dev,gui]"）
	pip install -e ".[dev,gui]"

# --- コード品質チェック ---

lint: ## Lint チェック（ruff check src/ tests/）
	ruff check src/ tests/

lint-fix: ## Lint 自動修正（ruff check --fix src/ tests/）
	ruff check --fix src/ tests/

format: ## コードフォーマット（ruff format src/ tests/）
	ruff format src/ tests/

type-check: ## 型チェック（mypy src/ --exclude gui）
	mypy src/ --exclude 'src/vibe_pdca/gui/'

# --- テスト ---

test: ## テスト実行（GUI除外、短縮出力）
	pytest --tb=short -q --ignore=tests/test_gui.py

test-all: ## 全テスト実行（GUI含む）
	pytest --tb=short -q

test-verbose: ## テスト実行（詳細出力）
	pytest -v --ignore=tests/test_gui.py

test-cov: ## カバレッジ付きテスト
	pytest --cov=src/vibe_pdca --cov-report=term-missing --ignore=tests/test_gui.py

# --- セキュリティ ---

security: ## シークレットスキャン（gitleaks）
	gitleaks detect --source . --config .gitleaks.toml

# --- ユーティリティ ---

clean: ## キャッシュ・ビルド成果物を削除
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .coverage htmlcov/

check: lint type-check test ## Lint + 型チェック + テストを一括実行
