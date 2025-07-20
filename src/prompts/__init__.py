"""
STT議事録システム - プロンプト管理パッケージ

AI処理で使用するプロンプトテンプレートを管理
"""

from .transcription import TranscriptionPrompts
from .minutes_generation import MinutesGenerationPrompts
from .quality_check import QualityCheckPrompts
from .video_analysis import VideoAnalysisPrompts

__all__ = [
    "TranscriptionPrompts",
    "MinutesGenerationPrompts",
    "QualityCheckPrompts",
    "VideoAnalysisPrompts"
]