"""
STT議事録システム - 議事録生成ノード

文字起こし結果から構造化された議事録を生成するノード
"""

import re
from typing import Dict, Any, Optional
from datetime import datetime

from src.workflows.state import STTState
from src.utils import get_logger, APIError, api_call_with_retry
from src.utils.logging_config import log_state_transition, LogContext
from src.utils.retry_utils import method_error_handler

# Gemini APIのインポートを試行
try:
    from google import genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


def generate_minutes_node(state: STTState) -> STTState:
    """
    議事録の生成
    
    処理内容:
    - 構造化された議事録の生成
    - サマリーの作成
    - フォーマット調整
    
    Args:
        state: 現在の処理状態
        
    Returns:
        更新された処理状態
    """
    logger = get_logger("minutes_generation")
    
    with LogContext(logger, "議事録生成", state["session_id"]) as ctx:
        # 状態遷移をログ
        log_state_transition(logger, state["processing_stage"], "minutes_generation", state["session_id"])
        state["processing_stage"] = "minutes_generation"
        
        transcription = state.get("transcription", "")
        
        # 文字起こし結果が空の場合は早期リターン
        if not transcription:
            _handle_empty_transcription(state, logger)
            return state
        
        ctx.log_progress(f"議事録生成開始: {len(transcription)}文字の文字起こしから生成")
        
        try:
            # 議事録とサマリーの生成
            if not HAS_GEMINI:
                # Gemini APIが利用できない場合は基本的な整形のみ
                ctx.log_progress("Gemini APIが利用できないため基本整形のみ実行")
                minutes = _generate_basic_minutes(transcription, state)
                summary = _generate_basic_summary(transcription)
            else:
                # AI を使用した高品質な議事録生成
                ctx.log_progress("AI を使用した議事録生成を実行")
                minutes = _generate_ai_minutes(transcription, state)
                summary = _generate_ai_summary(transcription, state)
            
            # 生成結果を状態に保存
            state["minutes"] = minutes
            state["summary"] = summary
            
            # 出力フォーマットに応じた調整
            output_format = state["settings"].get("output_format", "markdown")
            if output_format != "markdown":
                state["minutes"] = _convert_format(minutes, output_format)
            
            ctx.log_progress(f"議事録生成完了: {len(minutes)}文字")
            state["processing_log"].append(f"議事録生成完了: {len(minutes)}文字")
            
            logger.info(f"議事録生成完了: 議事録 {len(minutes)}文字, サマリー {len(summary)}文字")
            
        except Exception as e:
            _handle_minutes_generation_error(state, e, logger)
    
    return state

def _handle_empty_transcription(state: STTState, logger) -> None:
    """空の文字起こし結果を処理するヘルパー関数"""
    warning_msg = "文字起こし結果が空のため議事録生成をスキップします"
    state["warnings"].append(warning_msg)
    logger.warning(warning_msg)
    state["minutes"] = ""
    state["summary"] = ""

def _handle_minutes_generation_error(state: STTState, error: Exception, logger) -> None:
    """議事録生成エラーを処理するヘルパー関数"""
    error_msg = f"議事録生成エラー: {str(error)}"
    state["errors"].append(error_msg)
    logger.error(error_msg, exc_info=True)
    
    # エラー時は基本整形を試行
    try:
        state["minutes"] = _generate_basic_minutes(state.get("transcription", ""), state)
        state["summary"] = _generate_basic_summary(state.get("transcription", ""))
    except Exception:
        state["minutes"] = ""
        state["summary"] = ""


