# 言語ベースのプロンプト読み込み機能

このドキュメントでは、言語ベースのプロンプト読み込み機能と、プロンプトタイプによるオーバーライド機能について説明します。

## 概要

言語ベースのプロンプト読み込み機能は、言語（例: "ja", "en"）に基づいて適切なベースプロンプトを読み込み、さらにプロンプトタイプ（例: "meeting", "school"）に基づいてベースプロンプトをオーバーライドする機能です。

この機能により、以下のことが可能になります：

1. 言語に応じた適切なベースプロンプトの読み込み
2. 特定のプロンプトタイプによるベースプロンプトのオーバーライド

## ファイル構造

言語ベースのプロンプト読み込み機能は、以下のファイル構造に基づいています：

```
src/prompts/definitions/
├── base_prompts_en.md  # 英語ベースプロンプト
├── base_prompts_ja.md  # 日本語ベースプロンプト
├── meeting_prompts_ja.md  # 会議用プロンプト（オーバーライド用）
└── school_prompts_ja.md  # 学校用プロンプト（オーバーライド用）
```

## 使用方法

### 基本的な使用方法

```python
from src.utils.prompt_loader import load_and_render_prompt_with_language

# 英語ベースプロンプトの読み込み
en_prompt = load_and_render_prompt_with_language(
    category="transcription",
    prompt_name="basic_transcription",
    language="en",
    custom_instructions="Please be accurate."
)

# 日本語ベースプロンプトの読み込み
ja_prompt = load_and_render_prompt_with_language(
    category="transcription",
    prompt_name="basic_transcription",
    language="ja",
    custom_instructions="正確さを重視してください。"
)
```

### プロンプトタイプによるオーバーライド

```python
# 会議用プロンプトオーバーライド
meeting_prompt = load_and_render_prompt_with_language(
    category="minutes_generation",
    prompt_name="detailed_minutes",
    language="ja",
    prompt_type="meeting",
    meeting_info="重要な会議",
    custom_instructions="詳細に記録してください。"
)

# 学校用プロンプトオーバーライド
school_prompt = load_and_render_prompt_with_language(
    category="minutes_generation",
    prompt_name="meeting_types_lecture",
    language="ja",
    prompt_type="school",
    lecture_info="プログラミング講義",
    custom_instructions="学習ポイントを強調してください。"
)
```

## 実装の詳細

### PromptLoader クラス

`PromptLoader` クラスには、言語ベースのプロンプト読み込み機能を実装するための以下の定数とメソッドが追加されました：

```python
# 言語ごとのベースプロンプトファイル
BASE_PROMPT_FILES = {
    "en": "base_prompts_en.md",
    "ja": "base_prompts_ja.md"
}

# プロンプトタイプごとのファイル
PROMPT_TYPE_FILES = {
    "meeting": "meeting_prompts_ja.md",
    "school": "school_prompts_ja.md"
}

def load_prompt_with_language(self, category: str, prompt_name: str, language: str = "ja", prompt_type: Optional[str] = None) -> PromptTemplate:
    """
    言語とプロンプトタイプを指定してプロンプトを読み込む
    
    Args:
        category: プロンプトカテゴリ（例: "transcription", "minutes_generation"）
        prompt_name: プロンプト名（例: "basic_transcription", "detailed_minutes"）
        language: 言語コード（例: "ja", "en"）
        prompt_type: プロンプトタイプ（例: "meeting", "school"）
        
    Returns:
        PromptTemplate: 読み込まれたプロンプトテンプレート
    """
    # 実装の詳細は省略
```

### 便利な関数

```python
def load_and_render_prompt_with_language(category: str, prompt_name: str, language: str = "ja", prompt_type: Optional[str] = None, **kwargs) -> str:
    """
    言語とプロンプトタイプを指定してプロンプトを読み込んでレンダリングする便利関数
    
    Args:
        category: プロンプトカテゴリ
        prompt_name: プロンプト名
        language: 言語コード（例: "ja", "en"）
        prompt_type: プロンプトタイプ（例: "meeting", "school"）
        **kwargs: テンプレートパラメータ
        
    Returns:
        str: レンダリングされたプロンプト
    """
    loader = get_prompt_loader()  # グローバルローダーを使用
    template = loader.load_prompt_with_language(category, prompt_name, language, prompt_type)
    return loader.render_prompt(template, **kwargs)
```

## プロンプトの優先順位

プロンプトの読み込みには以下の優先順位があります：

1. プロンプトタイプが指定されていて、そのタイプのプロンプトが存在する場合、そのプロンプトが使用されます。
2. プロンプトタイプが指定されていないか、そのタイプのプロンプトが存在しない場合、言語に基づいたベースプロンプトが使用されます。
3. 指定された言語のベースプロンプトが存在しない場合、デフォルトの言語（日本語）のベースプロンプトが使用されます。

## テスト

言語ベースのプロンプト読み込み機能のテストは、以下のファイルで実装されています：

- `src/tests/test_utils/test_prompt_loader.py`: ユニットテスト
- `src/scripts/test_language_prompts.py`: 手動テスト用スクリプト

## 注意事項

- プロンプトタイプによるオーバーライドは、そのタイプのプロンプトファイルに該当するタグが存在する場合のみ有効です。
- 言語コードは現在 "ja" と "en" のみサポートしています。他の言語を追加する場合は、`BASE_PROMPT_FILES` 定数に追加してください。
- プロンプトタイプは現在 "meeting" と "school" のみサポートしています。他のタイプを追加する場合は、`PROMPT_TYPE_FILES` 定数に追加してください。