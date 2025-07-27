# プロンプト管理システム再構築技術定義書

## 1. 目的

現在のSTT議事録システムにおけるプロンプト管理は、各プロンプトが個別のMarkdownファイルとして`src/prompts/definitions/`以下に分散して配置されています。これにより、プロンプトの追加や編集の際に複数のファイルを操作する必要があり、管理が煩雑になるという課題があります。

本定義書は、この課題を解決するため、プロンプト定義を複数の論理的なグループに分けつつ、各グループ内ではXMLライクなタグ（例: `<prompt_name>...</prompt_name>`)を用いて各プロンプトを識別する新しい管理方式への移行を目的とします。これにより、プロンプトの追加・編集作業の効率化と一元管理を実現しつつ、論理的な分離を保ちます。

## 2. 現行アーキテクチャの概要

### ファイル構造
- `src/prompts/definitions/`以下に、カテゴリごとのサブディレクトリ（例: `transcription/`, `minutes_generation/`）が存在し、その中に個別のMarkdownファイル（例: `basic_transcription.md`, `detailed_minutes.md`）としてプロンプトが定義されています。

### `PromptLoader`の動作
- `src/utils/prompt_loader.py`内の`PromptLoader`クラスがプロンプトの読み込みとレンダリングを担当します。
- `load_prompt(category, prompt_name)`メソッドは、`category`と`prompt_name`に基づいて対応するMarkdownファイルのパスを構築し、ファイルを読み込みます。
- `_parse_markdown`メソッドは、読み込んだMarkdownファイルの内容を解析し、`## 概要`, `## パラメータ`, `## プロンプト本文`などのセクションを抽出して`PromptTemplate`オブジェクトを生成します。
- `render_prompt`メソッドは、`PromptTemplate`オブジェクトと引数として渡されたパラメータを用いて、プロンプト本文内のプレースホルダー（例: `{parameter_name}`）を置換します。

## 3. 提案アーキテクチャ

### ファイル構造
- プロンプト定義を以下の主要なMarkdownファイルに集約します。
    - `base_prompts.md`: 一般的・汎用的なプロンプト（例: 基本的な文字起こし、包括的な品質チェックなど）
    - `school_prompts.md`: 授業・講義関連のプロンプト（例: 授業議事録、教育コンテンツ向け動画解析など）
    - `meeting_prompts.md`: 会議関連のプロンプト（例: 詳細議事録、アクションアイテム抽出、会議向け動画解析など）
    - `override_prompts.md` (新規): 上記のプロンプトを特定の状況下で上書きするためのプロンプト。同じタグ名を持つプロンプトが定義された場合、このファイルの内容が優先されます。
- 既存のカテゴリ別サブディレクトリおよび個別のMarkdownファイルは廃止します。

### 各`*.md`ファイルの形式
- 各プロンプトは、一意のXMLライクなタグで囲まれます。タグ名はプロンプトの識別子として機能します。
- 各プロンプトの内部構造は、現行のMarkdownセクション（`# プロンプト名`, `## 概要`, `## パラメータ`, `## プロンプト本文`など）を維持します。

**`base_prompts.md`の例:**

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

<quality_check_comprehensive_check>
# 包括的品質チェックプロンプト

## 概要
文字起こし結果や議事録の品質を総合的に評価し、改善点を特定するためのプロンプトです。正確性、完全性、読みやすさなど複数の観点から品質をチェックします。

## パラメータ
- `{content}`: チェック対象のテキスト（文字起こしまたは議事録）
- `{content_type}`: コンテンツの種類（"transcription", "minutes", "summary"）
- `{language}`: 対象言語（例: "ja", "en"）
- `{quality_criteria}`: 品質基準（オプション）
- `{custom_instructions}`: カスタム指示（オプション）

## プロンプト本文

以下のコンテンツの品質を包括的にチェックしてください。

**コンテンツ種類**: {content_type}
**言語**: {language}
**品質基準**: {quality_criteria}

**品質チェック指示事項**:

...（以下略）...
</quality_check_comprehensive_check>
```

**`meeting_prompts.md`の例:**

```markdown
<minutes_generation_detailed_minutes>
# 詳細議事録生成プロンプト

## 概要
文字起こし結果から詳細で構造化された議事録を生成するためのプロンプトです。会議の内容を体系的に整理し、重要な情報を漏れなく記録します。

## パラメータ
- `{transcription}`: 文字起こし結果
- `{meeting_info}`: 会議情報（日時、参加者、議題など）
- `{language}`: 出力言語（例: "ja", "en"）
- `{format_type}`: 議事録の形式（例: "detailed", "summary"）
- `{custom_instructions}`: カスタム指示（オプション）

## プロンプト本文

以下の文字起こし結果から詳細な議事録を作成してください。

**言語**: {language}
**形式**: {format_type}
**会議情報**: {meeting_info}

**議事録作成指示事項**:

...（以下略）...
</minutes_generation_detailed_minutes>

<minutes_generation_action_items>
# アクションアイテム抽出プロンプト

## 概要
会議の文字起こし結果から具体的なアクションアイテム（タスク・課題・宿題）を抽出し、構造化して整理するためのプロンプトです。

## パラメータ
- `{transcription}`: 文字起こし結果
- `{meeting_context}`: 会議の種類や文脈（例: "プロジェクト会議", "授業", "研修"）
- `{language}`: 出力言語（例: "ja", "en"）
- `{include_deadlines}`: 期限情報を含めるかどうか（true/false）
- `{custom_instructions}`: カスタム指示（オプション）

