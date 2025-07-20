"""
STT議事録システム - ファイル解析ノードテスト

file_analysis.pyノードのテストケース
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.workflows.nodes.file_analysis import (
    analyze_file_node,
    _get_file_info,
    _get_audio_duration,
    _get_audio_metadata,
    is_video_file,
    is_audio_file,
    is_media_file
)
from src.workflows.state import STTState


class TestAnalyzeFileNode:
    """analyze_file_node関数のテスト"""
    
    def create_test_state(self, file_path: str) -> STTState:
        """テスト用状態を作成"""
        return STTState(
            session_id="test_session",
            timestamp=datetime.now(),
            file_path=file_path,
            original_filename=os.path.basename(file_path),
            file_size=1024,
            settings={},
            file_type=None,
            mime_type=None,
            is_video_dark=None,
            audio_duration=None,
            audio_sample_rate=None,
            audio_channels=None,
            chunks=None,
            chunk_durations=None,
            processing_stage="initialized",
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
    
    def test_analyze_nonexistent_file(self):
        """存在しないファイルの解析テスト"""
        state = self.create_test_state("/nonexistent/file.mp3")
        
        result = analyze_file_node(state)
        
        assert len(result["errors"]) > 0
        assert "ファイルが存在しません" in result["errors"][0]
        assert result["file_type"] == "unknown"
        assert result["audio_duration"] == 0.0
    
    @patch('src.workflows.nodes.file_analysis._get_file_info')
    @patch('src.workflows.nodes.file_analysis._get_audio_duration')
    @patch('src.workflows.nodes.file_analysis._get_audio_metadata')
    @patch('src.workflows.nodes.file_analysis.get_class_info')
    @patch('os.path.exists')
    def test_analyze_audio_file_success(self, mock_exists, mock_class_info, 
                                       mock_audio_metadata, mock_duration, mock_file_info):
        """音声ファイル解析成功のテスト"""
        # モックの設定
        mock_exists.return_value = True
        mock_file_info.return_value = {
            "file_type": "audio",
            "mime_type": "audio/wav"
        }
        mock_duration.return_value = 120.5
        mock_audio_metadata.return_value = {
            "audio_sample_rate": 44100,
            "audio_channels": 2
        }
        mock_class_info.return_value = {
            "name": "テスト授業",
            "teacher": "テスト先生",
            "datetime": "2024年05月20日 09:30～11:00"
        }
        
        state = self.create_test_state("/test/audio.wav")
        result = analyze_file_node(state)
        
        assert result["file_type"] == "audio"
        assert result["mime_type"] == "audio/wav"
        assert result["audio_duration"] == 120.5
        assert result["audio_sample_rate"] == 44100
        assert result["audio_channels"] == 2
        assert result["class_info"]["name"] == "テスト授業"
        assert result["processing_stage"] == "file_analysis"
        assert len(result["processing_log"]) > 0
        assert len(result["errors"]) == 0
    
    @patch('src.workflows.nodes.file_analysis._get_file_info')
    @patch('src.workflows.nodes.file_analysis._get_audio_duration')
    @patch('src.workflows.nodes.file_analysis._get_audio_metadata')
    @patch('os.path.exists')
    def test_analyze_video_file_success(self, mock_exists, mock_audio_metadata, 
                                       mock_duration, mock_file_info):
        """動画ファイル解析成功のテスト"""
        # モックの設定
        mock_exists.return_value = True
        mock_file_info.return_value = {
            "file_type": "video",
            "mime_type": "video/mp4"
        }
        mock_duration.return_value = 300.0
        mock_audio_metadata.return_value = {
            "audio_sample_rate": 48000,
            "audio_channels": 1
        }
        
        state = self.create_test_state("/test/video.mp4")
        result = analyze_file_node(state)
        
        assert result["file_type"] == "video"
        assert result["mime_type"] == "video/mp4"
        assert result["audio_duration"] == 300.0
        assert result["audio_sample_rate"] == 48000
        assert result["audio_channels"] == 1
        assert len(result["errors"]) == 0
    
    @patch('src.workflows.nodes.file_analysis._get_file_info')
    @patch('os.path.exists')
    def test_analyze_unknown_file_type(self, mock_exists, mock_file_info):
        """不明なファイル種別の解析テスト"""
        # モックの設定
        mock_exists.return_value = True
        mock_file_info.return_value = {
            "file_type": "unknown",
            "mime_type": None
        }
        
        state = self.create_test_state("/test/document.txt")
        result = analyze_file_node(state)
        
        assert result["file_type"] == "unknown"
        assert result["mime_type"] is None
        # 音声・動画でない場合は音声長は取得されない
        assert "audio_duration" not in result or result["audio_duration"] is None
    
    @patch('src.workflows.nodes.file_analysis._get_file_info')
    @patch('src.workflows.nodes.file_analysis._get_audio_duration')
    @patch('os.path.exists')
    def test_analyze_with_duration_error(self, mock_exists, mock_duration, mock_file_info):
        """音声長取得エラーのテスト"""
        # モックの設定
        mock_exists.return_value = True
        mock_file_info.return_value = {
            "file_type": "audio",
            "mime_type": "audio/mp3"
        }
        mock_duration.side_effect = Exception("Duration extraction failed")
        
        state = self.create_test_state("/test/corrupted.mp3")
        result = analyze_file_node(state)
        
        assert len(result["errors"]) > 0
        assert "ファイル解析エラー" in result["errors"][0]
        assert result["file_type"] == "unknown"  # エラー時のデフォルト値
        assert result["audio_duration"] == 0.0
    
    @patch('os.path.exists')
    def test_analyze_with_class_info_import_error(self, mock_exists):
        """クラス情報インポートエラーのテスト"""
        mock_exists.return_value = True
        
        with patch('src.workflows.nodes.file_analysis._get_file_info') as mock_file_info:
            mock_file_info.return_value = {
                "file_type": "audio",
                "mime_type": "audio/wav"
            }
            
            with patch('src.workflows.nodes.file_analysis._get_audio_duration') as mock_duration:
                mock_duration.return_value = 60.0
                
                with patch('src.workflows.nodes.file_analysis._get_audio_metadata') as mock_metadata:
                    mock_metadata.return_value = {"audio_sample_rate": 44100, "audio_channels": 2}
                    
                    # クラス情報のインポートエラーをシミュレート
                    with patch('builtins.__import__', side_effect=ImportError("Module not found")):
                        state = self.create_test_state("/test/audio.wav")
                        result = analyze_file_node(state)
                        
                        assert result["class_info"]["name"] == "不明"
                        assert result["class_info"]["teacher"] == "不明"
                        assert result["class_info"]["datetime"] == "不明"


class TestGetFileInfo:
    """_get_file_info関数のテスト"""
    
    def test_video_file_detection(self):
        """動画ファイル検出のテスト"""
        video_files = [
            "/test/video.mp4",
            "/test/movie.avi",
            "/test/clip.mov",
            "/test/recording.mkv",
            "/test/stream.webm"
        ]
        
        for file_path in video_files:
            with patch('mimetypes.guess_type') as mock_mime:
                mock_mime.return_value = ("video/mp4", None)
                result = _get_file_info(file_path)
                assert result["file_type"] == "video"
    
    def test_audio_file_detection(self):
        """音声ファイル検出のテスト"""
        audio_files = [
            "/test/audio.mp3",
            "/test/sound.wav",
            "/test/music.aac",
            "/test/recording.flac",
            "/test/voice.ogg"
        ]
        
        for file_path in audio_files:
            with patch('mimetypes.guess_type') as mock_mime:
                mock_mime.return_value = ("audio/mpeg", None)
                result = _get_file_info(file_path)
                assert result["file_type"] == "audio"
    
    def test_unknown_file_detection(self):
        """不明ファイル検出のテスト"""
        unknown_files = [
            "/test/document.txt",
            "/test/data.json",
            "/test/image.jpg",
            "/test/archive.zip"
        ]
        
        for file_path in unknown_files:
            with patch('mimetypes.guess_type') as mock_mime:
                mock_mime.return_value = ("text/plain", None)
                result = _get_file_info(file_path)
                assert result["file_type"] == "unknown"
    
    def test_mime_type_extraction(self):
        """MIMEタイプ抽出のテスト"""
        with patch('mimetypes.guess_type') as mock_mime:
            mock_mime.return_value = ("audio/wav", None)
            result = _get_file_info("/test/audio.wav")
            assert result["mime_type"] == "audio/wav"


class TestGetAudioDuration:
    """_get_audio_duration関数のテスト"""
    
    @patch('src.workflows.nodes.file_analysis.AudioSegment')
    def test_audio_duration_extraction(self, mock_audio_segment):
        """音声長抽出のテスト"""
        # AudioSegmentのモック設定
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=120500)  # 120.5秒をミリ秒で
        mock_audio_segment.from_file.return_value = mock_audio
        
        duration = _get_audio_duration("/test/audio.wav")
        assert duration == 120.5
        mock_audio_segment.from_file.assert_called_once_with("/test/audio.wav")
    
    @patch('src.workflows.nodes.file_analysis.AudioSegment')
    def test_audio_duration_error(self, mock_audio_segment):
        """音声長抽出エラーのテスト"""
        mock_audio_segment.from_file.side_effect = Exception("File format not supported")
        
        with pytest.raises(Exception):
            _get_audio_duration("/test/corrupted.mp3")


class TestGetAudioMetadata:
    """_get_audio_metadata関数のテスト"""
    
    @patch('src.workflows.nodes.file_analysis.AudioSegment')
    def test_audio_metadata_extraction(self, mock_audio_segment):
        """音声メタデータ抽出のテスト"""
        # AudioSegmentのモック設定
        mock_audio = Mock()
        mock_audio.frame_rate = 44100
        mock_audio.channels = 2
        mock_audio_segment.from_file.return_value = mock_audio
        
        metadata = _get_audio_metadata("/test/audio.wav")
        
        assert metadata["audio_sample_rate"] == 44100
        assert metadata["audio_channels"] == 2
    
    @patch('src.workflows.nodes.file_analysis.AudioSegment')
    def test_audio_metadata_error(self, mock_audio_segment):
        """音声メタデータ抽出エラーのテスト"""
        mock_audio_segment.from_file.side_effect = Exception("Metadata extraction failed")
        
        metadata = _get_audio_metadata("/test/corrupted.mp3")
        
        # エラー時はデフォルト値が返される
        assert metadata["audio_sample_rate"] is None
        assert metadata["audio_channels"] is None


class TestFileTypeDetection:
    """ファイル種別検出関数のテスト"""
    
    def test_is_video_file(self):
        """動画ファイル判定のテスト"""
        video_files = [
            "/test/video.mp4",
            "/test/movie.avi",
            "/test/clip.MOV",  # 大文字拡張子
            "/test/recording.mkv",
            "/test/stream.webm"
        ]
        
        for file_path in video_files:
            assert is_video_file(file_path) is True
        
        # 非動画ファイル
        non_video_files = [
            "/test/audio.mp3",
            "/test/document.txt",
            "/test/image.jpg"
        ]
        
        for file_path in non_video_files:
            assert is_video_file(file_path) is False
    
    def test_is_audio_file(self):
        """音声ファイル判定のテスト"""
        audio_files = [
            "/test/audio.mp3",
            "/test/sound.wav",
            "/test/music.AAC",  # 大文字拡張子
            "/test/recording.flac",
            "/test/voice.ogg"
        ]
        
        for file_path in audio_files:
            assert is_audio_file(file_path) is True
        
        # 非音声ファイル
        non_audio_files = [
            "/test/video.mp4",
            "/test/document.txt",
            "/test/image.jpg"
        ]
        
        for file_path in non_audio_files:
            assert is_audio_file(file_path) is False
    
    def test_is_media_file(self):
        """メディアファイル判定のテスト"""
        media_files = [
            "/test/video.mp4",
            "/test/audio.mp3",
            "/test/movie.avi",
            "/test/sound.wav"
        ]
        
        for file_path in media_files:
            assert is_media_file(file_path) is True
        
        # 非メディアファイル
        non_media_files = [
            "/test/document.txt",
            "/test/image.jpg",
            "/test/data.json"
        ]
        
        for file_path in non_media_files:
            assert is_media_file(file_path) is False
    
    def test_file_without_extension(self):
        """拡張子なしファイルの判定テスト"""
        assert is_video_file("/test/file_without_extension") is False
        assert is_audio_file("/test/file_without_extension") is False
        assert is_media_file("/test/file_without_extension") is False
    
    def test_empty_file_path(self):
        """空のファイルパスの判定テスト"""
        assert is_video_file("") is False
        assert is_audio_file("") is False
        assert is_media_file("") is False


class TestFileAnalysisIntegration:
    """ファイル解析の統合テスト"""
    
    def create_temp_audio_file(self) -> str:
        """テスト用音声ファイルを作成"""
        # 実際のファイルは作成せず、パスのみ返す
        return "/tmp/test_audio.wav"
    
    @patch('os.path.exists')
    @patch('src.workflows.nodes.file_analysis._get_file_info')
    @patch('src.workflows.nodes.file_analysis._get_audio_duration')
    @patch('src.workflows.nodes.file_analysis._get_audio_metadata')
    def test_complete_audio_analysis_workflow(self, mock_metadata, mock_duration, 
                                            mock_file_info, mock_exists):
        """完全な音声解析ワークフローのテスト"""
        # モックの設定
        mock_exists.return_value = True
        mock_file_info.return_value = {
            "file_type": "audio",
            "mime_type": "audio/wav"
        }
        mock_duration.return_value = 180.0
        mock_metadata.return_value = {
            "audio_sample_rate": 44100,
            "audio_channels": 2
        }
        
        # 初期状態の作成
        file_path = self.create_temp_audio_file()
        state = STTState(
            session_id="integration_test",
            timestamp=datetime.now(),
            file_path=file_path,
            original_filename="test_audio.wav",
            file_size=1024000,
            settings={"test": True},
            file_type=None,
            mime_type=None,
            is_video_dark=None,
            audio_duration=None,
            audio_sample_rate=None,
            audio_channels=None,
            chunks=None,
            chunk_durations=None,
            processing_stage="initialized",
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
        
        # ファイル解析実行
        result = analyze_file_node(state)
        
        # 結果検証
        assert result["processing_stage"] == "file_analysis"
        assert result["file_type"] == "audio"
        assert result["mime_type"] == "audio/wav"
        assert result["audio_duration"] == 180.0
        assert result["audio_sample_rate"] == 44100
        assert result["audio_channels"] == 2
        assert len(result["errors"]) == 0
        assert len(result["processing_log"]) > 0
        assert "ファイル解析完了" in result["processing_log"][-1]
    
    @patch('os.path.exists')
    @patch('src.workflows.nodes.file_analysis._get_file_info')
    def test_error_recovery_workflow(self, mock_file_info, mock_exists):
        """エラー回復ワークフローのテスト"""
        # ファイルは存在するが、情報取得でエラー
        mock_exists.return_value = True
        mock_file_info.side_effect = Exception("File info extraction failed")
        
        state = self.create_test_state("/test/problematic.mp3")
        result = analyze_file_node(state)
        
        # エラーが記録され、デフォルト値が設定される
        assert len(result["errors"]) > 0
        assert "ファイル解析エラー" in result["errors"][0]
        assert result["file_type"] == "unknown"
        assert result["audio_duration"] == 0.0
        
        # 処理は継続される（例外で停止しない）
        assert result["processing_stage"] == "file_analysis"
    
    def create_test_state(self, file_path: str) -> STTState:
        """テスト用状態を作成（統合テスト用）"""
        return STTState(
            session_id="test_session",
            timestamp=datetime.now(),
            file_path=file_path,
            original_filename=os.path.basename(file_path),
            file_size=1024,
            settings={},
            file_type=None,
            mime_type=None,
            is_video_dark=None,
            audio_duration=None,
            audio_sample_rate=None,
            audio_channels=None,
            chunks=None,
            chunk_durations=None,
            processing_stage="initialized",
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


if __name__ == "__main__":
    pytest.main([__file__])