"""
ストレージ管理のテスト

このモジュールは、インフラストラクチャ層のストレージ管理（StorageManager）の機能をテストします。
"""
import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import shutil
import tempfile
from pathlib import Path

from src.infrastructure.storage import StorageManager


class TestStorageManager(unittest.TestCase):
    """ストレージ管理のテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # 一時ディレクトリのモック
        self.temp_dir = MagicMock()
        self.temp_dir_patcher = patch('tempfile.mkdtemp', return_value='/tmp/test_dir')
        self.mock_temp_dir = self.temp_dir_patcher.start()
        
        # Pathのモック
        self.path_exists_patcher = patch('pathlib.Path.exists')
        self.mock_path_exists = self.path_exists_patcher.start()
        self.mock_path_exists.return_value = False
        
        self.path_mkdir_patcher = patch('pathlib.Path.mkdir')
        self.mock_path_mkdir = self.path_mkdir_patcher.start()
        
        # ファイル操作のモック
        self.open_patcher = patch('builtins.open', new_callable=mock_open)
        self.mock_open = self.open_patcher.start()
        
        self.shutil_patcher = patch('shutil.copy2')
        self.mock_shutil = self.shutil_patcher.start()
        
        # StorageManagerのインスタンス
        self.storage_manager = StorageManager()

    def tearDown(self):
        """各テスト実行後のクリーンアップ"""
        self.temp_dir_patcher.stop()
        self.path_exists_patcher.stop()
        self.path_mkdir_patcher.stop()
        self.open_patcher.stop()
        self.shutil_patcher.stop()

    def test_get_base_dir(self):
        """ベースディレクトリの取得をテスト"""
        # テスト実行
        base_dir = self.storage_manager.get_base_dir()
        
        # 検証
        self.assertIsInstance(base_dir, Path)

    def test_get_output_dir_existing(self):
        """既存の出力ディレクトリの取得をテスト"""
        # モックの設定
        self.mock_path_exists.return_value = True
        
        # テスト実行
        output_dir = self.storage_manager.get_output_dir("transcripts")
        
        # 検証
        self.assertIsInstance(output_dir, Path)
        self.mock_path_mkdir.assert_not_called()

    def test_get_output_dir_non_existing(self):
        """存在しない出力ディレクトリの取得をテスト"""
        # モックの設定
        self.mock_path_exists.return_value = False
        
        # テスト実行
        output_dir = self.storage_manager.get_output_dir("transcripts")
        
        # 検証
        self.assertIsInstance(output_dir, Path)
        self.mock_path_mkdir.assert_called_once()

    def test_get_temp_dir(self):
        """一時ディレクトリの取得をテスト"""
        # テスト実行
        temp_dir = self.storage_manager.get_temp_dir()
        
        # 検証
        self.assertEqual(temp_dir, Path('/tmp/test_dir'))
        self.mock_temp_dir.assert_called_once()

    def test_save_text(self):
        """テキストの保存をテスト"""
        # テスト実行
        path = self.storage_manager.save_text("テストテキスト", Path("test.txt"))
        
        # 検証
        self.mock_open.assert_called_once_with(Path("test.txt"), 'w', encoding='utf-8')
        self.mock_open().write.assert_called_once_with("テストテキスト")
        self.assertEqual(path, Path("test.txt"))

    def test_load_text(self):
        """テキストの読み込みをテスト"""
        # モックの設定
        self.mock_open().read.return_value = "テストテキスト"
        
        # テスト実行
        text = self.storage_manager.load_text(Path("test.txt"))
        
        # 検証
        self.mock_open.assert_called_once_with(Path("test.txt"), 'r', encoding='utf-8')
        self.mock_open().read.assert_called_once()
        self.assertEqual(text, "テストテキスト")

    def test_copy_file(self):
        """ファイルのコピーをテスト"""
        # テスト実行
        dest_path = self.storage_manager.copy_file(Path("source.txt"), Path("dest.txt"))
        
        # 検証
        self.mock_shutil.assert_called_once_with(Path("source.txt"), Path("dest.txt"))
        self.assertEqual(dest_path, Path("dest.txt"))

    @patch('pathlib.Path.glob')
    def test_list_files(self, mock_glob):
        """ファイル一覧の取得をテスト"""
        # モックの設定
        mock_glob.return_value = [Path("file1.txt"), Path("file2.txt")]
        
        # テスト実行
        files = self.storage_manager.list_files(Path("dir"), "*.txt")
        
        # 検証
        mock_glob.assert_called_once_with("*.txt")
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0], Path("file1.txt"))
        self.assertEqual(files[1], Path("file2.txt"))

    @patch('os.path.getsize')
    def test_get_file_size(self, mock_getsize):
        """ファイルサイズの取得をテスト"""
        # モックの設定
        mock_getsize.return_value = 1024
        
        # テスト実行
        size = self.storage_manager.get_file_size(Path("test.txt"))
        
        # 検証
        mock_getsize.assert_called_once_with(Path("test.txt"))
        self.assertEqual(size, 1024)

    @patch('os.path.getmtime')
    def test_get_file_modified_time(self, mock_getmtime):
        """ファイル更新時刻の取得をテスト"""
        # モックの設定
        mock_getmtime.return_value = 1622548800.0  # 2021-06-01 12:00:00
        
        # テスト実行
        mtime = self.storage_manager.get_file_modified_time(Path("test.txt"))
        
        # 検証
        mock_getmtime.assert_called_once_with(Path("test.txt"))
        self.assertEqual(mtime, 1622548800.0)

    @patch('pathlib.Path.unlink')
    def test_delete_file(self, mock_unlink):
        """ファイル削除をテスト"""
        # テスト実行
        self.storage_manager.delete_file(Path("test.txt"))
        
        # 検証
        mock_unlink.assert_called_once()

    @patch('shutil.rmtree')
    def test_delete_directory(self, mock_rmtree):
        """ディレクトリ削除をテスト"""
        # テスト実行
        self.storage_manager.delete_directory(Path("test_dir"))
        
        # 検証
        mock_rmtree.assert_called_once_with(Path("test_dir"))


if __name__ == '__main__':
    unittest.main()