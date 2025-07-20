# STT議事録システム開発ガイドライン - LangGraph移行版

## 1. プロジェクト概要

### 1.1 システム目的
音声・動画ファイルから高品質な議事録を自動生成するシステムをLangGraphベースのワークフローシステムに移行し、保守性、拡張性、デバッグ性を向上させる。

### 1.2 主要機能
- 音声・動画ファイルの自動判別と前処理
- Gemini APIを使用した高精度文字起こし
- AI による議事録生成と品質チェック
- Notion連携による自動アップロード
- LangGraphによる構造化されたワークフロー管理

## 2. ビルド・設定手順

### 2.1 環境要件
- **Python**: 3.8以上（推奨: 3.11+）
- **FFmpeg**: 音声・動画処理に必要
- **Git**: バージョン管理
- **仮想環境**: venv または conda推奨

### 2.2 初期セットアップ
```bash
# 1. リポジトリクローン
git clone <repository-url>
cd stt-gijirepo

# 2. 仮想環境作成・有効化
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# または
.venv\Scripts\activate     # Windows

# 3. 依存関係インストール（開発環境）
make install-dev
# または手動で
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov black isort mypy flake8 pre-commit

# 4. 開発環境セットアップ
make setup
# これにより以下が実行される：
# - .env ファイル作成（.env.example からコピー）
# - ディレクトリ作成（logs, temp, output）
# - pre-commit フック設定
```

### 2.3 環境変数設定
`.env` ファイルを編集して必要なAPIキーを設定：
```bash
# Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# Notion API（オプション）
NOTION_TOKEN=your_notion_token_here
NOTION_DATABASE_ID=your_database_id_here
```

### 2.4 設定確認
```bash
# 環境設定チェック
make check-env

# 依存関係確認
pip list | grep -E "(langgraph|google-genai|notion-client|pytest)"
```

### 2.5 ビルド・パッケージング
```bash
# パッケージビルド
make build

# クリーンアップ
make clean

# 全削除（設定ファイル含む）
make clean-all
```

## 2. アーキテクチャ原則

### 2.1 LangGraphベースの設計
- **ノードベース処理**: 各機能を独立したノードとして実装
- **状態管理**: TypedDictによる型安全な状態管理
- **条件分岐**: 明確な条件分岐ロジックによるワークフロー制御
- **エラーハンドリング**: 統一されたエラー処理とリトライ機能

### 2.2 コード構造
```
stt-gijirepo/
├── workflows/           # LangGraphワークフロー定義
│   ├── __init__.py
│   ├── stt_workflow.py  # メインワークフロー
│   └── nodes/           # 個別ノード実装
├── core/                # コア機能
│   ├── audio_processing.py
│   ├── video_processing.py
│   └── ai_services.py
├── utils/               # ユーティリティ
└── tests/               # テストコード
```

## 3. 開発規約

### 3.1 コーディング規約
- **Python 3.8+** を使用
- **Type Hints** を必須とする
- **Docstring** は Google スタイルで記述
- **Black** によるコードフォーマット
- **isort** によるimport整理

### 3.2 ノード実装規約
```python
def node_function(state: STTState) -> STTState:
    """
    ノード関数の標準テンプレート
    
    Args:
        state: 現在の処理状態
        
    Returns:
        更新された処理状態
    """
    try:
        # 処理ロジック
        state["processing_log"].append("処理完了メッセージ")
        return state
    except Exception as e:
        state["errors"].append(f"エラーメッセージ: {str(e)}")
        return state
```

### 3.3 状態管理規約
```python
class STTState(TypedDict):
    # 入力情報
    file_path: str
    settings: dict
    
    # 処理状態
    file_type: Optional[str]
    is_video_dark: Optional[bool]
    audio_duration: Optional[float]
    chunks: Optional[List[str]]
    
    # 処理結果
    transcription: Optional[str]
    quality_check_result: Optional[dict]
    minutes: Optional[str]
    class_info: Optional[dict]
    
    # エラー・ログ
    errors: List[str]
    processing_log: List[str]
    
    # 設定
    upload_to_notion: bool
    notion_database_id: Optional[str]
```

