# プロンプト分離ガイド

## 概要

STT議事録システムでは、メンテナンス性の向上を目的として、プロンプトをPythonコードから分離し、Markdownファイルで管理する仕組みを導入しました。

## 背景

従来のシステムでは、プロンプトがPythonコード内にハードコードされており、以下の問題がありました：

- プロンプトの修正にコード変更が必要
- プロンプトの内容が分散して管理が困難
- 非技術者によるプロンプト改善が困難
- バージョン管理が複雑

## 新しいアーキテクチャ

### ディレクトリ構造

```
src/prompts/definitions/
├── README.md                    # プロンプト定義の説明
├── transcription/               # 文字起こし関連プロンプト
│   ├── basic_transcription.md
│   ├── high_quality_transcription.md
│   ├── chunk_transcription.md
│   └── video_transcription.md
├── minutes_generation/          # 議事録生成関連プロンプト
│   ├── detailed_minutes.md
│   ├── summary_minutes.md
│   ├── action_items.md
│   └── meeting_types/
│       ├── regular_meeting.md
│       ├── lecture.md
│       └── workshop.md
├── quality_check/               # 品質チェック関連プロンプト
│   ├── comprehensive_check.md
│   ├── hallucination_check.md
│   ├── accuracy_check.md
│   └── comparative_check.md
└── video_analysis/              # 動画解析関連プロンプト
    ├── brightness_analysis.md
    ├── content_analysis.md
    └── comprehensive_analysis.md
```

### プロンプトファイルの形式

各プロンプトファイルは以下の統一された形式で記述されます：

```markdown
# プロンプト名

## 概要
プロンプトの目的と用途の説明

## パラメータ
- `{parameter1}`: パラメータの説明
- `{parameter2}`: パラメータの説明

## プロンプト本文
実際のプロンプトテキスト

## 使用例
プロンプトの使用例（オプション）

## 注意事項
特別な注意事項があれば記載（オプション）
```

## プロンプトローダーの使用方法

### 基本的な使用方法

```python
from src.utils.prompt_loader import PromptLoader, load_and_render_prompt

# プロンプトローダーのインスタンス作成
loader = PromptLoader()

# プロンプトテンプレートの読み込み
template = loader.load_prompt("transcription", "basic_transcription")

# パラメータを適用してプロンプトをレンダリング
rendered_prompt = loader.render_prompt(
    template,
    language="ja",
    custom_instructions="追加の指示"
)
```

### 便利関数の使用

```python
from src.utils.prompt_loader import load_and_render_prompt

# 一行でプロンプトを読み込み・レンダリング
prompt = load_and_render_prompt(
    category="transcription",
    prompt_name="basic_transcription",
    language="ja",
    custom_instructions="追加の指示"
)
```

### グローバルインスタンスの使用

```python
from src.utils.prompt_loader import get_prompt_loader

# シングルトンインスタンスを取得
loader = get_prompt_loader()
template = loader.load_prompt("minutes_generation", "detailed_minutes")
```

## 既存コードの移行

### 移行前（レガシー）

```python
class TranscriptionPrompts:
    BASE_PROMPTS = {
        "ja": {
            TranscriptionQuality.STANDARD: """
            以下の音声ファイルを高品質で日本語文字起こししてください。
            
            要求事項:
            1. 話者の発言を正確に文字に起こす
            2. 専門用語や固有名詞は文脈から推測して正確に記述
            ...
            """
        }
    }
    
    @classmethod
    def get_transcription_prompt(cls, language="ja", quality=TranscriptionQuality.STANDARD):
        return cls.BASE_PROMPTS[language][quality]
```

### 移行後（新方式）

