"""
Integration tests for error scenarios and recovery in STT workflow.
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from typing import Dict, Any

from src.workflows.stt_workflow import create_stt_workflow, execute_stt_workflow
from src.workflows.state import STTState, create_initial_state
from src.utils.error_handling import (
    FileProcessingError, 
    APIError, 
    NotionUploadError
)


class TestErrorScenarios:
    """Integration tests for error scenarios and recovery"""
    
    @pytest.fixture
    def sample_audio_file(self):
        """Create a temporary audio file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(b"fake_audio_data")
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

    def test_invalid_file_path_error(self, test_settings):
        """Test workflow with invalid file path"""
        # Create initial state with non-existent file
        initial_state = create_initial_state(
            file_path="/nonexistent/file.wav",
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify error handling
        assert len(result["errors"]) > 0
        assert any("ファイルが見つかりません" in error or "file not found" in error.lower() 
                  for error in result["errors"])
        assert "minutes" not in result or result["minutes"] == ""

    def test_unsupported_file_format_error(self, test_settings):
        """Test workflow with unsupported file format"""
        # Create temporary file with unsupported extension
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b"This is not an audio file")
            unsupported_file = f.name
        
        try:
            # Create initial state
            initial_state = create_initial_state(
                file_path=unsupported_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify error handling
            assert len(result["errors"]) > 0
            assert any("サポートされていない" in error or "unsupported" in error.lower() 
                      for error in result["errors"])
        finally:
            if os.path.exists(unsupported_file):
                os.unlink(unsupported_file)

    def test_corrupted_file_error(self, test_settings):
        """Test workflow with corrupted file"""
        # Create corrupted audio file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(b"corrupted_data_not_valid_audio")
            corrupted_file = f.name
        
        try:
            with patch('src.core.audio_processing.AudioProcessor') as mock_audio:
                # Mock audio processor to raise error for corrupted file
                mock_audio_instance = Mock()
                mock_audio.return_value = mock_audio_instance
                mock_audio_instance.get_audio_info.side_effect = FileProcessingError("Corrupted audio file")
                
                # Create initial state
                initial_state = create_initial_state(
                    file_path=corrupted_file,
                    settings=test_settings
                )
                
                # Execute workflow
                result = execute_stt_workflow(initial_state)
                
                # Verify error handling
                assert len(result["errors"]) > 0
                assert any("Corrupted audio file" in error for error in result["errors"])
        finally:
            if os.path.exists(corrupted_file):
                os.unlink(corrupted_file)

    def test_api_key_missing_error(self, sample_audio_file, test_settings):
        """Test workflow with missing API key"""
        # Remove API key
        del test_settings["gemini_api_key"]
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=sample_audio_file,
            settings=test_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Verify error handling
        assert len(result["errors"]) > 0
        assert any("API" in error and ("キー" in error or "key" in error.lower()) 
                  for error in result["errors"])

    def test_api_service_unavailable_error(self, sample_audio_file, test_settings):
        """Test workflow with API service unavailable"""
        with patch('src.core.ai_services.GeminiService') as mock_gemini:
            # Mock API service to be unavailable
            mock_gemini_instance = Mock()
            mock_gemini.return_value = mock_gemini_instance
            mock_gemini_instance.transcribe_audio.side_effect = APIError("Service unavailable")
            
            # Mock other processors
            with patch('src.core.audio_processing.AudioProcessor') as mock_audio:
                mock_audio_instance = Mock()
                mock_audio.return_value = mock_audio_instance
                mock_audio_instance.get_audio_info.return_value = {
                    "duration": 300,
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
                
                # Verify error handling
                assert len(result["errors"]) > 0
                assert any("Service unavailable" in error for error in result["errors"])

    def test_api_rate_limit_error(self, sample_audio_file, test_settings):
        """Test workflow with API rate limit exceeded"""
        with patch('src.core.ai_services.GeminiService') as mock_gemini:
            # Mock API rate limit error
            mock_gemini_instance = Mock()
            mock_gemini.return_value = mock_gemini_instance
            mock_gemini_instance.transcribe_audio.side_effect = APIError("Rate limit exceeded")
            
            # Mock other processors
            with patch('src.core.audio_processing.AudioProcessor') as mock_audio:
                mock_audio_instance = Mock()
                mock_audio.return_value = mock_audio_instance
                mock_audio_instance.get_audio_info.return_value = {
                    "duration": 300,
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
                
                # Verify error handling
                assert len(result["errors"]) > 0
                assert any("Rate limit" in error for error in result["errors"])

    def test_transcription_quality_too_low_error(self, sample_audio_file, test_settings):
        """Test workflow with transcription quality too low"""
        with patch('src.core.ai_services.GeminiService') as mock_gemini, \
             patch('src.core.audio_processing.AudioProcessor') as mock_audio:
            
            # Mock processors
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.return_value = {
                "duration": 300,
                "sample_rate": 44100,
                "channels": 2
            }
            
            mock_gemini_instance = Mock()
            mock_gemini.return_value = mock_gemini_instance
            mock_gemini_instance.transcribe_audio.return_value = "unclear mumbled speech"
            mock_gemini_instance.check_transcription_quality.return_value = {
                "overall_score": 25,  # Very low quality
                "confidence": 0.2,
                "issues": ["Poor audio quality", "Unclear speech"],
                "recommendations": ["Use better microphone", "Reduce background noise"]
            }
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify quality issues are reported
            assert "quality_check_result" in result
            assert result["quality_check_result"]["overall_score"] == 25
            assert len(result["quality_check_result"]["issues"]) > 0
            
            # Should still generate minutes but with warnings
            assert "minutes" in result
            assert len(result["processing_log"]) > 0

    def test_notion_upload_authentication_error(self, sample_audio_file, test_settings):
        """Test workflow with Notion authentication error"""
        # Enable Notion upload
        test_settings["upload_to_notion"] = True
        
        with patch('src.core.ai_services.GeminiService') as mock_gemini, \
             patch('src.core.audio_processing.AudioProcessor') as mock_audio, \
             patch('src.core.notion_client.NotionClient') as mock_notion:
            
            # Mock successful processing until Notion upload
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.return_value = {
                "duration": 300,
                "sample_rate": 44100,
                "channels": 2
            }
            
            mock_gemini_instance = Mock()
            mock_gemini.return_value = mock_gemini_instance
            mock_gemini_instance.transcribe_audio.return_value = "Test transcription"
            mock_gemini_instance.check_transcription_quality.return_value = {
                "overall_score": 85,
                "confidence": 0.9,
                "issues": [],
                "recommendations": []
            }
            mock_gemini_instance.generate_minutes.return_value = "# Test Minutes"
            
            # Mock Notion authentication error
            mock_notion_instance = Mock()
            mock_notion.return_value = mock_notion_instance
            mock_notion_instance.create_meeting_minutes_page.side_effect = NotionUploadError("Authentication failed")
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify minutes were generated but Notion upload failed
            assert "minutes" in result
            assert result["minutes"] == "# Test Minutes"
            assert len(result["errors"]) > 0
            assert any("Authentication failed" in error for error in result["errors"])

    def test_disk_space_insufficient_error(self, sample_audio_file, test_settings):
        """Test workflow with insufficient disk space"""
        with patch('src.core.audio_processing.AudioProcessor') as mock_audio:
            # Mock disk space error
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.side_effect = FileProcessingError("Insufficient disk space")
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify error handling
            assert len(result["errors"]) > 0
            assert any("disk space" in error.lower() for error in result["errors"])

    def test_network_interruption_error(self, sample_audio_file, test_settings):
        """Test workflow with network interruption during API calls"""
        with patch('src.core.ai_services.GeminiService') as mock_gemini, \
             patch('src.core.audio_processing.AudioProcessor') as mock_audio:
            
            # Mock network interruption
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.return_value = {
                "duration": 300,
                "sample_rate": 44100,
                "channels": 2
            }
            
            mock_gemini_instance = Mock()
            mock_gemini.return_value = mock_gemini_instance
            mock_gemini_instance.transcribe_audio.side_effect = APIError("Network timeout")
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify error handling
            assert len(result["errors"]) > 0
            assert any("Network timeout" in error for error in result["errors"])

    def test_memory_exhaustion_error(self, sample_audio_file, test_settings):
        """Test workflow with memory exhaustion"""
        with patch('src.core.audio_processing.AudioProcessor') as mock_audio:
            # Mock memory exhaustion
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.side_effect = MemoryError("Out of memory")
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify error handling
            assert len(result["errors"]) > 0
            assert any("memory" in error.lower() for error in result["errors"])

    def test_partial_failure_recovery(self, sample_audio_file, test_settings):
        """Test workflow recovery from partial failures"""
        with patch('src.core.ai_services.GeminiService') as mock_gemini, \
             patch('src.core.audio_processing.AudioProcessor') as mock_audio:
            
            # Mock successful audio processing
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.return_value = {
                "duration": 300,
                "sample_rate": 44100,
                "channels": 2
            }
            
            # Mock successful transcription but failed quality check
            mock_gemini_instance = Mock()
            mock_gemini.return_value = mock_gemini_instance
            mock_gemini_instance.transcribe_audio.return_value = "Test transcription"
            mock_gemini_instance.check_transcription_quality.side_effect = APIError("Quality check failed")
            mock_gemini_instance.generate_minutes.return_value = "# Test Minutes"
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify partial success - transcription and minutes should be available
            assert "transcription" in result
            assert result["transcription"] == "Test transcription"
            assert "minutes" in result
            assert result["minutes"] == "# Test Minutes"
            
            # But quality check error should be recorded
            assert len(result["errors"]) > 0
            assert any("Quality check failed" in error for error in result["errors"])

    def test_retry_mechanism_success(self, sample_audio_file, test_settings):
        """Test successful retry after initial failure"""
        with patch('src.core.ai_services.GeminiService') as mock_gemini, \
             patch('src.core.audio_processing.AudioProcessor') as mock_audio:
            
            # Mock audio processing
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.return_value = {
                "duration": 300,
                "sample_rate": 44100,
                "channels": 2
            }
            
            # Mock retry scenario - first call fails, second succeeds
            mock_gemini_instance = Mock()
            mock_gemini.return_value = mock_gemini_instance
            mock_gemini_instance.transcribe_audio.side_effect = [
                APIError("Temporary failure"),
                "Test transcription"  # Success on retry
            ]
            mock_gemini_instance.check_transcription_quality.return_value = {
                "overall_score": 85,
                "confidence": 0.9,
                "issues": [],
                "recommendations": []
            }
            mock_gemini_instance.generate_minutes.return_value = "# Test Minutes"
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify successful completion after retry
            assert "transcription" in result
            assert result["transcription"] == "Test transcription"
            assert "minutes" in result
            assert result["minutes"] == "# Test Minutes"
            assert len(result["errors"]) == 0

    def test_retry_mechanism_exhausted(self, sample_audio_file, test_settings):
        """Test retry mechanism when all retries are exhausted"""
        with patch('src.core.ai_services.GeminiService') as mock_gemini, \
             patch('src.core.audio_processing.AudioProcessor') as mock_audio:
            
            # Mock audio processing
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.return_value = {
                "duration": 300,
                "sample_rate": 44100,
                "channels": 2
            }
            
            # Mock persistent failure
            mock_gemini_instance = Mock()
            mock_gemini.return_value = mock_gemini_instance
            mock_gemini_instance.transcribe_audio.side_effect = APIError("Persistent failure")
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify failure after retries exhausted
            assert len(result["errors"]) > 0
            assert any("Persistent failure" in error for error in result["errors"])
            assert "transcription" not in result or result["transcription"] == ""

    def test_graceful_degradation_ai_unavailable(self, sample_audio_file, test_settings):
        """Test graceful degradation when AI services are unavailable"""
        with patch('src.core.ai_services.GeminiService') as mock_gemini, \
             patch('src.core.audio_processing.AudioProcessor') as mock_audio:
            
            # Mock audio processing
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.return_value = {
                "duration": 300,
                "sample_rate": 44100,
                "channels": 2
            }
            
            # Mock AI service completely unavailable
            mock_gemini.side_effect = Exception("AI service initialization failed")
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify graceful degradation
            assert len(result["errors"]) > 0
            assert any("AI service" in error for error in result["errors"])
            
            # Should still attempt basic processing if possible
            assert "processing_log" in result
            assert len(result["processing_log"]) > 0

    def test_concurrent_error_handling(self, sample_audio_file, test_settings):
        """Test error handling in concurrent processing scenarios"""
        with patch('src.core.ai_services.GeminiService') as mock_gemini, \
             patch('src.core.audio_processing.AudioProcessor') as mock_audio:
            
            # Mock audio processing with multiple chunks
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.return_value = {
                "duration": 1800,  # 30 minutes - triggers splitting
                "sample_rate": 44100,
                "channels": 2
            }
            mock_audio_instance.split_audio_into_chunks.return_value = [
                "/temp/chunk_001.wav",
                "/temp/chunk_002.wav",
                "/temp/chunk_003.wav"
            ]
            
            # Mock mixed success/failure for chunks
            mock_gemini_instance = Mock()
            mock_gemini.return_value = mock_gemini_instance
            mock_gemini_instance.transcribe_audio.side_effect = [
                "First chunk transcription",
                APIError("Second chunk failed"),
                "Third chunk transcription"
            ]
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify partial success handling
            assert len(result["errors"]) > 0
            assert any("Second chunk failed" in error for error in result["errors"])
            
            # Should still have some transcription results
            processing_log = result.get("processing_log", [])
            assert len(processing_log) > 0

    def test_error_logging_and_reporting(self, sample_audio_file, test_settings):
        """Test comprehensive error logging and reporting"""
        with patch('src.core.audio_processing.AudioProcessor') as mock_audio:
            # Mock multiple types of errors
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.side_effect = [
                FileProcessingError("File access error"),
                APIError("API connection error"),
                Exception("Unexpected error")
            ]
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify comprehensive error reporting
            assert len(result["errors"]) > 0
            assert "processing_log" in result
            
            # Check that errors are properly categorized and logged
            errors = result["errors"]
            assert any("error" in error.lower() for error in errors)

    def test_cleanup_after_errors(self, sample_audio_file, test_settings):
        """Test that cleanup occurs properly even after errors"""
        with patch('src.core.audio_processing.AudioProcessor') as mock_audio:
            # Mock error that should trigger cleanup
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.side_effect = FileProcessingError("Processing failed")
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=sample_audio_file,
                settings=test_settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify error was handled
            assert len(result["errors"]) > 0
            assert any("Processing failed" in error for error in result["errors"])
            
            # Verify workflow completed (didn't hang or crash)
            assert "processing_log" in result
            assert isinstance(result["errors"], list)