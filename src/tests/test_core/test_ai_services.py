"""
STT議事録システム - AI Services テスト

GeminiServiceクラスの包括的なテストスイート
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from typing import Dict, Any

from google import genai

from src.core.ai_services import GeminiService
from src.utils.error_handling import APIError


class TestGeminiService:
    """GeminiServiceクラスのテスト"""

    @pytest.fixture
    def mock_api_key(self):
        """テスト用APIキー"""
        return "test_api_key_12345"

    @pytest.fixture
    def gemini_service(self, mock_api_key):
        """GeminiServiceインスタンス"""
        with patch('google.genai.Client'):
            service = GeminiService(api_key=mock_api_key)
            return service

    @pytest.fixture
    def sample_audio_file(self):
        """テスト用音声ファイル"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(b'fake_audio_data')
            yield f.name
        os.unlink(f.name)

    @pytest.fixture
    def sample_video_file(self):
        """テスト用動画ファイル"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            f.write(b'fake_video_data')
            yield f.name
        os.unlink(f.name)

    def test_init_success(self, mock_api_key):
        """正常な初期化テスト"""
        with patch('google.genai.Client') as mock_client:
            service = GeminiService(api_key=mock_api_key)
            
            assert service.api_key == mock_api_key
            assert service.model_name == "gemini-1.5-pro"
            mock_client.assert_called_once()

    def test_init_custom_model(self, mock_api_key):
        """カスタムモデル指定での初期化テスト"""
        custom_model = "gemini-1.5-flash"
        with patch('google.genai.Client'):
            service = GeminiService(api_key=mock_api_key, model_name=custom_model)
            
            assert service.model_name == custom_model

    def test_init_missing_api_key(self):
        """APIキー未指定時のエラーテスト"""
        with pytest.raises(ValueError, match="API key is required"):
            GeminiService(api_key="")

    @patch('google.genai.configure')
    @patch('google.genai.GenerativeModel')
    def test_setup_client_success(self, mock_model_class, mock_configure, mock_api_key):
        """クライアントセットアップ成功テスト"""
        mock_model = Mock()
        mock_model_class.return_value = mock_model
        
        service = GeminiService(api_key=mock_api_key)
        
        assert service.model is not None
        mock_model_class.assert_called_once()

    @patch('google.genai.configure')
    @patch('google.genai.GenerativeModel')
    def test_setup_client_failure(self, mock_model_class, mock_configure, mock_api_key):
        """クライアントセットアップ失敗テスト"""
        mock_model_class.side_effect = Exception("API setup failed")
        
        with pytest.raises(APIError, match="Failed to setup Gemini client"):
            GeminiService(api_key=mock_api_key)

    @patch('google.genai.upload_file')
    def test_transcribe_audio_success(self, mock_upload, gemini_service, sample_audio_file):
        """音声文字起こし成功テスト"""
        # モックの設定
        mock_file = Mock()
        mock_file.uri = "test_uri"
        mock_upload.return_value = mock_file
        
        mock_response = Mock()
        mock_response.text = "これはテスト音声の文字起こし結果です。"
        gemini_service.model.generate_content.return_value = mock_response
        
        # テスト実行
        result = gemini_service.transcribe_audio(sample_audio_file)
        
        # 検証
        assert result == "これはテスト音声の文字起こし結果です。"
        mock_upload.assert_called_once()
        gemini_service.model.generate_content.assert_called_once()

    @patch('google.genai.upload_file')
    def test_transcribe_audio_with_prompt(self, mock_upload, gemini_service, sample_audio_file):
        """プロンプト指定での音声文字起こしテスト"""
        mock_file = Mock()
        mock_file.uri = "test_uri"
        mock_upload.return_value = mock_file
        
        mock_response = Mock()
        mock_response.text = "カスタムプロンプトでの文字起こし結果"
        gemini_service.model.generate_content.return_value = mock_response
        
        custom_prompt = "この音声を詳細に文字起こししてください"
        result = gemini_service.transcribe_audio(sample_audio_file, prompt=custom_prompt)
        
        assert result == "カスタムプロンプトでの文字起こし結果"

    @patch('google.genai.upload_file')
    def test_transcribe_audio_file_not_found(self, mock_upload, gemini_service):
        """存在しないファイルでのエラーテスト"""
        with pytest.raises(FileNotFoundError):
            gemini_service.transcribe_audio("nonexistent_file.wav")

    @patch('google.genai.upload_file')
    def test_transcribe_audio_api_error(self, mock_upload, gemini_service, sample_audio_file):
        """API呼び出しエラーテスト"""
        mock_upload.side_effect = Exception("API Error")
        
        with pytest.raises(APIError, match="Failed to transcribe audio"):
            gemini_service.transcribe_audio(sample_audio_file)

    def test_check_transcription_quality_high_quality(self, gemini_service):
        """高品質文字起こしの品質チェックテスト"""
        transcription = "これは非常に明確で詳細な文字起こし結果です。話者の意図が正確に伝わっています。"
        
        mock_response = Mock()
        mock_response.text = '{"confidence": 0.95, "issues": [], "overall_quality": "high"}'
        gemini_service.model.generate_content.return_value = mock_response
        
        result = gemini_service.check_transcription_quality(transcription)
        
        assert result["confidence"] == 0.95
        assert result["overall_quality"] == "high"
        assert len(result["issues"]) == 0

    def test_check_transcription_quality_with_duration(self, gemini_service):
        """音声長指定での品質チェックテスト"""
        transcription = "短い文字起こし"
        duration = 300.0  # 5分
        
        mock_response = Mock()
        mock_response.text = '{"confidence": 0.7, "issues": ["speaking_rate_too_fast"], "overall_quality": "medium"}'
        gemini_service.model.generate_content.return_value = mock_response
        
        result = gemini_service.check_transcription_quality(transcription, duration)
        
        assert result["confidence"] == 0.7
        assert "speaking_rate_too_fast" in result["issues"]

    def test_check_transcription_quality_api_error(self, gemini_service):
        """品質チェックAPIエラーテスト"""
        gemini_service.model.generate_content.side_effect = Exception("API Error")
        
        with pytest.raises(APIError, match="Failed to check transcription quality"):
            gemini_service.check_transcription_quality("test transcription")

    def test_generate_minutes_detailed(self, gemini_service):
        """詳細議事録生成テスト"""
        transcription = "会議の文字起こし内容です。重要な決定事項が含まれています。"
        
        mock_response = Mock()
        mock_response.text = """
        # 会議議事録
        
        ## 概要
        重要な決定事項について議論されました。
        
        ## 決定事項
        - 項目1: 承認
        - 項目2: 保留
        """
        gemini_service.model.generate_content.return_value = mock_response
        
        result = gemini_service.generate_minutes(transcription, format_type="detailed")
        
        assert "# 会議議事録" in result
        assert "## 概要" in result
        assert "## 決定事項" in result

    def test_generate_minutes_with_context(self, gemini_service):
        """コンテキスト指定での議事録生成テスト"""
        transcription = "プロジェクト進捗について議論"
        context = {
            "meeting_type": "進捗会議",
            "participants": ["田中", "佐藤", "鈴木"],
            "date": "2024-01-15"
        }
        
        mock_response = Mock()
        mock_response.text = "コンテキスト付き議事録"
        gemini_service.model.generate_content.return_value = mock_response
        
        result = gemini_service.generate_minutes(transcription, meeting_context=context)
        
        assert result == "コンテキスト付き議事録"

    def test_generate_minutes_summary_format(self, gemini_service):
        """サマリー形式での議事録生成テスト"""
        transcription = "長い会議の内容"
        
        mock_response = Mock()
        mock_response.text = "簡潔なサマリー"
        gemini_service.model.generate_content.return_value = mock_response
        
        result = gemini_service.generate_minutes(transcription, format_type="summary")
        
        assert result == "簡潔なサマリー"

    @patch('google.genai.upload_file')
    def test_analyze_video_content_brightness(self, mock_upload, gemini_service, sample_video_file):
        """動画明度解析テスト"""
        mock_file = Mock()
        mock_file.uri = "test_video_uri"
        mock_upload.return_value = mock_file
        
        mock_response = Mock()
        mock_response.text = '{"brightness_level": "dark", "confidence": 0.85, "recommendation": "audio_only"}'
        gemini_service.model.generate_content.return_value = mock_response
        
        result = gemini_service.analyze_video_content(sample_video_file, analysis_type="brightness")
        
        assert result["brightness_level"] == "dark"
        assert result["confidence"] == 0.85
        assert result["recommendation"] == "audio_only"

    @patch('google.genai.upload_file')
    def test_analyze_video_content_content_analysis(self, mock_upload, gemini_service, sample_video_file):
        """動画コンテンツ解析テスト"""
        mock_file = Mock()
        mock_upload.return_value = mock_file
        
        mock_response = Mock()
        mock_response.text = '{"content_type": "presentation", "has_slides": true, "speaker_visible": false}'
        gemini_service.model.generate_content.return_value = mock_response
        
        result = gemini_service.analyze_video_content(sample_video_file, analysis_type="content")
        
        assert result["content_type"] == "presentation"
        assert result["has_slides"] is True

    def test_estimate_confidence_high(self, gemini_service):
        """高信頼度テキストの信頼度推定テスト"""
        high_quality_text = "これは非常に明確で詳細な文章です。文法も正確で、内容も一貫しています。"
        
        confidence = gemini_service._estimate_confidence(high_quality_text)
        
        assert confidence >= 0.8

    def test_estimate_confidence_low(self, gemini_service):
        """低信頼度テキストの信頼度推定テスト"""
        low_quality_text = "あー、えーと、なんか、よくわからない、感じで、話してる"
        
        confidence = gemini_service._estimate_confidence(low_quality_text)
        
        assert confidence <= 0.6

    def test_calculate_speaking_rate_normal(self, gemini_service):
        """正常な話速計算テスト"""
        text = "これは約20文字のテスト文章です。"  # 20文字
        duration = 10.0  # 10秒
        
        rate = gemini_service._calculate_speaking_rate(text, duration)
        
        # 20文字 / 10秒 = 2文字/秒 = 120文字/分
        assert rate == 120.0

    def test_calculate_speaking_rate_no_duration(self, gemini_service):
        """音声長なしでの話速計算テスト"""
        text = "テスト文章"
        
        rate = gemini_service._calculate_speaking_rate(text, None)
        
        assert rate is None

    def test_get_model_info(self, gemini_service):
        """モデル情報取得テスト"""
        mock_model_info = {
            "name": "gemini-1.5-pro",
            "version": "1.5",
            "input_token_limit": 1000000
        }
        
        with patch.object(gemini_service, 'model') as mock_model:
            mock_model.get_model.return_value = mock_model_info
            
            info = gemini_service.get_model_info()
            
            assert info["name"] == "gemini-1.5-pro"
            assert "version" in info

    @pytest.mark.parametrize("language", ["ja", "en", "zh"])
    def test_transcribe_audio_different_languages(self, gemini_service, sample_audio_file, language):
        """異なる言語での文字起こしテスト"""
        with patch('google.genai.upload_file') as mock_upload:
            mock_file = Mock()
            mock_upload.return_value = mock_file
            
            mock_response = Mock()
            mock_response.text = f"Transcription in {language}"
            gemini_service.model.generate_content.return_value = mock_response
            
            result = gemini_service.transcribe_audio(sample_audio_file, language=language)
            
            assert f"Transcription in {language}" in result

    def test_transcribe_audio_retry_mechanism(self, gemini_service, sample_audio_file):
        """リトライ機能テスト"""
        with patch('google.genai.upload_file') as mock_upload:
            mock_file = Mock()
            mock_upload.return_value = mock_file
            
            # 最初の2回は失敗、3回目で成功
            gemini_service.model.generate_content.side_effect = [
                Exception("Temporary error"),
                Exception("Another error"),
                Mock(text="Success after retry")
            ]
            
            with patch('src.utils.retry_utils.api_call_with_retry') as mock_retry:
                mock_retry.return_value = "Success after retry"
                
                result = gemini_service.transcribe_audio(sample_audio_file)
                
                assert result == "Success after retry"

    def test_memory_cleanup_after_processing(self, gemini_service, sample_audio_file):
        """処理後のメモリクリーンアップテスト"""
        with patch('google.genai.upload_file') as mock_upload:
            mock_file = Mock()
            mock_upload.return_value = mock_file
            
            mock_response = Mock()
            mock_response.text = "Test result"
            gemini_service.model.generate_content.return_value = mock_response
            
            # ファイルサイズを記録
            initial_memory = gemini_service.__sizeof__()
            
            result = gemini_service.transcribe_audio(sample_audio_file)
            
            # メモリ使用量が大幅に増加していないことを確認
            final_memory = gemini_service.__sizeof__()
            assert final_memory - initial_memory < 1000000  # 1MB未満の増加

    def test_concurrent_requests_handling(self, gemini_service, sample_audio_file):
        """同時リクエスト処理テスト"""
        import threading
        import time
        
        results = []
        errors = []
        
        def transcribe_worker(file_path, worker_id):
            try:
                with patch('google.genai.upload_file') as mock_upload:
                    mock_file = Mock()
                    mock_upload.return_value = mock_file
                    
                    mock_response = Mock()
                    mock_response.text = f"Result from worker {worker_id}"
                    gemini_service.model.generate_content.return_value = mock_response
                    
                    result = gemini_service.transcribe_audio(file_path)
                    results.append(result)
            except Exception as e:
                errors.append(e)
        
        # 3つの並行リクエストを実行
        threads = []
        for i in range(3):
            thread = threading.Thread(target=transcribe_worker, args=(sample_audio_file, i))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # エラーが発生していないことを確認
        assert len(errors) == 0
        assert len(results) == 3