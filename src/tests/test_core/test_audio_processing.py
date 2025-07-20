"""
STT議事録システム - Audio Processing テスト

AudioProcessorクラスの包括的なテストスイート
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List

from pydub import AudioSegment
import ffmpeg

from src.core.audio_processing import AudioProcessor
from src.utils.error_handling import FileProcessingError


class TestAudioProcessor:
    """AudioProcessorクラスのテスト"""

    @pytest.fixture
    def audio_processor(self):
        """AudioProcessorインスタンス"""
        return AudioProcessor()

    @pytest.fixture
    def temp_dir(self):
        """テスト用一時ディレクトリ"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def sample_audio_file(self, temp_dir):
        """テスト用音声ファイル（WAV形式）"""
        # 1秒間の440Hz正弦波を生成
        audio = AudioSegment.silent(duration=1000)  # 1秒
        audio = audio.overlay(AudioSegment.sine(440, duration=1000))
        
        file_path = os.path.join(temp_dir, "test_audio.wav")
        audio.export(file_path, format="wav")
        return file_path

    @pytest.fixture
    def sample_mp3_file(self):
        """テスト用MP3ファイル"""
        # 実際のテストメディアファイルを使用
        project_root = Path(__file__).parent.parent.parent.parent
        file_path = project_root / "test_media" / "test.mp3"
        if not file_path.exists():
            pytest.skip(f"Test media file not found: {file_path}")
        return str(file_path)

    @pytest.fixture
    def sample_video_file(self):
        """テスト用動画ファイル"""
        # 実際のテストメディアファイルを使用
        project_root = Path(__file__).parent.parent.parent.parent
        file_path = project_root / "test_media" / "test.mp4"
        if not file_path.exists():
            pytest.skip(f"Test media file not found: {file_path}")
        return str(file_path)

    @pytest.fixture
    def long_audio_file(self, temp_dir):
        """テスト用長時間音声ファイル（15分）"""
        audio = AudioSegment.silent(duration=900000)  # 15分
        file_path = os.path.join(temp_dir, "long_audio.wav")
        audio.export(file_path, format="wav")
        return file_path

    def test_init_success(self):
        """正常な初期化テスト"""
        processor = AudioProcessor()
        assert processor is not None

    @patch('pydub.utils.which')
    def test_validate_dependencies_success(self, mock_which, audio_processor):
        """依存関係検証成功テスト"""
        mock_which.return_value = "/usr/bin/ffmpeg"
        
        # 例外が発生しないことを確認
        audio_processor._validate_dependencies()

    @patch('pydub.utils.which')
    def test_validate_dependencies_missing_ffmpeg(self, mock_which, audio_processor):
        """FFmpeg未インストール時のエラーテスト"""
        mock_which.return_value = None
        
        with pytest.raises(FileProcessingError, match="FFmpeg is not installed"):
            audio_processor._validate_dependencies()

    def test_load_audio_wav_success(self, audio_processor, sample_audio_file):
        """WAVファイル読み込み成功テスト"""
        audio = audio_processor.load_audio(sample_audio_file)
        
        assert isinstance(audio, AudioSegment)
        assert len(audio) == 1000  # 1秒 = 1000ms

    def test_load_audio_mp3_success(self, audio_processor, sample_mp3_file):
        """MP3ファイル読み込み成功テスト"""
        audio = audio_processor.load_audio(sample_mp3_file)
        
        assert isinstance(audio, AudioSegment)
        assert len(audio) == 2000  # 2秒 = 2000ms

    def test_load_audio_file_not_found(self, audio_processor):
        """存在しないファイルでのエラーテスト"""
        with pytest.raises(FileNotFoundError):
            audio_processor.load_audio("nonexistent_file.wav")

    def test_load_audio_invalid_format(self, audio_processor, temp_dir):
        """無効な音声形式でのエラーテスト"""
        invalid_file = os.path.join(temp_dir, "invalid.txt")
        with open(invalid_file, 'w') as f:
            f.write("This is not an audio file")
        
        with pytest.raises(FileProcessingError, match="Failed to load audio file"):
            audio_processor.load_audio(invalid_file)

    def test_get_audio_metadata_success(self, audio_processor, sample_audio_file):
        """音声メタデータ取得成功テスト"""
        metadata = audio_processor.get_audio_metadata(sample_audio_file)
        
        assert "duration" in metadata
        assert "sample_rate" in metadata
        assert "channels" in metadata
        assert "frame_rate" in metadata
        assert "file_size" in metadata
        
        assert metadata["duration"] == 1.0  # 1秒
        assert metadata["channels"] == 1  # モノラル
        assert metadata["file_size"] > 0

    def test_get_audio_metadata_file_not_found(self, audio_processor):
        """存在しないファイルのメタデータ取得エラーテスト"""
        with pytest.raises(FileNotFoundError):
            audio_processor.get_audio_metadata("nonexistent_file.wav")

    def test_split_audio_default_chunks(self, audio_processor, long_audio_file):
        """デフォルト設定での音声分割テスト"""
        audio = audio_processor.load_audio(long_audio_file)
        chunks = audio_processor.split_audio(audio)
        
        # 15分の音声を10分（600秒）ずつ分割すると2つのチャンクになる
        assert len(chunks) == 2
        assert len(chunks[0]) <= 600000  # 10分以下
        assert len(chunks[1]) <= 600000  # 10分以下

    def test_split_audio_custom_duration(self, audio_processor, long_audio_file):
        """カスタム分割時間での音声分割テスト"""
        audio = audio_processor.load_audio(long_audio_file)
        chunks = audio_processor.split_audio(audio, chunk_duration=300)  # 5分
        
        # 15分の音声を5分ずつ分割すると3つのチャンクになる
        assert len(chunks) == 3
        for chunk in chunks:
            assert len(chunk) <= 300000  # 5分以下

    def test_split_audio_with_overlap(self, audio_processor, long_audio_file):
        """オーバーラップ付き音声分割テスト"""
        audio = audio_processor.load_audio(long_audio_file)
        chunks = audio_processor.split_audio(audio, chunk_duration=300, overlap=10)
        
        assert len(chunks) >= 2
        # オーバーラップがあるため、各チャンクは指定時間より少し長くなる可能性がある

    def test_split_audio_short_audio(self, audio_processor, sample_audio_file):
        """短い音声の分割テスト（分割不要）"""
        audio = audio_processor.load_audio(sample_audio_file)
        chunks = audio_processor.split_audio(audio, chunk_duration=600)
        
        # 1秒の音声は分割されない
        assert len(chunks) == 1
        assert len(chunks[0]) == len(audio)

    def test_save_audio_chunks_success(self, audio_processor, long_audio_file, temp_dir):
        """音声チャンク保存成功テスト"""
        audio = audio_processor.load_audio(long_audio_file)
        chunks = audio_processor.split_audio(audio, chunk_duration=300)
        
        chunk_paths = audio_processor.save_audio_chunks(
            chunks, temp_dir, base_name="test_chunk"
        )
        
        assert len(chunk_paths) == len(chunks)
        for i, path in enumerate(chunk_paths):
            assert os.path.exists(path)
            assert f"test_chunk_{i:03d}.wav" in path

    def test_save_audio_chunks_custom_format(self, audio_processor, sample_audio_file, temp_dir):
        """カスタム形式での音声チャンク保存テスト"""
        audio = audio_processor.load_audio(sample_audio_file)
        chunks = [audio]  # 1つのチャンク
        
        chunk_paths = audio_processor.save_audio_chunks(
            chunks, temp_dir, base_name="custom", format="mp3"
        )
        
        assert len(chunk_paths) == 1
        assert chunk_paths[0].endswith(".mp3")
        assert os.path.exists(chunk_paths[0])

    def test_save_audio_chunks_invalid_directory(self, audio_processor, sample_audio_file):
        """無効なディレクトリでの保存エラーテスト"""
        audio = audio_processor.load_audio(sample_audio_file)
        chunks = [audio]
        
        with pytest.raises(FileProcessingError, match="Failed to save audio chunk"):
            audio_processor.save_audio_chunks(chunks, "/invalid/directory")

    def test_convert_to_wav_success(self, audio_processor, sample_mp3_file, temp_dir):
        """WAV変換成功テスト"""
        output_path = os.path.join(temp_dir, "converted.wav")
        
        result_path = audio_processor.convert_to_wav(sample_mp3_file, output_path)
        
        assert result_path == output_path
        assert os.path.exists(output_path)
        
        # 変換されたファイルが読み込めることを確認
        converted_audio = audio_processor.load_audio(output_path)
        assert isinstance(converted_audio, AudioSegment)

    def test_convert_to_wav_auto_output_path(self, audio_processor, sample_mp3_file):
        """自動出力パスでのWAV変換テスト"""
        result_path = audio_processor.convert_to_wav(sample_mp3_file)
        
        assert result_path.endswith(".wav")
        assert os.path.exists(result_path)
        
        # クリーンアップ
        os.unlink(result_path)

    def test_convert_to_wav_file_not_found(self, audio_processor, temp_dir):
        """存在しないファイルの変換エラーテスト"""
        output_path = os.path.join(temp_dir, "output.wav")
        
        with pytest.raises(FileNotFoundError):
            audio_processor.convert_to_wav("nonexistent.mp3", output_path)

    def test_normalize_audio_success(self, audio_processor, sample_audio_file):
        """音声正規化成功テスト"""
        audio = audio_processor.load_audio(sample_audio_file)
        original_dBFS = audio.dBFS
        
        normalized_audio = audio_processor.normalize_audio(audio, target_dBFS=-10.0)
        
        assert isinstance(normalized_audio, AudioSegment)
        # 正規化後の音量が目標値に近いことを確認（±1dBの誤差を許容）
        assert abs(normalized_audio.dBFS - (-10.0)) <= 1.0

    def test_normalize_audio_already_normalized(self, audio_processor, sample_audio_file):
        """既に正規化済み音声の処理テスト"""
        audio = audio_processor.load_audio(sample_audio_file)
        target_dBFS = -20.0
        
        # 一度正規化
        normalized_once = audio_processor.normalize_audio(audio, target_dBFS)
        # 再度正規化
        normalized_twice = audio_processor.normalize_audio(normalized_once, target_dBFS)
        
        # 音量レベルがほぼ同じであることを確認
        assert abs(normalized_once.dBFS - normalized_twice.dBFS) <= 0.5

    def test_normalize_audio_silent_audio(self, audio_processor):
        """無音音声の正規化テスト"""
        silent_audio = AudioSegment.silent(duration=1000)
        
        # 無音音声は正規化できないため、元の音声が返される
        result = audio_processor.normalize_audio(silent_audio)
        assert len(result) == len(silent_audio)

    @patch('ffmpeg.input')
    @patch('ffmpeg.output')
    @patch('ffmpeg.run')
    def test_extract_audio_from_video_success(self, mock_run, mock_output, mock_input, 
                                            audio_processor, sample_video_file, temp_dir):
        """動画からの音声抽出成功テスト"""
        output_path = os.path.join(temp_dir, "extracted_audio.wav")
        
        # FFmpegのモックを設定
        mock_stream = Mock()
        mock_input.return_value = mock_stream
        mock_output.return_value = mock_stream
        mock_run.return_value = None
        
        # 抽出後のファイルを作成（実際の処理をシミュレート）
        AudioSegment.silent(duration=1000).export(output_path, format="wav")
        
        result_path = audio_processor.extract_audio_from_video(sample_video_file, output_path)
        
        assert result_path == output_path
        assert os.path.exists(output_path)
        mock_input.assert_called_once_with(sample_video_file)
        mock_run.assert_called_once()

    @patch('ffmpeg.input')
    @patch('ffmpeg.output')
    @patch('ffmpeg.run')
    def test_extract_audio_from_video_auto_output(self, mock_run, mock_output, mock_input,
                                                 audio_processor, sample_video_file):
        """自動出力パスでの動画音声抽出テスト"""
        mock_stream = Mock()
        mock_input.return_value = mock_stream
        mock_output.return_value = mock_stream
        mock_run.return_value = None
        
        # 期待される出力パスを計算
        expected_output = sample_video_file.replace('.mp4', '_audio.wav')
        
        # 抽出後のファイルを作成
        AudioSegment.silent(duration=1000).export(expected_output, format="wav")
        
        result_path = audio_processor.extract_audio_from_video(sample_video_file)
        
        assert result_path == expected_output
        assert os.path.exists(expected_output)
        
        # クリーンアップ
        os.unlink(expected_output)

    @patch('ffmpeg.run')
    def test_extract_audio_from_video_ffmpeg_error(self, mock_run, audio_processor, sample_video_file):
        """FFmpegエラーでの音声抽出失敗テスト"""
        mock_run.side_effect = ffmpeg.Error("FFmpeg error", "", "")
        
        with pytest.raises(FileProcessingError, match="Failed to extract audio from video"):
            audio_processor.extract_audio_from_video(sample_video_file)

    def test_cleanup_temp_files_success(self, audio_processor, temp_dir):
        """一時ファイルクリーンアップ成功テスト"""
        # テスト用ファイルを作成
        temp_files = []
        for i in range(3):
            temp_file = os.path.join(temp_dir, f"temp_file_{i}.wav")
            with open(temp_file, 'w') as f:
                f.write("temp data")
            temp_files.append(temp_file)
        
        # すべてのファイルが存在することを確認
        for file_path in temp_files:
            assert os.path.exists(file_path)
        
        # クリーンアップ実行
        audio_processor.cleanup_temp_files(temp_files)
        
        # すべてのファイルが削除されていることを確認
        for file_path in temp_files:
            assert not os.path.exists(file_path)

    def test_cleanup_temp_files_nonexistent_files(self, audio_processor):
        """存在しないファイルのクリーンアップテスト"""
        nonexistent_files = [
            "/tmp/nonexistent1.wav",
            "/tmp/nonexistent2.wav"
        ]
        
        # 例外が発生しないことを確認
        audio_processor.cleanup_temp_files(nonexistent_files)

    def test_cleanup_temp_files_mixed_files(self, audio_processor, temp_dir):
        """存在するファイルと存在しないファイルの混在クリーンアップテスト"""
        # 存在するファイルを作成
        existing_file = os.path.join(temp_dir, "existing.wav")
        with open(existing_file, 'w') as f:
            f.write("data")
        
        mixed_files = [
            existing_file,
            "/tmp/nonexistent.wav"
        ]
        
        audio_processor.cleanup_temp_files(mixed_files)
        
        # 存在していたファイルが削除されていることを確認
        assert not os.path.exists(existing_file)

    def test_audio_processing_pipeline(self, audio_processor, sample_mp3_file, temp_dir):
        """音声処理パイプライン統合テスト"""
        # 1. MP3ファイルをWAVに変換
        wav_path = audio_processor.convert_to_wav(sample_mp3_file)
        
        # 2. 音声を読み込み
        audio = audio_processor.load_audio(wav_path)
        
        # 3. メタデータを取得
        metadata = audio_processor.get_audio_metadata(wav_path)
        
        # 4. 音声を正規化
        normalized_audio = audio_processor.normalize_audio(audio)
        
        # 5. 音声を分割（短い音声なので1つのチャンクになる）
        chunks = audio_processor.split_audio(normalized_audio, chunk_duration=60)
        
        # 6. チャンクを保存
        chunk_paths = audio_processor.save_audio_chunks(chunks, temp_dir)
        
        # 7. 一時ファイルをクリーンアップ
        cleanup_files = [wav_path] + chunk_paths
        audio_processor.cleanup_temp_files(cleanup_files)
        
        # 検証
        assert metadata["duration"] > 0
        assert len(chunks) == 1
        assert len(chunk_paths) == 1
        
        # すべてのファイルが削除されていることを確認
        for file_path in cleanup_files:
            assert not os.path.exists(file_path)

    @pytest.mark.parametrize("format_type", ["wav", "mp3", "flac"])
    def test_save_audio_chunks_different_formats(self, audio_processor, sample_audio_file, 
                                               temp_dir, format_type):
        """異なる形式での音声チャンク保存テスト"""
        audio = audio_processor.load_audio(sample_audio_file)
        chunks = [audio]
        
        chunk_paths = audio_processor.save_audio_chunks(
            chunks, temp_dir, format=format_type
        )
        
        assert len(chunk_paths) == 1
        assert chunk_paths[0].endswith(f".{format_type}")
        assert os.path.exists(chunk_paths[0])

    def test_large_file_handling(self, audio_processor, temp_dir):
        """大きなファイルの処理テスト"""
        # 30分の音声ファイルを作成（メモリ効率をテスト）
        large_audio = AudioSegment.silent(duration=1800000)  # 30分
        large_file_path = os.path.join(temp_dir, "large_audio.wav")
        large_audio.export(large_file_path, format="wav")
        
        # メタデータ取得
        metadata = audio_processor.get_audio_metadata(large_file_path)
        assert metadata["duration"] == 1800.0  # 30分
        
        # 音声読み込み
        audio = audio_processor.load_audio(large_file_path)
        assert len(audio) == 1800000  # 30分
        
        # 分割処理
        chunks = audio_processor.split_audio(audio, chunk_duration=600)  # 10分ずつ
        assert len(chunks) == 3  # 30分 ÷ 10分 = 3チャンク

    def test_error_recovery_and_cleanup(self, audio_processor, temp_dir):
        """エラー発生時の復旧とクリーンアップテスト"""
        # 無効な音声データでエラーを発生させる
        invalid_file = os.path.join(temp_dir, "invalid.wav")
        with open(invalid_file, 'wb') as f:
            f.write(b'invalid_audio_data')
        
        temp_files = [invalid_file]
        
        try:
            # エラーが発生することを期待
            audio_processor.load_audio(invalid_file)
        except FileProcessingError:
            # エラー後のクリーンアップ
            audio_processor.cleanup_temp_files(temp_files)
            
            # ファイルが削除されていることを確認
            assert not os.path.exists(invalid_file)