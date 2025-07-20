"""
STT議事録システム - 文字起こし用プロンプト

文字起こし処理で使用するプロンプトテンプレートを管理
"""

from typing import Dict, Any, Optional
from enum import Enum
import logging
from ..utils.prompt_loader import get_prompt_loader, load_and_render_prompt

logger = logging.getLogger(__name__)


class TranscriptionQuality(Enum):
    """文字起こし品質レベル"""
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
    
    # 基本プロンプトテンプレート
    BASE_PROMPTS = {
        "ja": {
            TranscriptionQuality.BASIC: """
以下の音声ファイルを日本語で文字起こししてください。

基本要求事項:
1. 話者の発言を正確に文字に起こす
2. 明らかな言い間違いは修正する
3. 聞き取れない部分は[不明瞭]と記載
4. 句読点を適切に配置

音声ファイル:
""",
            TranscriptionQuality.STANDARD: """
以下の音声ファイルを高品質で日本語文字起こししてください。

要求事項:
1. 話者の発言を正確に文字に起こす
2. 「えー」「あのー」などのフィラーは適度に除去
3. 句読点を適切に配置
4. 専門用語や固有名詞は文脈から推測して正確に記述
5. 聞き取れない部分は[不明瞭]と記載
6. 話者が複数いる場合は可能な限り区別する

音声ファイル:
""",
            TranscriptionQuality.HIGH: """
以下の音声ファイルを最高品質で日本語文字起こししてください。

詳細要求事項:
1. 話者の発言を完全に正確に文字に起こす
2. フィラー（「えー」「あのー」等）は文脈に応じて適切に処理
3. 句読点、改行を読みやすく配置
4. 専門用語、固有名詞、数値を正確に記述
5. 聞き取れない部分は[不明瞭: 推定○○秒]として時間も記載
6. 話者が複数いる場合は明確に区別し、可能であれば話者を特定
7. 重要な非言語情報（笑い声、拍手等）も[笑い]として記載
8. 文章の流れを整理し、読みやすい形に構成

音声ファイル:
""",
            TranscriptionQuality.PROFESSIONAL: """
以下の音声ファイルをプロフェッショナル品質で日本語文字起こししてください。

プロフェッショナル要求事項:
1. 完全な正確性: 話者の発言を一字一句正確に文字起こし
2. 高度な言語処理: 文脈を理解し、適切な漢字変換と表記統一
3. 構造化: 発言内容を論理的に整理し、段落分けを適切に実施
4. 話者識別: 複数話者を明確に区別し、可能な限り個人を特定
5. メタ情報: 発言の感情的ニュアンス、強調、間合いも記録
6. 専門性: 業界用語、技術用語を正確に記述
7. 品質保証: 聞き取り困難箇所は複数の解釈候補を提示
8. 時系列管理: 重要な発言には概算時刻を併記

出力形式:
- 話者別に明確に区分
- 重要度に応じた見出し付け
- 専門用語の注釈付き

音声ファイル:
"""
        },
        "en": {
            TranscriptionQuality.BASIC: """
Please transcribe the following audio file in English.

Basic requirements:
1. Accurately transcribe speaker's words
2. Correct obvious mistakes
3. Mark unclear parts as [unclear]
4. Use appropriate punctuation

Audio file:
""",
            TranscriptionQuality.STANDARD: """
Please provide high-quality English transcription of the following audio file.

Requirements:
1. Accurately transcribe speaker's words
2. Remove excessive filler words (um, uh, etc.) appropriately
3. Use proper punctuation and formatting
4. Accurately transcribe technical terms and proper nouns based on context
5. Mark unclear parts as [unclear]
6. Distinguish multiple speakers when possible

Audio file:
""",
            TranscriptionQuality.HIGH: """
Please provide the highest quality English transcription of the following audio file.

Detailed requirements:
1. Complete accuracy in transcribing speaker's words
2. Contextually appropriate handling of filler words
3. Proper punctuation and paragraph breaks for readability
4. Accurate transcription of technical terms, proper nouns, and numbers
5. Mark unclear parts as [unclear: estimated X seconds]
6. Clearly distinguish multiple speakers and identify them when possible
7. Include important non-verbal information (laughter, applause) as [laughter]
8. Structure content for optimal readability

Audio file:
""",
            TranscriptionQuality.PROFESSIONAL: """
Please provide professional-grade English transcription of the following audio file.

Professional requirements:
1. Complete accuracy: Word-for-word transcription
2. Advanced language processing: Context-aware formatting and consistency
3. Structured output: Logical organization with appropriate paragraphing
4. Speaker identification: Clear distinction and identification when possible
5. Meta-information: Emotional nuance, emphasis, and timing
6. Technical expertise: Accurate industry and technical terminology
7. Quality assurance: Multiple interpretation candidates for difficult sections
8. Temporal management: Approximate timestamps for important statements

Output format:
- Clear speaker separation
- Importance-based headings
- Technical term annotations

Audio file:
"""
        }
    }
    
    # コンテキスト別プロンプト拡張
    CONTEXT_EXTENSIONS = {
        TranscriptionContext.MEETING: {
            "ja": """

会議コンテキスト追加要求:
- 議題、決定事項、アクションアイテムを明確に識別
- 参加者の役職や立場を推測して記録
- 会議の流れ（開始、議論、決定、終了）を構造化
- 重要な数値、日程、責任者を強調表示
""",
            "en": """

Meeting context additional requirements:
- Clearly identify agenda items, decisions, and action items
- Infer and record participants' roles and positions
- Structure meeting flow (opening, discussion, decisions, closing)
- Highlight important numbers, dates, and responsible parties
"""
        },
        TranscriptionContext.LECTURE: {
            "ja": """

講義コンテキスト追加要求:
- 講義の主要トピックと学習目標を識別
- 重要な概念、定義、例を明確に区別
- 質疑応答セクションを別途整理
- 参考文献や推奨資料の言及を記録
""",
            "en": """

Lecture context additional requirements:
- Identify main topics and learning objectives
- Clearly distinguish key concepts, definitions, and examples
- Organize Q&A sections separately
- Record mentions of references and recommended materials
"""
        },
        TranscriptionContext.INTERVIEW: {
            "ja": """

インタビューコンテキスト追加要求:
- 質問者と回答者を明確に区別
- 重要な回答や洞察を強調
- 感情的なニュアンスや反応を記録
- フォローアップ質問の流れを整理
""",
            "en": """

Interview context additional requirements:
- Clearly distinguish interviewer and interviewee
- Highlight important answers and insights
- Record emotional nuances and reactions
- Organize follow-up question flows
"""
        },
        TranscriptionContext.PRESENTATION: {
            "ja": """

プレゼンテーションコンテキスト追加要求:
- プレゼンテーションの構造（導入、本論、結論）を識別
- スライドや資料への言及を記録
- 聴衆からの質問や反応を区別
- 重要なポイントや結論を強調
""",
            "en": """

Presentation context additional requirements:
- Identify presentation structure (introduction, main content, conclusion)
- Record references to slides or materials
- Distinguish audience questions and reactions
- Emphasize key points and conclusions
"""
        },
        TranscriptionContext.GENERAL: {
            "ja": """

一般コンテキスト追加要求:
- 話題の変化を適切に区切る
- 重要な情報や結論を識別
- 自然な会話の流れを保持
""",
            "en": """

General context additional requirements:
- Appropriately segment topic changes
- Identify important information and conclusions
- Maintain natural conversation flow
"""
        }
    }
    
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
            quality: 品質レベル
            context: コンテキスト
            custom_instructions: カスタム指示
            
        Returns:
            str: 文字起こし用プロンプト
        """
        try:
            # 品質レベルに応じてプロンプトファイルを選択
            prompt_mapping = {
                TranscriptionQuality.BASIC: "basic_transcription",
                TranscriptionQuality.STANDARD: "basic_transcription",
                TranscriptionQuality.HIGH: "high_quality_transcription",
                TranscriptionQuality.PROFESSIONAL: "high_quality_transcription"
            }
            
            prompt_name = prompt_mapping.get(quality, "basic_transcription")
            
            # Markdownプロンプトを読み込んでレンダリング
            return load_and_render_prompt(
                category="transcription",
                prompt_name=prompt_name,
                language=language,
                context=context.value,
                custom_instructions=custom_instructions or ""
            )
            
        except Exception as e:
            logger.warning(f"Failed to load Markdown prompt, falling back to legacy: {e}")
            # フォールバック: 既存のハードコードプロンプトを使用
            return cls._get_legacy_transcription_prompt(language, quality, context, custom_instructions)
    
    @classmethod
    def _get_legacy_transcription_prompt(
        cls,
        language: str,
        quality: TranscriptionQuality,
        context: TranscriptionContext,
        custom_instructions: Optional[str]
    ) -> str:
        """
        レガシープロンプトを取得（フォールバック用）
        
        Args:
            language: 言語コード
            quality: 品質レベル
            context: コンテキスト
            custom_instructions: カスタム指示
            
        Returns:
            str: レガシープロンプト
        """
        # 基本プロンプトを取得
        base_prompt = cls.BASE_PROMPTS.get(language, cls.BASE_PROMPTS["ja"]).get(
            quality, cls.BASE_PROMPTS[language][TranscriptionQuality.STANDARD]
        )
        
        # コンテキスト拡張を追加
        context_extension = cls.CONTEXT_EXTENSIONS.get(context, {}).get(language, "")
        
        # カスタム指示を追加
        custom_section = ""
        if custom_instructions:
            custom_section = f"\n\n追加指示:\n{custom_instructions}"
        
        return base_prompt + context_extension + custom_section
    
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
        分割音声用の文字起こしプロンプトを取得
        
        Args:
            chunk_index: チャンクインデックス（0から開始）
            total_chunks: 総チャンク数
            language: 言語コード
            quality: 品質レベル
            previous_context: 前のチャンクの文脈情報
            
        Returns:
            str: 分割音声用プロンプト
        """
        try:
            # チャンク用のMarkdownプロンプトを使用
            return load_and_render_prompt(
                category="transcription",
                prompt_name="chunk_transcription",
                chunk_index=chunk_index + 1,  # 1から開始に変換
                total_chunks=total_chunks,
                language=language,
                previous_context=previous_context or "",
                custom_instructions=""
            )
            
        except Exception as e:
            logger.warning(f"Failed to load chunk Markdown prompt, falling back to legacy: {e}")
            # フォールバック: レガシー方式
            return cls._get_legacy_chunk_transcription_prompt(
                chunk_index, total_chunks, language, quality
            )
    
    @classmethod
    def _get_legacy_chunk_transcription_prompt(
        cls,
        chunk_index: int,
        total_chunks: int,
        language: str,
        quality: TranscriptionQuality
    ) -> str:
        """
        レガシーチャンクプロンプトを取得（フォールバック用）
        
        Args:
            chunk_index: チャンクインデックス
            total_chunks: 総チャンク数
            language: 言語コード
            quality: 品質レベル
            
        Returns:
            str: レガシーチャンクプロンプト
        """
        base_prompt = cls._get_legacy_transcription_prompt(
            language, quality, TranscriptionContext.GENERAL, None
        )
        
        chunk_info = {
            "ja": f"""

【分割音声情報】
- これは全{total_chunks}個に分割された音声の第{chunk_index + 1}部分です
- 前後の文脈を考慮して自然な文章になるよう調整してください
- 文の途中で切れている場合は、可能な限り完全な文として補完してください
""",
            "en": f"""

【Split Audio Information】
- This is part {chunk_index + 1} of {total_chunks} split audio segments
- Please adjust for natural sentences considering the context
- If sentences are cut off, please complete them as much as possible
"""
        }
        
        return base_prompt + chunk_info.get(language, chunk_info["ja"])
    
    @classmethod
    def get_quality_levels(cls) -> Dict[str, str]:
        """
        利用可能な品質レベルを取得
        
        Returns:
            Dict: 品質レベルの説明
        """
        return {
            TranscriptionQuality.BASIC.value: "基本的な文字起こし",
            TranscriptionQuality.STANDARD.value: "標準品質の文字起こし",
            TranscriptionQuality.HIGH.value: "高品質な文字起こし",
            TranscriptionQuality.PROFESSIONAL.value: "プロフェッショナル品質の文字起こし"
        }
    
    @classmethod
    def get_supported_languages(cls) -> Dict[str, str]:
        """
        サポートされている言語を取得
        
        Returns:
            Dict: 言語コードと名前のマッピング
        """
        return {
            "ja": "日本語",
            "en": "English"
        }
    
    @classmethod
    def get_contexts(cls) -> Dict[str, str]:
        """
        利用可能なコンテキストを取得
        
        Returns:
            Dict: コンテキストの説明
        """
        return {
            TranscriptionContext.MEETING.value: "会議・ミーティング",
            TranscriptionContext.LECTURE.value: "講義・セミナー",
            TranscriptionContext.INTERVIEW.value: "インタビュー・対談",
            TranscriptionContext.PRESENTATION.value: "プレゼンテーション",
            TranscriptionContext.GENERAL.value: "一般的な会話"
        }