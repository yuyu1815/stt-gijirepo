"""
文字起こしドメインモデルのテスト

このモジュールは、ドメイン層の文字起こしモデル（TranscriptionResult, TranscriptionSegment, Speaker）の機能をテストします。
"""
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.domain.transcription import (
    TranscriptionResult, TranscriptionSegment, TranscriptionStatus,
    Speaker, HallucinationResult, HallucinationSeverity
)


class TestSpeaker(unittest.TestCase):
    """Speakerクラスのテストクラス"""

    def test_create_speaker(self):
        """Speakerの作成をテスト"""
        # テスト実行
        speaker = Speaker(id="speaker1", name="山田太郎")
        
        # 検証
        self.assertEqual(speaker.id, "speaker1")
        self.assertEqual(speaker.name, "山田太郎")

    def test_create_speaker_id_only(self):
        """IDのみのSpeakerの作成をテスト"""
        # テスト実行
        speaker = Speaker(id="speaker1")
        
        # 検証
        self.assertEqual(speaker.id, "speaker1")
        self.assertEqual(speaker.name, "speaker1")  # nameはidと同じになる

    def test_speaker_equality(self):
        """Speaker同士の等価性をテスト"""
        # テスト実行
        speaker1 = Speaker(id="speaker1", name="山田太郎")
        speaker2 = Speaker(id="speaker1", name="山田太郎")
        speaker3 = Speaker(id="speaker2", name="鈴木次郎")
        
        # 検証
        self.assertEqual(speaker1, speaker2)
        self.assertNotEqual(speaker1, speaker3)


class TestTranscriptionSegment(unittest.TestCase):
    """TranscriptionSegmentクラスのテストクラス"""

    def test_create_transcription_segment(self):
        """TranscriptionSegmentの作成をテスト"""
        # テスト用のデータ
        speaker = Speaker(id="speaker1", name="山田太郎")
        
        # テスト実行
        segment = TranscriptionSegment(
            text="これはテストです。",
            start_time=10.5,
            end_time=15.0,
            speaker=speaker
        )
        
        # 検証
        self.assertEqual(segment.text, "これはテストです。")
        self.assertEqual(segment.start_time, 10.5)
        self.assertEqual(segment.end_time, 15.0)
        self.assertEqual(segment.speaker, speaker)
        self.assertEqual(segment.duration, 4.5)

    def test_create_transcription_segment_no_speaker(self):
        """話者なしのTranscriptionSegmentの作成をテスト"""
        # テスト実行
        segment = TranscriptionSegment(
            text="これはテストです。",
            start_time=10.5,
            end_time=15.0
        )
        
        # 検証
        self.assertEqual(segment.text, "これはテストです。")
        self.assertEqual(segment.start_time, 10.5)
        self.assertEqual(segment.end_time, 15.0)
        self.assertIsNone(segment.speaker)
        self.assertEqual(segment.duration, 4.5)

    def test_duration(self):
        """セグメント期間の計算をテスト"""
        # テスト実行
        segment = TranscriptionSegment(
            text="これはテストです。",
            start_time=30.0,
            end_time=45.5
        )
        
        # 検証
        self.assertEqual(segment.duration, 15.5)

    def test_word_count(self):
        """単語数の計算をテスト"""
        # テスト実行
        segment = TranscriptionSegment(
            text="これは テスト です。",
            start_time=10.5,
            end_time=15.0
        )
        
        # 検証
        self.assertEqual(segment.word_count, 3)  # 空白で分割して3単語


class TestHallucinationResult(unittest.TestCase):
    """HallucinationResultクラスのテストクラス"""

    def test_create_hallucination_result(self):
        """HallucinationResultの作成をテスト"""
        # テスト実行
        result = HallucinationResult(
            text="これは幻覚です。",
            severity=HallucinationSeverity.HIGH,
            confidence=0.85,
            explanation="高い確率で幻覚と判断されました。"
        )
        
        # 検証
        self.assertEqual(result.text, "これは幻覚です。")
        self.assertEqual(result.severity, HallucinationSeverity.HIGH)
        self.assertEqual(result.confidence, 0.85)
        self.assertEqual(result.explanation, "高い確率で幻覚と判断されました。")

    def test_create_hallucination_result_default_values(self):
        """デフォルト値でのHallucinationResultの作成をテスト"""
        # テスト実行
        result = HallucinationResult(
            text="これは幻覚です。"
        )
        
        # 検証
        self.assertEqual(result.text, "これは幻覚です。")
        self.assertEqual(result.severity, HallucinationSeverity.UNKNOWN)
        self.assertEqual(result.confidence, 0.0)
        self.assertIsNone(result.explanation)

    def test_is_hallucination(self):
        """幻覚判定をテスト"""
        # テスト実行
        result_high = HallucinationResult(
            text="これは幻覚です。",
            severity=HallucinationSeverity.HIGH
        )
        result_medium = HallucinationResult(
            text="これは幻覚かもしれません。",
            severity=HallucinationSeverity.MEDIUM
        )
        result_low = HallucinationResult(
            text="これは幻覚ではないでしょう。",
            severity=HallucinationSeverity.LOW
        )
        result_none = HallucinationResult(
            text="これは幻覚ではありません。",
            severity=HallucinationSeverity.NONE
        )
        
        # 検証
        self.assertTrue(result_high.is_hallucination)
        self.assertTrue(result_medium.is_hallucination)
        self.assertFalse(result_low.is_hallucination)
        self.assertFalse(result_none.is_hallucination)


