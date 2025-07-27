"""
STT議事録システム - 品質チェックノード

文字起こし結果の品質チェックとハルシネーション検出を行うノード
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.workflows.state import STTState
from src.utils import get_logger, QualityCheckError, api_call_with_retry
from src.utils.logging_config import log_state_transition, LogContext
from src.utils.retry_utils import method_error_handler

# Gemini APIのインポートを試行
try:
    from google import genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


def quality_check_node(state: STTState) -> STTState:
    """
    文字起こし結果の品質チェック
    
    処理内容:
    - ハルシネーション検出
    - 信頼度スコア計算
    - 品質レポート生成
    
    Args:
        state: 現在の処理状態
        
    Returns:
        更新された処理状態
    """
    logger = get_logger("quality_check")
    
    with LogContext(logger, "品質チェック", state["session_id"]) as ctx:
        try:
            # 状態遷移をログ
            log_state_transition(logger, state["processing_stage"], "quality_check", state["session_id"])
            state["processing_stage"] = "quality_check"
            
            transcription = state.get("transcription", "")
            
            # 文字起こし結果が空の場合は早期リターン
            if not transcription:
                _handle_empty_transcription(state, logger)
                return state
            
            ctx.log_progress(f"文字起こし結果の品質チェック開始: {len(transcription)}文字")
            
            # 基本的な品質チェック
            basic_quality = _perform_basic_quality_check(transcription)
            ctx.log_progress(f"基本品質スコア: {basic_quality['quality_score']:.2f}")
            
            # ハルシネーション検出（設定で有効な場合）
            hallucination_result = {}
            if state["settings"].get("enable_hallucination_check"):
                ctx.log_progress("ハルシネーション検出を実行")
                hallucination_result = _detect_hallucination(transcription, state["settings"])
                ctx.log_progress(f"ハルシネーション検出完了: スコア {hallucination_result.get('hallucination_score', 0):.2f}")
            
            # 総合品質評価
            quality_result = _combine_quality_results(basic_quality, hallucination_result)
            
            # 品質チェック結果を状態に保存
            state["quality_check_result"] = quality_result
            
            # 品質に基づく警告の生成
            _generate_quality_warnings(state, quality_result)
            
            ctx.log_progress(f"品質チェック完了: 総合スコア {quality_result['overall_score']:.2f}")
            state["processing_log"].append(f"品質チェック完了: スコア {quality_result['overall_score']:.2f}")
            
            logger.info(f"品質チェック完了: 総合スコア {quality_result['overall_score']:.2f}")
            
        except Exception as e:
            _handle_quality_check_error(state, e, logger)
    
    return state

def _handle_empty_transcription(state: STTState, logger) -> None:
    """空の文字起こし結果を処理するヘルパー関数"""
    warning_msg = "文字起こし結果が空のため品質チェックをスキップします"
    state["warnings"].append(warning_msg)
    logger.warning(warning_msg)
    state["quality_check_result"] = _create_empty_quality_result()

def _handle_quality_check_error(state: STTState, error: Exception, logger) -> None:
    """品質チェックエラーを処理するヘルパー関数"""
    error_msg = f"品質チェックエラー: {str(error)}"
    state["errors"].append(error_msg)
    logger.error(error_msg, exc_info=True)
    
    # エラー時はデフォルト結果を設定
    state["quality_check_result"] = _create_error_quality_result(str(error))


def _perform_basic_quality_check(transcription: str) -> Dict[str, Any]:
    """
    基本的な品質チェックを実行
    
    Args:
        transcription: 文字起こし結果
        
    Returns:
        基本品質チェック結果
    """
    result = {
        "quality_score": 0.0,
        "issues": [],
        "metrics": {},
        "suggestions": []
    }
    
    # 基本メトリクスの計算
    char_count = len(transcription)
    word_count = len(transcription.split())
    line_count = len(transcription.split('\n'))
    
    result["metrics"] = {
        "character_count": char_count,
        "word_count": word_count,
        "line_count": line_count,
        "average_word_length": char_count / word_count if word_count > 0 else 0
    }
    
    # 品質チェック項目
    quality_score = 1.0
    
    # 1. 長さチェック
    if char_count < 50:
        result["issues"].append("文字起こし結果が短すぎます")
        result["suggestions"].append("音声ファイルの品質を確認してください")
        quality_score -= 0.3
    elif char_count < 200:
        result["issues"].append("文字起こし結果がやや短いです")
        quality_score -= 0.1
    
    # 2. 不明瞭部分のチェック
    unclear_patterns = ["[不明瞭]", "[聞き取れない]", "[雑音]", "？？？"]
    unclear_count = sum(transcription.count(pattern) for pattern in unclear_patterns)
    
    if unclear_count > 0:
        unclear_ratio = unclear_count / word_count if word_count > 0 else 0
        if unclear_ratio > 0.1:  # 10%以上が不明瞭
            result["issues"].append(f"不明瞭な部分が多すぎます ({unclear_count}箇所)")
            result["suggestions"].append("音声品質の改善を検討してください")
            quality_score -= 0.4
        elif unclear_ratio > 0.05:  # 5%以上が不明瞭
            result["issues"].append(f"不明瞭な部分があります ({unclear_count}箇所)")
            quality_score -= 0.2
    
    # 3. 繰り返しパターンのチェック
    repetition_score = _check_repetition_patterns(transcription)
    if repetition_score > 0.3:
        result["issues"].append("同じ内容の繰り返しが多く検出されました")
        result["suggestions"].append("音声の重複部分を確認してください")
        quality_score -= repetition_score * 0.3
    
    # 4. 文構造のチェック
    sentence_quality = _check_sentence_structure(transcription)
    if sentence_quality < 0.7:
        result["issues"].append("文の構造に問題がある可能性があります")
        result["suggestions"].append("文字起こし結果を手動で確認してください")
        quality_score -= (1.0 - sentence_quality) * 0.2
    
    # 5. 専門用語・固有名詞のチェック
    terminology_issues = _check_terminology(transcription)
    if terminology_issues:
        result["issues"].extend(terminology_issues)
        quality_score -= len(terminology_issues) * 0.1
    
    result["quality_score"] = max(0.0, min(1.0, quality_score))
    
    return result


@method_error_handler(QualityCheckError, "ハルシネーション検出に失敗しました")
def _detect_hallucination(transcription: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    ハルシネーション検出を実行
    
    Args:
        transcription: 文字起こし結果
        settings: システム設定
        
    Returns:
        ハルシネーション検出結果
    """
    logger = get_logger("quality_check")
    
    result = {
        "hallucination_score": 0.0,
        "detected_issues": [],
        "confidence": 0.0
    }
    
    # Gemini APIが利用できない場合は早期リターン
    if not HAS_GEMINI:
        logger.warning("Gemini APIが利用できないためハルシネーション検出をスキップします")
        return result
    
    # APIキーが設定されていない場合は早期リターン
    api_key = settings.get("gemini_api_key")
    if not api_key:
        logger.warning("Gemini APIキーが設定されていないためハルシネーション検出をスキップします")
        return result
    
    # API設定
    import os
    os.environ['GOOGLE_API_KEY'] = api_key
    client = genai.Client()
    model_name = settings.get("gemini_model")
    
    # ハルシネーション検出プロンプト
    prompt = _load_hallucination_check_prompt()
    
    # AI による検証実行
    def _generate_content():
        return client.models.generate_content(
            model=model_name,
            contents=[prompt, f"\n\n検証対象テキスト:\n{transcription}"]
        )
    
    response = api_call_with_retry(
        _generate_content,
        max_retries=settings.get("max_retries", 5),
        logger=logger
    )
    
    # 結果を解析
    analysis_result = _parse_hallucination_response(response.text)
    result.update(analysis_result)
    
    logger.info(f"ハルシネーション検出完了: スコア {result['hallucination_score']:.2f}")
    
    return result


