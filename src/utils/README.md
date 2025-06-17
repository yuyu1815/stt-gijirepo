# ユーティリティ

このディレクトリには、アプリケーション全体で使用される汎用的なユーティリティ関数やクラスが含まれています。これらのユーティリティは特定のドメインやビジネスロジックに依存せず、再利用可能な形で実装されています。

## ファイル一覧

- `ffmpeg.py` - FFmpegラッパー。音声・動画ファイルの変換、分割、情報抽出などの機能を提供します。
- `language.py` - 言語処理ユーティリティ。テキスト処理、言語検出、形態素解析などの機能を提供します。
- `parallel.py` - 並列処理ユーティリティ。マルチスレッドやマルチプロセスでの並列実行をサポートします。

## 使用方法

各ユーティリティは以下のようにインポートして使用します：

```python
from ..utils.ffmpeg import extract_audio, get_media_info
from ..utils.language import detect_language, split_into_sentences
from ..utils.parallel import parallel_map, ParallelExecutionMode

# FFmpegユーティリティの使用例
audio_path = extract_audio("video.mp4", "audio.wav")
media_info = get_media_info("audio.wav")

# 言語処理ユーティリティの使用例
lang = detect_language("こんにちは、世界")  # 'ja'
sentences = split_into_sentences("こんにちは。お元気ですか？")  # ['こんにちは。', 'お元気ですか？']

# 並列処理ユーティリティの使用例
results = parallel_map(
    lambda x: x * 2,
    [1, 2, 3, 4, 5],
    ParallelExecutionMode.THREAD
)  # [2, 4, 6, 8, 10]
```

## 設計原則

ユーティリティは以下の設計原則に従っています：

- 単一責任の原則：各ユーティリティは明確に定義された単一の責任を持ちます
- 依存性の最小化：外部ライブラリへの依存は必要最小限に抑えます
- 純粋関数の優先：可能な限り副作用のない純粋関数として実装します
- エラー処理の一貫性：例外処理と戻り値の扱いに一貫性を持たせます

## 注意事項

- FFmpegユーティリティを使用するには、システムにFFmpegがインストールされている必要があります
- 並列処理を行う際は、リソース使用量（CPU、メモリ）に注意してください
- 言語処理は対象言語によって精度が異なる場合があります