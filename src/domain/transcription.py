"""
文字起こしドメインモデル

このモジュールは、文字起こしに関するドメインモデルを定義します。
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional


class TranscriptionStatus(Enum):
    """文字起こしの状態を表す列挙型"""
    PENDING = auto()  # 未処理
    IN_PROGRESS = auto()  # 処理中
    COMPLETED = auto()  # 完了
    FAILED = auto()  # 失敗


class HallucinationSeverity(Enum):
    """ハルシネーションの重大度を表す列挙型"""
    NONE = auto()  # ハルシネーションなし
    LOW = auto()  # 軽度のハルシネーション
    MEDIUM = auto()  # 中程度のハルシネーション
    HIGH = auto()  # 重度のハルシネーション


@dataclass
class Speaker:
    """話者を表すデータクラス"""
    id: str  # 話者ID
    name: Optional[str] = None  # 話者名


@dataclass
class TranscriptionSegment:
    """文字起こしの一部分（発言単位）を表すデータクラス"""
    text: str  # 文字起こしテキスト
    start_time: float  # 開始時間（秒）
    end_time: float  # 終了時間（秒）
    speaker: Optional[Speaker] = None  # 話者
    confidence: float = 1.0  # 信頼度


@dataclass
class HallucinationResult:
    """ハルシネーションチェック結果を表すデータクラス"""
    segment: TranscriptionSegment  # チェック対象のセグメント
    severity: HallucinationSeverity  # ハルシネーションの重大度
    reason: Optional[str] = None  # ハルシネーションと判断した理由
    corrected_text: Optional[str] = None  # 修正されたテキスト（ある場合）


@dataclass
class TranscriptionResult:
    """文字起こし結果を表すドメインモデル"""
    source_file: Path  # 元のメディアファイルのパス
    segments: List[TranscriptionSegment] = field(default_factory=list)  # 文字起こしセグメントのリスト
    status: TranscriptionStatus = TranscriptionStatus.PENDING  # 文字起こしの状態
    hallucination_results: List[HallucinationResult] = field(default_factory=list)  # ハルシネーションチェック結果
    metadata: Dict = field(default_factory=dict)  # メタデータ

    @property
    def full_text(self) -> str:
        """
        すべてのセグメントを結合した完全なテキストを取得
        
        Returns:
            str: 完全な文字起こしテキスト
        """
        return "\n".join(segment.text for segment in self.segments)

    @property
    def has_hallucinations(self) -> bool:
        """
        ハルシネーションが検出されたかどうかを判定
        
        Returns:
            bool: ハルシネーションがある場合はTrue、それ以外はFalse
        """
        return any(result.severity != HallucinationSeverity.NONE for result in self.hallucination_results)

    @property
    def is_completed(self) -> bool:
        """
        文字起こしが完了しているかどうかを判定
        
        Returns:
            bool: 完了している場合はTrue、それ以外はFalse
        """
        return self.status == TranscriptionStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """
        文字起こしが失敗したかどうかを判定
        
        Returns:
            bool: 失敗した場合はTrue、それ以外はFalse
        """
        return self.status == TranscriptionStatus.FAILED

    def get_segment_at_time(self, time: float) -> Optional[TranscriptionSegment]:
        """
        指定した時間のセグメントを取得
        
        Args:
            time: 検索する時間（秒）
            
        Returns:
            Optional[TranscriptionSegment]: 該当するセグメント、ない場合はNone
        """
        for segment in self.segments:
            if segment.start_time <= time <= segment.end_time:
                return segment
        return None