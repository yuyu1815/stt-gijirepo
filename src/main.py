#!/usr/bin/env python3
"""
STT議事録システム - メインエントリーポイント

LangGraphベースのSTT議事録システムのコマンドライン実行インターフェース
"""

import os
import sys
import argparse
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.workflows.stt_workflow import execute_stt_workflow, execute_batch_processing, validate_workflow_config
from src.workflows.state import create_default_config
from src.utils import setup_logging, get_logger
from src.utils.class_info import get_class_info


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    設定ファイルを読み込み
    
    Args:
        config_path: 設定ファイルのパス
        
    Returns:
        設定辞書
    """
    # デフォルト設定を作成
    config = create_default_config()
    
    # 設定ファイルから読み込み
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            print(f"設定ファイルの読み込みエラー: {e}")
    
    # 環境変数から読み込み
    env_mappings = {
        "GEMINI_API_KEY": "gemini_api_key",
        "NOTION_TOKEN": "notion_token",
        "NOTION_DATABASE_ID": "notion_database_id"
    }
    
    for env_key, config_key in env_mappings.items():
        env_value = os.getenv(env_key)
        if env_value:
            config[config_key] = env_value
    
    return config


def find_media_files(path: str) -> List[str]:
    """
    指定されたパスからメディアファイルを検索
    
    Args:
        path: 検索パス（ファイルまたはディレクトリ）
        
    Returns:
        メディアファイルのパスリスト
    """
    media_extensions = {'.mp3', '.wav', '.aac', '.flac', '.ogg', '.wma', '.m4a',
                       '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
    
    path_obj = Path(path)
    
    if path_obj.is_file():
        if path_obj.suffix.lower() in media_extensions:
            return [str(path_obj)]
        else:
            print(f"警告: {path} はサポートされていないファイル形式です")
            return []
    
    elif path_obj.is_dir():
        media_files = []
        for file_path in path_obj.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in media_extensions:
                media_files.append(str(file_path))
        
        media_files.sort()  # ファイル名順にソート
        return media_files
    
    else:
        print(f"エラー: {path} が見つかりません")
        return []


def print_result_summary(result: Dict[str, Any]) -> None:
    """
    処理結果のサマリーを表示
    
    Args:
        result: 処理結果
    """
    print("\n" + "="*60)
    print("処理結果サマリー")
    print("="*60)
    
    # 基本情報
    print(f"ファイル: {result.get('original_filename', 'N/A')}")
    print(f"セッションID: {result.get('session_id', 'N/A')}")
    print(f"最終ステータス: {result.get('final_status', 'N/A')}")
    
    # 処理統計
    audio_duration = result.get('audio_duration', 0)
    if audio_duration > 0:
        minutes = int(audio_duration // 60)
        seconds = int(audio_duration % 60)
        print(f"音声長: {minutes}分{seconds}秒")
    
    transcription_length = len(result.get('transcription', ''))
    minutes_length = len(result.get('minutes', ''))
    print(f"文字起こし: {transcription_length:,}文字")
    print(f"議事録: {minutes_length:,}文字")
    
    # 品質情報
    quality_result = result.get('quality_check_result', {})
    if quality_result:
        quality_score = quality_result.get('overall_score', 0)
        print(f"品質スコア: {quality_score:.2f}")
    
    # Notion情報
    notion_page_id = result.get('notion_page_id')
    if notion_page_id:
        print(f"NotionページID: {notion_page_id}")
    
    # エラー・警告
    errors = result.get('errors', [])
    warnings = result.get('warnings', [])
    
    if errors:
        print(f"\nエラー ({len(errors)}件):")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
    
    if warnings:
        print(f"\n警告 ({len(warnings)}件):")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")
    
    # 処理ログ
    processing_log = result.get('processing_log', [])
    if processing_log:
        print(f"\n処理ログ:")
        for log_entry in processing_log[-5:]:  # 最後の5件のみ表示
            print(f"  - {log_entry}")
    
    print("="*60)


def save_results(result: Dict[str, Any], output_dir: str) -> None:
    """
    処理結果をファイルに保存
    
    Args:
        result: 処理結果
        output_dir: 出力ディレクトリ
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    session_id = result.get('session_id', 'unknown')
    original_filename = result.get('original_filename', 'unknown')
    
    # 議事録を保存
    minutes = result.get('minutes', '')
    if minutes:
        minutes_file = output_path / f"{original_filename}_{session_id}_minutes.md"
        with open(minutes_file, 'w', encoding='utf-8') as f:
            f.write(minutes)
        print(f"議事録を保存しました: {minutes_file}")
    
    # 文字起こし結果を保存
    transcription = result.get('transcription', '')
    if transcription:
        transcription_file = output_path / f"{original_filename}_{session_id}_transcription.txt"
        with open(transcription_file, 'w', encoding='utf-8') as f:
            f.write(transcription)
        print(f"文字起こし結果を保存しました: {transcription_file}")
    
    # 処理結果のJSONを保存
    result_file = output_path / f"{original_filename}_{session_id}_result.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        # datetimeオブジェクトを文字列に変換
        json_result = {}
        for key, value in result.items():
            if hasattr(value, 'isoformat'):
                json_result[key] = value.isoformat()
            else:
                json_result[key] = value
        
        json.dump(json_result, f, ensure_ascii=False, indent=2)
    print(f"処理結果を保存しました: {result_file}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="STT議事録システム - 音声・動画ファイルから議事録を自動生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 単一ファイルの処理
  python src/main.py audio.mp3
  
  # Notionにアップロード
  python src/main.py audio.mp3 --upload-notion
  
  # フォルダ内の全ファイルを処理
  python src/main.py /path/to/audio/folder --batch
  
  # 設定ファイルを指定
  python src/main.py audio.mp3 --config settings.json
  
  # 出力ディレクトリを指定
  python src/main.py audio.mp3 --output ./results
        """
    )
    
    # 位置引数
    parser.add_argument(
        'input_path',
        help='処理対象のファイルまたはディレクトリパス'
    )
    
    # オプション引数
    parser.add_argument(
        '--config', '-c',
        help='設定ファイルのパス (デフォルト: settings.json)',
        default='settings.json'
    )
    
    parser.add_argument(
        '--upload-notion', '-n',
        action=argparse.BooleanOptionalAction,
        default=True,
        help='Notionへのアップロードを有効化します (無効にする場合は --no-upload-notion)'
    )
    
    parser.add_argument(
        '--batch', '-b',
        action='store_true',
        help='バッチ処理モード（ディレクトリ内の全ファイルを処理）'
    )
    
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=3,
        help='バッチ処理時の最大並列数 (デフォルト: 3)'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='出力ディレクトリ (デフォルト: ./output)',
        default='./output'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='ログレベル (デフォルト: INFO)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='実際の処理を行わず、設定の検証のみ実行'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='詳細な出力を表示'
    )
    
    parser.add_argument(
        '--force-video-mode',
        action='store_true',
        help='音声ファイルを動画処理ルート（マルチモーダル解析）で強制的に処理'
    )
    
    args = parser.parse_args()
    
    # ログ設定
    logger = setup_logging(
        log_level=args.log_level,
        enable_console=True,
        log_dir="logs"
    )
    
    try:
        print("STT議事録システム - LangGraph版")
        print("="*50)
        
        # 設定を読み込み
        print(f"設定ファイルを読み込み中: {args.config}")
        config = load_config(args.config if os.path.exists(args.config) else None)
        
        # 設定を検証
        validation_result = validate_workflow_config(config)
        if not validation_result["valid"]:
            print("設定エラー:")
            for error in validation_result["errors"]:
                print(f"  - {error}")
            return 1
        
        if validation_result["warnings"]:
            print("設定警告:")
            for warning in validation_result["warnings"]:
                print(f"  - {warning}")
        
        if args.dry_run:
            print("設定検証完了（ドライラン）")
            return 0
        
        # 入力ファイルを検索
        print(f"入力パスを解析中: {args.input_path}")
        media_files = find_media_files(args.input_path)
        
        if not media_files:
            print("処理対象のメディアファイルが見つかりませんでした")
            return 1
        
        print(f"処理対象ファイル: {len(media_files)}件")
        if args.verbose:
            for file_path in media_files:
                print(f"  - {file_path}")
        
        # Notionアップロード可否の最終判断
        upload_enabled_by_user = args.upload_notion
        notion_db_id = config.get("notion_database_id")
        should_upload_to_notion = upload_enabled_by_user and bool(notion_db_id)
        
        # ユーザーがアップロードを意図していたのにIDがない場合は通知
        if upload_enabled_by_user and not bool(notion_db_id):
            print("情報: NotionデータベースIDが設定されていないため、Notionへのアップロードはスキップされます。")
        
        # 処理実行
        if args.batch and len(media_files) > 1:
            print(f"バッチ処理を開始 (最大並列数: {args.max_concurrent})")
            results = execute_batch_processing(
                media_files,
                config,
                max_concurrent=args.max_concurrent,
                upload_to_notion=should_upload_to_notion,
                force_video_mode=args.force_video_mode
            )
            
            # バッチ処理結果の表示
            success_count = sum(1 for r in results if r.get('final_status') == 'success')
            error_count = len(results) - success_count
            
            print(f"\nバッチ処理完了: 成功 {success_count}件, エラー {error_count}件")
            
            # 各結果を保存
            for result in results:
                if args.verbose:
                    print_result_summary(result)
                save_results(result, args.output)
        
        else:
            # 単一ファイル処理
            file_path = media_files[0]
            print(f"処理開始: {file_path}")
            
            result = execute_stt_workflow(
                file_path,
                config,
                upload_to_notion=should_upload_to_notion,
                force_video_mode=args.force_video_mode
            )
            
            # 結果表示
            print_result_summary(result)
            
            # 結果保存
            save_results(result, args.output)
            
            # 終了コードを設定
            if result.get('final_status') == 'success':
                print("\n処理が正常に完了しました")
                return 0
            else:
                print("\n処理中にエラーが発生しました")
                return 1
    
    except KeyboardInterrupt:
        print("\n処理が中断されました")
        return 130
    
    except Exception as e:
        logger.error(f"予期しないエラーが発生しました: {str(e)}", exc_info=True)
        print(f"エラー: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())