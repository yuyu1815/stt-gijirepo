"""
Performance tests for large file processing and system limits.
"""

import pytest
import os
import tempfile
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from typing import Dict, Any, List
import psutil

from src.workflows.stt_workflow import create_stt_workflow, execute_stt_workflow
from src.workflows.state import STTState, create_initial_state
from src.core.audio_processing import AudioProcessor
from src.core.video_processing import VideoProcessor
from src.core.ai_services import GeminiService


class TestLargeFileProcessing:
    """Performance tests for large file processing"""
    
    @pytest.fixture
    def large_audio_file(self):
        """Create a simulated large audio file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            # Create a file with simulated large size (1MB of fake data)
            f.write(b"fake_audio_data" * 70000)  # ~1MB
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)
    
    @pytest.fixture
    def very_large_audio_file(self):
        """Create a simulated very large audio file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            # Create a file with simulated very large size (10MB of fake data)
            f.write(b"fake_audio_data" * 700000)  # ~10MB
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)
    
    @pytest.fixture
    def performance_settings(self):
        """Performance test settings"""
        return {
            "chunk_size": 600,  # 10 minutes
            "use_ai": True,
            "output_format": "markdown",
            "minutes_type": "detailed",
            "upload_to_notion": False,
            "gemini_api_key": "test_api_key",
            "max_retries": 3,
            "timeout": 300  # 5 minutes
        }
    
    @pytest.fixture
    def mock_processors_for_performance(self):
        """Mock processors optimized for performance testing"""
        with patch('src.core.audio_processing.AudioProcessor') as mock_audio, \
             patch('src.core.video_processing.VideoProcessor') as mock_video, \
             patch('src.core.ai_services.GeminiService') as mock_gemini:
            
            # Mock AudioProcessor with realistic large file behavior
            mock_audio_instance = Mock()
            mock_audio.return_value = mock_audio_instance
            mock_audio_instance.get_audio_info.return_value = {
                "duration": 7200,  # 2 hours
                "sample_rate": 44100,
                "channels": 2,
                "file_size": 1024 * 1024 * 100  # 100MB
            }
            mock_audio_instance.split_audio_into_chunks.return_value = [
                f"/temp/chunk_{i:03d}.wav" for i in range(1, 25)  # 24 chunks
            ]
            
            # Mock VideoProcessor
            mock_video_instance = Mock()
            mock_video.return_value = mock_video_instance
            mock_video_instance.get_video_metadata.return_value = {
                "duration": 7200,
                "width": 1920,
                "height": 1080,
                "file_size": 1024 * 1024 * 500  # 500MB
            }
            
            # Mock GeminiService with simulated processing delays
            mock_gemini_instance = Mock()
            mock_gemini.return_value = mock_gemini_instance
            
            def mock_transcribe_with_delay(*args, **kwargs):
                time.sleep(0.1)  # Simulate processing time
                return f"Transcription for chunk {len(args)}"
            
            mock_gemini_instance.transcribe_audio.side_effect = mock_transcribe_with_delay
            mock_gemini_instance.check_transcription_quality.return_value = {
                "overall_score": 85,
                "confidence": 0.9,
                "issues": [],
                "recommendations": []
            }
            mock_gemini_instance.generate_minutes.return_value = "# Large File Meeting Minutes\n\n## Summary\nProcessed large file successfully."
            
            yield {
                "audio": mock_audio_instance,
                "video": mock_video_instance,
                "gemini": mock_gemini_instance
            }

    @pytest.mark.slow
    def test_large_audio_file_processing(self, large_audio_file, performance_settings, mock_processors_for_performance):
        """Test processing of large audio files"""
        start_time = time.time()
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=large_audio_file,
            settings=performance_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Verify successful processing
        assert "minutes" in result
        assert len(result["errors"]) == 0
        
        # Verify performance metrics
        assert processing_time < 60  # Should complete within 1 minute for mocked processing
        
        # Verify chunking was used for large file
        mock_processors_for_performance["audio"].split_audio_into_chunks.assert_called_once()
        
        # Log performance metrics
        print(f"Large file processing time: {processing_time:.2f} seconds")

    @pytest.mark.slow
    def test_very_large_audio_file_processing(self, very_large_audio_file, performance_settings, mock_processors_for_performance):
        """Test processing of very large audio files"""
        start_time = time.time()
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=very_large_audio_file,
            settings=performance_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Verify successful processing
        assert "minutes" in result
        assert len(result["errors"]) == 0
        
        # Verify performance is reasonable even for very large files
        assert processing_time < 120  # Should complete within 2 minutes for mocked processing
        
        # Log performance metrics
        print(f"Very large file processing time: {processing_time:.2f} seconds")

    def test_memory_usage_monitoring(self, large_audio_file, performance_settings, mock_processors_for_performance):
        """Test memory usage during large file processing"""
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=large_audio_file,
            settings=performance_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Verify successful processing
        assert "minutes" in result
        assert len(result["errors"]) == 0
        
        # Verify memory usage is reasonable (should not increase by more than 100MB)
        assert memory_increase < 100, f"Memory increased by {memory_increase:.2f} MB"
        
        # Log memory metrics
        print(f"Memory usage - Initial: {initial_memory:.2f} MB, Final: {final_memory:.2f} MB, Increase: {memory_increase:.2f} MB")

    def test_concurrent_processing_limits(self, large_audio_file, performance_settings, mock_processors_for_performance):
        """Test concurrent processing limits"""
        num_concurrent = 3
        results = []
        threads = []
        start_time = time.time()
        
        def process_file(file_path, settings):
            initial_state = create_initial_state(
                file_path=file_path,
                settings=settings.copy()
            )
            result = execute_stt_workflow(initial_state)
            results.append(result)
        
        # Start concurrent processing
        for i in range(num_concurrent):
            thread = threading.Thread(
                target=process_file,
                args=(large_audio_file, performance_settings)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=120)  # 2 minute timeout per thread
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify all processing completed successfully
        assert len(results) == num_concurrent
        for result in results:
            assert "minutes" in result
            assert len(result["errors"]) == 0
        
        # Verify concurrent processing is efficient
        assert total_time < 180  # Should complete within 3 minutes for mocked processing
        
        # Log performance metrics
        print(f"Concurrent processing ({num_concurrent} files) time: {total_time:.2f} seconds")

    def test_chunk_processing_performance(self, large_audio_file, performance_settings, mock_processors_for_performance):
        """Test performance of chunk-based processing"""
        # Mock many chunks to test chunk processing performance
        mock_processors_for_performance["audio"].split_audio_into_chunks.return_value = [
            f"/temp/chunk_{i:03d}.wav" for i in range(1, 51)  # 50 chunks
        ]
        
        start_time = time.time()
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=large_audio_file,
            settings=performance_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Verify successful processing
        assert "minutes" in result
        assert len(result["errors"]) == 0
        
        # Verify chunk processing performance
        chunks_processed = mock_processors_for_performance["gemini"].transcribe_audio.call_count
        assert chunks_processed > 0
        
        avg_time_per_chunk = processing_time / chunks_processed if chunks_processed > 0 else 0
        
        # Should process chunks efficiently
        assert avg_time_per_chunk < 1.0  # Less than 1 second per chunk on average
        
        # Log performance metrics
        print(f"Chunk processing - Total time: {processing_time:.2f}s, Chunks: {chunks_processed}, Avg per chunk: {avg_time_per_chunk:.3f}s")

    def test_disk_space_usage_monitoring(self, large_audio_file, performance_settings, mock_processors_for_performance):
        """Test disk space usage during processing"""
        # Get initial disk usage
        disk_usage_before = psutil.disk_usage(tempfile.gettempdir())
        free_space_before = disk_usage_before.free / 1024 / 1024  # MB
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=large_audio_file,
            settings=performance_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        # Get final disk usage
        disk_usage_after = psutil.disk_usage(tempfile.gettempdir())
        free_space_after = disk_usage_after.free / 1024 / 1024  # MB
        space_used = free_space_before - free_space_after
        
        # Verify successful processing
        assert "minutes" in result
        assert len(result["errors"]) == 0
        
        # Verify reasonable disk space usage
        assert space_used < 1000, f"Used {space_used:.2f} MB of disk space"
        
        # Log disk usage metrics
        print(f"Disk space usage - Before: {free_space_before:.2f} MB, After: {free_space_after:.2f} MB, Used: {space_used:.2f} MB")

    @pytest.mark.slow
    def test_long_duration_audio_processing(self, large_audio_file, performance_settings, mock_processors_for_performance):
        """Test processing of very long duration audio"""
        # Mock very long audio (4 hours)
        mock_processors_for_performance["audio"].get_audio_info.return_value = {
            "duration": 14400,  # 4 hours
            "sample_rate": 44100,
            "channels": 2,
            "file_size": 1024 * 1024 * 200  # 200MB
        }
        
        # Should create many chunks for very long audio
        mock_processors_for_performance["audio"].split_audio_into_chunks.return_value = [
            f"/temp/chunk_{i:03d}.wav" for i in range(1, 49)  # 48 chunks (5 min each)
        ]
        
        start_time = time.time()
        
        # Create initial state
        initial_state = create_initial_state(
            file_path=large_audio_file,
            settings=performance_settings
        )
        
        # Execute workflow
        result = execute_stt_workflow(initial_state)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Verify successful processing
        assert "minutes" in result
        assert len(result["errors"]) == 0
        
        # Verify chunking was used appropriately
        mock_processors_for_performance["audio"].split_audio_into_chunks.assert_called_once()
        
        # Log performance metrics
        print(f"Long duration audio processing time: {processing_time:.2f} seconds")

    def test_performance_with_different_chunk_sizes(self, large_audio_file, mock_processors_for_performance):
        """Test performance impact of different chunk sizes"""
        chunk_sizes = [300, 600, 900]  # 5, 10, 15 minutes
        performance_results = []
        
        for chunk_size in chunk_sizes:
            settings = {
                "chunk_size": chunk_size,
                "use_ai": True,
                "output_format": "markdown",
                "minutes_type": "detailed",
                "upload_to_notion": False,
                "gemini_api_key": "test_api_key"
            }
            
            # Adjust number of chunks based on chunk size
            num_chunks = max(1, 24 * 300 // chunk_size)  # Proportional to chunk size
            mock_processors_for_performance["audio"].split_audio_into_chunks.return_value = [
                f"/temp/chunk_{i:03d}.wav" for i in range(1, num_chunks + 1)
            ]
            
            start_time = time.time()
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=large_audio_file,
                settings=settings
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Verify successful processing
            assert "minutes" in result
            assert len(result["errors"]) == 0
            
            performance_results.append({
                "chunk_size": chunk_size,
                "processing_time": processing_time,
                "num_chunks": num_chunks
            })
            
            # Reset mock call count
            mock_processors_for_performance["gemini"].transcribe_audio.reset_mock()
        
        # Log performance comparison
        for result in performance_results:
            print(f"Chunk size: {result['chunk_size']}s, Time: {result['processing_time']:.2f}s, Chunks: {result['num_chunks']}")
        
        # Verify all chunk sizes work
        assert len(performance_results) == len(chunk_sizes)

    def test_memory_leak_detection(self, large_audio_file, performance_settings, mock_processors_for_performance):
        """Test for memory leaks during repeated processing"""
        process = psutil.Process()
        memory_readings = []
        
        # Process the same file multiple times
        for i in range(5):
            # Get memory before processing
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Create initial state
            initial_state = create_initial_state(
                file_path=large_audio_file,
                settings=performance_settings.copy()
            )
            
            # Execute workflow
            result = execute_stt_workflow(initial_state)
            
            # Verify successful processing
            assert "minutes" in result
            assert len(result["errors"]) == 0
            
            # Get memory after processing
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_readings.append({
                "iteration": i + 1,
                "memory_before": memory_before,
                "memory_after": memory_after,
                "memory_increase": memory_after - memory_before
            })
            
            # Reset mocks for next iteration
            mock_processors_for_performance["gemini"].transcribe_audio.reset_mock()
        
        # Analyze memory usage pattern
        total_increase = memory_readings[-1]["memory_after"] - memory_readings[0]["memory_before"]
        avg_increase_per_iteration = sum(r["memory_increase"] for r in memory_readings) / len(memory_readings)
        
        # Log memory usage pattern
        for reading in memory_readings:
            print(f"Iteration {reading['iteration']}: {reading['memory_before']:.2f} MB -> {reading['memory_after']:.2f} MB (+{reading['memory_increase']:.2f} MB)")
        
        print(f"Total memory increase: {total_increase:.2f} MB")
        print(f"Average increase per iteration: {avg_increase_per_iteration:.2f} MB")
        
        # Verify no significant memory leaks (total increase should be reasonable)
        assert total_increase < 50, f"Potential memory leak detected: {total_increase:.2f} MB increase"
        assert avg_increase_per_iteration < 10, f"High average memory increase: {avg_increase_per_iteration:.2f} MB per iteration"

    def test_cpu_usage_monitoring(self, large_audio_file, performance_settings, mock_processors_for_performance):
        """Test CPU usage during processing"""
        # Monitor CPU usage during processing
        cpu_readings = []
        
        def monitor_cpu():
            for _ in range(10):  # Monitor for 10 seconds
                cpu_percent = psutil.cpu_percent(interval=1)
                cpu_readings.append(cpu_percent)
        
        # Start CPU monitoring in background
        import threading
        monitor_thread = threading.Thread(target=monitor_cpu)
        monitor_thread.start()
        
        # Create initial state and execute workflow
        initial_state = create_initial_state(
            file_path=large_audio_file,
            settings=performance_settings
        )
        
        result = execute_stt_workflow(initial_state)
        
        # Wait for monitoring to complete
        monitor_thread.join()
        
        # Verify successful processing
        assert "minutes" in result
        assert len(result["errors"]) == 0
        
        # Analyze CPU usage
        if cpu_readings:
            avg_cpu = sum(cpu_readings) / len(cpu_readings)
            max_cpu = max(cpu_readings)
            
            print(f"CPU usage - Average: {avg_cpu:.1f}%, Max: {max_cpu:.1f}%")
            
            # Verify reasonable CPU usage (should not max out CPU)
            assert avg_cpu < 80, f"High average CPU usage: {avg_cpu:.1f}%"

    @pytest.mark.slow
    def test_stress_test_multiple_large_files(self, performance_settings, mock_processors_for_performance):
        """Stress test with multiple large files processed sequentially"""
        num_files = 5
        file_sizes = [1024 * 1024 * i for i in range(1, num_files + 1)]  # 1MB to 5MB
        
        total_start_time = time.time()
        results = []
        
        for i, file_size in enumerate(file_sizes):
            # Create temporary file of specified size
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                f.write(b"fake_audio_data" * (file_size // 15))  # Approximate size
                temp_file = f.name
            
            try:
                start_time = time.time()
                
                # Create initial state
                initial_state = create_initial_state(
                    file_path=temp_file,
                    settings=performance_settings.copy()
                )
                
                # Execute workflow
                result = execute_stt_workflow(initial_state)
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                # Verify successful processing
                assert "minutes" in result
                assert len(result["errors"]) == 0
                
                results.append({
                    "file_index": i + 1,
                    "file_size_mb": file_size / 1024 / 1024,
                    "processing_time": processing_time
                })
                
                # Reset mocks for next file
                mock_processors_for_performance["gemini"].transcribe_audio.reset_mock()
                
            finally:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
        
        total_end_time = time.time()
        total_time = total_end_time - total_start_time
        
        # Log stress test results
        print(f"Stress test results ({num_files} files):")
        for result in results:
            print(f"  File {result['file_index']} ({result['file_size_mb']:.1f} MB): {result['processing_time']:.2f}s")
        print(f"Total time: {total_time:.2f}s")
        
        # Verify all files processed successfully
        assert len(results) == num_files
        
        # Verify reasonable total processing time
        assert total_time < 300, f"Stress test took too long: {total_time:.2f}s"