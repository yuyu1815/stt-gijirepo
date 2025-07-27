"""
STT議事録システム - pytest設定とフィクスチャ

テスト実行に必要な設定、フィクスチャ、モックオブジェクトを提供
"""

import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Generator
import pytest
from unittest.mock import Mock, MagicMock, patch

# テスト用のインポート
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.workflows.state import STTState, STTConfig, create_initial_state, create_default_config
from src.utils.performance_monitor import PerformanceMonitor


# テスト設定
pytest_plugins = []


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """テストデータディレクトリのパス"""
    return Path(__file__).parent / "test_data"


@pytest.fixture(scope="session")
def temp_dir() -> Generator[Path, None, None]:
    """一時ディレクトリ"""
    temp_path = Path(tempfile.mkdtemp(prefix="stt_test_"))
    try:
        yield temp_path
    finally:
        if temp_path.exists():
            shutil.rmtree(temp_path)


@pytest.fixture
def sample_audio_file() -> Path:
    """サンプル音声ファイル"""
    # 実際のテストメディアファイルを使用
    project_root = Path(__file__).parent.parent.parent
    audio_file = project_root / "test_media" / "test.mp3"
    if not audio_file.exists():
        pytest.skip(f"Test media file not found: {audio_file}")
    return audio_file


@pytest.fixture
def sample_video_file() -> Path:
    """サンプル動画ファイル"""
    # 実際のテストメディアファイルを使用
    project_root = Path(__file__).parent.parent.parent
    video_file = project_root / "test_media" / "test.mp4"
    if not video_file.exists():
        pytest.skip(f"Test media file not found: {video_file}")
    return video_file


@pytest.fixture
def test_config() -> STTConfig:
    """テスト用設定"""
    import json
    from pathlib import Path
    
    # settings.jsonからAPI設定を読み込む
    api_settings = {
        "gemini_api_key": "test_api_key",
        "gemini_model": "gemini-1.5-pro",
        "notion_token": "test_notion_token",
        "notion_database_id": "test_database_id"
    }
    
    settings_file = Path("settings.json")
    if settings_file.exists():
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                
                # API設定を上書き
                for key in ["gemini_api_key", "gemini_model", "notion_token", "notion_database_id"]:
                    if key in settings:
                        api_settings[key] = settings[key]
        except Exception as e:
            print(f"警告: 設定ファイル({settings_file})の読み込みに失敗しました: {e}")
            print("テスト用のデフォルト値を使用します。")
    
    return STTConfig(
        # API設定
        gemini_api_key=api_settings["gemini_api_key"],
        gemini_model=api_settings["gemini_model"],
        notion_token=api_settings["notion_token"],
        
        # 処理設定
        max_audio_duration=600,  # 10分（テスト用に短縮）
        chunk_size=60,  # 1分（テスト用に短縮）
        max_retries=3,
        retry_delay=0.1,  # テスト用に短縮
        
        # 品質設定
        min_confidence_threshold=0.5,
        enable_quality_check=True,
        enable_hallucination_check=True,
        
        # 出力設定
        output_format="markdown",
        include_timestamps=True,
        include_speaker_labels=False,
        
        # Notion設定
        notion_database_id=api_settings["notion_database_id"],
        notion_template_id=None
    )


@pytest.fixture
def test_state(sample_audio_file: Path, test_config: STTConfig) -> STTState:
    """テスト用状態"""
    return create_initial_state(
        file_path=str(sample_audio_file),
        config=test_config,
        upload_to_notion=False
    )


@pytest.fixture
def sample_transcription() -> str:
    """サンプル文字起こしテキスト"""
    return """
こんにちは、皆さん。今日は重要な会議を開催いたします。
まず、プロジェクトの進捗状況について報告いたします。
現在、開発は順調に進んでおり、予定通り来月末には完成予定です。
次に、予算についてですが、当初の見積もりより10%削減できる見込みです。
最後に、次回の会議は来週の金曜日、午後2時から開催いたします。
以上で報告を終わります。ありがとうございました。
"""


