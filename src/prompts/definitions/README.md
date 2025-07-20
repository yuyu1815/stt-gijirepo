# プロンプト定義ファイル

このディレクトリには、STT議事録システムで使用される各種プロンプトのMarkdown定義ファイルが格納されています。

## ディレクトリ構造

```
src/prompts/definitions/
├── README.md                    # このファイル
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

## プロンプトファイルの形式

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

## メンテナンス指針

1. **一貫性**: 全てのプロンプトファイルは上記の形式に従って記述する
2. **バージョン管理**: プロンプトの変更履歴はGitで管理する
3. **テスト**: プロンプト変更時は関連するテストケースも更新する
4. **ドキュメント**: 新しいプロンプトを追加する際は、このREADMEも更新する

## 言語サポート

現在は日本語プロンプトのみをサポートしていますが、将来的には多言語対応を予定しています。