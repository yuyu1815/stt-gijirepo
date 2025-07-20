"""
STT議事録システム - エラーハンドリング

カスタム例外クラスとエラー処理ユーティリティ
"""

from typing import Optional, Dict, Any
import logging


class STTError(Exception):
    """STTシステム基底例外"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (詳細: {self.details})"
        return self.message


class FileProcessingError(STTError):
    """ファイル処理エラー"""
    
    def __init__(self, message: str, file_path: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.file_path = file_path


class APIError(STTError):
    """API呼び出しエラー"""
    
    def __init__(self, message: str, api_name: Optional[str] = None, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.api_name = api_name
        self.status_code = status_code


class QualityCheckError(STTError):
    """品質チェックエラー"""
    
    def __init__(self, message: str, quality_score: Optional[float] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.quality_score = quality_score


class NotionUploadError(STTError):
    """Notionアップロードエラー"""
    
    def __init__(self, message: str, database_id: Optional[str] = None, page_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.database_id = database_id
        self.page_id = page_id


def handle_error(error: Exception, context: str = "", logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    エラーを処理し、統一されたエラー情報を返す
    
    Args:
        error: 発生したエラー
        context: エラーが発生したコンテキスト
        logger: ログ出力用のロガー
        
    Returns:
        エラー情報の辞書
    """
    error_info = {
        "error_type": type(error).__name__,
        "message": str(error),
        "context": context
    }
    
    # カスタム例外の場合は詳細情報を追加
    if isinstance(error, STTError):
        error_info["details"] = error.details
        
        if isinstance(error, FileProcessingError):
            error_info["file_path"] = error.file_path
        elif isinstance(error, APIError):
            error_info["api_name"] = error.api_name
            error_info["status_code"] = error.status_code
        elif isinstance(error, QualityCheckError):
            error_info["quality_score"] = error.quality_score
        elif isinstance(error, NotionUploadError):
            error_info["database_id"] = error.database_id
            error_info["page_id"] = error.page_id
    
    # ログ出力
    if logger:
        logger.error(f"エラーが発生しました: {error_info}")
    
    return error_info


def is_retryable_error(error: Exception) -> bool:
    """
    エラーがリトライ可能かどうかを判定
    
    Args:
        error: 判定するエラー
        
    Returns:
        リトライ可能な場合True
    """
    # API関連のエラーは基本的にリトライ可能
    if isinstance(error, APIError):
        # 4xx系のクライアントエラーはリトライしない
        if error.status_code and 400 <= error.status_code < 500:
            return False
        return True
    
    # ファイル処理エラーの一部はリトライ可能
    if isinstance(error, FileProcessingError):
        # ファイルが存在しない場合はリトライしない
        if "not found" in str(error).lower() or "存在しません" in str(error):
            return False
        return True
    
    # その他のSTTErrorは基本的にリトライしない
    if isinstance(error, STTError):
        return False
    
    # システムエラーはリトライ可能
    return True