## 4. ワークフロー設計

### 4.1 メインワークフロー
1. **file_analysis**: ファイル解析・種別判定
2. **video_processing**: 動画前処理（必要時）
3. **audio_splitting**: 音声分割（長時間音声）
4. **transcription**: 文字起こし処理
5. **quality_check**: 品質チェック
6. **minutes_generation**: 議事録生成
7. **notion_upload**: Notionアップロード（オプション）

### 4.2 条件分岐ルール
- **ファイル種別**: 動画 → 前処理, 音声 → 直接処理
- **動画明度**: 暗い → 音声抽出, 明るい → 直接処理
- **音声長**: 40分超 → 分割処理, 以下 → 直接処理
- **エラー発生**: エラーノードへ遷移

## 5. エラーハンドリング

### 5.1 エラー分類
- **入力エラー**: ファイル不正、形式不対応
- **処理エラー**: API呼び出し失敗、変換エラー
- **出力エラー**: 保存失敗、アップロード失敗

### 5.2 リトライ戦略
```python
def with_retry(func, max_retries: int = 5, backoff_factor: float = 2.0):
    """指数バックオフによるリトライ機能"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(backoff_factor ** attempt)
```

## 6. テスト設定・実行

### 6.1 テスト環境セットアップ
```bash
# テスト用依存関係インストール
pip install pytest pytest-asyncio pytest-cov

# または開発環境一括インストール
make install-dev
```

### 6.2 テスト実行コマンド
```bash
# 基本テスト実行
make test
# または
python -m pytest src/tests/ -v

# カバレッジ付きテスト
make test-coverage
# または
python -m pytest src/tests/ --cov=src --cov-report=html --cov-report=term-missing

# 単体テストのみ
make test-unit
python -m pytest src/tests/test_core/ src/tests/test_utils/ -v

# 統合テストのみ
make test-integration
python -m pytest src/tests/test_workflows/ -v

# 特定のテストファイル実行
python -m pytest src/tests/test_core/test_ai_services.py -v

# 特定のテストメソッド実行
python -m pytest src/tests/test_core/test_ai_services.py::TestGeminiService::test_init_success -v
```

### 6.3 テスト分類とマーカー
```bash
# 高速テストのみ実行（slowマーカーを除外）
python -m pytest -m "not slow"

# 統合テストのみ実行
python -m pytest -m integration

# API必須テストを除外
python -m pytest -m "not requires_api"
```

### 6.4 テスト作成例

#### 基本的なテスト構造
```python
import pytest
from src.utils.class_info import extract_class_period

class TestClassInfo:
    """ClassInfo関連のテスト"""
    
    def test_extract_class_period_basic(self):
        """基本的な時限抽出テスト"""
        # 1限目（50分 = 0:50）
        result = extract_class_period(50)
        assert result == "1限"
        
        # 2限目（140分 = 2:20）
        result = extract_class_period(140)
        assert result == "2限"
    
    @pytest.mark.parametrize("minutes,expected", [
        (50, "1限"),
        (140, "2限"),
        (230, "3限"),
        (320, "4限"),
    ])
    def test_extract_class_period_parametrized(self, minutes, expected):
        """パラメータ化テスト"""
        assert extract_class_period(minutes) == expected
```

#### モックを使用したテスト
```python
import pytest
from unittest.mock import Mock, patch
from src.core.ai_services import GeminiService

class TestGeminiService:
    """GeminiServiceのテスト"""
    
    @patch('google.genai.configure')
    @patch('google.genai.GenerativeModel')
    def test_transcribe_audio_success(self, mock_model_class, mock_configure):
        """音声文字起こし成功テスト"""
        # モック設定
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "テスト文字起こし結果"
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        # テスト実行
        service = GeminiService(api_key="test_key")
        result = service.transcribe_audio("test_audio.wav")
        
        # 検証
        assert result == "テスト文字起こし結果"
```

#### フィクスチャを使用したテスト
```python
import pytest
from pathlib import Path

@pytest.fixture
def sample_audio_file(tmp_path):
    """テスト用音声ファイル"""
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"fake_audio_data")
    return audio_file

def test_audio_processing(sample_audio_file):
    """音声処理テスト"""
    assert sample_audio_file.exists()
    assert sample_audio_file.suffix == ".wav"
```

