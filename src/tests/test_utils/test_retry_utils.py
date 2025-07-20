"""
STT議事録システム - リトライユーティリティテスト

retry_utils.pyモジュールのテストケース
"""

import pytest
import time
import logging
from unittest.mock import Mock, patch, call

from src.utils.retry_utils import (
    with_retry,
    api_call_with_retry,
    RetryConfig,
    DEFAULT_RETRY_CONFIG,
    API_RETRY_CONFIG
)
from src.utils.error_handling import (
    APIError,
    FileProcessingError,
    STTError
)


class TestWithRetryDecorator:
    """with_retryデコレータのテスト"""
    
    def test_successful_execution(self):
        """成功時の実行テスト"""
        @with_retry(max_retries=3)
        def successful_function():
            return "success"
        
        result = successful_function()
        assert result == "success"
    
    def test_retry_on_retryable_error(self):
        """リトライ可能エラーでのリトライテスト"""
        call_count = 0
        
        @with_retry(max_retries=3, min_delay=0.01, backoff_factor=1.0)
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise APIError("一時的なエラー", status_code=500)
            return "success"
        
        result = failing_then_success()
        assert result == "success"
        assert call_count == 3
    
    def test_max_retries_exceeded(self):
        """最大リトライ回数超過のテスト"""
        call_count = 0
        
        @with_retry(max_retries=2, min_delay=0.01, backoff_factor=1.0)
        def always_failing():
            nonlocal call_count
            call_count += 1
            raise APIError("常に失敗", status_code=500)
        
        with pytest.raises(APIError):
            always_failing()
        
        assert call_count == 3  # 初回 + 2回のリトライ
    
    def test_non_retryable_error(self):
        """リトライ不可能エラーのテスト"""
        call_count = 0
        
        @with_retry(max_retries=3)
        def non_retryable_error():
            nonlocal call_count
            call_count += 1
            raise APIError("認証エラー", status_code=401)
        
        with pytest.raises(APIError):
            non_retryable_error()
        
        assert call_count == 1  # リトライされない
    
    def test_custom_retry_on_exception(self):
        """カスタム例外でのリトライテスト"""
        call_count = 0
        
        @with_retry(max_retries=2, min_delay=0.01, retry_on=ValueError)
        def custom_retry_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("カスタムエラー")
            return "success"
        
        result = custom_retry_function()
        assert result == "success"
        assert call_count == 2
    
    def test_custom_retry_on_multiple_exceptions(self):
        """複数のカスタム例外でのリトライテスト"""
        call_count = 0
        
        @with_retry(max_retries=3, min_delay=0.01, retry_on=(ValueError, TypeError))
        def multi_exception_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("値エラー")
            elif call_count == 2:
                raise TypeError("型エラー")
            return "success"
        
        result = multi_exception_function()
        assert result == "success"
        assert call_count == 3
    
    def test_non_matching_custom_exception(self):
        """カスタム例外に一致しないエラーのテスト"""
        call_count = 0
        
        @with_retry(max_retries=2, retry_on=ValueError)
        def non_matching_exception():
            nonlocal call_count
            call_count += 1
            raise TypeError("型エラー")
        
        with pytest.raises(TypeError):
            non_matching_exception()
        
        assert call_count == 1  # リトライされない
    
    @patch('time.sleep')
    def test_backoff_calculation(self, mock_sleep):
        """バックオフ計算のテスト"""
        call_count = 0
        
        @with_retry(max_retries=3, min_delay=1.0, backoff_factor=2.0, max_delay=10.0)
        def backoff_test():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise APIError("テストエラー", status_code=500)
            return "success"
        
        with pytest.raises(APIError):
            backoff_test()
        
        # 期待される遅延時間: 1.0, 2.0, 4.0
        expected_calls = [call(1.0), call(2.0), call(4.0)]
        mock_sleep.assert_has_calls(expected_calls)
    
    @patch('time.sleep')
    def test_max_delay_limit(self, mock_sleep):
        """最大遅延時間制限のテスト"""
        call_count = 0
        
        @with_retry(max_retries=2, min_delay=1.0, backoff_factor=10.0, max_delay=5.0)
        def max_delay_test():
            nonlocal call_count
            call_count += 1
            raise APIError("テストエラー", status_code=500)
        
        with pytest.raises(APIError):
            max_delay_test()
        
        # 計算値は10.0だが、max_delayの5.0に制限される
        expected_calls = [call(1.0), call(5.0)]
        mock_sleep.assert_has_calls(expected_calls)
    
    def test_with_logger(self):
        """ロガー付きリトライのテスト"""
        mock_logger = Mock(spec=logging.Logger)
        call_count = 0
        
        @with_retry(max_retries=2, min_delay=0.01, logger=mock_logger)
        def logged_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIError("ログテスト", status_code=500)
            return "success"
        
        result = logged_function()
        assert result == "success"
        
        # 警告ログが呼ばれることを確認
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "リトライ 1/2" in warning_call
    
    def test_logger_on_max_retries(self):
        """最大リトライ時のログテスト"""
        mock_logger = Mock(spec=logging.Logger)
        
        @with_retry(max_retries=1, min_delay=0.01, logger=mock_logger)
        def max_retry_log_test():
            raise APIError("常に失敗", status_code=500)
        
        with pytest.raises(APIError):
            max_retry_log_test()
        
        # エラーログが呼ばれることを確認
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "最大リトライ回数(1)に達しました" in error_call