```python
from src.utils.prompt_loader import load_and_render_prompt

class TranscriptionPrompts:
    @classmethod
    def get_transcription_prompt(
        cls,
        language: str = "ja",
        quality: TranscriptionQuality = TranscriptionQuality.STANDARD,
        custom_instructions: Optional[str] = None
    ) -> str:
        try:
            # 品質レベルに応じてプロンプトファイルを選択
            prompt_mapping = {
                TranscriptionQuality.BASIC: "basic_transcription",
                TranscriptionQuality.STANDARD: "basic_transcription",
                TranscriptionQuality.HIGH: "high_quality_transcription",
                TranscriptionQuality.PROFESSIONAL: "high_quality_transcription"
            }
            
            prompt_name = prompt_mapping.get(quality, "basic_transcription")
            
            # Markdownプロンプトを読み込んでレンダリング
            return load_and_render_prompt(
                category="transcription",
                prompt_name=prompt_name,
                language=language,
                custom_instructions=custom_instructions or ""
            )
            
        except Exception as e:
            logger.warning(f"Failed to load Markdown prompt, falling back to legacy: {e}")
            # フォールバック: 既存のハードコードプロンプトを使用
            return cls._get_legacy_transcription_prompt(language, quality, custom_instructions)
```

## 新しいプロンプトの作成

### 1. Markdownファイルの作成

適切なカテゴリディレクトリに新しいMarkdownファイルを作成します：

```bash
# 例: 新しい文字起こしプロンプトを作成
touch src/prompts/definitions/transcription/specialized_transcription.md
```

### 2. プロンプト内容の記述

統一された形式でプロンプトを記述します：

```markdown
# 専門分野特化文字起こしプロンプト

## 概要
専門分野に特化した高精度な文字起こしを行うためのプロンプトです。

## パラメータ
- `{language}`: 音声の言語（例: "ja", "en"）
- `{domain}`: 専門分野（例: "医療", "法律", "技術"）
- `{terminology_list}`: 専門用語リスト（オプション）
- `{custom_instructions}`: カスタム指示（オプション）

## プロンプト本文

以下の{domain}分野の音声ファイルを{language}で専門的に文字起こししてください。

**専門分野**: {domain}
**言語**: {language}

**専門分野特化要求事項**:
- {domain}分野の専門用語を正確に認識してください
- 業界標準の表記法に従ってください
- 略語や専門的な表現も適切に処理してください

{terminology_list}

{custom_instructions}

## 使用例
```
専門分野: 医療
言語: ja
出力: 医療専門用語を含む正確な文字起こし
```

## 注意事項
- 専門用語の正確性を最優先としてください
- 不明な専門用語は[専門用語不明: 推測内容]として記載してください
```

### 3. プロンプトクラスでの利用

```python
def get_specialized_transcription_prompt(
    language: str = "ja",
    domain: str = "一般",
    terminology_list: Optional[str] = None,
    custom_instructions: Optional[str] = None
) -> str:
    return load_and_render_prompt(
        category="transcription",
        prompt_name="specialized_transcription",
        language=language,
        domain=domain,
        terminology_list=terminology_list or "",
        custom_instructions=custom_instructions or ""
    )
```

## エラーハンドリングとフォールバック

新しいシステムでは、Markdownプロンプトの読み込みに失敗した場合、自動的にレガシープロンプトにフォールバックします：

```python
try:
    # Markdownプロンプトを試行
    return load_and_render_prompt(...)
except Exception as e:
    logger.warning(f"Failed to load Markdown prompt, falling back to legacy: {e}")
    # レガシープロンプトを使用
    return legacy_prompt_method(...)
```

## パフォーマンス最適化

### キャッシュ機能

プロンプトローダーは自動的にプロンプトをキャッシュし、2回目以降の読み込みを高速化します：

```python
loader = PromptLoader()

# 初回読み込み（ファイルから読み込み）
template1 = loader.load_prompt("transcription", "basic_transcription")

# 2回目読み込み（キャッシュから取得）
template2 = loader.load_prompt("transcription", "basic_transcription")

# キャッシュをクリア（必要に応じて）
loader.clear_cache()
```

### シングルトンパターン

グローバルインスタンスを使用することで、メモリ使用量を最適化できます：

