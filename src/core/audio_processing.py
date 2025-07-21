"""
STT議事録システム - 音声処理機能

音声ファイルの読み込み、分割、フォーマット変換、メタデータ取得などの基盤機能を提供
"""

import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

from pydub import AudioSegment
from pydub.utils import which
import ffmpeg

from ..utils import get_logger, FileProcessingError


class AudioProcessor:
    """音声処理を担当するクラス"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self._validate_dependencies()
    
    def _validate_dependencies(self) -> None:
        """必要な依存関係の確認"""
        if not which("ffmpeg"):
            raise FileProcessingError("FFmpegが見つかりません。FFmpegをインストールしてください。")
    
    def load_audio(self, file_path: str) -> AudioSegment:
        """
        音声ファイルを読み込む
        
        Args:
            file_path: 音声ファイルのパス
            
        Returns:
            AudioSegment: 読み込まれた音声データ
            
        Raises:
            FileProcessingError: ファイル読み込みエラー
        """
        try:
            if not os.path.exists(file_path):
                raise FileProcessingError(f"ファイルが見つかりません: {file_path}")
            
            self.logger.info(f"音声ファイルを読み込み中: {file_path}")
            audio = AudioSegment.from_file(file_path)
            
            self.logger.info(f"音声読み込み完了 - 長さ: {len(audio)/1000:.2f}秒")
            return audio
            
        except Exception as e:
            raise FileProcessingError(f"音声ファイルの読み込みに失敗: {str(e)}")
    
    def get_audio_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        音声ファイルのメタデータを取得
        
        Args:
            file_path: 音声ファイルのパス
            
        Returns:
            Dict: メタデータ情報
        """
        try:
            probe = ffmpeg.probe(file_path)
            audio_stream = next(
                (stream for stream in probe['streams'] if stream['codec_type'] == 'audio'),
                None
            )
            
            if not audio_stream:
                raise FileProcessingError("音声ストリームが見つかりません")
            
            metadata = {
                'duration': float(probe['format']['duration']),
                'sample_rate': int(audio_stream['sample_rate']),
                'channels': int(audio_stream['channels']),
                'codec': audio_stream['codec_name'],
                'bit_rate': int(audio_stream.get('bit_rate', 0)),
                'file_size': int(probe['format']['size'])
            }
            
            self.logger.info(f"メタデータ取得完了: {metadata}")
            return metadata
            
        except Exception as e:
            raise FileProcessingError(f"メタデータの取得に失敗: {str(e)}")
    
    def split_audio(
        self, 
        audio: AudioSegment, 
        chunk_duration: int = 600,  # 10分
        overlap: int = 5  # 5秒のオーバーラップ
    ) -> List[AudioSegment]:
        """
        音声を指定された長さで分割
        
        Args:
            audio: 分割する音声データ
            chunk_duration: 分割単位（秒）
            overlap: オーバーラップ時間（秒）
            
        Returns:
            List[AudioSegment]: 分割された音声データのリスト
        """
        try:
            chunks = []
            chunk_duration_ms = chunk_duration * 1000
            overlap_ms = overlap * 1000
            audio_length = len(audio)
            
            self.logger.info(f"音声分割開始 - 総長: {audio_length/1000:.2f}秒, チャンク長: {chunk_duration}秒")
            
            start = 0
            chunk_index = 0
            
            while start < audio_length:
                end = min(start + chunk_duration_ms, audio_length)
                chunk = audio[start:end]
                chunks.append(chunk)
                
                self.logger.debug(f"チャンク {chunk_index + 1} 作成: {start/1000:.2f}s - {end/1000:.2f}s")
                
                # 次のチャンクの開始位置（オーバーラップを考慮）
                start = end - overlap_ms
                chunk_index += 1
                
                # 最後のチャンクの場合は終了
                if end >= audio_length:
                    break
            
            self.logger.info(f"音声分割完了 - {len(chunks)}個のチャンクを作成")
            return chunks
            
        except Exception as e:
            raise FileProcessingError(f"音声分割に失敗: {str(e)}")
    
    def save_audio_chunks(
        self, 
        chunks: List[AudioSegment], 
        output_dir: str,
        base_name: str = "chunk",
        format: str = "wav"
    ) -> List[str]:
        """
        分割された音声チャンクをファイルに保存
        
        Args:
            chunks: 保存する音声チャンクのリスト
            output_dir: 出力ディレクトリ
            base_name: ファイル名のベース
            format: 出力フォーマット
            
        Returns:
            List[str]: 保存されたファイルパスのリスト
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
            saved_files = []
            
            for i, chunk in enumerate(chunks):
                filename = f"{base_name}_{i+1:03d}.{format}"
                file_path = os.path.join(output_dir, filename)
                
                chunk.export(file_path, format=format)
                saved_files.append(file_path)
                
                self.logger.debug(f"チャンク保存: {file_path}")
            
            self.logger.info(f"全チャンク保存完了: {len(saved_files)}ファイル")
            return saved_files
            
        except Exception as e:
            raise FileProcessingError(f"音声チャンクの保存に失敗: {str(e)}")
    
    def convert_to_wav(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        音声ファイルをWAV形式に変換
        
        Args:
            input_path: 入力ファイルパス
            output_path: 出力ファイルパス（Noneの場合は一時ファイル）
            
        Returns:
            str: 変換後のファイルパス
        """
        try:
            if output_path is None:
                # 一時ファイルを作成
                temp_fd, output_path = tempfile.mkstemp(suffix='.wav')
                os.close(temp_fd)
            
            self.logger.info(f"WAV変換開始: {input_path} -> {output_path}")
            
            audio = self.load_audio(input_path)
            audio.export(output_path, format="wav")
            
            self.logger.info("WAV変換完了")
            return output_path
            
        except Exception as e:
            raise FileProcessingError(f"WAV変換に失敗: {str(e)}")
    
    def normalize_audio(self, audio: AudioSegment, target_dBFS: float = -20.0) -> AudioSegment:
        """
        音声の音量を正規化
        
        Args:
            audio: 正規化する音声データ
            target_dBFS: 目標音量レベル
            
        Returns:
            AudioSegment: 正規化された音声データ
        """
        try:
            current_dBFS = audio.dBFS
            change_in_dBFS = target_dBFS - current_dBFS
            
            normalized_audio = audio.apply_gain(change_in_dBFS)
            
            self.logger.info(f"音声正規化完了: {current_dBFS:.2f}dBFS -> {target_dBFS:.2f}dBFS")
            return normalized_audio
            
        except Exception as e:
            raise FileProcessingError(f"音声正規化に失敗: {str(e)}")
    
    def split_audio_into_chunks(self, file_path: str, chunk_duration: int = 600) -> List[str]:
        """
        音声ファイルを指定された長さのチャンクに分割してファイルに保存
        
        Args:
            file_path: 分割する音声ファイルのパス
            chunk_duration: チャンクの長さ（秒）
            
        Returns:
            List[str]: 分割されたチャンクファイルのパスリスト
        """
        try:
            self.logger.info(f"音声ファイルをチャンクに分割開始: {file_path}")
            
            # 音声ファイルを読み込み
            audio = self.load_audio(file_path)
            
            # 音声を分割
            chunks = self.split_audio(audio, chunk_duration)
            
            # 一時ディレクトリを作成
            temp_dir = tempfile.mkdtemp(prefix="stt_audio_chunks_")
            
            # チャンクをファイルに保存
            base_name = Path(file_path).stem
            chunk_files = self.save_audio_chunks(chunks, temp_dir, base_name)
            
            self.logger.info(f"音声チャンク分割完了: {len(chunk_files)}個のファイル")
            return chunk_files
            
        except Exception as e:
            raise FileProcessingError(f"音声チャンク分割に失敗: {str(e)}")
    
    def cleanup_temp_files(self, file_paths: List[str]) -> int:
        """
        一時ファイルのクリーンアップ
        
        Args:
            file_paths: 削除するファイルパスのリスト
            
        Returns:
            int: 削除したファイル数
        """
        from .file_utils import FileUtils
        return FileUtils.cleanup_files(file_paths, self.logger)