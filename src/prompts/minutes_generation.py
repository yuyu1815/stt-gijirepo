"""
STT議事録システム - 議事録生成用プロンプト

議事録生成処理で使用するプロンプトテンプレートを管理
"""

from typing import Dict, Any, Optional
from enum import Enum
import logging
from ..utils.prompt_loader import load_and_render_prompt_with_language

logger = logging.getLogger(__name__)


# 後方互換性のための関数
def get_minutes_prompt(
    format_type=None,
    language="ja",
    meeting_type=None,
    meeting_context=None,
    custom_instructions=None,
    setting_type=None
) -> str:
    """
    議事録生成用プロンプトを取得する関数（後方互換性のため）
    
    Args:
        format_type: 議事録フォーマット
        language: 言語コード
        meeting_type: 会議タイプ
        meeting_context: 会議の文脈情報
        custom_instructions: カスタム指示
        setting_type: 設定タイプ ("会議", "授業", None)
        
    Returns:
        str: 議事録生成用プロンプト
    """
    # MinutesGenerationPromptsクラスのメソッドを呼び出す
    from src.prompts.minutes_generation import MinutesGenerationPrompts, MinutesFormat, MeetingType
    
    # デフォルト値の設定
    if format_type is None:
        format_type = MinutesFormat.DETAILED
    elif isinstance(format_type, str):
        # 文字列の場合はenumに変換
        format_map = {f.value: f for f in MinutesFormat}
        format_type = format_map.get(format_type, MinutesFormat.DETAILED)
        
    if meeting_type is None:
        meeting_type = MeetingType.REGULAR
    elif isinstance(meeting_type, str):
        # 文字列の場合はenumに変換
        type_map = {t.value: t for t in MeetingType}
        meeting_type = type_map.get(meeting_type, MeetingType.REGULAR)
    
    return MinutesGenerationPrompts.get_minutes_prompt(
        format_type=format_type,
        language=language,
        meeting_type=meeting_type,
        meeting_context=meeting_context,
        custom_instructions=custom_instructions,
        setting_type=setting_type
    )


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
    
    @classmethod
    def get_minutes_prompt(
        cls,
        format_type: MinutesFormat = MinutesFormat.DETAILED,
        language: str = "ja",
        meeting_type: MeetingType = MeetingType.REGULAR,
        meeting_context: Optional[Dict[str, Any]] = None,
        custom_instructions: Optional[str] = None,
        setting_type: Optional[str] = None
    ) -> str:
        """
        議事録生成用プロンプトを取得
        
        Args:
            format_type: 議事録フォーマット
            language: 言語コード ("ja", "en")
            meeting_type: 会議タイプ
            meeting_context: 会議の文脈情報
            custom_instructions: カスタム指示
            setting_type: 設定タイプ ("会議", "授業", None)
            
        Returns:
            str: 議事録生成用プロンプト
            
        Raises:
            FileNotFoundError: プロンプトファイルが見つからない場合
            ValueError: プロンプトの形式が不正な場合
        """
        try:
            # 会議情報を準備
            meeting_info = ""
            if meeting_context:
                meeting_info = f"日時: {meeting_context.get('date', '未設定')}, " \
                              f"参加者: {meeting_context.get('participants', '未設定')}, " \
                              f"議題: {meeting_context.get('agenda', '未設定')}"
            
            # フォーマットタイプに応じたプロンプト名を構築
            # prompt_loader.pyが抽出するプロンプト名に合わせる
            prompt_name_map = {
                MinutesFormat.DETAILED: "detailed_minutes",
                MinutesFormat.SUMMARY: "summary_minutes",
                MinutesFormat.ACTION_ITEMS: "action_items",
                # STRUCTURED, EXECUTIVE は現在対応するMarkdownタグがないため、必要に応じて追加
            }
            base_prompt_name = prompt_name_map.get(format_type)
            if not base_prompt_name:
                raise ValueError(f"Unsupported minutes format: {format_type.value}")

            # 設定タイプに応じたプロンプトタイプとプロンプト名を決定
            prompt_type = None
            prompt_name = base_prompt_name
            
            if setting_type == "会議":
                prompt_type = "meeting"
                logger.info("会議用のプロンプトを使用します")
            elif setting_type == "授業":
                prompt_type = "school"
                # 授業の場合は特別なプロンプト名を使用
                if format_type == MinutesFormat.DETAILED:
                    prompt_name = "meeting_types_lecture"
                    logger.info("授業用の講義ノートプロンプトを使用します")
                else:
                    logger.info("授業用のプロンプトを使用します")
            elif setting_type in ["meeting", "school"]:
                # 内部IDが直接指定された場合
                prompt_type = setting_type
                # schoolの場合は特別なプロンプト名を使用
                if setting_type == "school" and format_type == MinutesFormat.DETAILED:
                    prompt_name = "meeting_types_lecture"
                    logger.info("授業用の講義ノートプロンプトを使用します（内部ID指定）")
                else:
                    logger.info(f"{setting_type}用のプロンプトを使用します（内部ID指定）")
            else:
                logger.info("デフォルトのプロンプトを使用します")

            # 基本プロンプトを読み込む
            base_prompt = load_and_render_prompt_with_language(
                category="minutes_generation",
                prompt_name=prompt_name,
                language=language,
                prompt_type=prompt_type,  # 設定タイプに応じたプロンプトタイプを使用
                transcription="",  # 実際の文字起こしは後で置換される
                meeting_date=meeting_context.get('date', '') if meeting_context else '',
                participants=meeting_context.get('participants', '') if meeting_context else '',
                agenda=meeting_context.get('agenda', '') if meeting_context else '',
                meeting_info=meeting_info,
                lecture_title=meeting_context.get('name', '') if meeting_context else '',
                course_name=meeting_context.get('name', '') if meeting_context else '',
                instructor_name=meeting_context.get('teacher', '') if meeting_context else '',
                datetime=meeting_context.get('date', '') if meeting_context else '',
                lecture_number=meeting_context.get('lecture_number', '') if meeting_context else '',
                topic=meeting_context.get('agenda', '') if meeting_context else '',
                custom_instructions=custom_instructions or ""
            )
            
            # 会議タイプに応じた追加プロンプトを読み込む（設定タイプが指定されていない場合のみ）
            if not setting_type:
                try:
                    # 会議タイプに応じた追加プロンプトを読み込む
                    # prompt_loader.pyが抽出するプロンプト名に合わせる
                    meeting_type_prompt = load_and_render_prompt_with_language(
                        category="minutes_generation",
                        prompt_name=f"meeting_types_{meeting_type.value}",
                        language=language
                    )
                    # 基本プロンプトと会議タイププロンプトを結合
                    return f"{base_prompt}\n\n{meeting_type_prompt}"
                except (FileNotFoundError, ValueError) as e:
                    logger.warning(f"会議タイプ用プロンプトの読み込みに失敗しました: {e}")
                    # 会議タイププロンプトが読み込めなくても基本プロンプトは返す
                    return base_prompt
            
            # 設定タイプが指定されている場合は基本プロンプトのみを返す
            return base_prompt
                
        except FileNotFoundError as e:
            error_msg = f"議事録生成用プロンプトファイルが見つかりません: format={format_type.value}, language={language}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg) from e
        except ValueError as e:
            error_msg = f"議事録生成用プロンプトの形式が不正です: format={format_type.value}, language={language}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"議事録生成用プロンプトの読み込み中に予期せぬエラーが発生しました: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    
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
            
        Raises:
            FileNotFoundError: プロンプトファイルが見つからない場合
            ValueError: プロンプトの形式が不正な場合
        """
        try:
            # プロンプト名を構築 (prompt_loader.pyが抽出するプロンプト名に合わせる)
            prompt_name = "summary_minutes"
            
            # プロンプトを読み込んでレンダリング
            return load_and_render_prompt_with_language(
                category="minutes_generation",
                prompt_name=prompt_name,
                language=language,
                minutes_text=minutes_text,
                max_length=max_length
            )
        except FileNotFoundError as e:
            error_msg = f"議事録サマリー生成用プロンプトファイルが見つかりません: language={language}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg) from e
        except ValueError as e:
            error_msg = f"議事録サマリー生成用プロンプトの形式が不正です: language={language}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"議事録サマリー生成用プロンプトの読み込み中に予期せぬエラーが発生しました: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
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
            
        Raises:
            FileNotFoundError: プロンプトファイルが見つからない場合
            ValueError: プロンプトの形式が不正な場合
        """
        try:
            # プロンプト名を構築 (prompt_loader.pyが抽出するプロンプト名に合わせる)
            prompt_name = "action_items"
            
            # プロンプトを読み込んでレンダリング
            return load_and_render_prompt_with_language(
                category="minutes_generation",
                prompt_name=prompt_name,
                language=language,
                transcription_text=transcription_text
            )
        except FileNotFoundError as e:
            error_msg = f"アクションアイテム抽出用プロンプトファイルが見つかりません: language={language}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg) from e
        except ValueError as e:
            error_msg = f"アクションアイテム抽出用プロンプトの形式が不正です: language={language}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"アクションアイテム抽出用プロンプトの読み込み中に予期せぬエラーが発生しました: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
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
