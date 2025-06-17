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
from ..domain.minutes import Minutes
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

                # 各チャンクを個別に文字起こし
                if media_file.has_chunks:
                    logger.info(f"各チャンクを個別に文字起こしします: {len(media_file.chunks)}個のチャンク")
                    chunk_transcriptions = []

                    for chunk in media_file.chunks:
                        logger.info(f"チャンク {chunk.index} を文字起こしします: {chunk.file_path}")
                        # チャンクから一時的なMediaFileオブジェクトを作成
                        chunk_media = MediaFile(
                            file_path=chunk.file_path,
                            media_type=media_file.media_type,
                            duration=chunk.end_time - chunk.start_time
                        )
                        # チャンクを文字起こし
                        chunk_result = transcription_service.transcribe_audio(chunk_media)

                        # 文字起こしに失敗した場合はスキップ
                        if chunk_result.is_failed:
                            logger.warning(f"チャンク {chunk.index} の文字起こしに失敗しました: {chunk.file_path}")
                            continue

                        chunk_transcriptions.append(chunk_result)

                    # すべてのチャンクの文字起こし結果を結合
                    if chunk_transcriptions:
                        logger.info(f"すべてのチャンクの文字起こし結果を結合します: {len(chunk_transcriptions)}個の結果")
                        # 元のメディアファイルのパスを渡して結合
                        transcription_result = transcription_service.combine_transcriptions(
                            chunk_transcriptions,
                            original_source_file=media_file.file_path
                        )
                    else:
                        logger.error(f"文字起こしに成功したチャンクがありません: {media_file.file_path}")
                        return {
                            "success": False,
                            "file_path": str(file_path),
                            "error": "文字起こしに成功したチャンクがありません"
                        }
                else:
                    # チャンクがない場合は通常の文字起こし
                    logger.info(f"チャンクがないため、通常の文字起こしを実行します: {media_file.file_path}")
                    transcription_result = transcription_service.transcribe_audio(media_file)
            else:
                # 長時間メディアでない場合は通常の文字起こし
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
                # 関連ページの設定（例：同じ科目の議事録を関連付ける）
                self._set_related_pages(minutes)

                # 親ページの設定（例：MOCページを親ページに設定）
                self._set_parent_page(minutes)

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



    def _set_related_pages(self, minutes: Minutes) -> None:
        """
        関連ページを設定

        Args:
            minutes: 議事録
        """
        try:
            # 同じ科目の議事録を関連ページとして設定する例
            if minutes.subject:
                logger.info(f"同じ科目の議事録を関連ページとして検索します: {minutes.subject}")

                # 実際の実装では、Notionデータベースから同じ科目の議事録を検索する
                # 例: 
                # query_params = {
                #     "filter": {
                #         "property": "科目",
                #         "select": {
                #             "equals": minutes.subject
                #         }
                #     }
                # }
                # response = notion_client.databases.query(database_id=self.config.get("notion.database_id"), **query_params)
                # 
                # for page in response["results"]:
                #     page_id = page["id"]
                #     page_title = page["properties"]["タイトル"]["title"][0]["text"]["content"]
                #     
                #     # 自分自身は除外
                #     if page_title != minutes.title:
                #         minutes.add_related_page(page_id, page_title)

                # モック実装（実際の実装では削除）
                # ランダムなページIDとタイトルを生成
                import uuid
                for i in range(2):  # 2つの関連ページを追加
                    page_id = str(uuid.uuid4())
                    page_title = f"{minutes.subject} 議事録 {i+1}"
                    minutes.add_related_page(page_id, page_title)
                    logger.info(f"関連ページを追加しました: {page_title} ({page_id})")
        except Exception as e:
            logger.warning(f"関連ページの設定中にエラーが発生しました: {e}")

    def _set_parent_page(self, minutes: Minutes) -> None:
        """
        親ページを設定
        詳細なチェックを行い、MOCページを親ページとして設定します

        Args:
            minutes: 議事録
        """
        try:
            # MOCページを親ページとして設定
            moc_page_id = self.config.get("notion.moc_page_id")

            # MOCページIDの検証
            if not moc_page_id:
                logger.warning("MOCページIDが設定されていません。親ページは設定されません。")
                return

            # MOCページIDの形式チェック
            import uuid
            try:
                uuid.UUID(moc_page_id)
            except ValueError:
                logger.error(f"無効なMOCページIDの形式です: {moc_page_id}")
                raise ValueError(f"無効なMOCページIDの形式です: {moc_page_id}")

            # MOCページの存在確認（実際の実装ではNotion APIを使用）
            # 例:
            # try:
            #     notion_client.pages.retrieve(page_id=moc_page_id)
            # except Exception as e:
            #     logger.error(f"MOCページが存在しません: {moc_page_id} - {e}")
            #     raise ValueError(f"MOCページが存在しません: {moc_page_id}")

            # 親ページとして設定
            logger.info(f"MOCページを親ページとして設定します: {moc_page_id}")
            minutes.set_parent_page(moc_page_id)

            # 設定の確認
            if minutes.parent_page_id != moc_page_id:
                logger.error("親ページの設定に失敗しました")
                raise RuntimeError("親ページの設定に失敗しました")

            logger.info(f"親ページを正常に設定しました: {moc_page_id}")

        except Exception as e:
            logger.error(f"親ページの設定中にエラーが発生しました: {e}")
            # エラーは記録するが、処理は続行する（親ページがなくても議事録は作成可能）
            # 必要に応じて例外を再スローする場合:
            # raise RuntimeError(f"親ページの設定に失敗しました: {e}")


# シングルトンインスタンス
app = Application()
