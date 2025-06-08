"""
コマンドラインインターフェースのテスト

このモジュールは、アプリケーション層のコマンドラインインターフェース（CLI）の機能をテストします。
"""
import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
import argparse

from src.application.cli import parse_args, main, transcribe_command, generate_minutes_command


class TestCLI(unittest.TestCase):
    """CLIのテストクラス"""

    def setUp(self):
        """各テスト実行前の準備"""
        # サービスのモック
        self.transcription_patcher = patch('src.application.cli.transcription_service')
        self.mock_transcription = self.transcription_patcher.start()
        
        self.minutes_patcher = patch('src.application.cli.minutes_generator_service')
        self.mock_minutes = self.minutes_patcher.start()
        
        self.media_patcher = patch('src.application.cli.media_processor_service')
        self.mock_media = self.media_patcher.start()
        
        # ロガーのモック
        self.logger_patcher = patch('src.application.cli.logger')
        self.mock_logger = self.logger_patcher.start()
        
        # 標準出力のモック
        self.stdout_patcher = patch('sys.stdout')
        self.mock_stdout = self.stdout_patcher.start()

    def tearDown(self):
        """各テスト実行後のクリーンアップ"""
        self.transcription_patcher.stop()
        self.minutes_patcher.stop()
        self.media_patcher.stop()
        self.logger_patcher.stop()
        self.stdout_patcher.stop()

    def test_parse_args_transcribe(self):
        """transcribeコマンドの引数解析をテスト"""
        # テスト用のコマンドライン引数
        test_args = ['transcribe', 'test.mp3', '--output', 'output_dir']
        
        # テスト実行
        with patch('sys.argv', ['cli.py'] + test_args):
            args = parse_args()
        
        # 検証
        self.assertEqual(args.command, 'transcribe')
        self.assertEqual(args.input, 'test.mp3')
        self.assertEqual(args.output, 'output_dir')

    def test_parse_args_minutes(self):
        """minutesコマンドの引数解析をテスト"""
        # テスト用のコマンドライン引数
        test_args = ['minutes', 'transcript.txt', '--media', 'test.mp3', '--output', 'output_dir']
        
        # テスト実行
        with patch('sys.argv', ['cli.py'] + test_args):
            args = parse_args()
        
        # 検証
        self.assertEqual(args.command, 'minutes')
        self.assertEqual(args.transcript, 'transcript.txt')
        self.assertEqual(args.media, 'test.mp3')
        self.assertEqual(args.output, 'output_dir')

    def test_parse_args_no_command(self):
        """コマンドなしの引数解析をテスト"""
        # テスト用のコマンドライン引数
        test_args = []
        
        # テスト実行と検証
        with patch('sys.argv', ['cli.py'] + test_args):
            with self.assertRaises(SystemExit):
                parse_args()

    @patch('src.application.cli.transcribe_command')
    def test_main_transcribe(self, mock_transcribe_command):
        """transcribeコマンドのmain関数をテスト"""
        # テスト用のコマンドライン引数
        test_args = ['transcribe', 'test.mp3']
        
        # テスト実行
        with patch('sys.argv', ['cli.py'] + test_args):
            result = main()
        
        # 検証
        mock_transcribe_command.assert_called_once()
        self.assertEqual(result, 0)

    @patch('src.application.cli.generate_minutes_command')
    def test_main_minutes(self, mock_generate_minutes_command):
        """minutesコマンドのmain関数をテスト"""
        # テスト用のコマンドライン引数
        test_args = ['minutes', 'transcript.txt']
        
        # テスト実行
        with patch('sys.argv', ['cli.py'] + test_args):
            result = main()
        
        # 検証
        mock_generate_minutes_command.assert_called_once()
        self.assertEqual(result, 0)

    def test_main_exception(self):
        """例外発生時のmain関数をテスト"""
        # テスト用のコマンドライン引数
        test_args = ['transcribe', 'test.mp3']
        
        # モックの設定
        with patch('src.application.cli.transcribe_command', side_effect=Exception("テストエラー")):
            # テスト実行
            with patch('sys.argv', ['cli.py'] + test_args):
                result = main()
        
        # 検証
        self.mock_logger.error.assert_called_once()
        self.assertEqual(result, 1)

    def test_transcribe_command(self):
        """transcribe_commandをテスト"""
        # テスト用のデータ
        args = argparse.Namespace(
            input='test.mp3',
            output='output_dir',
            chunk_size=None,
            format=None
        )
        
        # モックの設定
        mock_media_file = MagicMock()
        self.mock_media.load_media_file.return_value = mock_media_file
        
        mock_result = MagicMock()
        self.mock_transcription.transcribe_audio.return_value = mock_result
        mock_result.is_completed = True
        
        # テスト実行
        result = transcribe_command(args)
        
        # 検証
        self.mock_media.load_media_file.assert_called_once_with(Path('test.mp3'))
        self.mock_transcription.transcribe_audio.assert_called_once_with(mock_media_file)
        self.assertEqual(result, 0)

    def test_transcribe_command_failed(self):
        """失敗したtranscribe_commandをテスト"""
        # テスト用のデータ
        args = argparse.Namespace(
            input='test.mp3',
            output='output_dir',
            chunk_size=None,
            format=None
        )
        
        # モックの設定
        mock_media_file = MagicMock()
        self.mock_media.load_media_file.return_value = mock_media_file
        
        mock_result = MagicMock()
        self.mock_transcription.transcribe_audio.return_value = mock_result
        mock_result.is_completed = False
        
        # テスト実行
        result = transcribe_command(args)
        
        # 検証
        self.mock_logger.error.assert_called_once()
        self.assertEqual(result, 1)

    def test_generate_minutes_command(self):
        """generate_minutes_commandをテスト"""
        # テスト用のデータ
        args = argparse.Namespace(
            transcript='transcript.txt',
            media='test.mp3',
            output='output_dir',
            format='markdown'
        )
        
        # モックの設定
        mock_media_file = MagicMock()
        self.mock_media.load_media_file.return_value = mock_media_file
        
        mock_transcription = MagicMock()
        mock_transcription.is_completed = True
        
        mock_minutes = MagicMock()
        self.mock_minutes.generate_minutes.return_value = mock_minutes
        
        # テスト実行
        with patch('src.application.cli.TranscriptionResult.load_from_file', return_value=mock_transcription):
            result = generate_minutes_command(args)
        
        # 検証
        self.mock_media.load_media_file.assert_called_once_with(Path('test.mp3'))
        self.mock_minutes.generate_minutes.assert_called_once()
        self.assertEqual(result, 0)

    def test_generate_minutes_command_no_transcript(self):
        """トランスクリプションなしのgenerate_minutes_commandをテスト"""
        # テスト用のデータ
        args = argparse.Namespace(
            transcript='transcript.txt',
            media='test.mp3',
            output='output_dir',
            format='markdown'
        )
        
        # モックの設定
        with patch('src.application.cli.TranscriptionResult.load_from_file', side_effect=FileNotFoundError):
            # テスト実行
            result = generate_minutes_command(args)
        
        # 検証
        self.mock_logger.error.assert_called_once()
        self.assertEqual(result, 1)

    def test_generate_minutes_command_failed(self):
        """失敗したgenerate_minutes_commandをテスト"""
        # テスト用のデータ
        args = argparse.Namespace(
            transcript='transcript.txt',
            media='test.mp3',
            output='output_dir',
            format='markdown'
        )
        
        # モックの設定
        mock_transcription = MagicMock()
        mock_transcription.is_completed = True
        
        with patch('src.application.cli.TranscriptionResult.load_from_file', return_value=mock_transcription):
            with patch('src.application.cli.media_processor_service.load_media_file', side_effect=Exception("テストエラー")):
                # テスト実行
                result = generate_minutes_command(args)
        
        # 検証
        self.mock_logger.error.assert_called_once()
        self.assertEqual(result, 1)


if __name__ == '__main__':
    unittest.main()