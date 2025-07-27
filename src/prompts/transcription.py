"""
STT議事録システム - 文字起こし用プロンプト

文字起こし処理で使用するプロンプトテンプレートを管理
"""

from typing import Dict, Any, Optional
from enum import Enum
import logging

from src.utils.prompt_loader import load_and_render_prompt_with_language

logger = logging.getLogger(__name__)


class TranscriptionQuality(Enum):
    """文字起こし品質"""
    BASIC = "basic"
    STANDARD = "standard"
    HIGH = "high"
    PROFESSIONAL = "professional"


class TranscriptionContext(Enum):
    """文字起こしコンテキスト"""
    MEETING = "meeting"
    LECTURE = "lecture"
    INTERVIEW = "interview"
    PRESENTATION = "presentation"
    GENERAL = "general"


class TranscriptionPrompts:
    """文字起こし用プロンプトクラス"""
    
    @classmethod
    def get_transcription_prompt(
        cls,
        language: str = "ja",
        quality: TranscriptionQuality = TranscriptionQuality.STANDARD,
        context: TranscriptionContext = TranscriptionContext.GENERAL,
        custom_instructions: Optional[str] = None
    ) -> str:
        """
        文字起こし用プロンプトを取得
        
        Args:
            language: 言語コード ("ja", "en")
            quality: 文字起こし品質
            context: 文字起こしコンテキスト
            custom_instructions: カスタム指示
            
        Returns:
            str: 文字起こし用プロンプト
            
        Raises:
            FileNotFoundError: プロンプトファイルが見つからない場合
            ValueError: プロンプトの形式が不正な場合
        """
        try:
            # コンテキストが指定されている場合はコンテキスト用プロンプトを使用
            if context != TranscriptionContext.GENERAL:
                prompt_name = f"{context.value}"
            else:
                # 品質レベルに応じたプロンプトを使用
                prompt_name = f"{quality.value}"
            
            # プロンプトを読み込んでレンダリング
            return load_and_render_prompt_with_language(
                category="transcription",
                prompt_name=prompt_name,
                language=language,
                custom_instructions=custom_instructions or ""
            )
        except FileNotFoundError as e:
            error_msg = f"文字起こし用プロンプトファイルが見つかりません: quality={quality.value}, context={context.value}, language={language}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg) from e
        except ValueError as e:
            error_msg = f"文字起こし用プロンプトの形式が不正です: quality={quality.value}, context={context.value}, language={language}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"文字起こし用プロンプトの読み込み中に予期せぬエラーが発生しました: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    @classmethod
    def get_chunk_transcription_prompt(
        cls,
        chunk_index: int,
        total_chunks: int,
        language: str = "ja",
        quality: TranscriptionQuality = TranscriptionQuality.STANDARD,
        previous_context: Optional[str] = None
    ) -> str:
        """
        チャンク文字起こし用プロンプトを取得
        
        Args:
            chunk_index: チャンクのインデックス
            total_chunks: 全チャンク数
            language: 言語コード
            quality: 文字起こし品質
            previous_context: 前のチャンクのコンテキスト
            
        Returns:
            str: チャンク文字起こし用プロンプト
            
        Raises:
            FileNotFoundError: プロンプトファイルが見つからない場合
            ValueError: プロンプトの形式が不正な場合
        """
        try:
            # プロンプト名を構築 (prompt_loader.pyが抽出するプロンプト名に合わせる)
            prompt_name = "chunk_transcription"
            
            # プロンプトを読み込んでレンダリング
            return load_and_render_prompt_with_language(
                category="transcription",
                prompt_name=prompt_name,
                language=language,
                chunk_index=chunk_index,
                total_chunks=total_chunks,
                previous_context=previous_context or "",
                custom_instructions=""
            )
        except FileNotFoundError as e:
            error_msg = f"チャンク文字起こし用プロンプトファイルが見つかりません: language={language}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg) from e
        except ValueError as e:
            error_msg = f"チャンク文字起こし用プロンプトの形式が不正です: language={language}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"チャンク文字起こし用プロンプトの読み込み中に予期せぬエラーが発生しました: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    @classmethod
    def get_quality_levels(cls) -> Dict[str, str]:
        """
        利用可能な品質レベルを取得
        
        Returns:
            Dict: 品質レベルの説明
        """
        return {
            TranscriptionQuality.BASIC.value: "基本品質",
            TranscriptionQuality.STANDARD.value: "標準品質",
            TranscriptionQuality.HIGH.value: "高品質",
            TranscriptionQuality.PROFESSIONAL.value: "プロフェッショナル品質"
        }
    
    @classmethod
    def get_supported_languages(cls) -> Dict[str, str]:
        """
        サポートされている言語を取得
        
        Returns:
            Dict: 言語コードと言語名
        """
        return {
            "ja": "日本語",
            "en": "英語",
            "zh": "中国語",
            "ko": "韓国語",
            "fr": "フランス語",
            "de": "ドイツ語",
            "es": "スペイン語"
        }
    
    @classmethod
    def get_contexts(cls) -> Dict[str, str]:
        """
        利用可能なコンテキストを取得
        
        Returns:
            Dict: コンテキストの説明
        """
        return {
            TranscriptionContext.MEETING.value: "会議",
            TranscriptionContext.LECTURE.value: "講義",
            TranscriptionContext.INTERVIEW.value: "インタビュー",
            TranscriptionContext.PRESENTATION.value: "プレゼンテーション",
            TranscriptionContext.GENERAL.value: "一般"
        }