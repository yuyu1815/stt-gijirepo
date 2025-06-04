"""
Notion連携サービス

このモジュールは、生成された議事録をNotionデータベースにアップロードするサービスを提供します。
"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..domain.minutes import Minutes, MinutesFormat, MinutesSection
from ..infrastructure.config import config_manager
from ..infrastructure.logger import logger
from ..infrastructure.storage import storage_manager


class NotionService:
    """Notion連携サービスクラス"""

    def __init__(self):
        """初期化"""
        self.api_key = config_manager.get_api_key("notion")
        self.database_id = config_manager.get("notion.database_id")
        self.max_retries = config_manager.get("notion.max_retries", 3)
        self.retry_delay = config_manager.get("notion.retry_delay", 2)
        self.max_retry_delay = config_manager.get("notion.max_retry_delay", 30)
        self.max_block_size = config_manager.get("notion.max_block_size", 2000)

    def upload_minutes(self, minutes: Minutes) -> Dict:
        """
        議事録をNotionにアップロード
        
        Args:
            minutes: アップロードする議事録
            
        Returns:
            アップロード結果の辞書
        """
        logger.info(f"議事録のNotionアップロードを開始します: {minutes.title}")
        
        # APIキーとデータベースIDが設定されていない場合はエラー
        if not self.api_key:
            logger.error("Notion APIキーが設定されていません")
            raise ValueError("Notion APIキーが設定されていません")
            
        if not self.database_id:
            logger.error("Notion データベースIDが設定されていません")
            raise ValueError("Notion データベースIDが設定されていません")
            
        try:
            # ページプロパティを作成
            properties = self._create_page_properties(minutes)
            
            # ページコンテンツを作成
            blocks = self._create_page_blocks(minutes)
            
            # Notionにページを作成
            page_id = self._create_notion_page(properties, blocks)
            
            logger.info(f"議事録のNotionアップロードが完了しました: {page_id}")
            
            return {
                "success": True,
                "page_id": page_id,
                "url": f"https://notion.so/{page_id.replace('-', '')}"
            }
        except Exception as e:
            logger.error(f"議事録のNotionアップロードに失敗しました: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _create_page_properties(self, minutes: Minutes) -> Dict:
        """
        Notionページのプロパティを作成
        
        Args:
            minutes: 議事録
            
        Returns:
            プロパティの辞書
        """
        # 基本プロパティ
        properties = {
            "タイトル": {"title": [{"text": {"content": minutes.title}}]},
            "日付": {"date": {"start": minutes.date.strftime("%Y-%m-%d")}},
        }
        
        # 科目名
        if minutes.subject:
            properties["科目"] = {"select": {"name": minutes.subject}}
            
        # 講師名
        if minutes.lecturer:
            properties["講師"] = {"rich_text": [{"text": {"content": minutes.lecturer}}]}
            
        # 出席者
        if minutes.attendees:
            properties["出席者"] = {"rich_text": [{"text": {"content": ", ".join(minutes.attendees)}}]}
            
        # メタデータ
        if minutes.metadata:
            # メタデータの一部をプロパティとして追加
            for key, value in minutes.metadata.items():
                if key in ["タグ", "カテゴリ", "重要度"]:
                    if isinstance(value, str):
                        properties[key] = {"select": {"name": value}}
                    elif isinstance(value, list) and len(value) > 0:
                        properties[key] = {"multi_select": [{"name": item} for item in value[:10]]}
                        
        return properties

    def _create_page_blocks(self, minutes: Minutes) -> List[Dict]:
        """
        Notionページのブロックを作成
        
        Args:
            minutes: 議事録
            
        Returns:
            ブロックのリスト
        """
        blocks = []
        
        # 要約セクション
        if MinutesSection.SUMMARY in minutes.content.paragraphs:
            blocks.append(self._create_heading_block("要約", 2))
            
            for paragraph in minutes.content.paragraphs[MinutesSection.SUMMARY]:
                blocks.append(self._create_paragraph_block(paragraph))
                
            blocks.append(self._create_divider_block())
            
        # 本文セクション
        if MinutesSection.CONTENT in minutes.content.paragraphs:
            blocks.append(self._create_heading_block("議事内容", 2))
            
            for paragraph in minutes.content.paragraphs[MinutesSection.CONTENT]:
                blocks.append(self._create_paragraph_block(paragraph))
                
            blocks.append(self._create_divider_block())
            
        # 重要ポイントセクション
        if MinutesSection.IMPORTANT_POINTS in minutes.content.paragraphs:
            blocks.append(self._create_heading_block("重要ポイント", 2))
            
            for paragraph in minutes.content.paragraphs[MinutesSection.IMPORTANT_POINTS]:
                blocks.append(self._create_paragraph_block(paragraph))
                
            blocks.append(self._create_divider_block())
            
        # タスク・宿題セクション
        if minutes.has_tasks:
            blocks.append(self._create_heading_block("タスク・宿題", 2))
            
            task_items = []
            for task in minutes.content.tasks:
                task_text = task.description
                if task.assignee:
                    task_text += f" 担当: {task.assignee}"
                if task.due_date:
                    task_text += f" 期限: {task.due_date.strftime('%Y-%m-%d')}"
                    
                task_items.append(task_text)
                
            blocks.append(self._create_bulleted_list_block(task_items))
            blocks.append(self._create_divider_block())
            
        # 用語集セクション
        if minutes.has_glossary:
            blocks.append(self._create_heading_block("用語集", 2))
            
            for item in minutes.content.glossary:
                blocks.append(self._create_paragraph_block(f"**{item.term}**: {item.definition}"))
                
            blocks.append(self._create_divider_block())
            
        # 画像セクション
        if minutes.has_images:
            blocks.append(self._create_heading_block("画像", 2))
            
            # タイムスタンプでソート
            sorted_images = sorted(minutes.content.images, key=lambda img: img.timestamp)
            
            for i, image in enumerate(sorted_images):
                timestamp_str = self._format_time(image.timestamp)
                blocks.append(self._create_heading_block(f"画像 {i+1}: {timestamp_str}", 3))
                
                # 実際の実装では、画像をNotionにアップロードする処理が必要
                # ここではモック実装として、画像の説明のみを追加
                blocks.append(self._create_paragraph_block(f"画像の説明: {image.description if image.description else '説明なし'}"))
                
            blocks.append(self._create_divider_block())
            
        return blocks

    def _create_heading_block(self, text: str, level: int = 1) -> Dict:
        """
        見出しブロックを作成
        
        Args:
            text: 見出しテキスト
            level: 見出しレベル（1-3）
            
        Returns:
            見出しブロック
        """
        heading_type = f"heading_{level}"
        return {
            "object": "block",
            "type": heading_type,
            heading_type: {
                "rich_text": [{"type": "text", "text": {"content": text}}],
                "color": "default"
            }
        }

    def _create_paragraph_block(self, text: str) -> Dict:
        """
        段落ブロックを作成
        
        Args:
            text: 段落テキスト
            
        Returns:
            段落ブロック
        """
        # テキストが長すぎる場合は分割
        if len(text) > self.max_block_size:
            chunks = self._split_text(text, self.max_block_size)
            blocks = []
            for chunk in chunks:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": chunk}}],
                        "color": "default"
                    }
                })
            return blocks
            
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": text}}],
                "color": "default"
            }
        }

    def _create_bulleted_list_block(self, items: List[str]) -> List[Dict]:
        """
        箇条書きリストブロックを作成
        
        Args:
            items: リスト項目
            
        Returns:
            箇条書きリストブロック
        """
        blocks = []
        for item in items:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": item}}],
                    "color": "default"
                }
            })
        return blocks

    def _create_divider_block(self) -> Dict:
        """
        区切り線ブロックを作成
        
        Returns:
            区切り線ブロック
        """
        return {
            "object": "block",
            "type": "divider",
            "divider": {}
        }

    def _split_text(self, text: str, max_length: int) -> List[str]:
        """
        テキストを指定された長さで分割
        
        Args:
            text: 分割するテキスト
            max_length: 最大長
            
        Returns:
            分割されたテキストのリスト
        """
        chunks = []
        current_chunk = ""
        
        # 段落ごとに分割
        paragraphs = text.split("\n")
        
        for paragraph in paragraphs:
            # 段落が最大長を超える場合は、さらに分割
            if len(paragraph) > max_length:
                # 文ごとに分割
                sentences = paragraph.split(". ")
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 2 <= max_length:
                        if current_chunk:
                            current_chunk += ". " if not current_chunk.endswith(".") else " "
                        current_chunk += sentence
                    else:
                        if current_chunk:
                            chunks.append(current_chunk + ("." if not current_chunk.endswith(".") else ""))
                        current_chunk = sentence
            else:
                # 段落が最大長以内の場合
                if len(current_chunk) + len(paragraph) + 1 <= max_length:
                    if current_chunk:
                        current_chunk += "\n"
                    current_chunk += paragraph
                else:
                    chunks.append(current_chunk)
                    current_chunk = paragraph
                    
        # 残りのテキストを追加
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

    def _create_notion_page(self, properties: Dict, blocks: List[Dict]) -> str:
        """
        Notionページを作成
        
        Args:
            properties: ページプロパティ
            blocks: ページブロック
            
        Returns:
            作成されたページのID
        """
        # ここでは実際のNotion API呼び出しの代わりにモック実装
        # 実際の実装では、Notion APIクライアントを使用してページを作成する
        
        # モック実装（実際の実装では削除）
        logger.info(f"Notion APIでページを作成します: {properties.get('タイトル', {}).get('title', [{}])[0].get('text', {}).get('content', 'タイトルなし')}")
        
        # 再試行メカニズム
        retry_count = 0
        while retry_count <= self.max_retries:
            try:
                # ここに実際のAPI呼び出しコードを実装
                # 例: response = notion_client.pages.create(parent={"database_id": self.database_id}, properties=properties)
                
                # モック応答（実際の実装では削除）
                import uuid
                mock_page_id = str(uuid.uuid4())
                
                # ブロックを追加
                # 例: for block in blocks: notion_client.blocks.children.append(block_id=mock_page_id, children=[block])
                
                # 成功した場合はページIDを返す
                return mock_page_id
            except Exception as e:
                retry_count += 1
                
                # 最大再試行回数に達した場合はエラーを発生
                if retry_count > self.max_retries:
                    logger.error(f"Notionページ作成の最大再試行回数に達しました: {e}")
                    raise
                    
                # 再試行前に待機（指数バックオフ）
                delay = min(self.retry_delay * (2 ** (retry_count - 1)), self.max_retry_delay)
                logger.warning(f"Notionページ作成に失敗しました。{delay}秒後に再試行します ({retry_count}/{self.max_retries}): {e}")
                time.sleep(delay)

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
notion_service = NotionService()