class TestApiCallWithRetry:
    """api_call_with_retry関数のテスト"""
    
    def test_successful_api_call(self):
        """成功するAPI呼び出しのテスト"""
        def mock_api_function(param1, param2=None):
            return f"result: {param1}, {param2}"
        
        result = api_call_with_retry(mock_api_function, "test", param2="value")
        assert result == "result: test, value"
    
    def test_api_call_with_retry_success(self):
        """リトライ後成功するAPI呼び出しのテスト"""
        call_count = 0
        
        def failing_api():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise APIError("API一時エラー", status_code=503)
            return "api_success"
        
        result = api_call_with_retry(
            failing_api,
            max_retries=3,
            min_delay=0.01,
            backoff_factor=1.0
        )
        assert result == "api_success"
        assert call_count == 3
    
    def test_api_call_max_retries_exceeded(self):
        """API呼び出し最大リトライ超過のテスト"""
        call_count = 0
        
        def always_failing_api():
            nonlocal call_count
            call_count += 1
            raise APIError("API常に失敗", status_code=500)
        
        with pytest.raises(APIError):
            api_call_with_retry(
                always_failing_api,
                max_retries=2,
                min_delay=0.01
            )
        
        assert call_count == 3  # 初回 + 2回のリトライ
    
    def test_api_call_client_error_no_retry(self):
        """クライアントエラーでリトライしないテスト"""
        call_count = 0
        
        def client_error_api():
            nonlocal call_count
            call_count += 1
            raise APIError("認証失敗", status_code=401)
        
        with pytest.raises(APIError):
            api_call_with_retry(client_error_api, max_retries=3)
        
        assert call_count == 1  # リトライされない
    
    def test_api_call_connection_error_retry(self):
        """接続エラーでリトライするテスト"""
        call_count = 0
        
        def connection_error_api():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("接続失敗")
            return "connected"
        
        result = api_call_with_retry(
            connection_error_api,
            max_retries=2,
            min_delay=0.01
        )
        assert result == "connected"
        assert call_count == 2
    
    def test_api_call_timeout_error_retry(self):
        """タイムアウトエラーでリトライするテスト"""
        call_count = 0
        
        def timeout_error_api():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("タイムアウト")
            return "completed"
        
        result = api_call_with_retry(
            timeout_error_api,
            max_retries=2,
            min_delay=0.01
        )
        assert result == "completed"
        assert call_count == 2
    
    def test_api_call_non_retryable_error(self):
        """リトライ不可能エラーのテスト"""
        call_count = 0
        
        def non_retryable_api():
            nonlocal call_count
            call_count += 1
            raise ValueError("値エラー")
        
        with pytest.raises(ValueError):
            api_call_with_retry(non_retryable_api, max_retries=3)
        
        assert call_count == 1  # リトライされない
    
    def test_api_call_with_logger(self):
        """ロガー付きAPI呼び出しのテスト"""
        mock_logger = Mock(spec=logging.Logger)
        call_count = 0
        
        def logged_api():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIError("ログテスト", status_code=500)
            return "logged_success"
        
        result = api_call_with_retry(
            logged_api,
            max_retries=2,
            min_delay=0.01,
            logger=mock_logger
        )
        assert result == "logged_success"
        
        # 警告ログが呼ばれることを確認
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "API呼び出しリトライ 1/2" in warning_call


