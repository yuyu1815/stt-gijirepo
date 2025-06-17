"""
設定管理のテスト

このモジュールは、インフラストラクチャ層の設定管理（ConfigManager）の機能をテストします。
"""
import unittest
from unittest.mock import patch, mock_open
import os
import json
from pathlib import Path

from src.infrastructure.config import ConfigManager


class TestConfigManager(unittest.TestCase):
    """設定管理のテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # 環境変数のモック
        self.env_patcher = patch.dict('os.environ', {
            'GEMINI_API_KEY': 'test_api_key',
            'APP_ENV': 'test'
        })
        self.env_patcher.start()
        
        # テスト用の設定データ
        self.test_config = {
            "app": {
                "name": "音声文字起こし・議事録自動生成ツール",
                "version": "1.0.0"
            },
            "transcription": {
                "max_retries": 3,
                "retry_delay": 2,
                "max_retry_delay": 30,
                "requests_per_minute": 5
            },
            "gemini": {
                "model": "gemini-2.0-flash"
            },
            "prompts": {
                "transcription": "prompts/transcription.md",
                "minutes_detailed": "prompts/minutes_detailed.md",
                "summary": "prompts/summary.md"
            }
        }
        
        # ConfigManagerのインスタンス
        self.config_manager = ConfigManager()

    def tearDown(self):
        """各テスト実行後のクリーンアップ"""
        self.env_patcher.stop()

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    @patch('pathlib.Path.exists')
    def test_load_config(self, mock_exists, mock_json_load, mock_file_open):
        """設定ファイルの読み込みをテスト"""
        # モックの設定
        mock_exists.return_value = True
        mock_json_load.return_value = self.test_config
        
        # テスト実行
        self.config_manager._load_config()
        
        # 検証
        mock_file_open.assert_called_once()
        mock_json_load.assert_called_once()
        self.assertEqual(self.config_manager._config, self.test_config)

    @patch('pathlib.Path.exists')
    def test_load_config_file_not_found(self, mock_exists):
        """設定ファイルが存在しない場合のテスト"""
        # モックの設定
        mock_exists.return_value = False
        
        # テスト実行
        self.config_manager._load_config()
        
        # 検証
        self.assertEqual(self.config_manager._config, {})

    def test_get_existing_key(self):
        """存在するキーの取得をテスト"""
        # テスト用のデータを設定
        self.config_manager._config = self.test_config
        
        # テスト実行
        value = self.config_manager.get("transcription.max_retries")
        
        # 検証
        self.assertEqual(value, 3)

    def test_get_nested_key(self):
        """ネストされたキーの取得をテスト"""
        # テスト用のデータを設定
        self.config_manager._config = self.test_config
        
        # テスト実行
        value = self.config_manager.get("app.name")
        
        # 検証
        self.assertEqual(value, "音声文字起こし・議事録自動生成ツール")

    def test_get_non_existing_key(self):
        """存在しないキーの取得をテスト"""
        # テスト用のデータを設定
        self.config_manager._config = self.test_config
        
        # テスト実行
        value = self.config_manager.get("non_existing_key", "default_value")
        
        # 検証
        self.assertEqual(value, "default_value")

    def test_get_api_key(self):
        """APIキーの取得をテスト"""
        # テスト実行
        api_key = self.config_manager.get_api_key("gemini")
        
        # 検証
        self.assertEqual(api_key, "test_api_key")

    def test_get_api_key_not_found(self):
        """存在しないAPIキーの取得をテスト"""
        # テスト実行
        api_key = self.config_manager.get_api_key("non_existing_api")
        
        # 検証
        self.assertIsNone(api_key)

    @patch('pathlib.Path')
    def test_get_prompt_path(self, mock_path):
        """プロンプトパスの取得をテスト"""
        # テスト用のデータを設定
        self.config_manager._config = self.test_config
        mock_path.return_value = Path("prompts/transcription.md")
        
        # テスト実行
        path = self.config_manager.get_prompt_path("transcription")
        
        # 検証
        self.assertEqual(str(path), "prompts/transcription.md")

    def test_get_prompt_path_not_found(self):
        """存在しないプロンプトパスの取得をテスト"""
        # テスト用のデータを設定
        self.config_manager._config = self.test_config
        
        # テスト実行
        path = self.config_manager.get_prompt_path("non_existing_prompt")
        
        # 検証
        self.assertEqual(path, Path("prompts/non_existing_prompt.md"))


if __name__ == '__main__':
    unittest.main()