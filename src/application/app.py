"""
メインアプリケーション

このモジュールは、アプリケーションのメインクラスを提供します。
各サービスを連携させ、全体のワークフローを制御します。
"""
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..domain.media import MediaFile
from ..domain.transcription import TranscriptionResult
from ..infrastructure.config import config_manager
from ..infrastructure.logger import logger
from ..infrastructure.storage import storage_manager
from ..services.class_info import class_info_service
from ..services.hallucination import hallucination_service
from ..services.media_processor import media_processor_service
from ..services.minutes import minutes_generator_service
from ..services.notion import notion_service
from ..services.transcription import transcription_service
from ..services.video_analysis import video_analysis_service


class Application:
    """アプリケーションクラス"""

    def __init__(self):
        """初期化"""
        logger.info("アプリケーションを初期化しています...")
        self.config = config_manager
        self.storage = storage_manager

    def run(self, args: Dict) -> Dict:
        """
        アプリケーションを実行

        Args:
            args: コマンドライン引数

        Returns:
            実行結果の辞書
        """
        logger.info("アプリケーションを開始します")
        start_time = time.time()

        try:
            # 入力ファイルまたはディレクトリを取得
            input_path = self._get_input_path(args)

            # 入力ファイルのリストを取得
            input_files = self._get_input_files(input_path)

            if not input_files:
                logger.error("処理対象のファイルがありません")
                return {"success": False, "error": "処理対象のファイルがありません"}

            logger.info(f"{len(input_files)}個のファイルを処理します")

            # 各ファイルを処理
            results = []
            for file_path in input_files:
                result = self._process_file(file_path, args)
                results.append(result)

            # 処理時間を計算
            elapsed_time = time.time() - start_time
            logger.info(f"アプリケーションを終了します（処理時間: {elapsed_time:.2f}秒）")

            return {
                "success": True,
                "results": results,
                "elapsed_time": elapsed_time
            }
        except Exception as e:
            logger.error(f"アプリケーションの実行中にエラーが発生しました: {e}")
            return {"success": False, "error": str(e)}

    def _get_input_path(self, args: Dict) -> Path:
        """
        入力パスを取得

        Args:
            args: コマンドライン引数

        Returns:
            入力パス
        """
        # 入力ファイルまたはディレクトリのパスを取得
        if "input" in args and args["input"]:
            input_path = Path(args["input"])
        else:
            # デフォルトの入力ディレクトリ
            input_path = Path(self.config.get("input_dir", "input"))

        # パスが存在するか確認
        if not input_path.exists():
            logger.error(f"入力パスが存在しません: {input_path}")
            raise FileNotFoundError(f"入力パスが存在しません: {input_path}")

        return input_path

    def _get_input_files(self, input_path: Path) -> List[Path]:
        """
        入力ファイルのリストを取得

        Args:
            input_path: 入力パス

        Returns:
            入力ファイルのリスト
        """
        input_files = []

        # ディレクトリの場合
        if input_path.is_dir():
            # サポートする拡張子
            audio_extensions = [".mp3", ".wav", ".aac", ".m4a", ".flac"]
            video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
            supported_extensions = audio_extensions + video_extensions

            # ディレクトリ内のファイルを検索
            for ext in supported_extensions:
                input_files.extend(list(input_path.glob(f"*{ext}")))

            logger.info(f"ディレクトリから{len(input_files)}個のメディアファイルを見つけました: {input_path}")
        # ファイルの場合
        elif input_path.is_file():
            input_files = [input_path]
            logger.info(f"入力ファイル: {input_path}")

        return input_files

    def _process_file(self, file_path: Path, args: Dict) -> Dict:
        """
        単一ファイルを処理

        Args:
            file_path: ファイルパス
            args: コマンドライン引数

        Returns:
            処理結果の辞書
        """
        logger.info(f"ファイルの処理を開始します: {file_path}")
        file_start_time = time.time()

        try:
            # メディアファイルを処理
            media_file = media_processor_service.process_media_file(file_path)


            # 暗い動画の場合は音声を抽出
            if media_file.is_video and media_file.is_dark_video:
                logger.info(f"暗い動画から音声を抽出します: {media_file.file_path}")
                media_file = media_processor_service.extract_audio_from_video(media_file)

            # 長時間メディアの場合は分割
            if media_file.is_long_media:
                logger.info(f"長時間メディアを分割します: {media_file.file_path}")
                media_file = media_processor_service.split_media_file(media_file)

            # 文字起こし
            transcription_result = transcription_service.transcribe_audio(media_file)

            # 文字起こしに失敗した場合
            if transcription_result.is_failed:
                logger.error(f"文字起こしに失敗しました: {media_file.file_path}")
                return {
                    "success": False,
                    "file_path": str(file_path),
                    "error": "文字起こしに失敗しました"
                }

            # ハルシネーションチェック
            transcription_result = hallucination_service.check_hallucination(media_file, transcription_result)

            # 授業情報を取得
            class_info = class_info_service.get_class_info_from_filename(file_path)

            # 画像抽出（動画の場合）
            extracted_images = None
            video_analysis_result = None
            if media_file.is_video and not media_file.is_dark_video:
                # 重要シーンの検出と画像抽出はスキップ（要件により）
                important_scenes = []
                extracted_images = []


            # 議事録生成
            minutes = minutes_generator_service.generate_minutes(
                transcription_result, 
                media_file, 
                extracted_images,
                video_analysis_result
            )

            # 科目名と講師名を設定
            minutes.subject = class_info.get("subject")
            minutes.lecturer = class_info.get("lecturer")

            # Notionアップロード
            notion_result = None
            if args.get("upload_to_notion", False):
                notion_result = notion_service.upload_minutes(minutes)

            # 処理時間を計算
            elapsed_time = time.time() - file_start_time
            logger.info(f"ファイルの処理が完了しました: {file_path} (処理時間: {elapsed_time:.2f}秒)")

            # 結果を返す
            return {
                "success": True,
                "file_path": str(file_path),
                "media_file": media_file,
                "transcription_result": transcription_result,
                "minutes": minutes,
                "notion_result": notion_result,
                "elapsed_time": elapsed_time
            }
        except Exception as e:
            logger.error(f"ファイルの処理中にエラーが発生しました: {file_path} - {e}")
            return {
                "success": False,
                "file_path": str(file_path),
                "error": str(e)
            }



# シングルトンインスタンス
app = Application()