### 6.5 テスト設定ファイル

#### pytest設定（pyproject.toml）
```toml
[tool.pytest.ini_options]
minversion = "7.0"
addopts = [
    "-ra",
    "--strict-markers",
    "--strict-config",
    "--cov=src",
    "--cov-report=term-missing",
    "--cov-report=html",
]
testpaths = ["src/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]
```

### 6.6 カバレッジレポート
```bash
# HTMLカバレッジレポート生成
make test-coverage

# カバレッジレポート確認
open htmlcov/index.html  # macOS
# または
xdg-open htmlcov/index.html  # Linux
```

### 6.7 継続的テスト
```bash
# ファイル変更監視でテスト自動実行
make test-watch
# または
python -m pytest src/tests/ -f
```

## 7. パフォーマンス最適化

### 7.1 並列処理
- 音声分割処理の並列化
- 複数ファイル処理の並列化
- API呼び出しの効率化

### 7.2 メモリ管理
- 大容量ファイルのストリーミング処理
- 中間ファイルの適切な削除
- メモリ使用量の監視

## 8. 監視・ログ

### 8.1 ログレベル
- **DEBUG**: 詳細な処理情報
- **INFO**: 一般的な処理状況
- **WARNING**: 注意が必要な状況
- **ERROR**: エラー情報

### 8.2 監視項目
- 処理時間の測定
- API呼び出し回数
- メモリ使用量
- エラー発生率

## 9. セキュリティ

### 9.1 API キー管理
- 環境変数による管理
- 設定ファイルの暗号化
- アクセス権限の制限

### 9.2 ファイル処理
- 入力ファイルの検証
- 一時ファイルの安全な削除
- パス traversal 攻撃の防止

## 10. 移行計画

### 10.1 Phase 1: 基盤構築（1-2週間）
- LangGraph環境構築
- 基本状態クラス定義
- コアノード実装

### 10.2 Phase 2: 主要機能移行（2-3週間）
- AI処理ノード実装
- 議事録生成ワークフロー構築
- 品質チェック機能統合

### 10.3 Phase 3: 高度機能実装（2-3週間）
- Notion連携改善
- 監視・デバッグ機能追加
- バッチ処理機能実装

### 10.4 Phase 4: 最適化・テスト（1-2週間）
- パフォーマンス最適化
- 包括的テスト実行
- ドキュメント整備

## 11. 品質保証

### 11.1 コードレビュー
- すべてのPRにレビューを必須とする
- アーキテクチャ変更は設計レビューを実施
- セキュリティ観点でのレビューを含める

### 11.2 継続的インテグレーション
- 自動テストの実行
- コード品質チェック
- セキュリティスキャン

## 12. ドキュメント管理

### 12.1 必須ドキュメント
- API仕様書
- ワークフロー図
- 運用手順書
- トラブルシューティングガイド

### 12.2 更新ルール
- コード変更時のドキュメント同期更新
- 定期的なドキュメントレビュー
- バージョン管理との連携

## 13. 運用・保守

### 13.1 デプロイメント
- 段階的デプロイメント
- ロールバック手順の確立
- 設定管理の自動化

### 13.2 監視・アラート
- システム稼働状況の監視
- エラー率の監視
- パフォーマンス劣化の検知

## 14. 開発固有情報

### 14.1 プロジェクト固有のコード規約

#### ファイル命名規則
```
# ワークフローノード
src/workflows/nodes/{機能名}.py

# プロンプト定義
src/prompts/definitions/{カテゴリ}/{具体的機能}.md

# テストファイル
src/tests/test_{モジュール名}/test_{機能名}.py
```

#### インポート順序（isort設定準拠）
```python
# 1. 標準ライブラリ
import os
import sys
from pathlib import Path

# 2. サードパーティライブラリ
import pytest
from google import genai
from langgraph import StateGraph

# 3. ローカルインポート
from src.core.ai_services import GeminiService
from src.utils.logging_config import get_logger
```

