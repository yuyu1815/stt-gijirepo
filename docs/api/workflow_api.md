# STT議事録システム - Workflow API リファレンス

## 概要

STT議事録システムのワークフローAPIは、LangGraphベースの構造化された処理フローを提供します。音声・動画ファイルから議事録生成までの全プロセスを自動化します。

## メイン API

### execute_stt_workflow

音声・動画ファイルを処理して議事録を生成するメイン関数です。

```python
def execute_stt_workflow(
    file_path: str,
    config: STTConfig,
    upload_to_notion: bool = False
) -> STTState
```

#### パラメータ

- **file_path** (`str`): 処理対象の音声・動画ファイルパス
- **config** (`STTConfig`): システム設定オブジェクト
- **upload_to_notion** (`bool`, optional): Notionへの自動アップロード有効化。デフォルト: `False`

#### 戻り値

- **STTState**: 処理結果を含む状態オブジェクト

#### 使用例

```python
from src.workflows.stt_workflow import execute_stt_workflow
from src.workflows.state import create_default_config

# 設定の作成
config = create_default_config()
config["gemini_api_key"] = "your_api_key_here"

# ワークフロー実行
result = execute_stt_workflow(
    file_path="meeting_audio.wav",
    config=config,
    upload_to_notion=True
)

# 結果の確認
if result["final_status"] == "success":
    print("議事録:", result["minutes"])
else:
    print("エラー:", result["errors"])
```

### execute_batch_processing

複数ファイルの並列処理を行います。

```python
def execute_batch_processing(
    file_paths: List[str],
    config: STTConfig,
    max_concurrent: int = 3
) -> List[STTState]
```

#### パラメータ

- **file_paths** (`List[str]`): 処理対象ファイルパスのリスト
- **config** (`STTConfig`): システム設定オブジェクト
- **max_concurrent** (`int`, optional): 最大並列処理数。デフォルト: `3`

#### 戻り値

- **List[STTState]**: 各ファイルの処理結果リスト

#### 使用例

```python
file_list = ["audio1.wav", "audio2.mp3", "video1.mp4"]
results = execute_batch_processing(
    file_paths=file_list,
    config=config,
    max_concurrent=2
)

for i, result in enumerate(results):
    print(f"ファイル {i+1}: {result['final_status']}")
```

## 状態管理

### STTState

処理状態を管理するTypedDictクラスです。

```python
class STTState(TypedDict):
    # 基本情報
    session_id: str
    timestamp: datetime
    
    # 入力情報
    file_path: str
    original_filename: str
    file_size: int
    settings: Dict[str, Any]
    
    # ファイル解析結果
    file_type: Optional[str]  # "video" | "audio"
    mime_type: Optional[str]
    is_video_dark: Optional[bool]
    audio_duration: Optional[float]
    audio_sample_rate: Optional[int]
    audio_channels: Optional[int]
    
    # 処理状態
    chunks: Optional[List[str]]
    chunk_durations: Optional[List[float]]
    processing_stage: str
    
    # AI処理結果
    transcription: Optional[str]
    transcription_confidence: Optional[float]
    quality_check_result: Optional[Dict[str, Any]]
    minutes: Optional[str]
    summary: Optional[str]
    
    # クラス情報
    class_info: Optional[Dict[str, Any]]
    
    # エラー・ログ
    errors: List[str]
    warnings: List[str]
    processing_log: List[str]
    performance_metrics: Dict[str, float]
    
    # 設定・フラグ
    upload_to_notion: bool
    notion_database_id: Optional[str]
    notion_page_id: Optional[str]
    
    # 出力情報
    output_files: List[str]
    final_status: str  # "success" | "error" | "partial"
```

### STTConfig

システム設定を管理するTypedDictクラスです。

```python
class STTConfig(TypedDict):
    # API設定
    gemini_api_key: str
    gemini_model: str
    notion_token: Optional[str]
    
    # 処理設定
    max_audio_duration: int  # 秒
    chunk_size: int  # 秒
    max_retries: int
    retry_delay: float
    
    # 品質設定
    min_confidence_threshold: float
    enable_quality_check: bool
    enable_hallucination_check: bool
    
    # 出力設定
    output_format: str  # "markdown" | "text" | "json"
    include_timestamps: bool
    include_speaker_labels: bool
    
    # Notion設定
    notion_database_id: Optional[str]
    notion_template_id: Optional[str]
```

## ワークフローノード

### ファイル解析ノード

```python
def analyze_file_node(state: STTState) -> STTState
```

入力ファイルの解析と基本情報の取得を行います。

