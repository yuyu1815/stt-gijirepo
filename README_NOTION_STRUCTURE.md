# Notion構造取得ツール

このツールは、Notionのデータベースやページの構造を取得し、整形して表示するためのコマンドラインツールです。データベースのプロパティ、ページのプロパティ、ブロックの内容などを取得することができます。

## 機能

- データベースの構造（プロパティなど）を取得
- ページのプロパティを取得
- ページやブロックの内容を取得（再帰的な取得も可能）
- 取得した情報をJSONファイルに保存

## 必要な環境

- Python 3.6以上
- `requests`ライブラリ
- Notion API トークン

## セットアップ

1. Notion APIのトークンを取得します。
   - [Notion Developers](https://developers.notion.com/) にアクセスし、インテグレーションを作成してトークンを取得してください。
   - 取得したトークンは`settings.json`ファイルに以下の形式で保存してください：
   ```json
   {
     "notion": {
       "token": "your_notion_api_token_here"
     }
   }
   ```

2. 必要なライブラリをインストールします。
   ```
   pip install requests
   ```

## 使用方法

### コマンドライン引数

```
python get_notion_structure.py [オプション]
```

#### オプション

- `--database DATABASE_ID`: データベースIDを指定してデータベースの構造を取得
- `--page PAGE_ID`: ページIDを指定してページのプロパティを取得
- `--blocks BLOCK_ID`: ページIDまたはブロックIDを指定してブロック内容を取得
- `--recursive`: ブロック内容を再帰的に取得する（`--blocks`と共に使用）
- `--output FILE_PATH`: 結果を保存するJSONファイルのパス
- `--token-file FILE_PATH`: Notionトークンを含むファイルのパス（デフォルト: `settings.json`）
- `-h, --help`: ヘルプメッセージを表示

### IDの取得方法

Notion上のデータベースやページのIDは、URLから取得できます。

- データベースID: `https://www.notion.so/workspace/database_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`
  - `database_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`の部分がデータベースIDです。
- ページID: `https://www.notion.so/workspace/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`
  - `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`の部分がページIDです。

### 出力形式

#### データベース構造

データベースの構造は以下の形式で表示されます：

```
=== データベース構造 ===
タイトル: データベース名

プロパティ:
  - プロパティ名 (プロパティタイプ)
    選択肢:
      * 選択肢1 (色)
      * 選択肢2 (色)
  - プロパティ名 (relation)
    関連データベース: database_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

#### ページプロパティ

ページのプロパティは以下の形式で表示されます：

```
=== ページプロパティ ===
  - プロパティ名 (プロパティタイプ): 値
  - タイトル (title): ページタイトル
  - 日付 (date): 2023-01-01
  - 選択肢 (multi_select): 選択肢1, 選択肢2
```

#### ブロック内容

ブロックの内容は以下の形式で表示されます：

```
=== ブロック内容 ===
- paragraph: テキスト内容
- heading_1: 見出し1
- bulleted_list_item: リスト項目
- image: 画像URL
- code (言語):
  コード内容
  複数行にわたるコード
- table: 幅=3, 列ヘッダー=True, 行ヘッダー=False
```

再帰的に取得した場合は、子ブロックがインデントされて表示されます。

## 使用例

### データベースの構造を取得

```
python get_notion_structure.py --database database_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### ページのプロパティを取得

```
python get_notion_structure.py --page XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### ページのブロック内容を取得

```
python get_notion_structure.py --blocks XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### ページのブロック内容を再帰的に取得

```
python get_notion_structure.py --blocks XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX --recursive
```

### 結果をJSONファイルに保存

```
python get_notion_structure.py --database database_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX --output database_structure.json
```

## 注意事項

- Notion APIの利用には制限があります。短時間に多数のリクエストを送信すると、レート制限に達する可能性があります。
- 再帰的なブロック取得は、ページの構造が複雑な場合に時間がかかる場合があります。
- ページやデータベースへのアクセス権限がない場合、エラーが発生します。インテグレーションをページやデータベースと共有していることを確認してください。