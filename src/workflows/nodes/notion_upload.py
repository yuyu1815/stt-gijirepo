"""
STT議事録システム - Notionアップロードノード

生成された議事録をNotionにアップロードするノード
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.workflows.state import STTState
from src.utils import get_logger, NotionUploadError, api_call_with_retry
from src.utils.logging_config import log_state_transition, LogContext

# Notion APIのインポートを試行
try:
    from notion_client import Client as NotionClient
    HAS_NOTION = True
except ImportError:
    HAS_NOTION = False


def upload_notion_node(state: STTState) -> STTState:
    """
    Notionへのアップロード
    
    処理内容:
    - Notion APIでのページ作成
    - コンテンツの構造化
    - エラーハンドリング
    
    Args:
        state: 現在の処理状態
        
    Returns:
        更新された処理状態
    """
    logger = get_logger("notion_upload")
    
    with LogContext(logger, "Notionアップロード", state["session_id"]) as ctx:
        try:
            # 状態遷移をログ
            log_state_transition(logger, state["processing_stage"], "notion_upload", state["session_id"])
            state["processing_stage"] = "notion_upload"
            
            # Notionアップロードが無効な場合はスキップ
            if not state.get("upload_to_notion", False):
                ctx.log_progress("Notionアップロードが無効のためスキップ")
                state["processing_log"].append("Notionアップロードをスキップ")
                return state
            
            # 議事録が空の場合はスキップ
            minutes = state.get("minutes", "")
            if not minutes:
                warning_msg = "議事録が空のためNotionアップロードをスキップします"
                state["warnings"].append(warning_msg)
                logger.warning(warning_msg)
                return state
            
            if not HAS_NOTION:
                error_msg = "Notion APIライブラリが利用できません"
                state["errors"].append(error_msg)
                logger.error(error_msg)
                return state
            
            ctx.log_progress("Notionアップロード開始")
            
            # Notion APIクライアントを初期化
            notion_client = _initialize_notion_client(state["settings"])
            
            # データベースIDを取得
            database_id = state.get("notion_database_id") or state["settings"].get("notion_database_id")
            if not database_id:
                error_msg = "NotionデータベースIDが設定されていません"
                state["errors"].append(error_msg)
                logger.error(error_msg)
                return state
            
            ctx.log_progress(f"データベースID: {database_id}")
            
            # ページデータを構築
            page_data = _build_page_data(state)
            
            # Notionページを作成
            page_response = _create_notion_page(notion_client, database_id, page_data)
            
            # 結果を状態に保存
            state["notion_page_id"] = page_response["id"]
            page_url = page_response.get("url", "")
            
            ctx.log_progress(f"Notionページ作成完了: {page_url}")
            state["processing_log"].append(f"Notionアップロード完了: {page_url}")
            
            logger.info(f"Notionアップロード完了: ページID {state['notion_page_id']}")
            
        except Exception as e:
            error_msg = f"Notionアップロードエラー: {str(e)}"
            state["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)
            
            # エラー時もページIDがあれば保存
            if hasattr(e, 'page_id') and e.page_id:
                state["notion_page_id"] = e.page_id
    
    return state


def _initialize_notion_client(settings: Dict[str, Any]) -> NotionClient:
    """
    Notion APIクライアントを初期化
    
    Args:
        settings: システム設定
        
    Returns:
        初期化されたNotionクライアント
    """
    notion_token = settings.get("notion_token")
    if not notion_token:
        raise NotionUploadError("Notionトークンが設定されていません")
    
    try:
        client = NotionClient(auth=notion_token)
        return client
    except Exception as e:
        raise NotionUploadError(f"Notionクライアントの初期化に失敗しました: {str(e)}")


def _build_page_data(state: STTState) -> Dict[str, Any]:
    """
    Notionページデータを構築
    
    Args:
        state: 現在の状態
        
    Returns:
        ページデータ
    """
    # クラス情報を取得
    class_info = state.get("class_info", {})
    class_name = class_info.get("name", "不明")
    teacher = class_info.get("teacher", "不明")
    datetime_str = class_info.get("datetime", "不明")
    
    # タイトルを生成
    title = _generate_page_title(class_info, state)
    
    # プロパティを構築
    properties = {
        "Name": {
            "title": [
                {
                    "text": {
                        "content": title
                    }
                }
            ]
        }
    }
    
    # 追加プロパティ（データベース構造に依存）
    if class_name != "不明":
        properties["授業名"] = {
            "rich_text": [
                {
                    "text": {
                        "content": class_name
                    }
                }
            ]
        }
    
    if teacher != "不明":
        properties["担当教員"] = {
            "rich_text": [
                {
                    "text": {
                        "content": teacher
                    }
                }
            ]
        }
    
    if datetime_str != "不明":
        properties["日時"] = {
            "rich_text": [
                {
                    "text": {
                        "content": datetime_str
                    }
                }
            ]
        }
    
    # 品質スコアを追加
    quality_result = state.get("quality_check_result")
    if quality_result:
        quality_score = quality_result.get("overall_score", 0.0)
        properties["品質スコア"] = {
            "number": quality_score
        }
    
    # ページコンテンツを構築
    children = _build_page_content(state)
    
    return {
        "properties": properties,
        "children": children
    }


def _generate_page_title(class_info: Dict[str, Any], state: STTState) -> str:
    """
    Notionページのタイトルを生成
    
    Args:
        class_info: クラス情報
        state: 現在の状態
        
    Returns:
        生成されたタイトル
    """
    class_name = class_info.get("name", "不明")
    datetime_str = class_info.get("datetime", "")
    
    if class_name != "不明":
        if datetime_str and datetime_str != "不明":
            return f"{class_name} - {datetime_str}"
        else:
            return f"{class_name} - 議事録"
    
    # クラス情報がない場合は現在日時を使用
    return f"議事録 - {datetime.now().strftime('%Y年%m月%d日 %H:%M')}"


def _build_page_content(state: STTState) -> List[Dict[str, Any]]:
    """
    Notionページのコンテンツを構築
    
    Args:
        state: 現在の状態
        
    Returns:
        ページコンテンツのブロック配列
    """
    children = []
    
    # サマリーセクション
    summary = state.get("summary", "")
    if summary:
        children.extend(_create_summary_blocks(summary))
    
    # 議事録メインコンテンツ
    minutes = state.get("minutes", "")
    if minutes:
        children.extend(_create_minutes_blocks(minutes))
    
    # 品質情報セクション
    quality_result = state.get("quality_check_result")
    if quality_result:
        children.extend(_create_quality_blocks(quality_result))
    
    # メタデータセクション
    children.extend(_create_metadata_blocks(state))
    
    return children


def _create_summary_blocks(summary: str) -> List[Dict[str, Any]]:
    """
    サマリーブロックを作成
    
    Args:
        summary: サマリー内容
        
    Returns:
        サマリーブロック配列
    """
    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "📋 サマリー"
                        }
                    }
                ]
            }
        }
    ]
    
    # サマリー内容を段落として追加
    summary_lines = summary.split('\n')
    for line in summary_lines:
        if line.strip():
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": line.strip()
                            }
                        }
                    ]
                }
            })
    
    return blocks


def _create_minutes_blocks(minutes: str) -> List[Dict[str, Any]]:
    """
    議事録ブロックを作成
    
    Args:
        minutes: 議事録内容
        
    Returns:
        議事録ブロック配列
    """
    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "📝 議事録"
                        }
                    }
                ]
            }
        }
    ]
    
    # Markdownを簡単なNotionブロックに変換
    blocks.extend(_convert_markdown_to_notion_blocks(minutes))
    
    return blocks


def _create_quality_blocks(quality_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    品質情報ブロックを作成
    
    Args:
        quality_result: 品質チェック結果
        
    Returns:
        品質情報ブロック配列
    """
    blocks = [
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "🔍 品質情報"
                        }
                    }
                ]
            }
        }
    ]
    
    # 品質スコア
    overall_score = quality_result.get("overall_score", 0.0)
    blocks.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": f"品質スコア: {overall_score:.2f}"
                    }
                }
            ]
        }
    })
    
    # サマリー
    summary = quality_result.get("summary", "")
    if summary:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": summary
                        }
                    }
                ]
            }
        })
    
    return blocks


