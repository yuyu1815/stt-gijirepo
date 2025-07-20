"""
STT議事録システム - エラーハンドリングテスト

error_handling.pyモジュールのテストケース
"""

import pytest
import logging
from unittest.mock import Mock

from src.utils.error_handling import (
    STTError,
    FileProcessingError,
    APIError,
    QualityCheckError,
    NotionUploadError,
    handle_error,
    is_retryable_error
)


class TestSTTError:
    """STTError基底例外クラスのテスト"""
    
    def test_basic_error_creation(self):
        """基本的なエラー作成のテスト"""
        error = STTError("テストエラー")
        assert str(error) == "テストエラー"
        assert error.message == "テストエラー"
        assert error.details == {}
    
    def test_error_with_details(self):
        """詳細情報付きエラーのテスト"""
        details = {"key": "value", "number": 123}
        error = STTError("詳細付きエラー", details)
        assert error.message == "詳細付きエラー"
        assert error.details == details
        assert "詳細: {'key': 'value', 'number': 123}" in str(error)
    
    def test_error_inheritance(self):
        """エラーの継承関係のテスト"""
        error = STTError("テスト")
        assert isinstance(error, Exception)
        assert isinstance(error, STTError)


class TestFileProcessingError:
    """FileProcessingError例外クラスのテスト"""
    
    def test_file_processing_error_creation(self):
        """ファイル処理エラー作成のテスト"""
        error = FileProcessingError("ファイル処理失敗", "/path/to/file.wav")
        assert error.message == "ファイル処理失敗"
        assert error.file_path == "/path/to/file.wav"
        assert isinstance(error, STTError)
    
    def test_file_processing_error_without_path(self):
        """ファイルパスなしのファイル処理エラーのテスト"""
        error = FileProcessingError("ファイル処理失敗")
        assert error.message == "ファイル処理失敗"
        assert error.file_path is None
    
    def test_file_processing_error_with_details(self):
        """詳細情報付きファイル処理エラーのテスト"""
        details = {"size": 1024, "format": "wav"}
        error = FileProcessingError("処理失敗", "/test.wav", details)
        assert error.details == details


class TestAPIError:
    """APIError例外クラスのテスト"""
    
    def test_api_error_creation(self):
        """API エラー作成のテスト"""
        error = APIError("API呼び出し失敗", "Gemini", 500)
        assert error.message == "API呼び出し失敗"
        assert error.api_name == "Gemini"
        assert error.status_code == 500
        assert isinstance(error, STTError)
    
    def test_api_error_minimal(self):
        """最小限のAPI エラーのテスト"""
        error = APIError("API失敗")
        assert error.message == "API失敗"
        assert error.api_name is None
        assert error.status_code is None
    
    def test_api_error_with_details(self):
        """詳細情報付きAPI エラーのテスト"""
        details = {"request_id": "12345", "retry_count": 3}
        error = APIError("タイムアウト", "Notion", 408, details)
        assert error.details == details


class TestQualityCheckError:
    """QualityCheckError例外クラスのテスト"""
    
    def test_quality_check_error_creation(self):
        """品質チェックエラー作成のテスト"""
        error = QualityCheckError("品質基準未達", 0.3)
        assert error.message == "品質基準未達"
        assert error.quality_score == 0.3
        assert isinstance(error, STTError)
    
    def test_quality_check_error_without_score(self):
        """スコアなしの品質チェックエラーのテスト"""
        error = QualityCheckError("品質チェック失敗")
        assert error.message == "品質チェック失敗"
        assert error.quality_score is None


class TestNotionUploadError:
    """NotionUploadError例外クラスのテスト"""
    
    def test_notion_upload_error_creation(self):
        """Notionアップロードエラー作成のテスト"""
        error = NotionUploadError("アップロード失敗", "db123", "page456")
        assert error.message == "アップロード失敗"
        assert error.database_id == "db123"
        assert error.page_id == "page456"
        assert isinstance(error, STTError)
    
    def test_notion_upload_error_minimal(self):
        """最小限のNotionアップロードエラーのテスト"""
        error = NotionUploadError("アップロード失敗")
        assert error.message == "アップロード失敗"
        assert error.database_id is None
        assert error.page_id is None


