# STT議事録システム Makefile
# 開発・運用タスクの自動化

.PHONY: help install install-dev test test-verbose test-coverage lint format type-check clean build run setup docs docker

# デフォルトターゲット
.DEFAULT_GOAL := help

# =============================================================================
# ヘルプ
# =============================================================================

help: ## このヘルプメッセージを表示
	@echo "STT議事録システム - 利用可能なコマンド:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# =============================================================================
# 環境セットアップ
# =============================================================================

install: ## 本番用依存関係をインストール
	pip install -r requirements.txt

install-dev: ## 開発用依存関係をインストール
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-cov black isort mypy flake8 pre-commit

setup: install-dev ## 開発環境の初期セットアップ
	@echo "開発環境をセットアップしています..."
	@if [ ! -f .env ]; then \
		echo ".env ファイルを作成しています..."; \
		cp .env.example .env; \
		echo ".env ファイルを編集して適切な値を設定してください"; \
	fi
	@mkdir -p logs temp output
	@echo "pre-commit フックをインストールしています..."
	pre-commit install
	@echo "セットアップ完了!"

# =============================================================================
# テスト
# =============================================================================

test: ## テストを実行
	python -m pytest src/tests/ -v

test-verbose: ## 詳細なテストを実行
	python -m pytest src/tests/ -v -s --tb=long

test-coverage: ## カバレッジ付きでテストを実行
	python -m pytest src/tests/ --cov=src --cov-report=html --cov-report=term-missing

test-unit: ## 単体テストのみ実行
	python -m pytest src/tests/test_core/ src/tests/test_utils/ -v

test-integration: ## 統合テストのみ実行
	python -m pytest src/tests/test_workflows/ -v

test-watch: ## ファイル変更を監視してテストを自動実行
	python -m pytest src/tests/ -f

# =============================================================================
# コード品質
# =============================================================================

lint: ## コード品質チェック (flake8)
	flake8 src/ --max-line-length=88 --extend-ignore=E203,W503

format: ## コードフォーマット (black + isort)
	black src/
	isort src/

format-check: ## フォーマットチェック (変更なし)
	black --check src/
	isort --check-only src/

type-check: ## 型チェック (mypy)
	mypy src/ --ignore-missing-imports

quality-check: format-check lint type-check ## 全品質チェックを実行

pre-commit: ## pre-commit フックを手動実行
	pre-commit run --all-files

# =============================================================================
# 実行
# =============================================================================

run: ## メインプログラムを実行 (引数: FILE=path/to/audio.wav)
	@if [ -z "$(FILE)" ]; then \
		echo "使用方法: make run FILE=path/to/audio.wav"; \
		exit 1; \
	fi
	python src/main.py "$(FILE)"

run-batch: ## バッチ処理を実行 (引数: DIR=path/to/directory)
	@if [ -z "$(DIR)" ]; then \
		echo "使用方法: make run-batch DIR=path/to/directory"; \
		exit 1; \
	fi
	python src/scripts/batch_process.py "$(DIR)"

run-example: ## サンプルファイルで実行
	python src/main.py examples/sample_files/sample.wav

# =============================================================================
# ビルド・パッケージング
# =============================================================================

build: clean ## パッケージをビルド
	python -m build

clean: ## 一時ファイル・キャッシュを削除
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/
	rm -rf temp/ logs/*.log output/

clean-all: clean ## 全ての生成ファイルを削除 (設定ファイル含む)
	rm -rf .env logs/ temp/ output/

# =============================================================================
# ドキュメント
# =============================================================================

docs: ## ドキュメントを生成
	@echo "API ドキュメントを生成しています..."
	@mkdir -p docs/api
	python -c "import src.workflows.stt_workflow; help(src.workflows.stt_workflow)" > docs/api/workflow_api.txt
	@echo "ドキュメント生成完了: docs/"

docs-serve: ## ドキュメントサーバーを起動 (要 mkdocs)
	@if command -v mkdocs >/dev/null 2>&1; then \
		mkdocs serve; \
	else \
		echo "mkdocs がインストールされていません。pip install mkdocs でインストールしてください。"; \
	fi

# =============================================================================
# パフォーマンス・ベンチマーク
# =============================================================================

benchmark: ## パフォーマンステストを実行
	python src/scripts/performance_benchmark.py

profile: ## プロファイリングを実行 (引数: FILE=path/to/audio.wav)
	@if [ -z "$(FILE)" ]; then \
		echo "使用方法: make profile FILE=path/to/audio.wav"; \
		exit 1; \
	fi
	python -m cProfile -o profile_results.prof src/main.py "$(FILE)"
	@echo "プロファイル結果: profile_results.prof"

# =============================================================================
# データベース・移行
# =============================================================================

migrate: ## 既存システムからの移行を実行
	python src/scripts/migrate_legacy.py

# =============================================================================
# Docker
# =============================================================================

docker-build: ## Dockerイメージをビルド
	docker build -t stt-gijirepo .

docker-run: ## Dockerコンテナを実行
	docker run -it --rm -v $(PWD):/app stt-gijirepo

docker-compose-up: ## Docker Composeでサービスを起動
	docker-compose up -d

docker-compose-down: ## Docker Composeでサービスを停止
	docker-compose down

# =============================================================================
# 開発支援
# =============================================================================

dev-server: ## 開発サーバーを起動 (ファイル監視付き)
	@echo "開発サーバーを起動しています..."
	@echo "ファイル変更を監視中... (Ctrl+C で停止)"
	python -m watchdog.observers src/ --patterns="*.py" --command="make test-unit"

install-hooks: ## Git フックをインストール
	pre-commit install
	@echo "Git pre-commit フックがインストールされました"

check-env: ## 環境設定をチェック
	@echo "環境設定をチェックしています..."
	@python -c "import os; print('GEMINI_API_KEY:', 'OK' if os.getenv('GEMINI_API_KEY') else 'NOT SET')"
	@python -c "import os; print('NOTION_TOKEN:', 'OK' if os.getenv('NOTION_TOKEN') else 'NOT SET')"
	@echo "Python バージョン: $(shell python --version)"
	@echo "pip パッケージ:"
	@pip list | grep -E "(langgraph|google-genai|notion-client|pytest)"

# =============================================================================
# リリース
# =============================================================================

version: ## 現在のバージョンを表示
	@python -c "import src; print(getattr(src, '__version__', 'Unknown'))" 2>/dev/null || echo "バージョン情報が見つかりません"

release-check: quality-check test ## リリース前チェック
	@echo "リリース前チェックを実行しています..."
	@echo "✓ コード品質チェック完了"
	@echo "✓ テスト実行完了"
	@echo "リリース準備完了!"

# =============================================================================
# ログ・監視
# =============================================================================

logs: ## ログファイルを表示
	@if [ -f logs/stt_system.log ]; then \
		tail -f logs/stt_system.log; \
	else \
		echo "ログファイルが見つかりません: logs/stt_system.log"; \
	fi

logs-error: ## エラーログのみ表示
	@if [ -f logs/stt_system.log ]; then \
		grep -i error logs/stt_system.log | tail -20; \
	else \
		echo "ログファイルが見つかりません"; \
	fi

monitor: ## システム監視情報を表示
	@echo "=== システム監視情報 ==="
	@echo "CPU使用率:"
	@top -l 1 | grep "CPU usage" || echo "CPU情報を取得できませんでした"
	@echo ""
	@echo "メモリ使用量:"
	@free -h 2>/dev/null || vm_stat | head -5 || echo "メモリ情報を取得できませんでした"
	@echo ""
	@echo "ディスク使用量:"
	@df -h . || echo "ディスク情報を取得できませんでした"