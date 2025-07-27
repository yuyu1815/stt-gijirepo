"""
STT議事録システム - Notion API クライアント

Notion APIを使用したページ作成、コンテンツアップロード、データベース操作などの機能を提供
"""

import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
import logging

from notion_client import Client
from notion_client.errors import APIResponseError, RequestTimeoutError

from ..utils import get_logger, APIError, api_call_with_retry
from ..utils.logging_config import LogContext
from ..utils.retry_utils import method_error_handler


class NotionClient:
    """Notion APIを使用したクライアントクラス"""
    
    def __init__(self, token: str):
        self.logger = get_logger(__name__)
        self.token = token
        self._setup_client()
    
    @method_error_handler(APIError, "Notion APIクライアントの初期化に失敗")
    def _setup_client(self) -> None:
        """Notion APIクライアントのセットアップ"""
        if not self.token:
            raise APIError("Notion トークンが設定されていません")
        
        self.client = Client(auth=self.token)
        
        # 接続テスト
        self._test_connection()
        
        self.logger.info("Notion APIクライアント初期化完了")
    
    @method_error_handler(APIError, "Notion API接続テストに失敗", passthrough_exceptions=[APIResponseError, RequestTimeoutError])
    def _test_connection(self) -> None:
        """Notion API接続テスト"""
        # ユーザーリストを取得して接続をテスト（users.me()ではなくusers.listを使用）
        self.client.users.list()
        self.logger.debug("Notion API接続テスト成功")
    
    @method_error_handler(APIError, "Notionページ作成に失敗", passthrough_exceptions=[APIResponseError])
    def create_page(
        self,
        parent_id: str,
        title: str,
        content: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Notionページを作成
        
        Args:
            parent_id: 親ページまたはデータベースのID
            title: ページタイトル
            content: ページコンテンツ（Markdown形式）
            properties: ページプロパティ
            
        Returns:
            Dict: 作成されたページ情報
        """
        self.logger.info(f"Notionページ作成開始: {title}")
        
        # ページプロパティの準備
        page_properties = {
            "title": {
                "title": [
                    {
                        "text": {
                            "content": title
                        }
                    }
                ]
            }
        }
        
        # 追加プロパティがある場合は統合
        if properties:
            page_properties.update(properties)
        
        # コンテンツをNotionブロックに変換
        children = self._markdown_to_blocks(content)
        
        # ページ作成（リトライ機能付き）
        def create_page_call():
            try:
                return self.client.pages.create(
                    parent={
                        "type": "database_id" if self._is_database_id(parent_id) else "page_id",
                        "database_id" if self._is_database_id(parent_id) else "page_id": parent_id
                    },
                    properties=page_properties,
                    children=children
                )
            except APIResponseError as e:
                # APIResponseErrorは特別に処理
                raise APIError(f"Notion APIエラー: {e.body}")
            except RequestTimeoutError as e:
                # RequestTimeoutErrorはAPIErrorに変換
                raise APIError(f"Request timeout: {str(e)}")
        
        # リトライ機能付きでAPI呼び出し
        response = api_call_with_retry(
            create_page_call,
            max_retries=3,
            logger=self.logger
        )
        
        # テスト期待値に合わせて、APIレスポンスをそのまま返す
        self.logger.info(f"Notionページ作成完了: {response['id']}")
        return response
    
    @method_error_handler(APIError, "Notionページ更新に失敗", passthrough_exceptions=[APIResponseError, RequestTimeoutError])
    def update_page(
        self,
        page_id: str,
        content: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Notionページを更新
        
        Args:
            page_id: ページID
            content: 新しいコンテンツ（Markdown形式）
            properties: 更新するプロパティ
            
        Returns:
            Dict: 更新されたページ情報
        """
        self.logger.info(f"Notionページ更新開始: {page_id}")
        
        # プロパティの更新
        if properties:
            try:
                self.client.pages.update(
                    page_id=page_id,
                    properties=properties
                )
            except APIResponseError as e:
                raise APIError(f"Notion APIエラー (プロパティ更新): {e.body}")
        
        # コンテンツの更新
        if content:
            # 既存のコンテンツを削除
            self._clear_page_content(page_id)
            
            # 新しいコンテンツを追加
            children = self._markdown_to_blocks(content)
            try:
                self.client.blocks.children.append(
                    block_id=page_id,
                    children=children
                )
            except APIResponseError as e:
                raise APIError(f"Notion APIエラー (コンテンツ更新): {e.body}")
        
        # 更新されたページ情報を取得
        try:
            response = self.client.pages.retrieve(page_id=page_id)
        except APIResponseError as e:
            raise APIError(f"Notion APIエラー (ページ情報取得): {e.body}")
        
        page_info = {
            'page_id': response['id'],
            'url': response['url'],
            'last_edited_time': response['last_edited_time']
        }
        
        self.logger.info(f"Notionページ更新完了: {page_id}")
        return page_info
    
    @method_error_handler(APIError, "データベース情報取得に失敗", passthrough_exceptions=[APIResponseError, RequestTimeoutError])
    def get_database_info(self, database_id: str) -> Dict[str, Any]:
        """
        データベース情報を取得
        
        Args:
            database_id: データベースID
            
        Returns:
            Dict: データベース情報
        """
        self.logger.info(f"Notionデータベース情報取得: {database_id}")
        
        try:
            response = self.client.databases.retrieve(database_id=database_id)
        except APIResponseError as e:
            raise APIError(f"Notion APIエラー: {e.body}")
        
        database_info = {
            'database_id': response['id'],
            'title': self._extract_title(response.get('title', [])),
            'url': response['url'],
            'properties': response['properties'],
            'created_time': response['created_time'],
            'last_edited_time': response['last_edited_time']
        }
        
        self.logger.info(f"データベース情報取得完了: {database_info['title']}")
        return database_info
    
    @method_error_handler(APIError, "データベースクエリに失敗", passthrough_exceptions=[APIResponseError, RequestTimeoutError])
    def query_database(
        self,
        database_id: str,
        filter_conditions: Optional[Dict[str, Any]] = None,
        sorts: Optional[List[Dict[str, Any]]] = None,
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        データベースをクエリ
        
        Args:
            database_id: データベースID
            filter_conditions: フィルター条件
            sorts: ソート条件
            page_size: ページサイズ
            
        Returns:
            List[Dict]: クエリ結果
        """
        self.logger.info(f"Notionデータベースクエリ: {database_id}")
        
        query_params = {
            "database_id": database_id,
            "page_size": page_size
        }
        
        if filter_conditions:
            query_params["filter"] = filter_conditions
        
        if sorts:
            query_params["sorts"] = sorts
        
        try:
            response = self.client.databases.query(**query_params)
        except APIResponseError as e:
            raise APIError(f"Notion APIエラー: {e.body}")
        
        results = []
        for page in response['results']:
            page_info = {
                'page_id': page['id'],
                'url': page['url'],
                'properties': page['properties'],
                'created_time': page['created_time'],
                'last_edited_time': page['last_edited_time']
            }
            results.append(page_info)
        
        self.logger.info(f"データベースクエリ完了: {len(results)}件")
        return results
    
    @method_error_handler(APIError, "Markdownブロック変換に失敗")
    def _markdown_to_blocks(self, markdown_content: str) -> List[Dict[str, Any]]:
        """
        MarkdownコンテンツをNotionブロックに変換
        
        Args:
            markdown_content: Markdownコンテンツ
            
        Returns:
            List[Dict]: Notionブロックのリスト
        """
        blocks = []
        lines = markdown_content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
            
            # ヘッダー
            if line.startswith('# '):
                blocks.append({
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                    }
                })
            elif line.startswith('## '):
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": line[3:]}}]
                    }
                })
            elif line.startswith('### '):
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": line[4:]}}]
                    }
                })
            # リスト
            elif line.startswith('- ') or line.startswith('* '):
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                    }
                })
            elif line.startswith('1. ') or line.startswith('- [ ] '):
                # チェックボックス
                if line.startswith('- [ ] '):
                    blocks.append({
                        "object": "block",
                        "type": "to_do",
                        "to_do": {
                            "rich_text": [{"type": "text", "text": {"content": line[6:]}}],
                            "checked": False
                        }
                    })
                elif line.startswith('- [x] '):
                    blocks.append({
                        "object": "block",
                        "type": "to_do",
                        "to_do": {
                            "rich_text": [{"type": "text", "text": {"content": line[6:]}}],
                            "checked": True
                        }
                    })
                else:
                    # 番号付きリスト
                    blocks.append({
                        "object": "block",
                        "type": "numbered_list_item",
                        "numbered_list_item": {
                            "rich_text": [{"type": "text", "text": {"content": line[3:]}}]
                        }
                    })
            # コードブロック
            elif line.startswith('```'):
                # 簡易実装：コードブロックは通常のテキストとして扱う
                continue
            # 通常のテキスト
            else:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": line}}]
                    }
                })
        
        # ブロックが空の場合はフォールバックとして全体を1つのテキストブロックとして扱う
        if not blocks:
            self.logger.warning("Markdownブロックが空のため、フォールバックを使用")
            return [{
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": markdown_content}}]
                }
            }]
            
        return blocks
    
    @method_error_handler(APIError, "ページコンテンツクリアに失敗", passthrough_exceptions=[APIResponseError, RequestTimeoutError])
    def _clear_page_content(self, page_id: str) -> None:
        """
        ページのコンテンツをクリア
        
        Args:
            page_id: ページID
        """
        # ページの子ブロックを取得
        response = self.client.blocks.children.list(block_id=page_id)
        
        # 各ブロックを削除
        for block in response['results']:
            self.client.blocks.delete(block_id=block['id'])
    
    def _is_database_id(self, id_string: str) -> bool:
        """
        IDがデータベースIDかどうかを判定
        
        Args:
            id_string: ID文字列
            
        Returns:
            bool: データベースIDの場合True
        """
        # この関数は例外を発生させずに結果を返すため、
        # method_error_handlerデコレータは使用しない
        try:
            # 簡易判定：データベース情報の取得を試行
            self.client.databases.retrieve(database_id=id_string)
            return True
        except APIResponseError:
            # APIエラーの場合はデータベースIDではない
            return False
        except Exception as e:
            # その他の例外の場合もFalseを返すが、ログに記録
            self.logger.debug(f"データベースID判定でエラー: {str(e)}")
            return False
    
    @method_error_handler(APIError, "タイトル抽出に失敗")
    def _extract_title(self, title_array: List[Dict[str, Any]]) -> str:
        """
        Notionのタイトル配列からテキストを抽出
        
        Args:
            title_array: Notionタイトル配列
            
        Returns:
            str: タイトルテキスト
        """
        # None または 空の配列の場合は空文字列を返す
        if title_array is None or not title_array:
            return ""
        
        title_parts = []
        for item in title_array:
            if item.get('type') == 'text':
                title_parts.append(item['text']['content'])
        
        # 結合した結果を返す
        return ''.join(title_parts)
    
    @method_error_handler(APIError, "議事録ページ作成に失敗", passthrough_exceptions=[APIResponseError, RequestTimeoutError])
    def create_meeting_minutes_page(
        self,
        database_id: str,
        title: str,
        minutes_content: str,
        meeting_date: Optional[datetime] = None,
        participants: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        議事録専用ページを作成
        
        Args:
            database_id: 議事録データベースID
            title: 議事録タイトル
            minutes_content: 議事録コンテンツ
            meeting_date: 会議日時
            participants: 参加者リスト
            tags: タグリスト
            
        Returns:
            Dict: 作成されたページ情報
        """
        # 議事録用プロパティの準備
        properties = {
            "Title": {
                "title": [
                    {
                        "text": {
                            "content": title
                        }
                    }
                ]
            }
        }
        
        # 会議日時の設定
        if meeting_date:
            properties["Date"] = {
                "date": {
                    "start": meeting_date.isoformat()
                }
            }
        else:
            # テスト期待値に合わせて、会議日時が指定されていない場合も空のDateプロパティを設定
            properties["Date"] = {
                "date": None
            }
        
        # 参加者の設定
        if participants:
            properties["Participants"] = {
                "multi_select": [
                    {"name": participant} for participant in participants
                ]
            }
        else:
            # テスト期待値に合わせて、参加者が指定されていない場合も空のParticipantsプロパティを設定
            properties["Participants"] = {
                "multi_select": []
            }
        
        # タグの設定
        if tags:
            properties["Tags"] = {
                "multi_select": [
                    {"name": tag} for tag in tags
                ]
            }
        else:
            # テスト期待値に合わせて、タグが指定されていない場合も空のTagsプロパティを設定
            properties["Tags"] = {
                "multi_select": []
            }
        
        # コンテンツをNotionブロックに変換
        children = self._markdown_to_blocks(minutes_content)
        
        # ページ作成（直接APIを呼び出す）
        return self.client.pages.create(
            parent={
                "database_id": database_id
            },
            properties=properties,
            children=children
        )
    
    @method_error_handler(APIError, "クライアント情報取得に失敗", passthrough_exceptions=[APIResponseError, RequestTimeoutError])
    def get_client_info(self) -> Dict[str, Any]:
        """
        クライアント情報を取得
        
        Returns:
            Dict: クライアント情報（Notion APIのユーザー情報）
        """
        # Notion APIからユーザー情報を取得
        return self.client.users.me()