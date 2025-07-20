"""
STT議事録システム - 品質チェックノードテスト

quality_check.pyノードのテストケース
"""

import pytest
import re
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.workflows.nodes.quality_check import (
    quality_check_node,
    _perform_basic_quality_check,
    _detect_hallucination,
    _check_repetition_patterns,
    _check_sentence_structure,
    _check_terminology,
    _calculate_text_similarity,
    _combine_quality_results,
    _generate_quality_summary,
    _generate_quality_warnings,
    _load_hallucination_check_prompt,
    _parse_hallucination_response,
    _create_empty_quality_result,
    _create_error_quality_result
)
from src.workflows.state import STTState
from src.utils.error_handling import QualityCheckError


class TestQualityCheckNode:
    """quality_check_node関数のテスト"""
    
    def create_test_state(self, **kwargs) -> STTState:
        """テスト用状態を作成"""
        default_state = {
            "session_id": "test_session",
            "timestamp": datetime.now(),
            "file_path": "/test/audio.wav",
            "original_filename": "audio.wav",
            "file_size": 1024,
            "settings": {
                "enable_quality_check": True,
                "enable_hallucination_check": True,
                "min_confidence_threshold": 0.7
            },
            "file_type": "audio",
            "mime_type": "audio/wav",
            "is_video_dark": None,
            "audio_duration": 120.0,
            "audio_sample_rate": 44100,
            "audio_channels": 2,
            "chunks": None,
            "chunk_durations": None,
            "processing_stage": "transcription",
            "transcription": "これは品質チェック用のテスト文字起こし結果です。内容は明確で理解しやすく、適切な長さを持っています。",
            "transcription_confidence": 0.8,
            "quality_check_result": None,
            "minutes": None,
            "summary": None,
            "class_info": None,
            "errors": [],
            "warnings": [],
            "processing_log": [],
            "performance_metrics": {},
            "upload_to_notion": False,
            "notion_database_id": None,
            "notion_page_id": None,
            "output_files": [],
            "final_status": "initialized"
        }
        default_state.update(kwargs)
        return STTState(**default_state)
    
    def test_quality_check_empty_transcription(self):
        """空の文字起こしの品質チェックテスト"""
        state = self.create_test_state(transcription="")
        result = quality_check_node(state)
        
        assert len(result["warnings"]) > 0
        assert "文字起こし結果が空" in result["warnings"][0]
        assert result["quality_check_result"]["overall_score"] == 0.0
        assert result["processing_stage"] == "quality_check"
    
    @patch('src.workflows.nodes.quality_check._perform_basic_quality_check')
    @patch('src.workflows.nodes.quality_check._detect_hallucination')
    @patch('src.workflows.nodes.quality_check._combine_quality_results')
    def test_quality_check_success(self, mock_combine, mock_hallucination, mock_basic):
        """品質チェック成功のテスト"""
        # モックの設定
        mock_basic.return_value = {
            "quality_score": 0.8,
            "issues": [],
            "metrics": {"word_count": 20},
            "suggestions": []
        }
        
        mock_hallucination.return_value = {
            "hallucination_score": 0.1,
            "detected_issues": [],
            "confidence": 0.9
        }
        
        mock_combine.return_value = {
            "overall_score": 0.85,
            "basic_quality": mock_basic.return_value,
            "hallucination_detection": mock_hallucination.return_value,
            "summary": "高品質な文字起こし結果"
        }
        
        state = self.create_test_state()
        result = quality_check_node(state)
        
        assert result["quality_check_result"]["overall_score"] == 0.85
        assert result["processing_stage"] == "quality_check"
        assert len(result["errors"]) == 0
        assert len(result["processing_log"]) > 0
        
        mock_basic.assert_called_once()
        mock_hallucination.assert_called_once()
        mock_combine.assert_called_once()
    
    @patch('src.workflows.nodes.quality_check._perform_basic_quality_check')
    def test_quality_check_hallucination_disabled(self, mock_basic):
        """ハルシネーション検出無効時のテスト"""
        mock_basic.return_value = {
            "quality_score": 0.7,
            "issues": [],
            "metrics": {"word_count": 15},
            "suggestions": []
        }
        
        state = self.create_test_state(
            settings={"enable_hallucination_check": False}
        )
        
        with patch('src.workflows.nodes.quality_check._detect_hallucination') as mock_hallucination:
            result = quality_check_node(state)
            
            # ハルシネーション検出が呼ばれないことを確認
            mock_hallucination.assert_not_called()
            assert result["quality_check_result"] is not None
    
    @patch('src.workflows.nodes.quality_check._perform_basic_quality_check')
    def test_quality_check_with_error(self, mock_basic):
        """品質チェックエラー時のテスト"""
        mock_basic.side_effect = Exception("品質チェック処理エラー")
        
        state = self.create_test_state()
        result = quality_check_node(state)
        
        assert len(result["errors"]) > 0
        assert "品質チェックエラー" in result["errors"][0]
        assert result["quality_check_result"]["overall_score"] == 0.0
        assert "error" in result["quality_check_result"]


