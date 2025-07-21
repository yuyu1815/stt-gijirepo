"""
STT議事録システム - 状態管理

LangGraphワークフローで使用する状態クラスの定義
"""

from typing import TypedDict, List, Optional, Dict, Any
from datetime import datetime


class STTState(TypedDict):
    """STTワークフローの状態管理クラス"""
    
    # 基本情報
    session_id: str
    timestamp: datetime
    
    # 入力情報
    file_path: str
    original_filename: str
    file_size: int
    settings: Dict[str, Any]
    
    # ファイル解析結果
    file_type: Optional[str]  # "video" | "audio"
    mime_type: Optional[str]
    is_video_dark: Optional[bool]
    audio_duration: Optional[float]
    audio_sample_rate: Optional[int]
    audio_channels: Optional[int]
    
    # 処理状態
    chunks: Optional[List[str]]
    chunk_durations: Optional[List[float]]
    processing_stage: str
    
    # 新しいワークフロー用の状態
    media_chunks: Optional[List[str]]  # 分割されたメディアチャンクのパスリスト
    chunk_transcriptions: Optional[List[str]]  # 音声ルートでのみ使用
    chunk_minutes: Optional[List[str]]  # 両ルートで生成され、結合される
    combined_minutes_text: Optional[str]  # 結合された中間議事録
    
    # AI処理結果
    transcription: Optional[str]
    transcription_confidence: Optional[float]
    quality_check_result: Optional[Dict[str, Any]]
    minutes: Optional[str]
    summary: Optional[str]
    
    # クラス情報（既存機能）
    class_info: Optional[Dict[str, Any]]
    
    # エラー・ログ
    errors: List[str]
    warnings: List[str]
    processing_log: List[str]
    performance_metrics: Dict[str, float]
    
    # 設定・フラグ
    upload_to_notion: bool
    force_video_mode: bool
    notion_database_id: Optional[str]
    notion_page_id: Optional[str]
    
    # 出力情報
    output_files: List[str]
    final_status: str  # "success" | "error" | "partial"


class STTConfig(TypedDict):
    """STTシステム設定クラス"""
    
    # API設定
    gemini_api_key: str
    gemini_model: str
    notion_token: Optional[str]
    
    # 処理設定
    max_audio_duration: int  # 秒
    chunk_size: int  # 秒
    max_retries: int
    retry_delay: float
    
    # 品質設定
    min_confidence_threshold: float
    enable_quality_check: bool
    enable_hallucination_check: bool
    
    # 出力設定
    output_format: str  # "markdown" | "text" | "json"
    include_timestamps: bool
    include_speaker_labels: bool
    
    # Notion設定
    notion_database_id: Optional[str]
    notion_template_id: Optional[str]


def create_initial_state(
    file_path: str,
    config: STTConfig,
    upload_to_notion: bool = False,
    force_video_mode: bool = False
) -> STTState:
    """初期状態を作成する関数"""
    import uuid
    import os
    
    return STTState(
        # 基本情報
        session_id=str(uuid.uuid4()),
        timestamp=datetime.now(),
        
        # 入力情報
        file_path=file_path,
        original_filename=os.path.basename(file_path),
        file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        settings=dict(config),
        
        # ファイル解析結果
        file_type=None,
        mime_type=None,
        is_video_dark=None,
        audio_duration=None,
        audio_sample_rate=None,
        audio_channels=None,
        
        # 処理状態
        chunks=None,
        chunk_durations=None,
        processing_stage="initialized",
        
        # 新しいワークフロー用の状態
        media_chunks=None,
        chunk_transcriptions=None,
        chunk_minutes=None,
        combined_minutes_text=None,
        
        # AI処理結果
        transcription=None,
        transcription_confidence=None,
        quality_check_result=None,
        minutes=None,
        summary=None,
        
        # クラス情報
        class_info=None,
        
        # エラー・ログ
        errors=[],
        warnings=[],
        processing_log=["ワークフロー初期化完了"],
        performance_metrics={},
        
        # 設定・フラグ
        upload_to_notion=upload_to_notion,
        force_video_mode=force_video_mode,
        notion_database_id=config.get("notion_database_id"),
        notion_page_id=None,
        
        # 出力情報
        output_files=[],
        final_status="initialized"
    )


def create_default_config() -> STTConfig:
    """デフォルト設定を作成する関数"""
    import os
    
    return STTConfig(
        # API設定
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model="gemini-1.5-pro",
        notion_token=os.getenv("NOTION_TOKEN"),
        
        # 処理設定
        max_audio_duration=2400,  # 40分
        chunk_size=600,  # 10分
        max_retries=5,
        retry_delay=2.0,
        
        # 品質設定
        min_confidence_threshold=0.7,
        enable_quality_check=True,
        enable_hallucination_check=True,
        
        # 出力設定
        output_format="markdown",
        include_timestamps=True,
        include_speaker_labels=False,
        
        # Notion設定
        notion_database_id=os.getenv("NOTION_DATABASE_ID"),
        notion_template_id=None
    )