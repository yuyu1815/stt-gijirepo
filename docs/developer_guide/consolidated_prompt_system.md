# 統合プロンプト管理システム

## 概要

STT議事録システムでは、プロンプト管理の効率化と一元化を目的として、プロンプト定義を複数の論理的なグループに分けつつ、各グループ内ではXMLライクなタグを用いて各プロンプトを識別する新しい管理方式を導入しました。

この新しいシステムでは、以下のメリットが得られます：

- **管理の効率化**: 関連するプロンプトを一つのファイルにまとめることで、管理が容易になります
- **一元的な把握**: 同じカテゴリのプロンプトを一覧できるため、全体像の把握が容易になります
- **オーバーライド機能**: 特定のプロンプトだけをカスタマイズする仕組みを提供します
- **後方互換性**: 従来の個別ファイル方式もサポートしているため、移行が容易です

## ファイル構造

プロンプト定義は以下の主要なMarkdownファイルに集約されています：

- `base_prompts.md`: 一般的・汎用的なプロンプト（例: 基本的な文字起こし、包括的な品質チェックなど）
- `school_prompts.md`: 授業・講義関連のプロンプト（例: 授業議事録、教育コンテンツ向け動画解析など）
- `meeting_prompts.md`: 会議関連のプロンプト（例: 詳細議事録、アクションアイテム抽出、会議向け動画解析など）
- `override_prompts.md`: 上記のプロンプトを特定の状況下で上書きするためのプロンプト

これらのファイルは `src/prompts/definitions/` ディレクトリに配置されています。

## プロンプト定義の形式

各プロンプトは、一意のXMLライクなタグで囲まれています。タグ名はプロンプトの識別子として機能し、`カテゴリ_プロンプト名` の形式で命名されています。

```markdown
<transcription_basic_transcription>
# 基本文字起こしプロンプト

## 概要
音声ファイルから基本的な文字起こしを行うためのプロンプトです。一般的な会話や議論の文字起こしに使用されます。

## パラメータ
- `{language}`: 音声の言語（例: "ja", "en"）
- `{custom_instructions}`: カスタム指示（オプション）

## プロンプト本文

以下の音声ファイルを正確に文字起こししてください。

**言語**: {language}

**指示事項**:
- 話者が複数いる場合は、話者を区別して記録してください（例: Aさん：、Bさん：）
- 専門用語や固有名詞も可能な限り正確に書き起こしてください
- 音声が不明瞭な場合は[不明瞭]と記載してください
- 背景音や雑音は無視してください
- タイムスタンプは不要です
- 「えー」「あのー」などのフィラーは適度に省略してください

{custom_instructions}
</transcription_basic_transcription>
```

各プロンプトの内部構造は、従来のMarkdownセクション（`# プロンプト名`, `## 概要`, `## パラメータ`, `## プロンプト本文`など）を維持しています。

## オーバーライド機能

`override_prompts.md` ファイルに定義されたプロンプトは、他のファイルで定義された同じ名前のプロンプトよりも優先されます。これにより、特定のプロンプトだけをカスタマイズすることが可能です。

例えば、`base_prompts.md` に定義された `transcription_basic_transcription` プロンプトを上書きするには、`override_prompts.md` に同じタグ名で新しい定義を追加します：

```markdown
<transcription_basic_transcription>
# 基本文字起こしプロンプト（カスタマイズ版）

## 概要
音声ファイルから基本的な文字起こしを行うためのカスタマイズされたプロンプトです。特定のプロジェクトや状況に合わせて調整されています。

...（以下省略）...
</transcription_basic_transcription>
```

## PromptLoaderの使用方法

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

### 利用可能なプロンプトの取得

```python
from src.utils.prompt_loader import get_prompt_loader

loader = get_prompt_loader()
available_prompts = loader.get_available_prompts()

# 結果の例
# {
#   "transcription": ["basic_transcription", "high_quality_transcription", ...],
#   "minutes_generation": ["detailed_minutes", "action_items", ...],
#   ...
# }
```

## 新しいプロンプトの追加

