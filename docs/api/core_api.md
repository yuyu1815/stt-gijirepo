# STT議事録システム - Core API リファレンス

## 概要

STT議事録システムのCore APIは、音声処理、AI処理、ファイル操作、Notion連携などの基本機能を提供します。

## AI Services API

### GeminiService

Google Gemini APIを使用したAI処理サービスです。

#### 初期化

```python
from src.core.ai_services import GeminiService

service = GeminiService(
    api_key="your_gemini_api_key",
    model_name="gemini-1.5-pro"  # オプション
)
```

#### メソッド

##### transcribe_audio

音声ファイルの文字起こしを行います。

```python
def transcribe_audio(
    self,
    audio_file_path: str,
    prompt: Optional[str] = None,
    language: str = "ja"
) -> str
```

**パラメータ:**
- `audio_file_path`: 音声ファイルのパス
- `prompt`: カスタムプロンプト（オプション）
- `language`: 言語コード（デフォルト: "ja"）

**戻り値:**
- 文字起こし結果のテキスト

**使用例:**
```python
transcription = service.transcribe_audio(
    "meeting.wav",
    language="ja"
)
print(transcription)
```

##### check_transcription_quality

文字起こし結果の品質をチェックします。

```python
def check_transcription_quality(
    self,
    transcription: str,
    original_audio_duration: Optional[float] = None
) -> Dict[str, Any]
```

**パラメータ:**
- `transcription`: 文字起こしテキスト
- `original_audio_duration`: 元音声の長さ（秒）

**戻り値:**
- 品質チェック結果の辞書

**使用例:**
```python
quality_result = service.check_transcription_quality(
    transcription,
    original_audio_duration=300.0
)
print(f"信頼度: {quality_result['confidence']}")
print(f"品質: {quality_result['overall_quality']}")
```

##### generate_minutes

文字起こしから議事録を生成します。

```python
def generate_minutes(
    self,
    transcription: str,
    meeting_context: Optional[Dict[str, Any]] = None,
    format_type: str = "detailed"
) -> str
```

**パラメータ:**
- `transcription`: 文字起こしテキスト
- `meeting_context`: 会議のコンテキスト情報
- `format_type`: 出力形式（"detailed", "summary", "action_items"）

**戻り値:**
- 生成された議事録

**使用例:**
```python
context = {
    "meeting_type": "週次ミーティング",
    "participants": ["田中", "佐藤", "鈴木"],
    "date": "2024-01-15"
}

minutes = service.generate_minutes(
    transcription,
    meeting_context=context,
    format_type="detailed"
)
```

##### analyze_video_content

動画コンテンツの解析を行います。

```python
def analyze_video_content(
    self,
    video_file_path: str,
    analysis_type: str = "brightness"
) -> Dict[str, Any]
```

**パラメータ:**
- `video_file_path`: 動画ファイルのパス
- `analysis_type`: 解析タイプ（"brightness", "content", "scene"）

**戻り値:**
- 解析結果の辞書

**使用例:**
```python
analysis = service.analyze_video_content(
    "presentation.mp4",
    analysis_type="brightness"
)
print(f"明度レベル: {analysis['brightness_level']}")
```

## Audio Processing API

### AudioProcessor

音声ファイルの処理を行うクラスです。

#### 初期化

```python
from src.core.audio_processing import AudioProcessor

processor = AudioProcessor()
```

#### メソッド

##### load_audio

音声ファイルを読み込みます。

```python
def load_audio(self, file_path: str) -> AudioSegment
```

**使用例:**
```python
audio = processor.load_audio("meeting.wav")
print(f"音声長: {len(audio)}ms")
```

##### get_audio_metadata

音声ファイルのメタデータを取得します。

```python
def get_audio_metadata(self, file_path: str) -> Dict[str, Any]
```

**戻り値:**
```python
{
    "duration": 300.0,      # 秒
    "sample_rate": 44100,   # Hz
    "channels": 2,          # チャンネル数
    "frame_rate": 44100,    # フレームレート
    "file_size": 1024000    # バイト
}
```

##### split_audio

長時間音声を分割します。

```python
def split_audio(
    self,
    audio: AudioSegment,
    chunk_duration: int = 600,  # 秒
    overlap: int = 5           # 秒
) -> List[AudioSegment]
```

