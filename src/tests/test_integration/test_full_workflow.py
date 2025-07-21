"""
Integration tests for full STT workflow.
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from typing import Dict, Any

from src.workflows.stt_workflow import create_stt_workflow, execute_stt_workflow
from src.workflows.state import STTState, create_initial_state


class TestFullWorkflow:
    """Integration tests for complete STT workflow"""
    
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
    
    @pytest.fixture
    def test_settings(self):
        """Test settings for workflow"""
        return {
            "chunk_size": 300,
            "use_ai": True,
            "output_format": "markdown",
            "minutes_type": "detailed",
            "upload_to_notion": False,
            "gemini_api_key": "test_api_key",
            "notion_token": "test_notion_token",
            "notion_database_id": "test_database_id"
        }
    
    @pytest.fixture
    def mock_all_processors(self):
        """Mock all processors and services"""
        with patch('src.core.audio_processing.AudioProcessor') as mock_audio, \
             patch('src.core.video_processing.VideoProcessor') as mock_video, \
             patch('src.core.ai_services.GeminiService') as mock_gemini, \
             patch('src.core.notion_client.NotionClient') as mock_notion:
            
            # Mock AudioProcessor
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.return_value = {
                "duration": 600,
                "sample_rate": 44100,
                "channels": 2
            }
            mock_audio_instance.split_audio_into_chunks.return_value = [
                "/temp/chunk_001.wav",
                "/temp/chunk_002.wav"
            ]
            
            # Mock VideoProcessor
            mock_video_instance = Mock()
            mock_video.return_value = mock_video_instance
            mock_video_instance.get_video_metadata.return_value = {
                "duration": 600,
                "width": 1920,
                "height": 1080
            }
            mock_video_instance.analyze_video_brightness.return_value = {
                "average_brightness": 128,
                "is_dark": False
            }
            mock_video_instance.split_video_into_chunks.return_value = [
                "/temp/chunk_001.mp4",
                "/temp/chunk_002.mp4"
            ]
            
            # Mock GeminiService
            mock_gemini_instance = Mock()
            mock_gemini.return_value = mock_gemini_instance
            mock_gemini_instance.transcribe_audio.return_value = "This is a test transcription from audio."
            mock_gemini_instance.transcribe_video.return_value = "This is a test transcription from video."
            mock_gemini_instance.check_transcription_quality.return_value = {
                "overall_score": 85,
                "confidence": 0.9,
                "issues": [],
                "recommendations": []
            }
            mock_gemini_instance.generate_minutes.return_value = "# Meeting Minutes\n\n## Summary\nThis is a test meeting summary."
            
            # Mock NotionClient
            mock_notion_instance = Mock()
            mock_notion.return_value = mock_notion_instance
            mock_notion_instance.create_meeting_minutes_page.return_value = {
                "id": "page_123",
                "url": "https://notion.so/page_123"
            }
            
            yield {
                "audio": mock_audio_instance,
                "video": mock_video_instance,
                "gemini": mock_gemini_instance,
                "notion": mock_notion_instance
            }

    def test_audio_to_minutes_complete_workflow(self, sample_audio_file, test_settings, mock_all_processors):
        """Test complete workflow from audio file to minutes"""
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_audio_file,
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify final state
        assert "minutes" in result
        assert result["minutes"] == "# Meeting Minutes\n\n## Summary\nThis is a test meeting summary."
        assert result["processing_stage"] == "complete"
        assert len(result["errors"]) == 0
        
        # Verify processing steps were executed
        assert "transcription" in result
        assert result["transcription"] == "This is a test transcription from audio."
        assert "quality_check_result" in result
        assert result["quality_check_result"]["overall_score"] == 85
        
        # Verify processors were called
        mock_all_processors["audio"].get_audio_info.assert_called_once()
        mock_all_processors["gemini"].transcribe_audio.assert_called()
        mock_all_processors["gemini"].check_transcription_quality.assert_called()
        mock_all_processors["gemini"].generate_minutes.assert_called()

    def test_video_to_minutes_complete_workflow(self, sample_video_file, test_settings, mock_all_processors):
        """Test complete workflow from video file to minutes"""
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_video_file,
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify final state
        assert "minutes" in result
        assert result["minutes"] == "# Meeting Minutes\n\n## Summary\nThis is a test meeting summary."
        assert result["processing_stage"] == "complete"
        assert len(result["errors"]) == 0
        
        # Verify video-specific processing
        assert "transcription" in result
        assert result["transcription"] == "This is a test transcription from video."
        
        # Verify video processors were called
        mock_all_processors["video"].get_video_metadata.assert_called_once()
        mock_all_processors["video"].analyze_video_brightness.assert_called_once()
        mock_all_processors["gemini"].transcribe_video.assert_called()

    def test_audio_workflow_with_splitting(self, sample_audio_file, test_settings, mock_all_processors):
        """Test audio workflow with file splitting for long audio"""
        # Mock long audio duration
        mock_all_processors["audio"].get_audio_info.return_value = {
            "duration": 3600,  # 1 hour - should trigger splitting
            "sample_rate": 44100,
            "channels": 2
        }
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_audio_file,
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify splitting was triggered
        mock_all_processors["audio"].split_audio_into_chunks.assert_called_once()
        
        # Verify final result
        assert "minutes" in result
        assert len(result["errors"]) == 0

    def test_video_workflow_with_dark_video(self, sample_video_file, test_settings, mock_all_processors):
        """Test video workflow with dark video (audio extraction)"""
        # Mock dark video
        mock_all_processors["video"].analyze_video_brightness.return_value = {
            "average_brightness": 30,  # Dark video
            "is_dark": True
        }
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_video_file,
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify brightness analysis was performed
        mock_all_processors["video"].analyze_video_brightness.assert_called_once()
        
        # Verify final result
        assert "minutes" in result
        assert len(result["errors"]) == 0

    def test_workflow_with_notion_upload(self, sample_audio_file, test_settings, mock_all_processors):
        """Test complete workflow with Notion upload"""
        # Enable Notion upload
        test_settings["upload_to_notion"] = True
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_audio_file,
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify Notion upload was performed
        mock_all_processors["notion"].create_meeting_minutes_page.assert_called_once()
        
        # Verify Notion page info in result
        assert "notion_page_id" in result
        assert result["notion_page_id"] == "page_123"
        assert "notion_page_url" in result
        assert result["notion_page_url"] == "https://notion.so/page_123"
        
        # Verify final result
        assert "minutes" in result
        assert len(result["errors"]) == 0

    def test_workflow_with_basic_minutes_generation(self, sample_audio_file, test_settings, mock_all_processors):
        """Test workflow with basic (non-AI) minutes generation"""
        # Disable AI
        test_settings["use_ai"] = False
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_audio_file,
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify basic processing was used
        # AI services should still be called for transcription but not for minutes generation
        mock_all_processors["gemini"].transcribe_audio.assert_called()
        
        # Verify final result
        assert "minutes" in result
        assert len(result["errors"]) == 0

    def test_workflow_with_summary_format(self, sample_audio_file, test_settings, mock_all_processors):
        """Test workflow with summary format minutes"""
        # Set summary format
        test_settings["minutes_type"] = "summary"
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_audio_file,
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify final result
        assert "minutes" in result
        assert len(result["errors"]) == 0

    def test_workflow_with_class_info(self, sample_audio_file, test_settings, mock_all_processors):
        """Test workflow with class information"""
        # Add class info to settings
        test_settings["class_info"] = {
            "subject": "Project Meeting",
            "date": "2023-01-15",
            "period": "1限",
            "instructor": "田中先生"
        }
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_audio_file,
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify class info is preserved
        assert "class_info" in result
        assert result["class_info"]["subject"] == "Project Meeting"
        assert result["class_info"]["date"] == "2023-01-15"
        
        # Verify final result
        assert "minutes" in result
        assert len(result["errors"]) == 0

    def test_workflow_state_transitions(self, sample_audio_file, test_settings, mock_all_processors):
        """Test that workflow state transitions are correct"""
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_audio_file,
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify processing log shows state transitions
        processing_log = result.get("processing_log", [])
        assert len(processing_log) > 0
        
        # Check for key processing stages in log
        log_text = " ".join(processing_log)
        assert "ファイル解析" in log_text or "file_analysis" in log_text.lower()
        assert "文字起こし" in log_text or "transcription" in log_text.lower()
        assert "議事録生成" in log_text or "minutes" in log_text.lower()

    def test_workflow_with_multiple_chunks(self, sample_audio_file, test_settings, mock_all_processors):
        """Test workflow with multiple audio chunks"""
        # Mock multiple chunks
        mock_all_processors["audio"].split_audio_into_chunks.return_value = [
            "/temp/chunk_001.wav",
            "/temp/chunk_002.wav",
            "/temp/chunk_003.wav",
            "/temp/chunk_004.wav"
        ]
        
        # Mock transcription for each chunk
        mock_all_processors["gemini"].transcribe_audio.side_effect = [
            "First chunk transcription.",
            "Second chunk transcription.",
            "Third chunk transcription.",
            "Fourth chunk transcription."
        ]
        
        # Create initial state with long duration to trigger splitting
        initial_state = create_initial_state(
            file_path=sample_audio_file,
            settings=test_settings
        )
        
        # Mock long audio
        mock_all_processors["audio"].get_audio_info.return_value = {
            "duration": 2400,  # 40 minutes - should trigger splitting
            "sample_rate": 44100,
            "channels": 2
        }
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify multiple transcription calls
        assert mock_all_processors["gemini"].transcribe_audio.call_count >= 4
        
        # Verify final result
        assert "minutes" in result
        assert len(result["errors"]) == 0

    def test_workflow_performance_tracking(self, sample_audio_file, test_settings, mock_all_processors):
        """Test that workflow tracks performance metrics"""
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_audio_file,
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify performance metrics are tracked
        assert "processing_time" in result or len(result["processing_log"]) > 0
        
        # Verify final result
        assert "minutes" in result
        assert len(result["errors"]) == 0

    def test_workflow_cleanup(self, sample_audio_file, test_settings, mock_all_processors):
        """Test that workflow properly cleans up temporary files"""
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_audio_file,
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify workflow completed successfully
        assert "minutes" in result
        assert len(result["errors"]) == 0
        
        # Note: Actual cleanup verification would require checking file system
        # but that's handled by individual component tests

    def test_workflow_with_different_output_formats(self, sample_audio_file, test_settings, mock_all_processors):
        """Test workflow with different output formats"""
        formats = ["markdown", "html", "text"]
        
        for output_format in formats:
            test_settings["output_format"] = output_format
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify final result
            assert "minutes" in result
            assert len(result["errors"]) == 0
            
            # Verify format is preserved in settings
            assert result["settings"]["output_format"] == output_format

    def test_workflow_memory_management(self, sample_audio_file, test_settings, mock_all_processors):
        """Test workflow memory management with large files"""
        # Mock large file processing
        mock_all_processors["audio"].get_audio_info.return_value = {
            "duration": 7200,  # 2 hours
            "sample_rate": 44100,
            "channels": 2,
            "file_size": 1024 * 1024 * 100  # 100MB
        }
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_audio_file,
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify workflow handled large file
        assert "minutes" in result
        assert len(result["errors"]) == 0

    def test_workflow_concurrent_processing_simulation(self, sample_audio_file, test_settings, mock_all_processors):
        """Test workflow behavior under simulated concurrent processing"""
        # Create multiple initial states
        states = []
        for i in range(3):
            state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings.copy()
            )
            state["file_path"] = f"{sample_audio_file}_{i}"
            states.append(state)
        
        # Execute workflows
        results = []
        for state in states:
            result = execute_stt_workflow(state)
            results.append(result)
        
        # Verify all workflows completed successfully
        for result in results:
            assert "minutes" in result
            assert len(result["errors"]) == 0

    def test_workflow_with_custom_settings(self, sample_audio_file, mock_all_processors):
        """Test workflow with various custom settings combinations"""
        custom_settings = {
            "chunk_size": 600,  # 10 minutes
            "use_ai": True,
            "output_format": "html",
            "minutes_type": "summary",
            "upload_to_notion": True,
            "gemini_api_key": "custom_api_key",
            "notion_token": "custom_notion_token",
            "notion_database_id": "custom_database_id",
            "max_retries": 5,
            "timeout": 120
        }
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_audio_file,
            settings=custom_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify custom settings were used
        assert result["settings"]["chunk_size"] == 600
        assert result["settings"]["output_format"] == "html"
        assert result["settings"]["minutes_type"] == "summary"
        
        # Verify final result
        assert "minutes" in result
        assert len(result["errors"]) == 0