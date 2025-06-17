# サービス層

このディレクトリには、アプリケーションのコアサービスを実装するモジュールが含まれています。各サービスは特定の機能領域に責任を持ち、ドメインオブジェクトを操作します。

## ファイル一覧

- `transcription.py` - 音声ファイルの文字起こしサービス。Gemini APIを使用して高精度な文字起こしを実現します。
- `minutes.py` - 文字起こし結果から構造化された議事録を生成するサービス。
- `minutes_parser.py` - 議事録テキストを解析し、構造化されたオブジェクトに変換するサービス。
- `media_processor.py` - 音声・動画ファイルの処理サービス。ファイルの分割、変換、情報抽出などを行います。
- `video_analysis.py` - 動画分析サービス。動画の内容を分析し、重要なシーンの検出やスクリーンショットの抽出を行います。
- `hallucination.py` - 幻覚検出サービス。AIによる文字起こしや議事録生成における幻覚（事実と異なる内容の生成）を検出します。
- `class_info.py` - 授業情報サービス。授業に関するメタデータの管理や解析を行います。
- `notion.py` - Notion連携サービス。生成された議事録をNotionに送信・管理します。

## 使用方法

各サービスはシングルトンパターンで実装されており、以下のようにインポートして使用します：

```python
from ..services.transcription import transcription_service
from ..services.minutes import minutes_generator_service

# 文字起こしの実行
result = transcription_service.transcribe_audio(media_file)

# 議事録の生成
minutes = minutes_generator_service.generate_minutes(result, media_file)
```

## 注意事項

- 各サービスはAPIキーなどの設定が必要な場合があります。設定は`config_manager`を通じて取得します。
- 大きなファイルを処理する場合は、メモリ使用量に注意してください。
- APIの呼び出しにはレート制限があるため、大量のリクエストを行う場合は適切な待機処理を実装してください。