@method_error_handler(APIError, "AI議事録生成に失敗しました")
def _generate_ai_minutes(transcription: str, state: STTState) -> str:
    """
    AI を使用した議事録生成
    
    Args:
        transcription: 文字起こし結果
        state: 現在の状態
        
    Returns:
        生成された議事録
    """
    logger = get_logger("minutes_generation")
    
    # API設定
    settings = state["settings"]
    api_key = settings.get("gemini_api_key")
    if not api_key:
        logger.warning("Gemini APIキーが設定されていないため基本整形にフォールバック")
        return _generate_basic_minutes(transcription, state)
    
    import os
    os.environ['GOOGLE_API_KEY'] = api_key
    client = genai.Client()
    model_name = settings.get("gemini_model")
    
    # 議事録生成プロンプトを構築
    prompt = _build_minutes_prompt(transcription, state)
    
    # AI による議事録生成実行
    def _generate_content():
        return client.models.generate_content(
            model=model_name,
            contents=prompt
        )
    
    response = api_call_with_retry(
        _generate_content,
        max_retries=settings.get("max_retries", 5),
        logger=logger
    )
    
    minutes = response.text.strip()
    
    # 後処理
    minutes = _post_process_minutes(minutes, state)
    
    logger.info(f"AI議事録生成完了: {len(minutes)}文字")
    return minutes


@method_error_handler(APIError, "AIサマリー生成に失敗しました")
def _generate_ai_summary(transcription: str, state: STTState) -> str:
    """
    AI を使用したサマリー生成
    
    Args:
        transcription: 文字起こし結果
        state: 現在の状態
        
    Returns:
        生成されたサマリー
        
    Raises:
        APIError: AI API呼び出しに失敗した場合
    """
    logger = get_logger("minutes_generation")
    
    # API設定
    settings = state["settings"]
    api_key = settings.get("gemini_api_key")
    if not api_key:
        logger.warning("Gemini APIキーが設定されていないため基本サマリーにフォールバック")
        return _generate_basic_summary(transcription)
    
    import os
    os.environ['GOOGLE_API_KEY'] = api_key
    client = genai.Client()
    model_name = settings.get("gemini_model")
    
    # サマリー生成プロンプト
    prompt = _build_summary_prompt(transcription, state)
    
    # AI によるサマリー生成実行
    def _generate_content():
        return client.models.generate_content(
            model=model_name,
            contents=prompt
        )
    
    response = api_call_with_retry(
        _generate_content,
        max_retries=settings.get("max_retries", 5),
        logger=logger
    )
    
    summary = response.text.strip()
    
    logger.info(f"AIサマリー生成完了: {len(summary)}文字")
    return summary


def _generate_basic_minutes(transcription: str, state: STTState) -> str:
    """
    基本的な議事録整形（AI なし）
    
    Args:
        transcription: 文字起こし結果
        state: 現在の状態
        
    Returns:
        整形された議事録
    """
    if not transcription:
        return ""
    
    # クラス情報を取得
    class_info = state.get("class_info", {})
    class_name = class_info.get("name", "不明")
    teacher = class_info.get("teacher", "不明")
    datetime_str = class_info.get("datetime", "不明")
    
    # 基本的なヘッダーを作成
    header = f"""# 議事録

## 基本情報
- **授業名**: {class_name}
- **担当教員**: {teacher}
- **日時**: {datetime_str}
- **作成日**: {datetime.now().strftime("%Y年%m月%d日")}

## 内容

"""
    
    # 文字起こし結果を整形
    formatted_content = _format_transcription_content(transcription)
    
    return header + formatted_content


def _generate_basic_summary(transcription: str) -> str:
    """
    基本的なサマリー生成（AI なし）
    
    Args:
        transcription: 文字起こし結果
        
    Returns:
        基本サマリー
    """
    if not transcription:
        return "内容なし"
    
    # 基本統計
    char_count = len(transcription)
    word_count = len(transcription.split())
    line_count = len(transcription.split('\n'))
    
    # 最初の200文字を抜粋
    excerpt = transcription[:200] + "..." if len(transcription) > 200 else transcription
    
    summary = f"""## サマリー

**統計情報**
- 文字数: {char_count:,}文字
- 単語数: {word_count:,}語
- 行数: {line_count}行

**内容抜粋**
{excerpt}
"""
    
    return summary


