"""
議事録ドメインモデルのテスト

このモジュールは、ドメイン層の議事録モデル（Minutes, MinutesContent, MinutesTask, GlossaryItem）の機能をテストします。
"""
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime

from src.domain.minutes import (
    Minutes, MinutesContent, MinutesFormat, MinutesSection,
    MinutesHeading, MinutesTask, GlossaryItem
)
from src.domain.transcription import TranscriptionResult


class TestMinutesContent(unittest.TestCase):
    """MinutesContentクラスのテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        pass

    def test_create_minutes_content(self):
        """MinutesContentの作成をテスト"""
        # テスト実行
        content = MinutesContent()
        
        # 検証
        self.assertEqual(len(content.paragraphs), 0)
        self.assertEqual(len(content.headings), 0)
        self.assertEqual(len(content.tasks), 0)
        self.assertEqual(len(content.glossary), 0)
        self.assertEqual(len(content.images), 0)

    def test_add_paragraph(self):
        """段落の追加をテスト"""
        # テスト用のデータ
        content = MinutesContent()
        section = MinutesSection.SUMMARY
        paragraphs = ["これはテスト用の要約です。", "2つ目の段落です。"]
        
        # テスト実行
        content.add_paragraph(section, paragraphs)
        
        # 検証
        self.assertIn(section, content.paragraphs)
        self.assertEqual(len(content.paragraphs[section]), 2)
        self.assertEqual(content.paragraphs[section][0], "これはテスト用の要約です。")
        self.assertEqual(content.paragraphs[section][1], "2つ目の段落です。")

    def test_add_heading(self):
        """見出しの追加をテスト"""
        # テスト用のデータ
        content = MinutesContent()
        heading = MinutesHeading(text="テスト見出し", level=2)
        
        # テスト実行
        content.add_heading(heading)
        
        # 検証
        self.assertEqual(len(content.headings), 1)
        self.assertEqual(content.headings[0], heading)

    def test_add_task(self):
        """タスクの追加をテスト"""
        # テスト用のデータ
        content = MinutesContent()
        task = MinutesTask(description="テストタスク", assignee="山田")
        
        # テスト実行
        content.add_task(task)
        
        # 検証
        self.assertEqual(len(content.tasks), 1)
        self.assertEqual(content.tasks[0], task)

    def test_add_glossary_item(self):
        """用語集アイテムの追加をテスト"""
        # テスト用のデータ
        content = MinutesContent()
        item = GlossaryItem(term="テスト", definition="ソフトウェアの品質を確認するための活動")
        
        # テスト実行
        content.add_glossary_item(item)
        
        # 検証
        self.assertEqual(len(content.glossary), 1)
        self.assertEqual(content.glossary[0], item)

    def test_add_image(self):
        """画像の追加をテスト"""
        # テスト用のデータ
        content = MinutesContent()
        image = MagicMock()
        
        # テスト実行
        content.add_image(image)
        
        # 検証
        self.assertEqual(len(content.images), 1)
        self.assertEqual(content.images[0], image)


class TestMinutesHeading(unittest.TestCase):
    """MinutesHeadingクラスのテストクラス"""

    def test_create_minutes_heading(self):
        """MinutesHeadingの作成をテスト"""
        # テスト実行
        heading = MinutesHeading(text="テスト見出し", level=2)
        
        # 検証
        self.assertEqual(heading.text, "テスト見出し")
        self.assertEqual(heading.level, 2)

    def test_create_minutes_heading_invalid_level(self):
        """不正なレベルでのMinutesHeadingの作成をテスト"""
        # テスト実行と検証
        with self.assertRaises(ValueError):
            MinutesHeading(text="テスト見出し", level=7)  # レベルは1-6のみ有効


class TestMinutesTask(unittest.TestCase):
    """MinutesTaskクラスのテストクラス"""

    def test_create_minutes_task(self):
        """MinutesTaskの作成をテスト"""
        # テスト実行
        task = MinutesTask(description="テストタスク", assignee="山田")
        
        # 検証
        self.assertEqual(task.description, "テストタスク")
        self.assertEqual(task.assignee, "山田")
        self.assertIsNone(task.due_date)

    def test_create_minutes_task_with_due_date(self):
        """期限付きMinutesTaskの作成をテスト"""
        # テスト用のデータ
        due_date = datetime(2025, 12, 31)
        
        # テスト実行
        task = MinutesTask(description="テストタスク", assignee="山田", due_date=due_date)
        
        # 検証
        self.assertEqual(task.description, "テストタスク")
        self.assertEqual(task.assignee, "山田")
        self.assertEqual(task.due_date, due_date)


class TestGlossaryItem(unittest.TestCase):
    """GlossaryItemクラスのテストクラス"""

    def test_create_glossary_item(self):
        """GlossaryItemの作成をテスト"""
        # テスト実行
        item = GlossaryItem(term="テスト", definition="ソフトウェアの品質を確認するための活動")
        
        # 検証
        self.assertEqual(item.term, "テスト")
        self.assertEqual(item.definition, "ソフトウェアの品質を確認するための活動")


class TestMinutes(unittest.TestCase):
    """Minutesクラスのテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # トランスクリプション結果のモック
        self.transcription = MagicMock(spec=TranscriptionResult)
        self.transcription.source_file = Path("test.mp3")

    def test_create_minutes(self):
        """Minutesの作成をテスト"""
        # テスト用のデータ
        title = "テスト議事録"
        date = datetime.now()
        content = MinutesContent()
        
        # テスト実行
        minutes = Minutes(
            title=title,
            date=date,
            content=content,
            source_transcription=self.transcription,
            format=MinutesFormat.MARKDOWN
        )
        
        # 検証
        self.assertEqual(minutes.title, title)
        self.assertEqual(minutes.date, date)
        self.assertEqual(minutes.content, content)
        self.assertEqual(minutes.source_transcription, self.transcription)
        self.assertEqual(minutes.format, MinutesFormat.MARKDOWN)
        self.assertIsNone(minutes.lecturer)
        self.assertIsNone(minutes.subject)
        self.assertEqual(minutes.attendees, [])
        self.assertIsNone(minutes.output_path)

    def test_create_minutes_with_optional_fields(self):
        """オプションフィールド付きMinutesの作成をテスト"""
        # テスト用のデータ
        title = "テスト議事録"
        date = datetime.now()
        content = MinutesContent()
        lecturer = "山田教授"
        subject = "プログラミング入門"
        attendees = ["鈴木", "佐藤", "田中"]
        
        # テスト実行
        minutes = Minutes(
            title=title,
            date=date,
            content=content,
            source_transcription=self.transcription,
            format=MinutesFormat.MARKDOWN,
            lecturer=lecturer,
            subject=subject,
            attendees=attendees
        )
        
        # 検証
        self.assertEqual(minutes.title, title)
        self.assertEqual(minutes.date, date)
        self.assertEqual(minutes.content, content)
        self.assertEqual(minutes.source_transcription, self.transcription)
        self.assertEqual(minutes.format, MinutesFormat.MARKDOWN)
        self.assertEqual(minutes.lecturer, lecturer)
        self.assertEqual(minutes.subject, subject)
        self.assertEqual(minutes.attendees, attendees)
        self.assertIsNone(minutes.output_path)

    def test_add_paragraph(self):
        """段落の追加をテスト"""
        # テスト用のデータ
        minutes = Minutes(
            title="テスト議事録",
            date=datetime.now(),
            content=MinutesContent(),
            source_transcription=self.transcription,
            format=MinutesFormat.MARKDOWN
        )
        section = MinutesSection.SUMMARY
        paragraphs = ["これはテスト用の要約です。"]
        
        # テスト実行
        minutes.add_paragraph(section, paragraphs)
        
        # 検証
        self.assertIn(section, minutes.content.paragraphs)
        self.assertEqual(minutes.content.paragraphs[section][0], "これはテスト用の要約です。")

    def test_add_heading(self):
        """見出しの追加をテスト"""
        # テスト用のデータ
        minutes = Minutes(
            title="テスト議事録",
            date=datetime.now(),
            content=MinutesContent(),
            source_transcription=self.transcription,
            format=MinutesFormat.MARKDOWN
        )
        heading = MinutesHeading(text="テスト見出し", level=2)
        
        # テスト実行
        minutes.add_heading(heading)
        
        # 検証
        self.assertEqual(len(minutes.content.headings), 1)
        self.assertEqual(minutes.content.headings[0], heading)

    def test_add_task(self):
        """タスクの追加をテスト"""
        # テスト用のデータ
        minutes = Minutes(
            title="テスト議事録",
            date=datetime.now(),
            content=MinutesContent(),
            source_transcription=self.transcription,
            format=MinutesFormat.MARKDOWN
        )
        task = MinutesTask(description="テストタスク", assignee="山田")
        
        # テスト実行
        minutes.add_task(task)
        
        # 検証
        self.assertEqual(len(minutes.content.tasks), 1)
        self.assertEqual(minutes.content.tasks[0], task)
        self.assertTrue(minutes.has_tasks)

    def test_add_glossary_item(self):
        """用語集アイテムの追加をテスト"""
        # テスト用のデータ
        minutes = Minutes(
            title="テスト議事録",
            date=datetime.now(),
            content=MinutesContent(),
            source_transcription=self.transcription,
            format=MinutesFormat.MARKDOWN
        )
        item = GlossaryItem(term="テスト", definition="ソフトウェアの品質を確認するための活動")
        
        # テスト実行
        minutes.add_glossary_item(item)
        
        # 検証
        self.assertEqual(len(minutes.content.glossary), 1)
        self.assertEqual(minutes.content.glossary[0], item)
        self.assertTrue(minutes.has_glossary)

    def test_add_image(self):
        """画像の追加をテスト"""
        # テスト用のデータ
        minutes = Minutes(
            title="テスト議事録",
            date=datetime.now(),
            content=MinutesContent(),
            source_transcription=self.transcription,
            format=MinutesFormat.MARKDOWN
        )
        image = MagicMock()
        
        # テスト実行
        minutes.add_image(image)
        
        # 検証
        self.assertEqual(len(minutes.content.images), 1)
        self.assertEqual(minutes.content.images[0], image)
        self.assertTrue(minutes.has_images)


if __name__ == '__main__':
    unittest.main()