**使用例:**
```python
audio = processor.load_audio("long_meeting.wav")
chunks = processor.split_audio(audio, chunk_duration=300)
print(f"{len(chunks)}個のチャンクに分割されました")
```

##### save_audio_chunks

音声チャンクをファイルに保存します。

```python
def save_audio_chunks(
    self,
    chunks: List[AudioSegment],
    output_dir: str,
    base_name: str = "chunk",
    format: str = "wav"
) -> List[str]
```

**戻り値:**
- 保存されたファイルパスのリスト

##### convert_to_wav

音声ファイルをWAV形式に変換します。

```python
def convert_to_wav(
    self,
    input_path: str,
    output_path: Optional[str] = None
) -> str
```

##### normalize_audio

音声の音量を正規化します。

```python
def normalize_audio(
    self,
    audio: AudioSegment,
    target_dBFS: float = -20.0
) -> AudioSegment
```

##### extract_audio_from_video

動画から音声を抽出します。

```python
def extract_audio_from_video(
    self,
    video_path: str,
    output_path: Optional[str] = None
) -> str
```

##### cleanup_temp_files

一時ファイルを削除します。

```python
def cleanup_temp_files(self, file_paths: List[str]) -> None
```

## Video Processing API

### VideoProcessor

動画ファイルの処理を行うクラスです。

#### 主要メソッド

##### analyze_brightness

動画の明度を解析します。

```python
def analyze_brightness(self, video_path: str) -> Dict[str, Any]
```

**戻り値:**
```python
{
    "average_brightness": 0.3,
    "is_dark": True,
    "brightness_distribution": [0.1, 0.2, 0.3, 0.4],
    "recommendation": "audio_only"
}
```

##### extract_frames

動画からフレームを抽出します。

```python
def extract_frames(
    self,
    video_path: str,
    output_dir: str,
    interval: int = 30  # 秒
) -> List[str]
```

##### get_video_info

動画の基本情報を取得します。

```python
def get_video_info(self, video_path: str) -> Dict[str, Any]
```

## File Utils API

### ファイル操作ユーティリティ

#### get_file_info

ファイルの基本情報を取得します。

```python
def get_file_info(file_path: str) -> Dict[str, Any]
```

**戻り値:**
```python
{
    "file_name": "meeting.wav",
    "file_size": 1024000,
    "file_type": "audio",
    "mime_type": "audio/wav",
    "created_at": "2024-01-15T10:00:00",
    "modified_at": "2024-01-15T10:30:00"
}
```

#### validate_file_format

ファイル形式の妥当性をチェックします。

```python
def validate_file_format(file_path: str) -> bool
```

#### create_temp_directory

一時ディレクトリを作成します。

```python
def create_temp_directory(prefix: str = "stt_") -> str
```

#### safe_file_move

ファイルを安全に移動します。

```python
def safe_file_move(src: str, dst: str) -> bool
```

## Notion Client API

### NotionClient

Notion APIとの連携を行うクラスです。

#### 初期化

```python
from src.core.notion_client import NotionClient

client = NotionClient(token="your_notion_token")
```

#### メソッド

##### create_page

新しいページを作成します。

```python
def create_page(
    self,
    database_id: str,
    title: str,
    content: str,
    properties: Optional[Dict[str, Any]] = None
) -> str
```

**戻り値:**
- 作成されたページのID

**使用例:**
```python
page_id = client.create_page(
    database_id="your_database_id",
    title="2024年1月15日 週次ミーティング",
    content=minutes_content,
    properties={
        "Date": "2024-01-15",
        "Type": "Weekly Meeting"
    }
)
```

##### update_page

既存のページを更新します。

```python
def update_page(
    self,
    page_id: str,
    content: str,
    properties: Optional[Dict[str, Any]] = None
) -> bool
```

##### get_database_info

データベース情報を取得します。

```python
def get_database_info(self, database_id: str) -> Dict[str, Any]
```

##### search_pages

ページを検索します。

```python
def search_pages(
    self,
    query: str,
    database_id: Optional[str] = None
) -> List[Dict[str, Any]]
```

##### format_content_for_notion

コンテンツをNotion形式に変換します。

```python
def format_content_for_notion(self, markdown_content: str) -> List[Dict[str, Any]]
```

## エラーハンドリング

### カスタム例外クラス

