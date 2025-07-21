"""
STT議事録システム - 文字起こしノード

Gemini APIを使用した文字起こし処理を行うノード
"""

import time
from typing import List, Optional, Dict, Any
import concurrent.futures
from pathlib import Path

from src.workflows.state import STTState
from src.utils import get_logger, APIError, FileProcessingError, api_call_with_retry
from src.utils.logging_config import log_state_transition, LogContext
from src.core.ai_services import GeminiService

# Gemini API
from google import genai
HAS_GEMINI = True



def transcribe_node(state: STTState) -> STTState:
    """
    Gemini APIを使用した文字起こし
    
    処理内容:
    - 単一/分割ファイルの処理
    - リトライ機能付きAPI呼び出し
    - 結果の統合
    
    Args:
        state: 現在の処理状態
        
    Returns:
        更新された処理状態
    """
    logger = get_logger("transcription")
    
    with LogContext(logger, "文字起こし", state["session_id"]) as ctx:
        try:
            # 状態遷移をログ
            log_state_transition(logger, state["processing_stage"], "transcription", state["session_id"])
            state["processing_stage"] = "transcription"
            
            if not HAS_GEMINI:
                raise APIError("Gemini APIが利用できません", "gemini")
            
            # API設定
            api_key = state["settings"].get("gemini_api_key")
            if not api_key:
                raise APIError("Gemini APIキーが設定されていません", "gemini")
            
            model_name = state["settings"].get("gemini_model", "gemini-1.5-pro")
            
            ctx.log_progress(f"Gemini API設定完了: {model_name}")
            
            # チャンクファイルを取得
            chunks = state.get("media_chunks") or state.get("chunks", [state["file_path"]])
            chunk_durations = state.get("chunk_durations", [state.get("audio_duration", 0)])
            
            ctx.log_progress(f"処理対象: {len(chunks)}個のファイル")
            
            # 文字起こし実行
            if len(chunks) == 1:
                # 単一ファイルの処理
                transcription = _transcribe_single_file(chunks[0], model_name, api_key)
                confidence = 0.8  # デフォルト信頼度
            else:
                # 複数チャンクの並列処理
                transcription, confidence, chunk_transcriptions = _transcribe_multiple_chunks(
                    chunks, chunk_durations, model_name, api_key
                )
                # 個別のチャンク文字起こし結果も保存
                state["chunk_transcriptions"] = chunk_transcriptions
            
            state["transcription"] = transcription
            state["transcription_confidence"] = confidence
            
            ctx.log_progress(f"文字起こし完了: {len(transcription)}文字, 信頼度: {confidence:.2f}")
            state["processing_log"].append(f"文字起こし完了: {len(transcription)}文字")
            
            logger.info(f"文字起こし完了: {len(transcription)}文字")
            
        except Exception as e:
            error_msg = f"文字起こしエラー: {str(e)}"
            state["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)
            
            # エラー時はデフォルト値を設定
            state["transcription"] = ""
            state["transcription_confidence"] = 0.0
    
    return state


def _transcribe_single_file(file_path: str, model_name: str, api_key: str) -> str:
    """
    単一ファイルの文字起こし
    
    Args:
        file_path: 音声ファイルのパス
        model_name: 使用するモデル名
        api_key: Gemini APIキー
        
    Returns:
        文字起こし結果
    """
    logger = get_logger("transcription")
    
    try:
        # API設定とクライアント初期化
        import os
        os.environ['GOOGLE_API_KEY'] = api_key
        client = genai.Client()
        
        # プロンプトを読み込み
        prompt = _load_transcription_prompt()
        
        # ファイルをアップロード
        logger.info(f"ファイルアップロード開始: {file_path}")
        uploaded_file = client.files.upload(file=file_path)
        
        # アップロード完了まで待機
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(1)
            uploaded_file = client.files.get(uploaded_file.name)
        
        if uploaded_file.state.name == "FAILED":
            raise APIError(f"ファイルアップロードに失敗しました: {file_path}", "gemini")
        
        logger.info(f"ファイルアップロード完了: {uploaded_file.name}")
        
        # 文字起こし実行（リトライ付き）
        def _generate_content():
            return client.models.generate_content(
                model=model_name,
                contents=[uploaded_file, prompt]
            )
        
        response = api_call_with_retry(
            _generate_content,
            max_retries=5,
            logger=logger
        )
        
        # ファイルを削除
        try:
            client.files.delete(uploaded_file.name)
            logger.debug(f"アップロードファイル削除: {uploaded_file.name}")
        except Exception as e:
            logger.warning(f"アップロードファイル削除に失敗: {e}")
        
        return response.text.strip()
        
    except Exception as e:
        raise APIError(f"文字起こしに失敗しました: {str(e)}", "gemini")


def _transcribe_multiple_chunks(
    chunks: List[str], 
    durations: List[float], 
    model_name: str,
    api_key: str,
    max_workers: int = 3
) -> tuple[str, float]:
    """
    複数チャンクの並列文字起こし
    
    Args:
        chunks: チャンクファイルのパス一覧
        durations: 各チャンクの長さ一覧
        model_name: 使用するモデル名
        api_key: Gemini APIキー
        max_workers: 最大並列数
        
    Returns:
        (統合された文字起こし結果, 平均信頼度)
    """
    logger = get_logger("transcription")
    
    def process_chunk(chunk_info):
        index, chunk_path = chunk_info
        try:
            logger.info(f"チャンク {index + 1}/{len(chunks)} 処理開始: {chunk_path}")
            result = _transcribe_single_file(chunk_path, model_name, api_key)
            logger.info(f"チャンク {index + 1}/{len(chunks)} 処理完了")
            return index, result, 0.8  # デフォルト信頼度
        except Exception as e:
            logger.error(f"チャンク {index + 1} 処理エラー: {str(e)}")
            return index, f"[チャンク {index + 1} 処理エラー: {str(e)}]", 0.0
    
    # 並列処理実行
    chunk_results = {}
    confidences = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_chunk, (i, chunk))
            for i, chunk in enumerate(chunks)
        ]
        
        for future in concurrent.futures.as_completed(futures):
            try:
                index, result, confidence = future.result()
                chunk_results[index] = result
                confidences.append(confidence)
            except Exception as e:
                logger.error(f"チャンク処理で予期しないエラー: {str(e)}")
    
    # 結果を順序通りに統合
    transcriptions = []
    chunk_times = []
    current_time = 0.0
    
    for i in range(len(chunks)):
        if i in chunk_results:
            transcriptions.append(chunk_results[i])
            
            # 時間情報を追加
            duration = durations[i] if durations and i < len(durations) else 0
            chunk_times.append((current_time, current_time + duration))
            current_time += duration
    
    # 統合された文字起こし結果を作成
    combined_transcription = _combine_transcriptions(transcriptions, chunk_times)
    average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    return combined_transcription, average_confidence, transcriptions


