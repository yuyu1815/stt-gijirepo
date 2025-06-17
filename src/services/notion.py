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
from ..utils.time_utils import format_time


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

            # 親ページが指定されている場合は、その下にページを作成
            parent_id = minutes.parent_page_id

            # Notionにページを作成
            page_id = self._create_notion_page(properties, blocks, parent_id)

            # 作成されたページIDを設定
            minutes.set_notion_page_id(page_id)

            # MOCページを更新または作成
            self._update_or_create_moc_page(minutes)

            # 関連ページがある場合は、それらのページにバックリンクを追加
            if minutes.has_related_pages:
                self._update_related_pages_with_backlinks(minutes)

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

        # 目次ブロック
        blocks.append(self._create_heading_block("目次", 2))
        blocks.append(self._create_table_of_contents_block())
        blocks.append(self._create_divider_block())

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

        # 関連ページセクション
        if minutes.has_related_pages:
            blocks.append(self._create_heading_block("関連ページ", 2))

            for page_id, title in minutes.related_pages.items():
                blocks.append(self._create_paragraph_block(f"**{title}**"))
                blocks.append(self._create_link_to_page_block(page_id))

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

    def _create_link_to_page_block(self, page_id: str) -> Dict:
        """
        ページへのリンクブロックを作成

        Args:
            page_id: リンク先のページID

        Returns:
            ページへのリンクブロック
        """
        return {
            "object": "block",
            "type": "link_to_page",
            "link_to_page": {
                "type": "page_id",
                "page_id": page_id
            }
        }

    def _create_table_of_contents_block(self) -> Dict:
        """
        目次ブロックを作成

        Returns:
            目次ブロック
        """
        return {
            "object": "block",
            "type": "table_of_contents",
            "table_of_contents": {
                "color": "default"
            }
        }

    def _create_bookmark_block(self, url: str, title: str = "") -> Dict:
        """
        ブックマークブロックを作成

        Args:
            url: ブックマークのURL
            title: ブックマークのタイトル（オプション）

        Returns:
            ブックマークブロック
        """
        block = {
            "object": "block",
            "type": "bookmark",
            "bookmark": {
                "url": url
            }
        }

        if title:
            block["bookmark"]["caption"] = [
                {
                    "type": "text",
                    "text": {
                        "content": title
                    }
                }
            ]

        return block

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

    def _create_notion_page(self, properties: Dict, blocks: List[Dict], parent_id: Optional[str] = None) -> str:
        """
        Notionページを作成

        Args:
            properties: ページプロパティ
            blocks: ページブロック
            parent_id: 親ページID（指定された場合はデータベースではなく親ページの下に作成）

        Returns:
            作成されたページのID
        """
        # ここでは実際のNotion API呼び出しの代わりにモック実装
        # 実際の実装では、Notion APIクライアントを使用してページを作成する

        # モック実装（実際の実装では削除）
        page_title = properties.get('タイトル', {}).get('title', [{}])[0].get('text', {}).get('content', 'タイトルなし')
        logger.info(f"Notion APIでページを作成します: {page_title}")

        # 再試行メカニズム
        retry_count = 0
        while retry_count <= self.max_retries:
            try:
                # ここに実際のAPI呼び出しコードを実装
                # 親ページが指定されている場合は、その下にページを作成
                # if parent_id:
                #     response = notion_client.pages.create(parent={"page_id": parent_id}, properties=properties)
                # else:
                #     response = notion_client.pages.create(parent={"database_id": self.database_id}, properties=properties)

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


    def _update_or_create_moc_page(self, minutes: Minutes) -> str:
        """
        MOC（Map of Content）ページを更新または作成
        詳細なチェックを行い、MOCページの存在確認、作成、更新を行います

        Args:
            minutes: 議事録

        Returns:
            MOCページのID

        Raises:
            ValueError: MOCページIDが無効な形式の場合
            RuntimeError: MOCページの作成または更新に失敗した場合
        """
        try:
            # MOCページのIDを取得（設定ファイルから）
            moc_page_id = config_manager.get("notion.moc_page_id")

            # MOCページIDの形式チェック（存在する場合）
            if moc_page_id:
                # UUIDの形式チェック（実際の実装ではNotion APIの仕様に合わせて調整）
                import uuid
                try:
                    uuid.UUID(moc_page_id)
                except ValueError:
                    logger.error(f"無効なMOCページIDの形式です: {moc_page_id}")
                    raise ValueError(f"無効なMOCページIDの形式です: {moc_page_id}")

                # MOCページの存在チェック（実際の実装ではNotion APIを使用）
                # 例: 
                # try:
                #     notion_client.pages.retrieve(page_id=moc_page_id)
                # except Exception as e:
                #     logger.error(f"MOCページが存在しません: {moc_page_id} - {e}")
                #     logger.info("MOCページが存在しないため、新規作成します")
                #     moc_page_id = None

                logger.info(f"MOCページIDを確認しました: {moc_page_id}")

            # MOCページが存在しない場合は作成
            if not moc_page_id:
                logger.info("MOCページが存在しないため、新規作成します")
                moc_page_id = self._create_moc_page()
                if not moc_page_id:
                    raise RuntimeError("MOCページの作成に失敗しました")

                # 設定に保存（実際の実装では必要に応じて）
                # config_manager.set("notion.moc_page_id", moc_page_id)
                logger.info(f"新しいMOCページを作成しました: {moc_page_id}")

            # MOCページを更新（新しいページへのリンクを追加）
            self._update_moc_page(moc_page_id, minutes)

            return moc_page_id
        except Exception as e:
            logger.error(f"MOCページの更新または作成中にエラーが発生しました: {e}")
            raise RuntimeError(f"MOCページの更新または作成に失敗しました: {e}")

    def _create_moc_page(self) -> str:
        """
        MOC（Map of Content）ページを作成
        詳細なチェックを行い、MOCページの作成と検証を行います

        Returns:
            作成されたMOCページのID

        Raises:
            ValueError: MOCページの作成に必要なパラメータが無効な場合
            RuntimeError: MOCページの作成に失敗した場合
        """
        try:
            logger.info("MOCページの作成を開始します")

            # MOCページのタイトルと日付を設定
            moc_title = "議事録インデックス（MOC）"
            current_date = datetime.now().strftime("%Y-%m-%d")

            # MOCページのプロパティを作成
            properties = {
                "タイトル": {"title": [{"text": {"content": moc_title}}]},
                "日付": {"date": {"start": current_date}},
            }

            # プロパティの検証
            if not properties["タイトル"]["title"][0]["text"]["content"]:
                logger.error("MOCページのタイトルが空です")
                raise ValueError("MOCページのタイトルが空です")

            # MOCページのブロックを作成
            blocks = []

            # 説明
            blocks.append(self._create_heading_block("議事録インデックス", 1))
            blocks.append(self._create_paragraph_block("このページは議事録のインデックス（Map of Content）です。すべての議事録へのリンクが含まれています。"))
            blocks.append(self._create_divider_block())

            # 目次
            blocks.append(self._create_heading_block("目次", 2))
            blocks.append(self._create_table_of_contents_block())
            blocks.append(self._create_divider_block())

            # 議事録セクション
            blocks.append(self._create_heading_block("議事録一覧", 2))
            blocks.append(self._create_paragraph_block("このセクションには、すべての議事録へのリンクが含まれています。"))
            blocks.append(self._create_divider_block())

            # ブロックの検証
            if len(blocks) < 3:
                logger.error("MOCページのブロックが不足しています")
                raise ValueError("MOCページのブロックが不足しています")

            # 議事録一覧セクションの存在確認
            has_minutes_list_section = False
            for block in blocks:
                if (block.get("type") == "heading_2" and 
                    block.get("heading_2", {}).get("rich_text", [{}])[0].get("text", {}).get("content") == "議事録一覧"):
                    has_minutes_list_section = True
                    break

            if not has_minutes_list_section:
                logger.error("MOCページに議事録一覧セクションがありません")
                raise ValueError("MOCページに議事録一覧セクションがありません")

            # Notionにページを作成
            moc_page_id = self._create_notion_page(properties, blocks)

            # 作成されたページIDの検証
            if not moc_page_id:
                logger.error("MOCページの作成に失敗しました: ページIDが取得できません")
                raise RuntimeError("MOCページの作成に失敗しました: ページIDが取得できません")

            # UUIDの形式チェック
            import uuid
            try:
                uuid.UUID(moc_page_id)
            except ValueError:
                logger.error(f"作成されたMOCページIDの形式が無効です: {moc_page_id}")
                raise ValueError(f"作成されたMOCページIDの形式が無効です: {moc_page_id}")

            logger.info(f"MOCページを作成しました: {moc_page_id}")
            return moc_page_id

        except Exception as e:
            logger.error(f"MOCページの作成中にエラーが発生しました: {e}")
            raise RuntimeError(f"MOCページの作成に失敗しました: {e}")

    def _update_moc_page(self, moc_page_id: str, minutes: Minutes) -> None:
        """
        MOCページを更新（新しいページへのリンクを追加）
        詳細なチェックを行い、MOCページの構造確認と更新を行います

        Args:
            moc_page_id: MOCページのID
            minutes: 追加する議事録

        Raises:
            ValueError: パラメータが無効な場合、またはMOCページの構造が想定と異なる場合
            RuntimeError: MOCページの更新に失敗した場合
        """
        try:
            logger.info(f"MOCページの更新を開始します: {moc_page_id}")

            # パラメータの検証
            if not moc_page_id:
                logger.error("MOCページIDが指定されていません")
                raise ValueError("MOCページIDが指定されていません")

            if not minutes.notion_page_id:
                logger.error("議事録のNotionページIDが設定されていません")
                raise ValueError("議事録のNotionページIDが設定されていません")

            # UUIDの形式チェック
            import uuid
            try:
                uuid.UUID(moc_page_id)
                if minutes.notion_page_id:
                    uuid.UUID(minutes.notion_page_id)
            except ValueError as e:
                logger.error(f"無効なページIDの形式です: {e}")
                raise ValueError(f"無効なページIDの形式です: {e}")

            # 実際の実装では、Notion APIを使用してMOCページを取得し、
            # 「議事録一覧」セクションの下に新しいページへのリンクを追加する

            # MOCページの存在確認（実際の実装ではNotion APIを使用）
            # try:
            #     page = notion_client.pages.retrieve(page_id=moc_page_id)
            #     # ページタイトルの確認
            #     page_title = page["properties"]["タイトル"]["title"][0]["text"]["content"]
            #     if "議事録インデックス" not in page_title and "MOC" not in page_title:
            #         logger.warning(f"MOCページのタイトルが想定と異なります: {page_title}")
            # except Exception as e:
            #     logger.error(f"MOCページの取得に失敗しました: {e}")
            #     raise RuntimeError(f"MOCページの取得に失敗しました: {e}")

            # MOCページのブロック構造を確認（実際の実装ではNotion APIを使用）
            # blocks = notion_client.blocks.children.list(block_id=moc_page_id)
            # 
            # # 「議事録一覧」セクションを見つける
            # minutes_section_id = None
            # for block in blocks["results"]:
            #     if block["type"] == "heading_2" and block["heading_2"]["rich_text"][0]["text"]["content"] == "議事録一覧":
            #         minutes_section_id = block["id"]
            #         break
            # 
            # # 「議事録一覧」セクションが見つからない場合は作成
            # if not minutes_section_id:
            #     logger.warning("MOCページに「議事録一覧」セクションが見つかりません。セクションを作成します。")
            #     response = notion_client.blocks.children.append(
            #         block_id=moc_page_id,
            #         children=[
            #             self._create_heading_block("議事録一覧", 2),
            #             self._create_paragraph_block("このセクションには、すべての議事録へのリンクが含まれています。"),
            #             self._create_divider_block()
            #         ]
            #     )
            #     # 作成されたセクションのIDを取得
            #     for block in response["results"]:
            #         if block["type"] == "heading_2" and block["heading_2"]["rich_text"][0]["text"]["content"] == "議事録一覧":
            #             minutes_section_id = block["id"]
            #             break
            # 
            # # 「議事録一覧」セクションの下に新しいページへのリンクを追加
            # if minutes_section_id:
            #     # 重複チェック（同じ議事録が既に追加されていないか確認）
            #     section_blocks = notion_client.blocks.children.list(block_id=minutes_section_id)
            #     is_duplicate = False
            #     for block in section_blocks["results"]:
            #         if block["type"] == "link_to_page" and block["link_to_page"]["page_id"] == minutes.notion_page_id:
            #             is_duplicate = True
            #             logger.info(f"議事録は既にMOCページに追加されています: {minutes.title}")
            #             break
            #     
            #     if not is_duplicate:
            #         notion_client.blocks.children.append(
            #             block_id=minutes_section_id,
            #             children=[
            #                 self._create_paragraph_block(f"{minutes.date.strftime('%Y-%m-%d')} - {minutes.title}"),
            #                 self._create_link_to_page_block(minutes.notion_page_id)
            #             ]
            #         )
            #         logger.info(f"MOCページに議事録へのリンクを追加しました: {minutes.title}")
            # else:
            #     logger.error("「議事録一覧」セクションの作成に失敗しました")
            #     raise RuntimeError("「議事録一覧」セクションの作成に失敗しました")

            # モック実装（実際の実装では削除）
            logger.info(f"MOCページを更新しました: {moc_page_id} - 追加された議事録: {minutes.title}")

        except Exception as e:
            logger.error(f"MOCページの更新中にエラーが発生しました: {e}")
            raise RuntimeError(f"MOCページの更新に失敗しました: {e}")

    def _update_related_pages_with_backlinks(self, minutes: Minutes) -> None:
        """
        関連ページにバックリンクを追加

        Args:
            minutes: 議事録
        """
        # 実際の実装では、Notion APIを使用して関連ページを更新し、
        # 現在のページへのバックリンクを追加する

        for related_page_id, related_page_title in minutes.related_pages.items():
            logger.info(f"関連ページにバックリンクを追加します: {related_page_title} ({related_page_id}) -> {minutes.title}")

            # 例:
            # 1. 関連ページのブロックを取得
            # blocks = notion_client.blocks.children.list(block_id=related_page_id)

            # 2. 「関連ページ」セクションを見つける、なければ作成
            # related_section_id = None
            # for block in blocks["results"]:
            #     if block["type"] == "heading_2" and block["heading_2"]["rich_text"][0]["text"]["content"] == "関連ページ":
            #         related_section_id = block["id"]
            #         break

            # if not related_section_id:
            #     # 「関連ページ」セクションを作成
            #     response = notion_client.blocks.children.append(
            #         block_id=related_page_id,
            #         children=[
            #             self._create_heading_block("関連ページ", 2),
            #             self._create_divider_block()
            #         ]
            #     )
            #     related_section_id = response["results"][0]["id"]

            # 3. 「関連ページ」セクションの下に現在のページへのリンクを追加
            # notion_client.blocks.children.append(
            #     block_id=related_section_id,
            #     children=[
            #         self._create_paragraph_block(f"{minutes.date.strftime('%Y-%m-%d')} - {minutes.title}"),
            #         self._create_link_to_page_block(minutes.notion_page_id)
            #     ]
            # )


# シングルトンインスタンス
notion_service = NotionService()