```python
# 基底例外
class STTError(Exception):
    pass

# ファイル処理エラー
class FileProcessingError(STTError):
    pass

# API呼び出しエラー
class APIError(STTError):
    pass

# 品質チェックエラー
class QualityCheckError(STTError):
    pass

# Notionアップロードエラー
class NotionUploadError(STTError):
    pass
```

### エラー処理の例

```python
from src.core.ai_services import GeminiService
from src.utils.error_handling import APIError, FileProcessingError

try:
    service = GeminiService(api_key="your_key")
    result = service.transcribe_audio("audio.wav")
except FileProcessingError as e:
    print(f"ファイル処理エラー: {e}")
except APIError as e:
    print(f"API呼び出しエラー: {e}")
except Exception as e:
    print(f"予期しないエラー: {e}")
```

## パフォーマンス最適化

### 並列処理

```python
from concurrent.futures import ThreadPoolExecutor
from src.core.audio_processing import AudioProcessor

processor = AudioProcessor()

def process_file(file_path):
    audio = processor.load_audio(file_path)
    return processor.normalize_audio(audio)

# 複数ファイルの並列処理
file_paths = ["audio1.wav", "audio2.wav", "audio3.wav"]

with ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(process_file, file_paths))
```

### メモリ効率的な処理

```python
# 大きなファイルの処理
def process_large_audio(file_path):
    processor = AudioProcessor()
    
    # メタデータのみ先に取得
    metadata = processor.get_audio_metadata(file_path)
    
    if metadata["duration"] > 1800:  # 30分以上
        # 音声を読み込まずに直接分割
        audio = processor.load_audio(file_path)
        chunks = processor.split_audio(audio, chunk_duration=600)
        
        # チャンクごとに処理
        results = []
        for i, chunk in enumerate(chunks):
            result = process_audio_chunk(chunk)
            results.append(result)
            
            # メモリ解放
            del chunk
        
        return results
    else:
        # 通常処理
        audio = processor.load_audio(file_path)
        return process_audio_chunk(audio)
```

## 設定とカスタマイズ

### AI Service設定

```python
# カスタム設定でGeminiServiceを初期化
service = GeminiService(
    api_key="your_key",
    model_name="gemini-1.5-flash",  # より高速なモデル
)

# カスタムプロンプトの使用
custom_prompt = """
この音声を日本語で文字起こししてください。
以下の点に注意してください：
- 専門用語は正確に記録
- 話者の感情も含める
- 不明瞭な部分は[不明]と記載
"""

transcription = service.transcribe_audio(
    "meeting.wav",
    prompt=custom_prompt
)
```

### Audio Processor設定

```python
# カスタム設定での音声処理
processor = AudioProcessor()

# 高品質設定
audio = processor.load_audio("input.wav")
normalized = processor.normalize_audio(audio, target_dBFS=-12.0)  # より高い音量

# 分割設定のカスタマイズ
chunks = processor.split_audio(
    audio,
    chunk_duration=300,  # 5分
    overlap=10          # 10秒のオーバーラップ
)
```

## ベストプラクティス

### 1. リソース管理

```python
# 適切なリソース管理
def process_audio_safely(file_path):
    processor = AudioProcessor()
    temp_files = []
    
    try:
        audio = processor.load_audio(file_path)
        
        if len(audio) > 600000:  # 10分以上
            chunks = processor.split_audio(audio)
            chunk_paths = processor.save_audio_chunks(chunks, "temp/")
            temp_files.extend(chunk_paths)
            
            # 処理...
            
    finally:
        # 一時ファイルのクリーンアップ
        processor.cleanup_temp_files(temp_files)
```

### 2. エラー処理

```python
# 堅牢なエラー処理
def robust_transcription(file_path, max_retries=3):
    service = GeminiService(api_key="your_key")
    
    for attempt in range(max_retries):
        try:
            return service.transcribe_audio(file_path)
        except APIError as e:
            if attempt == max_retries - 1:
                raise e
            print(f"リトライ {attempt + 1}/{max_retries}: {e}")
            time.sleep(2 ** attempt)  # 指数バックオフ
```

### 3. 設定の外部化

```python
# 設定ファイルの使用
import json

def load_config(config_path="config.json"):
    with open(config_path, 'r') as f:
        return json.load(f)

config = load_config()
service = GeminiService(
    api_key=config["gemini_api_key"],
    model_name=config.get("gemini_model", "gemini-1.5-pro")
)
```