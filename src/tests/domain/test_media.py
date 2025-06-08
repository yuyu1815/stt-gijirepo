"""
メディアドメインモデルのテスト

このモジュールは、ドメイン層のメディアモデル（MediaFile, MediaChunk, ExtractedImage）の機能をテストします。
"""
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import os

from src.domain.media import MediaFile, MediaChunk, ExtractedImage


class TestMediaFile(unittest.TestCase):
    """MediaFileクラスのテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # ファイル存在チェックのモック
        self.path_exists_patcher = patch('pathlib.Path.exists')
        self.mock_path_exists = self.path_exists_patcher.start()
        self.mock_path_exists.return_value = True
        
        # ファイルサイズのモック
        self.path_stat_patcher = patch('pathlib.Path.stat')
        self.mock_path_stat = self.path_stat_patcher.start()
        mock_stat = MagicMock()
        mock_stat.st_size = 1024 * 1024 * 10  # 10MB
        self.mock_path_stat.return_value = mock_stat

    def tearDown(self):
        """各テスト実行後のクリーンアップ"""
        self.path_exists_patcher.stop()
        self.path_stat_patcher.stop()

    def test_create_media_file(self):
        """MediaFileの作成をテスト"""
        # テスト実行
        media_file = MediaFile(file_path=Path("test.mp3"))
        
        # 検証
        self.assertEqual(media_file.file_path, Path("test.mp3"))
        self.assertEqual(media_file.file_size, 1024 * 1024 * 10)
        self.assertTrue(media_file.exists)
        self.assertFalse(media_file.is_video)
        self.assertFalse(media_file.is_long_media)
        self.assertEqual(len(media_file.chunks), 0)

    def test_create_media_file_non_existing(self):
        """存在しないファイルでのMediaFileの作成をテスト"""
        # モックの設定
        self.mock_path_exists.return_value = False
        
        # テスト実行と検証
        with self.assertRaises(FileNotFoundError):
            MediaFile(file_path=Path("non_existing.mp3"))

    def test_is_video(self):
        """動画ファイル判定をテスト"""
        # テスト実行
        media_file_mp4 = MediaFile(file_path=Path("test.mp4"))
        media_file_avi = MediaFile(file_path=Path("test.avi"))
        media_file_mp3 = MediaFile(file_path=Path("test.mp3"))
        
        # 検証
        self.assertTrue(media_file_mp4.is_video)
        self.assertTrue(media_file_avi.is_video)
        self.assertFalse(media_file_mp3.is_video)

    def test_is_long_media(self):
        """長時間メディア判定をテスト"""
        # モックの設定
        mock_stat_large = MagicMock()
        mock_stat_large.st_size = 1024 * 1024 * 100  # 100MB
        self.mock_path_stat.return_value = mock_stat_large
        
        # テスト実行
        media_file = MediaFile(file_path=Path("test.mp3"), long_media_threshold_mb=50)
        
        # 検証
        self.assertTrue(media_file.is_long_media)

    def test_add_chunk(self):
        """チャンクの追加をテスト"""
        # テスト用のデータ
        media_file = MediaFile(file_path=Path("test.mp3"))
        chunk = MediaChunk(
            file_path=Path("chunk_0.mp3"),
            index=0,
            start_time=0.0,
            end_time=60.0,
            parent_file=media_file
        )
        
        # テスト実行
        media_file.add_chunk(chunk)
        
        # 検証
        self.assertEqual(len(media_file.chunks), 1)
        self.assertEqual(media_file.chunks[0], chunk)
        self.assertTrue(media_file.has_chunks)

    def test_get_chunk_by_index(self):
        """インデックスによるチャンク取得をテスト"""
        # テスト用のデータ
        media_file = MediaFile(file_path=Path("test.mp3"))
        chunk0 = MediaChunk(
            file_path=Path("chunk_0.mp3"),
            index=0,
            start_time=0.0,
            end_time=60.0,
            parent_file=media_file
        )
        chunk1 = MediaChunk(
            file_path=Path("chunk_1.mp3"),
            index=1,
            start_time=60.0,
            end_time=120.0,
            parent_file=media_file
        )
        media_file.add_chunk(chunk0)
        media_file.add_chunk(chunk1)
        
        # テスト実行
        result = media_file.get_chunk_by_index(1)
        
        # 検証
        self.assertEqual(result, chunk1)

    def test_get_chunk_by_index_not_found(self):
        """存在しないインデックスによるチャンク取得をテスト"""
        # テスト用のデータ
        media_file = MediaFile(file_path=Path("test.mp3"))
        
        # テスト実行
        result = media_file.get_chunk_by_index(0)
        
        # 検証
        self.assertIsNone(result)


class TestMediaChunk(unittest.TestCase):
    """MediaChunkクラスのテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # ファイル存在チェックのモック
        self.path_exists_patcher = patch('pathlib.Path.exists')
        self.mock_path_exists = self.path_exists_patcher.start()
        self.mock_path_exists.return_value = True
        
        # 親ファイルのモック
        self.parent_file = MagicMock()
        self.parent_file.file_path = Path("test.mp3")

    def tearDown(self):
        """各テスト実行後のクリーンアップ"""
        self.path_exists_patcher.stop()

    def test_create_media_chunk(self):
        """MediaChunkの作成をテスト"""
        # テスト実行
        chunk = MediaChunk(
            file_path=Path("chunk_0.mp3"),
            index=0,
            start_time=0.0,
            end_time=60.0,
            parent_file=self.parent_file
        )
        
        # 検証
        self.assertEqual(chunk.file_path, Path("chunk_0.mp3"))
        self.assertEqual(chunk.index, 0)
        self.assertEqual(chunk.start_time, 0.0)
        self.assertEqual(chunk.end_time, 60.0)
        self.assertEqual(chunk.parent_file, self.parent_file)
        self.assertEqual(chunk.duration, 60.0)

    def test_create_media_chunk_non_existing(self):
        """存在しないファイルでのMediaChunkの作成をテスト"""
        # モックの設定
        self.mock_path_exists.return_value = False
        
        # テスト実行と検証
        with self.assertRaises(FileNotFoundError):
            MediaChunk(
                file_path=Path("non_existing.mp3"),
                index=0,
                start_time=0.0,
                end_time=60.0,
                parent_file=self.parent_file
            )

    def test_duration(self):
        """チャンク期間の計算をテスト"""
        # テスト実行
        chunk = MediaChunk(
            file_path=Path("chunk_0.mp3"),
            index=0,
            start_time=30.0,
            end_time=120.0,
            parent_file=self.parent_file
        )
        
        # 検証
        self.assertEqual(chunk.duration, 90.0)


