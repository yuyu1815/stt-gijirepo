"""
多言語対応モジュール

このモジュールは、アプリケーションの多言語対応のための機能を提供します。
"""
import json
import os
from pathlib import Path
from typing import Dict, Optional

from ..infrastructure.config import config_manager
from ..infrastructure.logger import logger
from ..infrastructure.storage import storage_manager


class LanguageManager:
    """多言語対応クラス"""

    def __init__(self):
        """初期化"""
        self.lang_dir = Path(config_manager.get("lang_dir", "resources/lang"))
        self.default_lang = config_manager.get("language", "ja")
        self.strings = {}
        self._load_language(self.default_lang)

    def _load_language(self, lang_code: str) -> bool:
        """
        言語ファイルを読み込む
        
        Args:
            lang_code: 言語コード（"ja", "en"など）
            
        Returns:
            読み込みに成功した場合はTrue、それ以外はFalse
        """
        lang_file = self.lang_dir / f"{lang_code}.json"
        
        # 言語ファイルが存在しない場合
        if not lang_file.exists():
            logger.warning(f"言語ファイルが見つかりません: {lang_file}")
            
            # デフォルト言語が指定された言語と異なる場合、デフォルト言語を試す
            if lang_code != self.default_lang:
                logger.info(f"デフォルト言語 ({self.default_lang}) を使用します")
                return self._load_language(self.default_lang)
                
            # デフォルト言語も見つからない場合は空の辞書を使用
            self.strings = {}
            return False
            
        try:
            # 言語ファイルを読み込む
            with open(lang_file, "r", encoding="utf-8") as f:
                self.strings = json.load(f)
                
            logger.info(f"言語ファイルを読み込みました: {lang_file}")
            return True
        except json.JSONDecodeError as e:
            logger.error(f"言語ファイルの解析に失敗しました: {e}")
            self.strings = {}
            return False
        except Exception as e:
            logger.error(f"言語ファイルの読み込みに失敗しました: {e}")
            self.strings = {}
            return False

    def get_string(self, key: str, default: Optional[str] = None) -> str:
        """
        指定されたキーに対応する文字列を取得
        
        Args:
            key: 文字列のキー（ドット区切りで階層指定可能）
            default: キーが存在しない場合のデフォルト値
            
        Returns:
            対応する文字列
        """
        # ドット区切りのキーを処理
        if "." in key:
            parts = key.split(".")
            current = self.strings
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default if default is not None else key
            
            if isinstance(current, str):
                return current
            return default if default is not None else key
        
        # 単一のキー
        if key in self.strings and isinstance(self.strings[key], str):
            return self.strings[key]
            
        return default if default is not None else key

    def change_language(self, lang_code: str) -> bool:
        """
        使用言語を変更
        
        Args:
            lang_code: 言語コード（"ja", "en"など）
            
        Returns:
            変更に成功した場合はTrue、それ以外はFalse
        """
        if self._load_language(lang_code):
            config_manager.set("language", lang_code)
            logger.info(f"言語を変更しました: {lang_code}")
            return True
        return False

    def get_available_languages(self) -> Dict[str, str]:
        """
        利用可能な言語の一覧を取得
        
        Returns:
            言語コードと言語名の辞書
        """
        languages = {}
        
        # 言語ディレクトリが存在しない場合
        if not self.lang_dir.exists():
            logger.warning(f"言語ディレクトリが見つかりません: {self.lang_dir}")
            return languages
            
        # 言語ファイルを検索
        for lang_file in self.lang_dir.glob("*.json"):
            lang_code = lang_file.stem
            
            try:
                # 言語ファイルから言語名を取得
                with open(lang_file, "r", encoding="utf-8") as f:
                    lang_data = json.load(f)
                    lang_name = lang_data.get("language_name", lang_code)
                    languages[lang_code] = lang_name
            except Exception as e:
                logger.warning(f"言語ファイルの読み込みに失敗しました: {lang_file} - {e}")
                languages[lang_code] = lang_code
                
        return languages

    def format_string(self, key: str, **kwargs) -> str:
        """
        文字列をフォーマット
        
        Args:
            key: 文字列のキー
            **kwargs: フォーマットパラメータ
            
        Returns:
            フォーマットされた文字列
        """
        template = self.get_string(key)
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"文字列フォーマットに必要なキーがありません: {e}")
            return template
        except Exception as e:
            logger.warning(f"文字列フォーマットに失敗しました: {e}")
            return template

    def create_default_language_files(self) -> None:
        """
        デフォルトの言語ファイルを作成
        """
        # 言語ディレクトリが存在しない場合は作成
        if not self.lang_dir.exists():
            self.lang_dir.mkdir(parents=True, exist_ok=True)
            
        # 日本語ファイル
        ja_file = self.lang_dir / "ja.json"
        if not ja_file.exists():
            ja_strings = {
                "language_name": "日本語",
                "app": {
                    "name": "音声文字起こし・議事録自動生成ツール",
                    "version": "1.0.0"
                },
                "common": {
                    "ok": "OK",
                    "cancel": "キャンセル",
                    "yes": "はい",
                    "no": "いいえ",
                    "error": "エラー",
                    "warning": "警告",
                    "info": "情報",
                    "success": "成功",
                    "failure": "失敗",
                    "loading": "読み込み中...",
                    "processing": "処理中...",
                    "completed": "完了",
                    "file": "ファイル",
                    "folder": "フォルダ",
                    "select": "選択",
                    "save": "保存",
                    "load": "読み込み",
                    "delete": "削除",
                    "edit": "編集",
                    "view": "表示",
                    "help": "ヘルプ",
                    "about": "このアプリについて"
                },
                "media": {
                    "video": "動画",
                    "audio": "音声",
                    "image": "画像",
                    "duration": "長さ",
                    "dark_video": "暗い動画",
                    "extract_audio": "音声抽出",
                    "split_audio": "音声分割",
                    "extract_image": "画像抽出"
                },
                "transcription": {
                    "title": "文字起こし",
                    "start": "文字起こし開始",
                    "in_progress": "文字起こし中...",
                    "completed": "文字起こし完了",
                    "failed": "文字起こし失敗",
                    "retry": "再試行",
                    "save_result": "結果を保存",
                    "hallucination_check": "ハルシネーションチェック",
                    "hallucination_detected": "ハルシネーションを検出しました"
                },
                "minutes": {
                    "title": "議事録",
                    "generate": "議事録生成",
                    "in_progress": "議事録生成中...",
                    "completed": "議事録生成完了",
                    "failed": "議事録生成失敗",
                    "save_result": "結果を保存",
                    "upload_to_notion": "Notionにアップロード",
                    "summary": "要約",
                    "important_points": "重要ポイント",
                    "tasks": "タスク・宿題",
                    "glossary": "用語集"
                },
                "notion": {
                    "title": "Notion連携",
                    "upload": "アップロード",
                    "in_progress": "アップロード中...",
                    "completed": "アップロード完了",
                    "failed": "アップロード失敗",
                    "select_database": "データベース選択",
                    "api_key": "APIキー",
                    "database_id": "データベースID"
                },
                "settings": {
                    "title": "設定",
                    "general": "一般",
                    "language": "言語",
                    "output_dir": "出力ディレクトリ",
                    "ffmpeg": "FFmpeg設定",
                    "ffmpeg_path": "FFmpegパス",
                    "ffprobe_path": "FFprobeパス",
                    "api": "API設定",
                    "gemini_api_key": "Gemini APIキー",
                    "image_quality": "画像品質",
                    "low": "低",
                    "medium": "中",
                    "high": "高",
                    "save": "設定を保存",
                    "reset": "設定をリセット"
                },
                "errors": {
                    "file_not_found": "ファイルが見つかりません: {file_path}",
                    "directory_not_found": "ディレクトリが見つかりません: {dir_path}",
                    "api_key_missing": "APIキーが設定されていません",
                    "api_error": "APIエラー: {message}",
                    "ffmpeg_error": "FFmpegエラー: {message}",
                    "transcription_error": "文字起こしエラー: {message}",
                    "minutes_generation_error": "議事録生成エラー: {message}",
                    "notion_upload_error": "Notionアップロードエラー: {message}"
                }
            }
            
            with open(ja_file, "w", encoding="utf-8") as f:
                json.dump(ja_strings, f, ensure_ascii=False, indent=2)
                
            logger.info(f"日本語ファイルを作成しました: {ja_file}")
            
        # 英語ファイル
        en_file = self.lang_dir / "en.json"
        if not en_file.exists():
            en_strings = {
                "language_name": "English",
                "app": {
                    "name": "Audio Transcription & Minutes Generation Tool",
                    "version": "1.0.0"
                },
                "common": {
                    "ok": "OK",
                    "cancel": "Cancel",
                    "yes": "Yes",
                    "no": "No",
                    "error": "Error",
                    "warning": "Warning",
                    "info": "Information",
                    "success": "Success",
                    "failure": "Failure",
                    "loading": "Loading...",
                    "processing": "Processing...",
                    "completed": "Completed",
                    "file": "File",
                    "folder": "Folder",
                    "select": "Select",
                    "save": "Save",
                    "load": "Load",
                    "delete": "Delete",
                    "edit": "Edit",
                    "view": "View",
                    "help": "Help",
                    "about": "About"
                },
                "media": {
                    "video": "Video",
                    "audio": "Audio",
                    "image": "Image",
                    "duration": "Duration",
                    "dark_video": "Dark Video",
                    "extract_audio": "Extract Audio",
                    "split_audio": "Split Audio",
                    "extract_image": "Extract Image"
                },
                "transcription": {
                    "title": "Transcription",
                    "start": "Start Transcription",
                    "in_progress": "Transcribing...",
                    "completed": "Transcription Completed",
                    "failed": "Transcription Failed",
                    "retry": "Retry",
                    "save_result": "Save Result",
                    "hallucination_check": "Hallucination Check",
                    "hallucination_detected": "Hallucination Detected"
                },
                "minutes": {
                    "title": "Minutes",
                    "generate": "Generate Minutes",
                    "in_progress": "Generating Minutes...",
                    "completed": "Minutes Generation Completed",
                    "failed": "Minutes Generation Failed",
                    "save_result": "Save Result",
                    "upload_to_notion": "Upload to Notion",
                    "summary": "Summary",
                    "important_points": "Important Points",
                    "tasks": "Tasks & Assignments",
                    "glossary": "Glossary"
                },
                "notion": {
                    "title": "Notion Integration",
                    "upload": "Upload",
                    "in_progress": "Uploading...",
                    "completed": "Upload Completed",
                    "failed": "Upload Failed",
                    "select_database": "Select Database",
                    "api_key": "API Key",
                    "database_id": "Database ID"
                },
                "settings": {
                    "title": "Settings",
                    "general": "General",
                    "language": "Language",
                    "output_dir": "Output Directory",
                    "ffmpeg": "FFmpeg Settings",
                    "ffmpeg_path": "FFmpeg Path",
                    "ffprobe_path": "FFprobe Path",
                    "api": "API Settings",
                    "gemini_api_key": "Gemini API Key",
                    "image_quality": "Image Quality",
                    "low": "Low",
                    "medium": "Medium",
                    "high": "High",
                    "save": "Save Settings",
                    "reset": "Reset Settings"
                },
                "errors": {
                    "file_not_found": "File not found: {file_path}",
                    "directory_not_found": "Directory not found: {dir_path}",
                    "api_key_missing": "API key is not set",
                    "api_error": "API Error: {message}",
                    "ffmpeg_error": "FFmpeg Error: {message}",
                    "transcription_error": "Transcription Error: {message}",
                    "minutes_generation_error": "Minutes Generation Error: {message}",
                    "notion_upload_error": "Notion Upload Error: {message}"
                }
            }
            
            with open(en_file, "w", encoding="utf-8") as f:
                json.dump(en_strings, f, ensure_ascii=False, indent=2)
                
            logger.info(f"英語ファイルを作成しました: {en_file}")


# シングルトンインスタンス
language_manager = LanguageManager()