def _create_metadata_blocks(state: STTState) -> List[Dict[str, Any]]:
    """
    メタデータブロックを作成
    
    Args:
        state: 現在の状態
        
    Returns:
        メタデータブロック配列
    """
    blocks = [
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "ℹ️ 処理情報"
                        }
                    }
                ]
            }
        }
    ]
    
    # 処理日時
    timestamp = state.get("timestamp")
    if timestamp:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"処理日時: {timestamp.strftime('%Y年%m月%d日 %H:%M:%S')}"
                        }
                    }
                ]
            }
        })
    
    # セッションID
    session_id = state.get("session_id", "")
    if session_id:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"セッションID: {session_id}"
                        }
                    }
                ]
            }
        })
    
    # 音声長
    audio_duration = state.get("audio_duration")
    if audio_duration:
        minutes = int(audio_duration // 60)
        seconds = int(audio_duration % 60)
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"音声長: {minutes}分{seconds}秒"
                        }
                    }
                ]
            }
        })
    
    return blocks


def _convert_markdown_to_notion_blocks(markdown: str) -> List[Dict[str, Any]]:
    """
    MarkdownをNotionブロックに変換（簡略版）
    
    Args:
        markdown: Markdown文字列
        
    Returns:
        Notionブロック配列
    """
    blocks = []
    lines = markdown.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 見出しの処理
        if line.startswith('# '):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": line[2:].strip()
                            }
                        }
                    ]
                }
            })
        elif line.startswith('## '):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": line[3:].strip()
                            }
                        }
                    ]
                }
            })
        elif line.startswith('### '):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": line[4:].strip()
                            }
                        }
                    ]
                }
            })
        # 箇条書きの処理
        elif line.startswith('- ') or line.startswith('* '):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": line[2:].strip()
                            }
                        }
                    ]
                }
            })
        # 通常の段落
        else:
            # 太字の処理
            rich_text = _parse_rich_text(line)
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": rich_text
                }
            })
    
    return blocks