class TestExtractedImage(unittest.TestCase):
    """ExtractedImageクラスのテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # ファイル存在チェックのモック
        self.path_exists_patcher = patch('pathlib.Path.exists')
        self.mock_path_exists = self.path_exists_patcher.start()
        self.mock_path_exists.return_value = True
        
        # 親ファイルのモック
        self.parent_file = MagicMock()
        self.parent_file.file_path = Path("test.mp4")

    def tearDown(self):
        """各テスト実行後のクリーンアップ"""
        self.path_exists_patcher.stop()

    def test_create_extracted_image(self):
        """ExtractedImageの作成をテスト"""
        # テスト実行
        image = ExtractedImage(
            file_path=Path("screenshot.jpg"),
            timestamp=60.0,
            parent_file=self.parent_file,
            description="テストスクリーンショット"
        )
        
        # 検証
        self.assertEqual(image.file_path, Path("screenshot.jpg"))
        self.assertEqual(image.timestamp, 60.0)
        self.assertEqual(image.parent_file, self.parent_file)
        self.assertEqual(image.description, "テストスクリーンショット")

    def test_create_extracted_image_non_existing(self):
        """存在しないファイルでのExtractedImageの作成をテスト"""
        # モックの設定
        self.mock_path_exists.return_value = False
        
        # テスト実行と検証
        with self.assertRaises(FileNotFoundError):
            ExtractedImage(
                file_path=Path("non_existing.jpg"),
                timestamp=60.0,
                parent_file=self.parent_file
            )

    def test_formatted_timestamp(self):
        """フォーマット済みタイムスタンプの取得をテスト"""
        # テスト実行
        image = ExtractedImage(
            file_path=Path("screenshot.jpg"),
            timestamp=3661.0,  # 1時間1分1秒
            parent_file=self.parent_file
        )
        
        # 検証
        self.assertEqual(image.formatted_timestamp, "01:01:01")


if __name__ == '__main__':
    unittest.main()