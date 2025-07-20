"""
STT議事録システム - 品質チェック用プロンプト

文字起こし結果の品質チェック処理で使用するプロンプトテンプレートを管理
"""

from typing import Dict, Any, Optional, List
from enum import Enum
import logging
from ..utils.prompt_loader import get_prompt_loader, load_and_render_prompt

logger = logging.getLogger(__name__)


class QualityCheckType(Enum):
    """品質チェックタイプ"""
    COMPREHENSIVE = "comprehensive"
    GRAMMAR = "grammar"
    COHERENCE = "coherence"
    TERMINOLOGY = "terminology"
    HALLUCINATION = "hallucination"
    READABILITY = "readability"


class QualityLevel(Enum):
    """品質レベル"""
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"
    PROFESSIONAL = "professional"


class QualityCheckPrompts:
    """品質チェック用プロンプトクラス"""
    
    # 包括的品質チェックプロンプト
    COMPREHENSIVE_PROMPTS = {
        "ja": {
            QualityLevel.BASIC: """
以下の文字起こしテキストの品質を基本レベルで評価してください。

評価項目:
1. 文法の正確性 (0-10点)
2. 文脈の一貫性 (0-10点)
3. 全体的な読みやすさ (0-10点)

以下のJSON形式で回答してください:
{{
    "grammar_score": 点数,
    "coherence_score": 点数,
    "readability_score": 点数,
    "overall_score": 平均点数,
    "issues": ["問題点1", "問題点2"],
    "suggestions": ["改善提案1", "改善提案2"]
}}

文字起こしテキスト:
""",
            QualityLevel.STANDARD: """
以下の文字起こしテキストの品質を標準レベルで評価してください。

評価項目:
1. 文法の正確性 (0-10点)
2. 文脈の一貫性 (0-10点)
3. 専門用語の適切性 (0-10点)
4. 全体的な読みやすさ (0-10点)
5. ハルシネーション（幻覚）の有無

以下のJSON形式で回答してください:
{{
    "grammar_score": 点数,
    "coherence_score": 点数,
    "terminology_score": 点数,
    "readability_score": 点数,
    "overall_score": 平均点数,
    "has_hallucination": true/false,
    "hallucination_examples": ["例1", "例2"],
    "issues": ["問題点1", "問題点2"],
    "suggestions": ["改善提案1", "改善提案2"]
}}

文字起こしテキスト:
""",
            QualityLevel.STRICT: """
以下の文字起こしテキストの品質を厳格レベルで評価してください。

詳細評価項目:
1. 文法の正確性 (0-10点) - 助詞、語尾、敬語の使い方
2. 文脈の一貫性 (0-10点) - 論理的な流れ、話題の連続性
3. 専門用語の適切性 (0-10点) - 業界用語、技術用語の正確性
4. 全体的な読みやすさ (0-10点) - 句読点、改行、構成
5. 情報の完全性 (0-10点) - 重要な情報の欠落がないか
6. ハルシネーション検出 - 実際に話されていない内容の混入

以下のJSON形式で回答してください:
{{
    "grammar_score": 点数,
    "coherence_score": 点数,
    "terminology_score": 点数,
    "readability_score": 点数,
    "completeness_score": 点数,
    "overall_score": 平均点数,
    "has_hallucination": true/false,
    "hallucination_examples": ["具体例1", "具体例2"],
    "grammar_issues": ["文法問題1", "文法問題2"],
    "coherence_issues": ["一貫性問題1", "一貫性問題2"],
    "terminology_issues": ["用語問題1", "用語問題2"],
    "missing_information": ["欠落情報1", "欠落情報2"],
    "suggestions": ["改善提案1", "改善提案2"]
}}

文字起こしテキスト:
""",
            QualityLevel.PROFESSIONAL: """
以下の文字起こしテキストの品質をプロフェッショナルレベルで評価してください。

プロフェッショナル評価項目:
1. 言語的正確性 (0-10点) - 文法、語彙、表現の適切性
2. 構造的一貫性 (0-10点) - 論理構造、情報の階層化
3. 専門性 (0-10点) - 専門用語、業界知識の正確性
4. 可読性 (0-10点) - 読みやすさ、理解しやすさ
5. 完全性 (0-10点) - 情報の網羅性、重要事項の記録
6. 信頼性 (0-10点) - ハルシネーション、事実誤認の有無
7. 実用性 (0-10点) - 実際の業務での使用可能性

詳細分析:
- 発話者の意図の正確な反映
- 文脈に応じた適切な表現選択
- 業界標準に準拠した用語使用
- 重要度に応じた情報の強調

以下のJSON形式で回答してください:
{{
    "linguistic_accuracy": 点数,
    "structural_coherence": 点数,
    "professional_terminology": 点数,
    "readability": 点数,
    "completeness": 点数,
    "reliability": 点数,
    "practicality": 点数,
    "overall_score": 平均点数,
    "quality_grade": "A/B/C/D/F",
    "has_hallucination": true/false,
    "hallucination_details": [
        {{
            "type": "追加情報/誤解釈/文脈違反",
            "content": "具体的な内容",
            "severity": "高/中/低"
        }}
    ],
    "detailed_issues": [
        {{
            "category": "文法/一貫性/専門性/可読性/完全性/信頼性/実用性",
            "issue": "具体的な問題",
            "location": "該当箇所",
            "severity": "高/中/低",
            "suggestion": "改善提案"
        }}
    ],
    "strengths": ["優れている点1", "優れている点2"],
    "improvement_priorities": ["最優先改善点1", "最優先改善点2"]
}}

文字起こしテキスト:
"""
        },
        "en": {
            QualityLevel.BASIC: """
Please evaluate the quality of the following transcription text at a basic level.

Evaluation criteria:
1. Grammar accuracy (0-10 points)
2. Contextual coherence (0-10 points)
3. Overall readability (0-10 points)

Please respond in the following JSON format:
{{
    "grammar_score": score,
    "coherence_score": score,
    "readability_score": score,
    "overall_score": average_score,
    "issues": ["issue1", "issue2"],
    "suggestions": ["suggestion1", "suggestion2"]
}}

Transcription text:
""",
            QualityLevel.STANDARD: """
Please evaluate the quality of the following transcription text at a standard level.

Evaluation criteria:
1. Grammar accuracy (0-10 points)
2. Contextual coherence (0-10 points)
3. Terminology appropriateness (0-10 points)
4. Overall readability (0-10 points)
5. Presence of hallucinations

Please respond in the following JSON format:
{{
    "grammar_score": score,
    "coherence_score": score,
    "terminology_score": score,
    "readability_score": score,
    "overall_score": average_score,
    "has_hallucination": true/false,
    "hallucination_examples": ["example1", "example2"],
    "issues": ["issue1", "issue2"],
    "suggestions": ["suggestion1", "suggestion2"]
}}

Transcription text:
""",
            QualityLevel.STRICT: """
Please evaluate the quality of the following transcription text at a strict level.

Detailed evaluation criteria:
1. Grammar accuracy (0-10 points) - Articles, tenses, sentence structure
2. Contextual coherence (0-10 points) - Logical flow, topic continuity
3. Terminology appropriateness (0-10 points) - Industry terms, technical accuracy
4. Overall readability (0-10 points) - Punctuation, formatting, structure
5. Information completeness (0-10 points) - No missing important information
6. Hallucination detection - Content not actually spoken

Please respond in the following JSON format:
{{
    "grammar_score": score,
    "coherence_score": score,
    "terminology_score": score,
    "readability_score": score,
    "completeness_score": score,
    "overall_score": average_score,
    "has_hallucination": true/false,
    "hallucination_examples": ["specific_example1", "specific_example2"],
    "grammar_issues": ["grammar_issue1", "grammar_issue2"],
    "coherence_issues": ["coherence_issue1", "coherence_issue2"],
    "terminology_issues": ["terminology_issue1", "terminology_issue2"],
    "missing_information": ["missing_info1", "missing_info2"],
    "suggestions": ["suggestion1", "suggestion2"]
}}

Transcription text:
""",
            QualityLevel.PROFESSIONAL: """
Please evaluate the quality of the following transcription text at a professional level.

Professional evaluation criteria:
1. Linguistic accuracy (0-10 points) - Grammar, vocabulary, expression appropriateness
2. Structural coherence (0-10 points) - Logical structure, information hierarchy
3. Professional terminology (0-10 points) - Technical terms, industry knowledge accuracy
4. Readability (0-10 points) - Ease of reading and understanding
5. Completeness (0-10 points) - Information comprehensiveness, important item recording
6. Reliability (0-10 points) - Absence of hallucinations and factual errors
7. Practicality (0-10 points) - Usability in actual business contexts

Detailed analysis:
- Accurate reflection of speaker's intent
- Appropriate expression selection based on context
- Industry-standard terminology usage
- Information emphasis based on importance

Please respond in the following JSON format:
{{
    "linguistic_accuracy": score,
    "structural_coherence": score,
    "professional_terminology": score,
    "readability": score,
    "completeness": score,
    "reliability": score,
    "practicality": score,
    "overall_score": average_score,
    "quality_grade": "A/B/C/D/F",
    "has_hallucination": true/false,
    "hallucination_details": [
        {{
            "type": "added_info/misinterpretation/context_violation",
            "content": "specific_content",
            "severity": "high/medium/low"
        }}
    ],
    "detailed_issues": [
        {{
            "category": "grammar/coherence/terminology/readability/completeness/reliability/practicality",
            "issue": "specific_issue",
            "location": "relevant_section",
            "severity": "high/medium/low",
            "suggestion": "improvement_suggestion"
        }}
    ],
    "strengths": ["strength1", "strength2"],
    "improvement_priorities": ["top_priority1", "top_priority2"]
}}

Transcription text:
"""
        }
    }
    
    # 特定品質チェック用プロンプト
    SPECIFIC_CHECK_PROMPTS = {
        QualityCheckType.GRAMMAR: {
            "ja": """
以下の文字起こしテキストの文法的正確性を詳細に評価してください。

チェック項目:
1. 助詞の使い方（は、が、を、に、で、から、まで等）
2. 動詞の活用と時制の一貫性
3. 敬語の適切な使用
4. 句読点の配置
5. 文の構造と完全性

JSON形式で回答:
{{
    "grammar_score": 点数(0-10),
    "particle_errors": ["助詞エラー1", "助詞エラー2"],
    "verb_errors": ["動詞エラー1", "動詞エラー2"],
    "honorific_errors": ["敬語エラー1", "敬語エラー2"],
    "punctuation_errors": ["句読点エラー1", "句読点エラー2"],
    "structure_errors": ["構造エラー1", "構造エラー2"],
    "corrections": [
        {{
            "original": "元の文",
            "corrected": "修正後の文",
            "reason": "修正理由"
        }}
    ]
}}

文字起こしテキスト:
""",
            "en": """
Please evaluate the grammatical accuracy of the following transcription text in detail.

Check items:
1. Article usage (a, an, the)
2. Verb conjugation and tense consistency
3. Subject-verb agreement
4. Punctuation placement
5. Sentence structure and completeness

Respond in JSON format:
{{
    "grammar_score": score(0-10),
    "article_errors": ["article_error1", "article_error2"],
    "verb_errors": ["verb_error1", "verb_error2"],
    "agreement_errors": ["agreement_error1", "agreement_error2"],
    "punctuation_errors": ["punctuation_error1", "punctuation_error2"],
    "structure_errors": ["structure_error1", "structure_error2"],
    "corrections": [
        {{
            "original": "original_sentence",
            "corrected": "corrected_sentence",
            "reason": "correction_reason"
        }}
    ]
}}

Transcription text:
"""
        },
        QualityCheckType.HALLUCINATION: {
            "ja": """
以下の文字起こしテキストにハルシネーション（実際には話されていない内容の混入）がないかチェックしてください。

チェック観点:
1. 不自然に詳細すぎる情報
2. 文脈に合わない突然の話題転換
3. 一般的すぎる内容や定型文の混入
4. 論理的に矛盾する内容
5. 音声では判断できない視覚的情報

JSON形式で回答:
{{
    "has_hallucination": true/false,
    "hallucination_probability": 確率(0-100),
    "suspicious_sections": [
        {{
            "content": "疑わしい内容",
            "reason": "疑わしい理由",
            "confidence": "確信度(高/中/低)"
        }}
    ],
    "reliability_score": 信頼性スコア(0-10),
    "recommendations": ["推奨事項1", "推奨事項2"]
}}

文字起こしテキスト:
""",
            "en": """
Please check the following transcription text for hallucinations (inclusion of content not actually spoken).

Check perspectives:
1. Unnaturally detailed information
2. Sudden topic changes that don't fit the context
3. Inclusion of overly general content or boilerplate text
4. Logically contradictory content
5. Visual information that cannot be determined from audio

Respond in JSON format:
{{
    "has_hallucination": true/false,
    "hallucination_probability": probability(0-100),
    "suspicious_sections": [
        {{
            "content": "suspicious_content",
            "reason": "reason_for_suspicion",
            "confidence": "confidence_level(high/medium/low)"
        }}
    ],
    "reliability_score": reliability_score(0-10),
    "recommendations": ["recommendation1", "recommendation2"]
}}

Transcription text:
"""
        },
        QualityCheckType.COHERENCE: {
            "ja": """
以下の文字起こしテキストの文脈的一貫性を評価してください。

評価項目:
1. 話題の論理的な流れ
2. 前後の文脈の整合性
3. 話者の発言の一貫性
4. 時系列の整合性
5. 情報の関連性

JSON形式で回答:
{{
    "coherence_score": 点数(0-10),
    "logical_flow_score": 論理的流れ(0-10),
    "context_consistency_score": 文脈一貫性(0-10),
    "speaker_consistency_score": 話者一貫性(0-10),
    "temporal_consistency_score": 時系列一貫性(0-10),
    "information_relevance_score": 情報関連性(0-10),
    "inconsistencies": [
        {{
            "type": "不整合のタイプ",
            "description": "具体的な説明",
            "location": "該当箇所",
            "severity": "重要度(高/中/低)"
        }}
    ],
    "improvement_suggestions": ["改善提案1", "改善提案2"]
}}

文字起こしテキスト:
""",
            "en": """
Please evaluate the contextual coherence of the following transcription text.

Evaluation items:
1. Logical flow of topics
2. Consistency of context before and after
3. Consistency of speaker statements
4. Temporal consistency
5. Information relevance

Respond in JSON format:
{{
    "coherence_score": score(0-10),
    "logical_flow_score": logical_flow(0-10),
    "context_consistency_score": context_consistency(0-10),
    "speaker_consistency_score": speaker_consistency(0-10),
    "temporal_consistency_score": temporal_consistency(0-10),
    "information_relevance_score": information_relevance(0-10),
    "inconsistencies": [
        {{
            "type": "inconsistency_type",
            "description": "specific_description",
            "location": "relevant_section",
            "severity": "importance(high/medium/low)"
        }}
    ],
    "improvement_suggestions": ["suggestion1", "suggestion2"]
}}

Transcription text:
"""
        }
    }
    
    @classmethod
    def get_quality_check_prompt(
        cls,
        check_type: QualityCheckType = QualityCheckType.COMPREHENSIVE,
        quality_level: QualityLevel = QualityLevel.STANDARD,
        language: str = "ja",
        custom_criteria: Optional[List[str]] = None
    ) -> str:
        """
        品質チェック用プロンプトを取得
        
        Args:
            check_type: チェックタイプ
            quality_level: 品質レベル
            language: 言語コード ("ja", "en")
            custom_criteria: カスタム評価基準
            
        Returns:
            str: 品質チェック用プロンプト
        """
        try:
            # チェックタイプに応じてプロンプトファイルを選択
            prompt_mapping = {
                QualityCheckType.COMPREHENSIVE: "comprehensive_check",
                QualityCheckType.HALLUCINATION: "hallucination_check",
                QualityCheckType.GRAMMAR: "comprehensive_check",
                QualityCheckType.COHERENCE: "comprehensive_check",
                QualityCheckType.TERMINOLOGY: "comprehensive_check",
                QualityCheckType.READABILITY: "comprehensive_check"
            }
            
            prompt_name = prompt_mapping.get(check_type, "comprehensive_check")
            
            # カスタム評価基準を準備
            custom_instructions = ""
            if custom_criteria:
                criteria_text = "\n".join([f"- {criteria}" for criteria in custom_criteria])
                custom_instructions = f"追加評価基準:\n{criteria_text}"
            
            # Markdownプロンプトを読み込んでレンダリング
            return load_and_render_prompt(
                category="quality_check",
                prompt_name=prompt_name,
                content="",  # 実際のコンテンツは後で置換される
                content_type="transcription",
                language=language,
                quality_criteria=quality_level.value,
                custom_instructions=custom_instructions
            )
            
        except Exception as e:
            logger.warning(f"Failed to load Markdown prompt, falling back to legacy: {e}")
            # フォールバック: 既存のハードコードプロンプトを使用
            return cls._get_legacy_quality_check_prompt(check_type, quality_level, language, custom_criteria)
    
    @classmethod
    def _get_legacy_quality_check_prompt(
        cls,
        check_type: QualityCheckType,
        quality_level: QualityLevel,
        language: str,
        custom_criteria: Optional[List[str]]
    ) -> str:
        """
        レガシー品質チェックプロンプトを取得（フォールバック用）
        
        Args:
            check_type: チェックタイプ
            quality_level: 品質レベル
            language: 言語コード
            custom_criteria: カスタム評価基準
            
        Returns:
            str: レガシー品質チェックプロンプト
        """
        if check_type == QualityCheckType.COMPREHENSIVE:
            base_prompt = cls.COMPREHENSIVE_PROMPTS.get(language, cls.COMPREHENSIVE_PROMPTS["ja"]).get(
                quality_level, cls.COMPREHENSIVE_PROMPTS[language][QualityLevel.STANDARD]
            )
        else:
            base_prompt = cls.SPECIFIC_CHECK_PROMPTS.get(check_type, {}).get(
                language, cls.SPECIFIC_CHECK_PROMPTS[check_type]["ja"]
            )
        
        # カスタム評価基準を追加
        if custom_criteria:
            criteria_text = "\n".join([f"- {criteria}" for criteria in custom_criteria])
            custom_section = f"\n\n追加評価基準:\n{criteria_text}"
            base_prompt += custom_section
        
        return base_prompt
    
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
        """
        prompts = {
            "ja": f"""
