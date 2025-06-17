"""
グラフィカルユーザーインターフェースのテスト

このモジュールは、アプリケーション層のグラフィカルユーザーインターフェース（GUI）の機能をテストします。
"""
import unittest
from unittest.mock import patch, MagicMock, call
import tkinter as tk
from pathlib import Path
import os

# GUIアプリケーションのインポート
# 注: 実際のインポートパスは実装によって異なる場合があります
from src.application.app import App, TranscriptionTab, MinutesTab


class TestApp(unittest.TestCase):
    """アプリケーションのメインウィンドウのテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # tkinterのモック
        self.root_patcher = patch('tkinter.Tk')
        self.mock_root = self.root_patcher.start()
        
        # サービスのモック
        self.transcription_patcher = patch('src.application.app.transcription_service')
        self.mock_transcription = self.transcription_patcher.start()
        
        self.minutes_patcher = patch('src.application.app.minutes_generator_service')
        self.mock_minutes = self.minutes_patcher.start()
        
        self.media_patcher = patch('src.application.app.media_processor_service')
        self.mock_media = self.media_patcher.start()
        
        # ロガーのモック
        self.logger_patcher = patch('src.application.app.logger')
        self.mock_logger = self.logger_patcher.start()
        
        # ファイルダイアログのモック
        self.filedialog_patcher = patch('tkinter.filedialog')
        self.mock_filedialog = self.filedialog_patcher.start()
        
        # メッセージボックスのモック
        self.messagebox_patcher = patch('tkinter.messagebox')
        self.mock_messagebox = self.messagebox_patcher.start()

    def tearDown(self):
        """各テスト実行後のクリーンアップ"""
        self.root_patcher.stop()
        self.transcription_patcher.stop()
        self.minutes_patcher.stop()
        self.media_patcher.stop()
        self.logger_patcher.stop()
        self.filedialog_patcher.stop()
        self.messagebox_patcher.stop()

    def test_app_initialization(self):
        """アプリケーションの初期化をテスト"""
        # テスト実行
        app = App()
        
        # 検証
        self.mock_root.assert_called_once()
        self.assertEqual(app.title, "音声文字起こし・議事録自動生成ツール")
        # ノートブックが作成されていることを確認
        self.assertTrue(hasattr(app, 'notebook'))

    def test_app_create_tabs(self):
        """タブの作成をテスト"""
        # テスト実行
        app = App()
        
        # 検証
        # 文字起こしタブと議事録タブが作成されていることを確認
        self.assertTrue(hasattr(app, 'transcription_tab'))
        self.assertTrue(hasattr(app, 'minutes_tab'))

    def test_app_run(self):
        """アプリケーションの実行をテスト"""
        # テスト実行
        app = App()
        app.run()
        
        # 検証
        # mainloopが呼び出されていることを確認
        app.root.mainloop.assert_called_once()


class TestTranscriptionTab(unittest.TestCase):
    """文字起こしタブのテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # 親ウィジェットのモック
        self.parent = MagicMock()
        
        # サービスのモック
        self.transcription_patcher = patch('src.application.app.transcription_service')
        self.mock_transcription = self.transcription_patcher.start()
        
        self.media_patcher = patch('src.application.app.media_processor_service')
        self.mock_media = self.media_patcher.start()
        
        # ロガーのモック
        self.logger_patcher = patch('src.application.app.logger')
        self.mock_logger = self.logger_patcher.start()
        
        # ファイルダイアログのモック
        self.filedialog_patcher = patch('tkinter.filedialog')
        self.mock_filedialog = self.filedialog_patcher.start()
        
        # メッセージボックスのモック
        self.messagebox_patcher = patch('tkinter.messagebox')
        self.mock_messagebox = self.messagebox_patcher.start()
        
        # tkinter変数のモック
        self.stringvar_patcher = patch('tkinter.StringVar')
        self.mock_stringvar = self.stringvar_patcher.start()
        
        self.booleanvar_patcher = patch('tkinter.BooleanVar')
        self.mock_booleanvar = self.booleanvar_patcher.start()

    def tearDown(self):
        """各テスト実行後のクリーンアップ"""
        self.transcription_patcher.stop()
        self.media_patcher.stop()
        self.logger_patcher.stop()
        self.filedialog_patcher.stop()
        self.messagebox_patcher.stop()
        self.stringvar_patcher.stop()
        self.booleanvar_patcher.stop()

    def test_transcription_tab_initialization(self):
        """文字起こしタブの初期化をテスト"""
        # テスト実行
        tab = TranscriptionTab(self.parent)
        
        # 検証
        # 必要なウィジェットが作成されていることを確認
        self.assertEqual(tab.parent, self.parent)
        self.assertTrue(hasattr(tab, 'file_path_var'))
        self.assertTrue(hasattr(tab, 'status_var'))
        self.assertTrue(hasattr(tab, 'chunk_var'))

    @patch('src.application.app.TranscriptionTab._create_widgets')
    def test_transcription_tab_create_widgets(self, mock_create_widgets):
        """ウィジェット作成をテスト"""
        # テスト実行
        tab = TranscriptionTab(self.parent)
        
        # 検証
        mock_create_widgets.assert_called_once()

    def test_transcription_tab_browse_file(self):
        """ファイル選択をテスト"""
        # モックの設定
        self.mock_filedialog.askopenfilename.return_value = "test.mp3"
        
        # テスト実行
        tab = TranscriptionTab(self.parent)
        tab.browse_file()
        
        # 検証
        self.mock_filedialog.askopenfilename.assert_called_once()
        tab.file_path_var.set.assert_called_with("test.mp3")

    def test_transcription_tab_start_transcription(self):
        """文字起こし開始をテスト"""
        # モックの設定
        tab = TranscriptionTab(self.parent)
        tab.file_path_var.get.return_value = "test.mp3"
        tab.chunk_var.get.return_value = True
        
        mock_media_file = MagicMock()
        self.mock_media.load_media_file.return_value = mock_media_file
        
        mock_result = MagicMock()
        self.mock_transcription.transcribe_audio.return_value = mock_result
        mock_result.is_completed = True
        
        # テスト実行
        with patch('threading.Thread') as mock_thread:
            tab.start_transcription()
            
            # スレッドが作成され、startが呼び出されていることを確認
            mock_thread.assert_called_once()
            mock_thread.return_value.start.assert_called_once()
            
            # スレッドに渡された関数を実行
            mock_thread.call_args[1]['target']()
        
        # 検証
        self.mock_media.load_media_file.assert_called_once_with(Path("test.mp3"))
        self.mock_transcription.transcribe_audio.assert_called_once_with(mock_media_file)
        self.mock_messagebox.showinfo.assert_called_once()


