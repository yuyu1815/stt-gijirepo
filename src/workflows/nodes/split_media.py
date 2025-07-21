"""
STT議事録システム - メディア分割ノード

動画・音声ファイルを処理可能なチャンクに分割する
"""

import os
import tempfile
from pathlib import Path
from typing import List

from src.core.audio_processing import AudioProcessor
from src.core.video_processing import VideoProcessor
from src.utils import get_logger
from src.utils.error_handling import handle_error
from src.workflows.state import STTState


def split_media_node(state: STTState) -> STTState:
    """
    メディアファイルを分割するノード
    
    Args:
        state: 現在の処理状態
        
    Returns:
        更新された処理状態
    """
    logger = get_logger("split_media")
    
    try:
        logger.info("メディア分割処理を開始")
        state["processing_stage"] = "splitting_media"
        
        file_path = state["file_path"]
        file_type = state.get("file_type")
        force_video_mode = state.get("force_video_mode", False)
        
        # 設定から分割サイズを取得
        chunk_size = state["settings"].get("chunk_size", 600)  # デフォルト10分
        
        media_chunks = []
        
        if file_type == "video" or force_video_mode:
            # 動画処理ルート（または強制動画モード）
            logger.info("動画処理ルートでメディアを分割")
            
            video_processor = VideoProcessor()
            
            # 動画の場合は動画チャンクとして分割
            if file_type == "video":
                media_chunks = video_processor.split_video_into_chunks(
                    file_path, 
                    chunk_duration=chunk_size
                )
            else:
                # 音声ファイルを動画処理ルートで処理する場合
                # 音声ファイルを一時的に動画形式に変換してから分割
                temp_video_path = _convert_audio_to_video(file_path)
                
                # 一時ファイルを状態に追加してクリーンアップ対象にする
                if "output_files" not in state:
                    state["output_files"] = []
                state["output_files"].append(temp_video_path)
                
                media_chunks = video_processor.split_video_into_chunks(
                    temp_video_path,
                    chunk_duration=chunk_size
                )
                
        else:
            # 音声処理ルート
            logger.info("音声処理ルートでメディアを分割")
            
            audio_processor = AudioProcessor()
            media_chunks = audio_processor.split_audio_into_chunks(
                file_path,
                chunk_duration=chunk_size
            )
        
        # 分割結果を状態に保存
        state["media_chunks"] = media_chunks
        state["processing_log"].append(f"メディア分割完了: {len(media_chunks)}個のチャンク")
        
        logger.info(f"メディア分割完了: {len(media_chunks)}個のチャンク生成")
        
        return state
        
    except Exception as e:
        error_msg = f"メディア分割エラー: {str(e)}"
        handle_error(e, "メディア分割処理", logger)
        state["errors"].append(error_msg)
        return state


def _convert_audio_to_video(audio_path: str) -> str:
    """
    音声ファイルを一時的な動画ファイルに変換
    
    Args:
        audio_path: 音声ファイルパス
        
    Returns:
        変換された動画ファイルパス
        
    Raises:
        FileProcessingError: 変換に失敗した場合
    """
    import subprocess
    from src.utils import FileProcessingError
    
    logger = get_logger("split_media")
    temp_dir = None
    temp_video_path = None
    
    try:
        # 一時ファイルを作成
        temp_dir = tempfile.mkdtemp(prefix="stt_audio_to_video_")
        temp_video_path = os.path.join(temp_dir, "temp_video.mp4")
        
        logger.info(f"音声を動画に変換開始: {audio_path} -> {temp_video_path}")
        
        # FFmpegを使用して音声を動画に変換（黒い画面付き）
        cmd = [
            "ffmpeg", "-y",
            "-i", audio_path,
            "-f", "lavfi",
            "-i", "color=black:size=640x480:rate=1",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            temp_video_path
        ]
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # 出力ファイルの存在確認
        if not os.path.exists(temp_video_path) or os.path.getsize(temp_video_path) == 0:
            raise FileProcessingError("音声から動画への変換に失敗しました（出力ファイルが空です）")
        
        logger.info("音声から動画への変換完了")
        return temp_video_path
        
    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg変換エラー: {e.stderr if e.stderr else str(e)}"
        logger.error(error_msg)
        
        # エラー時の一時ファイルクリーンアップ
        if temp_video_path and os.path.exists(temp_video_path):
            try:
                os.remove(temp_video_path)
            except Exception:
                pass
        if temp_dir and os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass
                
        raise FileProcessingError(error_msg)
        
    except Exception as e:
        error_msg = f"音声から動画への変換に失敗: {str(e)}"
        logger.error(error_msg)
        
        # エラー時の一時ファイルクリーンアップ
        if temp_video_path and os.path.exists(temp_video_path):
            try:
                os.remove(temp_video_path)
            except Exception:
                pass
        if temp_dir and os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass
                
        raise FileProcessingError(error_msg)