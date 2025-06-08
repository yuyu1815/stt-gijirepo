"""
メディア処理ドメインモデル

このモジュールは、メディアファイル（音声・動画）に関するドメインモデルを定義します。
"""
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional


class MediaType(Enum):
    """メディアタイプを表す列挙型"""
    AUDIO = auto()
    VIDEO = auto()
    UNKNOWN = auto()


class VideoQuality(Enum):
    """動画の品質を表す列挙型"""
    DARK = auto()
    NORMAL = auto()
    UNKNOWN = auto()


@dataclass
class MediaChunk:
    """メディアファイルの分割チャンクを表すデータクラス"""
    start_time: float  # 開始時間（秒）
    end_time: float  # 終了時間（秒）
    file_path: Path  # チャンクファイルのパス
    index: int  # チャンクのインデックス

    def __hash__(self):
        """
        ハッシュ値を計算するメソッド

        Returns:
            int: ハッシュ値
        """
        return hash((self.start_time, self.end_time, str(self.file_path), self.index))

    def __eq__(self, other):
        """
        等価性を判定するメソッド

        Args:
            other: 比較対象のオブジェクト

        Returns:
            bool: 等価の場合はTrue、それ以外はFalse
        """
        if not isinstance(other, MediaChunk):
            return False
        return (self.start_time == other.start_time and
                self.end_time == other.end_time and
                self.file_path == other.file_path and
                self.index == other.index)


@dataclass
class MediaFile:
    """メディアファイルを表すドメインモデル"""
    file_path: Path  # ファイルパス
    media_type: MediaType  # メディアタイプ
    duration: Optional[float] = None  # 長さ（秒）
    video_quality: Optional[VideoQuality] = None  # 動画の品質（動画の場合のみ）
    chunks: List[MediaChunk] = None  # 分割されたチャンク（分割された場合のみ）

    def __post_init__(self):
        """初期化後の処理"""
        if self.chunks is None:
            self.chunks = []

    @property
    def is_long_media(self) -> bool:
        """
        長時間メディアかどうかを判定

        Returns:
            bool: 40分（2400秒）以上の場合はTrue、それ以外はFalse
        """
        if self.duration is None:
            return False
        return self.duration >= 2400  # 40分 = 2400秒

    @property
    def is_video(self) -> bool:
        """
        動画ファイルかどうかを判定

        Returns:
            bool: 動画の場合はTrue、それ以外はFalse
        """
        return self.media_type == MediaType.VIDEO

    @property
    def is_audio(self) -> bool:
        """
        音声ファイルかどうかを判定

        Returns:
            bool: 音声の場合はTrue、それ以外はFalse
        """
        return self.media_type == MediaType.AUDIO

    @property
    def is_dark_video(self) -> bool:
        """
        暗い動画かどうかを判定

        Returns:
            bool: 暗い動画の場合はTrue、それ以外はFalse
        """
        if not self.is_video or self.video_quality is None:
            return False
        return self.video_quality == VideoQuality.DARK

    @property
    def has_chunks(self) -> bool:
        """
        チャンクに分割されているかどうかを判定

        Returns:
            bool: チャンクがある場合はTrue、それ以外はFalse
        """
        return len(self.chunks) > 0


@dataclass
class ExtractedImage:
    """抽出された画像を表すデータクラス"""
    file_path: Path  # 画像ファイルのパス
    timestamp: float  # タイムスタンプ（秒）
    source_media: Path  # 元のメディアファイルのパス
    description: Optional[str] = None  # 画像の説明
