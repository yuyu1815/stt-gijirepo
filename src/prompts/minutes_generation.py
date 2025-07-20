"""
STT議事録システム - 議事録生成用プロンプト

議事録生成処理で使用するプロンプトテンプレートを管理
"""

from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime
import logging
from ..utils.prompt_loader import get_prompt_loader, load_and_render_prompt

logger = logging.getLogger(__name__)


class MinutesFormat(Enum):
    """議事録フォーマット"""
    DETAILED = "detailed"
    SUMMARY = "summary"
    ACTION_ITEMS = "action_items"
    STRUCTURED = "structured"
    EXECUTIVE = "executive"


class MeetingType(Enum):
    """会議タイプ"""
    REGULAR = "regular"
    PROJECT = "project"
    BRAINSTORM = "brainstorm"
    REVIEW = "review"
    PLANNING = "planning"
    DECISION = "decision"
    TRAINING = "training"


class MinutesGenerationPrompts:
    """議事録生成用プロンプトクラス"""
    
    # 基本プロンプトテンプレート
    BASE_PROMPTS = {
        "ja": {
            MinutesFormat.DETAILED: """
以下の文字起こしテキストから詳細な議事録を作成してください。

# 議事録

## 基本情報
- 日時: {meeting_date}
- 参加者: {participants}
- 議題: {agenda}

## 議論内容
### 主要な議論ポイント
{main_discussion_placeholder}

### 決定事項
{decisions_placeholder}

### 課題・懸念事項
{issues_placeholder}

## アクションアイテム
{action_items_placeholder}

## 次回予定
{next_meeting_placeholder}

要求事項:
1. 重要な発言や決定事項を漏らさない
2. 冗長な表現は簡潔にまとめる
3. アクションアイテムは具体的に記載（担当者、期限、優先度）
4. 読みやすい構造で整理
5. Markdown形式で出力
6. 数値、日程、固有名詞は正確に記載

文字起こしテキスト:
""",
            MinutesFormat.SUMMARY: """
以下の文字起こしテキストから簡潔な議事録サマリーを作成してください。

## 会議サマリー

### 基本情報
- 日時: {meeting_date}
- 参加者: {participants}
- 議題: {agenda}

### 主要な議論
{main_points_placeholder}

### 決定事項
{decisions_placeholder}

### アクションアイテム
{action_items_placeholder}

### 次回予定
{next_steps_placeholder}

要求事項:
1. 重要なポイントのみを簡潔にまとめる
2. 1-2ページ以内に収める
3. 決定事項とアクションアイテムを明確に区別
4. 読みやすいMarkdown形式で出力

文字起こしテキスト:
""",
            MinutesFormat.ACTION_ITEMS: """
以下の文字起こしテキストからアクションアイテムに特化した議事録を作成してください。

## アクションアイテム

### 即座に実行すべき項目（高優先度）
{high_priority_placeholder}

### 今週中に実行すべき項目（中優先度）
{medium_priority_placeholder}

### 今月中に実行すべき項目（低優先度）
{low_priority_placeholder}

### フォローアップが必要な項目
{followup_placeholder}

各アクションアイテムの形式:
- [ ] **担当者**: 具体的な内容 (期限: YYYY/MM/DD, 優先度: 高/中/低)

要求事項:
1. 実行可能で具体的なアクションのみを抽出
2. 担当者、期限、優先度を明確に記載
3. 関連するアクションはグループ化
4. チェックボックス形式で出力

文字起こしテキスト:
""",
            MinutesFormat.STRUCTURED: """
以下の文字起こしテキストから構造化された議事録を作成してください。

# {meeting_title}

## 📋 会議概要
- **日時**: {meeting_date}
- **参加者**: {participants}
- **議題**: {agenda}
- **会議タイプ**: {meeting_type}

## 🎯 議論のポイント
### 主要トピック
{main_topics_placeholder}

### 提起された課題
{raised_issues_placeholder}

### 提案された解決策
{proposed_solutions_placeholder}

## ✅ 決定事項
{decisions_placeholder}

## 📝 アクションアイテム
{action_items_placeholder}

## 📊 データ・数値
{data_numbers_placeholder}

## 🔄 次回までの宿題
{homework_placeholder}

## 📅 次回予定
{next_meeting_placeholder}

要求事項:
1. 絵文字を使用して視覚的に分かりやすく
2. 重要度に応じて情報を階層化
3. データや数値は別セクションで整理
4. アクションアイテムは実行可能な形で記載

文字起こしテキスト:
""",
            MinutesFormat.EXECUTIVE: """
以下の文字起こしテキストから経営層向けのエグゼクティブサマリーを作成してください。

# エグゼクティブサマリー

## 🎯 会議の目的と成果
{purpose_outcome_placeholder}

## 📈 重要な決定事項
{key_decisions_placeholder}

## ⚠️ 注意が必要な課題
{critical_issues_placeholder}

## 💰 予算・リソースへの影響
{budget_impact_placeholder}

## 📊 KPI・メトリクス
{kpi_metrics_placeholder}

## 🚀 次のステップ
{next_steps_placeholder}

## ⏰ タイムライン
{timeline_placeholder}

要求事項:
1. 経営判断に必要な情報のみを抽出
2. 数値、予算、リスクを重点的に記載
3. 簡潔で分かりやすい表現
4. 戦略的な観点から整理

文字起こしテキスト:
"""
        },
        "en": {
            MinutesFormat.DETAILED: """
Please create detailed meeting minutes from the following transcription text.

# Meeting Minutes

## Basic Information
- Date: {meeting_date}
- Participants: {participants}
- Agenda: {agenda}

## Discussion Content
### Main Discussion Points
{main_discussion_placeholder}

### Decisions Made
{decisions_placeholder}

### Issues and Concerns
{issues_placeholder}

## Action Items
{action_items_placeholder}

## Next Meeting
{next_meeting_placeholder}

Requirements:
1. Don't miss important statements or decisions
2. Summarize verbose expressions concisely
3. Specify action items clearly (assignee, deadline, priority)
4. Organize in readable structure
5. Output in Markdown format
6. Record numbers, dates, and proper nouns accurately

Transcription text:
""",
            MinutesFormat.SUMMARY: """
Please create a concise meeting summary from the following transcription text.

## Meeting Summary

### Basic Information
- Date: {meeting_date}
- Participants: {participants}
- Agenda: {agenda}

### Main Discussion
{main_points_placeholder}

### Decisions Made
{decisions_placeholder}

### Action Items
{action_items_placeholder}

### Next Steps
{next_steps_placeholder}

Requirements:
1. Summarize only important points concisely
2. Keep within 1-2 pages
3. Clearly distinguish decisions from action items
4. Output in readable Markdown format

Transcription text:
""",
            MinutesFormat.ACTION_ITEMS: """
Please create action item-focused meeting minutes from the following transcription text.

## Action Items

### Immediate Actions (High Priority)
{high_priority_placeholder}

### This Week (Medium Priority)
{medium_priority_placeholder}

### This Month (Low Priority)
{low_priority_placeholder}

### Follow-up Required
{followup_placeholder}

Format for each action item:
- [ ] **Assignee**: Specific content (Deadline: YYYY/MM/DD, Priority: High/Medium/Low)

Requirements:
1. Extract only actionable and specific items
2. Clearly specify assignee, deadline, and priority
3. Group related actions
4. Output in checkbox format

Transcription text:
""",
            MinutesFormat.STRUCTURED: """
Please create structured meeting minutes from the following transcription text.

# {meeting_title}

## 📋 Meeting Overview
- **Date**: {meeting_date}
- **Participants**: {participants}
- **Agenda**: {agenda}
- **Meeting Type**: {meeting_type}

## 🎯 Discussion Points
### Main Topics
{main_topics_placeholder}

### Issues Raised
{raised_issues_placeholder}

### Proposed Solutions
{proposed_solutions_placeholder}

## ✅ Decisions Made
{decisions_placeholder}

## 📝 Action Items
{action_items_placeholder}

## 📊 Data & Numbers
{data_numbers_placeholder}

## 🔄 Homework Until Next Meeting
{homework_placeholder}

## 📅 Next Meeting
{next_meeting_placeholder}

Requirements:
1. Use emojis for visual clarity
2. Hierarchize information by importance
3. Organize data and numbers in separate section
4. Record action items in actionable format

Transcription text:
""",
            MinutesFormat.EXECUTIVE: """
Please create an executive summary for leadership from the following transcription text.

# Executive Summary

## 🎯 Meeting Purpose and Outcomes
{purpose_outcome_placeholder}

## 📈 Key Decisions
{key_decisions_placeholder}

## ⚠️ Critical Issues Requiring Attention
{critical_issues_placeholder}

## 💰 Budget and Resource Impact
{budget_impact_placeholder}

## 📊 KPIs and Metrics
{kpi_metrics_placeholder}

## 🚀 Next Steps
{next_steps_placeholder}

## ⏰ Timeline
{timeline_placeholder}

Requirements:
1. Extract only information necessary for executive decisions
2. Focus on numbers, budget, and risks
3. Use concise and clear expressions
4. Organize from strategic perspective

Transcription text:
"""
        }
    }
    
    # 会議タイプ別プロンプト拡張
    MEETING_TYPE_EXTENSIONS = {
        MeetingType.REGULAR: {
            "ja": """

定例会議追加要求:
- 前回からの進捗状況を明確に記載
- 定期的な報告事項を整理
- 継続課題の状況を追跡
- 次回までの宿題を明確化
""",
            "en": """

Regular meeting additional requirements:
- Clearly record progress since last meeting
- Organize regular reporting items
- Track status of ongoing issues
- Clarify homework until next meeting
"""
        },
        MeetingType.PROJECT: {
            "ja": """

プロジェクト会議追加要求:
- プロジェクトの進捗状況とマイルストーン
- リスクと課題の管理状況
- リソース配分と予算の状況
- スケジュールの調整事項
""",
            "en": """

Project meeting additional requirements:
- Project progress and milestones
- Risk and issue management status
- Resource allocation and budget status
- Schedule adjustment items
"""
        },
        MeetingType.BRAINSTORM: {
            "ja": """

ブレインストーミング追加要求:
- 提案されたアイデアを分類整理
- 実現可能性の評価結果
- 次のステップで検討すべき項目
- 創造的な発想を重視した記録
""",
            "en": """

Brainstorming additional requirements:
- Classify and organize proposed ideas
- Feasibility evaluation results
- Items to consider in next steps
- Record emphasizing creative thinking
"""
        },
        MeetingType.REVIEW: {
            "ja": """

レビュー会議追加要求:
- レビュー対象の評価結果
- 改善点と推奨事項
- 品質基準との比較
- 承認・却下の判定理由
""",
            "en": """

Review meeting additional requirements:
- Evaluation results of review subjects
- Improvement points and recommendations
- Comparison with quality standards
- Reasons for approval/rejection decisions
"""
        },
        MeetingType.PLANNING: {
            "ja": """

計画会議追加要求:
- 目標設定と成功指標
- タイムラインと重要な締切
- 必要なリソースと予算
- リスク要因と対策
""",
            "en": """

Planning meeting additional requirements:
- Goal setting and success metrics
- Timeline and important deadlines
- Required resources and budget
- Risk factors and countermeasures
"""
        },
        MeetingType.DECISION: {
            "ja": """

意思決定会議追加要求:
- 検討された選択肢の比較
- 決定の根拠と理由
- 決定事項の影響範囲
- 実行責任者と実行計画
""",
            "en": """

Decision meeting additional requirements:
- Comparison of considered options
- Basis and reasons for decisions
- Impact scope of decisions
- Implementation responsible parties and plans
"""
        },
        MeetingType.TRAINING: {
            "ja": """

研修会議追加要求:
- 学習目標と達成度
- 重要な学習ポイント
- 質疑応答の内容
- フォローアップの計画
""",
            "en": """

Training meeting additional requirements:
- Learning objectives and achievement levels
- Important learning points
- Q&A content
- Follow-up plans
"""
        }
    }
    
    @classmethod
    def get_minutes_prompt(
        cls,
        format_type: MinutesFormat = MinutesFormat.DETAILED,
        language: str = "ja",
        meeting_type: MeetingType = MeetingType.REGULAR,
        meeting_context: Optional[Dict[str, Any]] = None,
        custom_instructions: Optional[str] = None
    ) -> str:
        """
        議事録生成用プロンプトを取得
        
        Args:
            format_type: 議事録フォーマット
            language: 言語コード ("ja", "en")
            meeting_type: 会議タイプ
            meeting_context: 会議の文脈情報
            custom_instructions: カスタム指示
            
        Returns:
            str: 議事録生成用プロンプト
        """
        try:
            # フォーマットタイプに応じてプロンプトファイルを選択
            prompt_mapping = {
                MinutesFormat.DETAILED: "detailed_minutes",
                MinutesFormat.SUMMARY: "summary_minutes",
                MinutesFormat.ACTION_ITEMS: "action_items",
                MinutesFormat.STRUCTURED: "detailed_minutes",
                MinutesFormat.EXECUTIVE: "summary_minutes"
            }
            
            prompt_name = prompt_mapping.get(format_type, "detailed_minutes")
            
            # 会議タイプが授業の場合は専用プロンプトを使用
            if meeting_type == MeetingType.TRAINING:
                prompt_name = "meeting_types/lecture"
            
            # 会議情報を準備
            meeting_info = ""
            if meeting_context:
                meeting_info = f"日時: {meeting_context.get('date', '未設定')}, " \
                              f"参加者: {meeting_context.get('participants', '未設定')}, " \
                              f"議題: {meeting_context.get('agenda', '未設定')}"
            
            # Markdownプロンプトを読み込んでレンダリング
            return load_and_render_prompt(
                category="minutes_generation",
                prompt_name=prompt_name,
                transcription="",  # 実際の文字起こしは後で置換される
                meeting_info=meeting_info,
                language=language,
                format_type=format_type.value,
                custom_instructions=custom_instructions or ""
            )
            
        except Exception as e:
            logger.warning(f"Failed to load Markdown prompt, falling back to legacy: {e}")
            # フォールバック: 既存のハードコードプロンプトを使用
            return cls._get_legacy_minutes_prompt(
                format_type, language, meeting_type, meeting_context, custom_instructions
            )
    
    @classmethod
    def _get_legacy_minutes_prompt(
        cls,
        format_type: MinutesFormat,
        language: str,
        meeting_type: MeetingType,
        meeting_context: Optional[Dict[str, Any]],
        custom_instructions: Optional[str]
    ) -> str:
        """
        レガシー議事録プロンプトを取得（フォールバック用）
        
        Args:
            format_type: 議事録フォーマット
            language: 言語コード
            meeting_type: 会議タイプ
            meeting_context: 会議の文脈情報
            custom_instructions: カスタム指示
            
        Returns:
            str: レガシー議事録プロンプト
        """
        # 基本プロンプトを取得
        base_prompt = cls.BASE_PROMPTS.get(language, cls.BASE_PROMPTS["ja"]).get(
            format_type, cls.BASE_PROMPTS[language][MinutesFormat.DETAILED]
        )
        
        # 会議情報でプレースホルダーを置換
        if meeting_context:
            base_prompt = base_prompt.format(
                meeting_date=meeting_context.get('date', '未設定'),
                participants=meeting_context.get('participants', '未設定'),
                agenda=meeting_context.get('agenda', '未設定'),
                meeting_title=meeting_context.get('title', '会議'),
                meeting_type=meeting_context.get('type', meeting_type.value),
                main_discussion_placeholder="（文字起こしから抽出）",
                decisions_placeholder="（文字起こしから抽出）",
                issues_placeholder="（文字起こしから抽出）",
                action_items_placeholder="（文字起こしから抽出）",
                next_meeting_placeholder="（文字起こしから抽出）",
                main_points_placeholder="（文字起こしから抽出）",
                next_steps_placeholder="（文字起こしから抽出）",
                high_priority_placeholder="（文字起こしから抽出）",
                medium_priority_placeholder="（文字起こしから抽出）",
                low_priority_placeholder="（文字起こしから抽出）",
                followup_placeholder="（文字起こしから抽出）",
                main_topics_placeholder="（文字起こしから抽出）",
                raised_issues_placeholder="（文字起こしから抽出）",
                proposed_solutions_placeholder="（文字起こしから抽出）",
                data_numbers_placeholder="（文字起こしから抽出）",
                homework_placeholder="（文字起こしから抽出）",
                purpose_outcome_placeholder="（文字起こしから抽出）",
                key_decisions_placeholder="（文字起こしから抽出）",
                critical_issues_placeholder="（文字起こしから抽出）",
                budget_impact_placeholder="（文字起こしから抽出）",
                kpi_metrics_placeholder="（文字起こしから抽出）",
                timeline_placeholder="（文字起こしから抽出）"
            )
        
        # 会議タイプ別拡張を追加
        type_extension = cls.MEETING_TYPE_EXTENSIONS.get(meeting_type, {}).get(language, "")
        
        # カスタム指示を追加
        custom_section = ""
        if custom_instructions:
            custom_section = f"\n\n追加指示:\n{custom_instructions}"
        
        return base_prompt + type_extension + custom_section
    
    @classmethod
    def get_summary_prompt(
        cls,
        minutes_text: str,
        language: str = "ja",
        max_length: int = 200
    ) -> str:
        """
        議事録サマリー生成用プロンプトを取得
        
        Args:
            minutes_text: 議事録テキスト
            language: 言語コード
            max_length: 最大文字数
            
        Returns:
            str: サマリー生成用プロンプト
        """
        prompts = {
            "ja": f"""
以下の議事録から{max_length}文字以内の要約を作成してください。

要求事項:
1. 最も重要な決定事項を含める
2. 主要なアクションアイテムを含める
3. 次回までの重要な期限を含める
4. 簡潔で分かりやすい文章にする

議事録:
{minutes_text}
""",
            "en": f"""
Please create a summary of no more than {max_length} characters from the following meeting minutes.

Requirements:
1. Include the most important decisions
2. Include key action items
3. Include important deadlines until next meeting
4. Use concise and clear sentences

Meeting minutes:
{minutes_text}
"""
        }
        
        return prompts.get(language, prompts["ja"])
    
    @classmethod
    def get_action_items_extraction_prompt(
        cls,
        transcription_text: str,
        language: str = "ja"
    ) -> str:
        """
        アクションアイテム抽出専用プロンプトを取得
        
        Args:
            transcription_text: 文字起こしテキスト
            language: 言語コード
            
        Returns:
            str: アクションアイテム抽出用プロンプト
        """
        prompts = {
            "ja": f"""
以下の文字起こしテキストからアクションアイテムのみを抽出してください。

抽出条件:
1. 具体的で実行可能な内容のみ
2. 担当者が明確または推測可能
3. 期限が設定されているか設定可能
4. 「検討する」「考える」などの曖昧な表現は除外

出力形式:
- [ ] **担当者**: 具体的な内容 (期限: YYYY/MM/DD, 優先度: 高/中/低)

文字起こしテキスト:
{transcription_text}
""",
            "en": f"""
Please extract only action items from the following transcription text.

Extraction criteria:
1. Only specific and actionable content
2. Assignee is clear or can be inferred
3. Deadline is set or can be set
4. Exclude vague expressions like "consider" or "think about"

Output format:
- [ ] **Assignee**: Specific content (Deadline: YYYY/MM/DD, Priority: High/Medium/Low)

Transcription text:
{transcription_text}
"""
        }
        
        return prompts.get(language, prompts["ja"])
    
    @classmethod
    def get_format_types(cls) -> Dict[str, str]:
        """
        利用可能なフォーマットタイプを取得
        
        Returns:
            Dict: フォーマットタイプの説明
        """
        return {
            MinutesFormat.DETAILED.value: "詳細な議事録",
            MinutesFormat.SUMMARY.value: "簡潔なサマリー",
            MinutesFormat.ACTION_ITEMS.value: "アクションアイテム特化",
            MinutesFormat.STRUCTURED.value: "構造化された議事録",
            MinutesFormat.EXECUTIVE.value: "エグゼクティブサマリー"
        }
    
    @classmethod
    def get_meeting_types(cls) -> Dict[str, str]:
        """
        利用可能な会議タイプを取得
        
        Returns:
            Dict: 会議タイプの説明
        """
        return {
            MeetingType.REGULAR.value: "定例会議",
            MeetingType.PROJECT.value: "プロジェクト会議",
            MeetingType.BRAINSTORM.value: "ブレインストーミング",
            MeetingType.REVIEW.value: "レビュー会議",
            MeetingType.PLANNING.value: "計画会議",
            MeetingType.DECISION.value: "意思決定会議",
            MeetingType.TRAINING.value: "研修・トレーニング"
        }