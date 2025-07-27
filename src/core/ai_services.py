"""
STT議事録システム - AI サービス

Gemini APIを使用した文字起こし、品質チェック、議事録生成などのAI機能を提供
"""

import os
from typing import Dict, Any, Optional
from google import genai

from ..prompts import TranscriptionPrompts, QualityCheckPrompts
from ..prompts.quality_check import QualityCheckType, QualityLevel
from ..utils import get_logger, APIError
from ..utils.prompt_loader import load_and_render_prompt_with_language
from ..utils.retry_utils import method_error_handler
import json
from pathlib import Path


class GeminiService:
    """Gemini APIを使用したAIサービスクラス"""
    
    def __init__(self, api_key: str, model_name: Optional[str] = None):
        self.logger = get_logger(__name__)
        if not api_key:
            raise ValueError("API key is required")
        self.api_key = api_key
        
        # Load settings
        settings_file = Path("settings.json")
        with open(settings_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        
        # Set default model
        self.model_name = model_name if model_name is not None else settings.get("gemini_model")
        
        # Set task-specific models
        self.models = {
            "transcription": None,
            "minutes_generation": None,
            "summarization": None
        }
        
        # Load task-specific models from settings if available
        if "gemini_models" in settings:
            gemini_models = settings.get("gemini_models", {})
            self.models["transcription"] = gemini_models.get("transcription")
            self.models["minutes_generation"] = gemini_models.get("minutes_generation")
            self.models["summarization"] = gemini_models.get("summarization")
        
        self._setup_client()
    
    def get_model_for_task(self, task: str) -> str:
        """
        タスク用のモデル名を取得
        
        Args:
            task: タスク名 ("transcription", "minutes_generation", "summarization")
            
        Returns:
            str: モデル名
        """
        if task in self.models and self.models[task]:
            return self.models[task]
        return self.model_name
    
    def set_model_for_task(self, task: str, model_name: str) -> None:
        """
        タスク用のモデル名を設定
        
        Args:
            task: タスク名 ("transcription", "minutes_generation", "summarization")
            model_name: モデル名
        """
        if task in self.models:
            self.models[task] = model_name
            self.logger.info(f"{task}用モデルを設定: {model_name}")
    
    @method_error_handler(APIError, "Failed to setup Gemini client")
    def _setup_client(self) -> None:
        """Gemini APIクライアントのセットアップ"""
        self.client = genai.Client(api_key=self.api_key)
        self.logger.info(f"Gemini APIクライアント初期化完了: {self.model_name}")

    @method_error_handler(APIError, "Failed to transcribe audio")
    def transcribe_audio(
            self,
            audio_file_path: str,
            prompt: Optional[str],
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

        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"音声ファイルが見つかりません: {audio_file_path}")

        self.logger.info(f"音声文字起こし開始: {audio_file_path}")

        # プロンプトの読み込み
        prompt_text = TranscriptionPrompts.get_transcription_prompt(
            language=language
        ) if prompt is None else prompt

        # 音声ファイルをアップロード
        audio_file = self.client.files.upload(file=audio_file_path)
        
        # ファイルがACTIVE状態になるまで待機
        if not self._wait_for_file_active(audio_file.name):
            raise APIError(f"音声ファイルがACTIVE状態になりませんでした: {audio_file.name}")

        # 文字起こし用のモデルを取得
        transcription_model = self.get_model_for_task("transcription")
        self.logger.info(f"文字起こし用モデル: {transcription_model}")

        # 文字起こし実行
        response = self.client.models.generate_content(
            model=transcription_model,
            contents=[audio_file, prompt_text]
        )

        # ファイルを削除（Gemini側）- 失敗してもメイン処理には影響しないのでログだけ出す
        self._delete_uploaded_file(audio_file.name)

        self.logger.info(f"文字起こし完了: {len(response.text)}文字")
        return response.text.strip()

    def _wait_for_file_active(self, file_name: str, max_wait_time: int = 300) -> bool:
        """ファイルがACTIVE状態になるまで待機
        
        Args:
            file_name: ファイル名
            max_wait_time: 最大待機時間（秒）
            
        Returns:
            bool: ファイルがACTIVE状態になったかどうか
        """
        import time
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            file_info = self.client.files.get(name=file_name)
            
            if file_info.state == 'ACTIVE':
                self.logger.info(f"ファイル {file_name} がACTIVE状態になりました")
                return True
            elif file_info.state == 'FAILED':
                self.logger.error(f"ファイル {file_name} の処理が失敗しました")
                return False
            
            self.logger.debug(f"ファイル {file_name} の状態: {file_info.state} - 待機中...")
            time.sleep(5)  # 5秒待機
        
        self.logger.error(f"タイムアウト: ファイル {file_name} がACTIVE状態になりませんでした")
        return False
        
    def _delete_uploaded_file(self, file_name: str) -> None:
        """アップロードしたファイルを削除（エラーは無視）"""
        try:
            self.client.files.delete(name=file_name)
        except Exception as e:
            self.logger.warning(f"アップロードファイルの削除に失敗: {e}")

    @method_error_handler(APIError, "Failed to check transcription quality")
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
        self.logger.info("文字起こし品質チェック開始")

        # プロンプトの読み込み
        prompt = QualityCheckPrompts.get_quality_check_prompt(
            check_type=QualityCheckType.COMPREHENSIVE,
            quality_level=QualityLevel.STANDARD,
            language="ja"
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt
        )

        if not response.text:
            raise APIError("品質チェック結果が空です")

        # JSONパースを試行
        quality_result = self._parse_json_response(response.text)

        # 追加メトリクス
        quality_result.update({
            'text_length': len(transcription),
            'word_count': len(transcription.split()),
            'estimated_speaking_rate': self._calculate_speaking_rate(transcription, original_audio_duration),
            'model_used': self.model_name
        })

        self.logger.info(f"品質チェック完了: 品質={quality_result.get('overall_quality', 'unknown')}")
        return quality_result
    
    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """JSONレスポンスをパース（エラー時はフォールバック）"""
        import json
        try:
            return json.loads(response_text.strip())
        except json.JSONDecodeError:
            # JSONパースに失敗した場合のフォールバック
            self.logger.warning("JSONパースに失敗しました。フォールバック値を使用します。")
            return {
                "confidence": 0.7,
                "issues": ["JSON解析エラーのため詳細評価不可"],
                "overall_quality": "medium"
            }

    @method_error_handler(APIError, "Failed to generate minutes")
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
        self.logger.info(f"議事録生成開始: フォーマット={format_type}")

        # プロンプトを読み込んで構築
        prompt = load_and_render_prompt_with_language(
            category="minutes",
            prompt_name=format_type,
            language="ja",
            context=meeting_context,
            transcription=transcription
        )

        # 議事録生成用のモデルを取得
        minutes_model = self.get_model_for_task("minutes_generation")
        self.logger.info(f"議事録生成用モデル: {minutes_model}")

        # 議事録生成
        response = self.client.models.generate_content(
            model=minutes_model,
            contents=prompt
        )

        if not response.text:
            raise APIError("議事録生成結果が空です")

        self.logger.info(f"議事録生成完了: {len(response.text)}文字")
        return response.text.strip()
        
    def generate_minutes_from_text(
            self,
            prompt: str,
            task: str = "minutes_generation"
    ) -> str:
        """
        プロンプトテキストから議事録を生成
        
        Args:
            prompt: 議事録生成用のプロンプトテキスト
            task: タスク名 ("minutes_generation" または "summarization")
            
        Returns:
            str: 生成された議事録
        """
        try:
            # このメソッドは特殊なエラーハンドリングが必要なため、
            # method_error_handlerデコレータではなく、カスタムtry-exceptを使用
            
            self.logger.info(f"テキストからの{task}開始")

            # タスクに応じたモデルを取得
            model_to_use = self.get_model_for_task(task)
            self.logger.info(f"{task}用モデル: {model_to_use}")

            # 議事録生成
            response = self.client.models.generate_content(
                model=model_to_use,
                contents=prompt
            )

            if not response.text:
                raise APIError(f"{task}結果が空です")

            self.logger.info(f"テキストからの{task}完了: {len(response.text)}文字")
            return response.text.strip()
            
        except Exception as e:
            # レート制限エラー（429）の場合の特殊処理
            error_info = self._extract_rate_limit_info(str(e))
            
            raise APIError(
                f"Failed to generate minutes from text: {str(e)}", 
                api_name="gemini", 
                status_code=error_info["status_code"],
                retry_delay=error_info["retry_delay"]
            )

    @method_error_handler(APIError, "Failed to analyze video content")
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
        if not os.path.exists(video_file_path):
            raise FileNotFoundError(f"動画ファイルが見つかりません: {video_file_path}")
        
        self.logger.info(f"動画解析開始: {video_file_path}, タイプ={analysis_type}")
        
        # 動画ファイルをアップロード
        video_file = self.client.files.upload(file=video_file_path)
        
        # ファイルがACTIVE状態になるまで待機
        if not self._wait_for_file_active(video_file.name):
            raise APIError(f"動画ファイルがACTIVE状態になりませんでした: {video_file.name}")
        
        # 解析タイプに応じたプロンプトを取得
        prompt = load_and_render_prompt_with_language(
            category="video_analysis",
            prompt_name=analysis_type,
            language="ja"
        )
        
        # 解析実行
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[video_file, prompt]
        )
        
        # ファイルを削除（Gemini側）- 失敗してもメイン処理には影響しないのでログだけ出す
        self._delete_uploaded_file(video_file.name)
        
        # JSONパースを試行
        analysis_result = self._parse_json_response_with_fallback(
            response.text, 
            {"analysis_type": analysis_type, "raw_response": response.text, "parsing_error": True}
        )
        
        self.logger.info(f"動画解析完了: タイプ={analysis_type}")
        return analysis_result
    

    def _parse_json_response_with_fallback(self, response_text: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
        """JSONレスポンスをパース（エラー時は指定されたフォールバック値を使用）"""
        import json
        try:
            return json.loads(response_text.strip())
        except json.JSONDecodeError:
            self.logger.warning("JSONパースに失敗しました。フォールバック値を使用します。")
            return fallback
    
    def generate_minutes_from_media(
        self,
        media_file_path: str,
        prompt: str
    ) -> str:
        """
        メディアファイル（動画または音声）から議事録を生成

        Args:
            media_file_path: メディアファイルのパス
            prompt: 議事録生成用プロンプト

        Returns:
            str: 生成された議事録
        """
        try:
            # このメソッドは特殊なエラーハンドリングが必要なため、
            # method_error_handlerデコレータではなく、カスタムtry-exceptを使用
            
            # 早期リターンによるネスト削減
            if not os.path.exists(media_file_path):
                raise FileNotFoundError(f"メディアファイルが見つかりません: {media_file_path}")

            self.logger.info(f"メディアからの議事録生成開始: {media_file_path}")

            # メディアファイルをアップロード
            media_file = self.client.files.upload(file=media_file_path)
            
            # ファイルがACTIVE状態になるまで待機
            if not self._wait_for_file_active(media_file.name):
                raise APIError(f"メディアファイルがACTIVE状態になりませんでした: {media_file.name}")

            # 議事録生成実行
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[media_file, prompt]
            )
            # ファイルを削除（Gemini側）- 失敗してもメイン処理には影響しないのでログだけ出す
            self._delete_uploaded_file(media_file.name)

            self.logger.info(f"メディアからの議事録生成完了: {len(response.text)}文字")
            return response.text.strip()

        except Exception as e:
            # レート制限エラー（429）の場合の特殊処理
            error_info = self._extract_rate_limit_info(str(e))
            
            raise APIError(
                f"Failed to generate minutes from media: {str(e)}", 
                api_name="gemini", 
                status_code=error_info["status_code"],
                retry_delay=error_info["retry_delay"]
            )
    
    def _extract_rate_limit_info(self, error_str: str) -> Dict[str, Any]:
        """レート制限エラー情報を抽出"""
        retry_delay = None
        status_code = None
        
        # レート制限エラー（429）の場合、retryDelayを抽出
        if "429" in error_str and "RESOURCE_EXHAUSTED" in error_str:
            status_code = 429
            # retryDelayを抽出
            import re
            retry_delay_match = re.search(r"'retryDelay': '(\d+)s'", error_str)
            if retry_delay_match:
                retry_seconds = int(retry_delay_match.group(1))
                retry_delay = float(retry_seconds)
                self.logger.warning(f"レート制限エラー検出: {retry_delay}秒後に再試行します")
        
        return {
            "status_code": status_code,
            "retry_delay": retry_delay
        }
    
    def _estimate_confidence(self, text: str) -> float:
        """
        文字起こし結果の信頼度を推定
        
        Args:
            text: 文字起こしテキスト
            
        Returns:
            float: 信頼度スコア (0.0-1.0)
        """
        # エラー時のデフォルト値
        if not text:
            return 0.7
            
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
            # 何らかのエラーが発生した場合はデフォルト値を返す
            return 0.7
    
    def _calculate_speaking_rate(self, text: str, duration: Optional[float]) -> Optional[float]:
        """
        発話速度を計算
        
        Args:
            text: 文字起こしテキスト
            duration: 音声の長さ（秒）
            
        Returns:
            Optional[float]: 発話速度（文字/分）
        """
        # 早期リターンによるネスト削減
        if not text or duration is None or duration <= 0:
            return None
            
        try:
            char_count = len(text.replace(' ', '').replace('\n', ''))
            speaking_rate = (char_count / duration) * 60  # 文字/分
            
            return speaking_rate
            
        except Exception:
            # 計算エラー時はNoneを返す
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