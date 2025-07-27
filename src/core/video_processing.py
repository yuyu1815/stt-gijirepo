"""
STT議事録システム - 動画処理機能

動画ファイルの解析、明度チェック、音声抽出、フォーマット変換などの機能を提供
"""

import os
import tempfile
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import logging

import ffmpeg

from ..utils import get_logger, FileProcessingError
from ..utils.retry_utils import method_error_handler

# OpenCVのインポートを試行（オプション）
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


class VideoProcessor:
    """動画処理を担当するクラス"""
    
    def __init__(self):
        self.logger = get_logger(__name__)

    
    @method_error_handler(FileProcessingError, "動画メタデータの取得に失敗", passthrough_exceptions=[FileNotFoundError])
    def get_video_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        動画ファイルのメタデータを取得
        
        Args:
            file_path: 動画ファイルのパス
            
        Returns:
            Dict: メタデータ情報
        """
        if not os.path.exists(file_path):
            raise FileProcessingError(f"ファイルが見つかりません: {file_path}")
        
        self.logger.info(f"動画メタデータ取得中: {file_path}")
        probe = ffmpeg.probe(file_path)
        
        # 動画ストリーム情報
        video_stream = next(
            (stream for stream in probe['streams'] if stream['codec_type'] == 'video'),
            None
        )
        
        # 音声ストリーム情報
        audio_stream = next(
            (stream for stream in probe['streams'] if stream['codec_type'] == 'audio'),
            None
        )
        
        metadata = {
            'duration': float(probe['format']['duration']),
            'file_size': int(probe['format']['size']),
            'format_name': probe['format']['format_name'],
            'has_video': video_stream is not None,
            'has_audio': audio_stream is not None
        }
        
        if video_stream:
            metadata.update({
                'width': int(video_stream['width']),
                'height': int(video_stream['height']),
                'fps': eval(video_stream['r_frame_rate']),
                'video_codec': video_stream['codec_name'],
                'pixel_format': video_stream.get('pix_fmt', 'unknown')
            })
        
        if audio_stream:
            metadata.update({
                'audio_sample_rate': int(audio_stream['sample_rate']),
                'audio_channels': int(audio_stream['channels']),
                'audio_codec': audio_stream['codec_name']
            })
        
        self.logger.info(f"メタデータ取得完了: {metadata}")
        return metadata
    
    @method_error_handler(FileProcessingError, "動画明度解析に失敗", passthrough_exceptions=[FileNotFoundError])
    def analyze_video_brightness(self, file_path: str, sample_count: int = 10) -> Dict[str, Any]:
        """
        動画の明度を解析
        
        Args:
            file_path: 動画ファイルのパス
            sample_count: サンプリングするフレーム数
            
        Returns:
            Dict: 明度解析結果
        """
        if not HAS_OPENCV:
            self.logger.warning("OpenCVが利用できません。FFmpegベースの簡易解析を使用します。")
            return self._analyze_brightness_with_ffmpeg(file_path)
        
        self.logger.info(f"動画明度解析開始: {file_path}")
        
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            raise FileProcessingError("動画ファイルを開けませんでした")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = max(1, total_frames // sample_count)
        
        brightness_values = []
        
        for i in range(0, total_frames, frame_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # グレースケールに変換して平均明度を計算
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness = np.mean(gray)
            brightness_values.append(brightness)
        
        cap.release()
        
        if not brightness_values:
            raise FileProcessingError("フレームの読み取りに失敗しました")
        
        avg_brightness = np.mean(brightness_values)
        min_brightness = np.min(brightness_values)
        max_brightness = np.max(brightness_values)
        std_brightness = np.std(brightness_values)
        
        # 暗い動画の判定（平均明度が50以下を暗いと判定）
        is_dark = avg_brightness < 50
        
        result = {
            'average_brightness': float(avg_brightness),
            'min_brightness': float(min_brightness),
            'max_brightness': float(max_brightness),
            'std_brightness': float(std_brightness),
            'is_dark': is_dark,
            'sample_count': len(brightness_values),
            'analysis_method': 'opencv'
        }
        
        self.logger.info(f"明度解析完了: 平均={avg_brightness:.2f}, 暗い動画={is_dark}")
        return result
    
    @method_error_handler(FileProcessingError, "FFmpeg明度解析に失敗")
    def _analyze_brightness_with_ffmpeg(self, file_path: str) -> Dict[str, Any]:
        """
        FFmpegを使用した簡易明度解析
        
        Args:
            file_path: 動画ファイルのパス
            
        Returns:
            Dict: 明度解析結果
        """
        # FFmpegのhistogramフィルターを使用して明度情報を取得
        # 簡易的な実装として、ファイルサイズと解像度から推定
        metadata = self.get_video_metadata(file_path)
        
        # 簡易判定: 低解像度または小さいファイルサイズの場合は暗い可能性が高い
        width = metadata.get('width', 0)
        height = metadata.get('height', 0)
        file_size = metadata.get('file_size', 0)
        duration = metadata.get('duration', 1)
        
        # ビットレートベースの簡易判定
        bitrate = (file_size * 8) / duration if duration > 0 else 0
        
        # 低ビットレート（1Mbps以下）の場合は暗い動画の可能性
        is_dark = bitrate < 1000000 or (width * height) < 480 * 360
        
        result = {
            'average_brightness': 128.0,  # デフォルト値
            'min_brightness': 0.0,
            'max_brightness': 255.0,
            'std_brightness': 64.0,
            'is_dark': is_dark,
            'sample_count': 1,
            'analysis_method': 'ffmpeg_estimation',
            'estimated_bitrate': bitrate
        }
        
        self.logger.info(f"FFmpeg簡易明度解析完了: ビットレート={bitrate:.0f}, 暗い動画={is_dark}")
        return result
    
    @method_error_handler(FileProcessingError, "音声抽出に失敗", passthrough_exceptions=[FileNotFoundError])
    def extract_audio_from_video(self, video_path: str, output_path: Optional[str] = None) -> str:
        """
        動画ファイルから音声を抽出
        
        Args:
            video_path: 動画ファイルパス
            output_path: 出力音声ファイルパス
            
        Returns:
            str: 抽出された音声ファイルのパス
        """
        if output_path is None:
            # 一時ファイルを作成
            temp_fd, output_path = tempfile.mkstemp(suffix='.wav')
            os.close(temp_fd)
        
        self.logger.info(f"動画から音声抽出開始: {video_path} -> {output_path}")
        
        try:
            (
                ffmpeg
                .input(video_path)
                .output(
                    output_path,
                    acodec='pcm_s16le',  # 16-bit PCM
                    ac=1,                # モノラル
                    ar='16000'           # 16kHz サンプリングレート
                )
                .overwrite_output()
                .run(quiet=True, capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            error_message = e.stderr.decode() if e.stderr else str(e)
            raise FileProcessingError(f"FFmpeg音声抽出エラー: {error_message}")
        
        # 出力ファイルの存在確認
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise FileProcessingError("音声抽出に失敗しました（出力ファイルが空です）")
        
        self.logger.info("音声抽出完了")
        return output_path
    
    @method_error_handler(FileProcessingError, "動画フォーマット変換に失敗", passthrough_exceptions=[FileNotFoundError])
    def convert_video_format(
        self, 
        input_path: str, 
        output_path: str,
        target_format: str = "mp4",
        video_codec: str = "libx264",
        audio_codec: str = "aac"
    ) -> str:
        """
        動画フォーマットを変換
        
        Args:
            input_path: 入力動画ファイルパス
            output_path: 出力動画ファイルパス
            target_format: 出力フォーマット
            video_codec: 動画コーデック
            audio_codec: 音声コーデック
            
        Returns:
            str: 変換後のファイルパス
        """
        self.logger.info(f"動画フォーマット変換開始: {input_path} -> {output_path}")
        
        try:
            (
                ffmpeg
                .input(input_path)
                .output(
                    output_path,
                    vcodec=video_codec,
                    acodec=audio_codec,
                    format=target_format
                )
                .overwrite_output()
                .run(quiet=True, capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            error_message = e.stderr.decode() if e.stderr else str(e)
            raise FileProcessingError(f"FFmpeg動画変換エラー: {error_message}")
        
        self.logger.info("動画フォーマット変換完了")
        return output_path
    
    @method_error_handler(FileProcessingError, "フレーム抽出に失敗", passthrough_exceptions=[FileNotFoundError])
    def extract_frames(
        self, 
        video_path: str, 
        output_dir: str,
        frame_rate: float = 1.0,
        image_format: str = "jpg"
    ) -> list[str]:
        """
        動画からフレームを抽出
        
        Args:
            video_path: 動画ファイルパス
            output_dir: 出力ディレクトリ
            frame_rate: 抽出フレームレート（秒あたり）
            image_format: 画像フォーマット
            
        Returns:
            List[str]: 抽出されたフレーム画像のパスリスト
        """
        os.makedirs(output_dir, exist_ok=True)
        
        output_pattern = os.path.join(output_dir, f"frame_%04d.{image_format}")
        
        self.logger.info(f"フレーム抽出開始: {video_path}")
        
        try:
            (
                ffmpeg
                .input(video_path)
                .filter('fps', fps=frame_rate)
                .output(output_pattern)
                .overwrite_output()
                .run(quiet=True, capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            error_message = e.stderr.decode() if e.stderr else str(e)
            raise FileProcessingError(f"FFmpegフレーム抽出エラー: {error_message}")
        
        # 抽出されたファイルのリストを取得
        extracted_files = []
        for file in os.listdir(output_dir):
            if file.startswith("frame_") and file.endswith(f".{image_format}"):
                extracted_files.append(os.path.join(output_dir, file))
        
        extracted_files.sort()
        
        self.logger.info(f"フレーム抽出完了: {len(extracted_files)}フレーム")
        return extracted_files
    
    @method_error_handler(FileProcessingError, "動画長取得に失敗", passthrough_exceptions=[FileNotFoundError])
    def get_video_duration(self, file_path: str) -> float:
        """
        動画の長さを取得
        
        Args:
            file_path: 動画ファイルのパス
            
        Returns:
            float: 動画の長さ（秒）
        """
        metadata = self.get_video_metadata(file_path)
        return metadata['duration']
    
    def is_video_file(self, file_path: str) -> bool:
        """
        ファイルが動画ファイルかどうかを判定
        
        Args:
            file_path: ファイルパス
            
        Returns:
            bool: 動画ファイルの場合True
        """
        # この関数は例外を発生させずに結果を返すため、
        # method_error_handlerデコレータは使用しない
        try:
            metadata = self.get_video_metadata(file_path)
            return metadata.get('has_video', False)
        except Exception:
            # 例外が発生した場合は動画ファイルではないと判断
            self.logger.debug(f"動画ファイル判定: {file_path} - 例外発生のため非動画と判断")
            return False
    
    def cleanup_temp_files(self, file_paths: list[str]) -> int:
        """
        一時ファイルのクリーンアップ
        
        Args:
            file_paths: 削除するファイルパスのリスト
            
        Returns:
            int: 削除したファイル数
        """
        from .file_utils import FileUtils
        return FileUtils.cleanup_files(file_paths, self.logger)
        
    @method_error_handler(FileProcessingError, "動画チャンク分割に失敗", passthrough_exceptions=[FileNotFoundError])
    def split_video_into_chunks(self, file_path: str, chunk_duration: int = 600) -> List[str]:
        """
        動画ファイルを指定された長さのチャンクに分割してファイルに保存
        
        Args:
            file_path: 分割する動画ファイルのパス
            chunk_duration: チャンクの長さ（秒）
            
        Returns:
            List[str]: 分割されたチャンクファイルのパスリスト
        """
        self.logger.info(f"動画ファイルをチャンクに分割開始: {file_path}")
        
        # 動画の長さを取得
        duration = self.get_video_duration(file_path)
        
        # チャンク分割が不要な場合は元のファイルを返す
        if duration <= chunk_duration:
            self.logger.info(f"動画の長さ({duration:.2f}秒)がチャンク長({chunk_duration}秒)以下のため分割不要")
            return [file_path]
        
        # 一時ディレクトリを作成
        temp_dir = tempfile.mkdtemp(prefix="stt_video_chunks_")
        
        # ファイル名のベース部分を取得
        base_name = Path(file_path).stem
        
        # チャンクファイルのパスリスト
        chunk_files = []
        
        # 開始位置（秒）
        start = 0
        chunk_index = 1
        
        while start < duration:
            # チャンクの長さを計算（最後のチャンクは短くなる可能性あり）
            current_chunk_duration = min(chunk_duration, duration - start)
            
            # 出力ファイルパス
            output_path = os.path.join(temp_dir, f"{base_name}_{chunk_index:03d}.mp4")
            
            # FFmpegを使用して動画を分割
            try:
                (
                    ffmpeg
                    .input(file_path, ss=start)
                    .output(output_path, t=current_chunk_duration, c="copy")
                    .global_args("-y")  # 既存ファイルを上書き
                    .run(capture_stdout=True, capture_stderr=True)
                )
            except ffmpeg.Error as e:
                error_message = e.stderr.decode() if e.stderr else str(e)
                raise FileProcessingError(f"FFmpeg処理エラー: {error_message}")
            
            # 出力ファイルの存在確認
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise FileProcessingError(f"動画チャンクの作成に失敗: {output_path}")
                
            chunk_files.append(output_path)
            self.logger.debug(f"動画チャンク作成: {output_path} ({start:.2f}s - {start+current_chunk_duration:.2f}s)")
            
            # 次のチャンクの開始位置
            start += current_chunk_duration
            chunk_index += 1
        
        self.logger.info(f"動画チャンク分割完了: {len(chunk_files)}個のファイル")
        return chunk_files