def _build_minutes_prompt(transcription: str, state: STTState) -> str:
    """
    議事録生成用プロンプトを構築
    
    Args:
        transcription: 文字起こし結果
        state: 現在の状態
        
    Returns:
        構築されたプロンプト
    """
    # クラス情報を取得
    class_info = state.get("class_info", {})
    class_name = class_info.get("name", "不明")
    teacher = class_info.get("teacher", "不明")
    datetime_str = class_info.get("datetime", "不明")
    
    # 基本プロンプトを読み込み
    base_prompt = _load_minutes_prompt(state)
    
    # プロンプトに情報を埋め込み
    prompt = base_prompt.format(
        class_name=class_name,
        teacher=teacher,
        datetime=datetime_str,
        transcription=transcription
    )
    
    return prompt


def _build_summary_prompt(transcription: str, state: STTState) -> str:
    """
    サマリー生成用プロンプトを構築
    
    Args:
        transcription: 文字起こし結果
        state: 現在の状態
        
    Returns:
        構築されたプロンプト
    """
    base_prompt = _load_summary_prompt()
    
    # クラス情報を取得
    class_info = state.get("class_info", {})
    class_name = class_info.get("name", "不明")
    
    prompt = base_prompt.format(
        class_name=class_name,
        transcription=transcription
    )
    
    return prompt


def _load_minutes_prompt(state: STTState = None) -> str:
    """
    議事録生成用プロンプトを読み込み
    
    Args:
        state: 処理状態（設定情報を取得するため）
        
    Returns:
        プロンプト文字列
    """
    default_prompt = """以下の文字起こし結果から、構造化された議事録を作成してください。

授業情報:
- 授業名: {class_name}
- 担当教員: {teacher}
- 日時: {datetime}

要求事項:
1. Markdown形式で出力してください
2. 以下の構造で整理してください:
   - 基本情報
   - 主要なトピック
   - 重要なポイント
   - 質疑応答（あれば）
   - まとめ
3. 内容を要約し、重要な情報を強調してください
4. 専門用語や重要な概念は太字で強調してください
5. 必要に応じて箇条書きを使用してください

文字起こし結果:
{transcription}

上記の要求事項に従って、読みやすく整理された議事録を作成してください。"""
    
    try:
        # 設定タイプを取得（"会議" または "授業"）
        setting_type = None
        if state and "settings" in state:
            setting_type = state["settings"].get("prompt_type")
            
        # プロンプトファイルから読み込みを試行
        from src.prompts.minutes_generation import get_minutes_prompt
        return get_minutes_prompt(setting_type=setting_type)
    except ImportError:
        # プロンプトモジュールが未実装の場合はデフォルトを使用
        return default_prompt


def _load_summary_prompt() -> str:
    """
    サマリー生成用プロンプトを読み込み
    
    Returns:
        プロンプト文字列
    """
    try:
        # プロンプトローダーを使用してプロンプトを読み込み
        from src.utils.prompt_loader import load_and_render_prompt
        return load_and_render_prompt(
            category="minutes",
            prompt_name="generation_summary"
        )
    except ImportError:
        # プロンプトローダーが利用できない場合のフォールバック
        default_prompt = """以下の文字起こし結果から、簡潔なサマリーを作成してください。

授業名: {class_name}

要求事項:
1. 3-5行程度の簡潔なサマリーにしてください
2. 主要なトピックと重要なポイントを含めてください
3. 専門用語は適切に説明してください
4. 読みやすい日本語で記述してください

文字起こし結果:
{transcription}

上記の内容を簡潔にまとめてください。"""
        return default_prompt
        
    except Exception as e:
        # その他のエラーが発生した場合もデフォルトを使用
        logger = get_logger("minutes_generation")
        logger.warning(f"サマリープロンプト読み込みエラー: {str(e)}")
        
        default_prompt = """以下の文字起こし結果から、簡潔なサマリーを作成してください。

授業名: {class_name}

要求事項:
1. 3-5行程度の簡潔なサマリーにしてください
2. 主要なトピックと重要なポイントを含めてください
3. 専門用語は適切に説明してください
4. 読みやすい日本語で記述してください

文字起こし結果:
{transcription}

上記の内容を簡潔にまとめてください。"""
        return default_prompt