class TestRetryConfig:
    """RetryConfig設定クラスのテスト"""
    
    def test_default_config_creation(self):
        """デフォルト設定作成のテスト"""
        config = RetryConfig()
        assert config.max_retries == 5
        assert config.backoff_factor == 2.0
        assert config.min_delay == 1.0
        assert config.max_delay == 60.0
        assert config.retry_on is None
    
    def test_custom_config_creation(self):
        """カスタム設定作成のテスト"""
        config = RetryConfig(
            max_retries=3,
            backoff_factor=1.5,
            min_delay=0.5,
            max_delay=30.0,
            retry_on=ValueError
        )
        assert config.max_retries == 3
        assert config.backoff_factor == 1.5
        assert config.min_delay == 0.5
        assert config.max_delay == 30.0
        assert config.retry_on == ValueError
    
    def test_create_decorator(self):
        """デコレータ作成のテスト"""
        config = RetryConfig(max_retries=2, min_delay=0.01)
        decorator = config.create_decorator()
        
        call_count = 0
        
        @decorator
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIError("テスト", status_code=500)
            return "decorated_success"
        
        result = test_function()
        assert result == "decorated_success"
        assert call_count == 2
    
    def test_create_decorator_with_logger(self):
        """ロガー付きデコレータ作成のテスト"""
        mock_logger = Mock(spec=logging.Logger)
        config = RetryConfig(max_retries=1, min_delay=0.01)
        decorator = config.create_decorator(logger=mock_logger)
        
        @decorator
        def logged_test():
            raise APIError("ログテスト", status_code=500)
        
        with pytest.raises(APIError):
            logged_test()
        
        # エラーログが呼ばれることを確認
        mock_logger.error.assert_called_once()


class TestDefaultConfigs:
    """デフォルト設定のテスト"""
    
    def test_default_retry_config(self):
        """DEFAULT_RETRY_CONFIG のテスト"""
        assert DEFAULT_RETRY_CONFIG.max_retries == 5
        assert DEFAULT_RETRY_CONFIG.backoff_factor == 2.0
        assert DEFAULT_RETRY_CONFIG.min_delay == 1.0
        assert DEFAULT_RETRY_CONFIG.max_delay == 60.0
        assert DEFAULT_RETRY_CONFIG.retry_on is None
    
    def test_api_retry_config(self):
        """API_RETRY_CONFIG のテスト"""
        assert API_RETRY_CONFIG.max_retries == 5
        assert API_RETRY_CONFIG.backoff_factor == 2.0
        assert API_RETRY_CONFIG.min_delay == 2.0
        assert API_RETRY_CONFIG.max_delay == 30.0
        assert API_RETRY_CONFIG.retry_on == (APIError, ConnectionError, TimeoutError)


class TestRetryIntegration:
    """リトライ機能の統合テスト"""
    
    @patch('time.sleep')
    def test_complex_retry_scenario(self, mock_sleep):
        """複雑なリトライシナリオのテスト"""
        call_count = 0
        mock_logger = Mock(spec=logging.Logger)
        
        @with_retry(
            max_retries=3,
            min_delay=1.0,
            backoff_factor=2.0,
            max_delay=10.0,
            logger=mock_logger
        )
        def complex_function():
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                raise APIError("一時的エラー", status_code=503)
            elif call_count == 2:
                raise ConnectionError("接続エラー")
            elif call_count == 3:
                raise TimeoutError("タイムアウト")
            else:
                return "finally_success"
        
        result = complex_function()
        assert result == "finally_success"
        assert call_count == 4
        
        # 遅延時間の確認
        expected_calls = [call(1.0), call(2.0), call(4.0)]
        mock_sleep.assert_has_calls(expected_calls)
        
        # ログの確認
        assert mock_logger.warning.call_count == 3
    
    def test_retry_with_function_arguments(self):
        """引数付き関数のリトライテスト"""
        call_count = 0
        
        def api_with_args(endpoint, data=None, timeout=30):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIError("API エラー", status_code=500)
            return f"API call to {endpoint} with {data}, timeout={timeout}"
        
        result = api_call_with_retry(
            api_with_args,
            "/test/endpoint",
            data={"key": "value"},
            timeout=60,
            max_retries=2,
            min_delay=0.01
        )
        
        expected = "API call to /test/endpoint with {'key': 'value'}, timeout=60"
        assert result == expected
        assert call_count == 2


if __name__ == "__main__":
    pytest.main([__file__])