def _parse_rich_text(text: str) -> List[Dict[str, Any]]:
    """
    テキストをリッチテキスト形式に解析
    
    Args:
        text: 解析対象テキスト
        
    Returns:
        リッチテキスト配列
    """
    import re
    
    rich_text = []
    
    # 太字の処理（簡略版）
    parts = re.split(r'(\*\*.*?\*\*)', text)
    
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            # 太字
            content = part[2:-2]
            rich_text.append({
                "type": "text",
                "text": {
                    "content": content
                },
                "annotations": {
                    "bold": True
                }
            })
        elif part:
            # 通常のテキスト
            rich_text.append({
                "type": "text",
                "text": {
                    "content": part
                }
            })
    
    return rich_text if rich_text else [{"type": "text", "text": {"content": text}}]


def _create_notion_page(client: NotionClient, database_id: str, page_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Notionページを作成
    
    Args:
        client: Notionクライアント
        database_id: データベースID
        page_data: ページデータ
        
    Returns:
        作成されたページの情報
    """
    logger = get_logger("notion_upload")
    
    try:
        def _create_page():
            return client.pages.create(
                parent={"database_id": database_id},
                properties=page_data["properties"],
                children=page_data["children"]
            )
        
        response = api_call_with_retry(
            _create_page,
            max_retries=3,
            logger=logger
        )
        
        return response
        
    except Exception as e:
        raise NotionUploadError(
            f"Notionページの作成に失敗しました: {str(e)}",
            database_id=database_id
        )


def test_notion_connection(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Notion接続をテスト（既存コードとの互換性のため）
    
    Args:
        settings: システム設定
        
    Returns:
        テスト結果
    """
    result = {
        "success": False,
        "message": "",
        "user_info": None
    }
    
    try:
        if not HAS_NOTION:
            result["message"] = "Notion APIライブラリが利用できません"
            return result
        
        client = _initialize_notion_client(settings)
        
        # ユーザー情報を取得してテスト
        user_info = client.users.me()
        
        result["success"] = True
        result["message"] = "Notion接続テスト成功"
        result["user_info"] = user_info
        
    except Exception as e:
        result["message"] = f"Notion接続テスト失敗: {str(e)}"
    
    return result


def get_database_info(settings: Dict[str, Any], database_id: str) -> Dict[str, Any]:
    """
    データベース情報を取得（既存コードとの互換性のため）
    
    Args:
        settings: システム設定
        database_id: データベースID
        
    Returns:
        データベース情報
    """
    try:
        if not HAS_NOTION:
            raise NotionUploadError("Notion APIライブラリが利用できません")
        
        client = _initialize_notion_client(settings)
        database_info = client.databases.retrieve(database_id)
        
        return {
            "success": True,
            "database": database_info
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }