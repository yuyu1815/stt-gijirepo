"""
STT議事録システム - チャンク議事録結合ノード

各チャンクから生成された議事録を結合して中間議事録を作成する
"""

from typing import List
from datetime import datetime

from src.core.ai_services import GeminiService
from src.utils import get_logger
from src.utils.retry_utils import with_retry
from src.utils.prompt_loader import load_and_render_prompt
from src.workflows.state import STTState


def combine_chunk_minutes_node(state: STTState) -> STTState:
    """
    チャンク議事録を結合するノード
    
    Args:
        state: 現在の処理状態
        
    Returns:
        更新された処理状態
    """
    logger = get_logger("combine_minutes")
    
    try:
        logger.info("チャンク議事録の結合を開始")
        state["processing_stage"] = "combining_chunk_minutes"
        
        chunk_minutes = state.get("chunk_minutes", [])
        if not chunk_minutes:
            error_msg = "結合対象のチャンク議事録が見つかりません"
            logger.error(error_msg)
            state["errors"].append(error_msg)
            return state
        
        # 基本的な結合（単純な連結）
        basic_combined = _basic_combine_chunks(chunk_minutes, state)
        
        # AI による高度な結合処理
        gemini_api_key = state["settings"].get("gemini_api_key")
        if gemini_api_key:
            logger.info("AIによる高度な結合処理を実行")
            gemini_service = GeminiService(api_key=gemini_api_key)
            
            try:
                enhanced_combined = _ai_enhance_combined_minutes(
                    gemini_service, 
                    basic_combined, 
                    state
                )
                combined_minutes_text = enhanced_combined
            except Exception as e:
                logger.warning(f"AI結合処理でエラーが発生、基本結合を使用: {str(e)}")
                combined_minutes_text = basic_combined
        else:
            logger.info("Gemini APIキーが未設定のため、基本結合のみ実行")
            combined_minutes_text = basic_combined
        
        # 結果を状態に保存
        state["combined_minutes_text"] = combined_minutes_text
        state["processing_log"].append(f"チャンク議事録結合完了: {len(chunk_minutes)}個のチャンクを結合")
        
        logger.info(f"チャンク議事録結合完了: {len(chunk_minutes)}個のチャンクを結合")
        
        return state
        
    except Exception as e:
        error_msg = f"チャンク議事録結合エラー: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append(error_msg)
        return state


def _basic_combine_chunks(chunk_minutes: List[str], state: STTState) -> str:
    """
    チャンク議事録の基本的な結合
    
    Args:
        chunk_minutes: チャンク議事録のリスト
        state: 現在の処理状態
        
    Returns:
        結合された議事録テキスト
    """
    logger = get_logger("combine_minutes")
    
    # ヘッダー情報を作成
    original_filename = state.get("original_filename", "不明なファイル")
    timestamp = state.get("timestamp", datetime.now())
    processing_route = "動画処理ルート" if state.get("force_video_mode") or state.get("file_type") == "video" else "音声処理ルート"
    
    header = f"""# 議事録（中間版）

**ファイル名**: {original_filename}  
**処理日時**: {timestamp.strftime('%Y年%m月%d日 %H:%M:%S')}  
**処理ルート**: {processing_route}  
**チャンク数**: {len(chunk_minutes)}個  

---

"""
    
    # チャンクを結合
    combined_content = []
    for i, chunk_minute in enumerate(chunk_minutes, 1):
        if chunk_minute and chunk_minute.strip():
            combined_content.append(chunk_minute.strip())
        else:
            combined_content.append(f"## チャンク {i}\n\n[このチャンクは処理されませんでした]\n")
    
    # 最終的な結合
    full_content = header + "\n\n".join(combined_content)
    
    logger.debug(f"基本結合完了: {len(full_content)}文字")
    return full_content


@with_retry(max_retries=3, backoff_factor=2.0)
def _ai_enhance_combined_minutes(gemini_service: GeminiService, basic_combined: str, state: STTState) -> str:
    """
    AIによる結合議事録の品質向上
    
    Args:
        gemini_service: Geminiサービスインスタンス
        basic_combined: 基本結合された議事録
        state: 現在の処理状態
        
    Returns:
        品質向上された議事録テキスト
    """
    logger = get_logger("combine_minutes")
    
    try:
        logger.debug("AI結合処理を開始")
        
        # 結合・品質向上プロンプトを作成
        prompt = _create_combine_enhancement_prompt(basic_combined, state)
        
        # AIによる結合・品質向上（要約タスクとして実行）
        enhanced_text = gemini_service.generate_minutes_from_text(prompt, task="summarization")
        
        if not enhanced_text or enhanced_text.strip() == "":
            logger.warning("AI結合処理で空の結果が返されました")
            return basic_combined
        
        logger.debug("AI結合処理完了")
        return enhanced_text.strip()
        
    except Exception as e:
        logger.error(f"AI結合処理エラー: {str(e)}")
        raise


def _create_combine_enhancement_prompt(basic_combined: str, state: STTState) -> str:
    """
    結合・品質向上用のプロンプトを作成
    
    Args:
        basic_combined: 基本結合された議事録
        state: 現在の処理状態
        
    Returns:
        プロンプトテキスト
    """
    original_filename = state.get("original_filename", "不明なファイル")
    processing_route = "動画処理ルート" if state.get("force_video_mode") or state.get("file_type") == "video" else "音声処理ルート"
    
    # プロンプトローダーを使用してプロンプトを読み込み、レンダリング
    return load_and_render_prompt(
        category="minutes",
        prompt_name="combine_enhancement",
        original_filename=original_filename,
        processing_route=processing_route,
        basic_combined=basic_combined
    )