def _check_repetition_patterns(text: str) -> float:
    """
    繰り返しパターンをチェック
    
    Args:
        text: チェック対象テキスト
        
    Returns:
        繰り返しスコア（0.0-1.0、高いほど繰り返しが多い）
    """
    sentences = [s.strip() for s in text.split('。') if s.strip()]
    if len(sentences) < 2:
        return 0.0
    
    repetition_count = 0
    total_comparisons = 0
    
    for i in range(len(sentences)):
        for j in range(i + 1, len(sentences)):
            total_comparisons += 1
            # 類似度を簡単に計算（共通する文字の割合）
            similarity = _calculate_text_similarity(sentences[i], sentences[j])
            if similarity > 0.8:  # 80%以上類似
                repetition_count += 1
    
    return repetition_count / total_comparisons if total_comparisons > 0 else 0.0


def _check_sentence_structure(text: str) -> float:
    """
    文構造の品質をチェック
    
    Args:
        text: チェック対象テキスト
        
    Returns:
        文構造品質スコア（0.0-1.0）
    """
    sentences = [s.strip() for s in text.split('。') if s.strip()]
    if not sentences:
        return 0.0
    
    quality_score = 1.0
    
    # 極端に短い文や長い文をチェック
    for sentence in sentences:
        length = len(sentence)
        if length < 5:  # 極端に短い
            quality_score -= 0.1
        elif length > 200:  # 極端に長い
            quality_score -= 0.1
    
    # 句読点の使用をチェック
    punctuation_count = text.count('、') + text.count('。')
    if punctuation_count < len(sentences) * 0.5:
        quality_score -= 0.2
    
    return max(0.0, min(1.0, quality_score))


