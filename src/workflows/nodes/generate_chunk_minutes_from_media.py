"""
STT議事録システム - メディアチャンク議事録生成ノード

メディアチャンクから直接議事録を生成する（マルチモーダル解析ルート）
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.core.ai_services import GeminiService
from src.utils import get_logger, api_call_with_retry, APIError
from src.utils.retry_utils import with_retry
from src.utils.error_handling import handle_error
from src.workflows.state import STTState


def generate_chunk_minutes_from_media_node(state: STTState) -> STTState:
    """
    メディアチャンクから議事録を生成するノード（マルチモーダル解析）
    
    Args:
        state: 現在の処理状態
        
    Returns:
        更新された処理状態
    """
    logger = get_logger("chunk_minutes_media")
    
    try:
        logger.info("メディアチャンクからの議事録生成を開始")
        state["processing_stage"] = "generating_chunk_minutes_from_media"
        
        media_chunks = state.get("media_chunks", [])
        if not media_chunks:
            error_msg = "メディアチャンクが見つかりません"
            logger.error(error_msg)
            state["errors"].append(error_msg)
            return state
        
        # Geminiサービスを初期化
        gemini_api_key = state["settings"].get("gemini_api_key")
        if not gemini_api_key:
            error_msg = "Gemini APIキーが設定されていません"
            error = ValueError(error_msg)
            handle_error(error, "メディアチャンク議事録生成", logger)
            state["errors"].append(error_msg)
            return state
        
        gemini_service = GeminiService(api_key=gemini_api_key)
        
        # 各チャンクから議事録を生成
        chunk_minutes = []
        
        logger.info(f"{len(media_chunks)}個のメディアチャンクを処理中")
        
        # 並列処理で各チャンクを処理
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_chunk = {
                executor.submit(_process_media_chunk, gemini_service, chunk_path, i + 1, state): i
                for i, chunk_path in enumerate(media_chunks)
            }
            
            for future in as_completed(future_to_chunk):
                chunk_index = future_to_chunk[future]
                try:
                    chunk_minute = future.result()
                    chunk_minutes.append(chunk_minute)
                    logger.info(f"チャンク {chunk_index + 1}/{len(media_chunks)} 処理完了")
                except Exception as e:
                    # レート制限エラー（429）の場合、ユーザーフレンドリーなメッセージを表示
                    if isinstance(e, APIError) and e.status_code == 429 and e.retry_delay is not None:
                        error_msg = f"チャンク {chunk_index + 1} 処理エラー: レート制限に達しました。次に送信できる時間は{e.retry_delay}秒後です。"
                        logger.warning(error_msg)
                    else:
                        error_msg = f"チャンク {chunk_index + 1} 処理エラー: {str(e)}"
                        handle_error(e, f"チャンク {chunk_index + 1} 処理", logger)
                    
                    state["errors"].append(error_msg)
                    # エラーが発生したチャンクには空の議事録を追加
                    chunk_minutes.append(f"[チャンク {chunk_index + 1}: 処理エラーのため内容を取得できませんでした]")
        
        # チャンクの順序を保持するためにソート
        chunk_minutes_sorted = []
        for i in range(len(media_chunks)):
            if i < len(chunk_minutes):
                chunk_minutes_sorted.append(chunk_minutes[i])
            else:
                chunk_minutes_sorted.append(f"[チャンク {i + 1}: 処理されませんでした]")
        
        # 結果を状態に保存
        state["chunk_minutes"] = chunk_minutes_sorted
        state["processing_log"].append(f"メディアチャンク議事録生成完了: {len(chunk_minutes_sorted)}個")
        
        logger.info(f"メディアチャンクからの議事録生成完了: {len(chunk_minutes_sorted)}個の議事録")
        
        return state
        
    except Exception as e:
        # レート制限エラー（429）の場合、ユーザーフレンドリーなメッセージを表示
        if isinstance(e, APIError) and e.status_code == 429 and e.retry_delay is not None:
            error_msg = f"メディアチャンク議事録生成エラー: レート制限に達しました。次に送信できる時間は{e.retry_delay}秒後です。"
            logger.warning(error_msg)
            # ユーザーへの表示用メッセージを追加
            state["rate_limit_info"] = {
                "status": "rate_limited",
                "retry_delay": e.retry_delay,
                "retry_time": time.time() + e.retry_delay
            }
        else:
            error_msg = f"メディアチャンク議事録生成エラー: {str(e)}"
            handle_error(e, "メディアチャンク議事録生成", logger)
        
        state["errors"].append(error_msg)
        return state


@with_retry(max_retries=3, backoff_factor=2.0)
def _process_media_chunk(gemini_service: GeminiService, chunk_path: str, chunk_number: int, state: STTState = None) -> str:
    """
    単一のメディアチャンクを処理して議事録を生成
    
    Args:
        gemini_service: Geminiサービスインスタンス
        chunk_path: チャンクファイルパス
        chunk_number: チャンク番号
        state: 処理状態
        
    Returns:
        生成された議事録テキスト
    """
    logger = get_logger("chunk_minutes_media")
    
    try:
        logger.debug(f"チャンク {chunk_number} の処理開始: {chunk_path}")
        
        # メディアファイルから直接議事録を生成
        # Geminiのマルチモーダル機能を使用して動画/音声から議事録を生成
        prompt = _create_media_minutes_prompt(chunk_number, state)
        
        # ファイルの拡張子に基づいて処理方法を決定
        # api_call_with_retry を使用して API レート制限エラーを処理
        minutes_text = api_call_with_retry(
            gemini_service.generate_minutes_from_media,
            chunk_path, 
            prompt,
            max_retries=5,
            backoff_factor=3.0,
            min_delay=2.0,
            max_delay=60.0,
            logger=logger
        )
        
        if not minutes_text or minutes_text.strip() == "":
            return f"[チャンク {chunk_number}: 内容を取得できませんでした]"
        
        # チャンク番号を含む議事録として整形
        formatted_minutes = f"## チャンク {chunk_number}\n\n{minutes_text.strip()}\n"
        
        logger.debug(f"チャンク {chunk_number} の処理完了")
        return formatted_minutes
        
    except Exception as e:
        logger.error(f"チャンク {chunk_number} 処理エラー: {str(e)}")
        raise


def _create_media_minutes_prompt(chunk_number: int, state: STTState = None) -> str:
    """
    メディアチャンク用の議事録生成プロンプトを作成
    
    Args:
        chunk_number: チャンク番号
        state: 処理状態（設定情報を取得するため）
        
    Returns:
        プロンプトテキスト
    """

    # プロンプトローダーを使用して外部ファイルから読み込み
    from src.prompts.minutes_generation import MinutesGenerationPrompts, MinutesFormat

    # 設定タイプを取得（"会議" または "授業"）
    setting_type = None
    if state and "settings" in state:
        setting_type = state["settings"].get("prompt_type")
        
    # 詳細議事録プロンプトを使用し、チャンク番号をカスタム指示として渡す
    template = MinutesGenerationPrompts.get_minutes_prompt(
        format_type=MinutesFormat.DETAILED,
        language="ja", # またはstateから言語を取得
        custom_instructions=f"このメディアファイル（チャンク {chunk_number}）から議事録を生成してください。\n\nこのチャンクの内容のみを対象とし、他のチャンクの内容は含めないでください。",
        setting_type=setting_type
    )
    return template
