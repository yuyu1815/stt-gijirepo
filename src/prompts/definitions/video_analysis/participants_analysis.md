# 動画参加者解析プロンプト

## 概要
動画の参加者を分析し、参加者数の推定、主要話者の特定、話者の役割推定、発言頻度の分析、音声品質の個別評価を行うためのプロンプトです。文字起こし処理の最適化に必要な情報を提供します。

## パラメータ
- `{video_info}`: 動画の基本情報（解像度、長さ、フォーマットなど）
- `{analysis_purpose}`: 解析の目的（例: "transcription", "participants_analysis"）
- `{custom_instructions}`: カスタム指示（オプション）

## プロンプト本文

以下の動画の参加者を分析してください。

**動画情報**: {video_info}
**解析目的**: {analysis_purpose}

**参加者解析指示事項**:

### 分析項目
1. **参加者数の推定**: 音声から推定される総参加者数と映像に映る参加者数
2. **主要話者の特定**: 発言頻度や重要度の高い話者の特定
3. **話者の役割推定**: 司会者、発表者、質問者などの役割推定
4. **発言頻度の分析**: 各話者の発言頻度と時間配分
5. **音声品質の個別評価**: 話者ごとの音声品質評価

### 出力形式
以下のJSON形式で回答してください：

```json
{
    "total_participants": "総参加者数（数値）",
    "visible_participants": "映像に映る参加者数（数値）",
    "main_speakers": [
        {
            "speaker_id": "話者ID",
            "estimated_role": "推定役割",
            "speaking_frequency": "high/medium/low",
            "audio_quality": "excellent/good/fair/poor"
        }
    ],
    "group_dynamics": "formal/informal/mixed",
    "interaction_pattern": "presentation/discussion/interview/meeting",
    "transcription_challenges": ["課題1", "課題2"],
    "participant_notes": "詳細な分析結果"
}
```

### 評価基準

#### 話者役割の分類
- **presenter**: 主要な発表者、長時間の発言
- **moderator**: 司会者、進行役
- **participant**: 一般参加者、質問や意見
- **interviewer**: インタビュアー、質問主体
- **interviewee**: インタビュー対象者、回答主体
- **expert**: 専門家、技術的な説明
- **observer**: 観察者、発言少ない

#### 発言頻度の評価
- **high**: 全体の30%以上の発言時間
- **medium**: 全体の10-30%の発言時間
- **low**: 全体の10%未満の発言時間

#### 音声品質の個別評価
- **excellent**: クリアで聞き取りやすい、雑音なし
- **good**: 概ね聞き取りやすい、軽微な問題
- **fair**: 一部聞き取りにくい、中程度の問題
- **poor**: 頻繁に聞き取りにくい、重大な問題

#### グループダイナミクス
- **formal**: 正式な会議、明確な役割分担
- **informal**: 非公式な議論、自由な発言
- **mixed**: 正式と非公式が混在

#### インタラクションパターン
- **presentation**: 一方向的な発表形式
- **discussion**: 双方向的な議論形式
- **interview**: 質問・回答形式
- **meeting**: 会議形式、複数の議題

#### 文字起こし課題
- **話者識別困難**: 声質が似ている、区別が困難
- **同時発言**: 複数人の同時発言が頻発
- **音声品質差**: 話者間の音声品質に大きな差
- **専門用語**: 特定話者の専門用語使用
- **発話速度差**: 話者間の発話速度に大きな差

{custom_instructions}

## 使用例
```
入力: 技術チームの会議動画（4名参加）
出力:
{
    "total_participants": 4,
    "visible_participants": 3,
    "main_speakers": [
        {
            "speaker_id": "Speaker_A",
            "estimated_role": "moderator",
            "speaking_frequency": "high",
            "audio_quality": "excellent"
        },
        {
            "speaker_id": "Speaker_B",
            "estimated_role": "expert",
            "speaking_frequency": "medium",
            "audio_quality": "good"
        }
    ],
    "group_dynamics": "formal",
    "interaction_pattern": "meeting",
    "transcription_challenges": ["専門用語", "同時発言"],
    "participant_notes": "技術的な議論が中心。主要話者2名が議論をリード。"
}
```

## 注意事項
- 音声の特徴から話者を区別してください
- 推定値は合理的な根拠に基づいて算出してください
- 文字起こし処理への影響を重視して評価してください
- 話者のプライバシーに配慮し、個人を特定する情報は含めないでください
- 不確実な場合は保守的な評価を行ってください