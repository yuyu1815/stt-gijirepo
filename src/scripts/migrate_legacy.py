#!/usr/bin/env python3
"""
STT議事録システム - レガシーシステム移行スクリプト

既存のSTTシステムから新しいLangGraphベースのシステムへの移行を支援
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_logging
from src.utils.error_handling import STTError
from src.utils.retry_utils import method_error_handler
from src.workflows.state import create_default_config


class LegacyMigrator:
    """レガシーシステムからの移行を管理するクラス"""
    
    def __init__(self, legacy_dir: str, target_dir: str):
        """
        移行管理クラスの初期化
        
        Args:
            legacy_dir: 既存システムのディレクトリパス
            target_dir: 新システムのディレクトリパス
        """
        self.legacy_dir = Path(legacy_dir)
        self.target_dir = Path(target_dir)
        self.logger = logging.getLogger(__name__)
        
        # 移行統計
        self.migration_stats = {
            "files_processed": 0,
            "files_migrated": 0,
            "files_skipped": 0,
            "errors": 0,
            "warnings": 0
        }
        
    @method_error_handler(STTError, "移行処理に失敗")
    def migrate_all(self) -> Dict[str, Any]:
        """
        完全な移行プロセスを実行
        
        Returns:
            移行結果の詳細
        """
        self.logger.info("レガシーシステムの移行を開始します")
        
        # 1. 環境検証
        self._validate_environment()
        
        # 2. 設定ファイルの移行
        self._migrate_configuration()
        
        # 3. プロンプトファイルの移行
        self._migrate_prompts()
        
        # 4. 処理済みファイルの移行
        self._migrate_processed_files()
        
        # 5. ログファイルの移行
        self._migrate_logs()
        
        # 6. 設定の更新
        self._update_configurations()
        
        # 7. 移行後の検証
        self._validate_migration()
        
        self.logger.info("移行が正常に完了しました")
        return {
            "status": "success",
            "stats": self.migration_stats,
            "message": "移行が正常に完了しました"
        }
    
    def _validate_environment(self):
        """環境の検証"""
        self.logger.info("環境を検証しています...")
        
        # レガシーディレクトリの存在確認
        if not self.legacy_dir.exists():
            raise STTError(f"レガシーディレクトリが見つかりません: {self.legacy_dir}")
        
        # ターゲットディレクトリの作成
        self.target_dir.mkdir(parents=True, exist_ok=True)
        
        # 必要なディレクトリ構造を作成
        required_dirs = [
            "src/workflows",
            "src/core", 
            "src/utils",
            "src/prompts",
            "src/tests",
            "logs",
            "temp",
            "output"
        ]
        
        for dir_path in required_dirs:
            (self.target_dir / dir_path).mkdir(parents=True, exist_ok=True)
        
        self.logger.info("環境検証が完了しました")
    
    @method_error_handler(STTError, "設定ファイルの移行に失敗")
    def _migrate_configuration(self):
        """設定ファイルの移行"""
        self.logger.info("設定ファイルを移行しています...")
        
        # 既存のsettings.jsonを探す
        legacy_settings = self.legacy_dir / "settings.json"
        if not legacy_settings.exists():
            self.logger.info("既存の設定ファイルが見つかりません。デフォルト設定を作成します")
            self._create_default_config()
            self.migration_stats["files_processed"] += 1
            return
            
        # 設定ファイルの読み込みと変換
        try:
            with open(legacy_settings, 'r', encoding='utf-8') as f:
                legacy_config = json.load(f)
            
            # 新しい設定形式に変換
            new_config = self._convert_legacy_config(legacy_config)
            
            # 新しい設定ファイルとして保存
            target_settings = self.target_dir / "settings.json"
            with open(target_settings, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=2, ensure_ascii=False)
            
            self.migration_stats["files_migrated"] += 1
            self.logger.info("設定ファイルの移行が完了しました")
            
        except Exception as e:
            self.logger.warning(f"設定ファイルの移行に失敗しました: {e}")
            self.migration_stats["warnings"] += 1
            
            # デフォルト設定を作成
            self._create_default_config()
        
        self.migration_stats["files_processed"] += 1
    
    def _convert_legacy_config(self, legacy_config: Dict[str, Any]) -> Dict[str, Any]:
        """レガシー設定を新形式に変換"""
        new_config = create_default_config()
        
        # APIキーの移行
        if "gemini_api_key" in legacy_config:
            new_config["gemini_api_key"] = legacy_config["gemini_api_key"]
        
        if "notion_token" in legacy_config:
            new_config["notion_token"] = legacy_config["notion_token"]
        
        # モデル設定の移行
        if "model_name" in legacy_config:
            new_config["gemini_model"] = legacy_config["model_name"]
        
        # 処理設定の移行
        if "max_audio_duration" in legacy_config:
            new_config["max_audio_duration"] = legacy_config["max_audio_duration"]
        
        if "chunk_size" in legacy_config:
            new_config["chunk_size"] = legacy_config["chunk_size"]
        
        # Notion設定の移行
        if "notion_database_id" in legacy_config:
            new_config["notion_database_id"] = legacy_config["notion_database_id"]
        
        return new_config
    
    def _create_default_config(self):
        """デフォルト設定ファイルの作成"""
        default_config = create_default_config()
        
        target_settings = self.target_dir / "settings.json"
        with open(target_settings, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        self.logger.info("デフォルト設定ファイルを作成しました")
    
    def _migrate_prompts(self):
        """プロンプトファイルの移行"""
        self.logger.info("プロンプトファイルを移行しています...")
        
        # レガシーのPROMPTディレクトリを探す
        legacy_prompt_dir = self.legacy_dir / "PROMPT"
        if not legacy_prompt_dir.exists():
            legacy_prompt_dir = self.legacy_dir / "old_src" / "PROMPT"
        
        if legacy_prompt_dir.exists():
            target_prompt_dir = self.target_dir / "src" / "prompts"
            
            # プロンプトファイルのマッピング
            prompt_mapping = {
                "transcription_prompt.md": "transcription.py",
                "minutes_prompt_detailed.md": "minutes_generation.py", 
                "hallucination_check_prompt.md": "quality_check.py",
                "video_analysis_prompt.md": "video_analysis.py",
                "summary_prompt.md": "minutes_generation.py"  # サマリーは議事録生成に統合
            }
            
            for legacy_file, target_file in prompt_mapping.items():
                legacy_path = legacy_prompt_dir / legacy_file
                if legacy_path.exists():
                    try:
                        # Markdownファイルを読み込み
                        with open(legacy_path, 'r', encoding='utf-8') as f:
                            prompt_content = f.read()
                        
                        # Pythonモジュールとして変換
                        python_content = self._convert_prompt_to_python(prompt_content, legacy_file)
                        
                        # 新しいファイルとして保存
                        target_path = target_prompt_dir / target_file
                        if not target_path.exists():  # 既存ファイルは上書きしない
                            with open(target_path, 'w', encoding='utf-8') as f:
                                f.write(python_content)
                            
                            self.migration_stats["files_migrated"] += 1
                            self.logger.info(f"プロンプトファイルを移行しました: {legacy_file} -> {target_file}")
                        else:
                            self.migration_stats["files_skipped"] += 1
                            self.logger.info(f"プロンプトファイルは既に存在します: {target_file}")
                        
                        self.migration_stats["files_processed"] += 1
                        
                    except Exception as e:
                        self.logger.warning(f"プロンプトファイルの移行に失敗しました {legacy_file}: {e}")
                        self.migration_stats["warnings"] += 1
        else:
            self.logger.info("レガシープロンプトディレクトリが見つかりません")
    
    def _convert_prompt_to_python(self, markdown_content: str, filename: str) -> str:
        """MarkdownプロンプトをPythonモジュールに変換"""
        # ファイル名に基づいてプロンプト名を決定
        if "transcription" in filename:
            prompt_name = "TRANSCRIPTION_PROMPT"
        elif "minutes" in filename or "summary" in filename:
            prompt_name = "MINUTES_GENERATION_PROMPT"
        elif "hallucination" in filename:
            prompt_name = "QUALITY_CHECK_PROMPT"
        elif "video" in filename:
            prompt_name = "VIDEO_ANALYSIS_PROMPT"
        else:
            prompt_name = "CUSTOM_PROMPT"
        
        # Pythonモジュールテンプレート
        python_template = f'''"""
