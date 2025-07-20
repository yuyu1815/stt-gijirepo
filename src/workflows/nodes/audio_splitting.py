"""
STT議事録システム - 音声分割ノード

長時間音声の分割処理を行うノード
"""

import os
import math
from pathlib import Path
from typing import List, Tuple
from pydub import AudioSegment

from src.workflows.state import STTState
from src.utils import get_logger, FileProcessingError
from src.utils.logging_config import log_state_transition, LogContext


def split_audio_node(state: STTState) -> STTState:
    """
    長時間音声の分割処理
    
    処理内容:
    - 音声長の確認
    - 適切なサイズでの分割
    - 分割ファイルの管理
    
    Args:
        state: 現在の処理状態
        
    Returns:
        更新された処理状態
    """
    logger = get_logger("audio_splitting")
    
    with LogContext(logger, "音声分割", state["session_id"]) as ctx:
        try:
            # 状態遷移をログ
            log_state_transition(logger, state["processing_stage"], "audio_splitting", state["session_id"])
            state["processing_stage"] = "audio_splitting"
            
            file_path = state["file_path"]
            audio_duration = state.get("audio_duration", 0)
            
            # 設定から分割サイズを取得
            chunk_size = state["settings"].get("chunk_size", 600)  # デフォルト10分
            max_duration = state["settings"].get("max_audio_duration", 2400)  # デフォルト40分
            
            ctx.log_progress(f"音声長: {audio_duration:.2f}秒, 分割サイズ: {chunk_size}秒")
            
            # 分割が必要かチェック
            if audio_duration <= chunk_size:
                ctx.log_progress("分割不要（短時間音声）")
                state["chunks"] = [file_path]
                state["chunk_durations"] = [audio_duration]
                state["processing_log"].append(f"音声分割不要: {audio_duration:.2f}秒")
                return state
            
            # 最大長チェック
            if audio_duration > max_duration:
                warning_msg = f"音声が最大長({max_duration}秒)を超えています: {audio_duration:.2f}秒"
                state["warnings"].append(warning_msg)
                logger.warning(warning_msg)
            
            ctx.log_progress("音声分割を開始")
            
            # 音声を分割
            chunks, durations = _split_audio_file(
                file_path, 
                chunk_size,
                start_time_seconds=0
            )
            
            state["chunks"] = chunks
            state["chunk_durations"] = durations
            state["output_files"].extend(chunks)
            
            ctx.log_progress(f"音声分割完了: {len(chunks)}個のチャンクを作成")
            state["processing_log"].append(f"音声分割完了: {len(chunks)}個のチャンク")
            
            logger.info(f"音声分割完了: {len(chunks)}個のチャンク, 合計時間: {sum(durations):.2f}秒")
            
        except Exception as e:
            error_msg = f"音声分割エラー: {str(e)}"
            state["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)
            
            # エラー時は元ファイルをそのまま使用
            state["chunks"] = [state["file_path"]]
            state["chunk_durations"] = [state.get("audio_duration", 0)]
    
    return state


def _split_audio_file(
    file_path: str, 
    chunk_duration: int, 
    start_file_index: int = 0,
    start_time_seconds: int = 0
) -> Tuple[List[str], List[float]]:
    """
    音声ファイルを指定された長さで分割
    
    Args:
        file_path: 音声ファイルのパス
        chunk_duration: 分割する長さ（秒）
        start_file_index: 開始ファイルインデックス
        start_time_seconds: 開始時間（秒）
        
    Returns:
        (分割されたファイルパスのリスト, 各チャンクの長さのリスト)
    """
    logger = get_logger("audio_splitting")
    
    try:
        # 音声ファイルを読み込み
        audio = AudioSegment.from_file(file_path)
        total_duration_ms = len(audio)
        total_duration_s = total_duration_ms / 1000.0
        
        logger.info(f"音声ファイル読み込み完了: {total_duration_s:.2f}秒")
        
        # 開始時間を適用
        if start_time_seconds > 0:
            start_ms = start_time_seconds * 1000
            audio = audio[start_ms:]
            total_duration_ms = len(audio)
            total_duration_s = total_duration_ms / 1000.0
            logger.info(f"開始時間適用後: {total_duration_s:.2f}秒")
        
        # 分割数を計算
        chunk_duration_ms = chunk_duration * 1000
        num_chunks = math.ceil(total_duration_ms / chunk_duration_ms)
        
        logger.info(f"分割数: {num_chunks}個")
        
        # ファイルパスの準備
        file_path_obj = Path(file_path)
        base_name = file_path_obj.stem
        extension = file_path_obj.suffix
        output_dir = file_path_obj.parent
        
        chunk_files = []
        chunk_durations = []
        
        for i in range(num_chunks):
            # 分割範囲を計算
            start_ms = i * chunk_duration_ms
            end_ms = min((i + 1) * chunk_duration_ms, total_duration_ms)
            
            # チャンクを抽出
            chunk = audio[start_ms:end_ms]
            chunk_duration_actual = len(chunk) / 1000.0
            
            # ファイル名を生成
            chunk_filename = f"{base_name}_chunk_{start_file_index + i:03d}{extension}"
            chunk_path = output_dir / chunk_filename
            
            # チャンクを保存
            chunk.export(str(chunk_path), format=extension[1:])  # 拡張子から'.'を除去
            
            chunk_files.append(str(chunk_path))
            chunk_durations.append(chunk_duration_actual)
            
            logger.debug(f"チャンク {i+1}/{num_chunks} 作成: {chunk_path} ({chunk_duration_actual:.2f}秒)")
        
        logger.info(f"音声分割完了: {len(chunk_files)}個のファイルを作成")
        return chunk_files, chunk_durations
        
    except Exception as e:
        raise FileProcessingError(f"音声分割に失敗しました: {str(e)}", file_path)


def _calculate_optimal_chunk_size(duration: float, max_chunks: int = 10) -> int:
    """
    最適な分割サイズを計算
    
    Args:
        duration: 音声の長さ（秒）
        max_chunks: 最大分割数
        
    Returns:
        最適な分割サイズ（秒）
    """
    # 基本的な分割サイズ候補（秒）
    chunk_sizes = [300, 600, 900, 1200, 1800]  # 5分, 10分, 15分, 20分, 30分
    
    for chunk_size in chunk_sizes:
        num_chunks = math.ceil(duration / chunk_size)
        if num_chunks <= max_chunks:
            return chunk_size
    
    # すべての候補でも分割数が多すぎる場合は最大サイズを返す
    return chunk_sizes[-1]


def get_chunk_info(chunks: List[str], durations: List[float]) -> dict:
    """
    チャンク情報のサマリーを取得
    
    Args:
        chunks: チャンクファイルのパス一覧
        durations: 各チャンクの長さ一覧
        
    Returns:
        チャンク情報の辞書
    """
    if not chunks or not durations:
        return {
            "total_chunks": 0,
            "total_duration": 0.0,
            "average_duration": 0.0,
            "min_duration": 0.0,
            "max_duration": 0.0
        }
    
    return {
        "total_chunks": len(chunks),
        "total_duration": sum(durations),
        "average_duration": sum(durations) / len(durations),
        "min_duration": min(durations),
        "max_duration": max(durations)
    }


def cleanup_chunks(chunks: List[str], keep_original: bool = True) -> None:
    """
    分割されたチャンクファイルをクリーンアップ
    
    Args:
        chunks: クリーンアップするチャンクファイルのパス一覧
        keep_original: 元ファイルを保持するかどうか
    """
    logger = get_logger("audio_splitting")
    
    for chunk_path in chunks:
        try:
            if os.path.exists(chunk_path):
                # 元ファイルかどうかをチェック
                if keep_original and "_chunk_" not in os.path.basename(chunk_path):
                    continue
                
                os.remove(chunk_path)
                logger.debug(f"チャンクファイルを削除: {chunk_path}")
        except Exception as e:
            logger.warning(f"チャンクファイルの削除に失敗: {chunk_path} - {str(e)}")


def merge_chunk_results(chunk_results: List[str], chunk_times: List[Tuple[float, float]] = None) -> str:
    """
    チャンクの処理結果をマージ（既存コードとの互換性のため）
    
    Args:
        chunk_results: 各チャンクの処理結果
        chunk_times: 各チャンクの時間情報
        
    Returns:
        マージされた結果
    """
    if not chunk_results:
        return ""
    
    merged_result = []
    
    for i, result in enumerate(chunk_results):
        if chunk_times and i < len(chunk_times):
            start_time, end_time = chunk_times[i]
            merged_result.append(f"[{start_time:.1f}s-{end_time:.1f}s] {result}")
        else:
            merged_result.append(f"[Chunk {i+1}] {result}")
    
    return "\n\n".join(merged_result)