```python
from src.utils.prompt_loader import get_prompt_loader

# 常に同じインスタンスが返される
loader1 = get_prompt_loader()
loader2 = get_prompt_loader()
assert loader1 is loader2  # True
```

## テスト

### プロンプトローダーのテスト

```python
import pytest
from src.utils.prompt_loader import PromptLoader

def test_prompt_loading():
    loader = PromptLoader()
    template = loader.load_prompt("transcription", "basic_transcription")
    
    assert template.name == "basic_transcription"
    assert "language" in template.parameters
    assert template.content is not None

def test_prompt_rendering():
    loader = PromptLoader()
    template = loader.load_prompt("transcription", "basic_transcription")
    
    rendered = loader.render_prompt(
        template,
        language="ja",
        custom_instructions="テスト指示"
    )
    
    assert "ja" in rendered
    assert "テスト指示" in rendered
    assert "{language}" not in rendered
```

### プロンプトファイルの検証

新しいプロンプトファイルを作成した際は、以下の点を確認してください：

1. **必須セクション**: 「概要」と「プロンプト本文」セクションが存在する
2. **パラメータ形式**: `{parameter_name}` の形式でパラメータが定義されている
3. **文字エンコーディング**: UTF-8で保存されている
4. **Markdown形式**: 正しいMarkdown記法で記述されている

## トラブルシューティング

### よくある問題と解決方法

#### 1. プロンプトファイルが見つからない

```
FileNotFoundError: Prompt file not found: /path/to/prompt.md
```

**解決方法**:
- ファイルパスが正しいか確認
- ファイル名の拡張子が `.md` になっているか確認
- カテゴリディレクトリが存在するか確認

#### 2. 必須セクションが不足

```
ValueError: Missing required section '概要' in prompt: prompt_name
```

**解決方法**:
- Markdownファイルに「## 概要」セクションを追加
- 「## プロンプト本文」セクションが存在するか確認

#### 3. パラメータが置換されない

```
Warning: Unresolved parameters in prompt: ['parameter_name']
```

**解決方法**:
- `render_prompt` 呼び出し時に必要なパラメータを渡す
- パラメータ名が正しいか確認（`{parameter_name}` 形式）

#### 4. 文字化け

**解決方法**:
- Markdownファイルが UTF-8 で保存されているか確認
- BOM（Byte Order Mark）が含まれていないか確認

## ベストプラクティス

### 1. プロンプトの構造化

- 長いプロンプトは適切にセクション分けする
- 重要な指示は箇条書きで明確に記述する
- 例示を含めて理解しやすくする

### 2. パラメータの命名

- 分かりやすい名前を使用する（`{lang}` より `{language}`）
- 一貫した命名規則を使用する
- オプションパラメータは明確に示す

### 3. バージョン管理

- プロンプトの変更履歴をGitで管理する
- 重要な変更時はコミットメッセージに詳細を記載する
- 破壊的変更時は既存コードへの影響を確認する

### 4. テスト

- 新しいプロンプトには必ずテストを作成する
- パラメータの組み合わせをテストする
- エラーケースもテストに含める

## 今後の拡張予定

### 1. 多言語対応

- プロンプトファイルの多言語版作成
- 言語別ディレクトリ構造の導入

### 2. 動的プロンプト生成

- 条件に応じたプロンプトの動的生成
- テンプレートの継承機能

### 3. プロンプト品質評価

- プロンプトの効果測定機能
- A/Bテスト機能の導入

### 4. GUI管理ツール

- 非技術者向けのプロンプト編集ツール
- プレビュー機能付きエディタ

## まとめ

プロンプト分離により、以下のメリットが得られます：

- **保守性の向上**: プロンプトの修正が容易
- **可読性の向上**: プロンプトの内容が明確
- **拡張性の向上**: 新しいプロンプトの追加が簡単
- **協業の促進**: 非技術者もプロンプト改善に参加可能

この仕組みを活用して、より良いSTT議事録システムを構築していきましょう。