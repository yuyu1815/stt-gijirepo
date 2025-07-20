"""
STT議事録システム - AI サービス

Gemini APIを使用した文字起こし、品質チェック、議事録生成などのAI機能を提供
"""

import os
import time
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import logging

from google import genai
from google.genai import types

from ..utils import get_logger, APIError, api_call_with_retry
from ..utils.logging_config import LogContext


class GeminiService:
    """Gemini APIを使用したAIサービスクラス"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro"):
        self.logger = get_logger(__name__)
        if not api_key:
            raise ValueError("API key is required")
        self.api_key = api_key
        self.model_name = model_name
        self._setup_client()
    
    def _setup_client(self) -> None:
        """Gemini APIクライアントのセットアップ"""
        try:
            # 新しいAPIでのクライアント初期化
            os.environ['GOOGLE_API_KEY'] = self.api_key
            self.client = genai.Client()
            
            self.logger.info(f"Gemini APIクライアント初期化完了: {self.model_name}")
            
        except Exception as e:
            raise APIError(f"Failed to setup Gemini client: {str(e)}")
    
    def transcribe_audio(
        self, 
        audio_file_path: str, 
        prompt: Optional[str] = None,
        language: str = "ja"
    ) -> str:
        """
        音声ファイルを文字起こし
        
        Args:
            audio_file_path: 音声ファイルのパス
            prompt: 文字起こし用プロンプト
            language: 言語コード
            
        Returns:
            str: 文字起こし結果
        """
        try:
            if not os.path.exists(audio_file_path):
                raise FileNotFoundError(f"音声ファイルが見つかりません: {audio_file_path}")
            
            self.logger.info(f"音声文字起こし開始: {audio_file_path}")
            
            # 音声ファイルをアップロード
            audio_file = self.client.files.upload(file=audio_file_path)
            
            # デフォルトプロンプト
            if prompt is None:
                prompt = f"""
以下の音声ファイルを正確に文字起こししてください。

要求事項:
1. 話者の発言を正確に文字に起こす
2. 「えー」「あのー」などのフィラーは適度に除去
3. 句読点を適切に配置
4. 専門用語や固有名詞は文脈から推測して正確に記述
5. 聞き取れない部分は[不明瞭]と記載
6. 言語: {language}

