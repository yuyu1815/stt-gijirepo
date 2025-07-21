"""
STT議事録システム - テキストチャンク議事録生成ノード

文字起こしされたテキストチャンクから議事録を生成する（文字起こしベースルート）
"""

from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.core.ai_services import GeminiService
from src.utils import get_logger
from src.utils.retry_utils import with_retry
from src.utils.error_handling import handle_error
from src.workflows.state import STTState


def generate_chunk_minutes_from_text_node(state: STTState) -> STTState:
    """
    文字起こしテキストチャンクから議事録を生成するノード
    
    Args:
        state: 現在の処理状態
        
    Returns:
        更新された処理状態
    """
    logger = get_logger("chunk_minutes_text")
    
    try:
        logger.info("テキストチャンクからの議事録生成を開始")
        state["processing_stage"] = "generating_chunk_minutes_from_text"
        
        chunk_transcriptions = state.get("chunk_transcriptions", [])
        if not chunk_transcriptions:
            error_msg = "文字起こしチャンクが見つかりません"
            error = ValueError(error_msg)
            handle_error(error, "テキストチャンク議事録生成", logger)
            state["errors"].append(error_msg)
            return state
        
        # Geminiサービスを初期化
        gemini_api_key = state["settings"].get("gemini_api_key")
        if not gemini_api_key:
            error_msg = "Gemini APIキーが設定されていません"
            error = ValueError(error_msg)
            handle_error(error, "テキストチャンク議事録生成", logger)
            state["errors"].append(error_msg)
            return state
        
        gemini_service = GeminiService(api_key=gemini_api_key)
        
        # 各テキストチャンクから議事録を生成
        chunk_minutes = []
        
        logger.info(f"{len(chunk_transcriptions)}個のテキストチャンクを処理中")
        
        # 並列処理で各チャンクを処理
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_chunk = {
                executor.submit(_process_text_chunk, gemini_service, transcription_text, i + 1): i
                for i, transcription_text in enumerate(chunk_transcriptions)
            }
            
            for future in as_completed(future_to_chunk):
                chunk_index = future_to_chunk[future]
                try:
                    chunk_minute = future.result()
                    chunk_minutes.append(chunk_minute)
                    logger.info(f"チャンク {chunk_index + 1}/{len(chunk_transcriptions)} 処理完了")
                except Exception as e:
                    error_msg = f"チャンク {chunk_index + 1} 処理エラー: {str(e)}"
                    handle_error(e, f"チャンク {chunk_index + 1} 処理", logger)
                    state["errors"].append(error_msg)
                    # エラーが発生したチャンクには空の議事録を追加
                    chunk_minutes.append(f"[チャンク {chunk_index + 1}: 処理エラーのため内容を取得できませんでした]")
        
        # チャンクの順序を保持するためにソート
        chunk_minutes_sorted = []
        for i in range(len(chunk_transcriptions)):
            if i < len(chunk_minutes):
                chunk_minutes_sorted.append(chunk_minutes[i])
            else:
                chunk_minutes_sorted.append(f"[チャンク {i + 1}: 処理されませんでした]")
        
        # 結果を状態に保存
        state["chunk_minutes"] = chunk_minutes_sorted
        state["processing_log"].append(f"テキストチャンク議事録生成完了: {len(chunk_minutes_sorted)}個")
        
        logger.info(f"テキストチャンクからの議事録生成完了: {len(chunk_minutes_sorted)}個の議事録")
        
        return state
        
    except Exception as e:
        error_msg = f"テキストチャンク議事録生成エラー: {str(e)}"
        handle_error(e, "テキストチャンク議事録生成", logger)
        state["errors"].append(error_msg)
        return state


@with_retry(max_retries=3, backoff_factor=2.0)
def _process_text_chunk(gemini_service: GeminiService, transcription_text: str, chunk_number: int) -> str:
    """
    単一のテキストチャンクを処理して議事録を生成
    
    Args:
        gemini_service: Geminiサービスインスタンス
        transcription_text: 文字起こしテキスト
        chunk_number: チャンク番号
        
    Returns:
        生成された議事録テキスト
    """
    logger = get_logger("chunk_minutes_text")
    
    try:
        logger.debug(f"チャンク {chunk_number} の処理開始")
        
        # 文字起こしテキストが空の場合
        if not transcription_text or transcription_text.strip() == "":
            return f"[チャンク {chunk_number}: 文字起こし内容が空のため議事録を生成できませんでした]"
        
        # テキストから議事録を生成
        prompt = _create_text_minutes_prompt(chunk_number, transcription_text)
        minutes_text = gemini_service.generate_minutes_from_text(prompt)
        
        if not minutes_text or minutes_text.strip() == "":
            return f"[チャンク {chunk_number}: 議事録を生成できませんでした]"
        
        # チャンク番号を含む議事録として整形
        formatted_minutes = f"## チャンク {chunk_number}\n\n{minutes_text.strip()}\n"
        
        logger.debug(f"チャンク {chunk_number} の処理完了")
        return formatted_minutes
        
    except Exception as e:
        logger.error(f"チャンク {chunk_number} 処理エラー: {str(e)}")
        raise


def _create_text_minutes_prompt(chunk_number: int, transcription_text: str) -> str:
    """
    テキストチャンク用の議事録生成プロンプトを作成
    
    Args:
        chunk_number: チャンク番号
        transcription_text: 文字起こしテキスト
        
    Returns:
        プロンプトテキスト
    """
    try:
        # プロンプトローダーを使用して外部ファイルから読み込み
        from src.utils.prompt_loader import PromptLoader
        loader = PromptLoader()
        template = loader.load_prompt("minutes_generation", "chunk_text_minutes")
        return template.format(chunk_number=chunk_number, transcription_text=transcription_text)
    except Exception as e:
        # フォールバック用のデフォルトプロンプト
        from src.utils import get_logger
        logger = get_logger("chunk_minutes_text")
        logger.warning(f"外部プロンプトファイルの読み込みに失敗、デフォルトを使用: {str(e)}")
        
        return f"""
以下の文字起こしテキスト（チャンク {chunk_number}）から議事録を生成してください。

【文字起こしテキスト】
{transcription_text}

以下の点に注意して議事録を作成してください：

1. **内容の要約**: 話し合われた主要なトピックや議題を明確に記載
2. **発言者の識別**: 可能な限り発言者を特定し、発言内容を整理
3. **重要な決定事項**: 決定された事項や合意点を明確に記載
4. **アクションアイテム**: 今後の行動項目や担当者があれば記載
5. **時系列の整理**: 議論の流れを時系列で整理
6. **文字起こしの修正**: 明らかな誤字脱字や不自然な表現は適切に修正

出力形式：
- Markdown形式で出力
- 見出しや箇条書きを適切に使用
- 重要な部分は太字で強調
- 文字起こしの生テキストは含めず、整理された議事録のみを出力

このチャンクの内容のみを対象とし、他のチャンクの内容は含めないでください。
"""