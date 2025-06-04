"""
動画分析サービス

このモジュールは、動画の内容を分析し、重要なシーンや情報を抽出するサービスを提供します。
"""
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..domain.media import ExtractedImage, MediaFile, VideoQuality
from ..infrastructure.config import config_manager
from ..infrastructure.logger import logger
from ..infrastructure.storage import storage_manager
from ..services.media_processor import media_processor_service
from ..utils.ffmpeg import ffmpeg_wrapper


class VideoAnalysisService:
    """動画分析サービスクラス"""

    def __init__(self):
        """初期化"""
        self.api_key = config_manager.get_api_key("gemini")
        self.max_retries = config_manager.get("video_analysis.max_retries", 3)
        self.retry_delay = config_manager.get("video_analysis.retry_delay", 2)
        self.max_retry_delay = config_manager.get("video_analysis.max_retry_delay", 30)
        self.prompt_path = config_manager.get_prompt_path("video_analysis")
        self.image_quality = config_manager.get("video_analysis.image_quality", 3)
        self.scene_detection_threshold = config_manager.get("video_analysis.scene_detection_threshold", 0.3)
        self.min_scene_duration = config_manager.get("video_analysis.min_scene_duration", 2.0)

    def analyze_video(self, media_file: MediaFile) -> Dict:
        """
        動画を分析

        Args:
            media_file: 動画ファイル

        Returns:
            分析結果の辞書
        """
        logger.info(f"動画分析を開始します: {media_file.file_path}")

        # 動画ファイルでない場合はエラー
        if not media_file.is_video:
            logger.error(f"動画ファイルではありません: {media_file.file_path}")
            return {"error": "動画ファイルではありません"}

        try:
            # 暗い動画の場合は分析しない
            if media_file.is_dark_video:
                logger.warning(f"暗い動画は分析できません: {media_file.file_path}")
                return {"error": "暗い動画は分析できません"}

            # 重要シーンの検出と画像抽出はスキップ（要件により）
            important_scenes = []
            extracted_images = []

            # 画像分析もスキップ（要件により）
            analysis_result = {
                "summary": "動画分析はスキップされました（要件により）",
                "topics": [],
                "key_points": [],
                "image_descriptions": {}
            }

            # 結果を保存
            output_path = self._save_analysis_result(media_file, analysis_result, extracted_images)

            logger.info(f"動画分析が完了しました: {media_file.file_path}")

            # 結果を返す
            return {
                "success": True,
                "important_scenes": important_scenes,
                "extracted_images": extracted_images,
                "analysis_result": analysis_result,
                "output_path": output_path
            }
        except Exception as e:
            logger.error(f"動画分析に失敗しました: {e}")
            return {"error": str(e)}


    def _load_video_analysis_prompt(self) -> str:
        """
        動画分析プロンプトを読み込む

        Returns:
            プロンプトテキスト
        """
        if not self.prompt_path.exists():
            logger.warning(f"プロンプトファイルが見つかりません: {self.prompt_path}")
            return "動画から抽出した画像を分析し、内容を説明してください。"

        return storage_manager.load_text(self.prompt_path)


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

    def _save_analysis_result(self, media_file: MediaFile, analysis_result: Dict, 
                             images: List[ExtractedImage]) -> Path:
        """
        分析結果を保存

        Args:
            media_file: 動画ファイル
            analysis_result: 分析結果
            images: 抽出した画像のリスト

        Returns:
            保存したファイルのパス
        """
        # 出力ディレクトリを取得
        output_dir = storage_manager.get_output_dir("reports")

        # ファイル名を生成
        file_name = f"{media_file.file_path.stem}_video_analysis.md"
        output_path = output_dir / file_name

        # Markdown形式で保存
        content = self._format_analysis_for_output(media_file, analysis_result, images)
        storage_manager.save_text(content, output_path)

        # JSON形式でも保存
        json_path = output_dir / f"{media_file.file_path.stem}_video_analysis.json"
        storage_manager.save_json(analysis_result, json_path)

        logger.info(f"動画分析結果を保存しました: {output_path}")
        return output_path

    def _format_analysis_for_output(self, media_file: MediaFile, analysis_result: Dict, 
                                   images: List[ExtractedImage]) -> str:
        """
        出力用に分析結果をフォーマット

        Args:
            media_file: 動画ファイル
            analysis_result: 分析結果
            images: 抽出した画像のリスト

        Returns:
            フォーマットされたテキスト
        """
        lines = []

        # ヘッダー
        lines.append(f"# 動画分析結果: {media_file.file_path.name}")
        lines.append(f"生成日時: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 要約
        lines.append("## 要約")
        lines.append(analysis_result.get("summary", "要約情報がありません。"))
        lines.append("")

        # トピック
        lines.append("## トピック")
        for topic in analysis_result.get("topics", []):
            lines.append(f"- {topic}")
        if not analysis_result.get("topics"):
            lines.append("トピック情報がありません。")
        lines.append("")

        # 重要ポイント
        lines.append("## 重要ポイント")
        for point in analysis_result.get("key_points", []):
            lines.append(f"- {point}")
        if not analysis_result.get("key_points"):
            lines.append("重要ポイント情報がありません。")
        lines.append("")

        # 画像分析
        lines.append("## 画像分析")

        image_descriptions = analysis_result.get("image_descriptions", {})
        sorted_images = sorted(images, key=lambda img: img.timestamp)

        for image in sorted_images:
            image_key = str(image.file_path)
            if image_key in image_descriptions:
                desc = image_descriptions[image_key]

                lines.append(f"### {desc.get('timestamp_str', '不明な時間')}")
                lines.append(f"![画像]({image.file_path.as_posix()})")
                lines.append("")
                lines.append(f"**重要度**: {desc.get('importance', 'UNKNOWN')}")
                lines.append(f"**タイプ**: {desc.get('type', 'UNKNOWN')}")
                lines.append("")
                lines.append(desc.get("description", "説明がありません。"))
                lines.append("")

        return "\n".join(lines)


# シングルトンインスタンス
video_analysis_service = VideoAnalysisService()
