# 音声文字起こし・議事録自動生成ツール

このツールは音声ファイルを文字起こしし、Gemini 2.5 Flashを使って議事録を自動生成します。40分を超える音声ファイルは分割して処理し、文字起こしの精度を高めます。

## 主な機能

- Gemini 2.5 Flashを利用した音声ファイルの文字起こし
- ローカルの文字起こしサーバーも選択可能（従来方式）
- 40分超の長い音声ファイルを自動で分割して処理
- Gemini 2.5 Flashによる議事録自動生成
- 文字起こし結果と議事録をテキストファイルとして保存
- 動画ファイルにも対応し、暗い動画は自動でAAC音声に変換
- ファイル名で急な授業変更を指定可能（議事録に反映）

## 必要環境

- Python 3.6以上
- Gemini APIキー（文字起こしと議事録生成に必要）
- Notion APIトークン（Notionへのアップロードに必要、オプション）
- OpenCVおよびNumPy（requirements.txtでインストール）
- （オプション）http://localhost:5000/transcribe で動作するローカル文字起こしサーバー（従来方式の文字起こしに必要）

## インストール手順
1. Noteをコピー
   https://highfalutin-gooseberry-12c.notion.site/1e2270a9eb668049b2c9f5cd85a4443f?v=1e2270a9eb668107b467000c715eeb1a
2. このリポジトリをクローン
3. 必要なパッケージをインストール


```bash
pip install -r requirements.txt
```

4. APIキーを環境変数に設定

```bash
# Windowsの場合
set GEMINI_API_KEY=your_gemini_api_key_here
set NOTION_TOKEN=your_notion_token_here
set NOTION_DATABASE_ID=your_notion_database_id_here

# Linux/Macの場合
export GEMINI_API_KEY=your_gemini_api_key_here
export NOTION_TOKEN=your_notion_token_here
export NOTION_DATABASE_ID=your_notion_database_id_here
```

5. 設定ファイルの準備

settings.json.exampleをsettings.jsonにコピーして、必要な情報を設定します。
環境変数が設定されている場合は、環境変数が優先されます。

```bash
# Windowsの場合
copy settings.json.example settings.json

# Linux/Macの場合
cp settings.json.example settings.json
```

settings.jsonファイルを編集して、時間割情報や出力ディレクトリなどを設定します。
APIキーやトークンは環境変数で設定することを推奨します。

## 使い方

音声または動画ファイルのパスを指定してスクリプトを実行します。デフォルトではGemini 2.5 Flashを使用して文字起こしを行います。

```bash
python upload_and_transcribe.py --file パス/音声ファイル.mp3
```

動画ファイルにも対応しています。

```bash
python upload_and_transcribe.py --file パス/動画ファイル.mp4
```

ローカルの文字起こしサーバーを使用したい場合は、--use-serverオプションを指定します。

```bash
python upload_and_transcribe.py --file パス/メディアファイル.mp3 --use-server
```

文字起こしサーバーのURLを変更したい場合は、--urlオプションを指定します。
（--urlオプションを指定すると自動的にサーバーベースの文字起こしが使用されます）

```bash
python upload_and_transcribe.py --file パス/メディアファイル.mp3 --url http://サーバー:ポート/エンドポイント
```

### 分割ファイルの開始位置指定

長い音声ファイルを処理する際に、特定のファイル番号や時間から処理を開始することができます。

特定のファイル番号から処理を開始する場合（0始まり）：

```bash
python upload_and_transcribe.py --file パス/音声ファイル.mp3 --start-file 2
```

特定の時間（秒）から処理を開始する場合：

```bash
python upload_and_transcribe.py --file パス/音声ファイル.mp3 --start-time 1800
```

両方を組み合わせることも可能です：

```bash
python upload_and_transcribe.py --file パス/音声ファイル.mp3 --start-file 1 --start-time 600
```

## 動作概要

1. 入力ファイルが動画か音声かを判定
2. 動画の場合：
   - フレームの4箇所をチェックし暗いかを解析
   - 暗い場合は音声を抽出しAAC形式に変換
   - 暗くない場合は動画のまま処理
3. 音声/動画の長さを取得
4. 40分（2400秒）を超える場合：
   - チャンク数を切り上げ計算（duration/2400）
   - 均等な長さで音声を分割
   - 指定された開始ファイル番号（--start-file）と開始時間（--start-time）があれば、その位置から処理を開始
   - 各チャンクを個別に文字起こし（デフォルトではGemini 2.5 Flash、オプションでローカルサーバー）
   - 各チャンクの実際の開始時間と終了時間を記録
   - 文字起こし結果を結合（タイムスタンプは実際の開始時間に基づいて調整）
5. 40分以下の場合はファイル全体を一括で文字起こし（デフォルトではGemini 2.5 Flash、オプションでローカルサーバー）
6. 文字起こし後、Gemini 2.5 Flashで議事録を生成
7. 文字起こし結果と議事録をテキストファイルとして保存

## Notionへのアップロード

文字起こしした議事録をNotionにアップロードすることができます。

```bash
# 議事録をNotionにアップロードする
python upload_and_transcribe.py --file パス/メディアファイル.mp3 --upload-notion --notion-parent your_notion_database_id

# JSONファイルをNotionにアップロードする
python upload_to_notion.py --file パス/議事録.json --parent your_notion_database_id
```

Notionへのアップロードには、環境変数`NOTION_TOKEN`と`NOTION_DATABASE_ID`を設定するか、settings.jsonファイルに設定する必要があります。

## 多言語対応

このツールは多言語対応しています。現在、以下の言語がサポートされています：

- 日本語 (ja) - デフォルト
- 英語 (en)

言語設定を変更するには、`settings.json`ファイルの`app.language`パラメータを編集します：

```json
"app": {
  "language": "ja"  // "ja"（日本語）または"en"（英語）
}
```

新しい言語を追加するには、`lang`ディレクトリに新しい言語ファイル（例：`fr.json`）を作成し、既存の言語ファイルの構造に従って翻訳を追加します。

## 注意事項

- 文字起こしサーバーは、`file_path`キーで絶対パスを受け取り、`transcription`（文字起こしテキスト）と`segments`（詳細情報）を含むJSONを返す必要があります
- 動画ファイルの場合、自動で暗い動画（例：黒画面の音声記録）を検出し、AAC音声に変換して処理します
- 暗くない動画はそのまま処理されます
- 急な授業変更がある場合、ファイル名に「変更_新しい授業名」（例：「3限_変更_特別講義.mp3」）を含めることで、議事録に新しい授業名と変更注記が反映されます
- APIキーやトークンはリポジトリにコミットしないでください。環境変数を使用するか、.gitignoreに設定ファイルを追加してください。
