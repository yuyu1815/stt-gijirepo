"""
文字起こしサービス

このモジュールは、音声ファイルの文字起こしに関するサービスを提供します。
Gemini APIを使用して高精度な文字起こしを実現します。
"""
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import re
from google import genai

from ..domain.media import MediaChunk, MediaFile
from ..domain.transcription import (
    HallucinationResult, HallucinationSeverity, Speaker,
    TranscriptionResult, TranscriptionSegment, TranscriptionStatus
)
from ..infrastructure.config import config_manager
from ..infrastructure.logger import logger
from ..infrastructure.storage import storage_manager
from ..utils.parallel import ParallelExecutionMode, parallel_map
from ..utils.time_utils import format_time, time_str_to_seconds


class TranscriptionService:
    """文字起こしサービスクラス"""

    def __init__(self):
        """初期化"""
        self.api_key = config_manager.get_api_key("gemini")
        self.max_retries = config_manager.get("transcription.max_retries", 3)
        self.retry_delay = config_manager.get("transcription.retry_delay", 2)
        self.max_retry_delay = config_manager.get("transcription.max_retry_delay", 30)
        self.prompt_path = config_manager.get_prompt_path("transcription")

        # レート制限のための変数
        self.requests_per_minute = config_manager.get("transcription.requests_per_minute", 5)  # デフォルトは1分あたり5リクエスト
        self.request_timestamps = []  # リクエストのタイムスタンプを記録するリスト

    def combine_transcriptions(self, transcription_results: List[TranscriptionResult], original_source_file: Optional[Path] = None) -> TranscriptionResult:
        """
        複数の文字起こし結果を結合する

        Args:
            transcription_results: 文字起こし結果のリスト
            original_source_file: 元のメディアファイルのパス（指定しない場合は最初のチャンクのパスを使用）

        Returns:
            結合された文字起こし結果
        """
        if not transcription_results:
            logger.error("結合する文字起こし結果がありません")
            raise ValueError("結合する文字起こし結果がありません")

        # 最初の結果をベースにする
        base_result = transcription_results[0]

        # すべてのセグメントを収集
        all_segments = []
        for result in transcription_results:
            all_segments.extend(result.segments)

        # タイムスタンプでソート
        all_segments.sort(key=lambda s: s.start_time)

        # 結合された結果を作成（元のメディアファイルのパスを使用）
        source_file = original_source_file if original_source_file else base_result.source_file
        combined_result = TranscriptionResult(
            source_file=source_file,
            status=TranscriptionStatus.COMPLETED,
            segments=all_segments
        )

        # 結果を保存
        output_path = self._save_combined_transcription(combined_result)

        logger.info(f"{len(transcription_results)}個の文字起こし結果を結合しました: {len(all_segments)}個のセグメント")
        return combined_result

    def _save_combined_transcription(self, result: TranscriptionResult) -> Path:
        """
        結合された文字起こし結果を保存

        Args:
            result: 文字起こし結果

        Returns:
            保存したファイルのパス
        """
        # 出力ディレクトリを取得
        output_dir = storage_manager.get_output_dir("transcripts")

        # ファイル名を生成
        file_name = f"{result.source_file.stem}_combined_transcript.txt"
        output_path = output_dir / file_name

        # テキスト形式で保存
        content = self._format_transcription_for_output(result)
        storage_manager.save_text(content, output_path)

        logger.info(f"結合された文字起こし結果を保存しました: {output_path}")
        return output_path

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
                segments = self._transcribe_single_file(media_file.file_path, original_media_file=media_file) # Modified
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

        # チャンクをインデックス順にソート
        sorted_chunks = sorted(media_file.chunks, key=lambda chunk: chunk.index)

        logger.info(f"チャンクをインデックス順に処理します: {[chunk.index for chunk in sorted_chunks]}")

        # 各チャンクを順番に処理（APIの動作不良を防ぐため1スレッドに制限）
        chunk_results = parallel_map(
            lambda chunk: self._transcribe_chunk(chunk, media_file),
            sorted_chunks,
            ParallelExecutionMode.THREAD,
            max_workers=1
        )

        # 結果を結合（チャンクのインデックス順）
        all_segments = []
        for chunk_segments in chunk_results:
            all_segments.extend(chunk_segments)

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
        segments = self._transcribe_single_file(chunk.file_path, original_media_file=media_file) # Modified

        # タイムスタンプを調整（チャンクの開始時間を加算）
        for segment in segments:
            segment.start_time += chunk.start_time
            segment.end_time += chunk.start_time

        logger.info(f"チャンク {chunk.index} の文字起こしが完了しました: {len(segments)}個のセグメント")
        return segments

    def _transcribe_single_file(self, file_path: Union[str, Path], original_media_file: Optional[MediaFile] = None) -> List[TranscriptionSegment]: # Modified
        """
        単一の音声ファイルを文字起こし

        Args:
            file_path: 音声ファイルのパス
            original_media_file: (Optional) 元のメディアファイルオブジェクト（ビデオの場合に使用）

        Returns:
            文字起こしセグメントのリスト
        """
        file_path = Path(file_path)

        # プロンプトを読み込む
        prompt = self._load_transcription_prompt()

        # Gemini APIで文字起こし
        transcription = self._transcribe_with_gemini(file_path, prompt) # This mock doesn't know about original_media_file, if real API needs it, adapt here

        # transcriptionがNoneの場合、空の文字列を使用する
        if transcription is None:
            logger.warning(f"文字起こしの結果がNoneでした。空の文字列を使用します: {file_path}")
            transcription = ""

        # 文字起こし結果をパース
        segments = self._parse_transcription(transcription, original_media_file=original_media_file) # Modified

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

    def _extract_retry_delay_from_error(self, error) -> float:
        """
        エラーからretryDelayを抽出する

        Args:
            error: エラーオブジェクト

        Returns:
            抽出されたretryDelay（秒）、抽出できない場合はNone
        """
        try:
            # エラーメッセージを文字列に変換
            error_str = str(error)

            # RESOURCE_EXHAUSTEDエラーかどうかを確認
            if "RESOURCE_EXHAUSTED" in error_str:
                # retryDelayを抽出
                import re
                retry_delay_match = re.search(r"'retryDelay': '(\d+)s'", error_str)
                if retry_delay_match:
                    return float(retry_delay_match.group(1))

            return None
        except Exception as e:
            logger.warning(f"retryDelayの抽出に失敗しました: {e}")
            return None

    def _check_rate_limit(self):
        """
        レート制限をチェックし、必要に応じて待機する

        直近1分間のリクエスト数をチェックし、設定された上限を超えている場合は
        制限内に収まるまで待機します。
        """
        current_time = time.time()

        # 1分（60秒）以上前のタイムスタンプを削除
        self.request_timestamps = [ts for ts in self.request_timestamps if current_time - ts < 60]

        # 現在のリクエスト数が上限に達している場合
        if len(self.request_timestamps) >= self.requests_per_minute:
            # 最も古いリクエストから60秒経過するまで待機
            oldest_timestamp = self.request_timestamps[0]
            wait_time = 60 - (current_time - oldest_timestamp)

            if wait_time > 0:
                logger.info(f"レート制限に達しました。{wait_time:.2f}秒待機します（1分あたり{self.requests_per_minute}リクエスト）")
                time.sleep(wait_time)

                # 待機後に再度チェック（再帰呼び出し）
                self._check_rate_limit()

    def _transcribe_with_gemini(self, file_path: Path, prompt: str) -> str | None:
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

        # Gemini APIの設定
        client = genai.Client(api_key=self.api_key)
        model_name = config_manager.get("gemini.model", "gemini-2.0-flash")

        logger.info(f"Gemini APIで文字起こしを実行します: {file_path}")

        # 再試行メカニズム
        retry_count = 0
        while retry_count <= self.max_retries:
            try:
                # レート制限をチェック
                self._check_rate_limit()

                # リクエストのタイムスタンプを記録
                self.request_timestamps.append(time.time())

                # 音声ファイルをアップロード
                my_file = client.files.upload(file=str(file_path))

                while my_file.state.name == "PROCESSING":
                    print("ビデオを処理中...",end="\r")
                    time.sleep(5)  # 5秒待機
                    my_file = client.files.get(name=my_file.name)

                # Gemini APIを使用して文字起こし
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, my_file]
                )

                # 応答から文字起こしテキストを取得
                transcription = response.text

                # 成功した場合は結果を返す
                return transcription
            except Exception as e:
                retry_count += 1

                # 最大再試行回数に達した場合はエラーをログに記録し、Noneを返す
                if retry_count > self.max_retries:
                    logger.error(f"文字起こしの最大再試行回数に達しました: {e}")
                    return None

                # エラーからretryDelayを抽出
                retry_delay = self._extract_retry_delay_from_error(e)

                # retryDelayが抽出できた場合はそれを使用、できなかった場合は指数バックオフ
                if retry_delay is not None:
                    delay = retry_delay
                    logger.warning(f"文字起こしに失敗しました: {e}")
                    logger.info(f"APIから提供されたクールダウン時間 {delay}秒後に再試行します ({retry_count}/{self.max_retries})")
                else:
                    # 再試行前に待機（指数バックオフ）
                    delay = min(self.retry_delay * (2 ** (retry_count - 1)), self.max_retry_delay)
                    logger.warning(f"文字起こしに失敗しました。{delay}秒後に再試行します ({retry_count}/{self.max_retries}): {e}")

                time.sleep(delay)
        return None

    def _parse_transcription(self, transcription: str, original_media_file: Optional[MediaFile] = None) -> List[TranscriptionSegment]:
        """
        文字起こしテキストをパース

        Args:
            transcription: 文字起こしテキスト
            original_media_file: (Optional) 元のメディアファイルオブジェクト

        Returns:
            文字起こしセグメントのリスト
        """
        # 文字起こしテキストをセグメントに分割
        segments = []
        current_lines = transcription.strip().split('\n')
        idx = 0

        while idx < len(current_lines):
            line = current_lines[idx].strip()

            # 空行はスキップ
            if not line:
                idx += 1
                continue

            try:

                # タイムスタンプと話者、テキストを抽出
                # 例: [00:00:00 - 00:00:10] 話者A: これはテストです。
                segment_match = re.match(r'\[(\d{1,2}:\d{2}:\d{2})\s*-\s*(\d{1,2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.*)', line)

                if segment_match:
                    # セグメント情報を抽出
                    start_str, end_str, speaker_name, text_content = segment_match.groups()
                    start_time = time_str_to_seconds(start_str)
                    end_time = time_str_to_seconds(end_str)
                    speaker = Speaker(id=speaker_name.strip(), name=speaker_name.strip())
                    current_text_content = text_content.strip()

                    # 複数行にわたるテキストの処理
                    while idx + 1 < len(current_lines):
                        next_line = current_lines[idx+1].strip()
                        # 次の行が新しいセグメントの開始でなければ、現在のテキストに追加
                        if not re.match(r'\[(\d{1,2}:\d{2}:\d{2})\s*-\s*(\d{1,2}:\d{2}:\d{2})\]', next_line):
                            current_text_content += " " + next_line
                            idx += 1
                        else:
                            break

                    # セグメントを追加
                    segments.append(TranscriptionSegment(
                        text=current_text_content,
                        start_time=start_time,
                        end_time=end_time,
                        speaker=speaker
                    ))
                elif segments:
                    # 既存のセグメントがあれば、最後のセグメントにテキストを追加
                    segments[-1].text += f" {line}"
                else:
                    # セグメントがまだない場合は、新しいセグメントを作成
                    logger.warning(f"非セグメント行を文字起こし開始時に発見: '{line}'")
                    segments.append(TranscriptionSegment(
                        text=line,
                        start_time=0,
                        end_time=0,
                        speaker=None
                    ))
            except Exception as e:
                logger.warning(f"文字起こし行のパースに失敗しました: {line} - {e}")

            idx += 1

        return segments



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
            start_time_str = format_time(segment.start_time)
            end_time_str = format_time(segment.end_time)

            # 話者
            speaker_str = f"{segment.speaker.name}: " if segment.speaker else ""

            # 行を追加
            lines.append(f"[{start_time_str} - {end_time_str}] {speaker_str}{segment.text}")

        return "\n".join(lines)



# シングルトンインスタンス
transcription_service = TranscriptionService()
