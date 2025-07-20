"""
STT議事録システム - 文字起こしノードテスト

transcription.pyノードのテストケース
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

from src.workflows.nodes.transcription import (
    transcribe_node,
    _transcribe_single_file,
    _transcribe_multiple_chunks,
    _combine_transcriptions,
    _load_transcription_prompt,
    _generate_content_with_retry,
    check_transcription_quality
)
from src.workflows.state import STTState
from src.utils.error_handling import APIError, FileProcessingError


class TestTranscribeNode:
    """transcribe_node関数のテスト"""
    
    def create_test_state(self, **kwargs) -> STTState:
        """テスト用状態を作成"""
        default_state = {
            "session_id": "test_session",
            "timestamp": datetime.now(),
            "file_path": "/test/audio.wav",
            "original_filename": "audio.wav",
            "file_size": 1024,
            "settings": {
                "gemini_api_key": "test_api_key",
                "gemini_model": "gemini-1.5-pro"
            },
            "file_type": "audio",
            "mime_type": "audio/wav",
            "is_video_dark": None,
            "audio_duration": 120.0,
            "audio_sample_rate": 44100,
            "audio_channels": 2,
            "chunks": None,
            "chunk_durations": None,
            "processing_stage": "file_analysis",
            "transcription": None,
            "transcription_confidence": None,
            "quality_check_result": None,
            "minutes": None,
            "summary": None,
            "class_info": None,
            "errors": [],
            "warnings": [],
            "processing_log": [],
            "performance_metrics": {},
            "upload_to_notion": False,
            "notion_database_id": None,
            "notion_page_id": None,
            "output_files": [],
            "final_status": "initialized"
        }
        default_state.update(kwargs)
        return STTState(**default_state)
    
    def test_transcribe_no_gemini_api(self):
        """Gemini API利用不可のテスト"""
        with patch('src.workflows.nodes.transcription.HAS_GEMINI', False):
            state = self.create_test_state()
            result = transcribe_node(state)
            
            assert len(result["errors"]) > 0
            assert "Gemini APIが利用できません" in result["errors"][0]
            assert result["transcription"] == ""
            assert result["transcription_confidence"] == 0.0
    
    def test_transcribe_no_api_key(self):
        """APIキー未設定のテスト"""
        state = self.create_test_state(settings={})
        result = transcribe_node(state)
        
        assert len(result["errors"]) > 0
        assert "Gemini APIキーが設定されていません" in result["errors"][0]
        assert result["transcription"] == ""
        assert result["transcription_confidence"] == 0.0
    
    @patch('src.workflows.nodes.transcription._transcribe_single_file')
    def test_transcribe_single_file_success(self, mock_transcribe):
        """単一ファイル文字起こし成功のテスト"""
        mock_transcribe.return_value = "これはテスト用の文字起こし結果です。"
        
        state = self.create_test_state()
        result = transcribe_node(state)
        
        assert result["transcription"] == "これはテスト用の文字起こし結果です。"
        assert result["transcription_confidence"] == 0.8
        assert result["processing_stage"] == "transcription"
        assert len(result["errors"]) == 0
        assert len(result["processing_log"]) > 0
        
        mock_transcribe.assert_called_once_with(
            "/test/audio.wav", "gemini-1.5-pro", "test_api_key"
        )
    
    @patch('src.workflows.nodes.transcription._transcribe_multiple_chunks')
    def test_transcribe_multiple_chunks_success(self, mock_transcribe_chunks):
        """複数チャンク文字起こし成功のテスト"""
        mock_transcribe_chunks.return_value = (
            "これは複数チャンクの文字起こし結果です。", 0.85
        )
        
        state = self.create_test_state(
            chunks=["/test/chunk1.wav", "/test/chunk2.wav"],
            chunk_durations=[60.0, 60.0]
        )
        result = transcribe_node(state)
        
        assert result["transcription"] == "これは複数チャンクの文字起こし結果です。"
        assert result["transcription_confidence"] == 0.85
        assert len(result["errors"]) == 0
        
        mock_transcribe_chunks.assert_called_once_with(
            ["/test/chunk1.wav", "/test/chunk2.wav"],
            [60.0, 60.0],
            "gemini-1.5-pro",
            "test_api_key"
        )
    
    @patch('src.workflows.nodes.transcription._transcribe_single_file')
    def test_transcribe_with_api_error(self, mock_transcribe):
        """API エラー時のテスト"""
        mock_transcribe.side_effect = APIError("API呼び出しに失敗しました", "gemini", 500)
        
        state = self.create_test_state()
        result = transcribe_node(state)
        
        assert len(result["errors"]) > 0
        assert "文字起こしエラー" in result["errors"][0]
        assert result["transcription"] == ""
        assert result["transcription_confidence"] == 0.0
    
    def test_transcribe_with_custom_model(self):
        """カスタムモデル使用のテスト"""
        with patch('src.workflows.nodes.transcription._transcribe_single_file') as mock_transcribe:
            mock_transcribe.return_value = "カスタムモデルの結果"
            
            state = self.create_test_state(
                settings={
                    "gemini_api_key": "test_key",
                    "gemini_model": "gemini-1.5-flash"
                }
            )
            result = transcribe_node(state)
            
            mock_transcribe.assert_called_once_with(
                "/test/audio.wav", "gemini-1.5-flash", "test_key"
            )


class TestTranscribeSingleFile:
    """_transcribe_single_file関数のテスト"""
    
    @patch('src.workflows.nodes.transcription._load_transcription_prompt')
    @patch('src.workflows.nodes.transcription.genai.Client')
    @patch('os.environ')
    def test_transcribe_single_file_success(self, mock_env, mock_client_class, mock_load_prompt):
        """単一ファイル文字起こし成功のテスト"""
        # モックの設定
        mock_load_prompt.return_value = "文字起こしを行ってください。"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # ファイルアップロードのモック
        mock_uploaded_file = Mock()
        mock_uploaded_file.name = "uploaded_file_id"
        mock_uploaded_file.state.name = "ACTIVE"
        mock_client.files.upload.return_value = mock_uploaded_file
        mock_client.files.get.return_value = mock_uploaded_file
        
        # コンテンツ生成のモック
        mock_response = Mock()
        mock_response.text = "これは文字起こし結果です。"
        
        with patch('src.workflows.nodes.transcription._generate_content_with_retry') as mock_generate:
            mock_generate.return_value = mock_response
            
            result = _transcribe_single_file("/test/audio.wav", "gemini-1.5-pro", "test_key")
            
            assert result == "これは文字起こし結果です。"
            mock_client.files.upload.assert_called_once_with(file="/test/audio.wav")
            mock_generate.assert_called_once()
    
    @patch('src.workflows.nodes.transcription._load_transcription_prompt')
    @patch('src.workflows.nodes.transcription.genai.Client')
    @patch('os.environ')
    def test_transcribe_file_upload_failed(self, mock_env, mock_client_class, mock_load_prompt):
        """ファイルアップロード失敗のテスト"""
        mock_load_prompt.return_value = "プロンプト"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # アップロード失敗のモック
        mock_uploaded_file = Mock()
        mock_uploaded_file.state.name = "FAILED"
        mock_client.files.upload.return_value = mock_uploaded_file
        mock_client.files.get.return_value = mock_uploaded_file
        
        with pytest.raises(APIError) as exc_info:
            _transcribe_single_file("/test/audio.wav", "gemini-1.5-pro", "test_key")
        
        assert "ファイルアップロードに失敗しました" in str(exc_info.value)
    
    @patch('src.workflows.nodes.transcription._load_transcription_prompt')
    @patch('src.workflows.nodes.transcription.genai.Client')
    @patch('os.environ')
    @patch('time.sleep')
    def test_transcribe_file_processing_wait(self, mock_sleep, mock_env, mock_client_class, mock_load_prompt):
        """ファイル処理待機のテスト"""
        mock_load_prompt.return_value = "プロンプト"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # 処理中 → 完了の状態変化をモック
        mock_processing_file = Mock()
        mock_processing_file.name = "file_id"
        mock_processing_file.state.name = "PROCESSING"
        
        mock_active_file = Mock()
        mock_active_file.name = "file_id"
        mock_active_file.state.name = "ACTIVE"
        
        mock_client.files.upload.return_value = mock_processing_file
        mock_client.files.get.side_effect = [mock_processing_file, mock_active_file]
        
        mock_response = Mock()
        mock_response.text = "結果"
        
        with patch('src.workflows.nodes.transcription._generate_content_with_retry') as mock_generate:
            mock_generate.return_value = mock_response
            
            result = _transcribe_single_file("/test/audio.wav", "gemini-1.5-pro", "test_key")
            
            assert result == "結果"
            assert mock_client.files.get.call_count == 2
            mock_sleep.assert_called_once_with(1)


class TestTranscribeMultipleChunks:
    """_transcribe_multiple_chunks関数のテスト"""
    
    @patch('src.workflows.nodes.transcription._transcribe_single_file')
    @patch('src.workflows.nodes.transcription._combine_transcriptions')
    def test_transcribe_multiple_chunks_success(self, mock_combine, mock_transcribe_single):
        """複数チャンク文字起こし成功のテスト"""
        # 各チャンクの文字起こし結果をモック
        mock_transcribe_single.side_effect = [
            "最初のチャンクです。",
            "2番目のチャンクです。",
            "最後のチャンクです。"
        ]
        
        mock_combine.return_value = "最初のチャンクです。2番目のチャンクです。最後のチャンクです。"
        
        chunks = ["/test/chunk1.wav", "/test/chunk2.wav", "/test/chunk3.wav"]
        durations = [60.0, 60.0, 60.0]
        
        result_text, confidence = _transcribe_multiple_chunks(
            chunks, durations, "gemini-1.5-pro", "test_key", max_workers=2
        )
        
        assert result_text == "最初のチャンクです。2番目のチャンクです。最後のチャンクです。"
        assert confidence > 0.0
        assert mock_transcribe_single.call_count == 3
        mock_combine.assert_called_once()
    
    @patch('src.workflows.nodes.transcription._transcribe_single_file')
    def test_transcribe_chunks_with_partial_failure(self, mock_transcribe_single):
        """一部チャンク失敗時のテスト"""
        # 2番目のチャンクでエラー
        mock_transcribe_single.side_effect = [
            "最初のチャンク",
            APIError("API エラー", "gemini", 500),
            "3番目のチャンク"
        ]
        
        chunks = ["/test/chunk1.wav", "/test/chunk2.wav", "/test/chunk3.wav"]
        durations = [60.0, 60.0, 60.0]
        
        result_text, confidence = _transcribe_multiple_chunks(
            chunks, durations, "gemini-1.5-pro", "test_key", max_workers=1
        )
        
        # 成功したチャンクのみが結合される
        assert "最初のチャンク" in result_text
        assert "3番目のチャンク" in result_text
        assert confidence < 1.0  # 一部失敗により信頼度が下がる


class TestCombineTranscriptions:
    """_combine_transcriptions関数のテスト"""
    
    def test_combine_simple_transcriptions(self):
        """シンプルな文字起こし結合のテスト"""
        transcriptions = [
            "これは最初の部分です。",
            "これは2番目の部分です。",
            "これは最後の部分です。"
        ]
        
        result = _combine_transcriptions(transcriptions)
        
        expected = "これは最初の部分です。これは2番目の部分です。これは最後の部分です。"
        assert result == expected
    
    def test_combine_with_timestamps(self):
        """タイムスタンプ付き結合のテスト"""
        transcriptions = [
            "最初の発言",
            "2番目の発言",
            "最後の発言"
        ]
        chunk_times = [(0, 60), (60, 120), (120, 180)]
        
        result = _combine_transcriptions(transcriptions, chunk_times)
        
        # タイムスタンプが含まれることを確認
        assert "最初の発言" in result
        assert "2番目の発言" in result
        assert "最後の発言" in result
    
    def test_combine_empty_transcriptions(self):
        """空の文字起こし結合のテスト"""
        result = _combine_transcriptions([])
        assert result == ""
    
    def test_combine_with_empty_strings(self):
        """空文字列を含む結合のテスト"""
        transcriptions = ["最初の部分", "", "最後の部分"]
        result = _combine_transcriptions(transcriptions)
        
        assert "最初の部分" in result
        assert "最後の部分" in result


class TestLoadTranscriptionPrompt:
    """_load_transcription_prompt関数のテスト"""
    
    @patch('builtins.open', create=True)
    def test_load_prompt_success(self, mock_open):
        """プロンプト読み込み成功のテスト"""
        mock_file_content = "音声ファイルを文字起こししてください。\n正確性を重視してください。"
        mock_open.return_value.__enter__.return_value.read.return_value = mock_file_content
        
        result = _load_transcription_prompt()
        
        assert result == mock_file_content
        mock_open.assert_called_once()
    
    @patch('builtins.open', side_effect=FileNotFoundError("File not found"))
    def test_load_prompt_file_not_found(self, mock_open):
        """プロンプトファイル未発見のテスト"""
        result = _load_transcription_prompt()
        
        # デフォルトプロンプトが返される
        assert "音声ファイルを文字起こし" in result
        assert len(result) > 0


class TestGenerateContentWithRetry:
    """_generate_content_with_retry関数のテスト"""
    
    def test_generate_content_success(self):
        """コンテンツ生成成功のテスト"""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "生成されたコンテンツ"
        mock_model.generate_content.return_value = mock_response
        
        contents = ["テスト用コンテンツ"]
        result = _generate_content_with_retry(mock_model, contents)
        
        assert result == mock_response
        mock_model.generate_content.assert_called_once_with(contents)
    
    def test_generate_content_with_retry(self):
        """リトライ付きコンテンツ生成のテスト"""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "リトライ後の結果"
        
        # 最初の2回は失敗、3回目で成功
        mock_model.generate_content.side_effect = [
            Exception("一時的なエラー"),
            Exception("再度エラー"),
            mock_response
        ]
        
        contents = ["テスト用コンテンツ"]
        result = _generate_content_with_retry(mock_model, contents, max_retries=5)
        
        assert result == mock_response
        assert mock_model.generate_content.call_count == 3
    
    def test_generate_content_max_retries_exceeded(self):
        """最大リトライ回数超過のテスト"""
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("常に失敗")
        
        contents = ["テスト用コンテンツ"]
        
        with pytest.raises(Exception) as exc_info:
            _generate_content_with_retry(mock_model, contents, max_retries=2)
        
        assert "常に失敗" in str(exc_info.value)
        assert mock_model.generate_content.call_count == 3  # 初回 + 2回のリトライ


class TestCheckTranscriptionQuality:
    """check_transcription_quality関数のテスト"""
    
    def test_quality_check_good_transcription(self):
        """高品質文字起こしの品質チェック"""
        good_transcription = """
        本日の会議では、プロジェクトの進捗について話し合いました。
        開発チームからは、予定通り進んでいるとの報告がありました。
        来週までに、テスト環境の構築を完了する予定です。
        """
        
        result = check_transcription_quality(good_transcription)
        
        assert result["quality_score"] > 0.7
        assert result["word_count"] > 0
        assert result["sentence_count"] > 0
        assert len(result["issues"]) == 0
    
    def test_quality_check_poor_transcription(self):
        """低品質文字起こしの品質チェック"""
        poor_transcription = "あー、えーと、そのー、なんか、うーん。"
        
        result = check_transcription_quality(poor_transcription)
        
        assert result["quality_score"] < 0.5
        assert len(result["issues"]) > 0
        assert "フィラー語が多い" in str(result["issues"])
    
    def test_quality_check_empty_transcription(self):
        """空の文字起こしの品質チェック"""
        result = check_transcription_quality("")
        
        assert result["quality_score"] == 0.0
        assert result["word_count"] == 0
        assert result["sentence_count"] == 0
        assert len(result["issues"]) > 0
    
    def test_quality_check_repetitive_transcription(self):
        """反復的な文字起こしの品質チェック"""
        repetitive_transcription = "テスト テスト テスト テスト テスト"
        
        result = check_transcription_quality(repetitive_transcription)
        
        assert result["quality_score"] < 0.6
        assert len(result["issues"]) > 0


class TestTranscriptionIntegration:
    """文字起こし機能の統合テスト"""
    
    @patch('src.workflows.nodes.transcription._transcribe_single_file')
    def test_complete_transcription_workflow(self, mock_transcribe):
        """完全な文字起こしワークフローのテスト"""
        mock_transcribe.return_value = "これは統合テストの文字起こし結果です。品質の高い内容になっています。"
        
        state = STTState(
            session_id="integration_test",
            timestamp=datetime.now(),
            file_path="/test/integration_audio.wav",
            original_filename="integration_audio.wav",
            file_size=2048000,
            settings={
                "gemini_api_key": "integration_test_key",
                "gemini_model": "gemini-1.5-pro"
            },
            file_type="audio",
            mime_type="audio/wav",
            is_video_dark=None,
            audio_duration=180.0,
            audio_sample_rate=44100,
            audio_channels=2,
            chunks=None,
            chunk_durations=None,
            processing_stage="file_analysis",
            transcription=None,
            transcription_confidence=None,
            quality_check_result=None,
            minutes=None,
            summary=None,
            class_info=None,
            errors=[],
            warnings=[],
            processing_log=[],
            performance_metrics={},
            upload_to_notion=False,
            notion_database_id=None,
            notion_page_id=None,
            output_files=[],
            final_status="initialized"
        )
        
        result = transcribe_node(state)
        
        # 結果検証
        assert result["processing_stage"] == "transcription"
        assert result["transcription"] == "これは統合テストの文字起こし結果です。品質の高い内容になっています。"
        assert result["transcription_confidence"] == 0.8
        assert len(result["errors"]) == 0
        assert len(result["processing_log"]) > 0
        assert "文字起こし完了" in result["processing_log"][-1]
    
    @patch('src.workflows.nodes.transcription._transcribe_multiple_chunks')
    def test_multi_chunk_workflow(self, mock_transcribe_chunks):
        """複数チャンクワークフローのテスト"""
        mock_transcribe_chunks.return_value = (
            "複数チャンクの統合結果です。", 0.9
        )
        
        state = STTState(
            session_id="multi_chunk_test",
            timestamp=datetime.now(),
            file_path="/test/long_audio.wav",
            original_filename="long_audio.wav",
            file_size=10240000,
            settings={
                "gemini_api_key": "test_key",
                "gemini_model": "gemini-1.5-flash"
            },
            file_type="audio",
            mime_type="audio/wav",
            is_video_dark=None,
            audio_duration=3600.0,  # 1時間
            audio_sample_rate=44100,
            audio_channels=2,
            chunks=["/test/chunk1.wav", "/test/chunk2.wav", "/test/chunk3.wav"],
            chunk_durations=[1200.0, 1200.0, 1200.0],
            processing_stage="audio_splitting",
            transcription=None,
            transcription_confidence=None,
            quality_check_result=None,
            minutes=None,
            summary=None,
            class_info=None,
            errors=[],
            warnings=[],
            processing_log=[],
            performance_metrics={},
            upload_to_notion=False,
            notion_database_id=None,
            notion_page_id=None,
            output_files=[],
            final_status="initialized"
        )
        
        result = transcribe_node(state)
        
        assert result["transcription"] == "複数チャンクの統合結果です。"
        assert result["transcription_confidence"] == 0.9
        assert len(result["errors"]) == 0
        
        mock_transcribe_chunks.assert_called_once_with(
            ["/test/chunk1.wav", "/test/chunk2.wav", "/test/chunk3.wav"],
            [1200.0, 1200.0, 1200.0],
            "gemini-1.5-flash",
            "test_key"
        )


if __name__ == "__main__":
    pytest.main([__file__])