class TestTranscriptionResult(unittest.TestCase):
    """TranscriptionResultクラスのテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # テスト用のデータ
        self.source_file = Path("test.mp3")
        self.speaker1 = Speaker(id="speaker1", name="山田太郎")
        self.speaker2 = Speaker(id="speaker2", name="鈴木次郎")
        
        self.segment1 = TranscriptionSegment(
            text="こんにちは、山田です。",
            start_time=0.0,
            end_time=5.0,
            speaker=self.speaker1
        )
        self.segment2 = TranscriptionSegment(
            text="こんにちは、鈴木です。",
            start_time=5.5,
            end_time=10.0,
            speaker=self.speaker2
        )
        self.segment3 = TranscriptionSegment(
            text="今日はいい天気ですね。",
            start_time=10.5,
            end_time=15.0,
            speaker=self.speaker1
        )

    def test_create_transcription_result(self):
        """TranscriptionResultの作成をテスト"""
        # テスト実行
        result = TranscriptionResult(
            source_file=self.source_file,
            status=TranscriptionStatus.COMPLETED,
            segments=[self.segment1, self.segment2, self.segment3]
        )
        
        # 検証
        self.assertEqual(result.source_file, self.source_file)
        self.assertEqual(result.status, TranscriptionStatus.COMPLETED)
        self.assertEqual(len(result.segments), 3)
        self.assertEqual(result.segments[0], self.segment1)
        self.assertEqual(result.segments[1], self.segment2)
        self.assertEqual(result.segments[2], self.segment3)
        self.assertTrue(result.is_completed)

    def test_create_transcription_result_in_progress(self):
        """進行中のTranscriptionResultの作成をテスト"""
        # テスト実行
        result = TranscriptionResult(
            source_file=self.source_file,
            status=TranscriptionStatus.IN_PROGRESS
        )
        
        # 検証
        self.assertEqual(result.source_file, self.source_file)
        self.assertEqual(result.status, TranscriptionStatus.IN_PROGRESS)
        self.assertEqual(len(result.segments), 0)
        self.assertFalse(result.is_completed)

    def test_add_segment(self):
        """セグメントの追加をテスト"""
        # テスト用のデータ
        result = TranscriptionResult(
            source_file=self.source_file,
            status=TranscriptionStatus.IN_PROGRESS
        )
        
        # テスト実行
        result.add_segment(self.segment1)
        
        # 検証
        self.assertEqual(len(result.segments), 1)
        self.assertEqual(result.segments[0], self.segment1)

    def test_get_speakers(self):
        """話者の取得をテスト"""
        # テスト用のデータ
        result = TranscriptionResult(
            source_file=self.source_file,
            status=TranscriptionStatus.COMPLETED,
            segments=[self.segment1, self.segment2, self.segment3]
        )
        
        # テスト実行
        speakers = result.get_speakers()
        
        # 検証
        self.assertEqual(len(speakers), 2)
        self.assertIn(self.speaker1, speakers)
        self.assertIn(self.speaker2, speakers)

    def test_get_segments_by_speaker(self):
        """話者によるセグメントの取得をテスト"""
        # テスト用のデータ
        result = TranscriptionResult(
            source_file=self.source_file,
            status=TranscriptionStatus.COMPLETED,
            segments=[self.segment1, self.segment2, self.segment3]
        )
        
        # テスト実行
        segments = result.get_segments_by_speaker(self.speaker1)
        
        # 検証
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0], self.segment1)
        self.assertEqual(segments[1], self.segment3)

    def test_get_segments_by_time_range(self):
        """時間範囲によるセグメントの取得をテスト"""
        # テスト用のデータ
        result = TranscriptionResult(
            source_file=self.source_file,
            status=TranscriptionStatus.COMPLETED,
            segments=[self.segment1, self.segment2, self.segment3]
        )
        
        # テスト実行
        segments = result.get_segments_by_time_range(4.0, 12.0)
        
        # 検証
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0], self.segment1)  # 0.0-5.0
        self.assertEqual(segments[1], self.segment2)  # 5.5-10.0

    def test_full_text(self):
        """全テキストの取得をテスト"""
        # テスト用のデータ
        result = TranscriptionResult(
            source_file=self.source_file,
            status=TranscriptionStatus.COMPLETED,
            segments=[self.segment1, self.segment2, self.segment3]
        )
        
        # テスト実行
        text = result.full_text
        
        # 検証
        expected_text = "こんにちは、山田です。\nこんにちは、鈴木です。\n今日はいい天気ですね。"
        self.assertEqual(text, expected_text)

    def test_total_duration(self):
        """総時間の計算をテスト"""
        # テスト用のデータ
        result = TranscriptionResult(
            source_file=self.source_file,
            status=TranscriptionStatus.COMPLETED,
            segments=[self.segment1, self.segment2, self.segment3]
        )
        
        # テスト実行
        duration = result.total_duration
        
        # 検証
        # segment1: 0.0-5.0 (5.0秒)
        # segment2: 5.5-10.0 (4.5秒)
        # segment3: 10.5-15.0 (4.5秒)
        # 合計: 15.0秒 (最後のセグメントの終了時間)
        self.assertEqual(duration, 15.0)

    def test_word_count(self):
        """総単語数の計算をテスト"""
        # テスト用のデータ
        result = TranscriptionResult(
            source_file=self.source_file,
            status=TranscriptionStatus.COMPLETED,
            segments=[self.segment1, self.segment2, self.segment3]
        )
        
        # テスト実行
        word_count = result.word_count
        
        # 検証
        # segment1: "こんにちは、山田です。" (3単語)
        # segment2: "こんにちは、鈴木です。" (3単語)
        # segment3: "今日はいい天気ですね。" (4単語)
        # 合計: 10単語
        self.assertEqual(word_count, 10)


if __name__ == '__main__':
    unittest.main()