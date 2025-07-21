"""
Tests for video processing functionality.
"""

import pytest
import os
import tempfile
import numpy as np
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
from typing import Dict, Any

import ffmpeg

from src.core.video_processing import VideoProcessor
from src.utils.error_handling import FileProcessingError


class TestVideoProcessor:
    """Tests for VideoProcessor functionality"""
    
    @pytest.fixture
    def video_processor(self):
        """Create VideoProcessor instance"""
        return VideoProcessor()
    
    @pytest.fixture
    def sample_video_file(self):
        """Create a temporary video file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            f.write(b"fake_video_data")
            yield f.name
        os.unlink(f.name)
    
    @pytest.fixture
    def sample_video_metadata(self):
        """Sample video metadata for mocking"""
        return {
            'streams': [
                {
                    'codec_type': 'video',
                    'width': 1920,
                    'height': 1080,
                    'duration': '120.5',
                    'bit_rate': '5000000',
                    'codec_name': 'h264'
                },
                {
                    'codec_type': 'audio',
                    'sample_rate': '44100',
                    'channels': 2,
                    'codec_name': 'aac'
                }
            ],
            'format': {
                'duration': '120.5',
                'size': '75000000',
                'format_name': 'mov,mp4,m4a,3gp,3g2,mj2'
            }
        }

    def test_init(self, video_processor):
        """Test VideoProcessor initialization"""
        assert video_processor is not None
        assert hasattr(video_processor, 'logger')

    @patch('ffmpeg.probe')
    def test_get_video_metadata_success(self, mock_probe, video_processor, sample_video_file, sample_video_metadata):
        """Test successful video metadata extraction"""
        mock_probe.return_value = sample_video_metadata
        
        result = video_processor.get_video_metadata(sample_video_file)
        
        assert result is not None
        assert 'duration' in result
        assert 'width' in result
        assert 'height' in result
        assert 'file_size' in result
        assert result['duration'] == 120.5
        assert result['width'] == 1920
        assert result['height'] == 1080
        mock_probe.assert_called_once_with(sample_video_file)

    @patch('ffmpeg.probe')
    def test_get_video_metadata_file_not_found(self, mock_probe, video_processor):
        """Test metadata extraction with non-existent file"""
        mock_probe.side_effect = ffmpeg.Error('ffprobe', '', 'No such file')
        
        with pytest.raises(FileProcessingError):
            video_processor.get_video_metadata("nonexistent.mp4")

    @patch('ffmpeg.probe')
    def test_get_video_metadata_invalid_format(self, mock_probe, video_processor, sample_video_file):
        """Test metadata extraction with invalid video format"""
        mock_probe.return_value = {'streams': [], 'format': {}}
        
        result = video_processor.get_video_metadata(sample_video_file)
        
        # Should handle missing video stream gracefully
        assert result is not None
        assert result.get('width') is None
        assert result.get('height') is None

    @patch('cv2.VideoCapture')
    def test_analyze_video_brightness_with_opencv(self, mock_cv2_capture, video_processor, sample_video_file):
        """Test video brightness analysis using OpenCV"""
        # Mock OpenCV VideoCapture
        mock_cap = Mock()
        mock_cv2_capture.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 100  # Total frames
        
        # Mock frame reading
        mock_frames = [
            (True, np.ones((480, 640, 3), dtype=np.uint8) * 100),  # Medium brightness
            (True, np.ones((480, 640, 3), dtype=np.uint8) * 200),  # High brightness
            (True, np.ones((480, 640, 3), dtype=np.uint8) * 50),   # Low brightness
            (False, None)  # End of frames
        ]
        mock_cap.read.side_effect = mock_frames
        
        result = video_processor.analyze_video_brightness(sample_video_file, sample_count=3)
        
        assert result is not None
        assert 'average_brightness' in result
        assert 'is_dark' in result
        assert 'brightness_samples' in result
        assert isinstance(result['average_brightness'], float)
        assert isinstance(result['is_dark'], bool)
        mock_cap.release.assert_called_once()

    @patch('cv2.VideoCapture')
    def test_analyze_video_brightness_opencv_unavailable(self, mock_cv2_capture, video_processor, sample_video_file):
        """Test video brightness analysis when OpenCV is unavailable"""
        mock_cv2_capture.side_effect = ImportError("OpenCV not available")
        
        with patch.object(video_processor, '_analyze_brightness_with_ffmpeg') as mock_ffmpeg_analysis:
            mock_ffmpeg_analysis.return_value = {
                'average_brightness': 128.0,
                'is_dark': False,
                'method': 'ffmpeg'
            }
            
            result = video_processor.analyze_video_brightness(sample_video_file)
            
            assert result is not None
            assert result['method'] == 'ffmpeg'
            mock_ffmpeg_analysis.assert_called_once()

    @patch('ffmpeg.input')
    @patch('ffmpeg.run')
    def test_analyze_brightness_with_ffmpeg(self, mock_run, mock_input, video_processor, sample_video_file):
        """Test FFmpeg-based brightness analysis"""
        # Mock FFmpeg pipeline
        mock_stream = Mock()
        mock_input.return_value = mock_stream
        mock_stream.filter.return_value = mock_stream
        mock_stream.output.return_value = mock_stream
        
        # Mock FFmpeg output
        mock_run.return_value = (
            b"frame:0    pts:0       pts_time:0.000000   lavfi.signalstats.YAVG=128.5\n"
            b"frame:1    pts:25      pts_time:1.000000   lavfi.signalstats.YAVG=100.2\n"
            b"frame:2    pts:50      pts_time:2.000000   lavfi.signalstats.YAVG=150.8\n",
            b""
        )
        
        result = video_processor._analyze_brightness_with_ffmpeg(sample_video_file)
        
        assert result is not None
        assert 'average_brightness' in result
        assert 'is_dark' in result
        assert result['average_brightness'] > 0
        assert isinstance(result['is_dark'], bool)

    @patch('ffmpeg.input')
    @patch('ffmpeg.run')
    def test_extract_audio_from_video_success(self, mock_run, mock_input, video_processor, sample_video_file):
        """Test successful audio extraction from video"""
        # Mock FFmpeg pipeline
        mock_stream = Mock()
        mock_input.return_value = mock_stream
        mock_stream.audio = mock_stream
        mock_stream.output.return_value = mock_stream
        mock_run.return_value = None
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
            output_path = temp_audio.name
        
        try:
            result = video_processor.extract_audio_from_video(sample_video_file, output_path)
            
            assert result == output_path
            mock_input.assert_called_once_with(sample_video_file)
            mock_run.assert_called_once()
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    @patch('ffmpeg.input')
    @patch('ffmpeg.run')
    def test_extract_audio_from_video_auto_output(self, mock_run, mock_input, video_processor, sample_video_file):
        """Test audio extraction with automatic output path generation"""
        mock_stream = Mock()
        mock_input.return_value = mock_stream
        mock_stream.audio = mock_stream
        mock_stream.output.return_value = mock_stream
        mock_run.return_value = None
        
        result = video_processor.extract_audio_from_video(sample_video_file)
        
        assert result is not None
        assert result.endswith('.wav')
        assert 'temp_audio_' in result

    @patch('ffmpeg.input')
    @patch('ffmpeg.run')
    def test_extract_audio_from_video_ffmpeg_error(self, mock_run, mock_input, video_processor, sample_video_file):
        """Test audio extraction with FFmpeg error"""
        mock_stream = Mock()
        mock_input.return_value = mock_stream
        mock_stream.audio = mock_stream
        mock_stream.output.return_value = mock_stream
        mock_run.side_effect = ffmpeg.Error('ffmpeg', '', 'Conversion failed')
        
        with pytest.raises(FileProcessingError):
            video_processor.extract_audio_from_video(sample_video_file)

    @patch('ffmpeg.input')
    @patch('ffmpeg.run')
    def test_convert_video_format_success(self, mock_run, mock_input, video_processor, sample_video_file):
        """Test successful video format conversion"""
        mock_stream = Mock()
        mock_input.return_value = mock_stream
        mock_stream.output.return_value = mock_stream
        mock_run.return_value = None
        
        with tempfile.NamedTemporaryFile(suffix='.avi', delete=False) as temp_output:
            output_path = temp_output.name
        
        try:
            result = video_processor.convert_video_format(
                sample_video_file, 
                output_path, 
                target_format="avi",
                video_codec="libx264",
                audio_codec="aac"
            )
            
            assert result == output_path
            mock_input.assert_called_once_with(sample_video_file)
            mock_run.assert_called_once()
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    @patch('ffmpeg.input')
    @patch('ffmpeg.run')
    def test_convert_video_format_with_options(self, mock_run, mock_input, video_processor, sample_video_file):
        """Test video format conversion with custom options"""
        mock_stream = Mock()
        mock_input.return_value = mock_stream
        mock_stream.output.return_value = mock_stream
        mock_run.return_value = None
        
        with tempfile.NamedTemporaryFile(suffix='.mkv', delete=False) as temp_output:
            output_path = temp_output.name
        
        try:
            result = video_processor.convert_video_format(
                sample_video_file,
                output_path,
                target_format="mkv",
                video_codec="libx265",
                audio_codec="flac"
            )
            
            assert result == output_path
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    @patch('ffmpeg.input')
    @patch('ffmpeg.run')
    def test_extract_frames_success(self, mock_run, mock_input, video_processor, sample_video_file):
        """Test successful frame extraction"""
        mock_stream = Mock()
        mock_input.return_value = mock_stream
        mock_stream.filter.return_value = mock_stream
        mock_stream.output.return_value = mock_stream
        mock_run.return_value = None
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = video_processor.extract_frames(
                sample_video_file,
                temp_dir,
                frame_rate=0.5,
                image_format="png"
            )
            
            assert result == temp_dir
            mock_input.assert_called_once_with(sample_video_file)
            mock_run.assert_called_once()

    @patch('ffmpeg.probe')
    def test_get_video_duration_success(self, mock_probe, video_processor, sample_video_file, sample_video_metadata):
        """Test successful video duration extraction"""
        mock_probe.return_value = sample_video_metadata
        
        result = video_processor.get_video_duration(sample_video_file)
        
        assert result == 120.5
        mock_probe.assert_called_once_with(sample_video_file)

    @patch('ffmpeg.probe')
    def test_get_video_duration_no_duration(self, mock_probe, video_processor, sample_video_file):
        """Test video duration extraction when duration is not available"""
        mock_probe.return_value = {'format': {}}
        
        result = video_processor.get_video_duration(sample_video_file)
        
        assert result is None

    @pytest.mark.parametrize("filename,expected", [
        ("video.mp4", True),
        ("video.avi", True),
        ("video.mov", True),
        ("video.mkv", True),
        ("video.wmv", True),
        ("video.flv", True),
        ("video.webm", True),
        ("audio.mp3", False),
        ("document.pdf", False),
        ("image.jpg", False),
        ("", False),
    ])
    def test_is_video_file(self, video_processor, filename, expected):
        """Test video file detection"""
        result = video_processor.is_video_file(filename)
        assert result == expected

    def test_cleanup_temp_files_success(self, video_processor):
        """Test successful cleanup of temporary files"""
        # Create temporary files
        temp_files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(delete=False) as f:
                temp_files.append(f.name)
        
        # Verify files exist
        for file_path in temp_files:
            assert os.path.exists(file_path)
        
        # Cleanup
        video_processor.cleanup_temp_files(temp_files)
        
        # Verify files are deleted
        for file_path in temp_files:
            assert not os.path.exists(file_path)

    def test_cleanup_temp_files_nonexistent(self, video_processor):
        """Test cleanup with non-existent files"""
        nonexistent_files = ["/tmp/nonexistent1.tmp", "/tmp/nonexistent2.tmp"]
        
        # Should not raise an exception
        video_processor.cleanup_temp_files(nonexistent_files)

    def test_cleanup_temp_files_mixed(self, video_processor):
        """Test cleanup with mix of existing and non-existent files"""
        # Create one real temporary file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            real_file = f.name
        
        mixed_files = [real_file, "/tmp/nonexistent.tmp"]
        
        # Should not raise an exception
        video_processor.cleanup_temp_files(mixed_files)
        
        # Real file should be deleted
        assert not os.path.exists(real_file)

    @patch('ffmpeg.probe')
    def test_get_video_metadata_with_multiple_streams(self, mock_probe, video_processor, sample_video_file):
        """Test metadata extraction with multiple video/audio streams"""
        complex_metadata = {
            'streams': [
                {
                    'codec_type': 'video',
                    'width': 1920,
                    'height': 1080,
                    'duration': '120.5',
                    'codec_name': 'h264'
                },
                {
                    'codec_type': 'video',  # Second video stream
                    'width': 640,
                    'height': 480,
                    'duration': '120.5',
                    'codec_name': 'h264'
                },
                {
                    'codec_type': 'audio',
                    'sample_rate': '44100',
                    'channels': 2,
                    'codec_name': 'aac'
                },
                {
                    'codec_type': 'audio',  # Second audio stream
                    'sample_rate': '48000',
                    'channels': 6,
                    'codec_name': 'ac3'
                }
            ],
            'format': {
                'duration': '120.5',
                'size': '75000000'
            }
        }
        mock_probe.return_value = complex_metadata
        
        result = video_processor.get_video_metadata(sample_video_file)
        
        # Should use the first video stream
        assert result['width'] == 1920
        assert result['height'] == 1080
        assert 'audio_streams' in result
        assert len(result['audio_streams']) == 2

    @patch('cv2.VideoCapture')
    def test_analyze_video_brightness_empty_video(self, mock_cv2_capture, video_processor, sample_video_file):
        """Test brightness analysis with empty video"""
        mock_cap = Mock()
        mock_cv2_capture.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 0  # No frames
        mock_cap.read.return_value = (False, None)
        
        result = video_processor.analyze_video_brightness(sample_video_file)
        
        assert result is not None
        assert result['average_brightness'] == 0
        assert result['is_dark'] is True
        mock_cap.release.assert_called_once()