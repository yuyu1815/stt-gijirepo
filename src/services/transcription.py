"""
文字起こしサービス

このモジュールは、音声ファイルの文字起こしに関するサービスを提供します。
Gemini APIを使用して高精度な文字起こしを実現します。
"""
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..domain.media import MediaChunk, MediaFile
from ..domain.transcription import (
    HallucinationResult, HallucinationSeverity, Speaker,
    TranscriptionResult, TranscriptionSegment, TranscriptionStatus
)
from ..infrastructure.config import config_manager
from ..infrastructure.logger import logger
from ..infrastructure.storage import storage_manager
from ..utils.parallel import ParallelExecutionMode, parallel_map


class TranscriptionService:
    """文字起こしサービスクラス"""

    def __init__(self):
        """初期化"""
        self.api_key = config_manager.get_api_key("gemini")
        self.max_retries = config_manager.get("transcription.max_retries", 3)
        self.retry_delay = config_manager.get("transcription.retry_delay", 2)
        self.max_retry_delay = config_manager.get("transcription.max_retry_delay", 30)
        self.prompt_path = config_manager.get_prompt_path("transcription")

    def transcribe_audio(self, media_file: MediaFile) -> TranscriptionResult:
        """
        音声ファイルを文字起こし
        
        Args:
            media_file: 音声ファイル
            
        Returns:
            文字起こし結果
        """
        # 結果オブジェクトを初期化
        result = TranscriptionResult(
            source_file=media_file.file_path,
            status=TranscriptionStatus.IN_PROGRESS
        )
        
        try:
            # 長時間メディアの場合はチャンク処理
            if media_file.is_long_media and media_file.has_chunks:
                logger.info(f"長時間メディアをチャンク処理します: {media_file.file_path}")
                result = self._transcribe_chunks(media_file)
            else:
                # 単一ファイルの文字起こし
                logger.info(f"単一ファイルを文字起こしします: {media_file.file_path}")
                segments = self._transcribe_single_file(media_file.file_path)
                result.segments = segments
                result.status = TranscriptionStatus.COMPLETED
                
            # 結果を保存
            self._save_transcription_result(result)
            
            return result
        except Exception as e:
            logger.error(f"文字起こしに失敗しました: {e}")
            result.status = TranscriptionStatus.FAILED
            return result

    def _transcribe_chunks(self, media_file: MediaFile) -> TranscriptionResult:
        """
        チャンクに分割されたメディアファイルを文字起こし
        
        Args:
            media_file: チャンクに分割されたメディアファイル
            
        Returns:
            文字起こし結果
        """
        # 結果オブジェクトを初期化
        result = TranscriptionResult(
            source_file=media_file.file_path,
            status=TranscriptionStatus.IN_PROGRESS
        )
        
        # チャンクがない場合はエラー
        if not media_file.has_chunks:
            logger.error(f"チャンクが見つかりません: {media_file.file_path}")
            result.status = TranscriptionStatus.FAILED
            return result
            
        # 各チャンクを並列処理
        chunk_results = parallel_map(
            lambda chunk: self._transcribe_chunk(chunk, media_file),
            media_file.chunks,
            ParallelExecutionMode.THREAD
        )
        
        # 結果を結合
        all_segments = []
        for chunk_segments in chunk_results:
            all_segments.extend(chunk_segments)
            
        # タイムスタンプでソート
        all_segments.sort(key=lambda s: s.start_time)
        
        # 結果を設定
        result.segments = all_segments
        result.status = TranscriptionStatus.COMPLETED
        
        logger.info(f"{len(media_file.chunks)}個のチャンクの文字起こしが完了しました: {media_file.file_path}")
        return result

    def _transcribe_chunk(self, chunk: MediaChunk, media_file: MediaFile) -> List[TranscriptionSegment]:
        """
        単一のチャンクを文字起こし
        
        Args:
            chunk: 音声チャンク
            media_file: 元のメディアファイル
            
        Returns:
            文字起こしセグメントのリスト
        """
        logger.info(f"チャンク {chunk.index} を文字起こしします: {chunk.file_path}")
        
        # チャンクを文字起こし
        segments = self._transcribe_single_file(chunk.file_path)
        
        # タイムスタンプを調整（チャンクの開始時間を加算）
        for segment in segments:
            segment.start_time += chunk.start_time
            segment.end_time += chunk.start_time
            
        logger.info(f"チャンク {chunk.index} の文字起こしが完了しました: {len(segments)}個のセグメント")
        return segments

    def _transcribe_single_file(self, file_path: Union[str, Path]) -> List[TranscriptionSegment]:
        """
        単一の音声ファイルを文字起こし
        
        Args:
            file_path: 音声ファイルのパス
            
        Returns:
            文字起こしセグメントのリスト
        """
        file_path = Path(file_path)
        
        # プロンプトを読み込む
        prompt = self._load_transcription_prompt()
        
        # Gemini APIで文字起こし
        transcription = self._transcribe_with_gemini(file_path, prompt)
        
        # 文字起こし結果をパース
        segments = self._parse_transcription(transcription)
        
        logger.info(f"文字起こしが完了しました: {file_path} ({len(segments)}個のセグメント)")
        return segments

    def _load_transcription_prompt(self) -> str:
        """
        文字起こしプロンプトを読み込む
        
        Returns:
            プロンプトテキスト
        """
        if not self.prompt_path.exists():
            logger.warning(f"プロンプトファイルが見つかりません: {self.prompt_path}")
            return "音声を文字起こししてください。話者を区別し、タイムスタンプを含めてください。"
            
        return storage_manager.load_text(self.prompt_path)

    def _transcribe_with_gemini(self, file_path: Path, prompt: str) -> str:
        """
        Gemini APIを使用して文字起こし
        
        Args:
            file_path: 音声ファイルのパス
            prompt: プロンプトテキスト
            
        Returns:
            文字起こしテキスト
        """
        # APIキーが設定されていない場合はエラー
        if not self.api_key:
            logger.error("Gemini APIキーが設定されていません")
            raise ValueError("Gemini APIキーが設定されていません")
            
        # ここでは実際のGemini API呼び出しの代わりにモック実装
        # 実際の実装では、Gemini APIクライアントを使用して音声ファイルを送信し、文字起こし結果を取得する
        
        # モック実装（実際の実装では削除）
        logger.info(f"Gemini APIで文字起こしを実行します: {file_path}")
        
        # 再試行メカニズム
        retry_count = 0
        while retry_count <= self.max_retries:
            try:
                # ここに実際のAPI呼び出しコードを実装
                # 例: response = gemini_client.transcribe_audio(file_path, prompt)
                
                # モック応答（実際の実装では削除）
                mock_response = self._generate_mock_transcription(file_path)
                
                # 成功した場合は結果を返す
                return mock_response
            except Exception as e:
                retry_count += 1
                
                # 最大再試行回数に達した場合はエラーを発生
                if retry_count > self.max_retries:
                    logger.error(f"文字起こしの最大再試行回数に達しました: {e}")
                    raise
                    
                # 再試行前に待機（指数バックオフ）
                delay = min(self.retry_delay * (2 ** (retry_count - 1)), self.max_retry_delay)
                logger.warning(f"文字起こしに失敗しました。{delay}秒後に再試行します ({retry_count}/{self.max_retries}): {e}")
                time.sleep(delay)

    def _generate_mock_transcription(self, file_path: Path) -> str:
        """
        モック文字起こし結果を生成（実際の実装では削除）
        
        Args:
            file_path: 音声ファイルのパス
            
        Returns:
            モック文字起こしテキスト
        """
        # 実際の実装では削除
        return f"""
[00:00:00 - 00:00:10] 話者A: これは{file_path.stem}の文字起こしテストです。
[00:00:11 - 00:00:20] 話者B: はい、テスト音声の文字起こしを行っています。
[00:00:21 - 00:00:30] 話者A: このモジュールは実際のGemini APIを使用して文字起こしを行います。
[00:00:31 - 00:00:40] 話者B: 現在はモック実装になっていますが、実際の実装では適切なAPIクライアントを使用します。
"""

    def _parse_transcription(self, transcription: str) -> List[TranscriptionSegment]:
        """
        文字起こしテキストをパース
        
        Args:
            transcription: 文字起こしテキスト
            
        Returns:
            文字起こしセグメントのリスト
        """
        segments = []
        
        # 行ごとに処理
        for line in transcription.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
                
            try:
                # タイムスタンプと話者、テキストを抽出
                # 例: [00:00:00 - 00:00:10] 話者A: これはテストです。
                import re
                match = re.match(r'\[(\d+:\d+:\d+)\s*-\s*(\d+:\d+:\d+)\]\s*([^:]+):\s*(.*)', line)
                
                if match:
                    start_str, end_str, speaker_name, text = match.groups()
                    
                    # タイムスタンプを秒に変換
                    start_time = self._time_str_to_seconds(start_str)
                    end_time = self._time_str_to_seconds(end_str)
                    
                    # 話者オブジェクトを作成
                    speaker = Speaker(id=speaker_name.strip(), name=speaker_name.strip())
                    
                    # セグメントを作成
                    segment = TranscriptionSegment(
                        text=text.strip(),
                        start_time=start_time,
                        end_time=end_time,
                        speaker=speaker
                    )
                    
                    segments.append(segment)
                else:
                    # タイムスタンプがない場合は前のセグメントの続きとして扱う
                    if segments:
                        segments[-1].text += f" {line}"
            except Exception as e:
                logger.warning(f"文字起こし行のパースに失敗しました: {line} - {e}")
                
        return segments

    def _time_str_to_seconds(self, time_str: str) -> float:
        """
        時間文字列を秒に変換
        
        Args:
            time_str: 時間文字列（HH:MM:SS形式）
            
        Returns:
            秒数
        """
        parts = time_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = map(float, parts)
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            minutes, seconds = map(float, parts)
            return minutes * 60 + seconds
        else:
            return float(time_str)

    def _save_transcription_result(self, result: TranscriptionResult) -> Path:
        """
        文字起こし結果を保存
        
        Args:
            result: 文字起こし結果
            
        Returns:
            保存したファイルのパス
        """
        # 出力ディレクトリを取得
        output_dir = storage_manager.get_output_dir("transcripts")
        
        # ファイル名を生成
        file_name = f"{result.source_file.stem}_transcript.txt"
        output_path = output_dir / file_name
        
        # テキスト形式で保存
        content = self._format_transcription_for_output(result)
        storage_manager.save_text(content, output_path)
        
        logger.info(f"文字起こし結果を保存しました: {output_path}")
        return output_path

    def _format_transcription_for_output(self, result: TranscriptionResult) -> str:
        """
        出力用に文字起こし結果をフォーマット
        
        Args:
            result: 文字起こし結果
            
        Returns:
            フォーマットされたテキスト
        """
        lines = []
        
        # ヘッダー
        lines.append(f"# 文字起こし結果: {result.source_file.name}")
        lines.append(f"# 生成日時: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # セグメント
        for segment in result.segments:
            # 時間をフォーマット
            start_time_str = self._format_time(segment.start_time)
            end_time_str = self._format_time(segment.end_time)
            
            # 話者
            speaker_str = f"{segment.speaker.name}: " if segment.speaker else ""
            
            # 行を追加
            lines.append(f"[{start_time_str} - {end_time_str}] {speaker_str}{segment.text}")
            
        return "\n".join(lines)

    def _format_time(self, seconds: float) -> str:
        """
        秒を時間文字列にフォーマット
        
        Args:
            seconds: 秒数
            
        Returns:
            時間文字列（HH:MM:SS形式）
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# シングルトンインスタンス
transcription_service = TranscriptionService()