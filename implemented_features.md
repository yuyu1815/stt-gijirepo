# 音声文字起こし・議事録自動生成ツール 機能一覧

このドキュメントでは、音声文字起こし・議事録自動生成ツールに実装されている機能について説明します。

## 1. 概要

このツールは、音声ファイルや動画ファイルから自動的に文字起こしを行い、構造化された議事録を生成するアプリケーションです。Gemini APIを活用した高精度な文字起こしと議事録生成を実現し、Notionへの自動アップロード機能も備えています。

## 2. 主要機能

### 2.1 コマンドラインインターフェース

- 入力ファイルまたはディレクトリの指定
- 出力ディレクトリの指定
- 動画分析モード（通常版と軽量版）
- Notionアップロード機能
- 各種パラメータの設定（画像品質、画像抽出間隔、シーン検出閾値など）
- 言語設定（日本語/英語）
- 設定ファイルの指定
- APIキー設定（Gemini、Notion）

### 2.2 メディア処理機能

- 対応フォーマット
  - 音声ファイル: mp3, wav, aac, m4a, flac
  - 動画ファイル: mp4, avi, mov, mkv, webm
- 動画からの音声抽出
- 長時間メディアの自動分割（チャンク処理）
- 動画の品質判定（暗い動画の検出）
- 複数ファイルの並列処理

### 2.3 文字起こし機能

- Gemini APIを使用した高精度な文字起こし
- 話者の区別
- タイムスタンプ付きセグメント
- 長時間メディアの並列チャンク処理
- 再試行メカニズム（指数バックオフ）
- スクリーンショット指示の検出と処理

### 2.4 ハルシネーション（幻覚）チェック機能

- 文字起こし結果の信頼性評価
- 重大度レベル（NONE, LOW, MEDIUM, HIGH）
- 検出されたハルシネーションの理由と修正テキストの提供
- 長時間メディアのチャンク処理
- 結果レポートの生成（検出率、重大度別の集計、詳細結果）

### 2.5 動画分析機能

- 重要シーンの自動検出
  - シーン変化の検出
  - 講師の動きや指示の検出
  - 黒板/ホワイトボードの使用検出
- 重要シーンからの画像抽出
- 画像の分析
  - 画像の説明生成
  - 重要度評価（HIGH, MEDIUM, LOW）
  - タイプ分類（SLIDE, BOARD, INSTRUCTOR, OTHER）
- 動画全体の要約、トピック、重要ポイントの抽出
- 分析結果のMarkdownおよびJSON形式での保存

### 2.6 議事録生成機能

- 文字起こし結果からの構造化された議事録生成
- 議事録の構成
  - 要約
  - 議事内容
  - 重要ポイント
  - タスク・宿題（担当者、期限を含む）
  - 用語集
  - 画像（タイムスタンプ、説明を含む）
- 動画分析結果の統合
- Markdown形式での保存

### 2.7 Notion連携機能

- 生成された議事録のNotionデータベースへのアップロード
- ページプロパティの設定（タイトル、日付、科目名、講師名など）
- 構造化されたページコンテンツの作成
  - 見出し、段落、箇条書きリスト、区切り線などのブロック
  - 長いテキストの自動分割
- MOC（Map of Content）機能
  - インデックスページ（MOC）の自動作成と更新
  - 詳細なMOCページ検証と堅牢なエラー処理
    - MOCページIDの形式検証（UUID形式チェック）
    - MOCページの存在確認と構造検証
    - 「議事録一覧」セクションの自動検出と作成
    - 重複エントリの防止
  - 目次ブロックによるページ内ナビゲーション
  - 関連ページへのリンクとバックリンクの自動作成
  - 親子関係によるページ階層の構築
  - 同じ科目の議事録の自動関連付け
- 再試行メカニズム（指数バックオフ）

## 3. 設定オプション

### 3.1 基本設定

- `app.name`: アプリケーション名
- `app.version`: バージョン
- `output_dir`: 出力ディレクトリ
- `temp_dir`: 一時ファイルディレクトリ
- `log_dir`: ログディレクトリ
- `log_level`: ログレベル
- `lang_dir`: 言語リソースディレクトリ
- `prompt_dir`: プロンプトディレクトリ
- `ffmpeg_path`: FFmpegのパス
- `ffprobe_path`: FFprobeのパス
- `language`: 言語設定（ja/en）

### 3.2 API設定

- `gemini.api_key`: Gemini APIキー
- `gemini.model`: Geminiモデル
- `notion.api_key`: Notion APIキー
- `notion.database_id`: NotionデータベースID
- `notion.moc_page_id`: Notion MOCページID
- `notion.max_retries`: 最大再試行回数
- `notion.retry_delay`: 再試行間隔（秒）
- `notion.max_retry_delay`: 最大再試行間隔（秒）
- `notion.max_block_size`: 最大ブロックサイズ

### 3.3 メディア処理設定

- `media_processor.chunk_duration`: チャンク分割の長さ（秒）

### 3.4 動画分析設定

- `video_analysis.image_quality`: 画像品質（1-5、高いほど高品質）
- `video_analysis.image_interval`: 画像抽出間隔（秒）
- `video_analysis.scene_detection_threshold`: シーン検出閾値（0.0-1.0、高いほど厳しい）
- `video_analysis.min_scene_duration`: 最小シーン長（秒）

### 3.5 文字起こし設定

- `transcription.model`: 文字起こしモデル
- `transcription.language`: 文字起こし言語
- `transcription.task`: 文字起こしタスク
- `transcription.word_timestamps`: 単語レベルのタイムスタンプ有効化

### 3.6 ハルシネーション設定

- `hallucination.enabled`: ハルシネーションチェック有効化
- `hallucination.threshold`: ハルシネーション検出閾値

### 3.7 議事録設定

- `minutes.format`: 議事録フォーマット（markdown）
- `minutes.include_summary`: 要約の含有
- `minutes.include_important_points`: 重要ポイントの含有
- `minutes.include_tasks`: タスクの含有
- `minutes.include_glossary`: 用語集の含有
- `minutes.include_images`: 画像の含有
- `minutes.prompt_file`: 議事録生成プロンプトファイル

### 3.8 並列処理設定

- `parallel.thread_workers`: スレッドワーカー数
- `parallel.process_workers`: プロセスワーカー数

## 4. 使用方法

基本的な使用方法は以下の通りです：

```
python main.py -i <入力ファイルまたはディレクトリ> -o <出力ディレクトリ> [オプション]
```

### 主要なオプション

- `-i, --input`: 入力ファイルまたはディレクトリのパス
- `-o, --output-dir`: 出力ディレクトリのパス
- `--upload-to-notion`: 議事録をNotionにアップロードする
- `--language`: 言語設定（ja/en）
- `--config`: 設定ファイルのパス
- `--version`: バージョン情報を表示

詳細なオプションについては、`python main.py --help`を実行して確認してください。