音声ファイル:
"""
            
            # 文字起こし実行
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[audio_file, prompt]
            )
            
            if not response.text:
                raise APIError("文字起こし結果が空です")
            
            # ファイルを削除（Gemini側）
            try:
                self.client.files.delete(audio_file.name)
            except Exception as e:
                self.logger.warning(f"アップロードファイルの削除に失敗: {e}")
            
            self.logger.info(f"文字起こし完了: {len(response.text)}文字")
            return response.text.strip()
            
        except Exception as e:
            raise APIError(f"Failed to transcribe audio: {str(e)}")
    
    def check_transcription_quality(
        self, 
        transcription: str,
        original_audio_duration: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        文字起こし結果の品質チェック
        
        Args:
            transcription: 文字起こしテキスト
            original_audio_duration: 元音声の長さ（秒）
            
        Returns:
            Dict: 品質チェック結果
        """
        try:
            self.logger.info("文字起こし品質チェック開始")
            
            prompt = f"""
以下の文字起こしテキストの品質を評価してください。

評価項目:
1. 文法の正確性 (0-10点)
2. 文脈の一貫性 (0-10点)
3. 専門用語の適切性 (0-10点)
4. 全体的な読みやすさ (0-10点)
5. ハルシネーション（幻覚）の有無

以下のJSON形式で回答してください:
{{
    "confidence": 0.0-1.0の信頼度,
    "issues": ["問題点1", "問題点2"],
    "overall_quality": "high/medium/low"
}}

文字起こしテキスト:
{transcription}
"""
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            if not response.text:
                raise APIError("品質チェック結果が空です")
            
            # JSONパースを試行
            import json
            try:
                quality_result = json.loads(response.text.strip())
            except json.JSONDecodeError:
                # JSONパースに失敗した場合のフォールバック
                quality_result = {
                    "confidence": 0.7,
                    "issues": ["JSON解析エラーのため詳細評価不可"],
                    "overall_quality": "medium"
                }
            
            # 追加メトリクス
            quality_result.update({
                'text_length': len(transcription),
                'word_count': len(transcription.split()),
                'estimated_speaking_rate': self._calculate_speaking_rate(transcription, original_audio_duration),
                'model_used': self.model_name
            })
            
            self.logger.info(f"品質チェック完了: 品質={quality_result.get('overall_quality', 'unknown')}")
            return quality_result
            
        except Exception as e:
            raise APIError(f"Failed to check transcription quality: {str(e)}")
    
    def generate_minutes(
        self, 
        transcription: str,
        meeting_context: Optional[Dict[str, Any]] = None,
        format_type: str = "detailed"
    ) -> str:
        """
        文字起こしから議事録を生成
        
        Args:
            transcription: 文字起こしテキスト
            meeting_context: 会議の文脈情報
            format_type: 議事録フォーマット ("detailed", "summary", "action_items")
            
        Returns:
            str: 生成された議事録
        """
        try:
            self.logger.info(f"議事録生成開始: フォーマット={format_type}")
            
            # 文脈情報の準備
            context_info = ""
            if meeting_context:
                context_info = f"""
会議情報:
- 日時: {meeting_context.get('date', '不明')}
- 参加者: {meeting_context.get('participants', '不明')}
- 議題: {meeting_context.get('agenda', '不明')}
"""
            
            # フォーマット別プロンプト
            format_prompts = {
                "detailed": """
詳細な議事録を作成してください。以下の構成で整理してください:

# 議事録

## 基本情報
- 日時: 
- 参加者: 
- 議題: 

## 議論内容
### 主要な議論ポイント
- 
### 決定事項
- 
### 課題・懸念事項
- 

## アクションアイテム
- [ ] 担当者: 内容 (期限: )

## 次回予定
- 
""",
                "summary": """
簡潔な議事録サマリーを作成してください:

## 会議サマリー
- 主要な議論: 
- 決定事項: 
- アクションアイテム: 
""",
                "action_items": """
アクションアイテムに特化した議事録を作成してください:

## アクションアイテム
- [ ] 担当者: 内容 (期限: 優先度: )
"""
            }
            
            prompt = f"""
以下の文字起こしテキストから議事録を生成してください。

{context_info}

{format_prompts.get(format_type, format_prompts["detailed"])}

要求事項:
1. 重要な発言や決定事項を漏らさない
2. 冗長な表現は簡潔にまとめる
3. アクションアイテムは具体的に記載
4. 読みやすい構造で整理
5. Markdown形式で出力

文字起こしテキスト:
{transcription}
"""
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            if not response.text:
                raise APIError("議事録生成結果が空です")
            
            self.logger.info(f"議事録生成完了: {len(response.text)}文字")
            return response.text.strip()
            
        except Exception as e:
            raise APIError(f"Failed to generate minutes: {str(e)}")
    
    def analyze_video_content(
        self, 
        video_file_path: str,
        analysis_type: str = "brightness"
    ) -> Dict[str, Any]:
        """
        動画コンテンツの解析
        
        Args:
            video_file_path: 動画ファイルのパス
            analysis_type: 解析タイプ ("brightness", "content")
            
        Returns:
            Dict: 解析結果
        """
        try:
            if not os.path.exists(video_file_path):
                raise FileNotFoundError(f"動画ファイルが見つかりません: {video_file_path}")
            
            self.logger.info(f"動画解析開始: {video_file_path}, タイプ={analysis_type}")
            
            # 動画ファイルをアップロード
            video_file = self.client.files.upload(file=video_file_path)
            
            if analysis_type == "brightness":
                prompt = """
この動画の明度を分析してください。以下の点を評価してください:
1. 全体的な明るさレベル
2. 音声のみでの処理が適切かどうか

JSON形式で回答してください:
{
    "brightness_level": "bright/normal/dark",
    "confidence": 0.0-1.0の信頼度,
    "recommendation": "audio_only/video_processing"
}
"""
            else:  # content analysis
                prompt = """
この動画の内容を分析してください:
1. 主要なコンテンツタイプ（会議、プレゼン、講義など）
2. 視覚的要素の重要性

JSON形式で回答してください:
{
    "content_type": "meeting/presentation/lecture/other",
    "has_slides": true/false,
    "speaker_visible": true/false
}
"""
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[video_file, prompt]
            )
            
            if not response.text:
                raise APIError("動画解析結果が空です")
            
            # ファイルを削除（Gemini側）
            try:
                self.client.files.delete(video_file.name)
            except Exception as e:
                self.logger.warning(f"アップロードファイルの削除に失敗: {e}")
            
            # JSONパースを試行
            import json
            try:
                analysis_result = json.loads(response.text.strip())
            except json.JSONDecodeError:
                # JSONパースに失敗した場合のフォールバック
                analysis_result = {
                    "analysis_type": analysis_type,
                    "raw_response": response.text,
                    "parsing_error": True
                }
            
            self.logger.info(f"動画解析完了: タイプ={analysis_type}")
            return analysis_result
            
        except Exception as e:
            raise APIError(f"Failed to analyze video content: {str(e)}")
    
    def _estimate_confidence(self, text: str) -> float:
        """
        文字起こし結果の信頼度を推定
        
        Args:
            text: 文字起こしテキスト
            
        Returns:
            float: 信頼度スコア (0.0-1.0)
        """
        try:
            # 簡易的な信頼度推定
            confidence = 0.8  # ベース信頼度
            
            # 不明瞭マーカーの数で減点
            unclear_markers = text.count('[不明瞭]') + text.count('[聞き取れず]')
            confidence -= unclear_markers * 0.1
            
            # 文字数が極端に少ない場合は減点
            if len(text) < 50:
                confidence -= 0.2
            
            # 句読点の適切性で調整
            sentences = text.split('。')
            if len(sentences) > 1:
                confidence += 0.1
            
            return max(0.0, min(1.0, confidence))
            
        except Exception:
            return 0.7  # デフォルト値
    
    def _calculate_speaking_rate(self, text: str, duration: Optional[float]) -> Optional[float]:
        """
        発話速度を計算
        
        Args:
            text: 文字起こしテキスト
            duration: 音声の長さ（秒）
            
        Returns:
            Optional[float]: 発話速度（文字/分）
        """
        try:
            if duration is None or duration <= 0:
                return None
            
            char_count = len(text.replace(' ', '').replace('\n', ''))
            speaking_rate = (char_count / duration) * 60  # 文字/分
            
            return speaking_rate
            
        except Exception:
            return None
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        使用中のモデル情報を取得
        
        Returns:
            Dict: モデル情報
        """
        return {
            'model_name': self.model_name,
            'api_key_configured': bool(self.api_key),
            'client_initialized': hasattr(self, 'model')
        }