以下の2つのテキストを比較して、品質の改善度を評価してください。

元のテキスト:
{original_text}

改善されたテキスト:
{improved_text}

比較評価項目:
1. 文法の改善度
2. 読みやすさの改善度
3. 情報の正確性の改善度
4. 全体的な品質向上度

JSON形式で回答:
{{
    "grammar_improvement": 改善度(0-10),
    "readability_improvement": 改善度(0-10),
    "accuracy_improvement": 改善度(0-10),
    "overall_improvement": 全体改善度(0-10),
    "improvements_made": ["改善点1", "改善点2"],
    "remaining_issues": ["残存問題1", "残存問題2"],
    "recommendation": "総合的な推奨事項"
}}
""",
            "en": f"""
Please compare the following two texts and evaluate the degree of quality improvement.

Original text:
{original_text}

Improved text:
{improved_text}

Comparative evaluation items:
1. Grammar improvement
2. Readability improvement
3. Information accuracy improvement
4. Overall quality improvement

Respond in JSON format:
{{
    "grammar_improvement": improvement_degree(0-10),
    "readability_improvement": improvement_degree(0-10),
    "accuracy_improvement": improvement_degree(0-10),
    "overall_improvement": overall_improvement(0-10),
    "improvements_made": ["improvement1", "improvement2"],
    "remaining_issues": ["remaining_issue1", "remaining_issue2"],
    "recommendation": "comprehensive_recommendation"
}}
"""
        }
        
        return prompts.get(language, prompts["ja"])
    
    @classmethod
    def get_check_types(cls) -> Dict[str, str]:
        """
        利用可能なチェックタイプを取得
        
        Returns:
            Dict: チェックタイプの説明
        """
        return {
            QualityCheckType.COMPREHENSIVE.value: "包括的品質チェック",
            QualityCheckType.GRAMMAR.value: "文法チェック",
            QualityCheckType.COHERENCE.value: "一貫性チェック",
            QualityCheckType.TERMINOLOGY.value: "専門用語チェック",
            QualityCheckType.HALLUCINATION.value: "ハルシネーション検出",
            QualityCheckType.READABILITY.value: "可読性チェック"
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