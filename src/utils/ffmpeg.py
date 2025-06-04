"""
FFmpegラッパーモジュール

このモジュールは、FFmpegを使用した動画・音声処理のラッパー機能を提供します。
"""
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..infrastructure.config import config_manager
from ..infrastructure.logger import logger


class FFmpegWrapper:
    """FFmpegラッパークラス"""

    def __init__(self):
        """初期化"""
        self.ffmpeg_path = config_manager.get("ffmpeg_path", "ffmpeg")
        self.ffprobe_path = config_manager.get("ffprobe_path", "ffprobe")
        self._check_ffmpeg()

    def _check_ffmpeg(self) -> None:
        """
        FFmpegの存在を確認
        """
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if result.returncode != 0:
                logger.warning("FFmpegが見つかりません。パスを確認してください。")
        except FileNotFoundError:
            logger.warning("FFmpegが見つかりません。パスを確認してください。")

    def get_media_info(self, file_path: Union[str, Path]) -> Dict:
        """
        メディアファイルの情報を取得
        
        Args:
            file_path: メディアファイルのパス
            
        Returns:
            メディアファイルの情報
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"ファイルが存在しません: {file_path}")
            raise FileNotFoundError(f"ファイルが存在しません: {file_path}")
            
        try:
            result = subprocess.run(
                [
                    self.ffprobe_path,
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    str(file_path)
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            info = json.loads(result.stdout)
            logger.debug(f"メディア情報を取得しました: {file_path}")
            return info
        except subprocess.CalledProcessError as e:
            logger.error(f"メディア情報の取得に失敗しました: {e}")
            raise RuntimeError(f"メディア情報の取得に失敗しました: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"メディア情報のJSONデコードに失敗しました: {e}")
            raise RuntimeError(f"メディア情報のJSONデコードに失敗しました: {e}")

    def get_duration(self, file_path: Union[str, Path]) -> float:
        """
        メディアファイルの長さを取得（秒）
        
        Args:
            file_path: メディアファイルのパス
            
        Returns:
            メディアファイルの長さ（秒）
        """
        info = self.get_media_info(file_path)
        
        if "format" in info and "duration" in info["format"]:
            return float(info["format"]["duration"])
        
        logger.warning(f"メディアファイルの長さを取得できませんでした: {file_path}")
        return 0.0

    def is_video_file(self, file_path: Union[str, Path]) -> bool:
        """
        ファイルが動画ファイルかどうかを判定
        
        Args:
            file_path: ファイルパス
            
        Returns:
            動画ファイルの場合はTrue、それ以外はFalse
        """
        try:
            info = self.get_media_info(file_path)
            
            # ストリーム情報から動画ストリームを探す
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    return True
                    
            return False
        except Exception as e:
            logger.error(f"ファイルタイプの判定に失敗しました: {e}")
            return False

    def is_audio_file(self, file_path: Union[str, Path]) -> bool:
        """
        ファイルが音声ファイルかどうかを判定
        
        Args:
            file_path: ファイルパス
            
        Returns:
            音声ファイルの場合はTrue、それ以外はFalse
        """
        try:
            info = self.get_media_info(file_path)
            
            # ストリーム情報から音声ストリームを探す
            has_audio = False
            has_video = False
            
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "audio":
                    has_audio = True
                elif stream.get("codec_type") == "video":
                    has_video = True
                    
            # 音声ストリームがあり、動画ストリームがない場合は音声ファイル
            return has_audio and not has_video
        except Exception as e:
            logger.error(f"ファイルタイプの判定に失敗しました: {e}")
            return False

    def is_video_dark(self, file_path: Union[str, Path], sample_count: int = 10) -> bool:
        """
        動画が暗いかどうかを判定
        
        Args:
            file_path: 動画ファイルのパス
            sample_count: サンプリングする画像の数
            
        Returns:
            暗い動画の場合はTrue、それ以外はFalse
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"ファイルが存在しません: {file_path}")
            raise FileNotFoundError(f"ファイルが存在しません: {file_path}")
            
        if not self.is_video_file(file_path):
            logger.warning(f"動画ファイルではありません: {file_path}")
            return False
            
        try:
            # 動画の長さを取得
            duration = self.get_duration(file_path)
            
            # サンプリング間隔を計算
            interval = duration / (sample_count + 1)
            
            # 暗い画像のカウント
            dark_count = 0
            
            # 各サンプリングポイントで明るさを測定
            for i in range(1, sample_count + 1):
                time_pos = interval * i
                
                # FFmpegを使用して明るさを測定
                result = subprocess.run(
                    [
                        self.ffmpeg_path,
                        "-ss", str(time_pos),
                        "-i", str(file_path),
                        "-vframes", "1",
                        "-filter:v", "signalstats",
                        "-f", "null",
                        "-"
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                # 明るさの情報を抽出
                match = re.search(r"YAVG:(\d+\.\d+)", result.stderr)
                if match:
                    avg_brightness = float(match.group(1))
                    
                    # 明るさの閾値（0-255の範囲で、低いほど暗い）
                    threshold = 50.0
                    
                    if avg_brightness < threshold:
                        dark_count += 1
                        
            # 半分以上のサンプルが暗い場合、動画は暗いと判断
            return dark_count >= (sample_count / 2)
        except Exception as e:
            logger.error(f"動画の明るさ判定に失敗しました: {e}")
            return False

    def extract_audio(self, video_path: Union[str, Path], output_path: Union[str, Path]) -> Path:
        """
        動画から音声を抽出
        
        Args:
            video_path: 動画ファイルのパス
            output_path: 出力する音声ファイルのパス
            
        Returns:
            出力した音声ファイルのパス
        """
        video_path = Path(video_path)
        output_path = Path(output_path)
        
        if not video_path.exists():
            logger.error(f"ファイルが存在しません: {video_path}")
            raise FileNotFoundError(f"ファイルが存在しません: {video_path}")
            
        # 出力ディレクトリが存在しない場合は作成
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
        try:
            subprocess.run(
                [
                    self.ffmpeg_path,
                    "-i", str(video_path),
                    "-vn",  # 映像を除外
                    "-acodec", "aac",  # AACコーデックを使用
                    "-b:a", "192k",  # ビットレート
                    "-y",  # 既存ファイルを上書き
                    str(output_path)
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            
            logger.info(f"音声を抽出しました: {video_path} -> {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"音声抽出に失敗しました: {e}")
            raise RuntimeError(f"音声抽出に失敗しました: {e}")

    def split_audio(self, audio_path: Union[str, Path], output_dir: Union[str, Path], 
                   chunk_duration: int = 600) -> List[Path]:
        """
        音声ファイルを指定した長さのチャンクに分割
        
        Args:
            audio_path: 音声ファイルのパス
            output_dir: 出力ディレクトリ
            chunk_duration: チャンクの長さ（秒）
            
        Returns:
            分割したチャンクファイルのパスリスト
        """
        audio_path = Path(audio_path)
        output_dir = Path(output_dir)
        
        if not audio_path.exists():
            logger.error(f"ファイルが存在しません: {audio_path}")
            raise FileNotFoundError(f"ファイルが存在しません: {audio_path}")
            
        # 出力ディレクトリが存在しない場合は作成
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
            
        # 音声ファイルの長さを取得
        duration = self.get_duration(audio_path)
        
        # チャンク数を計算
        chunk_count = int(duration / chunk_duration) + (1 if duration % chunk_duration > 0 else 0)
        
        chunk_files = []
        
        try:
            for i in range(chunk_count):
                start_time = i * chunk_duration
                
                # 最後のチャンクの場合、残りの時間を使用
                if i == chunk_count - 1:
                    end_time = duration
                else:
                    end_time = (i + 1) * chunk_duration
                
                # 出力ファイル名
                output_file = output_dir / f"{audio_path.stem}_chunk{i:03d}{audio_path.suffix}"
                
                # FFmpegを使用してチャンクを抽出
                subprocess.run(
                    [
                        self.ffmpeg_path,
                        "-i", str(audio_path),
                        "-ss", str(start_time),
                        "-to", str(end_time),
                        "-c", "copy",  # コーデックをコピー
                        "-y",  # 既存ファイルを上書き
                        str(output_file)
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )
                
                chunk_files.append(output_file)
                logger.debug(f"音声チャンクを作成しました: {output_file} ({start_time}s-{end_time}s)")
                
            logger.info(f"音声ファイルを{chunk_count}個のチャンクに分割しました: {audio_path}")
            return chunk_files
        except subprocess.CalledProcessError as e:
            logger.error(f"音声分割に失敗しました: {e}")
            raise RuntimeError(f"音声分割に失敗しました: {e}")

    def extract_image(self, video_path: Union[str, Path], output_path: Union[str, Path], 
                     timestamp: float, quality: int = 3) -> Path:
        """
        動画から特定の時間の画像を抽出
        
        Args:
            video_path: 動画ファイルのパス
            output_path: 出力する画像ファイルのパス
            timestamp: 抽出する時間（秒）
            quality: 画像品質（1-5、高いほど高品質）
            
        Returns:
            出力した画像ファイルのパス
        """
        video_path = Path(video_path)
        output_path = Path(output_path)
        
        if not video_path.exists():
            logger.error(f"ファイルが存在しません: {video_path}")
            raise FileNotFoundError(f"ファイルが存在しません: {video_path}")
            
        # 出力ディレクトリが存在しない場合は作成
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
        # 品質設定
        quality_settings = {
            1: ["-q:v", "10", "-vf", "scale=640:-1"],  # 低品質
            2: ["-q:v", "5", "-vf", "scale=960:-1"],   # 中低品質
            3: ["-q:v", "3", "-vf", "scale=1280:-1"],  # 中品質
            4: ["-q:v", "2", "-vf", "scale=1920:-1"],  # 中高品質
            5: ["-q:v", "1", "-vf", "scale=2560:-1"]   # 高品質
        }
        
        # 品質設定の取得（範囲外の場合はデフォルト値を使用）
        q_setting = quality_settings.get(quality, quality_settings[3])
        
        try:
            subprocess.run(
                [
                    self.ffmpeg_path,
                    "-ss", str(timestamp),
                    "-i", str(video_path),
                    "-frames:v", "1",
                    *q_setting,
                    "-y",  # 既存ファイルを上書き
                    str(output_path)
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            
            logger.debug(f"画像を抽出しました: {video_path} -> {output_path} (時間: {timestamp}秒)")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"画像抽出に失敗しました: {e}")
            raise RuntimeError(f"画像抽出に失敗しました: {e}")

    def extract_images_at_intervals(self, video_path: Union[str, Path], output_dir: Union[str, Path], 
                                   interval: int = 60, quality: int = 3) -> List[Tuple[float, Path]]:
        """
        動画から一定間隔で画像を抽出
        
        Args:
            video_path: 動画ファイルのパス
            output_dir: 出力ディレクトリ
            interval: 抽出間隔（秒）
            quality: 画像品質（1-5、高いほど高品質）
            
        Returns:
            (タイムスタンプ, 画像パス)のタプルのリスト
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        
        if not video_path.exists():
            logger.error(f"ファイルが存在しません: {video_path}")
            raise FileNotFoundError(f"ファイルが存在しません: {video_path}")
            
        # 出力ディレクトリが存在しない場合は作成
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
            
        # 動画の長さを取得
        duration = self.get_duration(video_path)
        
        # 抽出する時間のリストを作成
        timestamps = [i for i in range(0, int(duration), interval)]
        
        # 最後のフレームが含まれていない場合は追加
        if int(duration) - timestamps[-1] > interval / 2:
            timestamps.append(int(duration))
            
        result = []
        
        for timestamp in timestamps:
            # 出力ファイル名
            output_file = output_dir / f"{video_path.stem}_{timestamp:06d}.jpg"
            
            # 画像を抽出
            try:
                self.extract_image(video_path, output_file, timestamp, quality)
                result.append((timestamp, output_file))
            except Exception as e:
                logger.warning(f"時間 {timestamp}秒 の画像抽出に失敗しました: {e}")
                
        logger.info(f"動画から{len(result)}枚の画像を抽出しました: {video_path}")
        return result


# シングルトンインスタンス
ffmpeg_wrapper = FFmpegWrapper()