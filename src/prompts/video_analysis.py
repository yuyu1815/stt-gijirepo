"""
STT議事録システム - 動画解析用プロンプト

動画解析処理で使用するプロンプトテンプレートを管理
"""

from typing import Dict, Any, Optional, List
from enum import Enum
import logging
from ..utils.prompt_loader import get_prompt_loader, load_and_render_prompt

logger = logging.getLogger(__name__)


class VideoAnalysisType(Enum):
    """動画解析タイプ"""
    BRIGHTNESS = "brightness"
    CONTENT = "content"
    SCENE = "scene"
    QUALITY = "quality"
    PARTICIPANTS = "participants"
    ENVIRONMENT = "environment"


class AnalysisDetail(Enum):
    """解析詳細レベル"""
    BASIC = "basic"
    STANDARD = "standard"
    DETAILED = "detailed"
    COMPREHENSIVE = "comprehensive"


class VideoAnalysisPrompts:
    """動画解析用プロンプトクラス"""
    
    # レガシープロンプトは削除済み - 新しいMarkdownベースのシステムを使用
    
    @classmethod
    def get_video_analysis_prompt(
        cls,
        analysis_type: VideoAnalysisType = VideoAnalysisType.BRIGHTNESS,
        detail_level: AnalysisDetail = AnalysisDetail.STANDARD,
        language: str = "ja",
        custom_focus: Optional[List[str]] = None
    ) -> str:
        """
        動画解析用プロンプトを取得
        
        Args:
            analysis_type: 解析タイプ
            detail_level: 詳細レベル
            language: 言語コード ("ja", "en")
            custom_focus: カスタム焦点項目
            
        Returns:
            str: 動画解析用プロンプト
        """
        try:
            # 解析タイプに応じてプロンプトファイルを選択
            prompt_mapping = {
                VideoAnalysisType.BRIGHTNESS: "brightness_analysis",
                VideoAnalysisType.CONTENT: "content_analysis",
                VideoAnalysisType.SCENE: "scene_analysis",
                VideoAnalysisType.QUALITY: "comprehensive_analysis",
                VideoAnalysisType.PARTICIPANTS: "participants_analysis",
                VideoAnalysisType.ENVIRONMENT: "environment_analysis"
            }
            
            prompt_name = prompt_mapping.get(analysis_type, "brightness_analysis")
            
            # 明度解析の場合は詳細レベルを考慮
            if analysis_type == VideoAnalysisType.BRIGHTNESS:
                # 詳細レベルに応じてプロンプトを選択（将来的な拡張用）
                # 現在は全て brightness_analysis を使用
                prompt_name = "brightness_analysis"
            
            # カスタム焦点項目を準備
            custom_instructions = ""
            if custom_focus:
                focus_text = "\n".join([f"- {focus}" for focus in custom_focus])
                custom_instructions = f"追加焦点項目:\n{focus_text}"
            
            # Markdownプロンプトを読み込んでレンダリング
            return load_and_render_prompt(
                category="video_analysis",
                prompt_name=prompt_name,
                video_info="",  # 実際の動画情報は後で置換される
                brightness_data="",  # 実際の明度データは後で置換される
                analysis_purpose=analysis_type.value,
                custom_instructions=custom_instructions
            )
            
        except Exception as e:
            logger.warning(f"Failed to load Markdown prompt, falling back to legacy: {e}")
            # フォールバック: 既存のハードコードプロンプトを使用
            return cls._get_legacy_video_analysis_prompt(analysis_type, detail_level, language, custom_focus)
    
    @classmethod
    def _get_legacy_video_analysis_prompt(
        cls,
        analysis_type: VideoAnalysisType,
        detail_level: AnalysisDetail,
        language: str,
        custom_focus: Optional[List[str]]
    ) -> str:
        """
        レガシー動画解析プロンプトを取得（フォールバック用）
        
        Args:
            analysis_type: 解析タイプ
            detail_level: 詳細レベル
            language: 言語コード
            custom_focus: カスタム焦点項目
            
        Returns:
            str: 基本的なフォールバックプロンプト
        """
        # 基本的なフォールバックプロンプト
        if language == "ja":
            base_prompt = f"""
この動画の{analysis_type.value}を分析してください。

分析項目:
1. 動画の基本的な特徴
2. 音声品質の評価
3. 視覚的要素の重要性
4. 文字起こし処理への影響

分析結果を詳細に記述してください。
"""
        else:
            base_prompt = f"""
Please analyze the {analysis_type.value} of this video.

Analysis items:
1. Basic characteristics of the video
2. Audio quality evaluation
3. Importance of visual elements
4. Impact on transcription processing

Please provide detailed analysis results.
"""
        
        # カスタム焦点項目を追加
        if custom_focus:
            focus_text = "\n".join([f"- {focus}" for focus in custom_focus])
            if language == "ja":
                custom_section = f"\n\n追加焦点項目:\n{focus_text}"
            else:
                custom_section = f"\n\nAdditional focus items:\n{focus_text}"
            base_prompt += custom_section
        
        return base_prompt
    
    @classmethod
    def get_comprehensive_analysis_prompt(
        cls,
        language: str = "ja",
        include_recommendations: bool = True
    ) -> str:
        """
        包括的動画解析用プロンプトを取得
        
        Args:
            language: 言語コード
            include_recommendations: 推奨事項を含めるか
            
        Returns:
            str: 包括的動画解析用プロンプト
        """
        # Build conditional parts outside f-string to avoid backslash issues
        comma_if_rec = "," if include_recommendations else ""
        
        if include_recommendations:
            proc_rec_start_ja = '"processing_recommendations": {'
            proc_rec_start_en = '"processing_recommendations": {'
            opt_settings_ja = '"optimal_settings": "推奨設定",'
            opt_settings_en = '"optimal_settings": "recommended_settings",'
            res_alloc_ja = '"resource_allocation": "リソース配分",'
            res_alloc_en = '"resource_allocation": "resource_allocation",'
            qual_exp_ja = '"quality_expectations": "品質期待値"'
            qual_exp_en = '"quality_expectations": "quality_expectations"'
            proc_rec_end = '}'
        else:
            proc_rec_start_ja = proc_rec_start_en = ""
            opt_settings_ja = opt_settings_en = ""
            res_alloc_ja = res_alloc_en = ""
            qual_exp_ja = qual_exp_en = ""
            proc_rec_end = ""
        
        prompts = {
            "ja": f"""
この動画を包括的に分析してください。

包括的分析項目:
1. 明度・照明環境の詳細分析
2. コンテンツタイプと構造の分析
3. 参加者と話者の分析
4. 音響環境と品質の評価
5. シーン構成と変化の分析
6. 技術的品質の評価
7. 文字起こし処理への影響評価

以下のJSON形式で回答してください:
{{
    "brightness_analysis": {{
        "overall_level": "bright/normal/dark",
        "variation": "low/medium/high",
        "audio_only_suitable": true/false
    }},
    "content_analysis": {{
        "type": "meeting/presentation/lecture/interview/other",
        "structure": "formal/informal/mixed",
        "participants": 数値
    }},
    "audio_analysis": {{
        "quality": "excellent/good/fair/poor",
        "clarity": "high/medium/low",
        "background_noise": "minimal/moderate/significant"
    }},
    "scene_analysis": {{
        "major_changes": 数値,
        "complexity": "simple/moderate/complex"
    }},
    "technical_quality": {{
        "resolution": "推定解像度",
        "compression": "high/medium/low"
    }},
    "transcription_assessment": {{
        "difficulty": "easy/moderate/difficult",
        "recommended_approach": "video_required/video_preferred/audio_sufficient",
        "expected_accuracy": "high/medium/low"
    }}{comma_if_rec}
    {proc_rec_start_ja}
        {opt_settings_ja}
        {res_alloc_ja}
        {qual_exp_ja}
    {proc_rec_end}
}}
""",
            "en": f"""
Please analyze this video comprehensively.

Comprehensive analysis items:
1. Detailed brightness and lighting environment analysis
2. Content type and structure analysis
3. Participant and speaker analysis
4. Acoustic environment and quality evaluation
5. Scene composition and change analysis
6. Technical quality evaluation
7. Impact assessment on transcription processing

Please respond in the following JSON format:
{{
    "brightness_analysis": {{
        "overall_level": "bright/normal/dark",
        "variation": "low/medium/high",
        "audio_only_suitable": true/false
    }},
    "content_analysis": {{
        "type": "meeting/presentation/lecture/interview/other",
        "structure": "formal/informal/mixed",
        "participants": number
    }},
    "audio_analysis": {{
        "quality": "excellent/good/fair/poor",
        "clarity": "high/medium/low",
        "background_noise": "minimal/moderate/significant"
    }},
    "scene_analysis": {{
        "major_changes": number,
        "complexity": "simple/moderate/complex"
    }},
    "technical_quality": {{
        "resolution": "estimated_resolution",
        "compression": "high/medium/low"
    }},
    "transcription_assessment": {{
        "difficulty": "easy/moderate/difficult",
        "recommended_approach": "video_required/video_preferred/audio_sufficient",
        "expected_accuracy": "high/medium/low"
    }}{comma_if_rec}
    {proc_rec_start_en}
        {opt_settings_en}
        {res_alloc_en}
        {qual_exp_en}
    {proc_rec_end}
}}
"""
        }
        
        return prompts.get(language, prompts["ja"])
    
    @classmethod
    def get_analysis_types(cls) -> Dict[str, str]:
        """
        利用可能な解析タイプを取得
        
        Returns:
            Dict: 解析タイプの説明
        """
        return {
            VideoAnalysisType.BRIGHTNESS.value: "明度解析",
            VideoAnalysisType.CONTENT.value: "コンテンツ解析",
            VideoAnalysisType.SCENE.value: "シーン解析",
            VideoAnalysisType.QUALITY.value: "品質解析",
            VideoAnalysisType.PARTICIPANTS.value: "参加者解析",
            VideoAnalysisType.ENVIRONMENT.value: "環境解析"
        }
    
    @classmethod
    def get_detail_levels(cls) -> Dict[str, str]:
        """
        利用可能な詳細レベルを取得
        
        Returns:
            Dict: 詳細レベルの説明
        """
        return {
            AnalysisDetail.BASIC.value: "基本レベル",
            AnalysisDetail.STANDARD.value: "標準レベル",
            AnalysisDetail.DETAILED.value: "詳細レベル",
            AnalysisDetail.COMPREHENSIVE.value: "包括的レベル"
        }