STT議事録システム - {prompt_name.replace('_', ' ').title()}

レガシーシステムから移行されたプロンプト
"""

{prompt_name} = """
{markdown_content.strip()}
"""

def get_prompt(**kwargs) -> str:
    """
    プロンプトを取得し、必要に応じてパラメータを置換
    
    Args:
        **kwargs: プロンプト内で置換するパラメータ
        
    Returns:
        フォーマット済みプロンプト
    """
    prompt = {prompt_name}
    
    # パラメータ置換
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        if placeholder in prompt:
            prompt = prompt.replace(placeholder, str(value))
    
    return prompt
'''
        
        return python_template
    
    def _migrate_processed_files(self):
        """処理済みファイルの移行"""
        self.logger.info("処理済みファイルを移行しています...")
        
        # 出力ディレクトリを探す
        possible_output_dirs = [
            self.legacy_dir / "output",
            self.legacy_dir / "results", 
            self.legacy_dir / "generated"
        ]
        
        target_output_dir = self.target_dir / "output"
        
        for output_dir in possible_output_dirs:
            if output_dir.exists():
                try:
                    # ファイルをコピー
                    for file_path in output_dir.rglob("*"):
                        if file_path.is_file():
                            relative_path = file_path.relative_to(output_dir)
                            target_path = target_output_dir / relative_path
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            shutil.copy2(file_path, target_path)
                            self.migration_stats["files_migrated"] += 1
                            
                        self.migration_stats["files_processed"] += 1
                    
                    self.logger.info(f"処理済みファイルを移行しました: {output_dir}")
                    
                except Exception as e:
                    self.logger.warning(f"処理済みファイルの移行に失敗しました {output_dir}: {e}")
                    self.migration_stats["warnings"] += 1
    
    def _migrate_logs(self):
        """ログファイルの移行"""
        self.logger.info("ログファイルを移行しています...")
        
        # ログファイルを探す
        possible_log_files = [
            self.legacy_dir / "stt_system.log",
            self.legacy_dir / "logs" / "stt_system.log",
            self.legacy_dir / "app.log"
        ]
        
        target_log_dir = self.target_dir / "logs"
        
        for log_file in possible_log_files:
            if log_file.exists():
                try:
                    target_log_file = target_log_dir / f"legacy_{log_file.name}"
                    shutil.copy2(log_file, target_log_file)
                    
                    self.migration_stats["files_migrated"] += 1
                    self.migration_stats["files_processed"] += 1
                    
                    self.logger.info(f"ログファイルを移行しました: {log_file.name}")
                    
                except Exception as e:
                    self.logger.warning(f"ログファイルの移行に失敗しました {log_file}: {e}")
                    self.migration_stats["warnings"] += 1
    
    def _update_configurations(self):
        """設定の更新と最適化"""
        self.logger.info("設定を更新しています...")
        
        try:
            # .env.exampleファイルの作成
            env_example_path = self.target_dir / ".env.example"
            if not env_example_path.exists():
                env_content = """# STT議事録システム 環境変数設定
