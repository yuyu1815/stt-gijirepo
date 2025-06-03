"""
議事録ドメインモデル

このモジュールは、議事録に関するドメインモデルを定義します。
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional

from .media import ExtractedImage
from .transcription import TranscriptionResult


class MinutesFormat(Enum):
    """議事録のフォーマットを表す列挙型"""
    MARKDOWN = auto()
    HTML = auto()
    PLAIN_TEXT = auto()


class MinutesSection(Enum):
    """議事録のセクションを表す列挙型"""
    HEADER = auto()  # ヘッダー（タイトル、日時、参加者など）
    SUMMARY = auto()  # 要約
    CONTENT = auto()  # 本文
    IMPORTANT_POINTS = auto()  # 重要ポイント
    TASKS = auto()  # タスク・宿題
    GLOSSARY = auto()  # 用語集
    IMAGES = auto()  # 画像セクション


@dataclass
class MinutesHeading:
    """議事録の見出しを表すデータクラス"""
    text: str  # 見出しテキスト
    level: int  # 見出しレベル（1-6）
    timestamp: Optional[float] = None  # 関連するタイムスタンプ（秒）


@dataclass
class MinutesTask:
    """議事録内のタスク・宿題を表すデータクラス"""
    description: str  # タスクの説明
    due_date: Optional[datetime] = None  # 期限
    assignee: Optional[str] = None  # 担当者


@dataclass
class GlossaryItem:
    """用語集の項目を表すデータクラス"""
    term: str  # 用語
    definition: str  # 定義


@dataclass
class MinutesContent:
    """議事録の内容を表すデータクラス"""
    headings: List[MinutesHeading] = field(default_factory=list)  # 見出しのリスト
    paragraphs: Dict[MinutesSection, List[str]] = field(default_factory=dict)  # セクション別の段落リスト
    tasks: List[MinutesTask] = field(default_factory=list)  # タスク・宿題のリスト
    glossary: List[GlossaryItem] = field(default_factory=list)  # 用語集のリスト
    images: List[ExtractedImage] = field(default_factory=list)  # 画像のリスト

    def __post_init__(self):
        """初期化後の処理"""
        # paragraphsの初期化
        if not self.paragraphs:
            self.paragraphs = {section: [] for section in MinutesSection}


@dataclass
class Minutes:
    """議事録を表すドメインモデル"""
    title: str  # タイトル
    date: datetime  # 日付
    content: MinutesContent  # 内容
    source_transcription: TranscriptionResult  # 元の文字起こし結果
    format: MinutesFormat = MinutesFormat.MARKDOWN  # フォーマット
    lecturer: Optional[str] = None  # 講師名
    subject: Optional[str] = None  # 科目名
    attendees: List[str] = field(default_factory=list)  # 出席者リスト
    metadata: Dict = field(default_factory=dict)  # メタデータ
    output_path: Optional[Path] = None  # 出力先パス

    @property
    def has_images(self) -> bool:
        """
        画像があるかどうかを判定
        
        Returns:
            bool: 画像がある場合はTrue、それ以外はFalse
        """
        return len(self.content.images) > 0

    @property
    def has_tasks(self) -> bool:
        """
        タスク・宿題があるかどうかを判定
        
        Returns:
            bool: タスク・宿題がある場合はTrue、それ以外はFalse
        """
        return len(self.content.tasks) > 0

    @property
    def has_glossary(self) -> bool:
        """
        用語集があるかどうかを判定
        
        Returns:
            bool: 用語集がある場合はTrue、それ以外はFalse
        """
        return len(self.content.glossary) > 0

    def add_image(self, image: ExtractedImage) -> None:
        """
        画像を追加
        
        Args:
            image: 追加する画像
        """
        self.content.images.append(image)

    def add_task(self, task: MinutesTask) -> None:
        """
        タスク・宿題を追加
        
        Args:
            task: 追加するタスク・宿題
        """
        self.content.tasks.append(task)

    def add_glossary_item(self, item: GlossaryItem) -> None:
        """
        用語集の項目を追加
        
        Args:
            item: 追加する用語集の項目
        """
        self.content.glossary.append(item)

    def add_heading(self, heading: MinutesHeading) -> None:
        """
        見出しを追加
        
        Args:
            heading: 追加する見出し
        """
        self.content.headings.append(heading)

    def add_paragraph(self, section: MinutesSection, text: str) -> None:
        """
        段落を追加
        
        Args:
            section: 追加するセクション
            text: 追加するテキスト
        """
        if section not in self.content.paragraphs:
            self.content.paragraphs[section] = []
        self.content.paragraphs[section].append(text)