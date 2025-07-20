"""
STT議事録システム - ログ設定

統一されたログ設定とロガー管理
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


class STTFormatter(logging.Formatter):
    """STTシステム用カスタムフォーマッター"""
    
    def __init__(self):
        super().__init__()
        self.default_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        self.detailed_format = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    
    def format(self, record):
        # DEBUGレベルの場合は詳細フォーマットを使用
        if record.levelno == logging.DEBUG:
            formatter = logging.Formatter(self.detailed_format)
        else:
            formatter = logging.Formatter(self.default_format)
        
        return formatter.format(record)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: str = "logs",
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    enable_console: bool = True,
    session_id: Optional[str] = None
) -> logging.Logger:
    """
    ログ設定をセットアップ
    
    Args:
        log_level: ログレベル
        log_file: ログファイル名（Noneの場合は自動生成）
        log_dir: ログディレクトリ
        max_file_size: ログファイルの最大サイズ
        backup_count: バックアップファイル数
        enable_console: コンソール出力を有効にするか
        session_id: セッションID（ログファイル名に使用）
        
    Returns:
        設定されたロガー
    """
    # ログディレクトリを作成
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # ログファイル名を決定
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if session_id:
            log_file = f"stt_{session_id}_{timestamp}.log"
        else:
            log_file = f"stt_{timestamp}.log"
    
    log_file_path = log_path / log_file
    
    # ルートロガーを取得
    logger = logging.getLogger("stt_system")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 既存のハンドラーをクリア
    logger.handlers.clear()
    
    # カスタムフォーマッターを作成
    formatter = STTFormatter()
    
    # ファイルハンドラーを追加
    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path,
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # コンソールハンドラーを追加
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 初期ログメッセージ
    logger.info(f"ログシステムが初期化されました - レベル: {log_level}, ファイル: {log_file_path}")
    
    return logger


def get_logger(name: str = "stt_system") -> logging.Logger:
    """
    指定された名前のロガーを取得
    
    Args:
        name: ロガー名
        
    Returns:
        ロガーインスタンス
    """
    return logging.getLogger(name)


def log_performance(logger: logging.Logger, operation: str, duration: float, **kwargs):
    """
    パフォーマンス情報をログ出力
    
    Args:
        logger: ロガー
        operation: 操作名
        duration: 実行時間（秒）
        **kwargs: 追加情報
    """
    extra_info = ""
    if kwargs:
        extra_info = " - " + ", ".join([f"{k}: {v}" for k, v in kwargs.items()])
    
    logger.info(f"パフォーマンス - {operation}: {duration:.2f}秒{extra_info}")


def log_state_transition(logger: logging.Logger, from_stage: str, to_stage: str, session_id: str):
    """
    状態遷移をログ出力
    
    Args:
        logger: ロガー
        from_stage: 遷移前の状態
        to_stage: 遷移後の状態
        session_id: セッションID
    """
    logger.info(f"状態遷移 [{session_id}]: {from_stage} → {to_stage}")


def log_error_with_context(logger: logging.Logger, error: Exception, context: Dict[str, Any]):
    """
    コンテキスト情報付きでエラーをログ出力
    
    Args:
        logger: ロガー
        error: エラー
        context: コンテキスト情報
    """
    context_str = ", ".join([f"{k}: {v}" for k, v in context.items()])
    logger.error(f"エラー発生: {error} - コンテキスト: {context_str}", exc_info=True)


class LogContext:
    """ログコンテキスト管理クラス"""
    
    def __init__(self, logger: logging.Logger, operation: str, session_id: Optional[str] = None):
        self.logger = logger
        self.operation = operation
        self.session_id = session_id
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        session_info = f" [{self.session_id}]" if self.session_id else ""
        self.logger.info(f"開始{session_info}: {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()
        session_info = f" [{self.session_id}]" if self.session_id else ""
        
        if exc_type is None:
            self.logger.info(f"完了{session_info}: {self.operation} ({duration:.2f}秒)")
        else:
            self.logger.error(f"エラー終了{session_info}: {self.operation} ({duration:.2f}秒) - {exc_val}")
    
    def log_progress(self, message: str):
        """進捗をログ出力"""
        session_info = f" [{self.session_id}]" if self.session_id else ""
        self.logger.info(f"進捗{session_info}: {self.operation} - {message}")


# デフォルトロガーの初期化
_default_logger = None

def get_default_logger() -> logging.Logger:
    """デフォルトロガーを取得"""
    global _default_logger
    if _default_logger is None:
        _default_logger = setup_logging()
    return _default_logger