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
                
            # 重要シーンを検出
            important_scenes = self._detect_important_scenes(media_file)
            
            # 重要シーンから画像を抽出
            extracted_images = self._extract_images_from_scenes(media_file, important_scenes)
            
            # 画像を分析
            analysis_result = self._analyze_images_with_gemini(media_file, extracted_images)
            
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

    def _detect_important_scenes(self, media_file: MediaFile) -> List[float]:
        """
        重要シーンを検出
        
        Args:
            media_file: 動画ファイル
            
        Returns:
            重要シーンのタイムスタンプのリスト
        """
        logger.info(f"重要シーンを検出します: {media_file.file_path}")
        
        # シーン変化を検出
        scene_changes = media_processor_service.detect_scene_changes(
            media_file, 
            threshold=self.scene_detection_threshold,
            min_scene_duration=self.min_scene_duration
        )
        
        # スライド切り替わりを検出（実際の実装では、より高度なアルゴリズムを使用）
        # ここではシーン変化をそのまま使用
        slide_changes = scene_changes
        
        # 講師の動きや指示を検出（実際の実装では、動き検出や人物検出を使用）
        # ここではモック実装
        instructor_movements = self._detect_instructor_movements(media_file)
        
        # 黒板/ホワイトボードの使用検出（実際の実装では、色検出や領域検出を使用）
        # ここではモック実装
        board_usage = self._detect_board_usage(media_file)
        
        # 全ての重要シーンを結合
        all_scenes = sorted(set(scene_changes + slide_changes + instructor_movements + board_usage))
        
        logger.info(f"{len(all_scenes)}個の重要シーンを検出しました: {media_file.file_path}")
        return all_scenes

    def _detect_instructor_movements(self, media_file: MediaFile) -> List[float]:
        """
        講師の動きや指示を検出（モック実装）
        
        Args:
            media_file: 動画ファイル
            
        Returns:
            講師の動きや指示のタイムスタンプのリスト
        """
        # 実際の実装では、動き検出や人物検出を使用
        # ここではモック実装として、一定間隔でタイムスタンプを生成
        duration = media_file.duration
        interval = 300  # 5分ごと
        
        return [i for i in range(0, int(duration), interval)]

    def _detect_board_usage(self, media_file: MediaFile) -> List[float]:
        """
        黒板/ホワイトボードの使用検出（モック実装）
        
        Args:
            media_file: 動画ファイル
            
        Returns:
            黒板/ホワイトボードの使用タイムスタンプのリスト
        """
        # 実際の実装では、色検出や領域検出を使用
        # ここではモック実装として、一定間隔でタイムスタンプを生成
        duration = media_file.duration
        interval = 600  # 10分ごと
        
        return [i for i in range(0, int(duration), interval)]

    def _extract_images_from_scenes(self, media_file: MediaFile, 
                                   scenes: List[float]) -> List[ExtractedImage]:
        """
        シーンから画像を抽出
        
        Args:
            media_file: 動画ファイル
            scenes: シーンのタイムスタンプのリスト
            
        Returns:
            抽出した画像のリスト
        """
        logger.info(f"{len(scenes)}個のシーンから画像を抽出します: {media_file.file_path}")
        
        extracted_images = []
        for timestamp in scenes:
            image = media_processor_service.extract_image_at_timestamp(
                media_file, timestamp, self.image_quality
            )
            if image:
                extracted_images.append(image)
                
        logger.info(f"{len(extracted_images)}枚の画像を抽出しました: {media_file.file_path}")
        return extracted_images

    def _analyze_images_with_gemini(self, media_file: MediaFile, 
                                   images: List[ExtractedImage]) -> Dict:
        """
        Gemini APIを使用して画像を分析
        
        Args:
            media_file: 動画ファイル
            images: 抽出した画像のリスト
            
        Returns:
            分析結果の辞書
        """
        logger.info(f"{len(images)}枚の画像を分析します: {media_file.file_path}")
        
        # プロンプトを読み込む
        prompt = self._load_video_analysis_prompt()
        
        # APIキーが設定されていない場合はエラー
        if not self.api_key:
            logger.error("Gemini APIキーが設定されていません")
            raise ValueError("Gemini APIキーが設定されていません")
            
        # ここでは実際のGemini API呼び出しの代わりにモック実装
        # 実際の実装では、Gemini APIクライアントを使用して画像を送信し、分析結果を取得する
        
        # モック実装（実際の実装では削除）
        logger.info(f"Gemini APIで画像分析を実行します: {media_file.file_path}")
        
        # 再試行メカニズム
        retry_count = 0
        while retry_count <= self.max_retries:
            try:
                # ここに実際のAPI呼び出しコードを実装
                # 例: response = gemini_client.analyze_images(images, prompt)
                
                # モック応答（実際の実装では削除）
                mock_response = self._generate_mock_analysis(media_file, images)
                
                # 成功した場合は結果を返す
                return mock_response
            except Exception as e:
                retry_count += 1
                
                # 最大再試行回数に達した場合はエラーを発生
                if retry_count > self.max_retries:
                    logger.error(f"画像分析の最大再試行回数に達しました: {e}")
                    raise
                    
                # 再試行前に待機（指数バックオフ）
                delay = min(self.retry_delay * (2 ** (retry_count - 1)), self.max_retry_delay)
                logger.warning(f"画像分析に失敗しました。{delay}秒後に再試行します ({retry_count}/{self.max_retries}): {e}")
                time.sleep(delay)

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

    def _generate_mock_analysis(self, media_file: MediaFile, 
                               images: List[ExtractedImage]) -> Dict:
        """
        モック分析結果を生成（実際の実装では削除）
        
        Args:
            media_file: 動画ファイル
            images: 抽出した画像のリスト
            
        Returns:
            モック分析結果
        """
        # 実際の実装では削除
        
        # 画像ごとの説明を生成
        image_descriptions = {}
        for i, image in enumerate(images):
            timestamp_str = self._format_time(image.timestamp)
            image_descriptions[str(image.file_path)] = {
                "timestamp": image.timestamp,
                "timestamp_str": timestamp_str,
                "description": f"画像 {i+1}: {timestamp_str} の時点での画面。これはモックの説明です。実際の実装では、Gemini APIを使用して画像の内容を分析します。",
                "importance": "HIGH" if i % 3 == 0 else ("MEDIUM" if i % 3 == 1 else "LOW"),
                "type": "SLIDE" if i % 4 == 0 else ("BOARD" if i % 4 == 1 else ("INSTRUCTOR" if i % 4 == 2 else "OTHER"))
            }
            
        # 全体の要約を生成
        summary = f"この動画は{media_file.file_path.stem}に関するものです。全体で{len(images)}枚の重要なシーンが検出されました。"
        
        # トピックを生成
        topics = [
            "トピック1: モックトピック",
            "トピック2: サンプルトピック",
            "トピック3: テストトピック"
        ]
        
        # 重要ポイントを生成
        key_points = [
            "重要ポイント1: これはモックの重要ポイントです。",
            "重要ポイント2: 実際の実装では、Gemini APIを使用して重要ポイントを抽出します。",
            "重要ポイント3: 動画の内容に基づいて重要なポイントが生成されます。"
        ]
        
        return {
            "summary": summary,
            "topics": topics,
            "key_points": key_points,
            "image_descriptions": image_descriptions
        }

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