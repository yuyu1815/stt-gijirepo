# 動画コンテンツ解析プロンプト

## 概要
動画の内容を分析し、コンテンツタイプ、参加者数、音声品質、視覚的要素の重要性を評価するためのプロンプトです。文字起こし処理の最適化に必要な情報を提供します。

## パラメータ
- `{video_info}`: 動画の基本情報（解像度、長さ、フォーマットなど）
- `{analysis_purpose}`: 解析の目的（例: "transcription", "content_analysis"）
- `{custom_instructions}`: カスタム指示（オプション）

## プロンプト本文

以下の動画の内容を分析してください。

**動画情報**: {video_info}
**解析目的**: {analysis_purpose}

**コンテンツ解析指示事項**:

### 分析項目
1. **主要なコンテンツタイプ**: 会議、プレゼンテーション、講義、インタビュー、ディスカッションなど
2. **参加者数の推定**: 音声から推定される参加者数
3. **音声品質の評価**: 録音品質、明瞭度、ノイズレベル
4. **視覚的要素の重要性**: スライド、ホワイトボード、画面共有、資料の有無
5. **文字起こし処理への影響**: 処理難易度に影響する要因

### 出力形式
以下のJSON形式で回答してください：

```json
{{
    "content_type": "meeting/presentation/lecture/interview/discussion/other",
    "estimated_participants": 数値,
    "audio_quality": "excellent/good/fair/poor",
    "visual_elements": {{
        "slides_present": true/false,
        "whiteboard_usage": true/false,
        "screen_sharing": true/false,
        "documents_shown": true/false
    }},
    "visual_importance": "critical/important/moderate/minimal",
    "transcription_factors": ["要因1", "要因2", "要因3"],
    "content_notes": "詳細な分析結果"
}}
```

### 評価基準

#### コンテンツタイプの判定
- **meeting**: 複数参加者による議論や意思決定
- **presentation**: 一人または少数による発表形式
- **lecture**: 教育的な内容の一方向的な説明
- **interview**: 質問者と回答者による対話形式
- **discussion**: 自由な意見交換や議論
- **other**: 上記に当てはまらない形式

#### 音声品質の評価
- **excellent**: クリアで雑音なし、全ての発言が明瞭
- **good**: 概ねクリア、軽微な雑音あり
- **fair**: 一部不明瞭、中程度の雑音あり
- **poor**: 頻繁に不明瞭、重大な雑音あり

#### 視覚的重要度の判定
- **critical**: 映像なしでは内容理解が困難
- **important**: 映像が内容理解を大幅に助ける
- **moderate**: 映像が内容理解をある程度助ける
- **minimal**: 音声のみで十分理解可能

{custom_instructions}

## 使用例
```
入力: 技術プレゼンテーション動画（スライド使用、単一話者）
出力:
{{
    "content_type": "presentation",
    "estimated_participants": 1,
    "audio_quality": "good",
    "visual_elements": {{
        "slides_present": true,
        "whiteboard_usage": false,
        "screen_sharing": true,
        "documents_shown": false
    }},
    "visual_importance": "important",
    "transcription_factors": ["専門用語多用", "スライド参照あり"],
    "content_notes": "技術的なプレゼンテーション。スライドの内容が理解に重要。"
}}
```

## 注意事項
- 音声の内容と映像の情報を総合的に判断してください
- 推定値は合理的な根拠に基づいて算出してください
- 文字起こし処理への影響を重視して評価してください
- 不確実な場合は保守的な評価を行ってください