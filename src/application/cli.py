"""
コマンドラインインターフェース

このモジュールは、コマンドラインからアプリケーションを操作するためのインターフェースを提供します。
"""
import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..infrastructure.config import config_manager
from ..infrastructure.logger import logger
from .app import app


def parse_arguments() -> Dict:
    """
    コマンドライン引数を解析

    Returns:
        解析された引数の辞書
    """
    parser = argparse.ArgumentParser(
        description="音声文字起こし・議事録自動生成ツール",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # 入力ファイルまたはディレクトリ
    parser.add_argument(
        "-i", "--input",
        help="入力ファイルまたはディレクトリのパス",
        type=str
    )

    # 出力ディレクトリ
    parser.add_argument(
        "-o", "--output-dir",
        help="出力ディレクトリのパス",
        type=str
    )


    # Notionアップロード
    parser.add_argument(
        "--upload-to-notion",
        help="議事録をNotionにアップロードする",
        action="store_true"
    )

    # 画像品質
    parser.add_argument(
        "--image-quality",
        help="抽出する画像の品質（1-5、高いほど高品質）",
        type=int,
        choices=range(1, 6),
        default=3
    )

    # 画像抽出間隔
    parser.add_argument(
        "--image-interval",
        help="画像抽出の間隔（秒）",
        type=int,
        default=60
    )

    # シーン検出閾値
    parser.add_argument(
        "--scene-threshold",
        help="シーン検出の閾値（0.0-1.0、高いほど厳しい）",
        type=float,
        default=0.3
    )

    # 最小シーン長
    parser.add_argument(
        "--min-scene-duration",
        help="最小シーン長（秒）",
        type=float,
        default=2.0
    )

    # チャンク長
    parser.add_argument(
        "--chunk-duration",
        help="音声チャンクの長さ（秒）",
        type=int,
        default=600
    )

    # 言語設定
    parser.add_argument(
        "--language",
        help="言語設定（ja/en）",
        type=str,
        choices=["ja", "en"],
        default="ja"
    )

    # 設定ファイル
    parser.add_argument(
        "--config",
        help="設定ファイルのパス",
        type=str
    )

    # APIキー設定
    parser.add_argument(
        "--gemini-api-key",
        help="Gemini APIキー",
        type=str
    )

    parser.add_argument(
        "--notion-api-key",
        help="Notion APIキー",
        type=str
    )

    parser.add_argument(
        "--notion-database-id",
        help="Notion データベースID",
        type=str
    )

    # バージョン情報
    parser.add_argument(
        "--version",
        help="バージョン情報を表示",
        action="store_true"
    )

    # 引数を解析
    args = parser.parse_args()

    # 引数を辞書に変換
    args_dict = vars(args)

    # バージョン情報を表示
    if args_dict.get("version"):
        print_version()
        sys.exit(0)

    # 設定ファイルを読み込む
    if args_dict.get("config"):
        load_config_file(args_dict["config"])

    # 環境変数から設定を上書き
    override_config_from_env()

    # 引数から設定を上書き
    override_config_from_args(args_dict)

    return args_dict


def load_config_file(config_path: str) -> None:
    """
    設定ファイルを読み込む

    Args:
        config_path: 設定ファイルのパス
    """
    config_path = Path(config_path)

    if not config_path.exists():
        logger.error(f"設定ファイルが見つかりません: {config_path}")
        print(f"エラー: 設定ファイルが見つかりません: {config_path}")
        sys.exit(1)

    try:
        # 設定ファイルの拡張子に応じて読み込み方法を変更
        if config_path.suffix.lower() == ".json":
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            logger.error(f"サポートされていない設定ファイル形式です: {config_path}")
            print(f"エラー: サポートされていない設定ファイル形式です: {config_path}")
            sys.exit(1)

        # 設定を適用
        for key, value in config.items():
            config_manager.set(key, value)

        logger.info(f"設定ファイルを読み込みました: {config_path}")
    except Exception as e:
        logger.error(f"設定ファイルの読み込みに失敗しました: {e}")
        print(f"エラー: 設定ファイルの読み込みに失敗しました: {e}")
        sys.exit(1)


def override_config_from_env() -> None:
    """
    環境変数から設定を上書き
    """
    # APIキー
    if gemini_api_key := os.environ.get("GEMINI_API_KEY"):
        config_manager.set("gemini_api_key", gemini_api_key)

    if notion_api_key := os.environ.get("NOTION_API_KEY"):
        config_manager.set("notion.api_key", notion_api_key)

    if notion_database_id := os.environ.get("NOTION_DATABASE_ID"):
        config_manager.set("notion.database_id", notion_database_id)

    # 出力ディレクトリ
    if output_dir := os.environ.get("OUTPUT_DIR"):
        config_manager.set("output_dir", output_dir)

    # 言語設定
    if language := os.environ.get("LANGUAGE"):
        config_manager.set("language", language)


def override_config_from_args(args: Dict) -> None:
    """
    コマンドライン引数から設定を上書き

    Args:
        args: コマンドライン引数の辞書
    """
    # 出力ディレクトリ
    if output_dir := args.get("output_dir"):
        config_manager.set("output_dir", output_dir)

    # 画像品質
    if image_quality := args.get("image_quality"):
        config_manager.set("video_analysis.image_quality", image_quality)

    # 画像抽出間隔
    if image_interval := args.get("image_interval"):
        config_manager.set("video_analysis.image_interval", image_interval)

    # シーン検出閾値
    if scene_threshold := args.get("scene_threshold"):
        config_manager.set("video_analysis.scene_detection_threshold", scene_threshold)

    # 最小シーン長
    if min_scene_duration := args.get("min_scene_duration"):
        config_manager.set("video_analysis.min_scene_duration", min_scene_duration)

    # チャンク長
    if chunk_duration := args.get("chunk_duration"):
        config_manager.set("media_processor.chunk_duration", chunk_duration)

    # 言語設定
    if language := args.get("language"):
        config_manager.set("language", language)

    # APIキー
    if gemini_api_key := args.get("gemini_api_key"):
        config_manager.set("gemini_api_key", gemini_api_key)

    if notion_api_key := args.get("notion_api_key"):
        config_manager.set("notion.api_key", notion_api_key)

    if notion_database_id := args.get("notion_database_id"):
        config_manager.set("notion.database_id", notion_database_id)


def print_version() -> None:
    """バージョン情報を表示"""
    version = config_manager.get("app.version", "1.0.0")
    print(f"音声文字起こし・議事録自動生成ツール v{version}")
    print("Copyright (c) 2023")


def print_progress(completed: int, total: int) -> None:
    """
    進捗状況を表示

    Args:
        completed: 完了したタスク数
        total: 全タスク数
    """
    if total == 0:
        percent = 100
    else:
        percent = int(completed / total * 100)

    bar_length = 40
    filled_length = int(bar_length * completed / total)
    bar = "=" * filled_length + "-" * (bar_length - filled_length)

    sys.stdout.write(f"\r進捗: [{bar}] {percent}% ({completed}/{total})")
    sys.stdout.flush()

    if completed == total:
        sys.stdout.write("\n")


def print_result_summary(result: Dict) -> None:
    """
    結果の要約を表示

    Args:
        result: 実行結果の辞書
    """
    if not result.get("success", False):
        print(f"エラー: {result.get('error', '不明なエラー')}")
        return

    results = result.get("results", [])
    success_count = sum(1 for r in results if r.get("success", False))
    failure_count = len(results) - success_count

    print(f"\n処理結果:")
    print(f"- 成功: {success_count}件")
    print(f"- 失敗: {failure_count}件")
    print(f"- 処理時間: {result.get('elapsed_time', 0):.2f}秒")

    # 失敗したファイルがある場合は詳細を表示
    if failure_count > 0:
        print("\n失敗したファイル:")
        for r in results:
            if not r.get("success", False):
                print(f"- {r.get('file_path', '不明')}: {r.get('error', '不明なエラー')}")


def main() -> int:
    """
    メイン関数

    Returns:
        終了コード
    """
    try:
        # コマンドライン引数を解析
        args = parse_arguments()

        # アプリケーションを実行
        result = app.run(args)

        # 結果の要約を表示
        print_result_summary(result)

        # 成功した場合は0、失敗した場合は1を返す
        return 0 if result.get("success", False) else 1
    except KeyboardInterrupt:
        print("\n処理を中断しました")
        return 130  # SIGINT
    except Exception as e:
        logger.error(f"予期しないエラーが発生しました: {e}")
        print(f"エラー: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