def _check_terminology(text: str) -> List[str]:
    """
    専門用語・固有名詞の問題をチェック
    
    Args:
        text: チェック対象テキスト
        
    Returns:
        検出された問題のリスト
    """
    issues = []
    
    # 明らかに間違った変換をチェック
    common_mistakes = [
        ("ひらがな", "平仮名"),
        ("かたかな", "片仮名"),
        ("かんじ", "漢字"),
        ("にほんご", "日本語"),
        ("えいご", "英語")
    ]
    
    for mistake, correct in common_mistakes:
        if mistake in text:
            issues.append(f"'{mistake}' は '{correct}' の可能性があります")
    
    # 不自然なカタカナ表記をチェック
    katakana_pattern = re.compile(r'[ア-ン]{10,}')
    long_katakana = katakana_pattern.findall(text)
    if long_katakana:
        issues.append("長いカタカナ表記が検出されました（誤変換の可能性）")
    
    return issues


def _calculate_text_similarity(text1: str, text2: str) -> float:
    """
    テキストの類似度を計算
    
    Args:
        text1: テキスト1
        text2: テキスト2
        
    Returns:
        類似度（0.0-1.0）
    """
    if not text1 or not text2:
        return 0.0
    
    # 簡単な文字レベルの類似度計算
    set1 = set(text1)
    set2 = set(text2)
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    return intersection / union if union > 0 else 0.0