### 1. 適切なファイルの選択

新しいプロンプトを追加する場合、まず適切なファイルを選択します：

- 一般的・汎用的なプロンプト → `base_prompts.md`
- 授業・講義関連のプロンプト → `school_prompts.md`
- 会議関連のプロンプト → `meeting_prompts.md`
- 既存プロンプトのカスタマイズ → `override_prompts.md`

### 2. プロンプトの追加

選択したファイルに、XMLライクなタグで囲まれた新しいプロンプトを追加します：

```markdown
<カテゴリ_プロンプト名>
# プロンプトタイトル

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
</カテゴリ_プロンプト名>
```

### 3. プロンプトの使用

追加したプロンプトは、従来と同じ方法で使用できます：

```python
prompt = load_and_render_prompt(
    category="カテゴリ",
    prompt_name="プロンプト名",
    parameter1="値1",
    parameter2="値2"
)
```

## 後方互換性

新しいシステムは、従来の個別ファイル方式もサポートしています。`src/prompts/definitions/カテゴリ/プロンプト名.md` の形式で配置された個別のMarkdownファイルも、引き続き使用できます。

ただし、同じカテゴリとプロンプト名の組み合わせが統合ファイルと個別ファイルの両方に存在する場合、統合ファイルのプロンプトが優先されます。さらに、`override_prompts.md` に定義されたプロンプトは、他のすべての定義よりも優先されます。

## エラーハンドリングとフォールバック

プロンプトの読み込みに失敗した場合、以下の順序でフォールバックが試行されます：

1. `override_prompts.md` で定義されたプロンプト
2. 対応する統合ファイル（`base_prompts.md`, `school_prompts.md`, `meeting_prompts.md`）で定義されたプロンプト
3. 個別のMarkdownファイル（`src/prompts/definitions/カテゴリ/プロンプト名.md`）

すべての方法で読み込みに失敗した場合、`FileNotFoundError` 例外が発生します。

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

## 移行ガイド

### 既存のプロンプトの移行

既存の個別プロンプトファイルを統合ファイルに移行するには：

1. プロンプトの種類に応じて適切な統合ファイルを選択
2. XMLライクなタグで囲んだ形式でプロンプトを追加
3. 元の個別ファイルは削除するか、バックアップとして残しておく

### コード変更の必要性

既存のコードは変更なしで動作しますが、新しいプロンプトを追加する際は統合ファイルを使用することを推奨します。

## トラブルシューティング

### よくある問題と解決方法

#### 1. プロンプトが見つからない

```
FileNotFoundError: Prompt not found: category/prompt_name
```

**解決方法**:
- タグ名が正しいか確認（`カテゴリ_プロンプト名`の形式）
- 統合ファイル内にプロンプトが存在するか確認
- カテゴリとプロンプト名が正しいか確認

#### 2. XMLタグが正しく解析されない

```
ValueError: Prompt tag 'category_prompt_name' not found in file
```

**解決方法**:
- XMLタグが正しく閉じられているか確認（`</カテゴリ_プロンプト名>`）
- タグ内に他のXMLタグが入れ子になっていないか確認
- ファイルがUTF-8でエンコードされているか確認

#### 3. プロンプトの形式が不正

```
ValueError: Missing required section '概要' in prompt: prompt_name
```

**解決方法**:
- 必須セクション（`## 概要`と`## プロンプト本文`）が存在するか確認
- セクションヘッダーが正しい形式か確認（`## `で始まる）

## まとめ

統合プロンプト管理システムにより、以下のメリットが得られます：

- **保守性の向上**: 関連するプロンプトを一つのファイルにまとめることで、管理が容易になります
- **可読性の向上**: 同じカテゴリのプロンプトを一覧できるため、全体像の把握が容易になります
- **拡張性の向上**: オーバーライド機能により、特定のプロンプトだけをカスタマイズできます
- **後方互換性**: 従来の個別ファイル方式もサポートしているため、移行が容易です

この仕組みを活用して、より効率的なプロンプト管理を実現しましょう。