- ファイル形式の判定
- メタデータの抽出
- 音声長の取得
- ファイルサイズの確認

### 動画処理ノード

```python
def process_video_node(state: STTState) -> STTState
```

動画ファイルの前処理を行います。

- 動画の明度解析
- 必要に応じて音声抽出
- フォーマット変換

### 音声分割ノード

```python
def split_audio_node(state: STTState) -> STTState
```

長時間音声の分割処理を行います。

- 音声長の確認
- 適切なサイズでの分割
- 分割ファイルの管理

### 文字起こしノード

```python
def transcribe_node(state: STTState) -> STTState
```

Gemini APIを使用した文字起こしを行います。

- 単一/分割ファイルの処理
- リトライ機能付きAPI呼び出し
- 結果の統合

### 品質チェックノード

```python
def quality_check_node(state: STTState) -> STTState
```

文字起こし結果の品質チェックを行います。

- ハルシネーション検出
- 信頼度スコア計算
- 品質レポート生成

### 議事録生成ノード

```python
def generate_minutes_node(state: STTState) -> STTState
```

議事録の生成を行います。

- 構造化された議事録の生成
- サマリーの作成
- フォーマット調整

### Notionアップロードノード

```python
def upload_notion_node(state: STTState) -> STTState
```

Notionへのアップロードを行います。

- Notion APIでのページ作成
- コンテンツの構造化
- エラーハンドリング

## ユーティリティ関数

### create_initial_state

初期状態オブジェクトを作成します。

```python
def create_initial_state(
    file_path: str,
    config: STTConfig,
    upload_to_notion: bool = False
) -> STTState
```

### create_default_config

デフォルト設定オブジェクトを作成します。

```python
def create_default_config() -> STTConfig
```

### get_workflow_status

ワークフローの現在状態を取得します。

```python
def get_workflow_status(state: STTState) -> Dict[str, Any]
```

## エラーハンドリング

### カスタム例外

```python
class STTError(Exception):
    """STTシステム基底例外"""
    pass

class FileProcessingError(STTError):
    """ファイル処理エラー"""
    pass

class APIError(STTError):
    """API呼び出しエラー"""
    pass

class QualityCheckError(STTError):
    """品質チェックエラー"""
    pass

class NotionUploadError(STTError):
    """Notionアップロードエラー"""
    pass
```

### エラー処理例

```python
try:
    result = execute_stt_workflow(file_path, config)
except FileProcessingError as e:
    print(f"ファイル処理エラー: {e}")
except APIError as e:
    print(f"API呼び出しエラー: {e}")
except Exception as e:
    print(f"予期しないエラー: {e}")
```

## パフォーマンス監視

### メトリクス取得

処理結果のperformance_metricsフィールドから各種メトリクスを取得できます。

```python
result = execute_stt_workflow(file_path, config)
metrics = result["performance_metrics"]

print(f"総処理時間: {metrics['total_time']:.2f}秒")
print(f"文字起こし時間: {metrics['transcription_time']:.2f}秒")
print(f"議事録生成時間: {metrics['minutes_generation_time']:.2f}秒")
```

## 設定例

### 基本設定

```python
config = {
    "gemini_api_key": "your_api_key",
    "gemini_model": "gemini-1.5-pro",
    "max_audio_duration": 2400,  # 40分
    "chunk_size": 600,  # 10分
    "max_retries": 5,
    "retry_delay": 2.0,
    "min_confidence_threshold": 0.7,
    "enable_quality_check": True,
    "enable_hallucination_check": True,
    "output_format": "markdown",
    "include_timestamps": True,
    "include_speaker_labels": False
}
```

### Notion連携設定

```python
config.update({
    "notion_token": "your_notion_token",
    "notion_database_id": "your_database_id"
})
```

## 制限事項

- 音声ファイルの最大長: 40分（設定で変更可能）
- 対応形式: WAV, MP3, MP4, AVI, MOV
- 同時処理数: 最大5ファイル（推奨3ファイル）
- API制限: Gemini APIの利用制限に準拠

## トラブルシューティング

### よくある問題

1. **APIキーエラー**
   - 環境変数またはconfigでAPIキーが正しく設定されているか確認

2. **ファイル形式エラー**
   - 対応形式のファイルを使用しているか確認
   - FFmpegが正しくインストールされているか確認

3. **メモリ不足**
   - 長時間音声の場合は分割処理が有効になっているか確認
   - システムメモリが十分にあるか確認

4. **Notionアップロードエラー**
   - NotionトークンとデータベースIDが正しく設定されているか確認
   - データベースの権限設定を確認