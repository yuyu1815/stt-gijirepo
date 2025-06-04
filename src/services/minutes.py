"""
議事録生成サービス

このモジュールは、文字起こし結果から構造化された議事録を生成するサービスを提供します。
"""
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..domain.media import ExtractedImage, MediaFile
from ..domain.minutes import (
    GlossaryItem, Minutes, MinutesContent, MinutesFormat, 
    MinutesHeading, MinutesSection, MinutesTask
)
from ..domain.transcription import TranscriptionResult
from ..infrastructure.config import config_manager
from ..infrastructure.logger import logger
from ..infrastructure.storage import storage_manager


class MinutesGeneratorService:
    """議事録生成サービスクラス"""

    def __init__(self):
        """初期化"""
        self.api_key = config_manager.get_api_key("gemini")
        self.max_retries = config_manager.get("minutes.max_retries", 3)
        self.retry_delay = config_manager.get("minutes.retry_delay", 2)
        self.max_retry_delay = config_manager.get("minutes.max_retry_delay", 30)
        self.prompt_path = config_manager.get_prompt_path("minutes_detailed")
        self.summary_prompt_path = config_manager.get_prompt_path("summary")

        # レート制限のための変数
        self.requests_per_minute = config_manager.get("minutes.requests_per_minute", 5)  # デフォルトは1分あたり5リクエスト
        self.request_timestamps = []  # リクエストのタイムスタンプを記録するリスト

    def generate_minutes(self, transcription_result: TranscriptionResult, 
                        media_file: MediaFile, 
                        extracted_images: Optional[List[ExtractedImage]] = None,
                        video_analysis_result: Optional[Dict] = None) -> Minutes:
        """
        文字起こし結果から議事録を生成

        Args:
            transcription_result: 文字起こし結果
            media_file: メディアファイル
            extracted_images: 抽出された画像のリスト（オプション）
            video_analysis_result: 動画分析結果（オプション）

        Returns:
            生成された議事録
        """
        logger.info(f"議事録生成を開始します: {transcription_result.source_file}")

        # 文字起こしが完了していない場合はエラー
        if not transcription_result.is_completed:
            logger.error(f"文字起こしが完了していません: {transcription_result.source_file}")
            raise ValueError(f"文字起こしが完了していません: {transcription_result.source_file}")

        try:
            # 議事録の基本情報を設定
            minutes = self._initialize_minutes(transcription_result, media_file)

            # 議事録の内容を生成
            minutes = self._generate_minutes_content(minutes, transcription_result, extracted_images, video_analysis_result)

            # 議事録を保存
            output_path = self._save_minutes(minutes)
            minutes.output_path = output_path

            logger.info(f"議事録生成が完了しました: {output_path}")
            return minutes
        except Exception as e:
            logger.error(f"議事録生成に失敗しました: {e}")
            raise

    def _initialize_minutes(self, transcription_result: TranscriptionResult, 
                           media_file: MediaFile) -> Minutes:
        """
        議事録の基本情報を初期化

        Args:
            transcription_result: 文字起こし結果
            media_file: メディアファイル

        Returns:
            初期化された議事録
        """
        # ファイル名から日付情報を抽出（実際の実装では、より高度な日付抽出を行う）
        date = self._extract_date_from_filename(media_file.file_path)

        # タイトルを生成
        title = f"{media_file.file_path.stem} 議事録"

        # 空の議事録コンテンツを作成
        content = MinutesContent()

        # 議事録オブジェクトを作成
        minutes = Minutes(
            title=title,
            date=date,
            content=content,
            source_transcription=transcription_result,
            format=MinutesFormat.MARKDOWN
        )

        return minutes

    def _extract_date_from_filename(self, file_path: Path) -> datetime:
        """
        ファイル名から日付情報を抽出

        Args:
            file_path: ファイルパス

        Returns:
            抽出された日付、抽出できない場合は現在の日付
        """
        # 実際の実装では、ファイル名のパターンに基づいて日付を抽出
        # ここでは簡易的に現在の日付を返す
        return datetime.now()

    def _generate_minutes_content(self, minutes: Minutes, 
                                 transcription_result: TranscriptionResult,
                                 extracted_images: Optional[List[ExtractedImage]] = None,
                                 video_analysis_result: Optional[Dict] = None) -> Minutes:
        """
        議事録の内容を生成

        Args:
            minutes: 議事録
            transcription_result: 文字起こし結果
            extracted_images: 抽出された画像のリスト（オプション）
            video_analysis_result: 動画分析結果（オプション）

        Returns:
            内容が生成された議事録
        """
        # プロンプトを読み込む
        prompt = self._load_minutes_prompt()

        # Gemini APIで議事録内容を生成
        minutes_content = self._generate_with_gemini(transcription_result, prompt, extracted_images, video_analysis_result)

        # 生成された内容を議事録に設定
        minutes = self._parse_minutes_content(minutes, minutes_content)

        # 画像を追加
        if extracted_images:
            for image in extracted_images:
                minutes.add_image(image)

        return minutes

    def _load_minutes_prompt(self) -> str:
        """
        議事録生成プロンプトを読み込む

        Returns:
            プロンプトテキスト
        """
        if not self.prompt_path.exists():
            logger.warning(f"プロンプトファイルが見つかりません: {self.prompt_path}")
            return "文字起こし結果から議事録を生成してください。要約、重要ポイント、タスク、用語集を含めてください。"

        return storage_manager.load_text(self.prompt_path)

    def _generate_with_gemini(self, transcription_result: TranscriptionResult, 
                             prompt: str,
                             extracted_images: Optional[List[ExtractedImage]] = None,
                             video_analysis_result: Optional[Dict] = None) -> str:
        """
        Gemini APIを使用して議事録内容を生成

        Args:
            transcription_result: 文字起こし結果
            prompt: プロンプトテキスト
            extracted_images: 抽出された画像のリスト（オプション）
            video_analysis_result: 動画分析結果（オプション）

        Returns:
            生成された議事録内容
        """
        # APIキーが設定されていない場合はエラー
        if not self.api_key:
            logger.error("Gemini APIキーが設定されていません")
            raise ValueError("Gemini APIキーが設定されていません")

        # 文字起こしテキストを取得
        transcription_text = transcription_result.full_text

        # 動画分析結果がある場合は、プロンプトに追加情報を含める
        if video_analysis_result:
            prompt += f"\n\n動画分析結果:\n{video_analysis_result.get('summary', '')}"

            if video_analysis_result.get('topics'):
                prompt += f"\n\nトピック:\n" + "\n".join([f"- {topic}" for topic in video_analysis_result.get('topics', [])])

            if video_analysis_result.get('key_points'):
                prompt += f"\n\n重要ポイント:\n" + "\n".join([f"- {point}" for point in video_analysis_result.get('key_points', [])])

        # Gemini APIの設定
        from google import genai
        client = genai.Client(api_key=self.api_key)
        model_name = config_manager.get("gemini.model", "gemini-2.0-flash")

        logger.info(f"Gemini APIで議事録内容を生成します: {transcription_result.source_file}")

        # 再試行メカニズム
        retry_count = 0
        while retry_count <= self.max_retries:
            try:
                # レート制限をチェック
                self._check_rate_limit()

                # リクエストのタイムスタンプを記録
                self.request_timestamps.append(time.time())

                # コンテンツの準備
                contents = [
                    prompt,
                    f"以下は文字起こし結果です：\n\n{transcription_text}"
                ]

                # 抽出された画像がある場合は追加
                if extracted_images and len(extracted_images) > 0:
                    image_descriptions = []
                    for img in extracted_images:
                        image_descriptions.append(f"- 画像: {img.file_path.name} (タイムスタンプ: {self._format_time(img.timestamp)})")
                        # 画像ファイルをアップロード
                        try:
                            image_file = client.files.upload(file=str(img.file_path))
                            contents.append(image_file)
                        except Exception as e:
                            logger.warning(f"画像のアップロードに失敗しました: {img.file_path} - {e}")

                    if image_descriptions:
                        contents.append(f"以下は抽出された画像です：\n\n" + "\n".join(image_descriptions))

                # Gemini APIを使用して議事録内容を生成
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )

                # 応答から議事録内容を取得
                minutes_content = response.text

                # 成功した場合は結果を返す
                return minutes_content
            except Exception as e:
                retry_count += 1

                # 最大再試行回数に達した場合はエラーを発生
                if retry_count > self.max_retries:
                    logger.error(f"議事録生成の最大再試行回数に達しました: {e}")
                    raise

                # 再試行前に待機（指数バックオフ）
                delay = min(self.retry_delay * (2 ** (retry_count - 1)), self.max_retry_delay)
                logger.warning(f"議事録生成に失敗しました。{delay}秒後に再試行します ({retry_count}/{self.max_retries}): {e}")
                time.sleep(delay)

    def _generate_mock_minutes(self, transcription_result: TranscriptionResult,
                              extracted_images: Optional[List[ExtractedImage]] = None,
                              video_analysis_result: Optional[Dict] = None) -> str:
        """
        モック議事録内容を生成（実際の実装では削除）

        Args:
            transcription_result: 文字起こし結果
            extracted_images: 抽出された画像のリスト（オプション）
            video_analysis_result: 動画分析結果（オプション）

        Returns:
            モック議事録内容
        """
        # 実際の実装では削除

        # 基本情報
        title = f"{transcription_result.source_file.stem} 議事録"
        date = datetime.now().strftime("%Y-%m-%d")

        # 要約
        summary = f"これは{transcription_result.source_file.stem}に関する議事録です。これはモックの要約です。実際の実装では、Gemini APIを使用して文字起こし結果から要約を生成します。"

        # 本文
        content = """
## 議事内容

### 1. はじめに
- これはモックの議事録内容です。
- 実際の実装では、Gemini APIを使用して文字起こし結果から議事録を生成します。

### 2. 主要な議題
- 議題1: モック議題
- 議題2: サンプル議題
- 議題3: テスト議題

### 3. 議論
- 議論ポイント1: これはモックの議論ポイントです。
- 議論ポイント2: 実際の実装では、文字起こし結果から議論ポイントを抽出します。
- 議論ポイント3: 議事録は構造化された形式で生成されます。
"""

        # 重要ポイント
        important_points = """
## 重要ポイント
- 重要ポイント1: これはモックの重要ポイントです。
- 重要ポイント2: 実際の実装では、Gemini APIを使用して重要ポイントを抽出します。
- 重要ポイント3: 文字起こし結果から重要なポイントが抽出されます。
"""

        # タスク・宿題
        tasks = """
## タスク・宿題
- タスク1: これはモックのタスクです。担当: 山田
- タスク2: 実際の実装では、文字起こし結果からタスクを抽出します。期限: 2023-12-31
- タスク3: タスクには担当者や期限などの情報が含まれます。
"""

        # 用語集
        glossary = """
## 用語集
- 用語1: これはモックの用語説明です。
- 用語2: 実際の実装では、文字起こし結果から専門用語を抽出し、説明を生成します。
- 用語3: 用語集は議事録の理解を助けるために生成されます。
"""

        # 画像セクション
        images_section = ""
        if extracted_images:
            images_section = "\n## 画像\n"
            for i, image in enumerate(extracted_images):
                timestamp_str = self._format_time(image.timestamp)
                images_section += f"\n### 画像 {i+1}: {timestamp_str}\n"
                images_section += f"![画像 {i+1}]({image.file_path.as_posix()})\n"

                # 動画分析結果がある場合は、画像の説明を追加
                if video_analysis_result and "image_descriptions" in video_analysis_result:
                    image_key = str(image.file_path)
                    if image_key in video_analysis_result["image_descriptions"]:
                        desc = video_analysis_result["image_descriptions"][image_key]
                        # より詳細な画像説明を生成
                        images_section += f"\n#### 画像の説明\n{desc.get('description', '')}\n"

                        # 画像が示す授業内容との関連性
                        if "importance" in desc:
                            importance = desc.get("importance", "UNKNOWN")
                            images_section += f"\n#### 重要度\n{importance}\n"

                        # 画像のタイプ情報があれば追加
                        if "type" in desc:
                            img_type = desc.get("type", "OTHER")
                            images_section += f"\n#### 画像タイプ\n{img_type}\n"

                        # 授業内容との関連性
                        images_section += f"\n#### 授業内容との関連性\nこの画像は{timestamp_str}時点の授業内容を視覚的に表しています。\n"
                    else:
                        images_section += "\n画像の説明がありません。この画像は授業の視覚的な補足資料として活用できます。\n"
                else:
                    images_section += "\n画像の説明がありません。この画像は授業の視覚的な補足資料として活用できます。\n"

        # 全体を結合
        return f"""# {title}
日付: {date}

## 要約
{summary}

{content}

{important_points}

{tasks}

{glossary}

{images_section}
"""

    def _parse_minutes_content(self, minutes: Minutes, content: str) -> Minutes:
        """
        生成された議事録内容を解析して議事録オブジェクトに設定

        Args:
            minutes: 議事録
            content: 生成された議事録内容

        Returns:
            内容が設定された議事録
        """
        # 各セクションを抽出
        sections = self._extract_sections(content)

        # 要約を設定
        if "要約" in sections:
            minutes.add_paragraph(MinutesSection.SUMMARY, sections["要約"])

        # 重要ポイントを設定
        if "重要ポイント" in sections:
            minutes.add_paragraph(MinutesSection.IMPORTANT_POINTS, sections["重要ポイント"])

        # 本文を設定
        if "議事内容" in sections:
            minutes.add_paragraph(MinutesSection.CONTENT, sections["議事内容"])

        # 見出しを抽出して設定
        headings = self._extract_headings(content)
        for heading in headings:
            minutes.add_heading(heading)

        # タスク・宿題を抽出して設定
        tasks = self._extract_tasks(content)
        for task in tasks:
            minutes.add_task(task)

        # 用語集を抽出して設定
        glossary_items = self._extract_glossary(content)
        for item in glossary_items:
            minutes.add_glossary_item(item)

        return minutes

    def _extract_sections(self, content: str) -> Dict[str, str]:
        """
        議事録内容から各セクションを抽出

        Args:
            content: 議事録内容

        Returns:
            セクション名とテキストの辞書
        """
        sections = {}

        # セクションを抽出（## で始まる行をセクションの開始とみなす）
        import re
        section_pattern = r"## ([^\n]+)\n(.*?)(?=\n## |$)"
        matches = re.findall(section_pattern, content, re.DOTALL)

        for section_name, section_content in matches:
            sections[section_name.strip()] = section_content.strip()

        return sections

    def _extract_headings(self, content: str) -> List[MinutesHeading]:
        """
        議事録内容から見出しを抽出

        Args:
            content: 議事録内容

        Returns:
            見出しのリスト
        """
        headings = []

        # 見出しを抽出（#で始まる行）
        import re
        heading_pattern = r"(#{1,6}) ([^\n]+)"
        matches = re.findall(heading_pattern, content)

        for hashes, text in matches:
            level = len(hashes)
            heading = MinutesHeading(
                text=text.strip(),
                level=level
            )
            headings.append(heading)

        return headings

    def _extract_tasks(self, content: str) -> List[MinutesTask]:
        """
        議事録内容からタスク・宿題を抽出

        Args:
            content: 議事録内容

        Returns:
            タスク・宿題のリスト
        """
        tasks = []

        # タスクセクションを探す
        import re
        task_section_pattern = r"## タスク・宿題\n(.*?)(?=\n## |$)"
        task_section_match = re.search(task_section_pattern, content, re.DOTALL)

        if task_section_match:
            task_section = task_section_match.group(1)

            # タスクを抽出（- で始まる行）
            task_pattern = r"- ([^\n]+)"
            task_matches = re.findall(task_pattern, task_section)

            for task_text in task_matches:
                # 担当者と期限を抽出
                assignee = None
                due_date = None

                assignee_match = re.search(r"担当: ([^,\.]+)", task_text)
                if assignee_match:
                    assignee = assignee_match.group(1).strip()

                due_date_match = re.search(r"期限: (\d{4}-\d{2}-\d{2})", task_text)
                if due_date_match:
                    due_date_str = due_date_match.group(1)
                    try:
                        due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
                    except ValueError:
                        pass

                task = MinutesTask(
                    description=task_text.strip(),
                    assignee=assignee,
                    due_date=due_date
                )
                tasks.append(task)

        return tasks

    def _extract_glossary(self, content: str) -> List[GlossaryItem]:
        """
        議事録内容から用語集を抽出

        Args:
            content: 議事録内容

        Returns:
            用語集のリスト
        """
        glossary_items = []

        # 用語集セクションを探す
        import re
        glossary_section_pattern = r"## 用語集\n(.*?)(?=\n## |$)"
        glossary_section_match = re.search(glossary_section_pattern, content, re.DOTALL)

        if glossary_section_match:
            glossary_section = glossary_section_match.group(1)

            # 用語を抽出（- で始まる行）
            glossary_pattern = r"- ([^:]+): ([^\n]+)"
            glossary_matches = re.findall(glossary_pattern, glossary_section)

            for term, definition in glossary_matches:
                item = GlossaryItem(
                    term=term.strip(),
                    definition=definition.strip()
                )
                glossary_items.append(item)

        return glossary_items

    def _save_minutes(self, minutes: Minutes) -> Path:
        """
        議事録を保存

        Args:
            minutes: 議事録

        Returns:
            保存したファイルのパス
        """
        # 出力ディレクトリを取得
        output_dir = storage_manager.get_output_dir("minutes")

        # ファイル名を生成
        file_name = f"{minutes.source_transcription.source_file.stem}_minutes.md"
        output_path = output_dir / file_name

        # Markdown形式で保存
        content = self._format_minutes_for_output(minutes)
        storage_manager.save_text(content, output_path)

        logger.info(f"議事録を保存しました: {output_path}")
        return output_path

    def _format_minutes_for_output(self, minutes: Minutes) -> str:
        """
        出力用に議事録をフォーマット

        Args:
            minutes: 議事録

        Returns:
            フォーマットされたテキスト
        """
        lines = []

        # ヘッダー
        lines.append(f"# {minutes.title}")
        lines.append(f"日付: {minutes.date.strftime('%Y-%m-%d')}")
        if minutes.lecturer:
            lines.append(f"講師: {minutes.lecturer}")
        if minutes.subject:
            lines.append(f"科目: {minutes.subject}")
        if minutes.attendees:
            lines.append(f"出席者: {', '.join(minutes.attendees)}")
        lines.append("")

        # 要約
        if MinutesSection.SUMMARY in minutes.content.paragraphs:
            lines.append("## 要約")
            for paragraph in minutes.content.paragraphs[MinutesSection.SUMMARY]:
                lines.append(paragraph)
            lines.append("")

        # 本文
        if MinutesSection.CONTENT in minutes.content.paragraphs:
            lines.append("## 議事内容")
            for paragraph in minutes.content.paragraphs[MinutesSection.CONTENT]:
                lines.append(paragraph)
            lines.append("")

        # 重要ポイント
        if MinutesSection.IMPORTANT_POINTS in minutes.content.paragraphs:
            lines.append("## 重要ポイント")
            for paragraph in minutes.content.paragraphs[MinutesSection.IMPORTANT_POINTS]:
                lines.append(paragraph)
            lines.append("")

        # タスク・宿題
        if minutes.has_tasks:
            lines.append("## タスク・宿題")
            for task in minutes.content.tasks:
                task_line = f"- {task.description}"
                if task.assignee:
                    task_line += f" 担当: {task.assignee}"
                if task.due_date:
                    task_line += f" 期限: {task.due_date.strftime('%Y-%m-%d')}"
                lines.append(task_line)
            lines.append("")

        # 用語集
        if minutes.has_glossary:
            lines.append("## 用語集")
            for item in minutes.content.glossary:
                lines.append(f"- {item.term}: {item.definition}")
            lines.append("")

        # 画像
        if minutes.has_images:
            lines.append("## 画像")

            # タイムスタンプでソート
            sorted_images = sorted(minutes.content.images, key=lambda img: img.timestamp)

            for i, image in enumerate(sorted_images):
                timestamp_str = self._format_time(image.timestamp)
                lines.append(f"### 画像 {i+1}: {timestamp_str}")
                lines.append(f"![画像 {i+1}]({image.file_path.as_posix()})")

                if image.description:
                    lines.append("")
                    lines.append(image.description)

                lines.append("")

        return "\n".join(lines)

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

    def generate_summary(self, transcription_result: TranscriptionResult) -> str:
        """
        文字起こし結果から要約を生成

        Args:
            transcription_result: 文字起こし結果

        Returns:
            生成された要約
        """
        logger.info(f"要約生成を開始します: {transcription_result.source_file}")

        # 文字起こしが完了していない場合はエラー
        if not transcription_result.is_completed:
            logger.error(f"文字起こしが完了していません: {transcription_result.source_file}")
            raise ValueError(f"文字起こしが完了していません: {transcription_result.source_file}")

        try:
            # プロンプトを読み込む
            prompt = self._load_summary_prompt()

            # Gemini APIで要約を生成
            summary = self._generate_summary_with_gemini(transcription_result, prompt)

            logger.info(f"要約生成が完了しました: {transcription_result.source_file}")
            return summary
        except Exception as e:
            logger.error(f"要約生成に失敗しました: {e}")
            raise

    def _load_summary_prompt(self) -> str:
        """
        要約生成プロンプトを読み込む

        Returns:
            プロンプトテキスト
        """
        if not self.summary_prompt_path.exists():
            logger.warning(f"プロンプトファイルが見つかりません: {self.summary_prompt_path}")
            return "文字起こし結果を簡潔に要約してください。"

        return storage_manager.load_text(self.summary_prompt_path)

    def _generate_summary_with_gemini(self, transcription_result: TranscriptionResult, prompt: str) -> str:
        """
        Gemini APIを使用して要約を生成

        Args:
            transcription_result: 文字起こし結果
            prompt: プロンプトテキスト

        Returns:
            生成された要約
        """
        # APIキーが設定されていない場合はエラー
        if not self.api_key:
            logger.error("Gemini APIキーが設定されていません")
            raise ValueError("Gemini APIキーが設定されていません")

        # 文字起こしテキストを取得
        transcription_text = transcription_result.full_text

        # Gemini APIの設定
        from google import genai
        client = genai.Client(api_key=self.api_key)
        model_name = config_manager.get("gemini.model", "gemini-2.0-flash")

        logger.info(f"Gemini APIで要約を生成します: {transcription_result.source_file}")

        # 再試行メカニズム
        retry_count = 0
        while retry_count <= self.max_retries:
            try:
                # レート制限をチェック
                self._check_rate_limit()

                # リクエストのタイムスタンプを記録
                self.request_timestamps.append(time.time())

                # コンテンツの準備
                contents = [
                    prompt,
                    f"以下は文字起こし結果です：\n\n{transcription_text}"
                ]

                # Gemini APIを使用して要約を生成
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )

                # 応答から要約を取得
                summary = response.text

                # 成功した場合は結果を返す
                return summary
            except Exception as e:
                retry_count += 1

                # 最大再試行回数に達した場合はエラーを発生
                if retry_count > self.max_retries:
                    logger.error(f"要約生成の最大再試行回数に達しました: {e}")
                    raise

                # 再試行前に待機（指数バックオフ）
                delay = min(self.retry_delay * (2 ** (retry_count - 1)), self.max_retry_delay)
                logger.warning(f"要約生成に失敗しました。{delay}秒後に再試行します ({retry_count}/{self.max_retries}): {e}")
                time.sleep(delay)


# シングルトンインスタンス
minutes_generator_service = MinutesGeneratorService()
