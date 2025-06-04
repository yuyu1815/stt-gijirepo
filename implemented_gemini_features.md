# Geminiを使用した実装機能

このプロジェクトでは、Google Gemini APIを活用して以下の機能を実装しています。

## 1. 動画/音声文字起こし

`src\services\transcription.py`の`_transcribe_with_gemini`メソッドを使用して、音声ファイルや動画ファイルから高精度な文字起こしを行います。

```python
def _transcribe_with_gemini(self, file_path: Path, prompt: str) -> str:
    """
    Gemini APIを使用して文字起こし
    """
```

## 2. ハルシネーション（幻覚）チェック

`src\services\hallucination.py`の`_check_with_gemini`メソッドを使用して、文字起こし結果に含まれる可能性のあるハルシネーション（AIが実際には存在しない情報を生成してしまう現象）をチェックします。

```python
def _check_with_gemini(self, file_path: Path, transcription_text: str, prompt: str) -> str:
    """
    Gemini APIを使用してハルシネーションチェック
    """
```

## 3. 議事録生成

`src\services\minutes.py`の`_generate_with_gemini`メソッドを使用して、文字起こし結果から構造化された議事録を生成します。

```python
def _generate_with_gemini(self, transcription_result: TranscriptionResult, prompt: str, extracted_images=None, video_analysis_result=None) -> str:
    """
    Gemini APIを使用して議事録内容を生成
    """
```

## 4. 要約生成

`src\services\minutes.py`の`_generate_summary_with_gemini`メソッドを使用して、文字起こし結果から要約を生成します。

```python
def _generate_summary_with_gemini(self, transcription_result: TranscriptionResult, prompt: str) -> str:
    """
    Gemini APIを使用して要約を生成
    """
```

## 5. 動画分析（削除済み）

以下の機能は要件により削除されました：

- 動画から重要なシーンを検出
- 重要シーンから画像を抽出
- 抽出した画像をGemini APIで分析
