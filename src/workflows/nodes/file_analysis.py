"""
STT議事録システム - ファイル解析ノード

入力ファイルの解析と基本情報の取得を行うノード
"""

import os
import mimetypes
from pathlib import Path
from typing import Dict, Any
from pydub import AudioSegment

from src.workflows.state import STTState
from src.utils import get_logger, FileProcessingError
from src.utils.logging_config import log_state_transition, LogContext
from src.core.audio_processing import AudioProcessor
from src.core.file_utils import FileUtils

# OpenCVのインポートを試行（オプション）
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


def analyze_file_node(state: STTState) -> STTState:
    """
    入力ファイルの解析と基本情報の取得
    
    処理内容:
    - ファイル形式の判定
    - メタデータの抽出
    - 音声長の取得
    - ファイルサイズの確認
    
    Args:
        state: 現在の処理状態
        
    Returns:
        更新された処理状態
    """
    logger = get_logger("file_analysis")
    
    with LogContext(logger, "ファイル解析", state["session_id"]) as ctx:
        try:
            # 状態遷移をログ
            log_state_transition(logger, state["processing_stage"], "file_analysis", state["session_id"])
            state["processing_stage"] = "file_analysis"
            
            file_path = state["file_path"]
            
            # ファイルの存在確認
            if not os.path.exists(file_path):
                raise FileProcessingError(f"ファイルが存在しません: {file_path}", file_path)
            
            ctx.log_progress("ファイル存在確認完了")
            
            # ファイル情報の取得
            file_info = _get_file_info(file_path)
            state.update(file_info)
            
            ctx.log_progress(f"ファイル種別: {state['file_type']}")
            
            # 音声長の取得
            if state["file_type"] in ["audio", "video"]:
                duration = _get_audio_duration(file_path)
                state["audio_duration"] = duration
                ctx.log_progress(f"音声長: {duration:.2f}秒")
                
                # 音声メタデータの取得
                audio_metadata = _get_audio_metadata(file_path)
                state.update(audio_metadata)
            
            # クラス情報の取得（既存機能）
            try:
                from src.utils.class_info import get_class_info
                class_info = get_class_info(file_path)
                state["class_info"] = class_info
                ctx.log_progress("クラス情報取得完了")
            except ImportError:
                # クラス情報ユーティリティが未実装の場合はスキップ
                state["class_info"] = {"name": "不明", "teacher": "不明", "datetime": "不明"}
                logger.warning("クラス情報ユーティリティが利用できません")
            
            # 処理ログの追加
            state["processing_log"].append(f"ファイル解析完了: {state['file_type']}, {state['audio_duration']:.2f}秒")
            
            # パフォーマンスメトリクスの記録
            from datetime import datetime
            current_time = datetime.now()
            if hasattr(ctx, 'start_time') and ctx.start_time:
                duration = (current_time - ctx.start_time).total_seconds()
                state["performance_metrics"]["file_analysis_duration"] = duration
            else:
                state["performance_metrics"]["file_analysis_duration"] = 0.0
            
            logger.info(f"ファイル解析完了: {file_path}")
            
        except Exception as e:
            error_msg = f"ファイル解析エラー: {str(e)}"
            state["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)
            
            # エラー時も基本情報は設定
            if "file_type" not in state or state["file_type"] is None:
                state["file_type"] = "unknown"
            if "audio_duration" not in state or state["audio_duration"] is None:
                state["audio_duration"] = 0.0
    
    return state


def _get_file_info(file_path: str) -> Dict[str, Any]:
    """
    ファイルの基本情報を取得
    
    Args:
        file_path: ファイルパス
        
    Returns:
        ファイル情報の辞書
    """
    file_info = {}
    
    # MIMEタイプの取得
    mime_type, _ = mimetypes.guess_type(file_path)
    file_info["mime_type"] = mime_type
    
    # ファイル拡張子から種別を判定
    file_extension = Path(file_path).suffix.lower()
    
    # 動画ファイルの判定
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
    # 音声ファイルの判定
    audio_extensions = {'.mp3', '.wav', '.aac', '.flac', '.ogg', '.wma', '.m4a'}
    
    if file_extension in video_extensions:
        file_info["file_type"] = "video"
    elif file_extension in audio_extensions:
        file_info["file_type"] = "audio"
    elif mime_type:
        if mime_type.startswith('video/'):
            file_info["file_type"] = "video"
        elif mime_type.startswith('audio/'):
            file_info["file_type"] = "audio"
        else:
            file_info["file_type"] = "unknown"
    else:
        file_info["file_type"] = "unknown"
    
    return file_info


def _get_audio_duration(file_path: str) -> float:
    """
    音声ファイルの長さを取得
    
    Args:
        file_path: ファイルパス
        
    Returns:
        音声長（秒）
    """
    try:
        # pydubを使用して音声長を取得
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0  # ミリ秒から秒に変換
    except Exception as e:
        # pydubで失敗した場合はOpenCVを試す（動画ファイルの場合）
        if HAS_OPENCV:
            try:
                cap = cv2.VideoCapture(file_path)
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    duration = frame_count / fps if fps > 0 else 0
                    cap.release()
                    return duration
                else:
                    raise FileProcessingError(f"音声長の取得に失敗しました: {str(e)}", file_path)
            except Exception as e2:
                raise FileProcessingError(f"音声長の取得に失敗しました: {str(e2)}", file_path)
        else:
            raise FileProcessingError(f"音声長の取得に失敗しました（OpenCVが利用できません）: {str(e)}", file_path)


def _get_audio_metadata(file_path: str) -> Dict[str, Any]:
    """
    音声メタデータを取得
    
    Args:
        file_path: ファイルパス
        
    Returns:
        音声メタデータの辞書
    """
    metadata = {}
    
    try:
        audio = AudioSegment.from_file(file_path)
        metadata["audio_sample_rate"] = audio.frame_rate
        metadata["audio_channels"] = audio.channels
    except Exception:
        # メタデータの取得に失敗した場合はデフォルト値を設定
        metadata["audio_sample_rate"] = None
        metadata["audio_channels"] = None
    
    return metadata


def is_video_file(file_path: str) -> bool:
    """
    動画ファイルかどうかを判定（既存コードとの互換性のため）
    
    Args:
        file_path: ファイルパス
        
    Returns:
        動画ファイルの場合True
    """
    file_info = _get_file_info(file_path)
    return file_info["file_type"] == "video"


def is_audio_file(file_path: str) -> bool:
    """
    音声ファイルかどうかを判定（既存コードとの互換性のため）
    
    Args:
        file_path: ファイルパス
        
    Returns:
        音声ファイルの場合True
    """
    file_info = _get_file_info(file_path)
    return file_info["file_type"] == "audio"


def is_media_file(file_path: str) -> bool:
    """
    メディアファイル（音声または動画）かどうかを判定
    
    Args:
        file_path: ファイルパス
        
    Returns:
        メディアファイルの場合True
    """
    file_info = _get_file_info(file_path)
    return file_info["file_type"] in ["audio", "video"]