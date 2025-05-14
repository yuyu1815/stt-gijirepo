# Notion議事録アップロード機能

このドキュメントでは、音声から生成した議事録をNotionにアップロードする機能について説明します。

## 前提条件

1. Notionのインテグレーショントークンを取得し、`settings.json`ファイルに保存してください。
   - トークンは以下のように`settings.json`ファイルの`notion`セクションに追加してください：
   ```json
   {
     "notion": {
       "token": "ntn_xxxxxxxx"
     }
   }
   ```
   - トークンの取得方法は[Notion API公式ドキュメント](https://developers.notion.com/docs/getting-started)を参照してください。
   - 注：後方互換性のため、従来の`mcp.txt`ファイル（`notion:ntn_xxxxxxxx`形式）も引き続きサポートしています。

2. アップロード先のNotionページまたはデータベースのIDを取得してください。
   - ページIDはNotionのURLから取得できます（例: `https://www.notion.so/myworkspace/a8aec43384f447ed84390e8e42c2e089`の場合、IDは`a8aec43384f447ed84390e8e42c2e089`）。
   - データベースIDは`database_`で始まる文字列です。

## 使用方法

### 1. 音声ファイルから議事録を生成してNotionにアップロードする

```bash
python upload_and_transcribe.py --file "音声ファイルのパス" --upload-notion --notion-parent "NotionのページまたはデータベースID"
```

#### オプション

- `--file`: 処理する音声ファイルのパス（必須）
- `--upload-notion`: 議事録をNotionにアップロードするフラグ
- `--notion-parent`: Notionの親ページまたはデータベースID（必須、`--upload-notion`を指定した場合）
- `--notion-token-file`: Notionトークンを含むファイルのパス（デフォルト: `settings.json`）

### 2. 既存の議事録ファイルをNotionにアップロードする

既に生成済みの議事録ファイルをNotionにアップロードする場合は、以下のコマンドを使用します：

```bash
python upload_to_notion.py --file "議事録ファイルのパス" --parent "NotionのページまたはデータベースID"
```

#### オプション

- `--file`: アップロードする議事録ファイルのパス（必須）
- `--parent`: Notionの親ページまたはデータベースID（必須）
- `--token-file`: Notionトークンを含むファイルのパス（デフォルト: `settings.json`）

## 議事録のフォーマット

アップロードされる議事録は、以下のセクションを含むマークダウン形式です：

1. 基本情報（日時、講師、出席者、記録担当）
2. 授業内容（箇条書き形式）
3. 要約（キーポイント）
4. 課題・宿題
5. 専門用語集

## トラブルシューティング

1. **「トークンファイルが見つかりません」または「Notionトークンが設定ファイルに見つかりませんでした」エラー**
   - `settings.json`ファイルがプロジェクトのルートディレクトリに存在することを確認してください。
   - `settings.json`ファイルに`notion`セクションと`token`キーが正しく設定されていることを確認してください。
   - 後方互換性のために`--notion-token-file`または`--token-file`オプションで別のトークンファイルを指定することもできます。

2. **「ページの作成に失敗しました」エラー**
   - Notionトークンが有効であることを確認してください。
   - 指定したページまたはデータベースIDが正しいことを確認してください。
   - トークンに指定したページへの書き込み権限があることを確認してください。

3. **「議事録のアップロードに失敗しました」エラー**
   - 議事録ファイルが存在し、正しいフォーマットであることを確認してください。
   - インターネット接続が正常であることを確認してください。
