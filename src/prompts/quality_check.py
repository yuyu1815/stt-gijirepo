"""
STT議事録システム - 品質チェック用プロンプト

品質チェック処理で使用するプロンプトテンプレートを管理
"""

from typing import Dict
from enum import Enum
import logging
from ..utils.prompt_loader import load_and_render_prompt_with_language

logger = logging.getLogger(__name__)


class QualityCheckType(Enum):
    """品質チェックタイプ"""
    COMPREHENSIVE = "comprehensive"
    HALLUCINATION = "hallucination"
    GRAMMAR = "grammar"
    COHERENCE = "coherence"
    TERMINOLOGY = "terminology"
    READABILITY = "readability"


class QualityLevel(Enum):
    """品質レベル"""
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"
    PROFESSIONAL = "professional"


class QualityCheckPrompts:
    """品質チェック用プロンプトクラス"""
    
    @classmethod
    def get_quality_check_prompt(
        cls,
        check_type: QualityCheckType = QualityCheckType.COMPREHENSIVE,
        quality_level: QualityLevel = QualityLevel.STANDARD,
        language: str = "ja",
    ) -> str:
        """
        品質チェック用プロンプトを取得
        
        Args:
            check_type: チェックタイプ
            quality_level: 品質レベル
            language: 言語コード ("ja", "en")
        Returns:
            str: 品質チェック用プロンプト
            
        Raises:
            FileNotFoundError: プロンプトファイルが見つからない場合
            ValueError: プロンプトの形式が不正な場合
        """
        try:
            # プロンプト名を構築 (prompt_loader.pyが抽出するプロンプト名に合わせる)
            prompt_name = f"{check_type.value}_{quality_level.value}"
            

            # プロンプトを読み込んでレンダリング
            return load_and_render_prompt_with_language(
                category="quality_check",
                prompt_name=prompt_name,
                language=language,
            )
        except FileNotFoundError as e:
            error_msg = f"品質チェック用プロンプトファイルが見つかりません: check_type={check_type.value}, quality_level={quality_level.value}, language={language}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg) from e
        except ValueError as e:
            error_msg = f"品質チェック用プロンプトの形式が不正です: check_type={check_type.value}, quality_level={quality_level.value}, language={language}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"品質チェック用プロンプトの読み込み中に予期せぬエラーが発生しました: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    
    @classmethod
    def get_comparative_quality_prompt(
        cls,
        original_text: str,
        improved_text: str,
        language: str = "ja"
    ) -> str:
        """
        比較品質チェック用プロンプトを取得
        
        Args:
            original_text: 元のテキスト
            improved_text: 改善されたテキスト
            language: 言語コード
            
        Returns:
            str: 比較品質チェック用プロンプト
            
        Raises:
            FileNotFoundError: プロンプトファイルが見つからない場合
            ValueError: プロンプトの形式が不正な場合
        """
        try:
            # プロンプト名を構築 (prompt_loader.pyが抽出するプロンプト名に合わせる)
            prompt_name = "comparative_check"
            
            # プロンプトを読み込んでレンダリング
            return load_and_render_prompt_with_language(
                category="quality_check",
                prompt_name=prompt_name,
                language=language,
            )
        except FileNotFoundError as e:
            error_msg = f"比較品質チェック用プロンプトファイルが見つかりません: language={language}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg) from e
        except ValueError as e:
            error_msg = f"比較品質チェック用プロンプトの形式が不正です: language={language}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"比較品質チェック用プロンプトの読み込み中に予期せぬエラーが発生しました: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    @classmethod
    def get_check_types(cls) -> Dict[str, str]:
        """
        利用可能なチェックタイプを取得
        
        Returns:
            Dict: チェックタイプの説明
        """
        return {
            QualityCheckType.COMPREHENSIVE.value: "包括的品質チェック",
            QualityCheckType.HALLUCINATION.value: "ハルシネーションチェック",
            QualityCheckType.GRAMMAR.value: "文法チェック",
            QualityCheckType.COHERENCE.value: "一貫性チェック",
            QualityCheckType.TERMINOLOGY.value: "専門用語チェック",
            QualityCheckType.READABILITY.value: "読みやすさチェック"
        }
    
    @classmethod
    def get_quality_levels(cls) -> Dict[str, str]:
        """
        利用可能な品質レベルを取得
        
        Returns:
            Dict: 品質レベルの説明
        """
        return {
            QualityLevel.BASIC.value: "基本レベル",
            QualityLevel.STANDARD.value: "標準レベル",
            QualityLevel.STRICT.value: "厳格レベル",
            QualityLevel.PROFESSIONAL.value: "プロフェッショナルレベル"
        }