def _combine_quality_results(basic_result: Dict[str, Any], hallucination_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    品質チェック結果を統合
    
    Args:
        basic_result: 基本品質チェック結果
        hallucination_result: ハルシネーション検出結果
        
    Returns:
        統合された品質チェック結果
    """
    # 基本品質スコア
    basic_score = basic_result.get("quality_score", 0.0)
    
    # ハルシネーションスコア（低いほど良い）
    hallucination_score = hallucination_result.get("hallucination_score", 0.0)
    hallucination_penalty = hallucination_score * 0.5
    
    # 総合スコア計算
    overall_score = max(0.0, basic_score - hallucination_penalty)
    
    return {
        "overall_score": overall_score,
        "basic_quality": basic_result,
        "hallucination_detection": hallucination_result,
        "timestamp": datetime.now().isoformat(),
        "summary": _generate_quality_summary(overall_score, basic_result, hallucination_result)
    }


def _generate_quality_summary(overall_score: float, basic_result: Dict[str, Any], hallucination_result: Dict[str, Any]) -> str:
    """
    品質チェックサマリーを生成
    
    Args:
        overall_score: 総合スコア
        basic_result: 基本品質チェック結果
        hallucination_result: ハルシネーション検出結果
        
    Returns:
        品質サマリー文字列
    """
    if overall_score >= 0.8:
        quality_level = "高品質"
    elif overall_score >= 0.6:
        quality_level = "中品質"
    elif overall_score >= 0.4:
        quality_level = "低品質"
    else:
        quality_level = "要改善"
    
    issues_count = len(basic_result.get("issues", []))
    hallucination_issues = len(hallucination_result.get("detected_issues", []))
    
    summary = f"品質レベル: {quality_level} (スコア: {overall_score:.2f})\n"
    summary += f"基本品質問題: {issues_count}件\n"
    summary += f"ハルシネーション問題: {hallucination_issues}件"
    
    return summary


def _generate_quality_warnings(state: STTState, quality_result: Dict[str, Any]) -> None:
    """
    品質に基づく警告を生成
    
    Args:
        state: 現在の状態
        quality_result: 品質チェック結果
    """
    overall_score = quality_result.get("overall_score", 0.0)
    min_threshold = state["settings"].get("min_confidence_threshold")
    
    if overall_score < min_threshold:
        warning_msg = f"品質スコア({overall_score:.2f})が閾値({min_threshold})を下回っています"
        state["warnings"].append(warning_msg)
    
    # 基本品質の問題
    basic_issues = quality_result.get("basic_quality", {}).get("issues", [])
    for issue in basic_issues:
        state["warnings"].append(f"品質問題: {issue}")
    
    # ハルシネーション問題
    hallucination_issues = quality_result.get("hallucination_detection", {}).get("detected_issues", [])
    for issue in hallucination_issues:
        state["warnings"].append(f"ハルシネーション: {issue}")


@method_error_handler(QualityCheckError, "ハルシネーション検出用プロンプトの読み込みに失敗")
def _load_hallucination_check_prompt() -> str:
    """
    ハルシネーション検出用プロンプトを読み込み
    
    Returns:
        プロンプト文字列
    """
    logger = get_logger("quality_check")
    
    # プロンプトローダーを使用して外部ファイルから読み込み
    try:
        from src.utils.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.load_prompt("quality_check", "hallucination_check")
        if prompt:
            return prompt
    except ImportError:
        logger.warning("PromptLoaderモジュールが見つかりません、デフォルトプロンプトを使用します")
    except Exception as e:
        logger.warning(f"外部プロンプトファイルの読み込みに失敗、デフォルトを使用: {str(e)}")
    
    # デフォルトプロンプト
    logger.info("デフォルトのハルシネーション検出プロンプトを使用します")
    return """以下の文字起こし結果について、ハルシネーション（幻覚・誤認識）の可能性を検証してください。

検証項目:
1. 音声から実際に聞こえるはずのない内容が含まれていないか
2. 文脈に合わない突然の話題転換がないか
3. 明らかに不自然な専門用語や固有名詞がないか
4. 同じ内容の不自然な繰り返しがないか
5. 音声の品質に対して過度に詳細な内容になっていないか

以下の形式で回答してください:
ハルシネーションスコア: [0.0-1.0の数値]
検出された問題: [問題のリスト]
信頼度: [0.0-1.0の数値]"""


@method_error_handler(QualityCheckError, "ハルシネーション検出レスポンスの解析に失敗")
def _parse_hallucination_response(response_text: str) -> Dict[str, Any]:
    """
    ハルシネーション検出レスポンスを解析
    
    Args:
        response_text: AIからのレスポンステキスト
        
    Returns:
        解析結果
    """
    result = {
        "hallucination_score": 0.0,
        "detected_issues": [],
        "confidence": 0.0
    }
    
    if not response_text:
        return result
    
    lines = response_text.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # スコアの抽出
        if 'ハルシネーションスコア' in line or 'スコア' in line:
            score_match = re.search(r'(\d+\.?\d*)', line)
            if score_match:
                result["hallucination_score"] = float(score_match.group(1))
        
        # 信頼度の抽出
        elif '信頼度' in line:
            confidence_match = re.search(r'(\d+\.?\d*)', line)
            if confidence_match:
                result["confidence"] = float(confidence_match.group(1))
        
        # 問題の抽出
        elif '問題' in line and '：' in line:
            issue = line.split('：', 1)[1].strip()
            if issue:
                result["detected_issues"].append(issue)
    
    return result


def _create_empty_quality_result() -> Dict[str, Any]:
    """空の品質チェック結果を作成"""
    return {
        "overall_score": 0.0,
        "basic_quality": {
            "quality_score": 0.0,
            "issues": ["文字起こし結果が空です"],
            "metrics": {},
            "suggestions": []
        },
        "hallucination_detection": {
            "hallucination_score": 0.0,
            "detected_issues": [],
            "confidence": 0.0
        },
        "timestamp": datetime.now().isoformat(),
        "summary": "品質チェック未実行（文字起こし結果が空）"
    }


def _create_error_quality_result(error_message: str) -> Dict[str, Any]:
    """エラー時の品質チェック結果を作成"""
    return {
        "overall_score": 0.0,
        "basic_quality": {
            "quality_score": 0.0,
            "issues": [f"品質チェックエラー: {error_message}"],
            "metrics": {},
            "suggestions": ["品質チェック処理を再実行してください"]
        },
        "hallucination_detection": {
            "hallucination_score": 0.0,
            "detected_issues": [],
            "confidence": 0.0
        },
        "timestamp": datetime.now().isoformat(),
        "summary": f"品質チェックエラー: {error_message}"
    }