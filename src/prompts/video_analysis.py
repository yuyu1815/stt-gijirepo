"""
STT議事録システム - 動画解析用プロンプト

動画解析処理で使用するプロンプトテンプレートを管理
"""

from typing import Dict, Optional, List
from enum import Enum
import logging

from src.utils.prompt_loader import load_and_render_prompt_with_language

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
            
        Raises:
            FileNotFoundError: プロンプトファイルが見つからない場合
            ValueError: プロンプトの形式が不正な場合
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
            return load_and_render_prompt_with_language(
                category="video_analysis",
                prompt_name=prompt_name,
                language=language,
            )
        except FileNotFoundError as e:
            error_msg = f"動画解析用プロンプトファイルが見つかりません: analysis_type={analysis_type.value}, detail_level={detail_level.value}, language={language}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg) from e
        except ValueError as e:
            error_msg = f"動画解析用プロンプトの形式が不正です: analysis_type={analysis_type.value}, detail_level={detail_level.value}, language={language}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"動画解析用プロンプトの読み込み中に予期せぬエラーが発生しました: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    
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
            
        Raises:
            FileNotFoundError: プロンプトファイルが見つからない場合
            ValueError: プロンプトの形式が不正な場合
        """
        try:
            # プロンプト名を構築 (prompt_loader.pyが抽出するプロンプト名に合わせる)
            if include_recommendations:
                prompt_name = "comprehensive_analysis_with_recommendations"
            else:
                prompt_name = "comprehensive_analysis"
            
            # プロンプトを読み込んでレンダリング
            return load_and_render_prompt_with_language(
                category="video_analysis",
                prompt_name=prompt_name,
                language=language,
                video_info=""  # 実際の動画情報は後で置換される
            )
        except FileNotFoundError as e:
            error_msg = f"包括的動画解析用プロンプトファイルが見つかりません: language={language}, include_recommendations={include_recommendations}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg) from e
        except ValueError as e:
            error_msg = f"包括的動画解析用プロンプトの形式が不正です: language={language}, include_recommendations={include_recommendations}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"包括的動画解析用プロンプトの読み込み中に予期せぬエラーが発生しました: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
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