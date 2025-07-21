"""
Tests for split media workflow node.
"""

import pytest
import os
import tempfile
import subprocess
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
from typing import Dict, Any, List

from src.workflows.nodes.split_media import split_media_node, _convert_audio_to_video
from src.workflows.state import STTState
from src.utils.error_handling import FileProcessingError


class TestSplitMediaNode:
    """Tests for split_media_node functionality"""
    
    @pytest.fixture
    def base_state(self):
        """Create base STT state for testing"""
        return {
            "file_path": "/test/audio.wav",
            "file_type": "audio",
            "settings": {"chunk_size": 300},
            "processing_log": [],
            "errors": [],
            "force_video_mode": False
        }
    
    @pytest.fixture
    def video_state(self, base_state):
        """Create video STT state for testing"""
        state = base_state.copy()
        state["file_path"] = "/test/video.mp4"
        state["file_type"] = "video"
        return state
    
    @pytest.fixture
    def sample_audio_file(self):
        """Create a temporary audio file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(b"fake_audio_data")
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)
    
    @pytest.fixture
    def sample_video_file(self):
        """Create a temporary video file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            f.write(b"fake_video_data")
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    @patch('src.workflows.nodes.split_media.AudioProcessor')
    def test_split_media_node_audio_success(self, mock_audio_processor_class, base_state):
        """Test successful audio media splitting"""
        # Mock AudioProcessor
        mock_processor = Mock()
        mock_audio_processor_class.return_value = mock_processor
        mock_processor.split_audio_into_chunks.return_value = [
            "/temp/chunk_001.wav",
            "/temp/chunk_002.wav",
            "/temp/chunk_003.wav"
        ]
        
        result = split_media_node(base_state)
        
        assert result["processing_stage"] == "splitting_media"
        assert "media_chunks" in result
        assert len(result["media_chunks"]) == 3
        assert result["media_chunks"][0] == "/temp/chunk_001.wav"
        assert len(result["processing_log"]) > 0
        assert "メディア分割完了: 3個のチャンク" in result["processing_log"]
        assert len(result["errors"]) == 0
        
        mock_processor.split_audio_into_chunks.assert_called_once_with(
            "/test/audio.wav",
            chunk_duration=300
        )

    @patch('src.workflows.nodes.split_media.VideoProcessor')
    def test_split_media_node_video_success(self, mock_video_processor_class, video_state):
        """Test successful video media splitting"""
        # Mock VideoProcessor
        mock_processor = Mock()
        mock_video_processor_class.return_value = mock_processor
        mock_processor.split_video_into_chunks.return_value = [
            "/temp/chunk_001.mp4",
            "/temp/chunk_002.mp4"
        ]
        
        result = split_media_node(video_state)
        
        assert result["processing_stage"] == "splitting_media"
        assert "media_chunks" in result
        assert len(result["media_chunks"]) == 2
        assert result["media_chunks"][0] == "/temp/chunk_001.mp4"
        assert len(result["processing_log"]) > 0
        assert "メディア分割完了: 2個のチャンク" in result["processing_log"]
        assert len(result["errors"]) == 0
        
        mock_processor.split_video_into_chunks.assert_called_once_with(
            "/test/video.mp4",
            chunk_duration=300
        )

    @patch('src.workflows.nodes.split_media.VideoProcessor')
    @patch('src.workflows.nodes.split_media._convert_audio_to_video')
    def test_split_media_node_force_video_mode(self, mock_convert, mock_video_processor_class, base_state):
        """Test audio splitting in force video mode"""
        # Setup force video mode
        base_state["force_video_mode"] = True
        
        # Mock conversion
        mock_convert.return_value = "/temp/converted_video.mp4"
        
        # Mock VideoProcessor
        mock_processor = Mock()
        mock_video_processor_class.return_value = mock_processor
        mock_processor.split_video_into_chunks.return_value = [
            "/temp/video_chunk_001.mp4",
            "/temp/video_chunk_002.mp4"
        ]
        
        result = split_media_node(base_state)
        
        assert result["processing_stage"] == "splitting_media"
        assert "media_chunks" in result
        assert len(result["media_chunks"]) == 2
        assert "output_files" in result
        assert "/temp/converted_video.mp4" in result["output_files"]
        assert len(result["errors"]) == 0
        
        mock_convert.assert_called_once_with("/test/audio.wav")
        mock_processor.split_video_into_chunks.assert_called_once_with(
            "/temp/converted_video.mp4",
            chunk_duration=300
        )

    def test_split_media_node_custom_chunk_size(self, base_state):
        """Test media splitting with custom chunk size"""
        base_state["settings"]["chunk_size"] = 600  # 10 minutes
        
        with patch('src.workflows.nodes.split_media.AudioProcessor') as mock_audio_processor_class:
            mock_processor = Mock()
            mock_audio_processor_class.return_value = mock_processor
            mock_processor.split_audio_into_chunks.return_value = ["/temp/chunk_001.wav"]
            
            result = split_media_node(base_state)
            
            mock_processor.split_audio_into_chunks.assert_called_once_with(
                "/test/audio.wav",
                chunk_duration=600
            )

    def test_split_media_node_default_chunk_size(self, base_state):
        """Test media splitting with default chunk size when not specified"""
        # Remove chunk_size from settings
        del base_state["settings"]["chunk_size"]
        
        with patch('src.workflows.nodes.split_media.AudioProcessor') as mock_audio_processor_class:
            mock_processor = Mock()
            mock_audio_processor_class.return_value = mock_processor
            mock_processor.split_audio_into_chunks.return_value = ["/temp/chunk_001.wav"]
            
            result = split_media_node(base_state)
            
            # Should use default chunk size of 600 seconds
            mock_processor.split_audio_into_chunks.assert_called_once_with(
                "/test/audio.wav",
                chunk_duration=600
            )

    @patch('src.workflows.nodes.split_media.AudioProcessor')
    def test_split_media_node_audio_processor_error(self, mock_audio_processor_class, base_state):
        """Test handling of AudioProcessor errors"""
        mock_processor = Mock()
        mock_audio_processor_class.return_value = mock_processor
        mock_processor.split_audio_into_chunks.side_effect = Exception("Audio processing failed")
        
        result = split_media_node(base_state)
        
        assert len(result["errors"]) > 0
        assert "メディア分割エラー" in result["errors"][0]
        assert "Audio processing failed" in result["errors"][0]
        assert "media_chunks" not in result

    @patch('src.workflows.nodes.split_media.VideoProcessor')
    def test_split_media_node_video_processor_error(self, mock_video_processor_class, video_state):
        """Test handling of VideoProcessor errors"""
        mock_processor = Mock()
        mock_video_processor_class.return_value = mock_processor
        mock_processor.split_video_into_chunks.side_effect = Exception("Video processing failed")
        
        result = split_media_node(video_state)
        
        assert len(result["errors"]) > 0
        assert "メディア分割エラー" in result["errors"][0]
        assert "Video processing failed" in result["errors"][0]
        assert "media_chunks" not in result

    @patch('src.workflows.nodes.split_media._convert_audio_to_video')
    @patch('src.workflows.nodes.split_media.VideoProcessor')
    def test_split_media_node_conversion_error(self, mock_video_processor_class, mock_convert, base_state):
        """Test handling of audio to video conversion errors"""
        base_state["force_video_mode"] = True
        mock_convert.side_effect = FileProcessingError("Conversion failed")
        
        result = split_media_node(base_state)
        
        assert len(result["errors"]) > 0
        assert "メディア分割エラー" in result["errors"][0]
        assert "Conversion failed" in result["errors"][0]

    def test_split_media_node_empty_chunks(self, base_state):
        """Test handling when no chunks are produced"""
        with patch('src.workflows.nodes.split_media.AudioProcessor') as mock_audio_processor_class:
            mock_processor = Mock()
            mock_audio_processor_class.return_value = mock_processor
            mock_processor.split_audio_into_chunks.return_value = []
            
            result = split_media_node(base_state)
            
            assert result["media_chunks"] == []
            assert "メディア分割完了: 0個のチャンク" in result["processing_log"]
            assert len(result["errors"]) == 0

    def test_split_media_node_missing_file_path(self, base_state):
        """Test handling when file_path is missing from state"""
        del base_state["file_path"]
        
        result = split_media_node(base_state)
        
        assert len(result["errors"]) > 0
        assert "メディア分割エラー" in result["errors"][0]

    def test_split_media_node_missing_settings(self, base_state):
        """Test handling when settings are missing from state"""
        del base_state["settings"]
        
        with patch('src.workflows.nodes.split_media.AudioProcessor') as mock_audio_processor_class:
            mock_processor = Mock()
            mock_audio_processor_class.return_value = mock_processor
            mock_processor.split_audio_into_chunks.return_value = ["/temp/chunk_001.wav"]
            
            result = split_media_node(base_state)
            
            # Should handle missing settings gracefully and use defaults
            assert len(result["errors"]) > 0  # Will error due to missing settings key


