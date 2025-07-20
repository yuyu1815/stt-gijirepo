"""
STT議事録システム - ログ設定テスト

logging_config.pyモジュールのテストケース
"""

import pytest
import logging
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, call
from datetime import datetime

from src.utils.logging_config import (
    STTFormatter,
    setup_logging,
    get_logger,
    log_performance,
    log_state_transition,
    log_error_with_context,
    LogContext,
    get_default_logger
)


class TestSTTFormatter:
    """STTFormatterカスタムフォーマッターのテスト"""
    
    def test_formatter_creation(self):
        """フォーマッター作成のテスト"""
        formatter = STTFormatter()
        assert formatter.default_format == '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        assert formatter.detailed_format == '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    
    def test_info_level_formatting(self):
        """INFOレベルのフォーマットテスト"""
        formatter = STTFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/file.py",
            lineno=123,
            msg="テストメッセージ",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        assert "test_logger" in formatted
        assert "INFO" in formatted
        assert "テストメッセージ" in formatted
        # INFOレベルでは詳細情報（ファイル名:行番号）は含まれない
        assert "[file.py:123]" not in formatted
    
    def test_debug_level_formatting(self):
        """DEBUGレベルのフォーマットテスト"""
        formatter = STTFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.DEBUG,
            pathname="/test/file.py",
            lineno=123,
            msg="デバッグメッセージ",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        assert "test_logger" in formatted
        assert "DEBUG" in formatted
        assert "デバッグメッセージ" in formatted
        # DEBUGレベルでは詳細情報（ファイル名:行番号）が含まれる
        assert "[file.py:123]" in formatted
    
    def test_error_level_formatting(self):
        """ERRORレベルのフォーマットテスト"""
        formatter = STTFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="/test/file.py",
            lineno=456,
            msg="エラーメッセージ",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        assert "test_logger" in formatted
        assert "ERROR" in formatted
        assert "エラーメッセージ" in formatted
        # ERRORレベルでは詳細情報は含まれない
        assert "[file.py:456]" not in formatted


class TestSetupLogging:
    """setup_logging関数のテスト"""
    
    def test_basic_setup(self):
        """基本的なログ設定のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = setup_logging(
                log_level="INFO",
                log_dir=temp_dir,
                enable_console=False
            )
            
            assert logger.name == "stt_system"
            assert logger.level == logging.INFO
            assert len(logger.handlers) == 1  # ファイルハンドラーのみ
            
            # ログファイルが作成されることを確認
            log_files = list(Path(temp_dir).glob("stt_*.log"))
            assert len(log_files) == 1
    
    def test_custom_log_file(self):
        """カスタムログファイル名のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_filename = "custom_test.log"
            logger = setup_logging(
                log_file=custom_filename,
                log_dir=temp_dir,
                enable_console=False
            )
            
            log_file_path = Path(temp_dir) / custom_filename
            assert log_file_path.exists()
    
    def test_session_id_in_filename(self):
        """セッションIDがファイル名に含まれるテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            session_id = "test_session_123"
            logger = setup_logging(
                log_dir=temp_dir,
                session_id=session_id,
                enable_console=False
            )
            
            log_files = list(Path(temp_dir).glob(f"stt_{session_id}_*.log"))
            assert len(log_files) == 1
    
    def test_console_and_file_handlers(self):
        """コンソールとファイル両方のハンドラーのテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = setup_logging(
                log_dir=temp_dir,
                enable_console=True
            )
            
            assert len(logger.handlers) == 2  # ファイル + コンソール
            
            # ハンドラーの種類を確認
            handler_types = [type(h).__name__ for h in logger.handlers]
            assert "RotatingFileHandler" in handler_types
            assert "StreamHandler" in handler_types
    
    def test_log_level_setting(self):
        """ログレベル設定のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # DEBUGレベル
            debug_logger = setup_logging(
                log_level="DEBUG",
                log_dir=temp_dir,
                enable_console=False
            )
            assert debug_logger.level == logging.DEBUG
            
            # WARNINGレベル
            warning_logger = setup_logging(
                log_level="WARNING",
                log_dir=temp_dir,
                enable_console=False
            )
            assert warning_logger.level == logging.WARNING
    
    def test_rotating_file_handler_config(self):
        """ローテーティングファイルハンドラー設定のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            max_size = 1024 * 1024  # 1MB
            backup_count = 3
            
            logger = setup_logging(
                log_dir=temp_dir,
                max_file_size=max_size,
                backup_count=backup_count,
                enable_console=False
            )
            
            # RotatingFileHandlerの設定を確認
            file_handler = None
            for handler in logger.handlers:
                if hasattr(handler, 'maxBytes'):
                    file_handler = handler
                    break
            
            assert file_handler is not None
            assert file_handler.maxBytes == max_size
            assert file_handler.backupCount == backup_count


