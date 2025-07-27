"""
API Keys Test

このテストは、settings.jsonからAPIキーが正しく読み込まれているかをテストします。
"""

import os
import json
import pytest
from pathlib import Path

from src.workflows.state import create_default_config, STTConfig


def get_settings_json_keys():
    """settings.jsonのAPIキーを取得"""
    settings_file = Path("settings.json")
    if settings_file.exists():
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                return settings
        except Exception as e:
            print(f"settings.jsonの読み込みに失敗しました: {e}")
    else:
        print("settings.jsonが見つかりません")
    return {}


class TestAPIKeys:
    """APIキーのテスト"""
    
    def test_settings_json_exists(self):
        """settings.jsonが存在するかテスト"""
        settings_file = Path("settings.json")
        assert settings_file.exists(), "settings.jsonが見つかりません"
    
    def test_settings_json_has_api_keys(self):
        """settings.jsonにAPIキーが含まれているかテスト"""
        settings = get_settings_json_keys()
        assert 'gemini_api_key' in settings, "settings.jsonにgemini_api_keyが含まれていません"
        assert 'gemini_model' in settings, "settings.jsonにgemini_modelが含まれていません"
        assert 'notion_token' in settings, "settings.jsonにnotion_tokenが含まれていません"
        assert 'notion_database_id' in settings, "settings.jsonにnotion_database_idが含まれていません"
    
    def test_create_default_config_uses_settings_json(self):
        """create_default_config()がsettings.jsonの値を使用しているかテスト"""
        settings = get_settings_json_keys()
        config = create_default_config()
        
        # gemini_modelはsettings.jsonから読み込まれる
        assert config.get('gemini_model') == settings.get('gemini_model'), \
            "create_default_config()のgemini_modelがsettings.jsonと一致しません"
    
    def test_test_config_uses_settings_json(self, test_config):
        """test_config fixtureがsettings.jsonの値を使用しているかテスト"""
        settings = get_settings_json_keys()
        
        # APIキーの比較
        print("\n=== settings.jsonのAPIキー ===")
        print(f"gemini_api_key: {settings.get('gemini_api_key')}")
        print(f"gemini_model: {settings.get('gemini_model')}")
        print(f"notion_token: {settings.get('notion_token')}")
        print(f"notion_database_id: {settings.get('notion_database_id')}")
        
        print("\n=== test_configのAPIキー ===")
        print(f"gemini_api_key: {test_config.get('gemini_api_key')}")
        print(f"gemini_model: {test_config.get('gemini_model')}")
        print(f"notion_token: {test_config.get('notion_token')}")
        print(f"notion_database_id: {test_config.get('notion_database_id')}")
        
        # APIキーがsettings.jsonから読み込まれているか検証
        assert test_config.get('gemini_api_key') == settings.get('gemini_api_key'), \
            "test_configのgemini_api_keyがsettings.jsonと一致しません"
        assert test_config.get('gemini_model') == settings.get('gemini_model'), \
            "test_configのgemini_modelがsettings.jsonと一致しません"
        assert test_config.get('notion_token') == settings.get('notion_token'), \
            "test_configのnotion_tokenがsettings.jsonと一致しません"
        assert test_config.get('notion_database_id') == settings.get('notion_database_id'), \
            "test_configのnotion_database_idがsettings.jsonと一致しません"
    
    def test_mock_environment_variables_uses_settings_json(self, mock_environment_variables):
        """mock_environment_variables fixtureがsettings.jsonの値を使用しているかテスト"""
        settings = get_settings_json_keys()
        
        # 環境変数の比較
        print("\n=== settings.jsonのAPIキー ===")
        print(f"gemini_api_key: {settings.get('gemini_api_key')}")
        print(f"notion_token: {settings.get('notion_token')}")
        print(f"notion_database_id: {settings.get('notion_database_id')}")
        
        print("\n=== モック環境変数のAPIキー ===")
        print(f"GEMINI_API_KEY: {mock_environment_variables.get('GEMINI_API_KEY')}")
        print(f"NOTION_TOKEN: {mock_environment_variables.get('NOTION_TOKEN')}")
        print(f"NOTION_DATABASE_ID: {mock_environment_variables.get('NOTION_DATABASE_ID')}")
        
        # 環境変数がsettings.jsonから読み込まれているか検証
        assert mock_environment_variables.get('GEMINI_API_KEY') == settings.get('gemini_api_key'), \
            "モック環境変数のGEMINI_API_KEYがsettings.jsonと一致しません"
        assert mock_environment_variables.get('NOTION_TOKEN') == settings.get('notion_token'), \
            "モック環境変数のNOTION_TOKENがsettings.jsonと一致しません"
        assert mock_environment_variables.get('NOTION_DATABASE_ID') == settings.get('notion_database_id'), \
            "モック環境変数のNOTION_DATABASE_IDがsettings.jsonと一致しません"