class TestPerformBasicQualityCheck:
    """_perform_basic_quality_check関数のテスト"""
    
    def test_basic_quality_check_good_text(self):
        """高品質テキストの基本品質チェック"""
        good_text = """
        本日の会議では、プロジェクトの進捗について詳細に話し合いました。
        開発チームからは、予定通りに作業が進んでいるとの報告がありました。
        来週までに、テスト環境の構築を完了する予定です。
        品質保証チームとの連携も順調に進んでいます。
        """
        
        result = _perform_basic_quality_check(good_text)
        
        assert result["quality_score"] > 0.7
        assert result["metrics"]["word_count"] > 0
        assert result["metrics"]["character_count"] > 0
        assert len(result["issues"]) == 0
    
    def test_basic_quality_check_short_text(self):
        """短いテキストの基本品質チェック"""
        short_text = "短いテスト"
        
        result = _perform_basic_quality_check(short_text)
        
        assert result["quality_score"] < 0.8
        assert len(result["issues"]) > 0
        assert "短すぎます" in str(result["issues"])
        assert len(result["suggestions"]) > 0
    
    def test_basic_quality_check_repetitive_text(self):
        """反復的なテキストの基本品質チェック"""
        repetitive_text = "テスト テスト テスト テスト テスト テスト テスト テスト"
        
        result = _perform_basic_quality_check(repetitive_text)
        
        assert result["quality_score"] < 0.6
        assert len(result["issues"]) > 0
    
    def test_basic_quality_check_empty_text(self):
        """空テキストの基本品質チェック"""
        result = _perform_basic_quality_check("")
        
        assert result["quality_score"] == 0.0
        assert result["metrics"]["word_count"] == 0
        assert result["metrics"]["character_count"] == 0
        assert len(result["issues"]) > 0
    
    def test_basic_quality_check_metrics(self):
        """メトリクス計算のテスト"""
        test_text = "これは テスト用の 文章です。\n改行も 含まれています。"
        
        result = _perform_basic_quality_check(test_text)
        
        assert result["metrics"]["character_count"] == len(test_text)
        assert result["metrics"]["word_count"] == len(test_text.split())
        assert result["metrics"]["line_count"] == len(test_text.split('\n'))
        assert result["metrics"]["average_word_length"] > 0


class TestDetectHallucination:
    """_detect_hallucination関数のテスト"""
    
    @patch('src.workflows.nodes.quality_check._load_hallucination_check_prompt')
    @patch('src.workflows.nodes.quality_check.genai.Client')
    @patch('os.environ')
    def test_detect_hallucination_success(self, mock_env, mock_client_class, mock_load_prompt):
        """ハルシネーション検出成功のテスト"""
        mock_load_prompt.return_value = "ハルシネーションをチェックしてください"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.text = "ハルシネーション検出結果: スコア 0.1, 問題なし"
        mock_client.generate_content.return_value = mock_response
        
        settings = {"gemini_api_key": "test_key"}
        transcription = "これは正常な文字起こし結果です。"
        
        with patch('src.workflows.nodes.quality_check._parse_hallucination_response') as mock_parse:
            mock_parse.return_value = {
                "hallucination_score": 0.1,
                "detected_issues": [],
                "confidence": 0.9
            }
            
            result = _detect_hallucination(transcription, settings)
            
            assert result["hallucination_score"] == 0.1
            assert result["confidence"] == 0.9
            assert len(result["detected_issues"]) == 0
    
    def test_detect_hallucination_no_api_key(self):
        """APIキー未設定時のハルシネーション検出テスト"""
        settings = {}
        transcription = "テスト文字起こし"
        
        result = _detect_hallucination(transcription, settings)
        
        assert result["hallucination_score"] == 0.0
        assert result["confidence"] == 0.0
        assert "APIキーが設定されていません" in str(result.get("error", ""))
    
    @patch('src.workflows.nodes.quality_check.HAS_GEMINI', False)
    def test_detect_hallucination_no_gemini(self):
        """Gemini API利用不可時のテスト"""
        settings = {"gemini_api_key": "test_key"}
        transcription = "テスト文字起こし"
        
        result = _detect_hallucination(transcription, settings)
        
        assert result["hallucination_score"] == 0.0
        assert "Gemini APIが利用できません" in str(result.get("error", ""))


class TestCheckFunctions:
    """各種チェック関数のテスト"""
    
    def test_check_repetition_patterns_normal(self):
        """正常テキストの反復パターンチェック"""
        normal_text = "これは正常な文章です。内容に問題はありません。"
        issues = _check_repetition_patterns(normal_text)
        assert len(issues) == 0
    
    def test_check_repetition_patterns_repetitive(self):
        """反復的テキストの反復パターンチェック"""
        repetitive_text = "テスト テスト テスト テスト テスト"
        issues = _check_repetition_patterns(repetitive_text)
        assert len(issues) > 0
        assert "反復" in str(issues)
    
    def test_check_sentence_structure_good(self):
        """良い文構造のチェック"""
        good_text = "これは適切な文構造を持つ文章です。句読点も正しく使用されています。"
        issues = _check_sentence_structure(good_text)
        assert len(issues) == 0
    
    def test_check_sentence_structure_poor(self):
        """悪い文構造のチェック"""
        poor_text = "これは文構造が悪い文章です句読点がありません長すぎる文章になっています"
        issues = _check_sentence_structure(poor_text)
        assert len(issues) > 0
    
    def test_check_terminology_normal(self):
        """正常な専門用語チェック"""
        normal_text = "プロジェクトの進捗について話し合いました。"
        issues = _check_terminology(normal_text)
        assert len(issues) == 0
    
    def test_check_terminology_issues(self):
        """専門用語問題のチェック"""
        issue_text = "ひらがなばかりのぶんしょうです。かたかなもありません。"
        issues = _check_terminology(issue_text)
        # 実装によっては問題が検出される可能性
        assert isinstance(issues, list)


class TestTextSimilarity:
    """_calculate_text_similarity関数のテスト"""
    
    def test_identical_texts(self):
        """同一テキストの類似度テスト"""
        text = "これは同じテキストです"
        similarity = _calculate_text_similarity(text, text)
        assert similarity == 1.0
    
    def test_similar_texts(self):
        """類似テキストの類似度テスト"""
        text1 = "これはテストです"
        text2 = "これはテスト文章です"
        similarity = _calculate_text_similarity(text1, text2)
        assert 0.0 < similarity < 1.0
    
    def test_different_texts(self):
        """異なるテキストの類似度テスト"""
        text1 = "完全に異なる内容"
        text2 = "xyz123"
        similarity = _calculate_text_similarity(text1, text2)
        assert similarity < 0.5
    
    def test_empty_texts(self):
        """空テキストの類似度テスト"""
        similarity = _calculate_text_similarity("", "")
        assert similarity == 0.0
        
        similarity = _calculate_text_similarity("テスト", "")
        assert similarity == 0.0


class TestCombineQualityResults:
    """_combine_quality_results関数のテスト"""
    
    def test_combine_good_results(self):
        """良好な結果の統合テスト"""
        basic_result = {
            "quality_score": 0.8,
            "issues": [],
            "metrics": {"word_count": 50}
        }
        
        hallucination_result = {
            "hallucination_score": 0.1,
            "detected_issues": [],
            "confidence": 0.9
        }
        
        combined = _combine_quality_results(basic_result, hallucination_result)
        
        assert combined["overall_score"] > 0.7
        assert combined["basic_quality"] == basic_result
        assert combined["hallucination_detection"] == hallucination_result
        assert "timestamp" in combined
        assert "summary" in combined
    
    def test_combine_poor_results(self):
        """低品質結果の統合テスト"""
        basic_result = {
            "quality_score": 0.4,
            "issues": ["短すぎる"],
            "metrics": {"word_count": 5}
        }
        
        hallucination_result = {
            "hallucination_score": 0.8,
            "detected_issues": ["疑わしい内容"],
            "confidence": 0.3
        }
        
        combined = _combine_quality_results(basic_result, hallucination_result)
        
        assert combined["overall_score"] < 0.5
        assert len(combined["basic_quality"]["issues"]) > 0
        assert len(combined["hallucination_detection"]["detected_issues"]) > 0


class TestGenerateQualitySummary:
    """_generate_quality_summary関数のテスト"""
    
    def test_generate_high_quality_summary(self):
        """高品質サマリー生成のテスト"""
        basic_result = {"issues": []}
        hallucination_result = {"detected_issues": []}
        
        summary = _generate_quality_summary(0.9, basic_result, hallucination_result)
        
        assert "高品質" in summary
        assert "0.90" in summary
    
    def test_generate_low_quality_summary(self):
        """低品質サマリー生成のテスト"""
        basic_result = {"issues": ["問題1", "問題2"]}
        hallucination_result = {"detected_issues": ["ハルシネーション"]}
        
        summary = _generate_quality_summary(0.3, basic_result, hallucination_result)
        
        assert "要改善" in summary or "低品質" in summary
        assert "2件" in summary
        assert "1件" in summary


class TestLoadHallucinationPrompt:
    """_load_hallucination_check_prompt関数のテスト"""
    
    @patch('builtins.open', create=True)
    def test_load_prompt_success(self, mock_open):
        """プロンプト読み込み成功のテスト"""
        mock_content = "ハルシネーションをチェックしてください。\n正確性を重視してください。"
        mock_open.return_value.__enter__.return_value.read.return_value = mock_content
        
        result = _load_hallucination_check_prompt()
        
        assert result == mock_content
        mock_open.assert_called_once()
    
    @patch('builtins.open', side_effect=FileNotFoundError("File not found"))
    def test_load_prompt_file_not_found(self, mock_open):
        """プロンプトファイル未発見のテスト"""
        result = _load_hallucination_check_prompt()
        
        # デフォルトプロンプトが返される
        assert "ハルシネーション" in result
        assert len(result) > 0


class TestParseHallucinationResponse:
    """_parse_hallucination_response関数のテスト"""
    
    def test_parse_good_response(self):
        """良好な応答の解析テスト"""
        response_text = """
        ハルシネーション検出結果:
        スコア: 0.1
        信頼度: 0.9
        問題: なし
        """
        
        result = _parse_hallucination_response(response_text)
        
        assert result["hallucination_score"] <= 0.2
        assert result["confidence"] >= 0.8
        assert len(result["detected_issues"]) == 0
    
    def test_parse_poor_response(self):
        """問題のある応答の解析テスト"""
        response_text = """
        ハルシネーション検出結果:
        スコア: 0.8
        信頼度: 0.3
        問題: 疑わしい内容が検出されました
        """
        
        result = _parse_hallucination_response(response_text)
        
        assert result["hallucination_score"] >= 0.7
        assert result["confidence"] <= 0.4
        assert len(result["detected_issues"]) > 0
    
    def test_parse_invalid_response(self):
        """無効な応答の解析テスト"""
        invalid_response = "無効な応答形式です"
        
        result = _parse_hallucination_response(invalid_response)
        
        # デフォルト値が返される
        assert result["hallucination_score"] == 0.5
        assert result["confidence"] == 0.5
        assert isinstance(result["detected_issues"], list)


