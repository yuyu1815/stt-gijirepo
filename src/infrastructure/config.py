"""
設定管理モジュール

このモジュールは、アプリケーションの設定を管理するための機能を提供します。
環境変数と設定ファイルから設定を読み込み、優先順位に基づいて適用します。
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigManager:
    """設定管理クラス"""

    def __init__(self, config_dir: str = "config"):
        """
        初期化

        Args:
            config_dir: 設定ファイルのディレクトリパス
        """
        self.config_dir = Path(config_dir)
        self.settings = {}
        self._load_settings()

    def _load_settings(self) -> None:
        """
        設定ファイルから設定を読み込む
        """
        # 一般設定ファイル
        settings_path = self.config_dir / "settings.json"
        if settings_path.exists():
            with open(settings_path, "r", encoding="utf-8") as f:
                self.settings.update(json.load(f))

        # Notion設定ファイル
        notion_path = self.config_dir / "notion.json"
        if notion_path.exists():
            with open(notion_path, "r", encoding="utf-8") as f:
                self.settings["notion"] = json.load(f)

        # ログ設定ファイル
        logging_path = self.config_dir / "logging.json"
        if logging_path.exists():
            with open(logging_path, "r", encoding="utf-8") as f:
                self.settings["logging"] = json.load(f)

        # 環境変数から設定を上書き
        self._load_from_env()

    def _load_from_env(self) -> None:
        """
        環境変数から設定を読み込む
        環境変数は設定ファイルよりも優先される
        """
        # APIキー
        if gemini_api_key := os.environ.get("GEMINI_API_KEY"):
            self.settings["gemini_api_key"] = gemini_api_key

        if notion_api_key := os.environ.get("NOTION_API_KEY"):
            if "notion" not in self.settings:
                self.settings["notion"] = {}
            self.settings["notion"]["api_key"] = notion_api_key

        if notion_database_id := os.environ.get("NOTION_DATABASE_ID"):
            if "notion" not in self.settings:
                self.settings["notion"] = {}
            self.settings["notion"]["database_id"] = notion_database_id

        # 出力ディレクトリ
        if output_dir := os.environ.get("OUTPUT_DIR"):
            self.settings["output_dir"] = output_dir

        # 言語設定
        if language := os.environ.get("LANGUAGE"):
            self.settings["language"] = language

    def get(self, key: str, default: Any = None) -> Any:
        """
        設定値を取得

        Args:
            key: 設定キー（ドット区切りで階層指定可能）
            default: キーが存在しない場合のデフォルト値

        Returns:
            設定値
        """
        # ドット区切りのキーを処理
        if "." in key:
            parts = key.split(".")
            current = self.settings
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            return current

        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        設定値を設定

        Args:
            key: 設定キー（ドット区切りで階層指定可能）
            value: 設定値
        """
        # ドット区切りのキーを処理
        if "." in key:
            parts = key.split(".")
            current = self.settings
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value
        else:
            self.settings[key] = value

    def save(self) -> None:
        """
        設定をファイルに保存
        """
        # 一般設定
        general_settings = {k: v for k, v in self.settings.items() 
                           if k not in ["notion", "logging"]}

        settings_path = self.config_dir / "settings.json"
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(general_settings, f, indent=4, ensure_ascii=False)

        # Notion設定
        if "notion" in self.settings:
            notion_path = self.config_dir / "notion.json"
            with open(notion_path, "w", encoding="utf-8") as f:
                json.dump(self.settings["notion"], f, indent=4, ensure_ascii=False)

        # ログ設定
        if "logging" in self.settings:
            logging_path = self.config_dir / "logging.json"
            with open(logging_path, "w", encoding="utf-8") as f:
                json.dump(self.settings["logging"], f, indent=4, ensure_ascii=False)

    def _load_api_key_from_file(self, service: str) -> Optional[str]:
        """
        APIキーをファイルから読み込む

        Args:
            service: サービス名（"gemini", "notion"など）

        Returns:
            APIキー
        """
        api_key_file = self.get(f"{service}.api_key_file")
        if not api_key_file:
            return None

        api_key_path = Path(api_key_file)
        if not api_key_path.exists():
            return None

        try:
            with open(api_key_path, "r", encoding="utf-8") as f:
                api_keys = json.load(f)
                return api_keys.get(service, {}).get("api_key")
        except Exception as e:
            print(f"APIキーファイルの読み込みに失敗しました: {e}")
            return None

    def get_api_key(self, service: str) -> Optional[str]:
        """
        APIキーを取得

        Args:
            service: サービス名（"gemini", "notion"など）

        Returns:
            APIキー
        """
        # 優先順位: 環境変数 > APIキーファイル > 設定ファイル内のAPIキー
        if service == "gemini":
            return (self.get("gemini_api_key") or 
                    self._load_api_key_from_file(service) or 
                    self.get("gemini.api_key"))
        elif service == "notion":
            return (self.get("notion.api_key") or 
                    self._load_api_key_from_file(service))
        return None

    def get_output_dir(self, subdir: Optional[str] = None) -> Path:
        """
        出力ディレクトリを取得

        Args:
            subdir: サブディレクトリ名

        Returns:
            出力ディレクトリのパス
        """
        output_dir = Path(self.get("output_dir", "output"))
        if subdir:
            output_dir = output_dir / subdir

        # ディレクトリが存在しない場合は作成
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)

        return output_dir

    def get_prompt_path(self, prompt_name: str) -> Path:
        """
        プロンプトファイルのパスを取得

        Args:
            prompt_name: プロンプト名

        Returns:
            プロンプトファイルのパス
        """
        prompt_dir = Path(self.get("prompt_dir", "prompts"))
        return prompt_dir / f"{prompt_name}.md"

    def get_language(self) -> str:
        """
        言語設定を取得

        Returns:
            言語コード（"ja", "en"など）
        """
        return self.get("language", "ja")


# シングルトンインスタンス
config_manager = ConfigManager()
