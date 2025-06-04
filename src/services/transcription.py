"""
文字起こしサービス

このモジュールは、音声ファイルの文字起こしに関するサービスを提供します。
Gemini APIを使用して高精度な文字起こしを実現します。
"""
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import re # Added
from google import genai
from ..services.media_processor import media_processor_service # Added

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
        self.media_processor_service = media_processor_service # Added

        # レート制限のための変数
        self.requests_per_minute = config_manager.get("transcription.requests_per_minute", 5)  # デフォルトは1分あたり5リクエスト
        self.request_timestamps = []  # リクエストのタイムスタンプを記録するリスト

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
                myfile = client.files.upload(file=str(file_path))

                # Gemini APIを使用して文字起こし
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, myfile]
                )

                # 応答から文字起こしテキストを取得
                transcription = response.text

                # 成功した場合は結果を返す
                return transcription
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

    def _parse_transcription(self, transcription: str, original_media_file: Optional[MediaFile] = None) -> List[TranscriptionSegment]:
        """
        文字起こしテキストをパース

        Args:
            transcription: 文字起こしテキスト
            original_media_file: (Optional) 元のメディアファイルオブジェクト（ビデオの場合、スクリーンショット処理に使用）

        Returns:
            文字起こしセグメントのリスト
        """
        # スクリーンショットの処理
        processed_transcription = transcription
        if original_media_file and original_media_file.is_video:
            processed_transcription = self._process_screenshots(transcription, original_media_file)

        # 文字起こしテキストをセグメントに分割
        segments = []
        current_lines = processed_transcription.strip().split('\n')
        idx = 0

        while idx < len(current_lines):
            line = current_lines[idx].strip()

            # 空行はスキップ
            if not line:
                idx += 1
                continue

            try:
                # スクリーンショットタグの行はスキップ
                if line.lower().startswith("<screenshot>") or line.lower().startswith("</screenshot>"):
                    idx += 1
                    continue

                # タイムスタンプと話者、テキストを抽出
                # 例: [00:00:00 - 00:00:10] 話者A: これはテストです。
                segment_match = re.match(r'\[(\d{1,2}:\d{2}:\d{2})\s*-\s*(\d{1,2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.*)', line)

                if segment_match:
                    # セグメント情報を抽出
                    start_str, end_str, speaker_name, text_content = segment_match.groups()
                    start_time = self._time_str_to_seconds(start_str)
                    end_time = self._time_str_to_seconds(end_str)
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

    def _process_screenshots(self, transcription: str, original_media_file: MediaFile) -> str:
        """
        文字起こしテキストからスクリーンショット指示を処理し、必要に応じてスクリーンショットを抽出する

        Args:
            transcription: 文字起こしテキスト
            original_media_file: 元のメディアファイルオブジェクト

        Returns:
            スクリーンショット指示を処理した後の文字起こしテキスト
        """
        # スクリーンショットパターンの定義
        screenshot_pattern = re.compile(
            r"<screenshot>\s*\[(\d{2}:\d{2}:\d{2})\]\s*(.*?)\s*</screenshot>",
            re.DOTALL
        )

        # スクリーンショットタグを処理した後のテキスト
        processed_text = transcription

        # スクリーンショットタグを検索
        for match in screenshot_pattern.finditer(transcription):
            # タイムスタンプと説明を抽出
            timestamp_str = match.group(1)
            description = match.group(2).strip()
            timestamp_seconds = self._time_str_to_seconds(timestamp_str)

            # ファイル名の安全な作成
            max_filename_len = 100  # ファイル名の最大長
            safe_description = re.sub(r'[^\w぀-ヿ㐀-䶿一-鿿＀-￯\s-]', '', description).replace(' ', '_')
            safe_description = re.sub(r'_+', '_', safe_description).strip('_')

            if not safe_description:
                safe_description = f"screenshot_{timestamp_str.replace(':', '')}"

            # ファイル名が長すぎる場合は切り詰める
            if len(safe_description.encode('utf-8')) > max_filename_len:
                encoded_desc = safe_description.encode('utf-8')
                safe_description = encoded_desc[:max_filename_len].decode('utf-8', 'ignore')
                if not safe_description:
                    safe_description = f"screenshot_{timestamp_str.replace(':', '')}_truncated"

            # ファイル名を作成
            filename = f"{safe_description}_{timestamp_str.replace(':', '-')}.jpg"

            # ログ出力
            logger.info(f"スクリーンショット指示を検出: 時間={timestamp_str} ({timestamp_seconds}秒), 説明='{description}', ファイル名='{filename}'")
            logger.info(f"スクリーンショット元ファイル: {original_media_file.file_path}")

            # スクリーンショット抽出処理（実際の処理はコメントアウト）
            try:
                # 実際のスクリーンショット抽出処理をここに実装
                # 現在はプレースホルダーとしてログ出力のみ
                logger.info(f"スクリーンショット抽出シミュレーション: '{filename}' を {timestamp_seconds}秒から抽出")

                # 以下は実際の処理例（現在はコメントアウト）
                # image_quality = config_manager.get("video_analysis.image_quality", 3)
                # actual_image_path = media_processor_service.extract_image_at_timestamp(
                #     video_file=original_media_file,
                #     timestamp=timestamp_seconds,
                #     quality=image_quality,
                #     output_filename=filename
                # )
                # if actual_image_path:
                #     logger.info(f"スクリーンショット抽出成功: {actual_image_path}")
                # else:
                #     logger.warning(f"スクリーンショット抽出に失敗した可能性があります: {filename} (パスが返されていません)")
            except Exception as e:
                logger.error(f"スクリーンショット抽出に失敗しました: {filename} - {e}", exc_info=True)

            # スクリーンショットタグを文字起こしテキストから削除
            processed_text = processed_text.replace(match.group(0), "")

        return processed_text

    def _time_str_to_seconds(self, time_str: str) -> float:
        """
        時間文字列を秒に変換

        Args:
            time_str: 時間文字列（HH:MM:SS形式）

        Returns:
            秒数
        """
        parts = time_str.split(':')
        if len(parts) == 3: # HH:MM:SS
            try:
                hours, minutes, seconds = map(float, parts)
                return hours * 3600 + minutes * 60 + seconds
            except ValueError:
                logger.warning(f"HH:MM:SS形式の時刻文字列のパースに失敗しました: {time_str}")
                return 0.0
        elif len(parts) == 2: # MM:SS
            try:
                minutes, seconds = map(float, parts)
                return minutes * 60 + seconds
            except ValueError:
                logger.warning(f"MM:SS形式の時刻文字列のパースに失敗しました: {time_str}")
                return 0.0
        elif len(parts) == 1: # SS
            try:
                return float(parts[0])
            except ValueError:
                logger.warning(f"SS形式の時刻文字列のパースに失敗しました: {time_str}")
                return 0.0
        else:
            # Handle H:MM:SS (single digit hour) which might be common
            if ':' in time_str:
                try:
                    h, m, s = map(float, time_str.split(':'))
                    if time_str.count(':') == 2: # Assume H:MM:SS if three parts after split
                         return h * 3600 + m * 60 + s
                except ValueError:
                    pass # Fall through if this specific parsing fails
            logger.warning(f"予期しない時刻文字列形式です: {time_str}。秒として直接パースするか、0を返します。")
            try:
                return float(time_str) # Try to parse as raw seconds as a last resort
            except ValueError:
                logger.error(f"無効な時刻文字列形式で、パースできません: {time_str}")
                return 0.0 # Default or raise more specific error

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
