# 音声文字起こし・議事録自動生成ツール

このプロジェクトは、音声ファイルや動画ファイルから文字起こしを行い、高品質な議事録を自動生成するツールです。Gemini APIを活用して、文字起こしの品質向上やハルシネーション（幻覚）の検出、構造化された議事録の生成を実現します。

## 機能

- 音声ファイル・動画ファイルの文字起こし
- 文字起こし結果のハルシネーションチェック
- 構造化された議事録の自動生成
- 動画からの画像抽出とシーン検出
- Notionへの議事録アップロード

## 必要条件

- Python 3.8以上
- FFmpeg（動画・音声処理用）
- Gemini API キー
- Notion API キー（Notionアップロード機能を使用する場合）

## インストール

1. リポジトリをクローン

```bash
git clone https://github.com/yourusername/tts-mcp.git
cd tts-mcp
```

2. 必要なパッケージをインストール

```bash
pip install -r requirements.txt
```

3. 設定ファイルを作成

```bash
cp config/settings.json.example config/settings.json
```

4. 設定ファイルを編集して、APIキーなどを設定

```bash
# お好みのエディタで設定ファイルを開く
notepad config/settings.json
```

## 使用方法

### 基本的な使い方

```bash
python main.py -i <入力ファイルまたはディレクトリ> -o <出力ディレクトリ>
```

### オプション

- `-i, --input`: 入力ファイルまたはディレクトリのパス（必須）
- `-o, --output-dir`: 出力ディレクトリのパス（オプション、デフォルト: `output`）
- `--upload-to-notion`: 議事録をNotionにアップロードする
- `--image-quality`: 抽出する画像の品質（1-5、高いほど高品質、デフォルト: 3）
- `--image-interval`: 画像抽出の間隔（秒、デフォルト: 60）
- `--scene-threshold`: シーン検出の閾値（0.0-1.0、高いほど厳しい、デフォルト: 0.3）
- `--min-scene-duration`: 最小シーン長（秒、デフォルト: 2.0）
- `--chunk-duration`: 音声チャンクの長さ（秒、デフォルト: 600）
- `--language`: 言語設定（ja/en、デフォルト: ja）
- `--config`: 設定ファイルのパス
- `--gemini-api-key`: Gemini APIキー
- `--notion-api-key`: Notion APIキー
- `--notion-database-id`: Notion データベースID
- `--version`: バージョン情報を表示

### 使用例

1. 単一の音声ファイルを処理

```bash
python main.py -i path/to/audio.mp3
```


2. ディレクトリ内のすべてのメディアファイルを処理

```bash
python main.py -i path/to/media/directory
```

3. 議事録をNotionにアップロード

```bash
python main.py -i path/to/audio.mp3 --upload-to-notion
```

## プロジェクト構造

```
tts-mcp/
├── config/                 # 設定ファイル
├── docs/                   # ドキュメント
├── output/                 # 出力ディレクトリ
├── prompts/                # プロンプトテンプレート
├── resources/              # リソースファイル
├── src/                    # ソースコード
│   ├── application/        # アプリケーション層
│   ├── domain/             # ドメイン層
│   ├── infrastructure/     # インフラ層
│   ├── services/           # サービス層
│   └── utils/              # ユーティリティ
├── tests/                  # テスト
├── main.py                 # メインスクリプト
└── README.md               # このファイル
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は[LICENSE](LICENSE)ファイルを参照してください。

## 謝辞

- このプロジェクトは、[FFmpeg](https://ffmpeg.org/)を使用しています。
- 文字起こしと議事録生成には、Google Gemini APIを使用しています。
