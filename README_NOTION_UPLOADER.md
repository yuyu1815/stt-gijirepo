# Notion講義ノートアップローダー

このツールは、講義ノートをNotionデータベースにアップロードするためのシンプルなPythonスクリプトです。

## 機能

- マークダウン形式の講義ノートをNotionデータベースにアップロード
- 科目名と科目番号（webアプリケーション、DB設計）の設定
- 設定ファイル（settings.json）によるNotionの接続情報の管理
- コマンドラインからの簡単な操作

## 前提条件

- Python 3.6以上
- `requests`ライブラリ（`pip install requests`でインストール）
- NotionのAPIトークン
- 講義ノート用のNotionデータベース

## データベース構造

このツールは以下の構造を持つNotionデータベースに対応しています：

```json
{
  "title": "講義ノート",
  "properties": {
    "科目番号": {
      "type": "select",
      "id": "8b2%60",
      "options": [
        {
          "name": "webアプリケーション",
          "color": "blue"
        },
        {
          "name": "DB設計",
          "color": "brown"
        }
      ]
    },
    "作成日時": {
      "type": "created_time",
      "id": "%60W_p"
    },
    "科目": {
      "type": "title",
      "id": "title"
    }
  }
}
```

## セットアップ

1. NotionのAPIトークンを取得します（[Notion Developers](https://developers.notion.com/)から）
2. 上記の構造を持つデータベースをNotionで作成します
3. `settings.json`ファイルに以下の情報を設定します：

```json
{
  "notion": {
    "token": "your_notion_api_token",
    "url": "https://www.notion.so/your-notion-page-url",
    "database_id": "your_database_id"
  }
}
```

## 使い方

### コマンドライン

```bash
python notion_uploader.py lecture_note.md --subject "webアプリケーション"
```

### オプション

- `file`: アップロードする講義ノートファイルのパス（必須）
- `--database`, `-d`: NotionデータベースID（settings.jsonに設定されていない場合）
- `--subject`, `-s`: 科目番号（"webアプリケーション"または"DB設計"）
- `--settings`: 設定ファイルのパス（デフォルト: "settings.json"）

### Pythonコードから使用

```python
from notion_uploader import NotionUploader

# インスタンス化
uploader = NotionUploader()

# データベースIDの取得
database_id = uploader.settings["notion"]["database_id"]

# ファイルからアップロード
result = uploader.upload_lecture_note_from_file(database_id, "lecture_note.md", "webアプリケーション")

# または直接コンテンツをアップロード
title = "Webアプリケーション開発入門"
content = "# Webアプリケーション開発入門\n\n## 1. HTMLの基礎\n\nHTMLはWebページの構造を定義するマークアップ言語です。"
result = uploader.upload_lecture_note(database_id, title, content, "webアプリケーション")

# 結果の確認
if result["success"]:
    print(result["message"])
    print(f"URL: {result['url']}")
else:
    print(result["message"])
```

## 注意事項

- NotionのAPIトークンは秘密情報です。公開リポジトリにアップロードしないでください。
- 大量のリクエストを短時間に送信すると、NotionのAPIレート制限に達する可能性があります。