class TestCreateQualityResults:
    """品質結果作成関数のテスト"""
    
    def test_create_empty_quality_result(self):
        """空の品質結果作成のテスト"""
        result = _create_empty_quality_result()
        
        assert result["overall_score"] == 0.0
        assert result["basic_quality"]["quality_score"] == 0.0
        assert result["hallucination_detection"]["hallucination_score"] == 0.0
        assert "timestamp" in result
        assert "summary" in result
    
    def test_create_error_quality_result(self):
        """エラー品質結果作成のテスト"""
        error_message = "テストエラーメッセージ"
        result = _create_error_quality_result(error_message)
        
        assert result["overall_score"] == 0.0
        assert result["error"] == error_message
        assert "timestamp" in result
        assert "summary" in result


class TestQualityCheckIntegration:
    """品質チェック機能の統合テスト"""
    
    @patch('src.workflows.nodes.quality_check._detect_hallucination')
    def test_complete_quality_check_workflow(self, mock_hallucination):
        """完全な品質チェックワークフローのテスト"""
        mock_hallucination.return_value = {
            "hallucination_score": 0.2,
            "detected_issues": [],
            "confidence": 0.8
        }
        
        state = STTState(
            session_id="quality_integration_test",
            timestamp=datetime.now(),
            file_path="/test/quality_audio.wav",
            original_filename="quality_audio.wav",
            file_size=1024000,
            settings={
                "enable_quality_check": True,
                "enable_hallucination_check": True,
                "min_confidence_threshold": 0.7,
                "gemini_api_key": "test_key"
            },
            file_type="audio",
            mime_type="audio/wav",
            is_video_dark=None,
            audio_duration=300.0,
            audio_sample_rate=44100,
            audio_channels=2,
            chunks=None,
            chunk_durations=None,
            processing_stage="transcription",
            transcription="本日の会議では、プロジェクトの進捗について詳細に話し合いました。開発チームからは順調に作業が進んでいるとの報告がありました。来週までにテスト環境の構築を完了する予定です。",
            transcription_confidence=0.85,
            quality_check_result=None,
            minutes=None,
            summary=None,
            class_info=None,
            errors=[],
            warnings=[],
            processing_log=[],
            performance_metrics={},
            upload_to_notion=False,
            notion_database_id=None,
            notion_page_id=None,
            output_files=[],
            final_status="initialized"
        )
        
        result = quality_check_node(state)
        
        # 結果検証
        assert result["processing_stage"] == "quality_check"
        assert result["quality_check_result"] is not None
        assert result["quality_check_result"]["overall_score"] > 0.0
        assert len(result["errors"]) == 0
        assert len(result["processing_log"]) > 0
        assert "品質チェック完了" in result["processing_log"][-1]
    
    def test_quality_check_with_warnings(self):
        """警告付き品質チェックのテスト"""
        state = STTState(
            session_id="warning_test",
            timestamp=datetime.now(),
            file_path="/test/warning_audio.wav",
            original_filename="warning_audio.wav",
            file_size=1024,
            settings={
                "enable_quality_check": True,
                "enable_hallucination_check": False,
                "min_confidence_threshold": 0.8
            },
            file_type="audio",
            mime_type="audio/wav",
            is_video_dark=None,
            audio_duration=60.0,
            audio_sample_rate=44100,
            audio_channels=2,
            chunks=None,
            chunk_durations=None,
            processing_stage="transcription",
            transcription="短い文字起こし結果",  # 短いテキストで警告を発生させる
            transcription_confidence=0.6,  # 低い信頼度で警告を発生させる
            quality_check_result=None,
            minutes=None,
            summary=None,
            class_info=None,
            errors=[],
            warnings=[],
            processing_log=[],
            performance_metrics={},
            upload_to_notion=False,
            notion_database_id=None,
            notion_page_id=None,
            output_files=[],
            final_status="initialized"
        )
        
        result = quality_check_node(state)
        
        # 警告が生成されることを確認
        assert result["quality_check_result"]["overall_score"] < 0.8
        assert len(result["warnings"]) > 0 or len(result["quality_check_result"]["basic_quality"]["issues"]) > 0


if __name__ == "__main__":
    pytest.main([__file__])