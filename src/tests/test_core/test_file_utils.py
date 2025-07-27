"""
Tests for file utilities functionality.
"""

import pytest
import os
import shutil
import tempfile
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from src.core.file_utils import FileUtils
from src.utils.error_handling import FileProcessingError


class TestFileUtils:
    """Tests for FileUtils functionality"""
    
    @pytest.fixture
    def file_utils(self):
        """Create FileUtils instance"""
        return FileUtils()
    
    @pytest.fixture
    def sample_text_file(self):
        """Create a temporary text file for testing"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is a test file.\nIt has multiple lines.\nFor testing purposes.")
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)
    
    @pytest.fixture
    def sample_binary_file(self):
        """Create a temporary binary file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
            f.write(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09')
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)
    
    @pytest.fixture
    def temp_directory(self):
        """Create a temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    def test_init(self, file_utils):
        """Test FileUtils initialization"""
        assert file_utils is not None
        assert hasattr(file_utils, 'logger')
        assert hasattr(file_utils, 'temp_files')
        assert isinstance(file_utils.temp_files, list)

    def test_validate_file_success(self, file_utils, sample_text_file):
        """Test successful file validation"""
        result = file_utils.validate_file(sample_text_file)
        
        assert isinstance(result, dict)
        assert result['is_valid'] is True

    def test_validate_file_nonexistent(self, file_utils):
        """Test file validation with non-existent file"""
        with pytest.raises(FileProcessingError, match="File does not exist"):
            file_utils.validate_file("/nonexistent/file.txt")

    def test_validate_file_directory(self, file_utils, temp_directory):
        """Test file validation with directory instead of file"""
        with pytest.raises(FileProcessingError, match="Path is not a file"):
            file_utils.validate_file(temp_directory)

    @patch('os.access')
    def test_validate_file_no_read_permission(self, mock_access, file_utils, sample_text_file):
        """Test file validation without read permission"""
        mock_access.return_value = False
        
        with pytest.raises(FileProcessingError, match="File is not readable"):
            file_utils.validate_file(sample_text_file)

    def test_validate_file_with_max_size(self, file_utils, sample_text_file):
        """Test file validation with size limit"""
        # Should pass with large max_size
        result = file_utils.validate_file(sample_text_file, max_size_mb=1)
        assert result is True
        
        # Should fail with very small max_size
        with pytest.raises(FileProcessingError, match="File size exceeds maximum"):
            file_utils.validate_file(sample_text_file, max_size_mb=0.000001)

    def test_validate_file_with_allowed_extensions(self, file_utils, sample_text_file):
        """Test file validation with allowed extensions"""
        # Should pass with correct extension
        result = file_utils.validate_file(sample_text_file, allowed_extensions=['.txt', '.md'])
        assert result is True
        
        # Should fail with wrong extension
        with pytest.raises(FileProcessingError, match="File extension not allowed"):
            file_utils.validate_file(sample_text_file, allowed_extensions=['.pdf', '.doc'])

    def test_get_file_info_success(self, file_utils, sample_text_file):
        """Test successful file info retrieval"""
        result = file_utils.get_file_info(sample_text_file)
        
        assert isinstance(result, dict)
        assert 'size' in result
        assert 'modified_time' in result
        assert 'created_time' in result
        assert 'extension' in result
        assert 'mime_type' in result
        assert 'is_binary' in result
        
        assert result['size'] > 0
        assert result['extension'] == '.txt'
        assert result['is_binary'] is False

    def test_get_file_info_binary_file(self, file_utils, sample_binary_file):
        """Test file info retrieval for binary file"""
        result = file_utils.get_file_info(sample_binary_file)
        
        assert result['is_binary'] is True
        assert result['extension'] == '.bin'

    def test_get_file_info_nonexistent(self, file_utils):
        """Test file info retrieval for non-existent file"""
        with pytest.raises(FileProcessingError):
            file_utils.get_file_info("/nonexistent/file.txt")

    @pytest.mark.parametrize("algorithm,expected_length", [
        ('md5', 32),
        ('sha1', 40),
        ('sha256', 64),
    ])
    def test_calculate_file_hash(self, file_utils, sample_text_file, algorithm, expected_length):
        """Test file hash calculation with different algorithms"""
        result = file_utils.calculate_file_hash(sample_text_file, algorithm)
        
        assert isinstance(result, str)
        assert len(result) == expected_length
        assert all(c in '0123456789abcdef' for c in result)

    def test_calculate_file_hash_consistency(self, file_utils, sample_text_file):
        """Test that hash calculation is consistent"""
        hash1 = file_utils.calculate_file_hash(sample_text_file, 'md5')
        hash2 = file_utils.calculate_file_hash(sample_text_file, 'md5')
        
        assert hash1 == hash2

    def test_calculate_file_hash_different_content(self, file_utils):
        """Test that different files produce different hashes"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f1:
            f1.write("Content 1")
            file1 = f1.name
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f2:
            f2.write("Content 2")
            file2 = f2.name
        
        try:
            hash1 = file_utils.calculate_file_hash(file1, 'md5')
            hash2 = file_utils.calculate_file_hash(file2, 'md5')
            
            assert hash1 != hash2
        finally:
            os.unlink(file1)
            os.unlink(file2)

    def test_calculate_file_hash_invalid_algorithm(self, file_utils, sample_text_file):
        """Test file hash calculation with invalid algorithm"""
        with pytest.raises(FileProcessingError, match="Unsupported hash algorithm"):
            file_utils.calculate_file_hash(sample_text_file, 'invalid_algorithm')

    def test_create_temp_file_default(self, file_utils):
        """Test temporary file creation with default parameters"""
        temp_file = file_utils.create_temp_file()
        
        assert os.path.exists(temp_file)
        assert temp_file.startswith(tempfile.gettempdir())
        assert 'stt_' in os.path.basename(temp_file)
        assert temp_file in file_utils.temp_files
        
        # Cleanup
        os.unlink(temp_file)

    def test_create_temp_file_custom_params(self, file_utils, temp_directory):
        """Test temporary file creation with custom parameters"""
        temp_file = file_utils.create_temp_file(
            suffix='.test',
            prefix='custom_',
            dir=temp_directory
        )
        
        assert os.path.exists(temp_file)
        assert temp_file.startswith(temp_directory)
        assert temp_file.endswith('.test')
        assert 'custom_' in os.path.basename(temp_file)

    def test_create_temp_directory_default(self, file_utils):
        """Test temporary directory creation with default parameters"""
        temp_dir = file_utils.create_temp_directory()
        
        assert os.path.exists(temp_dir)
        assert os.path.isdir(temp_dir)
        assert temp_dir.startswith(tempfile.gettempdir())
        assert 'stt_' in os.path.basename(temp_dir)
        assert temp_dir in file_utils.temp_files
        
        # Cleanup
        shutil.rmtree(temp_dir)

    def test_create_temp_directory_custom_params(self, file_utils, temp_directory):
        """Test temporary directory creation with custom parameters"""
        temp_dir = file_utils.create_temp_directory(
            prefix='test_dir_',
            dir=temp_directory
        )
        
        assert os.path.exists(temp_dir)
        assert os.path.isdir(temp_dir)
        assert temp_dir.startswith(temp_directory)
        assert 'test_dir_' in os.path.basename(temp_dir)

    def test_copy_file_success(self, file_utils, sample_text_file, temp_directory):
        """Test successful file copying"""
        dst_path = os.path.join(temp_directory, 'copied_file.txt')
        
        result = file_utils.copy_file(sample_text_file, dst_path)
        
        assert result == dst_path
        assert os.path.exists(dst_path)
        
        # Verify content is the same
        with open(sample_text_file, 'r') as f1, open(dst_path, 'r') as f2:
            assert f1.read() == f2.read()

    def test_copy_file_overwrite_false(self, file_utils, sample_text_file, temp_directory):
        """Test file copying without overwrite when destination exists"""
        dst_path = os.path.join(temp_directory, 'existing_file.txt')
        
        # Create existing file
        with open(dst_path, 'w') as f:
            f.write("Existing content")
        
        with pytest.raises(FileProcessingError, match="Destination file already exists"):
            file_utils.copy_file(sample_text_file, dst_path, overwrite=False)

    def test_copy_file_overwrite_true(self, file_utils, sample_text_file, temp_directory):
        """Test file copying with overwrite when destination exists"""
        dst_path = os.path.join(temp_directory, 'existing_file.txt')
        
        # Create existing file
        with open(dst_path, 'w') as f:
            f.write("Existing content")
        
        result = file_utils.copy_file(sample_text_file, dst_path, overwrite=True)
        
        assert result == dst_path
        assert os.path.exists(dst_path)
        
        # Verify content was overwritten
        with open(sample_text_file, 'r') as f1, open(dst_path, 'r') as f2:
            assert f1.read() == f2.read()

    def test_copy_file_nonexistent_source(self, file_utils, temp_directory):
        """Test file copying with non-existent source"""
        dst_path = os.path.join(temp_directory, 'destination.txt')
        
        with pytest.raises(FileProcessingError, match="Source file does not exist"):
            file_utils.copy_file("/nonexistent/file.txt", dst_path)

    def test_move_file_success(self, file_utils, temp_directory):
        """Test successful file moving"""
        # Create source file
        src_path = os.path.join(temp_directory, 'source.txt')
        with open(src_path, 'w') as f:
            f.write("Test content")
        
        dst_path = os.path.join(temp_directory, 'moved_file.txt')
        
        result = file_utils.move_file(src_path, dst_path)
        
        assert result == dst_path
        assert not os.path.exists(src_path)
        assert os.path.exists(dst_path)
        
        # Verify content
        with open(dst_path, 'r') as f:
            assert f.read() == "Test content"

    def test_move_file_overwrite_false(self, file_utils, temp_directory):
        """Test file moving without overwrite when destination exists"""
        # Create source file
        src_path = os.path.join(temp_directory, 'source.txt')
        with open(src_path, 'w') as f:
            f.write("Source content")
        
        # Create destination file
        dst_path = os.path.join(temp_directory, 'destination.txt')
        with open(dst_path, 'w') as f:
            f.write("Destination content")
        
        with pytest.raises(FileProcessingError, match="Destination file already exists"):
            file_utils.move_file(src_path, dst_path, overwrite=False)

    def test_delete_file_success(self, file_utils, temp_directory):
        """Test successful file deletion"""
        # Create file to delete
        file_path = os.path.join(temp_directory, 'to_delete.txt')
        with open(file_path, 'w') as f:
            f.write("Delete me")
        
        assert os.path.exists(file_path)
        
        result = file_utils.delete_file(file_path)
        
        assert result is True
        assert not os.path.exists(file_path)

    def test_delete_file_nonexistent_ignore_errors(self, file_utils):
        """Test file deletion with non-existent file and ignore_errors=True"""
        result = file_utils.delete_file("/nonexistent/file.txt", ignore_errors=True)
        
        assert result is False

    def test_delete_file_nonexistent_raise_errors(self, file_utils):
        """Test file deletion with non-existent file and ignore_errors=False"""
        with pytest.raises(FileProcessingError):
            file_utils.delete_file("/nonexistent/file.txt", ignore_errors=False)

    def test_ensure_directory_new(self, file_utils, temp_directory):
        """Test directory creation for new directory"""
        new_dir = os.path.join(temp_directory, 'new_directory')
        
        assert not os.path.exists(new_dir)
        
        result = file_utils.ensure_directory(new_dir)
        
        assert result == new_dir
        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)

    def test_ensure_directory_existing(self, file_utils, temp_directory):
        """Test directory creation for existing directory"""
        result = file_utils.ensure_directory(temp_directory)
        
        assert result == temp_directory
        assert os.path.exists(temp_directory)
        assert os.path.isdir(temp_directory)

    def test_ensure_directory_nested(self, file_utils, temp_directory):
        """Test nested directory creation"""
        nested_dir = os.path.join(temp_directory, 'level1', 'level2', 'level3')
        
        assert not os.path.exists(nested_dir)
        
        result = file_utils.ensure_directory(nested_dir)
        
        assert result == nested_dir
        assert os.path.exists(nested_dir)
        assert os.path.isdir(nested_dir)

    def test_get_available_filename_no_conflict(self, file_utils, temp_directory):
        """Test available filename generation with no conflict"""
        file_path = os.path.join(temp_directory, 'new_file.txt')
        
        result = file_utils.get_available_filename(file_path)
        
        assert result == file_path

    def test_get_available_filename_with_conflict(self, file_utils, temp_directory):
        """Test available filename generation with conflict"""
        file_path = os.path.join(temp_directory, 'existing_file.txt')
        
        # Create existing file
        with open(file_path, 'w') as f:
            f.write("Existing")
        
        result = file_utils.get_available_filename(file_path)
        
        assert result != file_path
        assert 'existing_file' in result
        assert result.endswith('.txt')
        assert not os.path.exists(result)

    def test_get_available_filename_multiple_conflicts(self, file_utils, temp_directory):
        """Test available filename generation with multiple conflicts"""
        base_path = os.path.join(temp_directory, 'file.txt')
        
        # Create multiple conflicting files
        for i in range(3):
            if i == 0:
                conflict_path = base_path
            else:
                name, ext = os.path.splitext(base_path)
                conflict_path = f"{name}_{i}{ext}"
            
            with open(conflict_path, 'w') as f:
                f.write(f"Content {i}")
        
        result = file_utils.get_available_filename(base_path)
        
        assert result != base_path
        assert not os.path.exists(result)
        assert result.endswith('.txt')

    @patch('shutil.disk_usage')
    def test_get_disk_usage_success(self, mock_disk_usage, file_utils, temp_directory):
        """Test successful disk usage retrieval"""
        mock_disk_usage.return_value = (1000000000, 500000000, 500000000)  # total, used, free
        
        result = file_utils.get_disk_usage(temp_directory)
        
        assert isinstance(result, dict)
        assert 'total' in result
        assert 'used' in result
        assert 'free' in result
        assert 'percent_used' in result
        
        assert result['total'] == 1000000000
        assert result['used'] == 500000000
        assert result['free'] == 500000000
        assert result['percent_used'] == 50.0

    @patch('shutil.disk_usage')
    def test_get_disk_usage_error(self, mock_disk_usage, file_utils):
        """Test disk usage retrieval with error"""
        mock_disk_usage.side_effect = OSError("Permission denied")
        
        with pytest.raises(FileProcessingError):
            file_utils.get_disk_usage("/invalid/path")

    def test_cleanup_temp_files(self, file_utils):
        """Test cleanup of temporary files"""
        # Create some temporary files
        temp_file1 = file_utils.create_temp_file()
        temp_file2 = file_utils.create_temp_file()
        temp_dir = file_utils.create_temp_directory()
        
        assert os.path.exists(temp_file1)
        assert os.path.exists(temp_file2)
        assert os.path.exists(temp_dir)
        assert len(file_utils.temp_files) == 3
        
        file_utils.cleanup_temp_files()
        
        assert not os.path.exists(temp_file1)
        assert not os.path.exists(temp_file2)
        assert not os.path.exists(temp_dir)
        assert len(file_utils.temp_files) == 0

    def test_cleanup_files_static_method(self, temp_directory):
        """Test static cleanup_files method"""
        # Create test files
        file1 = os.path.join(temp_directory, 'file1.txt')
        file2 = os.path.join(temp_directory, 'file2.txt')
        
        with open(file1, 'w') as f:
            f.write("File 1")
        with open(file2, 'w') as f:
            f.write("File 2")
        
        assert os.path.exists(file1)
        assert os.path.exists(file2)
        
        FileUtils.cleanup_files([file1, file2])
        
        assert not os.path.exists(file1)
        assert not os.path.exists(file2)

    def test_cleanup_files_with_nonexistent(self, temp_directory):
        """Test static cleanup_files method with non-existent files"""
        # Create one real file
        real_file = os.path.join(temp_directory, 'real_file.txt')
        with open(real_file, 'w') as f:
            f.write("Real file")
        
        file_list = [real_file, "/nonexistent/file.txt"]
        
        # Should not raise an exception
        FileUtils.cleanup_files(file_list)
        
        assert not os.path.exists(real_file)

    @pytest.mark.parametrize("filename,expected", [
        ("document.pdf", "application"),
        ("image.jpg", "image"),
        ("audio.mp3", "audio"),
        ("video.mp4", "video"),
        ("text.txt", "text"),
        ("unknown.xyz", "application"),
        ("no_extension", "application"),
    ])
    def test_get_file_type(self, file_utils, filename, expected):
        """Test file type detection"""
        result = file_utils.get_file_type(filename)
        assert result.startswith(expected)

    @pytest.mark.parametrize("size_bytes,expected", [
        (0, "0 B"),
        (1023, "1023 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1048576, "1.0 MB"),
        (1073741824, "1.0 GB"),
        (1099511627776, "1.0 TB"),
        (2048, "2.0 KB"),
        (1536000, "1.5 MB"),
    ])
    def test_format_file_size(self, file_utils, size_bytes, expected):
        """Test file size formatting"""
        result = file_utils.format_file_size(size_bytes)
        assert result == expected

    def test_format_file_size_negative(self, file_utils):
        """Test file size formatting with negative size"""
        result = file_utils.format_file_size(-1024)
        assert result == "0 B"

    def test_destructor_cleanup(self):
        """Test that destructor cleans up temporary files"""
        file_utils = FileUtils()
        
        # Create temporary files
        temp_file = file_utils.create_temp_file()
        temp_dir = file_utils.create_temp_directory()
        
        assert os.path.exists(temp_file)
        assert os.path.exists(temp_dir)
        
        # Delete the instance (trigger destructor)
        del file_utils
        
        # Files should be cleaned up
        assert not os.path.exists(temp_file)
        assert not os.path.exists(temp_dir)

    def test_context_manager_like_usage(self, file_utils):
        """Test FileUtils usage in a context-manager-like pattern"""
        temp_files = []
        
        try:
            # Create temporary files
            temp_file1 = file_utils.create_temp_file()
            temp_file2 = file_utils.create_temp_file()
            temp_files.extend([temp_file1, temp_file2])
            
            assert all(os.path.exists(f) for f in temp_files)
            
            # Do some work with the files
            with open(temp_file1, 'w') as f:
                f.write("Test content 1")
            
            with open(temp_file2, 'w') as f:
                f.write("Test content 2")
            
        finally:
            # Cleanup
            file_utils.cleanup_temp_files()
            
        assert all(not os.path.exists(f) for f in temp_files)

    def test_large_file_handling(self, file_utils, temp_directory):
        """Test handling of large files (simulated)"""
        large_file = os.path.join(temp_directory, 'large_file.bin')
        
        # Create a moderately large file (1MB)
        with open(large_file, 'wb') as f:
            f.write(b'0' * (1024 * 1024))
        
        # Test file info
        info = file_utils.get_file_info(large_file)
        assert info['file_size'] == 1024 * 1024
        
        # Test hash calculation
        hash_result = file_utils.calculate_file_hash(large_file, 'md5')
        assert len(hash_result) == 32
        
        # Test copy
        copy_path = os.path.join(temp_directory, 'large_file_copy.bin')
        file_utils.copy_file(large_file, copy_path)
        assert os.path.exists(copy_path)
        assert os.path.getsize(copy_path) == 1024 * 1024