@pytest.fixture
def sample_minutes() -> str:
    """サンプル議事録"""
    return """
# 議事録

## 基本情報
- 日時: 2024-01-15 14:00
- 参加者: 田中、佐藤、鈴木
- 議題: プロジェクト進捗報告

## 議論内容
### 主要な議論ポイント
- プロジェクトの進捗状況
- 予算の見直し
- 次回会議の日程

### 決定事項
- 開発は予定通り来月末完成
- 予算を10%削減
- 次回会議は来週金曜日14:00

## アクションアイテム
- [ ] 田中: 最終仕様書の確認 (期限: 2024-01-20)
- [ ] 佐藤: 予算削減案の詳細検討 (期限: 2024-01-18)

## 次回予定
- 日時: 2024-01-22 14:00
- 議題: 最終確認と承認
"""


@pytest.fixture
def mock_gemini_service():
    """モックGeminiサービス"""
    mock_service = Mock()
    
    # 文字起こしのモック
    mock_service.transcribe_audio.return_value = {
        'transcription': 'テスト用文字起こし結果',
        'confidence': 0.85,
        'language': 'ja',
        'model_used': 'gemini-1.5-pro',
        'processing_time': 1234567890
    }
    
    # 品質チェックのモック
    mock_service.check_transcription_quality.return_value = {
        'grammar_score': 8,
        'coherence_score': 9,
        'terminology_score': 7,
        'readability_score': 8,
        'overall_score': 8,
        'has_hallucination': False,
        'issues': [],
        'suggestions': ['改善提案1', '改善提案2']
    }
    
    # 議事録生成のモック
    mock_service.generate_minutes.return_value = {
        'minutes': 'テスト用議事録',
        'summary': 'テスト用サマリー',
        'format_type': 'detailed',
        'word_count': 100,
        'model_used': 'gemini-1.5-pro',
        'generated_at': 1234567890
    }
    
    return mock_service


@pytest.fixture
def mock_notion_client():
    """モックNotionクライアント"""
    mock_client = Mock()
    
    # ページ作成のモック
    mock_client.create_page.return_value = {
        'page_id': 'test_page_id',
        'url': 'https://notion.so/test_page',
        'title': 'テスト議事録',
        'created_time': '2024-01-15T14:00:00Z',
        'last_edited_time': '2024-01-15T14:00:00Z'
    }
    
    # データベース情報のモック
    mock_client.get_database_info.return_value = {
        'database_id': 'test_database_id',
        'title': 'テストデータベース',
        'url': 'https://notion.so/test_database',
        'properties': {},
        'created_time': '2024-01-01T00:00:00Z',
        'last_edited_time': '2024-01-15T14:00:00Z'
    }
    
    return mock_client


@pytest.fixture
def mock_audio_processor():
    """モック音声プロセッサ"""
    mock_processor = Mock()
    
    # 音声読み込みのモック
    mock_audio_segment = Mock()
    mock_audio_segment.__len__ = Mock(return_value=60000)  # 60秒
    mock_processor.load_audio.return_value = mock_audio_segment
    
    # メタデータ取得のモック
    mock_processor.get_audio_metadata.return_value = {
        'duration': 60.0,
        'sample_rate': 16000,
        'channels': 1,
        'codec': 'pcm_s16le',
        'bit_rate': 256000,
        'file_size': 1920000
    }
    
    # 音声分割のモック
    mock_processor.split_audio.return_value = [mock_audio_segment]
    
    # チャンク保存のモック
    mock_processor.save_audio_chunks.return_value = ['chunk_001.wav']
    
    return mock_processor


@pytest.fixture
def mock_video_processor():
    """モック動画プロセッサ"""
    mock_processor = Mock()
    
    # 動画メタデータのモック
    mock_processor.get_video_metadata.return_value = {
        'duration': 120.0,
        'file_size': 10485760,  # 10MB
        'format_name': 'mp4',
        'has_video': True,
        'has_audio': True,
        'width': 1920,
        'height': 1080,
        'fps': 30.0,
        'video_codec': 'h264',
        'audio_sample_rate': 48000,
        'audio_channels': 2,
        'audio_codec': 'aac'
    }
    
    # 明度解析のモック
    mock_processor.analyze_video_brightness.return_value = {
        'average_brightness': 128.0,
        'min_brightness': 50.0,
        'max_brightness': 200.0,
        'std_brightness': 30.0,
        'is_dark': False,
        'sample_count': 10,
        'analysis_method': 'opencv'
    }
    
    # 音声抽出のモック
    mock_processor.extract_audio_from_video.return_value = '/tmp/extracted_audio.wav'
    
    return mock_processor


