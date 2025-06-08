"""
議事録生成サービスのテスト

このモジュールは、議事録生成サービス（MinutesGeneratorService）の機能をテストします。
"""
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from pathlib import Path

from src.domain.media import MediaFile, ExtractedImage
from src.domain.minutes import Minutes, MinutesContent, MinutesFormat, MinutesSection
from src.domain.transcription import TranscriptionResult, TranscriptionStatus
from src.services.minutes import MinutesGeneratorService, minutes_generator_service


class TestMinutesGeneratorService(unittest.TestCase):
    """議事録生成サービスのテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # モックの設定
        self.config_patcher = patch('src.services.minutes.config_manager')
        self.mock_config = self.config_patcher.start()
        self.mock_config.get_api_key.return_value = "test_api_key"
        self.mock_config.get.return_value = 3  # max_retries, retry_delay, etc.
        self.mock_config.get_prompt_path.return_value = Path("test_prompt_path")

        self.logger_patcher = patch('src.services.minutes.logger')
        self.mock_logger = self.logger_patcher.start()

        self.storage_patcher = patch('src.services.minutes.storage_manager')
        self.mock_storage = self.storage_patcher.start()
        self.mock_storage.load_text.return_value = "テストプロンプト"
        self.mock_storage.get_output_dir.return_value = Path("test_output_dir")
        self.mock_storage.save_text.return_value = None

        self.parser_patcher = patch('src.services.minutes.minutes_parser_service')
        self.mock_parser = self.parser_patcher.start()
        
        # テスト用のサービスインスタンス
        self.service = MinutesGeneratorService()
        
        # テスト用のデータ
        self.test_file_path = Path("test_file.mp3")
        self.test_media_file = MediaFile(file_path=self.test_file_path)
        self.test_transcription = TranscriptionResult(
            source_file=self.test_file_path,
            status=TranscriptionStatus.COMPLETED,
            segments=[]
        )
        self.test_transcription.full_text = "これはテスト用の文字起こしテキストです。"

    def tearDown(self):
        """各テスト実行後のクリーンアップ"""
        self.config_patcher.stop()
        self.logger_patcher.stop()
        self.storage_patcher.stop()
        self.parser_patcher.stop()

    def test_initialize_minutes(self):
        """_initialize_minutes メソッドのテスト"""
        # テスト実行
        minutes = self.service._initialize_minutes(self.test_transcription, self.test_media_file)
        
        # 検証
        self.assertEqual(minutes.title, f"{self.test_file_path.stem} 議事録")
        self.assertIsInstance(minutes.date, datetime)
        self.assertIsInstance(minutes.content, MinutesContent)
        self.assertEqual(minutes.source_transcription, self.test_transcription)
        self.assertEqual(minutes.format, MinutesFormat.MARKDOWN)

    def test_extract_date_from_filename(self):
        """_extract_date_from_filename メソッドのテスト"""
        # テスト実行
        date = self.service._extract_date_from_filename(self.test_file_path)
        
        # 検証
        self.assertIsInstance(date, datetime)

    @patch('src.services.minutes.genai')
    def test_generate_minutes_content(self, mock_genai):
        """_generate_minutes_content メソッドのテスト"""
        # モックの設定
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "テスト議事録内容"
        mock_client.models.generate_content.return_value = mock_response
        
        # テスト用のデータ
        minutes = Minutes(
            title="テスト議事録",
            date=datetime.now(),
            content=MinutesContent(),
            source_transcription=self.test_transcription,
            format=MinutesFormat.MARKDOWN
        )
        
        # モックの戻り値を設定
        self.mock_parser.parse_minutes_content.return_value = minutes
        
        # テスト実行
        result = self.service._generate_minutes_content(minutes, self.test_transcription)
        
        # 検証
        self.assertEqual(result, minutes)
        self.mock_parser.parse_minutes_content.assert_called_once()

    def test_load_minutes_prompt(self):
        """_load_minutes_prompt メソッドのテスト"""
        # テスト実行
        prompt = self.service._load_minutes_prompt()
        
        # 検証
        self.assertEqual(prompt, "テストプロンプト")
        self.mock_storage.load_text.assert_called_once()

    @patch('src.services.minutes.genai')
    def test_generate_with_gemini(self, mock_genai):
        """_generate_with_gemini メソッドのテスト"""
        # モックの設定
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "テスト議事録内容"
        mock_client.models.generate_content.return_value = mock_response
        
        # テスト実行
        result = self.service._generate_with_gemini(self.test_transcription, "テストプロンプト")
        
        # 検証
        self.assertEqual(result, "テスト議事録内容")
        mock_client.models.generate_content.assert_called_once()

    def test_save_minutes(self):
        """_save_minutes メソッドのテスト"""
        # テスト用のデータ
        minutes = Minutes(
            title="テスト議事録",
            date=datetime.now(),
            content=MinutesContent(),
            source_transcription=self.test_transcription,
            format=MinutesFormat.MARKDOWN
        )
        
        # テスト実行
        result = self.service._save_minutes(minutes)
        
        # 検証
        self.assertEqual(result, Path("test_output_dir") / f"{self.test_file_path.stem}_minutes.md")
        self.mock_storage.save_text.assert_called_once()

    def test_format_minutes_for_output(self):
        """_format_minutes_for_output メソッドのテスト"""
        # テスト用のデータ
        minutes = Minutes(
            title="テスト議事録",
            date=datetime.now(),
            content=MinutesContent(),
            source_transcription=self.test_transcription,
            format=MinutesFormat.MARKDOWN
        )
        minutes.add_paragraph(MinutesSection.SUMMARY, ["これはテスト用の要約です。"])
        
        # テスト実行
        result = self.service._format_minutes_for_output(minutes)
        
        # 検証
        self.assertIn("# テスト議事録", result)
        self.assertIn("## 要約", result)
        self.assertIn("これはテスト用の要約です。", result)

    def test_check_rate_limit(self):
        """_check_rate_limit メソッドのテスト"""
        # テスト用のデータ
        self.service.requests_per_minute = 5
        self.service.request_timestamps = []
        
        # テスト実行
        self.service._check_rate_limit()
        
        # 検証
        self.assertEqual(len(self.service.request_timestamps), 0)

    def test_format_time(self):
        """_format_time メソッドのテスト"""
        # テスト実行
        result = self.service._format_time(3661.5)  # 1時間1分1.5秒
        
        # 検証
        self.assertEqual(result, "01:01:01")

    @patch('src.services.minutes.genai')
    def test_generate_summary(self, mock_genai):
        """generate_summary メソッドのテスト"""
        # モックの設定
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "テスト要約"
        mock_client.models.generate_content.return_value = mock_response
        
        # テスト実行
        result = self.service.generate_summary(self.test_transcription)
        
        # 検証
        self.assertEqual(result, "テスト要約")
        mock_client.models.generate_content.assert_called_once()

    def test_load_summary_prompt(self):
        """_load_summary_prompt メソッドのテスト"""
        # テスト実行
        prompt = self.service._load_summary_prompt()
        
        # 検証
        self.assertEqual(prompt, "テストプロンプト")
        self.mock_storage.load_text.assert_called_once()

    @patch('src.services.minutes.genai')
    def test_generate_summary_with_gemini(self, mock_genai):
        """_generate_summary_with_gemini メソッドのテスト"""
        # モックの設定
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "テスト要約"
        mock_client.models.generate_content.return_value = mock_response
        
        # テスト実行
        result = self.service._generate_summary_with_gemini(self.test_transcription, "テストプロンプト")
        
        # 検証
        self.assertEqual(result, "テスト要約")
        mock_client.models.generate_content.assert_called_once()


if __name__ == '__main__':
    unittest.main()