#### ログ出力パターン
```python
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

def example_function():
    logger.info("処理開始: example_function")
    try:
        # 処理ロジック
        logger.debug("詳細な処理情報")
        result = some_operation()
        logger.info(f"処理完了: {result}")
        return result
    except Exception as e:
        logger.error(f"処理エラー: {str(e)}", exc_info=True)
        raise
```

### 14.2 デバッグ・トラブルシューティング

#### 一般的な問題と解決方法

**1. Gemini API エラー**
```bash
# API キー確認
make check-env

# ログ確認
tail -f logs/stt_*.log | grep -i error

# テスト実行でAPI接続確認
python -c "from src.core.ai_services import GeminiService; print('API OK')"
```

**2. 音声・動画処理エラー**
```bash
# FFmpeg インストール確認
ffmpeg -version

# テストメディアファイル確認
ls -la test_media/

# 音声処理テスト
python -c "from src.core.audio_processing import AudioProcessor; print('Audio OK')"
```

**3. テスト失敗時の対処**
```bash
# 詳細なテスト出力
python -m pytest src/tests/ -v -s --tb=long

# 特定のテストのみ実行
python -m pytest src/tests/test_core/test_ai_services.py::TestGeminiService::test_init_success -v

# カバレッジ確認
make test-coverage
open htmlcov/index.html
```

#### パフォーマンス監視
```python
from src.utils.performance_monitor import PerformanceMonitor

# 使用例
monitor = PerformanceMonitor()
monitor.start_monitoring()

# 処理実行
result = some_heavy_operation()

metrics = monitor.get_metrics()
print(f"CPU使用率: {metrics['cpu_percent']}%")
print(f"メモリ使用量: {metrics['memory_mb']}MB")
```

### 14.3 開発ワークフロー

#### 新機能開発手順
1. **ブランチ作成**: `git checkout -b feature/new-feature`
2. **テスト作成**: 先にテストを書く（TDD推奨）
3. **実装**: 機能実装
4. **品質チェック**: `make quality-check`
5. **テスト実行**: `make test-coverage`
6. **プルリクエスト**: レビュー依頼

#### コミット規約
```
feat: 新機能追加
fix: バグ修正
docs: ドキュメント更新
style: コードスタイル修正
refactor: リファクタリング
test: テスト追加・修正
chore: その他の変更
```

### 14.4 プロジェクト固有の設定

#### 環境変数一覧
```bash
# 必須
GEMINI_API_KEY=your_gemini_api_key

# オプション
NOTION_TOKEN=your_notion_token
NOTION_DATABASE_ID=your_database_id
LOG_LEVEL=INFO
MAX_AUDIO_DURATION=3600
CHUNK_SIZE=300
```

#### 設定ファイル（settings.json）
```json
{
  "audio_settings": {
    "sample_rate": 16000,
    "channels": 1,
    "chunk_duration": 300
  },
  "ai_settings": {
    "model_name": "gemini-1.5-pro",
    "max_retries": 3,
    "timeout": 60
  },
  "output_settings": {
    "format": "markdown",
    "include_timestamps": true,
    "include_confidence": false
  }
}
```

### 14.5 よく使用するMakeコマンド

```bash
# 開発環境セットアップ
make setup

# テスト実行（推奨）
make test-coverage

# コード品質チェック
make quality-check

# 実行（サンプルファイル）
make run FILE=test_media/test.mp3

# バッチ処理
make run-batch DIR=input_directory

# ログ監視
make logs

# 環境確認
make check-env

# クリーンアップ
make clean
```

### 14.6 IDE設定推奨事項

#### VS Code設定（.vscode/settings.json）
```json
{
  "python.defaultInterpreterPath": "./.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.sortImports.args": ["--profile", "black"],
  "files.exclude": {
    "**/__pycache__": true,
    "**/.pytest_cache": true,
    "**/htmlcov": true
  }
}
```

#### PyCharm設定
- インタープリター: `.venv/bin/python`
- コードスタイル: Black（100文字）
- インポート最適化: isort
- テストランナー: pytest

この ガイドラインに従って開発を進めることで、保守性が高く拡張しやすいSTT議事録システムの構築を目指します。