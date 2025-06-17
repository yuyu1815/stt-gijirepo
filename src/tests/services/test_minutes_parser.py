"""
議事録パーサーサービスのテスト

このモジュールは、議事録パーサーサービス（MinutesParserService）の機能をテストします。
"""
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from pathlib import Path

from src.domain.minutes import (
    GlossaryItem, Minutes, MinutesContent, MinutesFormat, 
    MinutesHeading, MinutesSection, MinutesTask
)
from src.domain.transcription import TranscriptionResult, TranscriptionStatus
from src.services.minutes_parser import MinutesParserService, minutes_parser_service


class TestMinutesParserService(unittest.TestCase):
    """議事録パーサーサービスのテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # モックの設定
        self.logger_patcher = patch('src.services.minutes_parser.logger')
        self.mock_logger = self.logger_patcher.start()
        
        # テスト用のサービスインスタンス
        self.service = MinutesParserService()
        
        # テスト用のデータ
        self.test_file_path = Path("test_file.mp3")
        self.test_transcription = TranscriptionResult(
            source_file=self.test_file_path,
            status=TranscriptionStatus.COMPLETED,
            segments=[]
        )
        self.test_minutes = Minutes(
            title="テスト議事録",
            date=datetime.now(),
            content=MinutesContent(),
            source_transcription=self.test_transcription,
            format=MinutesFormat.MARKDOWN
        )
        
        # テスト用の議事録内容
        self.test_content = """# テスト議事録
日付: 2025-06-08

## 要約
これはテスト用の要約です。

## 議事内容
### 1. はじめに
- これはテスト用の議事内容です。
- テスト目的で作成されました。

### 2. 主要な議題
- 議題1: テスト議題
- 議題2: サンプル議題

## 重要ポイント
- 重要ポイント1: これは重要なポイントです。
- 重要ポイント2: これも重要なポイントです。

## タスク・宿題
- タスク1: これはテスト用のタスクです。担当: 山田
- タスク2: これも別のタスクです。期限: 2025-12-31

## 用語集
- テスト: ソフトウェアの品質を確認するための活動
- 議事録: 会議の内容を記録したもの
"""

    def tearDown(self):
        """各テスト実行後のクリーンアップ"""
        self.logger_patcher.stop()

    def test_parse_minutes_content(self):
        """parse_minutes_content メソッドのテスト"""
        # テスト実行
        result = self.service.parse_minutes_content(self.test_minutes, self.test_content)
        
        # 検証
        self.assertEqual(result, self.test_minutes)
        self.assertTrue(MinutesSection.SUMMARY in result.content.paragraphs)
        self.assertTrue(MinutesSection.CONTENT in result.content.paragraphs)
        self.assertTrue(MinutesSection.IMPORTANT_POINTS in result.content.paragraphs)
        self.assertEqual(len(result.content.tasks), 2)
        self.assertEqual(len(result.content.glossary), 2)

    def test_extract_sections(self):
        """_extract_sections メソッドのテスト"""
        # テスト実行
        sections = self.service._extract_sections(self.test_content)
        
        # 検証
        self.assertIn("要約", sections)
        self.assertIn("議事内容", sections)
        self.assertIn("重要ポイント", sections)
        self.assertIn("タスク・宿題", sections)
        self.assertIn("用語集", sections)
        self.assertIn("これはテスト用の要約です。", sections["要約"])

    def test_extract_headings(self):
        """_extract_headings メソッドのテスト"""
        # テスト実行
        headings = self.service._extract_headings(self.test_content)
        
        # 検証
        self.assertEqual(len(headings), 8)  # 全見出し数
        self.assertEqual(headings[0].text, "テスト議事録")
        self.assertEqual(headings[0].level, 1)
        self.assertEqual(headings[1].text, "要約")
        self.assertEqual(headings[1].level, 2)

    def test_extract_tasks(self):
        """_extract_tasks メソッドのテスト"""
        # テスト実行
        tasks = self.service._extract_tasks(self.test_content)
        
        # 検証
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].description, "タスク1: これはテスト用のタスクです。担当: 山田")
        self.assertEqual(tasks[0].assignee, "山田")
        self.assertIsNone(tasks[0].due_date)
        self.assertEqual(tasks[1].description, "タスク2: これも別のタスクです。期限: 2025-12-31")
        self.assertIsNone(tasks[1].assignee)
        self.assertEqual(tasks[1].due_date.year, 2025)
        self.assertEqual(tasks[1].due_date.month, 12)
        self.assertEqual(tasks[1].due_date.day, 31)

    def test_extract_glossary(self):
        """_extract_glossary メソッドのテスト"""
        # テスト実行
        glossary_items = self.service._extract_glossary(self.test_content)
        
        # 検証
        self.assertEqual(len(glossary_items), 2)
        self.assertEqual(glossary_items[0].term, "テスト")
        self.assertEqual(glossary_items[0].definition, "ソフトウェアの品質を確認するための活動")
        self.assertEqual(glossary_items[1].term, "議事録")
        self.assertEqual(glossary_items[1].definition, "会議の内容を記録したもの")

    def test_extract_sections_empty(self):
        """_extract_sections メソッドの空入力テスト"""
        # テスト実行
        sections = self.service._extract_sections("")
        
        # 検証
        self.assertEqual(len(sections), 0)

    def test_extract_headings_empty(self):
        """_extract_headings メソッドの空入力テスト"""
        # テスト実行
        headings = self.service._extract_headings("")
        
        # 検証
        self.assertEqual(len(headings), 0)

    def test_extract_tasks_empty(self):
        """_extract_tasks メソッドの空入力テスト"""
        # テスト実行
        tasks = self.service._extract_tasks("")
        
        # 検証
        self.assertEqual(len(tasks), 0)

    def test_extract_glossary_empty(self):
        """_extract_glossary メソッドの空入力テスト"""
        # テスト実行
        glossary_items = self.service._extract_glossary("")
        
        # 検証
        self.assertEqual(len(glossary_items), 0)

    def test_extract_tasks_invalid_date(self):
        """_extract_tasks メソッドの不正な日付テスト"""
        # テスト用の不正な日付を含むコンテンツ
        invalid_date_content = """
## タスク・宿題
- タスク1: これはテスト用のタスクです。期限: 2025-13-32
"""
        
        # テスト実行
        tasks = self.service._extract_tasks(invalid_date_content)
        
        # 検証
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].description, "タスク1: これはテスト用のタスクです。期限: 2025-13-32")
        self.assertIsNone(tasks[0].due_date)  # 不正な日付はNoneになる

    def test_parse_minutes_content_with_all_sections(self):
        """parse_minutes_content メソッドの全セクション含むテスト"""
        # テスト用のデータ
        minutes = Minutes(
            title="テスト議事録",
            date=datetime.now(),
            content=MinutesContent(),
            source_transcription=self.test_transcription,
            format=MinutesFormat.MARKDOWN
        )
        
        # テスト実行
        result = self.service.parse_minutes_content(minutes, self.test_content)
        
        # 検証
        self.assertEqual(result, minutes)
        self.assertTrue(MinutesSection.SUMMARY in result.content.paragraphs)
        self.assertTrue(MinutesSection.CONTENT in result.content.paragraphs)
        self.assertTrue(MinutesSection.IMPORTANT_POINTS in result.content.paragraphs)
        self.assertEqual(len(result.content.tasks), 2)
        self.assertEqual(len(result.content.glossary), 2)
        self.assertEqual(len(result.content.headings), 8)


if __name__ == '__main__':
    unittest.main()