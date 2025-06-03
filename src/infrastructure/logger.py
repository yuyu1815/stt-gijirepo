"""
ログ管理モジュール

このモジュールは、アプリケーションのログ機能を提供します。
構造化ログを出力し、ログレベルに応じた適切なログ記録を行います。
"""
import json
import logging
import logging.config
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .config import config_manager


class Logger:
    """ログ管理クラス"""

    def __init__(self):
        """初期化"""
        self.logger = logging.getLogger("tts-mcp")
        self._configure_logger()

    def _configure_logger(self) -> None:
        """
        ロガーの設定
        """
        # 設定ファイルからログ設定を読み込む
        log_config = config_manager.get("logging", {})
        
        if log_config:
            # 設定ファイルがある場合はそれを使用
            logging.config.dictConfig(log_config)
        else:
            # デフォルト設定
            self._configure_default_logger()

    def _configure_default_logger(self) -> None:
        """
        デフォルトのロガー設定
        """
        # ログレベルの設定
        log_level_str = config_manager.get("log_level", "INFO")
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        
        # ルートロガーの設定
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # ハンドラの設定
        # コンソールハンドラ
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        # ファイルハンドラ
        log_dir = Path(config_manager.get("log_dir", "logs"))
        if not log_dir.exists():
            log_dir.mkdir(parents=True, exist_ok=True)
            
        log_file = log_dir / f"tts-mcp_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # ハンドラの追加
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        
        # アプリケーションロガーの設定
        self.logger.setLevel(log_level)

    def debug(self, message: str, **kwargs) -> None:
        """
        DEBUGレベルのログを出力
        
        Args:
            message: ログメッセージ
            **kwargs: 追加のコンテキスト情報
        """
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """
        INFOレベルのログを出力
        
        Args:
            message: ログメッセージ
            **kwargs: 追加のコンテキスト情報
        """
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """
        WARNINGレベルのログを出力
        
        Args:
            message: ログメッセージ
            **kwargs: 追加のコンテキスト情報
        """
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """
        ERRORレベルのログを出力
        
        Args:
            message: ログメッセージ
            **kwargs: 追加のコンテキスト情報
        """
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """
        CRITICALレベルのログを出力
        
        Args:
            message: ログメッセージ
            **kwargs: 追加のコンテキスト情報
        """
        self._log(logging.CRITICAL, message, **kwargs)

    def _log(self, level: int, message: str, **kwargs) -> None:
        """
        ログを出力
        
        Args:
            level: ログレベル
            message: ログメッセージ
            **kwargs: 追加のコンテキスト情報
        """
        # 構造化ログのためのコンテキスト情報
        extra = {"context": kwargs} if kwargs else {}
        
        # ログ出力
        self.logger.log(level, message, extra=extra)

    def log_exception(self, message: str, exc: Optional[Exception] = None, **kwargs) -> None:
        """
        例外情報を含むログを出力
        
        Args:
            message: ログメッセージ
            exc: 例外オブジェクト
            **kwargs: 追加のコンテキスト情報
        """
        if exc:
            kwargs["exception"] = {
                "type": type(exc).__name__,
                "message": str(exc)
            }
        self.error(message, **kwargs)
        self.logger.exception(message)


# シングルトンインスタンス
logger = Logger()