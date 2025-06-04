"""
ハルシネーションチェックサービス

このモジュールは、文字起こし結果のハルシネーション（幻覚）をチェックし、
信頼性を評価するサービスを提供します。
"""
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from google import genai

from ..domain.media import MediaFile
from ..domain.transcription import (
    HallucinationResult, HallucinationSeverity, 
    TranscriptionResult, TranscriptionSegment
)
from ..infrastructure.config import config_manager
from ..infrastructure.logger import logger
from ..infrastructure.storage import storage_manager
from ..utils.parallel import ParallelExecutionMode, parallel_map


class HallucinationService:
    """ハルシネーションチェックサービスクラス"""

    def __init__(self):
        """初期化"""
        self.api_key = config_manager.get_api_key("gemini")
        self.max_retries = config_manager.get("hallucination.max_retries", 3)
        self.retry_delay = config_manager.get("hallucination.retry_delay", 2)
        self.max_retry_delay = config_manager.get("hallucination.max_retry_delay", 30)
        self.prompt_path = config_manager.get_prompt_path("hallucination_check")

        # レート制限のための変数
        self.requests_per_minute = config_manager.get("hallucination.requests_per_minute", 5)  # デフォルトは1分あたり5リクエスト
        self.request_timestamps = []  # リクエストのタイムスタンプを記録するリスト

    def check_hallucination(self, media_file: MediaFile, 
                           transcription_result: TranscriptionResult) -> TranscriptionResult:
        """
        文字起こし結果のハルシネーションをチェック

        Args:
            media_file: メディアファイル
            transcription_result: 文字起こし結果

        Returns:
            ハルシネーションチェック結果を含む文字起こし結果
        """
        logger.info(f"ハルシネーションチェックを開始します: {media_file.file_path}")

        # 文字起こしが完了していない場合はエラー
        if not transcription_result.is_completed:
            logger.error(f"文字起こしが完了していません: {transcription_result.source_file}")
            return transcription_result

        # セグメントがない場合は何もしない
        if not transcription_result.segments:
            logger.warning(f"文字起こしセグメントがありません: {transcription_result.source_file}")
            return transcription_result

        try:
            # 長時間メディアの場合はチャンク処理
            if media_file.is_long_media and media_file.has_chunks:
                logger.info(f"長時間メディアのハルシネーションチェックをチャンク処理します: {media_file.file_path}")
                hallucination_results = self._check_hallucination_chunks(media_file, transcription_result)
            else:
                # 単一ファイルのハルシネーションチェック
                logger.info(f"単一ファイルのハルシネーションチェックを実行します: {media_file.file_path}")
                hallucination_results = self._check_hallucination_single_file(
                    media_file.file_path, transcription_result.segments
                )

            # 結果を設定
            transcription_result.hallucination_results = hallucination_results

            # 結果を保存
            self._save_hallucination_results(transcription_result)

            logger.info(f"ハルシネーションチェックが完了しました: {media_file.file_path}")
            return transcription_result
        except Exception as e:
            logger.error(f"ハルシネーションチェックに失敗しました: {e}")
            return transcription_result

    def _check_hallucination_chunks(self, media_file: MediaFile, 
                                   transcription_result: TranscriptionResult) -> List[HallucinationResult]:
        """
        チャンクに分割されたメディアファイルのハルシネーションをチェック

        Args:
            media_file: チャンクに分割されたメディアファイル
            transcription_result: 文字起こし結果

        Returns:
            ハルシネーションチェック結果のリスト
        """
        # チャンクがない場合はエラー
        if not media_file.has_chunks:
            logger.error(f"チャンクが見つかりません: {media_file.file_path}")
            return []

        # チャンクごとにセグメントをグループ化
        chunk_segments = self._group_segments_by_chunks(transcription_result.segments, media_file.chunks)

        # 各チャンクを並列処理
        chunk_results = []
        for i, (chunk, segments) in enumerate(chunk_segments.items()):
            logger.info(f"チャンク {i} のハルシネーションチェックを実行します: {chunk.file_path}")
            results = self._check_hallucination_single_file(chunk.file_path, segments)
            chunk_results.extend(results)

        logger.info(f"{len(media_file.chunks)}個のチャンクのハルシネーションチェックが完了しました: {media_file.file_path}")
        return chunk_results

    def _group_segments_by_chunks(self, segments: List[TranscriptionSegment], 
                                 chunks: List) -> Dict:
        """
        セグメントをチャンクごとにグループ化

        Args:
            segments: 文字起こしセグメントのリスト
            chunks: チャンクのリスト

        Returns:
            チャンクごとのセグメントの辞書
        """
        chunk_segments = {chunk: [] for chunk in chunks}

        for segment in segments:
            # セグメントが属するチャンクを特定
            for chunk in chunks:
                if chunk.start_time <= segment.start_time < chunk.end_time:
                    chunk_segments[chunk].append(segment)
                    break

        return chunk_segments

    def _check_hallucination_single_file(self, file_path: Union[str, Path], 
                                        segments: List[TranscriptionSegment]) -> List[HallucinationResult]:
        """
        単一ファイルのハルシネーションをチェック

        Args:
            file_path: 音声ファイルのパス
            segments: 文字起こしセグメントのリスト

        Returns:
            ハルシネーションチェック結果のリスト
        """
        file_path = Path(file_path)

        # プロンプトを読み込む
        prompt = self._load_hallucination_check_prompt()

        # セグメントをテキストに変換
        transcription_text = self._format_segments_for_check(segments)

        # Gemini APIでハルシネーションチェック
        check_result = self._check_with_gemini(file_path, transcription_text, prompt)

        # チェック結果をパース
        hallucination_results = self._parse_hallucination_check(check_result, segments)

        logger.info(f"ハルシネーションチェックが完了しました: {file_path} ({len(hallucination_results)}個の結果)")
        return hallucination_results

    def _load_hallucination_check_prompt(self) -> str:
        """
        ハルシネーションチェックプロンプトを読み込む

        Returns:
            プロンプトテキスト
        """
        if not self.prompt_path.exists():
            logger.warning(f"プロンプトファイルが見つかりません: {self.prompt_path}")
            return "音声ファイルと文字起こし結果を比較し、ハルシネーション（幻覚）がないか確認してください。"

        return storage_manager.load_text(self.prompt_path)

    def _format_segments_for_check(self, segments: List[TranscriptionSegment]) -> str:
        """
        チェック用にセグメントをフォーマット

        Args:
            segments: 文字起こしセグメントのリスト

        Returns:
            フォーマットされたテキスト
        """
        lines = []

        for segment in segments:
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

    def _check_with_gemini(self, file_path: Path, transcription_text: str, prompt: str) -> str:
        """
        Gemini APIを使用してハルシネーションチェック

        Args:
            file_path: 音声ファイルのパス
            transcription_text: 文字起こしテキスト
            prompt: プロンプトテキスト

        Returns:
            ハルシネーションチェック結果
        """
        # APIキーが設定されていない場合はエラー
        if not self.api_key:
            logger.error("Gemini APIキーが設定されていません")
            raise ValueError("Gemini APIキーが設定されていません")

        # Gemini APIの設定
        client = genai.Client(api_key=self.api_key)
        model_name = config_manager.get("gemini.model", "gemini-2.0-flash")

        logger.info(f"Gemini APIでハルシネーションチェックを実行します: {file_path}")

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
                    time.sleep(5)
                    my_file = client.files.get(name=my_file.name)

                # Gemini APIを使用してハルシネーションチェック
                # プロンプトと音声ファイルに加えて、文字起こしテキストも送信
                contents = [
                    prompt,
                    f"以下は文字起こし結果です：\n\n{transcription_text}",
                    my_file
                ]

                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )

                # 応答からハルシネーションチェック結果を取得
                check_result = response.text

                # 成功した場合は結果を返す
                return check_result
            except Exception as e:
                retry_count += 1

                # 最大再試行回数に達した場合はエラーをログに記録し、例外を発生
                if retry_count > self.max_retries:
                    logger.error(f"ハルシネーションチェックの最大再試行回数に達しました: {e}")
                    raise

                # 再試行前に待機（指数バックオフ）
                delay = min(self.retry_delay * (2 ** (retry_count - 1)), self.max_retry_delay)
                logger.warning(f"ハルシネーションチェックに失敗しました。{delay}秒後に再試行します ({retry_count}/{self.max_retries}): {e}")
                time.sleep(delay)

    def _parse_hallucination_check(self, check_result: str, 
                                  segments: List[TranscriptionSegment]) -> List[HallucinationResult]:
        """
        ハルシネーションチェック結果をパース

        Args:
            check_result: ハルシネーションチェック結果
            segments: 文字起こしセグメントのリスト

        Returns:
            ハルシネーション結果のリスト
        """
        hallucination_results = []

        # 「ハルシネーションは検出されませんでした」という文字列がある場合は全てNONEとする
        if "ハルシネーションは検出されませんでした" in check_result:
            for segment in segments:
                result = HallucinationResult(
                    segment=segment,
                    severity=HallucinationSeverity.NONE
                )
                hallucination_results.append(result)
            return hallucination_results

        # 結果をブロックに分割
        blocks = check_result.split("\n\n")

        for block in blocks:
            if not block.strip():
                continue

            lines = block.strip().split("\n")
            if len(lines) < 2:
                continue

            try:
                # セグメント行を抽出
                segment_line = None
                for line in lines:
                    if line.startswith("SEGMENT:"):
                        segment_line = line[len("SEGMENT:"):].strip()
                        break

                if not segment_line:
                    continue

                # 対応するセグメントを検索
                target_segment = None
                for segment in segments:
                    segment_text = self._format_segment_for_comparison(segment)
                    if segment_text in segment_line or segment_line in segment_text:
                        target_segment = segment
                        break

                if not target_segment:
                    logger.warning(f"対応するセグメントが見つかりません: {segment_line}")
                    continue

                # 重大度を抽出
                severity_str = None
                for line in lines:
                    if line.startswith("SEVERITY:"):
                        severity_str = line[len("SEVERITY:"):].strip()
                        break

                severity = HallucinationSeverity.NONE
                if severity_str:
                    if severity_str == "LOW":
                        severity = HallucinationSeverity.LOW
                    elif severity_str == "MEDIUM":
                        severity = HallucinationSeverity.MEDIUM
                    elif severity_str == "HIGH":
                        severity = HallucinationSeverity.HIGH

                # 理由を抽出
                reason = None
                for line in lines:
                    if line.startswith("REASON:"):
                        reason = line[len("REASON:"):].strip()
                        break

                # 修正テキストを抽出
                corrected_text = None
                for line in lines:
                    if line.startswith("CORRECTED:"):
                        corrected_text = line[len("CORRECTED:"):].strip()
                        break

                # ハルシネーション結果を作成
                result = HallucinationResult(
                    segment=target_segment,
                    severity=severity,
                    reason=reason,
                    corrected_text=corrected_text
                )

                hallucination_results.append(result)
            except Exception as e:
                logger.warning(f"ハルシネーションチェック結果のパースに失敗しました: {block} - {e}")

        # 結果がない場合は全てNONEとする
        if not hallucination_results:
            for segment in segments:
                result = HallucinationResult(
                    segment=segment,
                    severity=HallucinationSeverity.NONE
                )
                hallucination_results.append(result)

        return hallucination_results

    def _format_segment_for_comparison(self, segment: TranscriptionSegment) -> str:
        """
        比較用にセグメントをフォーマット

        Args:
            segment: 文字起こしセグメント

        Returns:
            フォーマットされたテキスト
        """
        # 時間をフォーマット
        start_time_str = self._format_time(segment.start_time)
        end_time_str = self._format_time(segment.end_time)

        # 話者
        speaker_str = f"{segment.speaker.name}: " if segment.speaker else ""

        return f"[{start_time_str} - {end_time_str}] {speaker_str}{segment.text}"

    def _save_hallucination_results(self, result: TranscriptionResult) -> Path:
        """
        ハルシネーションチェック結果を保存

        Args:
            result: 文字起こし結果（ハルシネーションチェック結果を含む）

        Returns:
            保存したファイルのパス
        """
        # 出力ディレクトリを取得
        output_dir = storage_manager.get_output_dir("reports")

        # ファイル名を生成
        file_name = f"{result.source_file.stem}_hallucination_report.txt"
        output_path = output_dir / file_name

        # テキスト形式で保存
        content = self._format_hallucination_results_for_output(result)
        storage_manager.save_text(content, output_path)

        logger.info(f"ハルシネーションチェック結果を保存しました: {output_path}")
        return output_path

    def _format_hallucination_results_for_output(self, result: TranscriptionResult) -> str:
        """
        出力用にハルシネーションチェック結果をフォーマット

        Args:
            result: 文字起こし結果（ハルシネーションチェック結果を含む）

        Returns:
            フォーマットされたテキスト
        """
        lines = []

        # ヘッダー
        lines.append(f"# ハルシネーションチェック結果: {result.source_file.name}")
        lines.append(f"# 生成日時: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 要約
        total_segments = len(result.segments)
        hallucination_count = sum(1 for h in result.hallucination_results if h.severity != HallucinationSeverity.NONE)

        lines.append(f"## 要約")
        lines.append(f"- 総セグメント数: {total_segments}")
        lines.append(f"- ハルシネーション検出数: {hallucination_count}")
        lines.append(f"- ハルシネーション率: {hallucination_count / total_segments * 100:.2f}%")
        lines.append("")

        # 重大度別の集計
        severity_counts = {
            HallucinationSeverity.LOW: 0,
            HallucinationSeverity.MEDIUM: 0,
            HallucinationSeverity.HIGH: 0
        }

        for result in result.hallucination_results:
            if result.severity in severity_counts:
                severity_counts[result.severity] += 1

        lines.append(f"## 重大度別の集計")
        lines.append(f"- 低（LOW）: {severity_counts[HallucinationSeverity.LOW]}")
        lines.append(f"- 中（MEDIUM）: {severity_counts[HallucinationSeverity.MEDIUM]}")
        lines.append(f"- 高（HIGH）: {severity_counts[HallucinationSeverity.HIGH]}")
        lines.append("")

        # 詳細結果
        lines.append(f"## 詳細結果")

        for i, hallucination in enumerate(result.hallucination_results):
            if hallucination.severity == HallucinationSeverity.NONE:
                continue

            segment = hallucination.segment

            # 時間をフォーマット
            start_time_str = self._format_time(segment.start_time)
            end_time_str = self._format_time(segment.end_time)

            # 話者
            speaker_str = f"{segment.speaker.name}: " if segment.speaker else ""

            lines.append(f"### ハルシネーション {i+1}")
            lines.append(f"- 時間: [{start_time_str} - {end_time_str}]")
            lines.append(f"- 話者: {speaker_str.strip(':')}")
            lines.append(f"- 重大度: {hallucination.severity.name}")
            lines.append(f"- 原文: {segment.text}")

            if hallucination.reason:
                lines.append(f"- 理由: {hallucination.reason}")

            if hallucination.corrected_text:
                lines.append(f"- 修正文: {hallucination.corrected_text}")

            lines.append("")

        return "\n".join(lines)


# シングルトンインスタンス
hallucination_service = HallucinationService()