class TestHandleError:
    """handle_error関数のテスト"""
    
    def test_handle_basic_exception(self):
        """基本的な例外処理のテスト"""
        error = ValueError("値エラー")
        result = handle_error(error, "テストコンテキスト")
        
        assert result["error_type"] == "ValueError"
        assert result["message"] == "値エラー"
        assert result["context"] == "テストコンテキスト"
        assert "details" not in result
    
    def test_handle_stt_error(self):
        """STTError処理のテスト"""
        details = {"test": "data"}
        error = STTError("STTエラー", details)
        result = handle_error(error, "STTコンテキスト")
        
        assert result["error_type"] == "STTError"
        assert result["message"] == "STTエラー"
        assert result["context"] == "STTコンテキスト"
        assert result["details"] == details
    
    def test_handle_file_processing_error(self):
        """ファイル処理エラー処理のテスト"""
        error = FileProcessingError("ファイルエラー", "/test/file.wav")
        result = handle_error(error)
        
        assert result["error_type"] == "FileProcessingError"
        assert result["file_path"] == "/test/file.wav"
    
    def test_handle_api_error(self):
        """API エラー処理のテスト"""
        error = APIError("API エラー", "TestAPI", 404)
        result = handle_error(error)
        
        assert result["error_type"] == "APIError"
        assert result["api_name"] == "TestAPI"
        assert result["status_code"] == 404
    
    def test_handle_quality_check_error(self):
        """品質チェックエラー処理のテスト"""
        error = QualityCheckError("品質エラー", 0.2)
        result = handle_error(error)
        
        assert result["error_type"] == "QualityCheckError"
        assert result["quality_score"] == 0.2
    
    def test_handle_notion_upload_error(self):
        """Notionアップロードエラー処理のテスト"""
        error = NotionUploadError("Notionエラー", "db123", "page456")
        result = handle_error(error)
        
        assert result["error_type"] == "NotionUploadError"
        assert result["database_id"] == "db123"
        assert result["page_id"] == "page456"
    
    def test_handle_error_with_logger(self):
        """ロガー付きエラー処理のテスト"""
        mock_logger = Mock(spec=logging.Logger)
        error = ValueError("ログテスト")
        
        result = handle_error(error, "ログコンテキスト", mock_logger)
        
        assert result["error_type"] == "ValueError"
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "エラーが発生しました" in call_args


class TestIsRetryableError:
    """is_retryable_error関数のテスト"""
    
    def test_api_error_retryable(self):
        """リトライ可能なAPI エラーのテスト"""
        # 5xx系エラーはリトライ可能
        error = APIError("サーバーエラー", "TestAPI", 500)
        assert is_retryable_error(error) is True
        
        # ステータスコードなしはリトライ可能
        error = APIError("不明なエラー", "TestAPI")
        assert is_retryable_error(error) is True
    
    def test_api_error_not_retryable(self):
        """リトライ不可能なAPI エラーのテスト"""
        # 4xx系エラーはリトライ不可
        error = APIError("認証エラー", "TestAPI", 401)
        assert is_retryable_error(error) is False
        
        error = APIError("リクエストエラー", "TestAPI", 400)
        assert is_retryable_error(error) is False
        
        error = APIError("見つからない", "TestAPI", 404)
        assert is_retryable_error(error) is False
    
    def test_file_processing_error_retryable(self):
        """リトライ可能なファイル処理エラーのテスト"""
        error = FileProcessingError("一時的な処理エラー")
        assert is_retryable_error(error) is True
        
        error = FileProcessingError("変換エラー")
        assert is_retryable_error(error) is True
    
    def test_file_processing_error_not_retryable(self):
        """リトライ不可能なファイル処理エラーのテスト"""
        error = FileProcessingError("File not found")
        assert is_retryable_error(error) is False
        
        error = FileProcessingError("ファイルが存在しません")
        assert is_retryable_error(error) is False
    
    def test_other_stt_errors_not_retryable(self):
        """その他のSTTエラーはリトライ不可のテスト"""
        error = QualityCheckError("品質エラー")
        assert is_retryable_error(error) is False
        
        error = NotionUploadError("アップロードエラー")
        assert is_retryable_error(error) is False
    
    def test_system_errors_retryable(self):
        """システムエラーはリトライ可能のテスト"""
        error = ConnectionError("接続エラー")
        assert is_retryable_error(error) is True
        
        error = TimeoutError("タイムアウト")
        assert is_retryable_error(error) is True
        
        error = ValueError("値エラー")
        assert is_retryable_error(error) is True


class TestErrorIntegration:
    """エラーハンドリングの統合テスト"""
    
    def test_error_chain_handling(self):
        """エラーチェーン処理のテスト"""
        # 元のエラー
        original_error = ValueError("元のエラー")
        
        # STTErrorでラップ
        wrapped_error = FileProcessingError("ファイル処理中にエラー", "/test.wav", {"original": str(original_error)})
        
        # エラー処理
        result = handle_error(wrapped_error, "統合テスト")
        
        assert result["error_type"] == "FileProcessingError"
        assert result["file_path"] == "/test.wav"
        assert result["details"]["original"] == "元のエラー"
        assert is_retryable_error(wrapped_error) is True
    
    def test_error_context_preservation(self):
        """エラーコンテキスト保持のテスト"""
        details = {
            "session_id": "test-session-123",
            "file_path": "/audio/test.wav",
            "processing_stage": "transcription"
        }
        
        error = APIError("Gemini API呼び出し失敗", "Gemini", 503, details)
        result = handle_error(error, "文字起こし処理中")
        
        assert result["context"] == "文字起こし処理中"
        assert result["api_name"] == "Gemini"
        assert result["status_code"] == 503
        assert result["details"]["session_id"] == "test-session-123"
        assert is_retryable_error(error) is True


if __name__ == "__main__":
    pytest.main([__file__])