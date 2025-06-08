"""
ロギング機能のテスト

このモジュールは、インフラストラクチャ層のロギング機能の機能をテストします。
"""
import unittest
from unittest.mock import patch, MagicMock
import logging
from pathlib import Path

from src.infrastructure.logger import setup_logger


class TestLogger(unittest.TestCase):
    """ロギング機能のテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # ロギングのモック
        self.mock_logger = MagicMock()
        self.log_patcher = patch('logging.getLogger', return_value=self.mock_logger)
        self.mock_get_logger = self.log_patcher.start()
        
        # ファイルハンドラのモック
        self.file_handler = MagicMock()
        self.file_handler_patcher = patch('logging.FileHandler', return_value=self.file_handler)
        self.mock_file_handler = self.file_handler_patcher.start()
        
        # ストリームハンドラのモック
        self.stream_handler = MagicMock()
        self.stream_handler_patcher = patch('logging.StreamHandler', return_value=self.stream_handler)
        self.mock_stream_handler = self.stream_handler_patcher.start()
        
        # フォーマッタのモック
        self.formatter = MagicMock()
        self.formatter_patcher = patch('logging.Formatter', return_value=self.formatter)
        self.mock_formatter = self.formatter_patcher.start()
        
        # Pathのモック
        self.path_patcher = patch('pathlib.Path')
        self.mock_path = self.path_patcher.start()
        self.mock_path.return_value.exists.return_value = False
        self.mock_path.return_value.mkdir.return_value = None

    def tearDown(self):
        """各テスト実行後のクリーンアップ"""
        self.log_patcher.stop()
        self.file_handler_patcher.stop()
        self.stream_handler_patcher.stop()
        self.formatter_patcher.stop()
        self.path_patcher.stop()

    def test_setup_logger_default(self):
        """デフォルト設定でのロガーセットアップをテスト"""
        # テスト実行
        logger = setup_logger()
        
        # 検証
        self.mock_get_logger.assert_called_once_with('tts_app')
        self.mock_path.assert_called()
        self.mock_path.return_value.exists.assert_called_once()
        self.mock_path.return_value.mkdir.assert_called_once()
        self.mock_file_handler.assert_called_once()
        self.mock_stream_handler.assert_called_once()
        self.mock_formatter.assert_called_once()
        self.assertEqual(self.mock_logger.addHandler.call_count, 2)
        self.assertEqual(logger, self.mock_logger)

    def test_setup_logger_custom_name(self):
        """カスタム名でのロガーセットアップをテスト"""
        # テスト実行
        logger = setup_logger(name='custom_logger')
        
        # 検証
        self.mock_get_logger.assert_called_once_with('custom_logger')
        self.assertEqual(logger, self.mock_logger)

    def test_setup_logger_custom_level(self):
        """カスタムログレベルでのロガーセットアップをテスト"""
        # テスト実行
        logger = setup_logger(level=logging.ERROR)
        
        # 検証
        self.mock_logger.setLevel.assert_called_once_with(logging.ERROR)
        self.assertEqual(logger, self.mock_logger)

    def test_setup_logger_custom_log_dir(self):
        """カスタムログディレクトリでのロガーセットアップをテスト"""
        # テスト実行
        logger = setup_logger(log_dir=Path('custom/log/dir'))
        
        # 検証
        self.mock_path.assert_called_with('custom/log/dir')
        self.assertEqual(logger, self.mock_logger)

    def test_setup_logger_existing_log_dir(self):
        """既存のログディレクトリでのロガーセットアップをテスト"""
        # モックの設定
        self.mock_path.return_value.exists.return_value = True
        
        # テスト実行
        logger = setup_logger()
        
        # 検証
        self.mock_path.return_value.exists.assert_called_once()
        self.mock_path.return_value.mkdir.assert_not_called()
        self.assertEqual(logger, self.mock_logger)

    def test_setup_logger_file_only(self):
        """ファイルのみのロガーセットアップをテスト"""
        # テスト実行
        logger = setup_logger(console_output=False)
        
        # 検証
        self.mock_file_handler.assert_called_once()
        self.mock_stream_handler.assert_not_called()
        self.assertEqual(self.mock_logger.addHandler.call_count, 1)
        self.assertEqual(logger, self.mock_logger)

    def test_setup_logger_console_only(self):
        """コンソールのみのロガーセットアップをテスト"""
        # テスト実行
        logger = setup_logger(file_output=False)
        
        # 検証
        self.mock_file_handler.assert_not_called()
        self.mock_stream_handler.assert_called_once()
        self.assertEqual(self.mock_logger.addHandler.call_count, 1)
        self.assertEqual(logger, self.mock_logger)

    def test_setup_logger_custom_format(self):
        """カスタムフォーマットでのロガーセットアップをテスト"""
        # テスト実行
        custom_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logger = setup_logger(log_format=custom_format)
        
        # 検証
        self.mock_formatter.assert_called_once_with(custom_format)
        self.assertEqual(logger, self.mock_logger)


if __name__ == '__main__':
    unittest.main()