class TestGetLogger:
    """get_logger関数のテスト"""
    
    def test_get_default_logger(self):
        """デフォルトロガー取得のテスト"""
        logger = get_logger()
        assert logger.name == "stt_system"
    
    def test_get_named_logger(self):
        """名前付きロガー取得のテスト"""
        logger_name = "test_module"
        logger = get_logger(logger_name)
        assert logger.name == logger_name
    
    def test_same_logger_instance(self):
        """同じ名前で同じインスタンスが返されるテスト"""
        logger1 = get_logger("same_name")
        logger2 = get_logger("same_name")
        assert logger1 is logger2


class TestLogPerformance:
    """log_performance関数のテスト"""
    
    def test_basic_performance_log(self):
        """基本的なパフォーマンスログのテスト"""
        mock_logger = Mock(spec=logging.Logger)
        
        log_performance(mock_logger, "test_operation", 1.23)
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "パフォーマンス - test_operation: 1.23秒" in call_args
    
    def test_performance_log_with_kwargs(self):
        """追加情報付きパフォーマンスログのテスト"""
        mock_logger = Mock(spec=logging.Logger)
        
        log_performance(
            mock_logger,
            "file_processing",
            2.45,
            file_size=1024,
            format="wav"
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "パフォーマンス - file_processing: 2.45秒" in call_args
        assert "file_size: 1024" in call_args
        assert "format: wav" in call_args


class TestLogStateTransition:
    """log_state_transition関数のテスト"""
    
    def test_state_transition_log(self):
        """状態遷移ログのテスト"""
        mock_logger = Mock(spec=logging.Logger)
        
        log_state_transition(
            mock_logger,
            "file_analysis",
            "transcription",
            "session_123"
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "状態遷移 [session_123]: file_analysis → transcription" in call_args


class TestLogErrorWithContext:
    """log_error_with_context関数のテスト"""
    
    def test_error_log_with_context(self):
        """コンテキスト付きエラーログのテスト"""
        mock_logger = Mock(spec=logging.Logger)
        error = ValueError("テストエラー")
        context = {
            "file_path": "/test/file.wav",
            "session_id": "session_456",
            "stage": "processing"
        }
        
        log_error_with_context(mock_logger, error, context)
        
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "エラー発生: テストエラー" in call_args
        assert "file_path: /test/file.wav" in call_args
        assert "session_id: session_456" in call_args
        assert "stage: processing" in call_args
        
        # exc_info=Trueが渡されることを確認
        call_kwargs = mock_logger.error.call_args[1]
        assert call_kwargs.get("exc_info") is True


class TestLogContext:
    """LogContextクラスのテスト"""
    
    def test_basic_context_usage(self):
        """基本的なコンテキスト使用のテスト"""
        mock_logger = Mock(spec=logging.Logger)
        
        with LogContext(mock_logger, "test_operation"):
            pass
        
        # 開始と完了のログが呼ばれることを確認
        assert mock_logger.info.call_count == 2
        
        start_call = mock_logger.info.call_args_list[0][0][0]
        end_call = mock_logger.info.call_args_list[1][0][0]
        
        assert "開始: test_operation" in start_call
        assert "完了: test_operation" in end_call
        assert "秒)" in end_call  # 実行時間が含まれる
    
    def test_context_with_session_id(self):
        """セッションID付きコンテキストのテスト"""
        mock_logger = Mock(spec=logging.Logger)
        session_id = "test_session_789"
        
        with LogContext(mock_logger, "test_operation", session_id):
            pass
        
        start_call = mock_logger.info.call_args_list[0][0][0]
        end_call = mock_logger.info.call_args_list[1][0][0]
        
        assert f"開始 [{session_id}]: test_operation" in start_call
        assert f"完了 [{session_id}]: test_operation" in end_call
    
    def test_context_with_exception(self):
        """例外発生時のコンテキストのテスト"""
        mock_logger = Mock(spec=logging.Logger)
        
        with pytest.raises(ValueError):
            with LogContext(mock_logger, "failing_operation"):
                raise ValueError("テスト例外")
        
        # 開始とエラー終了のログが呼ばれることを確認
        assert mock_logger.info.call_count == 1  # 開始のみ
        assert mock_logger.error.call_count == 1  # エラー終了
        
        start_call = mock_logger.info.call_args[0][0]
        error_call = mock_logger.error.call_args[0][0]
        
        assert "開始: failing_operation" in start_call
        assert "エラー終了: failing_operation" in error_call
        assert "テスト例外" in error_call
    
    def test_log_progress(self):
        """進捗ログのテスト"""
        mock_logger = Mock(spec=logging.Logger)
        
        with LogContext(mock_logger, "progress_operation") as ctx:
            ctx.log_progress("50%完了")
            ctx.log_progress("処理中...")
        
        # 開始、進捗×2、完了のログが呼ばれることを確認
        assert mock_logger.info.call_count == 4
        
        progress_calls = mock_logger.info.call_args_list[1:3]  # 進捗ログのみ
        
        assert "進捗: progress_operation - 50%完了" in progress_calls[0][0][0]
        assert "進捗: progress_operation - 処理中..." in progress_calls[1][0][0]
    
    def test_log_progress_with_session_id(self):
        """セッションID付き進捗ログのテスト"""
        mock_logger = Mock(spec=logging.Logger)
        session_id = "progress_session"
        
        with LogContext(mock_logger, "progress_operation", session_id) as ctx:
            ctx.log_progress("進捗メッセージ")
        
        progress_call = mock_logger.info.call_args_list[1][0][0]  # 2番目のコール（進捗）
        assert f"進捗 [{session_id}]: progress_operation - 進捗メッセージ" in progress_call


class TestGetDefaultLogger:
    """get_default_logger関数のテスト"""
    
    @patch('src.utils.logging_config.setup_logging')
    def test_default_logger_creation(self, mock_setup):
        """デフォルトロガー作成のテスト"""
        mock_logger = Mock(spec=logging.Logger)
        mock_setup.return_value = mock_logger
        
        # グローバル変数をリセット
        import src.utils.logging_config
        src.utils.logging_config._default_logger = None
        
        logger = get_default_logger()
        
        assert logger is mock_logger
        mock_setup.assert_called_once()
    
    @patch('src.utils.logging_config.setup_logging')
    def test_default_logger_singleton(self, mock_setup):
        """デフォルトロガーのシングルトン動作のテスト"""
        mock_logger = Mock(spec=logging.Logger)
        mock_setup.return_value = mock_logger
        
        # グローバル変数をリセット
        import src.utils.logging_config
        src.utils.logging_config._default_logger = None
        
        logger1 = get_default_logger()
        logger2 = get_default_logger()
        
        assert logger1 is logger2
        mock_setup.assert_called_once()  # 1回だけ呼ばれる


class TestLoggingIntegration:
    """ログ機能の統合テスト"""
    
    def test_full_logging_workflow(self):
        """完全なログワークフローのテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # ログ設定
            logger = setup_logging(
                log_level="DEBUG",
                log_dir=temp_dir,
                enable_console=False,
                session_id="integration_test"
            )
            
            # 各種ログ出力
            logger.info("統合テスト開始")
            
            with LogContext(logger, "test_operation", "integration_test") as ctx:
                ctx.log_progress("処理開始")
                log_performance(logger, "sub_operation", 0.5, items=10)
                log_state_transition(logger, "init", "processing", "integration_test")
                ctx.log_progress("処理完了")
            
            # ログファイルが作成され、内容が書き込まれることを確認
            log_files = list(Path(temp_dir).glob("stt_integration_test_*.log"))
            assert len(log_files) == 1
            
            log_content = log_files[0].read_text(encoding='utf-8')
            assert "統合テスト開始" in log_content
            assert "開始 [integration_test]: test_operation" in log_content
            assert "パフォーマンス - sub_operation: 0.50秒" in log_content
            assert "状態遷移 [integration_test]: init → processing" in log_content
            assert "完了 [integration_test]: test_operation" in log_content
    
    def test_error_logging_integration(self):
        """エラーログの統合テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = setup_logging(
                log_dir=temp_dir,
                enable_console=False
            )
            
            # エラーコンテキスト付きログ
            error = RuntimeError("統合テストエラー")
            context = {"operation": "integration_test", "step": "error_test"}
            log_error_with_context(logger, error, context)
            
            # LogContextでの例外処理
            try:
                with LogContext(logger, "error_operation") as ctx:
                    ctx.log_progress("エラー前の進捗")
                    raise ValueError("コンテキスト内エラー")
            except ValueError:
                pass
            
            # ログファイルの内容確認
            log_files = list(Path(temp_dir).glob("stt_*.log"))
            log_content = log_files[0].read_text(encoding='utf-8')
            
            assert "エラー発生: 統合テストエラー" in log_content
            assert "operation: integration_test" in log_content
            assert "エラー終了: error_operation" in log_content
            assert "コンテキスト内エラー" in log_content


if __name__ == "__main__":
    pytest.main([__file__])