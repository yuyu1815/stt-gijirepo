"""
STT議事録システム - リトライユーティリティ

指数バックオフによるリトライ機能の実装
"""

import time
import logging
from typing import Callable, Any, Optional, Type, Union, Tuple
from functools import wraps

from .error_handling import APIError, is_retryable_error


def with_retry(
    max_retries: int = 5,
    backoff_factor: float = 2.0,
    min_delay: float = 1.0,
    max_delay: float = 60.0,
    retry_on: Optional[Union[Type[Exception], Tuple[Type[Exception], ...]]] = None,
    logger: Optional[logging.Logger] = None
):
    """
    指数バックオフによるリトライデコレータ
    
    Args:
        max_retries: 最大リトライ回数
        backoff_factor: バックオフ係数
        min_delay: 最小遅延時間（秒）
        max_delay: 最大遅延時間（秒）
        retry_on: リトライ対象の例外クラス
        logger: ログ出力用のロガー
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # 最後の試行の場合は例外を再発生
                    if attempt == max_retries:
                        if logger:
                            logger.error(f"最大リトライ回数({max_retries})に達しました: {func.__name__}")
                        raise e
                    
                    # リトライ対象の例外かチェック
                    should_retry = False
                    if retry_on:
                        should_retry = isinstance(e, retry_on)
                    else:
                        should_retry = is_retryable_error(e)
                    
                    if not should_retry:
                        if logger:
                            logger.error(f"リトライ不可能なエラーです: {e}")
                        raise e
                    
                    # 遅延時間を計算
                    delay = min(min_delay * (backoff_factor ** attempt), max_delay)
                    
                    if logger:
                        logger.warning(f"リトライ {attempt + 1}/{max_retries}: {func.__name__} - {e} (次の試行まで{delay:.1f}秒待機)")
                    
                    time.sleep(delay)
            
            # ここには到達しないはずだが、念のため
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


def api_call_with_retry(
    func: Callable,
    *args,
    max_retries: int = 5,
    backoff_factor: float = 2.0,
    min_delay: float = 1.0,
    max_delay: float = 60.0,
    logger: Optional[logging.Logger] = None,
    **kwargs
) -> Any:
    """
    API呼び出しのリトライ機能
    
    Args:
        func: 実行する関数
        *args: 関数の位置引数
        max_retries: 最大リトライ回数
        backoff_factor: バックオフ係数
        min_delay: 最小遅延時間（秒）
        max_delay: 最大遅延時間（秒）
        logger: ログ出力用のロガー
        **kwargs: 関数のキーワード引数
        
    Returns:
        関数の実行結果
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            # 最後の試行の場合は例外を再発生
            if attempt == max_retries:
                if logger:
                    logger.error(f"API呼び出しの最大リトライ回数({max_retries})に達しました: {func.__name__}")
                raise e
            
            # APIエラーのみリトライ対象
            if not isinstance(e, (APIError, ConnectionError, TimeoutError)):
                if logger:
                    logger.error(f"API呼び出しでリトライ不可能なエラーです: {e}")
                raise e
            
            # 4xx系のクライアントエラーはリトライしない
            if isinstance(e, APIError) and e.status_code and 400 <= e.status_code < 500:
                if logger:
                    logger.error(f"クライアントエラーのためリトライしません: {e}")
                raise e
            
            # 遅延時間を計算
            delay = min(min_delay * (backoff_factor ** attempt), max_delay)
            
            if logger:
                logger.warning(f"API呼び出しリトライ {attempt + 1}/{max_retries}: {func.__name__} - {e} (次の試行まで{delay:.1f}秒待機)")
            
            time.sleep(delay)
    
    # ここには到達しないはずだが、念のため
    if last_exception:
        raise last_exception


class RetryConfig:
    """リトライ設定クラス"""
    
    def __init__(
        self,
        max_retries: int = 5,
        backoff_factor: float = 2.0,
        min_delay: float = 1.0,
        max_delay: float = 60.0,
        retry_on: Optional[Union[Type[Exception], Tuple[Type[Exception], ...]]] = None
    ):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.retry_on = retry_on
    
    def create_decorator(self, logger: Optional[logging.Logger] = None):
        """設定に基づいてリトライデコレータを作成"""
        return with_retry(
            max_retries=self.max_retries,
            backoff_factor=self.backoff_factor,
            min_delay=self.min_delay,
            max_delay=self.max_delay,
            retry_on=self.retry_on,
            logger=logger
        )


# デフォルトのリトライ設定
DEFAULT_RETRY_CONFIG = RetryConfig()
API_RETRY_CONFIG = RetryConfig(
    max_retries=5,
    backoff_factor=2.0,
    min_delay=2.0,
    max_delay=30.0,
    retry_on=(APIError, ConnectionError, TimeoutError)
)