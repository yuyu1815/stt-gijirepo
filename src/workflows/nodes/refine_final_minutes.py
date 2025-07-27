"""
STT議事録システム - 最終議事録精製ノード

結合された議事録を最終的に精製・品質向上する
"""

from datetime import datetime
from typing import Dict, Any

from src.core.ai_services import GeminiService
from src.utils import get_logger
from src.utils.retry_utils import with_retry
from src.utils.class_info import get_class_info
from src.workflows.state import STTState


def refine_final_minutes_node(state: STTState) -> STTState:
    """
    最終議事録を精製するノード
    
    Args:
        state: 現在の処理状態
        
    Returns:
        更新された処理状態
    """
    logger = get_logger("refine_minutes")
    
    try:
        logger.info("最終議事録の精製を開始")
        state["processing_stage"] = "refining_final_minutes"
        
        combined_minutes_text = state.get("combined_minutes_text")
        if not combined_minutes_text:
            error_msg = "精製対象の結合議事録が見つかりません"
            logger.error(error_msg)
            state["errors"].append(error_msg)
            return state
        
        # クラス情報を取得（既存機能）
        class_info = _extract_class_info(state)
        if class_info:
            state["class_info"] = class_info
            logger.info(f"クラス情報を抽出: {class_info.get('period', '不明')}")
        
        # Geminiサービスを初期化
        gemini_api_key = state["settings"].get("gemini_api_key")
        if not gemini_api_key:
            # APIキーがない場合は基本的な精製のみ
            logger.info("Gemini APIキーが未設定のため、基本精製のみ実行")
            refined_minutes = _basic_refine_minutes(combined_minutes_text, state)
        else:
            # AIによる高度な精製
            logger.info("AIによる高度な精製処理を実行")
            gemini_service = GeminiService(api_key=gemini_api_key)
            
            try:
                refined_minutes = _ai_refine_minutes(
                    gemini_service, 
                    combined_minutes_text, 
                    state
                )
            except Exception as e:
                logger.warning(f"AI精製処理でエラーが発生、基本精製を使用: {str(e)}")
                refined_minutes = _basic_refine_minutes(combined_minutes_text, state)
        
        # 最終的な議事録として保存
        state["minutes"] = refined_minutes
        state["processing_log"].append("最終議事録精製完了")
        
        logger.info("最終議事録精製完了")
        
        return state
        
    except Exception as e:
        error_msg = f"最終議事録精製エラー: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append(error_msg)
        return state


def _extract_class_info(state: STTState) -> Dict[str, Any]:
    """
    クラス情報を抽出（既存機能の活用）
    
    Args:
        state: 現在の処理状態
        
    Returns:
        クラス情報辞書
    """
    try:
        audio_duration = state.get("audio_duration")
        if audio_duration:
            # 分単位に変換
            duration_minutes = int(audio_duration / 60)
            class_info = get_class_info(duration_minutes)
            return class_info
    except Exception as e:
        logger = get_logger("refine_minutes")
        logger.warning(f"クラス情報抽出エラー: {str(e)}")
    
    return {}


def _basic_refine_minutes(combined_minutes: str, state: STTState) -> str:
    """
    基本的な議事録精製
    
    Args:
        combined_minutes: 結合された議事録
        state: 現在の処理状態
        
    Returns:
        精製された議事録
    """
    logger = get_logger("refine_minutes")
    
    # 基本的なメタデータを追加
    original_filename = state.get("original_filename", "不明なファイル")
    timestamp = state.get("timestamp", datetime.now())
    class_info = state.get("class_info", {})
    
    # ヘッダーを更新
    header = f"""# 議事録

**ファイル名**: {original_filename}  
**作成日時**: {timestamp.strftime('%Y年%m月%d日 %H:%M:%S')}  
"""
    
    if class_info:
        header += f"**授業時限**: {class_info.get('period', '不明')}  \n"
        header += f"**推定時間**: {class_info.get('time_range', '不明')}  \n"
    
    header += "\n---\n\n"
    
    # 既存の内容から古いヘッダーを削除
    content_lines = combined_minutes.split('\n')
    content_start = 0
    
    # "---" までの行をスキップ
    for i, line in enumerate(content_lines):
        if line.strip() == "---":
            content_start = i + 1
            break
    
    refined_content = '\n'.join(content_lines[content_start:]).strip()
    
    # 最終的な議事録を構成
    final_minutes = header + refined_content
    
    logger.debug(f"基本精製完了: {len(final_minutes)}文字")
    return final_minutes


@with_retry(max_retries=3, backoff_factor=2.0)
def _ai_refine_minutes(gemini_service: GeminiService, combined_minutes: str, state: STTState) -> str:
    """
    AIによる高度な議事録精製
    
    Args:
        gemini_service: Geminiサービスインスタンス
        combined_minutes: 結合された議事録
        state: 現在の処理状態
        
    Returns:
        精製された議事録
    """
    logger = get_logger("refine_minutes")
    
    try:
        logger.debug("AI精製処理を開始")
        
        # 精製プロンプトを作成
        prompt = _create_refinement_prompt(combined_minutes, state)
        
        # AIによる精製（議事録生成タスクとして実行）
        refined_text = gemini_service.generate_minutes_from_text(prompt, task="minutes_generation")
        
        if not refined_text or refined_text.strip() == "":
            logger.warning("AI精製処理で空の結果が返されました")
            return _basic_refine_minutes(combined_minutes, state)
        
        logger.debug("AI精製処理完了")
        return refined_text.strip()
        
    except Exception as e:
        logger.error(f"AI精製処理エラー: {str(e)}")
        raise


def _create_refinement_prompt(combined_minutes: str, state: STTState) -> str:
    """
    精製用のプロンプトを作成
    
    Args:
        combined_minutes: 結合された議事録
        state: 現在の処理状態
        
    Returns:
        プロンプトテキスト
    """
    original_filename = state.get("original_filename", "不明なファイル")
    class_info = state.get("class_info", {})
    processing_route = "動画処理ルート" if state.get("force_video_mode") or state.get("file_type") == "video" else "音声処理ルート"
    
    class_info_text = ""
    if class_info:
        class_info_text = f"""
- 授業時限: {class_info.get('period', '不明')}
- 推定時間: {class_info.get('time_range', '不明')}"""
    
    return f"""
以下の議事録を最終版として精製してください。読みやすさ、正確性、実用性を重視して改善してください。

【処理情報】
- ファイル名: {original_filename}
- 処理ルート: {processing_route}{class_info_text}

【議事録（精製前）】
{combined_minutes}

以下の点に注意して最終的な議事録を作成してください：

1. **構造の最適化**: 
   - 論理的で読みやすい見出し構造
   - 適切な段落分けと箇条書きの使用
   - 重要度に応じた情報の階層化

2. **内容の精製**:
   - 重複内容の統合と整理
   - 不明確な表現の明確化
   - 重要な決定事項の強調

3. **実用性の向上**:
   - アクションアイテムの明確な整理
   - 決定事項と議論事項の分離
   - 今後の課題や宿題の明記

4. **品質の向上**:
   - 文法や表現の自然さの改善
   - 専門用語の適切な使用
   - 読み手にとって分かりやすい表現

5. **メタデータの整備**:
   - 適切なタイトルと日時情報
   - 参加者情報（判明している場合）
   - 議事録の概要や要約

出力形式：
- Markdown形式で出力
- 適切な見出し構造（H1, H2, H3）
- 重要な部分は太字で強調
- 決定事項やアクションアイテムは専用セクション
- 必要に応じて表や箇条書きを活用

実用的で読みやすい、高品質な最終議事録を作成してください。
"""