"""
STT議事録システム - 動画処理ノード

動画ファイルの前処理を行うノード
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import tempfile

from src.workflows.state import STTState
from src.utils import get_logger, FileProcessingError
from src.utils.logging_config import log_state_transition, LogContext

# OpenCVのインポートを試行（オプション）
try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


def process_video_node(state: STTState) -> STTState:
    """
    動画ファイルの前処理
    
    処理内容:
    - 動画の明度解析
    - 必要に応じて音声抽出
    - フォーマット変換
    
    Args:
        state: 現在の処理状態
        
    Returns:
        更新された処理状態
    """
    logger = get_logger("video_processing")
    
    with LogContext(logger, "動画処理", state["session_id"]) as ctx:
        try:
            # 状態遷移をログ
            log_state_transition(logger, state["processing_stage"], "video_processing", state["session_id"])
            state["processing_stage"] = "video_processing"
            
            file_path = state["file_path"]
            
            # 動画ファイルでない場合はスキップ
            if state["file_type"] != "video":
                ctx.log_progress("動画ファイルではないためスキップ")
                state["processing_log"].append("動画処理をスキップ（動画ファイルではない）")
                return state
            
            ctx.log_progress("動画の明度解析を開始")
            
            # 動画の明度を解析
            is_dark = _is_video_dark(file_path)
            state["is_video_dark"] = is_dark
            
            if is_dark:
                ctx.log_progress("暗い動画と判定 - 音声抽出を実行")
                
                # 音声を抽出
                audio_path = _convert_video_to_audio(file_path)
                
                # 抽出した音声ファイルのパスを更新
                state["file_path"] = audio_path
                state["file_type"] = "audio"
                state["output_files"].append(audio_path)
                
                ctx.log_progress(f"音声抽出完了: {audio_path}")
                state["processing_log"].append(f"暗い動画から音声抽出: {audio_path}")
            else:
                ctx.log_progress("明るい動画と判定 - そのまま処理継続")
                state["processing_log"].append("明るい動画として処理継続")
            
            logger.info(f"動画処理完了: is_dark={is_dark}")
            
        except Exception as e:
            error_msg = f"動画処理エラー: {str(e)}"
            state["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)
            
            # エラー時もデフォルト値を設定
            if "is_video_dark" not in state or state["is_video_dark"] is None:
                state["is_video_dark"] = False
    
    return state


def _is_video_dark(file_path: str, darkness_threshold: float = 10.0, sample_frames: int = 30) -> bool:
    """
    動画が暗いかどうかを判定
    
    Args:
        file_path: 動画ファイルのパス
        darkness_threshold: 暗さの閾値（0-255）
        sample_frames: サンプリングするフレーム数
        
    Returns:
        暗い動画の場合True
    """
    logger = get_logger("video_processing")
    
    if not HAS_OPENCV:
        logger.warning("OpenCVが利用できないため、動画の明度解析をスキップします")
        return False
    
    try:
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            raise FileProcessingError(f"動画ファイルを開けません: {file_path}", file_path)
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames == 0:
            raise FileProcessingError(f"動画にフレームがありません: {file_path}", file_path)
        
        # サンプリング間隔を計算
        frame_interval = max(1, total_frames // sample_frames)
        
        brightness_values = []
        frame_count = 0
        
        for i in range(0, total_frames, frame_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            # グレースケールに変換
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 平均明度を計算
            brightness = np.mean(gray)
            brightness_values.append(brightness)
            frame_count += 1
            
            if frame_count >= sample_frames:
                break
        
        cap.release()
        
        if not brightness_values:
            raise FileProcessingError(f"動画フレームの解析に失敗しました: {file_path}", file_path)
        
        # 全体の平均明度を計算
        average_brightness = np.mean(brightness_values)
        
        logger.info(f"動画の平均明度: {average_brightness:.2f} (閾値: {darkness_threshold})")
        
        return average_brightness < darkness_threshold
        
    except Exception as e:
        logger.error(f"動画明度解析エラー: {str(e)}")
        # エラーの場合は安全側に倒して暗くないと判定
        return False


def _convert_video_to_audio(video_path: str, output_format: str = "aac") -> str:
    """
    動画ファイルから音声を抽出
    
    Args:
        video_path: 動画ファイルのパス
        output_format: 出力音声フォーマット
        
    Returns:
        抽出された音声ファイルのパス
    """
    logger = get_logger("video_processing")
    
    try:
        # 出力ファイル名を生成
        video_path_obj = Path(video_path)
        output_path = video_path_obj.parent / f"{video_path_obj.stem}_extracted.{output_format}"
        
        # FFmpegコマンドを構築
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vn",  # 動画ストリームを無効化
            "-acodec", "aac" if output_format == "aac" else "copy",
            "-y",  # 既存ファイルを上書き
            str(output_path)
        ]
        
        logger.info(f"音声抽出コマンド実行: {' '.join(cmd)}")
        
        # FFmpegを実行
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5分でタイムアウト
        )
        
        if result.returncode != 0:
            raise FileProcessingError(
                f"音声抽出に失敗しました: {result.stderr}",
                video_path
            )
        
        if not output_path.exists():
            raise FileProcessingError(
                f"音声ファイルが作成されませんでした: {output_path}",
                video_path
            )
        
        logger.info(f"音声抽出完了: {output_path}")
        return str(output_path)
        
    except subprocess.TimeoutExpired:
        raise FileProcessingError(f"音声抽出がタイムアウトしました: {video_path}", video_path)
    except Exception as e:
        raise FileProcessingError(f"音声抽出エラー: {str(e)}", video_path)


def _get_video_info(file_path: str) -> Dict[str, Any]:
    """
    動画ファイルの情報を取得
    
    Args:
        file_path: 動画ファイルのパス
        
    Returns:
        動画情報の辞書
    """
    info = {}
    
    if not HAS_OPENCV:
        return info
    
    try:
        cap = cv2.VideoCapture(file_path)
        if cap.isOpened():
            info["frame_count"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            info["fps"] = cap.get(cv2.CAP_PROP_FPS)
            info["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            info["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            info["duration"] = info["frame_count"] / info["fps"] if info["fps"] > 0 else 0
            cap.release()
    except Exception:
        pass
    
    return info


def count_frames(file_path: str) -> int:
    """
    動画のフレーム数を取得（既存コードとの互換性のため）
    
    Args:
        file_path: 動画ファイルのパス
        
    Returns:
        フレーム数
    """
    if not HAS_OPENCV:
        return 0
    
    try:
        cap = cv2.VideoCapture(file_path)
        if cap.isOpened():
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            return frame_count
    except Exception:
        pass
    
    return 0


def split_video(file_path: str, max_frames: int = 3600) -> list:
    """
    動画を分割（既存コードとの互換性のため）
    
    Args:
        file_path: 動画ファイルのパス
        max_frames: 最大フレーム数
        
    Returns:
        分割されたファイルのパスのリスト
    """
    logger = get_logger("video_processing")
    
    try:
        total_frames = count_frames(file_path)
        if total_frames <= max_frames:
            return [file_path]
        
        # 分割が必要な場合の処理（簡略化）
        logger.warning(f"動画分割が必要ですが、現在は未実装です: {file_path}")
        return [file_path]
        
    except Exception as e:
        logger.error(f"動画分割エラー: {str(e)}")
        return [file_path]