def _combine_transcriptions(transcriptions: List[str], chunk_times: List[tuple] = None) -> str:
    """
    複数の文字起こし結果を統合
    
    Args:
        transcriptions: 文字起こし結果のリスト
        chunk_times: 各チャンクの時間情報
        
    Returns:
        統合された文字起こし結果
    """
    if not transcriptions:
        return ""
    
    combined_parts = []
    
    for i, transcription in enumerate(transcriptions):
        if not transcription.strip():
            continue
        
        # 時間情報を追加（オプション）
        if chunk_times and i < len(chunk_times):
            start_time, end_time = chunk_times[i]
            time_header = f"\n--- {start_time/60:.1f}分 - {end_time/60:.1f}分 ---\n"
            combined_parts.append(time_header + transcription)
        else:
            combined_parts.append(transcription)
    
    return "\n\n".join(combined_parts)


def _load_transcription_prompt() -> str:
    """
    文字起こし用プロンプトを読み込み
    
    Returns:
        プロンプト文字列
    """
    try:
        # プロンプトローダーを使用して外部ファイルから読み込み
        from src.utils.prompt_loader import PromptLoader
        loader = PromptLoader()
        return loader.load_prompt("transcription", "detailed_transcription")
    except Exception as e:
        # フォールバック用のデフォルトプロンプト
        logger = get_logger("transcription")
        logger.warning(f"外部プロンプトファイルの読み込みに失敗、デフォルトを使用: {str(e)}")
        
        return """以下の音声ファイルを議事録用に文字起こししてください。

注意事項:
- 日本語の音声です。正確に文字起こししてください。
- 専門用語や固有名詞も可能な限り正確に書き起こしてください。
- 音声が不明瞭な場合は[不明瞭]と記載してください。
- 背景音や雑音は無視してください。
- タイムスタンプは不要です。
- 話者が複数いる場合は「Aさん：」「Bさん：」のように区別してください。

映像情報がある場合：
- その状況や書いている内容も事細かく書いてください。
- 議事録側にこれは動画の映像の内容などと記してください。
- コードが記述されている場合それを議事録に記述してください。
- コードの場合は以下のようにしてください：
  Aさん：文字起こし
  コード ```コードの中身```"""


def _generate_content_with_retry(model, contents: list, max_retries: int = 5):
    """
    リトライ機能付きコンテンツ生成（既存コードとの互換性のため）
    
    Args:
        model: Geminiモデル
        contents: 生成用コンテンツ
        max_retries: 最大リトライ回数
        
    Returns:
        生成結果
    """
    def _generate():
        return model.generate_content(contents)
    
    return api_call_with_retry(
        _generate,
        max_retries=max_retries,
        logger=get_logger("transcription")
    )


def check_transcription_quality(transcription: str) -> Dict[str, Any]:
    """
    文字起こし品質の基本チェック
    
    Args:
        transcription: 文字起こし結果
        
    Returns:
        品質チェック結果
    """
    if not transcription:
        return {
            "quality_score": 0.0,
            "issues": ["文字起こし結果が空です"],
            "word_count": 0,
            "estimated_confidence": 0.0
        }
    
    issues = []
    word_count = len(transcription.split())
    
    # 基本的な品質チェック
    if len(transcription) < 50:
        issues.append("文字起こし結果が短すぎます")
    
    if "[不明瞭]" in transcription:
        unclear_count = transcription.count("[不明瞭]")
        if unclear_count > word_count * 0.1:  # 10%以上が不明瞭
            issues.append(f"不明瞭な部分が多すぎます ({unclear_count}箇所)")
    
    # 品質スコアを計算
    quality_score = 1.0
    if issues:
        quality_score -= len(issues) * 0.2
    
    quality_score = max(0.0, min(1.0, quality_score))
    
    return {
        "quality_score": quality_score,
        "issues": issues,
        "word_count": word_count,
        "estimated_confidence": quality_score * 0.8 + 0.2  # 0.2-1.0の範囲
    }