"""
メディア処理サービス

このモジュールは、音声・動画ファイルの処理に関するサービスを提供します。
"""
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..domain.media import ExtractedImage, MediaChunk, MediaFile, MediaType, VideoQuality
from ..infrastructure.config import config_manager
from ..infrastructure.logger import logger
from ..infrastructure.storage import storage_manager
from ..utils.ffmpeg import ffmpeg_wrapper
from ..utils.parallel import ParallelExecutionMode, parallel_map


class MediaProcessorService:
    """メディア処理サービスクラス"""

    def __init__(self):
        """初期化"""
        self.temp_dir = Path(config_manager.get("temp_dir", "temp"))
        if not self.temp_dir.exists():
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        # 設定からチャンク分割の長さを取得（デフォルトは600秒）
        self.chunk_duration = config_manager.get("media_processor.chunk_duration", 600)

    def process_media_file(self, file_path: Union[str, Path]) -> MediaFile:
        """
        メディアファイルを処理

        Args:
            file_path: メディアファイルのパス

        Returns:
            処理されたMediaFileオブジェクト
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"ファイルが存在しません: {file_path}")
            raise FileNotFoundError(f"ファイルが存在しません: {file_path}")

        # メディアタイプを判定
        media_type = self._determine_media_type(file_path)

        # 長さを取得
        duration = ffmpeg_wrapper.get_duration(file_path)

        # MediaFileオブジェクトを作成
        media_file = MediaFile(
            file_path=file_path,
            media_type=media_type,
            duration=duration
        )

        # 動画の場合は品質を判定
        if media_file.is_video:
            is_dark = ffmpeg_wrapper.is_video_dark(file_path)
            media_file.video_quality = VideoQuality.DARK if is_dark else VideoQuality.NORMAL

        logger.info(f"メディアファイルを処理しました: {file_path} (タイプ: {media_type.name}, 長さ: {duration:.2f}秒)")
        return media_file

    def _determine_media_type(self, file_path: Path) -> MediaType:
        """
        ファイルのメディアタイプを判定

        Args:
            file_path: ファイルパス

        Returns:
            メディアタイプ
        """
        if ffmpeg_wrapper.is_video_file(file_path):
            return MediaType.VIDEO
        elif ffmpeg_wrapper.is_audio_file(file_path):
            return MediaType.AUDIO
        else:
            return MediaType.UNKNOWN

    def extract_audio_from_video(self, video_file: MediaFile) -> MediaFile:
        """
        動画から音声を抽出

        Args:
            video_file: 動画ファイル

        Returns:
            抽出した音声ファイル
        """
        if not video_file.is_video:
            logger.warning(f"動画ファイルではありません: {video_file.file_path}")
            return video_file

        # 出力ファイルパスを生成
        output_path = self.temp_dir / f"{video_file.file_path.stem}_audio.aac"

        # 音声を抽出
        ffmpeg_wrapper.extract_audio(video_file.file_path, output_path)

        # 新しいMediaFileオブジェクトを作成
        audio_file = MediaFile(
            file_path=output_path,
            media_type=MediaType.AUDIO,
            duration=video_file.duration
        )

        logger.info(f"動画から音声を抽出しました: {video_file.file_path} -> {output_path}")
        return audio_file

    def split_media_file(self, media_file: MediaFile, chunk_duration: int = None) -> MediaFile:
        """
        メディアファイルをチャンクに分割

        Args:
            media_file: メディアファイル
            chunk_duration: チャンクの長さ（秒）。指定しない場合は設定ファイルの値を使用

        Returns:
            チャンクに分割されたMediaFileオブジェクト
        """
        # chunk_durationが指定されていない場合は設定値を使用
        if chunk_duration is None:
            chunk_duration = self.chunk_duration

        # 分割が必要ない場合はそのまま返す
        if not media_file.is_long_media:
            logger.info(f"メディアファイルは分割が必要ありません: {media_file.file_path} (長さ: {media_file.duration:.2f}秒)")
            return media_file

        # 出力ディレクトリを生成
        output_dir = self.temp_dir / f"{media_file.file_path.stem}_chunks"
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)

        # ファイルを分割（設定から取得したチャンク長を使用）
        logger.info(f"メディアファイルを分割します: {media_file.file_path} (チャンク長: {chunk_duration}秒)")
        chunk_files = ffmpeg_wrapper.split_audio(media_file.file_path, output_dir, chunk_duration)

        # チャンク情報を作成
        chunks = []
        for i, chunk_file in enumerate(chunk_files):
            start_time = i * chunk_duration
            end_time = min((i + 1) * chunk_duration, media_file.duration)

            chunk = MediaChunk(
                start_time=start_time,
                end_time=end_time,
                file_path=chunk_file,
                index=i
            )
            chunks.append(chunk)

        # MediaFileオブジェクトを更新
        media_file.chunks = chunks

        logger.info(f"メディアファイルを{len(chunks)}個のチャンクに分割しました: {media_file.file_path}")
        return media_file

    def extract_images_from_video(self, video_file: MediaFile, 
                                 interval: int = 60, quality: int = 3) -> List[ExtractedImage]:
        logger.warning(f"Interval-based image extraction (extract_images_from_video) is disabled. Called for {video_file.file_path}")
        return []
        # """
        # 動画から一定間隔で画像を抽出

        # Args:
        #     video_file: 動画ファイル
        #     interval: 抽出間隔（秒）
        #     quality: 画像品質（1-5、高いほど高品質）

        # Returns:
        #     抽出した画像のリスト
        # """
        # if not video_file.is_video:
        #     logger.warning(f"動画ファイルではありません: {video_file.file_path}")
        #     return []

        # # 出力ディレクトリを生成
        # output_dir = storage_manager.get_output_dir("images") / video_file.file_path.stem
        # if not output_dir.exists():
        #     output_dir.mkdir(parents=True, exist_ok=True)

        # # 画像を抽出
        # extracted = ffmpeg_wrapper.extract_images_at_intervals(
        #     video_file.file_path, output_dir, interval, quality
        # )

        # # ExtractedImageオブジェクトを作成
        # images = []
        # for timestamp, image_path in extracted:
        #     image = ExtractedImage(
        #         file_path=image_path,
        #         timestamp=timestamp,
        #         source_media=video_file.file_path
        #     )
        #     images.append(image)

        # logger.info(f"動画から{len(images)}枚の画像を抽出しました: {video_file.file_path}")
        # return images

    def extract_image_at_timestamp(self, video_file: MediaFile, timestamp: float, 
                                  quality: int = 3, output_filename: Optional[str] = None) -> Optional[ExtractedImage]:
        """
        動画から特定の時間の画像を抽出

        Args:
            video_file: 動画ファイル
            timestamp: 抽出する時間（秒）
            quality: 画像品質（1-5、高いほど高品質）
            output_filename: (Optional) 出力ファイル名

        Returns:
            抽出した画像、失敗した場合はNone
        """
        if not video_file.is_video:
            logger.warning(f"動画ファイルではありません: {video_file.file_path}")
            return None

        # タイムスタンプが範囲外の場合
        if timestamp < 0 or timestamp > video_file.duration:
            logger.warning(f"タイムスタンプが範囲外です: {timestamp} (動画の長さ: {video_file.duration:.2f}秒)")
            return None

        # 出力ディレクトリを生成
        output_dir = storage_manager.get_output_dir("images") / video_file.file_path.stem
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)

        if output_filename:
            # Ensure the output_filename does not contain path traversal components for security
            safe_output_filename = Path(output_filename).name
            output_file = output_dir / safe_output_filename
        else:
            # Default filename if not provided (ensure it still has an extension, e.g. .jpg)
            output_file = output_dir / f"{video_file.file_path.stem}_{int(timestamp):06d}.jpg"
            # Note: The ffmpeg_wrapper.extract_image will determine the actual output format.
            # If output_filename has .webp, ffmpeg_wrapper must support it.

        try:
            # 画像を抽出
            # The ffmpeg_wrapper.extract_image call needs to handle the output_file path correctly.
            # If output_filename specifies a .webp, ffmpeg_wrapper must be able to produce it.
            ffmpeg_wrapper.extract_image(video_file.file_path, output_file, timestamp, quality)

            # ExtractedImageオブジェクトを作成
            image = ExtractedImage(
                file_path=output_file,
                timestamp=timestamp,
                source_media=video_file.file_path
            )

            logger.info(f"動画から画像を抽出しました: {video_file.file_path} -> {output_file} (時間: {timestamp:.2f}秒)")
            return image
        except Exception as e:
            logger.error(f"画像抽出に失敗しました: {output_file} - {e}", exc_info=True) # Added output_file to log
            return None

    def detect_scene_changes(self, video_file: MediaFile, 
                            threshold: float = 0.3, min_scene_duration: float = 2.0) -> List[float]:
        """
        動画からシーン変化を検出

        Args:
            video_file: 動画ファイル
            threshold: 検出閾値（0.0-1.0、高いほど厳しい）
            min_scene_duration: 最小シーン長（秒）

        Returns:
            シーン変化のタイムスタンプのリスト
        """
        if not video_file.is_video:
            logger.warning(f"動画ファイルではありません: {video_file.file_path}")
            return []

        # 一時ファイルを作成
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # FFmpegでシーン検出を実行
            cmd = [
                ffmpeg_wrapper.ffmpeg_path,
                "-i", str(video_file.file_path),
                "-filter:v", f"select='gt(scene,{threshold})',showinfo",
                "-f", "null",
                "-"
            ]

            import subprocess
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                check=False
            )

            # 出力からタイムスタンプを抽出
            import re
            timestamps = []
            last_timestamp = 0.0

            for line in result.stderr.splitlines():
                # showinfo フィルタの出力からタイムスタンプを抽出
                match = re.search(r"pts_time:(\d+\.\d+)", line)
                if match:
                    timestamp = float(match.group(1))

                    # 最小シーン長を確認
                    if timestamp - last_timestamp >= min_scene_duration:
                        timestamps.append(timestamp)
                        last_timestamp = timestamp

            logger.info(f"動画から{len(timestamps)}個のシーン変化を検出しました: {video_file.file_path}")
            return timestamps
        except Exception as e:
            logger.error(f"シーン検出に失敗しました: {e}")
            return []
        finally:
            # 一時ファイルを削除
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def extract_images_at_scene_changes(self, video_file: MediaFile, 
                                       quality: int = 3) -> List[ExtractedImage]:
        """
        動画からシーン変化の画像を抽出

        Args:
            video_file: 動画ファイル
            quality: 画像品質（1-5、高いほど高品質）

        Returns:
            抽出した画像のリスト
        """
        # シーン変化を検出
        timestamps = self.detect_scene_changes(video_file)

        if not timestamps:
            logger.warning(f"シーン変化が検出されませんでした: {video_file.file_path}")
            return []

        # 各シーン変化の画像を抽出
        images = []
        for timestamp in timestamps:
            image = self.extract_image_at_timestamp(video_file, timestamp, quality)
            if image:
                images.append(image)

        logger.info(f"シーン変化から{len(images)}枚の画像を抽出しました: {video_file.file_path}")
        return images

    def batch_process_media_files(self, file_paths: List[Union[str, Path]]) -> List[MediaFile]:
        """
        複数のメディアファイルを一括処理

        Args:
            file_paths: メディアファイルのパスのリスト

        Returns:
            処理されたMediaFileオブジェクトのリスト
        """
        # 並列処理でメディアファイルを処理（APIの動作不良を防ぐため1スレッドに制限）
        media_files = parallel_map(
            lambda path: self.process_media_file(path),
            file_paths,
            ParallelExecutionMode.THREAD,
            max_workers=1
        )

        logger.info(f"{len(media_files)}個のメディアファイルを処理しました")
        return media_files

    def save_media_info(self, media_file: MediaFile) -> Path:
        """
        メディアファイル情報をJSONファイルとして保存

        Args:
            media_file: メディアファイル

        Returns:
            保存したJSONファイルのパス
        """
        # メディアファイル情報を辞書に変換
        info = {
            "file_path": str(media_file.file_path),
            "media_type": media_file.media_type.name,
            "duration": media_file.duration,
            "is_long_media": media_file.is_long_media
        }

        # 動画の場合は品質情報を追加
        if media_file.is_video and media_file.video_quality:
            info["video_quality"] = media_file.video_quality.name

        # チャンク情報を追加
        if media_file.has_chunks:
            info["chunks"] = [
                {
                    "index": chunk.index,
                    "start_time": chunk.start_time,
                    "end_time": chunk.end_time,
                    "file_path": str(chunk.file_path)
                }
                for chunk in media_file.chunks
            ]

        # JSONファイルとして保存
        output_file = storage_manager.get_output_dir() / f"{media_file.file_path.stem}_media_info.json"
        storage_manager.save_json(info, output_file)

        logger.info(f"メディアファイル情報を保存しました: {output_file}")
        return output_file


# シングルトンインスタンス
media_processor_service = MediaProcessorService()
