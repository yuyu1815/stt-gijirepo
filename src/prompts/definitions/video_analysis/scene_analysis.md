# 動画シーン解析プロンプト

## 概要
動画のシーン構成を分析し、主要なシーン変化、重要な瞬間、話者の変更タイミング、視覚的変化ポイントを特定するためのプロンプトです。文字起こし処理の最適化に必要な情報を提供します。

## パラメータ
- `{video_info}`: 動画の基本情報（解像度、長さ、フォーマットなど）
- `{analysis_purpose}`: 解析の目的（例: "transcription", "scene_analysis"）
- `{custom_instructions}`: カスタム指示（オプション）

## プロンプト本文

以下の動画のシーン構成を分析してください。

**動画情報**: {video_info}
**解析目的**: {analysis_purpose}

**シーン解析指示事項**:

### 分析項目
1. **主要なシーンの変化**: 内容や構成が大きく変わるポイント
2. **重要な瞬間の特定**: 文字起こしで特に注意すべき箇所
3. **話者の変更タイミング**: 発言者が変わるタイミングの特定
4. **視覚的な変化ポイント**: 画面構成や表示内容の変化
5. **文字起こしに影響する要素**: 処理難易度に影響する要因

### 出力形式
以下のJSON形式で回答してください：

```json
{
    "scene_changes": "シーン変化の回数（数値）",
    "major_scenes": [
        {
            "start_time": "概算時刻",
            "description": "シーンの説明",
            "importance": "high/medium/low"
        }
    ],
    "speaker_changes": "話者変更の回数（数値）",
    "visual_transitions": [
        {
            "time": "概算時刻",
            "type": "transition_type",
            "description": "変化の説明"
        }
    ],
    "transcription_factors": ["要因1", "要因2"],
    "scene_notes": "詳細な分析結果"
}
```

### 評価基準

#### シーン重要度の判定
- **high**: 内容理解に必須、文字起こしで重点的に処理すべき
- **medium**: 内容理解に有用、標準的な処理で対応
- **low**: 補足的な内容、簡略化した処理でも可

#### 視覚的変化の種類
- **slide_change**: スライドの切り替え
- **screen_share**: 画面共有の開始/終了
- **camera_switch**: カメラアングルの変更
- **content_switch**: 表示内容の大幅な変更
- **lighting_change**: 照明条件の変化
- **participant_change**: 参加者の入退場

#### 文字起こし影響要因
- **音声品質変化**: 録音条件の変化
- **話者重複**: 複数人の同時発言
- **背景音増加**: 雑音レベルの上昇
- **専門用語集中**: 特定分野の用語が集中
- **早口/遅口**: 発話速度の大幅な変化

{custom_instructions}

## 使用例
```
入力: 1時間の技術会議動画
出力:
{
    "scene_changes": 5,
    "major_scenes": [
        {
            "start_time": "00:00:00",
            "description": "開会挨拶と議題説明",
            "importance": "medium"
        },
        {
            "start_time": "00:05:30",
            "description": "技術仕様の詳細説明",
            "importance": "high"
        }
    ],
    "speaker_changes": 12,
    "visual_transitions": [
        {
            "time": "00:05:30",
            "type": "slide_change",
            "description": "技術仕様スライドに切り替え"
        }
    ],
    "transcription_factors": ["専門用語集中", "複数話者重複"],
    "scene_notes": "技術的な議論が中心。スライド参照が多い。"
}
```

## 注意事項
- 時刻は概算で構いませんが、相対的な順序は正確にしてください
- 文字起こし処理への影響を重視して評価してください
- 不確実な場合は保守的な評価を行ってください
- 重要なシーンの見落としがないよう注意してください