# このファイルを .env にコピーして実際の値を設定してください

# API設定
GEMINI_API_KEY=your_gemini_api_key_here
NOTION_TOKEN=your_notion_token_here
NOTION_DATABASE_ID=your_notion_database_id_here

# 処理設定
MAX_AUDIO_DURATION=2400
CHUNK_SIZE=600
MAX_RETRIES=5

# 品質設定
MIN_CONFIDENCE_THRESHOLD=0.7
ENABLE_QUALITY_CHECK=true

# 出力設定
OUTPUT_FORMAT=markdown
INCLUDE_TIMESTAMPS=true
"""
                with open(env_example_path, 'w', encoding='utf-8') as f:
                    f.write(env_content)
                
                self.logger.info(".env.exampleファイルを作成しました")
            
            # README更新の提案
            readme_path = self.target_dir / "MIGRATION_README.md"
            readme_content = self._generate_migration_readme()
            
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            
            self.logger.info("移行ガイドを作成しました")
            
        except Exception as e:
            self.logger.warning(f"設定更新に失敗しました: {e}")
            self.migration_stats["warnings"] += 1
    
    def _generate_migration_readme(self) -> str:
        """移行ガイドの生成"""
        return f"""# STT議事録システム 移行ガイド

## 移行完了

レガシーシステムから新しいLangGraphベースのSTT議事録システムへの移行が完了しました。