def _format_transcription_content(transcription: str) -> str:
    """
    文字起こし内容を整形
    
    Args:
        transcription: 文字起こし結果
        
    Returns:
        整形された内容
    """
    # 基本的な整形処理
    lines = transcription.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 話者の識別と整形
        if '：' in line or ':' in line:
            # 話者がいる場合
            if '：' in line:
                speaker, content = line.split('：', 1)
                formatted_lines.append(f"**{speaker.strip()}**: {content.strip()}")
            else:
                speaker, content = line.split(':', 1)
                formatted_lines.append(f"**{speaker.strip()}**: {content.strip()}")
        else:
            # 話者がない場合
            formatted_lines.append(line)
    
    return '\n\n'.join(formatted_lines)


def _post_process_minutes(minutes: str, state: STTState) -> str:
    """
    議事録の後処理
    
    Args:
        minutes: 生成された議事録
        state: 現在の状態
        
    Returns:
        後処理された議事録
    """
    # タイムスタンプの追加（設定で有効な場合）
    if state["settings"].get("include_timestamps"):
        timestamp = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
        minutes = f"{minutes}\n\n---\n*生成日時: {timestamp}*"
    
    # 品質情報の追加（オプション）
    quality_result = state.get("quality_check_result")
    if quality_result and quality_result.get("overall_score", 0) < 0.7:
        warning = "\n\n> ⚠️ **注意**: この議事録は品質スコアが低い文字起こし結果から生成されています。内容を確認してください。"
        minutes += warning
    
    return minutes


def _convert_format(content: str, output_format: str) -> str:
    """
    出力フォーマットを変換
    
    Args:
        content: 変換対象のコンテンツ
        output_format: 出力フォーマット
        
    Returns:
        変換されたコンテンツ
    """
    if output_format == "text":
        # Markdownからプレーンテキストに変換
        # 簡単な変換（見出し、太字などを除去）
        text_content = re.sub(r'#+\s*', '', content)  # 見出し
        text_content = re.sub(r'\*\*(.*?)\*\*', r'\1', text_content)  # 太字
        text_content = re.sub(r'\*(.*?)\*', r'\1', text_content)  # イタリック
        text_content = re.sub(r'`(.*?)`', r'\1', text_content)  # インラインコード
        return text_content
    
    elif output_format == "json":
        # JSON形式に変換（簡略化）
        import json
        return json.dumps({
            "content": content,
            "format": "markdown",
            "generated_at": datetime.now().isoformat()
        }, ensure_ascii=False, indent=2)
    
    # デフォルトはMarkdownのまま
    return content


def extract_key_points(minutes: str) -> list:
    """
    議事録から重要なポイントを抽出（既存コードとの互換性のため）
    
    Args:
        minutes: 議事録内容
        
    Returns:
        重要なポイントのリスト
    """
    key_points = []
    
    # 太字で強調された部分を抽出
    bold_pattern = re.compile(r'\*\*(.*?)\*\*')
    bold_matches = bold_pattern.findall(minutes)
    key_points.extend(bold_matches)
    
    # 箇条書きの項目を抽出
    bullet_pattern = re.compile(r'^[-*+]\s+(.+)$', re.MULTILINE)
    bullet_matches = bullet_pattern.findall(minutes)
    key_points.extend(bullet_matches)
    
    # 重複を除去
    return list(set(key_points))


def generate_title_from_content(transcription: str, class_info: Dict[str, Any] = None) -> str:
    """
    内容からタイトルを生成（既存コードとの互換性のため）
    
    Args:
        transcription: 文字起こし結果
        class_info: クラス情報
        
    Returns:
        生成されたタイトル
    """
    if class_info and class_info.get("name") != "不明":
        class_name = class_info["name"]
        datetime_str = class_info.get("datetime", "")
        if datetime_str and datetime_str != "不明":
            return f"{class_name} - {datetime_str}"
        else:
            return f"{class_name} - 議事録"
    
    # クラス情報がない場合は内容から推測
    lines = transcription.split('\n')[:5]  # 最初の5行を確認
    for line in lines:
        if len(line.strip()) > 10 and len(line.strip()) < 50:
            return f"{line.strip()[:30]}... - 議事録"
    
    return f"議事録 - {datetime.now().strftime('%Y年%m月%d日')}"