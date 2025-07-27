"""
STT議事録システム - メインワークフロー定義

LangGraphを使用したSTT議事録システムのメインワークフロー
"""

from typing import Dict, Any, Literal, Optional, cast

# LangGraphのインポートを試行

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables.config import RunnableConfig


from src.workflows.state import STTState, STTConfig, create_initial_state
from src.workflows.nodes import (
    analyze_file_node,
    process_video_node,
    split_audio_node,
    transcribe_node,
    quality_check_node,
    generate_minutes_node,
    upload_notion_node
)
from src.workflows.nodes.split_media import split_media_node
from src.workflows.nodes.generate_chunk_minutes_from_media import generate_chunk_minutes_from_media_node
from src.workflows.nodes.generate_chunk_minutes_from_text import generate_chunk_minutes_from_text_node
from src.workflows.nodes.combine_chunk_minutes import combine_chunk_minutes_node
from src.workflows.nodes.refine_final_minutes import refine_final_minutes_node
from src.utils import get_logger
from src.utils.logging_config import LogContext


def create_stt_workflow() -> StateGraph:
    """
    STTワークフローを作成

    Returns:
        構築されたワークフローグラフ
    """
    # ワークフローグラフを初期化
    workflow = StateGraph(STTState)

    # ノードを追加
    workflow.add_node("file_analysis", analyze_file_node)
    workflow.add_node("video_processing", process_video_node)
    workflow.add_node("audio_splitting", split_audio_node)
    workflow.add_node("transcription", transcribe_node)
    workflow.add_node("quality_check", quality_check_node)
    workflow.add_node("minutes_generation", generate_minutes_node)
    workflow.add_node("notion_upload", upload_notion_node)
    workflow.add_node("error_handler", error_handler_node)

    # 新しいワークフロー用のノードを追加
    workflow.add_node("split_media", split_media_node)
    workflow.add_node("generate_chunk_minutes_from_media", generate_chunk_minutes_from_media_node)
    workflow.add_node("generate_chunk_minutes_from_text", generate_chunk_minutes_from_text_node)
    workflow.add_node("combine_chunk_minutes", combine_chunk_minutes_node)
    workflow.add_node("refine_final_minutes", refine_final_minutes_node)
    
    # エントリーポイントを設定
    workflow.set_entry_point("file_analysis")
    
    # 新しいブランチワークフローの条件分岐を定義
    workflow.add_conditional_edges(
        "file_analysis",
        route_after_file_analysis,
        {
            "split_media": "split_media",
            "error": "error_handler"
        }
    )
    
    workflow.add_conditional_edges(
        "split_media",
        route_after_split_media,
        {
            "generate_chunk_minutes_from_media": "generate_chunk_minutes_from_media",
            "transcription": "transcription",
            "error": "error_handler"
        }
    )
    
    workflow.add_conditional_edges(
        "transcription",
        route_after_transcription,
        {
            "generate_chunk_minutes_from_text": "generate_chunk_minutes_from_text",
            "error": "error_handler"
        }
    )
    
    # 両ルートから combine_chunk_minutes へ
    workflow.add_conditional_edges(
        "generate_chunk_minutes_from_media",
        route_after_chunk_minutes_generation,
        {
            "combine_chunk_minutes": "combine_chunk_minutes",
            "error": "error_handler"
        }
    )
    
    workflow.add_conditional_edges(
        "generate_chunk_minutes_from_text",
        route_after_chunk_minutes_generation,
        {
            "combine_chunk_minutes": "combine_chunk_minutes",
            "error": "error_handler"
        }
    )
    
    workflow.add_conditional_edges(
        "combine_chunk_minutes",
        route_after_combine_chunk_minutes,
        {
            "refine_final_minutes": "refine_final_minutes",
            "error": "error_handler"
        }
    )
    
    workflow.add_conditional_edges(
        "refine_final_minutes",
        route_after_refine_final_minutes,
        {
            "quality_check": "quality_check",
            "error": "error_handler"
        }
    )
    
    workflow.add_conditional_edges(
        "quality_check",
        route_after_quality_check,
        {
            "notion_upload": "notion_upload",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "notion_upload",
        route_after_notion_upload,
        {
            "end": END,
            "error": "error_handler"
        }
    )
    
    workflow.add_edge("error_handler", END)
    
    return workflow


def route_after_file_analysis(state: STTState) -> Literal["split_media", "error"]:
    """
    ファイル解析後のルーティング（新しいワークフロー）
    
    Args:
        state: 現在の状態
        
    Returns:
        次のノード名
    """
    # エラーチェック
    if state.get("errors"):
        return "error"
    
    file_type = state.get("file_type")
    
    # 新しいワークフローでは全てのファイルをsplit_mediaに送る
    if file_type in ["video", "audio"]:
        return "split_media"
    else:
        # 不明なファイル形式の場合はエラー
        state["errors"].append(f"サポートされていないファイル形式: {file_type}")
        return "error"


def route_after_video_processing(state: STTState) -> Literal["audio_splitting", "transcription", "error"]:
    """
    動画処理後のルーティング
    
    Args:
        state: 現在の状態
        
    Returns:
        次のノード名
    """
    # エラーチェック
    if state.get("errors"):
        return "error"
    
    # 動画が暗い場合は音声抽出済みなので音声分割へ
    # 明るい場合は直接文字起こしへ
    is_video_dark = state.get("is_video_dark", False)
    
    if is_video_dark:
        # 音声抽出済みなので音声分割をチェック
        return "audio_splitting"
    else:
        # 明るい動画は直接文字起こし
        return "transcription"


def route_after_audio_splitting(state: STTState) -> Literal["transcription", "error"]:
    """
    音声分割後のルーティング
    
    Args:
        state: 現在の状態
        
    Returns:
        次のノード名
    """
    # エラーチェック
    if state.get("errors"):
        return "error"
    
    # 音声分割後は必ず文字起こしへ
    return "transcription"


def route_after_transcription(state: STTState) -> Literal["generate_chunk_minutes_from_text", "error"]:
    """
    文字起こし後のルーティング
    
    Args:
        state: 現在の状態
        
    Returns:
        次のノード名
    """
    # エラーチェック
    if state.get("errors"):
        return "error"
    
    # 文字起こし結果があるかチェック
    transcription = state.get("transcription", "")
    if not transcription:
        state["errors"].append("文字起こし結果が空です")
        return "error"
    
    return "generate_chunk_minutes_from_text"


def route_after_quality_check(state: STTState) -> Literal["minutes_generation", "error"]:
    """
    品質チェック後のルーティング
    
    Args:
        state: 現在の状態
        
    Returns:
        次のノード名
    """
    # エラーチェック
    if state.get("errors"):
        return "error"
    
    # 品質チェック後は議事録生成へ
    return "minutes_generation"


def route_after_minutes_generation(state: STTState) -> Literal["notion_upload", "end"]:
    """
    議事録生成後のルーティング
    
    Args:
        state: 現在の状態
        
    Returns:
        次のノード名
    """
    # Notionアップロードが有効な場合はアップロードへ
    if state.get("upload_to_notion", False):
        return "notion_upload"
    else:
        # アップロードしない場合は終了
        state["final_status"] = "success"
        return "end"


def route_after_notion_upload(state: STTState) -> Literal["end", "error"]:
    """
    Notionアップロード後のルーティング
    
    Args:
        state: 現在の状態
        
    Returns:
        次のノード名
    """
    # エラーチェック
    if state.get("errors"):
        # Notionアップロードエラーは致命的ではないので警告として処理
        notion_errors = [error for error in state["errors"] if "Notion" in error]
        if notion_errors:
            state["warnings"].extend(notion_errors)
            # Notionエラーをエラーリストから削除
            state["errors"] = [error for error in state["errors"] if "Notion" not in error]
    
    state["final_status"] = "success"
    return "end"


def route_after_split_media(state: STTState) -> Literal["generate_chunk_minutes_from_media", "transcription", "error"]:
    """
    メディア分割後のルーティング
    
    Args:
        state: 現在の状態
        
    Returns:
        次のノード名
    """
    # エラーチェック
    if state.get("errors"):
        return "error"
    
    file_type = state.get("file_type")
    force_video_mode = state.get("force_video_mode", False)
    
    # 動画ファイルまたは強制動画モードの場合は動画処理ルートへ
    if file_type == "video" or force_video_mode:
        return "generate_chunk_minutes_from_media"
    else:
        # 音声処理ルートは文字起こしへ
        return "transcription"


def route_after_chunk_minutes_generation(state: STTState) -> Literal["combine_chunk_minutes", "error"]:
    """
    チャンク議事録生成後のルーティング
    
    Args:
        state: 現在の状態
        
    Returns:
        次のノード名
    """
    # エラーチェック
    if state.get("errors"):
        return "error"
    
    # チャンク議事録が生成されたら結合へ
    return "combine_chunk_minutes"


def route_after_combine_chunk_minutes(state: STTState) -> Literal["refine_final_minutes", "error"]:
    """
    チャンク議事録結合後のルーティング
    
    Args:
        state: 現在の状態
        
    Returns:
        次のノード名
    """
    # エラーチェック
    if state.get("errors"):
        return "error"
    
    # 結合後は精製へ
    return "refine_final_minutes"


def route_after_refine_final_minutes(state: STTState) -> Literal["quality_check", "error"]:
    """
    最終議事録精製後のルーティング
    
    Args:
        state: 現在の状態
        
    Returns:
        次のノード名
    """
    # エラーチェック
    if state.get("errors"):
        return "error"
    
    # 精製後は品質チェックへ
    return "quality_check"


def error_handler_node(state: STTState) -> STTState:
    """
    エラーハンドリングノード
    
    Args:
        state: 現在の状態
        
    Returns:
        更新された状態
    """
    logger = get_logger("workflow")
    
    with LogContext(logger, "エラーハンドリング", state["session_id"]) as ctx:
        # エラー状態を設定
        state["final_status"] = "error"
        state["processing_stage"] = "error"
        
        # エラーサマリーを作成
        error_count = len(state.get("errors", []))
        warning_count = len(state.get("warnings", []))
        
        ctx.log_progress(f"エラー処理: {error_count}件のエラー, {warning_count}件の警告")
        
        # エラーログを出力
        for error in state.get("errors", []):
            logger.error(f"ワークフローエラー: {error}")
        
        for warning in state.get("warnings", []):
            logger.warning(f"ワークフロー警告: {warning}")
        
        # 処理ログに追加
        state["processing_log"].append(f"エラー終了: {error_count}件のエラーが発生")
        
        logger.error(f"ワークフローがエラーで終了しました: {error_count}件のエラー")
    
    return state


def execute_stt_workflow(
    file_path: str,
    config: STTConfig,
    upload_to_notion: bool = False,
    force_video_mode: bool = False,
    checkpointer: Any = None
) -> STTState:
    """
    STTワークフローを実行
    
    Args:
        file_path: 処理対象ファイルパス
        config: システム設定
        upload_to_notion: Notionアップロードフラグ
        force_video_mode: 音声ファイルを動画処理ルートで強制処理するフラグ
        checkpointer: チェックポイント機能（オプション）
        
    Returns:
        処理結果を含む状態オブジェクト
    """
    logger = get_logger("workflow")
    
    try:
        # 初期状態を作成
        initial_state = create_initial_state(file_path, config, upload_to_notion, force_video_mode)
        
        logger.info(f"STTワークフロー開始: {file_path} (セッション: {initial_state['session_id']})")
        
        # ワークフローを構築
        workflow = create_stt_workflow()
        
        # チェックポイント機能を設定
        if checkpointer is None:
            checkpointer = MemorySaver()
        
        app = workflow.compile(checkpointer=checkpointer)
        
        # ワークフローを実行
        config_dict = {"configurable": {"thread_id": initial_state["session_id"]}}
        runnable_config = cast(Optional[RunnableConfig], config_dict)
        
        final_state = None
        # Cast initial_state to Any to satisfy type checker
        initial_state_any = cast(Any, initial_state)
        for state in app.stream(initial_state_any, runnable_config):
            final_state = state
            # 進捗ログ
            current_stage = list(state.keys())[0] if state else "unknown"
            logger.debug(f"ワークフロー進捗: {current_stage}")
        
        if final_state is None:
            raise RuntimeError("ワークフローの実行に失敗しました")
        
        # 最終状態を取得
        result_state = list(final_state.values())[0]
        
        # 実行結果をログ
        final_status = result_state.get("final_status", "unknown")
        error_count = len(result_state.get("errors", []))
        warning_count = len(result_state.get("warnings", []))
        
        logger.info(f"STTワークフロー完了: {final_status} (エラー: {error_count}, 警告: {warning_count})")
        
        return result_state
        
    except Exception as e:
        logger.error(f"STTワークフロー実行エラー: {str(e)}", exc_info=True)
        
        # エラー状態を作成
        error_state = create_initial_state(file_path, config, upload_to_notion, force_video_mode)
        error_state["errors"].append(f"ワークフロー実行エラー: {str(e)}")
        error_state["final_status"] = "error"
        
        return error_state


def execute_batch_processing(
    file_paths: list,
    config: STTConfig,
    max_concurrent: int = 3,
    upload_to_notion: bool = False,
    force_video_mode: bool = False
) -> list:
    """
    複数ファイルの並列処理
    
    Args:
        file_paths: 処理対象ファイルパスのリスト
        config: システム設定
        max_concurrent: 最大並列数
        upload_to_notion: Notionアップロードフラグ
        force_video_mode: 音声ファイルを動画処理ルートで強制処理するフラグ
        
    Returns:
        各ファイルの処理結果リスト
    """
    import concurrent.futures
    from threading import Lock
    
    logger = get_logger("workflow")
    results = []
    results_lock = Lock()
    
    def process_single_file(file_path: str) -> STTState:
        """単一ファイルの処理"""
        try:
            result = execute_stt_workflow(file_path, config, upload_to_notion, force_video_mode)
            
            with results_lock:
                results.append(result)
                logger.info(f"バッチ処理完了: {file_path} ({result.get('final_status', 'unknown')})")
            
            return result
            
        except Exception as e:
            logger.error(f"バッチ処理エラー: {file_path} - {str(e)}")
            
            # エラー状態を作成
            error_state = create_initial_state(file_path, config, upload_to_notion)
            error_state["errors"].append(f"バッチ処理エラー: {str(e)}")
            error_state["final_status"] = "error"
            
            with results_lock:
                results.append(error_state)
            
            return error_state
    
    logger.info(f"バッチ処理開始: {len(file_paths)}ファイル (最大並列数: {max_concurrent})")
    
    # 並列処理実行
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = [executor.submit(process_single_file, file_path) for file_path in file_paths]
        
        # 全ての処理完了を待機
        concurrent.futures.wait(futures)
    
    # 結果をファイルパス順にソート
    sorted_results = []
    for file_path in file_paths:
        for result in results:
            if result.get("file_path") == file_path:
                sorted_results.append(result)
                break
    
    # 統計情報をログ
    success_count = sum(1 for r in sorted_results if r.get("final_status") == "success")
    error_count = len(sorted_results) - success_count
    
    logger.info(f"バッチ処理完了: 成功 {success_count}件, エラー {error_count}件")
    
    return sorted_results


def get_workflow_status(state: STTState) -> Dict[str, Any]:
    """
    ワークフローの状態情報を取得
    
    Args:
        state: ワークフロー状態
        
    Returns:
        状態情報の辞書
    """
    return {
        "session_id": state.get("session_id", ""),
        "processing_stage": state.get("processing_stage", ""),
        "final_status": state.get("final_status", ""),
        "file_path": state.get("file_path", ""),
        "file_type": state.get("file_type", ""),
        "audio_duration": state.get("audio_duration", 0),
        "transcription_length": len(state.get("transcription", "")),
        "minutes_length": len(state.get("minutes", "")),
        "quality_score": state.get("quality_check_result", {}).get("overall_score", 0),
        "notion_page_id": state.get("notion_page_id", ""),
        "error_count": len(state.get("errors", [])),
        "warning_count": len(state.get("warnings", [])),
        "processing_log": state.get("processing_log", [])
    }


def validate_workflow_config(config: STTConfig) -> Dict[str, Any]:
    """
    ワークフロー設定を検証
    
    Args:
        config: 設定辞書
        
    Returns:
        検証結果
    """
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": []
    }
    
    # 必須設定のチェック
    required_keys = ["gemini_api_key"]
    for key in required_keys:
        if not config.get(key):
            validation_result["errors"].append(f"必須設定が不足しています: {key}")
            validation_result["valid"] = False
    
    # Notion設定のチェック
    if config.get("notion_token") and not config.get("notion_database_id"):
        validation_result["warnings"].append("Notionトークンが設定されていますがデータベースIDがありません")
    
    # 数値設定のチェック
    numeric_settings = {
        "max_audio_duration": (60, 7200),  # 1分〜2時間
        "chunk_size": (60, 1800),  # 1分〜30分
        "max_retries": (1, 10),
        "min_confidence_threshold": (0.0, 1.0)
    }
    
    for key, (min_val, max_val) in numeric_settings.items():
        value = config.get(key)
        if value is not None:
            if not isinstance(value, (int, float)) or not (min_val <= value <= max_val):
                validation_result["warnings"].append(f"設定値が範囲外です: {key}={value} (範囲: {min_val}-{max_val})")
    
    return validation_result