## 移行統計

- 処理ファイル数: {self.migration_stats['files_processed']}
- 移行ファイル数: {self.migration_stats['files_migrated']}
- スキップファイル数: {self.migration_stats['files_skipped']}
- 警告数: {self.migration_stats['warnings']}
- エラー数: {self.migration_stats['errors']}

## 次のステップ

1. **環境変数の設定**
   ```bash
   cp .env.example .env
   # .envファイルを編集して適切な値を設定
   ```

2. **依存関係のインストール**
   ```bash
   pip install -r requirements.txt
   ```

3. **システムのテスト**
   ```bash
   python src/main.py --help
   ```

4. **設定の確認**
   - `settings.json`ファイルの内容を確認
   - 必要に応じて設定を調整

## 主な変更点

- **LangGraphベースのワークフロー**: より構造化された処理フロー
- **型安全性の向上**: TypeHintsによる型チェック
- **エラーハンドリングの改善**: 統一されたエラー処理
- **テストカバレッジの向上**: 包括的なテストスイート
- **監視・ログ機能の強化**: 詳細な処理ログ

## トラブルシューティング

問題が発生した場合は、以下を確認してください：

1. 環境変数が正しく設定されているか
2. 必要な依存関係がインストールされているか
3. APIキーが有効であるか
4. ログファイル（logs/stt_system.log）でエラーの詳細を確認

## サポート

移行に関する問題や質問がある場合は、プロジェクトのIssueページで報告してください。
"""
    
    def _validate_migration(self):
        """移行後の検証"""
        self.logger.info("移行結果を検証しています...")
        
        # 必須ファイルの存在確認
        required_files = [
            "settings.json",
            ".env.example",
            "MIGRATION_README.md"
        ]
        
        for file_name in required_files:
            file_path = self.target_dir / file_name
            if not file_path.exists():
                raise STTError(f"必須ファイルが見つかりません: {file_name}")
        
        # ディレクトリ構造の確認
        required_dirs = [
            "src/workflows",
            "src/core",
            "src/utils", 
            "src/prompts",
            "logs",
            "output"
        ]
        
        for dir_name in required_dirs:
            dir_path = self.target_dir / dir_name
            if not dir_path.exists():
                raise STTError(f"必須ディレクトリが見つかりません: {dir_name}")
        
        self.logger.info("移行検証が完了しました")


@method_error_handler(STTError, "移行メイン関数に失敗", passthrough_exceptions=[KeyboardInterrupt])
def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(
        description="STT議事録システム レガシー移行スクリプト"
    )
    parser.add_argument(
        "legacy_dir",
        help="レガシーシステムのディレクトリパス"
    )
    parser.add_argument(
        "target_dir", 
        help="新システムのディレクトリパス"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="ログレベル"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際の移行を行わず、処理内容のみを表示"
    )
    
    args = parser.parse_args()
    
    # ログ設定
    setup_logging(level=args.log_level)
    logger = logging.getLogger(__name__)
    
    if args.dry_run:
        logger.info("ドライランモード: 実際の移行は行いません")
        # TODO: ドライラン機能の実装
        return 0
    
    # 移行実行
    migrator = LegacyMigrator(args.legacy_dir, args.target_dir)
    result = migrator.migrate_all()
    
    if result["status"] == "success":
        logger.info("移行が正常に完了しました")
        print(f"移行統計: {result['stats']}")
        return 0
    else:
        logger.error(f"移行に失敗しました: {result.get('error', 'Unknown error')}")
        print(f"移行統計: {result['stats']}")
        return 1


if __name__ == "__main__":
    sys.exit(main())