class TestConvertAudioToVideo:
    """Tests for _convert_audio_to_video helper function"""
    
    @pytest.fixture
    def sample_audio_file(self):
        """Create a temporary audio file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(b"fake_audio_data")
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)

    @patch('subprocess.run')
    @patch('tempfile.mkdtemp')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_convert_audio_to_video_success(self, mock_getsize, mock_exists, mock_mkdtemp, mock_run, sample_audio_file):
        """Test successful audio to video conversion"""
        # Mock temporary directory creation
        mock_mkdtemp.return_value = "/tmp/stt_audio_to_video_123"
        
        # Mock file existence and size checks
        mock_exists.return_value = True
        mock_getsize.return_value = 1024  # Non-zero size
        
        # Mock successful subprocess run
        mock_run.return_value = Mock(returncode=0)
        
        result = _convert_audio_to_video(sample_audio_file)
        
        assert result == "/tmp/stt_audio_to_video_123/temp_video.mp4"
        
        # Verify FFmpeg command was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]  # First positional argument (the command)
        assert call_args[0] == "ffmpeg"
        assert "-i" in call_args
        assert sample_audio_file in call_args
        assert "color=black:size=640x480:rate=1" in call_args
        assert "-c:v" in call_args
        assert "libx264" in call_args
        assert "-c:a" in call_args
        assert "aac" in call_args

    @patch('subprocess.run')
    @patch('tempfile.mkdtemp')
    def test_convert_audio_to_video_ffmpeg_error(self, mock_mkdtemp, mock_run, sample_audio_file):
        """Test handling of FFmpeg subprocess errors"""
        mock_mkdtemp.return_value = "/tmp/stt_audio_to_video_123"
        
        # Mock FFmpeg failure
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["ffmpeg"],
            stderr="FFmpeg conversion error"
        )
        
        with pytest.raises(FileProcessingError, match="FFmpeg変換エラー"):
            _convert_audio_to_video(sample_audio_file)

    @patch('subprocess.run')
    @patch('tempfile.mkdtemp')
    @patch('os.path.exists')
    def test_convert_audio_to_video_output_file_missing(self, mock_exists, mock_mkdtemp, mock_run, sample_audio_file):
        """Test handling when output file doesn't exist after conversion"""
        mock_mkdtemp.return_value = "/tmp/stt_audio_to_video_123"
        mock_run.return_value = Mock(returncode=0)
        mock_exists.return_value = False  # Output file doesn't exist
        
        with pytest.raises(FileProcessingError, match="音声から動画への変換に失敗しました"):
            _convert_audio_to_video(sample_audio_file)

    @patch('subprocess.run')
    @patch('tempfile.mkdtemp')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_convert_audio_to_video_empty_output_file(self, mock_getsize, mock_exists, mock_mkdtemp, mock_run, sample_audio_file):
        """Test handling when output file is empty after conversion"""
        mock_mkdtemp.return_value = "/tmp/stt_audio_to_video_123"
        mock_run.return_value = Mock(returncode=0)
        mock_exists.return_value = True
        mock_getsize.return_value = 0  # Empty file
        
        with pytest.raises(FileProcessingError, match="音声から動画への変換に失敗しました"):
            _convert_audio_to_video(sample_audio_file)

    @patch('subprocess.run')
    @patch('tempfile.mkdtemp')
    def test_convert_audio_to_video_general_exception(self, mock_mkdtemp, mock_run, sample_audio_file):
        """Test handling of general exceptions during conversion"""
        mock_mkdtemp.return_value = "/tmp/stt_audio_to_video_123"
        mock_run.side_effect = Exception("Unexpected error")
        
        with pytest.raises(FileProcessingError, match="音声から動画への変換に失敗"):
            _convert_audio_to_video(sample_audio_file)

    @patch('subprocess.run')
    @patch('tempfile.mkdtemp')
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('os.rmdir')
    def test_convert_audio_to_video_cleanup_on_error(self, mock_rmdir, mock_remove, mock_exists, mock_mkdtemp, mock_run, sample_audio_file):
        """Test cleanup of temporary files on error"""
        temp_dir = "/tmp/stt_audio_to_video_123"
        temp_video = "/tmp/stt_audio_to_video_123/temp_video.mp4"
        
        mock_mkdtemp.return_value = temp_dir
        mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd=["ffmpeg"])
        mock_exists.side_effect = lambda path: path in [temp_video, temp_dir]
        
        with pytest.raises(FileProcessingError):
            _convert_audio_to_video(sample_audio_file)
        
        # Verify cleanup was attempted
        mock_remove.assert_called_with(temp_video)
        mock_rmdir.assert_called_with(temp_dir)

    @patch('subprocess.run')
    @patch('tempfile.mkdtemp')
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('os.rmdir')
    def test_convert_audio_to_video_cleanup_error_ignored(self, mock_rmdir, mock_remove, mock_exists, mock_mkdtemp, mock_run, sample_audio_file):
        """Test that cleanup errors are ignored"""
        temp_dir = "/tmp/stt_audio_to_video_123"
        temp_video = "/tmp/stt_audio_to_video_123/temp_video.mp4"
        
        mock_mkdtemp.return_value = temp_dir
        mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd=["ffmpeg"])
        mock_exists.side_effect = lambda path: path in [temp_video, temp_dir]
        
        # Make cleanup operations fail
        mock_remove.side_effect = OSError("Permission denied")
        mock_rmdir.side_effect = OSError("Directory not empty")
        
        # Should still raise the original conversion error, not cleanup errors
        with pytest.raises(FileProcessingError, match="FFmpeg変換エラー"):
            _convert_audio_to_video(sample_audio_file)

    def test_convert_audio_to_video_nonexistent_file(self):
        """Test conversion with non-existent audio file"""
        with pytest.raises(FileProcessingError):
            _convert_audio_to_video("/nonexistent/audio.wav")

    @patch('subprocess.run')
    @patch('tempfile.mkdtemp')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_convert_audio_to_video_command_structure(self, mock_getsize, mock_exists, mock_mkdtemp, mock_run, sample_audio_file):
        """Test that the FFmpeg command is structured correctly"""
        mock_mkdtemp.return_value = "/tmp/test_dir"
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        mock_run.return_value = Mock(returncode=0)
        
        _convert_audio_to_video(sample_audio_file)
        
        # Verify the command structure
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        
        # Check for required FFmpeg parameters
        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd  # Overwrite output files
        assert "-i" in cmd  # Input file
        assert sample_audio_file in cmd
        assert "-f" in cmd and "lavfi" in cmd  # Lavfi filter
        assert "color=black:size=640x480:rate=1" in cmd  # Black background
        assert "-c:v" in cmd and "libx264" in cmd  # Video codec
        assert "-c:a" in cmd and "aac" in cmd  # Audio codec
        assert "-shortest" in cmd  # Stop at shortest stream
        assert "/tmp/test_dir/temp_video.mp4" in cmd  # Output file
        
        # Verify subprocess.run was called with correct parameters
        assert call_args[1]["check"] is True
        assert call_args[1]["capture_output"] is True
        assert call_args[1]["text"] is True