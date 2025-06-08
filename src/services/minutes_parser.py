"""
議事録パーサーサービス

このモジュールは、生成された議事録テキストを解析し、構造化されたオブジェクトに変換する機能を提供します。
"""
import re
from datetime import datetime
from typing import Dict, List

from ..domain.minutes import (
    GlossaryItem, Minutes, MinutesHeading, MinutesSection, MinutesTask
)
from ..infrastructure.logger import logger


class MinutesParserService:
    """議事録パーサーサービスクラス"""

    def parse_minutes_content(self, minutes: Minutes, content: str) -> Minutes:
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


# シングルトンインスタンス
minutes_parser_service = MinutesParserService()