## プロンプト本文

以下の文字起こし結果からアクションアイテム（課題・タスク・宿題）を抽出してください。

**言語**: {language}
**会議種類**: {meeting_context}
**期限情報の抽出**: {include_deadlines}

**アクションアイテム抽出指示事項**:

...（以下略）...
</minutes_generation_action_items>
```

- タグ名は、`{category}_{prompt_name}`の形式とします。（例: `transcription_basic_transcription`）

## 4. `PromptLoader`への変更点

### `__init__`
- `self.prompts_dir`は、`src/prompts/definitions/`を指すように変更はありません。
- `PromptLoader`は、初期化時にマスタープロンプトファイル（`base_prompts.md`, `school_prompts.md`, `meeting_prompts.md`）を読み込み、内部的に全てのプロンプトブロックをキャッシュします。
- **上書きの考慮**: `override_prompts.md`が存在する場合、このファイルを最後に読み込み、同じタグ名を持つプロンプトがあれば、その内容でキャッシュを上書きします。これにより、`override_prompts.md`のプロンプトが優先されます。`load_prompt`呼び出し時のファイルI/Oを最小限に抑えます。

### `load_prompt(self, category: str, prompt_name: str) -> PromptTemplate`
- このメソッドは、まず`category`と`prompt_name`を結合したタグ名（例: `transcription_basic_transcription`）を生成します。
- 次に、このタグ名に対応するプロンプトブロックを内部キャッシュから抽出します。キャッシュは初期化時に全てのマスターファイルと`override_prompts.md`から構築されており、`override_prompts.md`の内容が優先されるように処理されています。
- 抽出したプロンプトブロックの内容を、既存の`_parse_markdown`メソッドに渡して解析させます。
- キャッシュのキーはタグ名を使用します。

### `_parse_markdown(self, content: str, prompt_name: str) -> PromptTemplate`
- このメソッドは、タグで囲まれた単一のプロンプトブロックの内容を処理するように変更はありません。
- ただし、`load_prompt`から渡される`content`は、既に特定のプロンプトブロックのみが抽出された状態であることを前提とします。

### `_extract_sections(self, lines: List[str]) -> Dict[str, str]`
- このメソッドは、Markdownのセクション（`## 概要`など）を抽出する既存のロジックを維持します。

### 新規追加メソッド: `_extract_prompt_block(self, full_content: str, tag_name: str) -> str`
- `load_prompt`から呼び出され、マスターファイル全体のコンテンツと検索対象の`tag_name`を受け取ります。
- 正規表現などを用いて、`<tag_name>...</tag_name>`の形式で囲まれたブロックの内容を抽出して返します。
- タグが見つからない場合は`ValueError`などを発生させます。

### `render_prompt(self, template: PromptTemplate, **kwargs) -> str`
- 変更なし。

### `get_available_prompts(self) -> Dict[str, List[str]]`
- このメソッドは、全てのマスタープロンプトファイル（`base_prompts.md`, `school_prompts.md`, `meeting_prompts.md`, `override_prompts.md`）を読み込み、その中から全てのプロンプトタグを抽出し、カテゴリとプロンプト名に分解してリストを生成するように変更します。
- `category_dir.rglob('*.md')`のようなファイルシステム走査は不要になります。

## 5. 移行戦略

1.  **マスタープロンプトファイルの作成**: 既存の全てのMarkdownプロンプトファイルを読み込み、提案されたXMLライクなタグで囲み、論理的なグループ（ベース、学校、会議）に分けて`base_prompts.md`, `school_prompts.md`, `meeting_prompts.md`に結合します。必要に応じて、特定のプロンプトを上書きするための`override_prompts.md`も作成します。この作業はスクリプト化することが望ましいです。
2.  **`PromptLoader`の改修**: 上記「4. `PromptLoader`への変更点」に従って`PromptLoader`クラスを改修します。
3.  **既存プロンプトファイルの削除**: `PromptLoader`の改修とテストが完了した後、`src/prompts/definitions/`以下の既存の個別のMarkdownファイルを削除します。
4.  **関連コードの修正**: `PromptLoader`を直接呼び出している箇所（例: `minutes_generation.py`, `quality_check.py`など）で、`load_and_render_prompt`関数が正しく動作することを確認します。

## 6. テスト考慮事項

-   **単体テスト**:
    -   `_extract_prompt_block`メソッドが正しくプロンプトブロックを抽出できるか。
    -   `load_prompt`が適切なマスターファイルから特定のプロンプトを正しく読み込めるか。
    -   **`override_prompts.md`に定義されたプロンプトが、他のマスターファイルに同じタグ名で定義されたプロンプトを正しく上書きするか。**
    -   存在しないプロンプト名が指定された場合に適切にエラーを発生させるか。
    -   `get_available_prompts`が全てのマスターファイルから全てのプロンプト名を正しく列挙できるか。
-   **結合テスト**:
    -   `minutes_generation.py`, `quality_check.py`, `transcription.py`, `video_analysis.py`などの各プロンプトクラスが、新しい`PromptLoader`を通じてプロンプトを正しく取得し、レンダリングできるか。
    -   既存のワークフロー（議事録生成、品質チェックなど）が、新しいプロンプトシステムで問題なく動作するか。
-   **パフォーマンス**: 複数のマスターファイルからの読み込みとキャッシュ戦略が、パフォーマンスに影響がないか、または改善されるかを確認します。

---
**作成日**: 2025年7月26日
**作成者**: Gemini CLI Agent