@pytest.fixture
def mock_file_utils():
    """モックファイルユーティリティ"""
    mock_utils = Mock()
    
    # ファイル検証のモック
    mock_utils.validate_file.return_value = {
        'file_path': '/test/file.wav',
        'file_name': 'file.wav',
        'file_size': 1024000,
        'file_extension': '.wav',
        'mime_type': 'audio/wav',
        'is_audio': True,
        'is_video': False,
        'is_supported': True,
        'size_ok': True,
        'is_empty': False,
        'is_valid': True
    }
    
    # ファイル情報のモック
    mock_utils.get_file_info.return_value = {
        'absolute_path': '/test/file.wav',
        'file_name': 'file.wav',
        'file_size': 1024000,
        'file_hash': 'abc123def456',
        'is_readable': True,
        'is_writable': True
    }
    
    return mock_utils


@pytest.fixture
def performance_monitor() -> PerformanceMonitor:
    """パフォーマンス監視インスタンス"""
    return PerformanceMonitor(
        collection_interval=0.1,  # テスト用に短縮
        max_history_size=100,
        enable_auto_collection=False  # テストでは手動制御
    )


@pytest.fixture
def mock_environment_variables():
    """環境変数のモック"""
    import json
    from pathlib import Path
    
    # デフォルト値
    env_vars = {
        'GEMINI_API_KEY': 'test_gemini_key',
        'NOTION_TOKEN': 'test_notion_token',
        'NOTION_DATABASE_ID': 'test_database_id'
    }
    
    # settings.jsonからAPI設定を読み込む
    settings_file = Path("settings.json")
    if settings_file.exists():
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                
                # API設定を上書き
                if "gemini_api_key" in settings:
                    env_vars['GEMINI_API_KEY'] = settings["gemini_api_key"]
                if "notion_token" in settings:
                    env_vars['NOTION_TOKEN'] = settings["notion_token"]
                if "notion_database_id" in settings:
                    env_vars['NOTION_DATABASE_ID'] = settings["notion_database_id"]
        except Exception as e:
            print(f"警告: 設定ファイル({settings_file})の読み込みに失敗しました: {e}")
            print("テスト用のデフォルト環境変数を使用します。")
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


# テスト用ヘルパー関数
def create_test_state(**overrides) -> STTState:
    """テスト用状態を作成"""
    default_state = {
        'session_id': 'test_session_123',
        'timestamp': datetime.now(),
        'file_path': '/test/audio.wav',
        'original_filename': 'audio.wav',
        'file_size': 1024000,
        'settings': {},
        'file_type': 'audio',
        'mime_type': 'audio/wav',
        'is_video_dark': None,
        'audio_duration': 60.0,
        'audio_sample_rate': 16000,
        'audio_channels': 1,
        'chunks': None,
        'chunk_durations': None,
        'processing_stage': 'initialized',
        'transcription': None,
        'transcription_confidence': None,
        'quality_check_result': None,
        'minutes': None,
        'summary': None,
        'class_info': None,
        'errors': [],
        'warnings': [],
        'processing_log': ['テスト初期化完了'],
        'performance_metrics': {},
        'upload_to_notion': False,
        'notion_database_id': None,
        'notion_page_id': None,
        'output_files': [],
        'final_status': 'initialized'
    }
    
    default_state.update(overrides)
    return STTState(**default_state)


def assert_state_transition(before_state: STTState, after_state: STTState, expected_changes: Dict[str, Any]):
    """状態遷移のアサーション"""
    for key, expected_value in expected_changes.items():
        assert key in after_state, f"状態に'{key}'が存在しません"
        assert after_state[key] == expected_value, f"'{key}'の値が期待値と異なります: {after_state[key]} != {expected_value}"


def assert_no_errors(state: STTState):
    """エラーがないことをアサート"""
    assert len(state['errors']) == 0, f"エラーが発生しています: {state['errors']}"


def assert_processing_log_contains(state: STTState, expected_message: str):
    """処理ログに期待するメッセージが含まれることをアサート"""
    assert any(expected_message in log for log in state['processing_log']), \
        f"処理ログに'{expected_message}'が見つかりません: {state['processing_log']}"


# テスト用マーカー
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
pytest.mark.requires_api = pytest.mark.requires_api