class TestMinutesTab(unittest.TestCase):
    """議事録タブのテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # 親ウィジェットのモック
        self.parent = MagicMock()
        
        # サービスのモック
        self.minutes_patcher = patch('src.application.app.minutes_generator_service')
        self.mock_minutes = self.minutes_patcher.start()
        
        self.media_patcher = patch('src.application.app.media_processor_service')
        self.mock_media = self.media_patcher.start()
        
        # ロガーのモック
        self.logger_patcher = patch('src.application.app.logger')
        self.mock_logger = self.logger_patcher.start()
        
        # ファイルダイアログのモック
        self.filedialog_patcher = patch('tkinter.filedialog')
        self.mock_filedialog = self.filedialog_patcher.start()
        
        # メッセージボックスのモック
        self.messagebox_patcher = patch('tkinter.messagebox')
        self.mock_messagebox = self.messagebox_patcher.start()
        
        # tkinter変数のモック
        self.stringvar_patcher = patch('tkinter.StringVar')
        self.mock_stringvar = self.stringvar_patcher.start()

    def tearDown(self):
        """各テスト実行後のクリーンアップ"""
        self.minutes_patcher.stop()
        self.media_patcher.stop()
        self.logger_patcher.stop()
        self.filedialog_patcher.stop()
        self.messagebox_patcher.stop()
        self.stringvar_patcher.stop()

    def test_minutes_tab_initialization(self):
        """議事録タブの初期化をテスト"""
        # テスト実行
        tab = MinutesTab(self.parent)
        
        # 検証
        # 必要なウィジェットが作成されていることを確認
        self.assertEqual(tab.parent, self.parent)
        self.assertTrue(hasattr(tab, 'transcript_path_var'))
        self.assertTrue(hasattr(tab, 'media_path_var'))
        self.assertTrue(hasattr(tab, 'status_var'))

    @patch('src.application.app.MinutesTab._create_widgets')
    def test_minutes_tab_create_widgets(self, mock_create_widgets):
        """ウィジェット作成をテスト"""
        # テスト実行
        tab = MinutesTab(self.parent)
        
        # 検証
        mock_create_widgets.assert_called_once()

    def test_minutes_tab_browse_transcript(self):
        """トランスクリプトファイル選択をテスト"""
        # モックの設定
        self.mock_filedialog.askopenfilename.return_value = "transcript.txt"
        
        # テスト実行
        tab = MinutesTab(self.parent)
        tab.browse_transcript()
        
        # 検証
        self.mock_filedialog.askopenfilename.assert_called_once()
        tab.transcript_path_var.set.assert_called_with("transcript.txt")

    def test_minutes_tab_browse_media(self):
        """メディアファイル選択をテスト"""
        # モックの設定
        self.mock_filedialog.askopenfilename.return_value = "test.mp3"
        
        # テスト実行
        tab = MinutesTab(self.parent)
        tab.browse_media()
        
        # 検証
        self.mock_filedialog.askopenfilename.assert_called_once()
        tab.media_path_var.set.assert_called_with("test.mp3")

    def test_minutes_tab_generate_minutes(self):
        """議事録生成をテスト"""
        # モックの設定
        tab = MinutesTab(self.parent)
        tab.transcript_path_var.get.return_value = "transcript.txt"
        tab.media_path_var.get.return_value = "test.mp3"
        
        mock_media_file = MagicMock()
        self.mock_media.load_media_file.return_value = mock_media_file
        
        mock_transcription = MagicMock()
        mock_transcription.is_completed = True
        
        mock_minutes = MagicMock()
        self.mock_minutes.generate_minutes.return_value = mock_minutes
        mock_minutes.output_path = Path("minutes.md")
        
        # テスト実行
        with patch('src.application.app.TranscriptionResult.load_from_file', return_value=mock_transcription):
            with patch('threading.Thread') as mock_thread:
                tab.generate_minutes()
                
                # スレッドが作成され、startが呼び出されていることを確認
                mock_thread.assert_called_once()
                mock_thread.return_value.start.assert_called_once()
                
                # スレッドに渡された関数を実行
                mock_thread.call_args[1]['target']()
        
        # 検証
        self.mock_media.load_media_file.assert_called_once_with(Path("test.mp3"))
        self.mock_minutes.generate_minutes.assert_called_once()
        self.mock_messagebox.showinfo.assert_called_once()


if __name__ == '__main__':
    unittest.main()