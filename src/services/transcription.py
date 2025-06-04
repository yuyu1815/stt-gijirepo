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

    def _parse_transcription(self, transcription: str, original_media_file: Optional[MediaFile] = None) -> List[TranscriptionSegment]: # Modified
        """
        文字起こしテキストをパース
        
        Args:
            transcription: 文字起こしテキスト
            original_media_file: (Optional) 元のメディアファイルオブジェクト（ビデオの場合、スクリーンショット処理に使用）
            
        Returns:
            文字起こしセグメントのリスト
        """
        # --- Screenshot Detection and Action (New) ---
        if original_media_file and original_media_file.is_video:
            # This pattern assumes the description might be multi-line if not careful with prompt.
            # For simplicity, DOTALL is used, but prompt should ideally ensure description is single line or clearly delimited.
            screenshot_pattern = re.compile(
                r"<screenshot>\s*\[(\d{2}:\d{2}:\d{2})\]\s*(.*?)\s*</screenshot>",
                re.DOTALL
            )
            # Operate on the full 'transcription' string before splitting into lines
            # This is important if a screenshot tag spans multiple lines in the raw output
            # However, the prompt for transcription.md aims to put it on its own lines.
            # For robustness, we might iterate matches and then remove them from `transcription`
            # before line-by-line processing for segments.
            # For now, let's assume the prompt works and screenshot tags are on their own lines
            # or handled by the segment parsing logic if they are not removed.

            # The current segment parsing logic might misinterpret screenshot tags as text.
            # A better approach would be to find all screenshot tags, log/process them,
            # and then *remove* them from the transcription string before parsing segments.
            # This avoids screenshot tags being accidentally included in segment text.

            temp_transcription_for_screenshots = transcription # Work on a copy for finding screenshots

            for match in screenshot_pattern.finditer(temp_transcription_for_screenshots):
                timestamp_str = match.group(1)
                description = match.group(2).strip()
                timestamp_seconds = self._time_str_to_seconds(timestamp_str)

                safe_description = re.sub(r'[^\w぀-ヿ㐀-䶿一-鿿＀-￯\s-]', '', description).replace(' ', '_')
                safe_description = re.sub(r'_+', '_', safe_description).strip('_')
                if not safe_description:
                    safe_description = f"screenshot_{timestamp_str.replace(':', '')}"

                max_len = 100
                if len(safe_description.encode('utf-8')) > max_len:
                    safe_description = safe_description[:max_len//3]

                filename = f"{safe_description}.webp"

                logger.info(f"Screenshot instruction pattern found: time={timestamp_str} ({timestamp_seconds}s), desc='{description}', intended_filename='{filename}'")
                logger.info(f"Original media file for screenshot: {original_media_file.file_path}")

                # Placeholder for actual call to media_processor_service
                logger.info(f"Placeholder: Simulating call to extract screenshot '{filename}' at {timestamp_seconds}s from {original_media_file.file_path}.")
                # try:
                #     image_quality = config_manager.get("video_analysis.image_quality", 3)
                #     actual_image_path = self.media_processor_service.extract_image_at_timestamp(
                #         video_file=original_media_file,
                #         timestamp=timestamp_seconds,
                #         quality=image_quality,
                #         output_filename=filename
                #     )
                #     if actual_image_path:
                #         logger.info(f"Successfully triggered screenshot extraction: {actual_image_path}")
                #     else:
                #         logger.warning(f"Screenshot extraction may have failed for {filename} (no path returned).")
                # except Exception as e:
                #     logger.error(f"Failed to trigger screenshot extraction for {filename}: {e}", exc_info=True)
        # --- End of Screenshot Detection and Action ---

        segments = []
        current_lines = transcription.strip().split('\n')
        idx = 0
        while idx < len(current_lines):
            line = current_lines[idx].strip()
            if not line:
                idx += 1
                continue

            # Skip screenshot directive lines from regular segment parsing
            if line.lower().startswith("<screenshot>") or line.lower().startswith("</screenshot>"):
                # We could also add these lines as special segments if needed for display in the final transcript
                # For now, just skipping them as per the requirements (tag itself not included)
                # but the content between them IS the desired output for that part.
                # The prompt implies these tags are markers for Gemini to output structured data,
                # which we've processed above. The actual lines like `<screenshot>` and `[HH:MM:SS]Description`
                # are part of that structure, not part of the spoken text.
                
                # If the prompt transcription.md instructs Gemini to output:
                # الكلام الكلام الكلام <screenshot_instruction>[HH:MM:SS]وصف</screenshot_instruction> الكلام الكلام
                # And Gemini *transforms* this into:
                # الكلام الكلام الكلام
                # <screenshot>
                # [HH:MM:SS]وصف
                # </screenshot>
                # الكلام الكلام
                # Then the screenshot block itself needs to be parsed into a special kind of segment or ignored if already handled.
                # The current screenshot logic above finds these blocks.
                # The question is whether these lines also appear in `current_lines` and need skipping.
                # Let's assume the screenshot block (e.g. <screenshot>, [time]desc, </screenshot>)
                # should be converted into a single placeholder or image reference in the final transcript,
                # or simply logged for action and removed from the textual transcript.
                # The prompt asks for the screenshot tag to be replaced by the <screenshot> block.
                # This means the _parse_transcription should ideally see the output *with* the <screenshot> block.

                # If the line is part of the screenshot block that Gemini is supposed to output:
                if line.lower() == "<screenshot>":
                    # Potentially start a "screenshot" segment or note its presence
                    # For now, we assume the screenshot logic above has handled it, and we just need to not parse these as regular text
                    pass
                elif line.lower() == "</screenshot>":
                    # Potentially end a "screenshot" segment
                    pass
                elif re.match(r'\[\d{2}:\d{2}:\d{2}\].*', line) and \
                     idx > 0 and current_lines[idx-1].lower() == "<screenshot>" and \
                     idx + 1 < len(current_lines) and current_lines[idx+1].lower() == "</screenshot>":
                    # This is the description line inside a screenshot block.
                    # We could create a special segment type for this.
                    # For now, let's just ensure it's not treated as spoken text.
                    # segments.append(TranscriptionSegment(text=line, start_time=segments[-1].end_time if segments else 0, end_time=segments[-1].end_time if segments else 0, speaker=None, is_screenshot_info=True))
                    pass # Already processed by screenshot logic, skip regular parsing
                else:
                    # This case might occur if a line *looks* like a screenshot tag but isn't part of a full block.
                    # Treat as normal text to be safe, or log a warning.
                    logger.debug(f"Line resembling screenshot tag but not fully matched or out of context: {line}")
                    # Fall through to regular parsing below if not explicitly skipped.
                    # To be safe, if it's not part of the main segment structure, it might be appended to previous.
                    pass # Allow it to be processed by the logic below if it's not one of the structural screenshot tags

                # The following lines are from the original Japanese code's parsing logic
            try:
                # タイムスタンプと話者、テキストを抽出
                # 例: [00:00:00 - 00:00:10] 話者A: これはテストです。
                # import re # Already imported at top level
                # Regex from original code: r'\[(\d+:\d+:\d+)\s*-\s*(\d+:\d+:\d+)\]\s*([^:]+):\s*(.*)'
                # Modified to be more flexible with HH:MM:SS or H:MM:SS
                segment_match = re.match(r'\[(\d{1,2}:\d{2}:\d{2})\s*-\s*(\d{1,2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.*)', line)
                
                if segment_match:
                    start_str, end_str, speaker_name, text_content = segment_match.groups()
                    start_time = self._time_str_to_seconds(start_str)
                    end_time = self._time_str_to_seconds(end_str)
                    speaker = Speaker(id=speaker_name.strip(), name=speaker_name.strip())
                    
                    current_text_content = text_content.strip()

                    # Multi-line text accumulation logic from the original user prompt for this function
                    # This needs to be adapted to the Japanese code's style or confirmed if existing logic is sufficient.
                    # The original Japanese code only appends if `match` is None.
                    # The user's new logic for _parse_transcription has more detailed multi-line handling.
                    # Let's try to integrate the spirit of the user's multi-line logic:
                    while idx + 1 < len(current_lines):
                        next_line_content = current_lines[idx+1].strip()
                        # If next line does not look like a new timestamped segment OR a screenshot tag line
                        if not (re.match(r'\[(\d{1,2}:\d{2}:\d{2})\s*-\s*(\d{1,2}:\d{2}:\d{2})\]', next_line_content) or \
                                next_line_content.lower() == "<screenshot>" or \
                                next_line_content.lower() == "</screenshot>" or \
                                (next_line_content.startswith("[") and next_line_content.endswith("]") and ":" in next_line_content and len(next_line_content) < 35 and next_line_content.count(':') == 2) # Heuristic for [HH:MM:SS]Description lines
                               ):
                            current_text_content += " " + next_line_content
                            idx += 1
                        else:
                            break
                    segments.append(TranscriptionSegment(text=current_text_content, start_time=start_time, end_time=end_time, speaker=speaker))

                # Handling for lines that are part of the <screenshot> block textually (as per user prompt's new logic),
                # or other non-standard lines.
                # This part of the logic from the user's prompt might need careful integration
                # with the existing Japanese code's "else: if segments: segments[-1].text += f" {line}""
                elif line.lower() == "<screenshot>" or line.lower() == "</screenshot>" or \
                     (line.startswith("[") and line.endswith("]") and ":" in line and len(line) < 35 and line.count(':') == 2 and \
                      idx > 0 and current_lines[idx-1].lower() == "<screenshot>" and \
                      idx + 1 < len(current_lines) and current_lines[idx+1].lower() == "</screenshot>"):
                    # This is for the textual representation of the screenshot block in the transcript if desired.
                    # The prompt asks for the <screenshot_instruction> to be replaced by this block.
                    # So, these lines should be part of the output.
                    # We can create a segment with no speaker and time matching the previous segment's end.
                    # This makes the screenshot block appear inline with the transcript.
                    effective_start_time = segments[-1].end_time if segments else 0 # Heuristic for timing
                    segments.append(TranscriptionSegment(text=line, start_time=effective_start_time, end_time=effective_start_time, speaker=None))

                elif segments: # Original Japanese code's logic for appending to previous segment
                    segments[-1].text += f" {line}"
                else:
                    # If no segments yet and line doesn't match standard segment or screenshot structure.
                    # This could be preamble, or unexpected content. Create a segment for it.
                    logger.warning(f"非セグメント行を文字起こし開始時に発見: '{line}'")
                    segments.append(TranscriptionSegment(text=line, start_time=0, end_time=0, speaker=None)) # Default speaker, times
            except Exception as e:
                logger.warning(f"文字起こし行のパースに失敗しました: {line} - {e}")
            idx +=1 # Ensure idx increments in all paths through the loop

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