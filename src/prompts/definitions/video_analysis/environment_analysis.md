# 動画環境解析プロンプト

## 概要
動画の録画環境を分析し、録画環境の種類、音響環境の評価、背景ノイズの分析、照明環境の評価、技術的品質の評価を行うためのプロンプトです。文字起こし処理の最適化に必要な情報を提供します。

## パラメータ
- `{video_info}`: 動画の基本情報（解像度、長さ、フォーマットなど）
- `{analysis_purpose}`: 解析の目的（例: "transcription", "environment_analysis"）
- `{custom_instructions}`: カスタム指示（オプション）

## プロンプト本文

以下の動画の環境を分析してください。

**動画情報**: {video_info}
**解析目的**: {analysis_purpose}

**環境解析指示事項**:

### 分析項目
1. **録画環境の種類**: オフィス、自宅、スタジオ、屋外、車内など
2. **音響環境の評価**: エコー、背景ノイズ、音響特性の評価
3. **背景ノイズの分析**: ノイズの種類と影響度の分析
4. **照明環境の評価**: 照明の種類、品質、安定性の評価
5. **技術的品質の評価**: 解像度、フレームレート、圧縮品質の評価

### 出力形式
以下のJSON形式で回答してください：

```json
{
    "recording_environment": "office/home/studio/outdoor/vehicle/other",
    "acoustic_environment": {
        "echo_level": "none/minimal/moderate/significant",
        "background_noise": "none/minimal/moderate/significant",
        "noise_types": ["ノイズタイプ1", "ノイズタイプ2"]
    },
    "lighting_environment": {
        "lighting_type": "natural/artificial/mixed",
        "lighting_quality": "excellent/good/fair/poor",
        "consistency": "stable/variable"
    },
    "technical_quality": {
        "video_resolution": "推定解像度",
        "frame_rate": "推定フレームレート",
        "compression_artifacts": "none/minimal/moderate/significant"
    },
    "transcription_impact": {
        "audio_clarity": "excellent/good/fair/poor",
        "processing_difficulty": "easy/moderate/difficult/very_difficult"
    },
    "environment_notes": "詳細な分析結果"
}
```

### 評価基準

#### 録画環境の分類
- **office**: オフィス環境、会議室など
- **home**: 自宅環境、個人の部屋など
- **studio**: 専用スタジオ、録音・録画専用環境
- **outdoor**: 屋外環境、公園、街中など
- **vehicle**: 車内、電車内など移動中
- **other**: 上記に当てはまらない特殊な環境

#### 音響環境の評価
- **echo_level**: 
  - **none**: エコーなし
  - **minimal**: わずかなエコー
  - **moderate**: 中程度のエコー
  - **significant**: 強いエコー、音響処理に影響
- **background_noise**:
  - **none**: 背景ノイズなし
  - **minimal**: わずかなノイズ
  - **moderate**: 中程度のノイズ
  - **significant**: 強いノイズ、音声認識に影響

#### ノイズの種類
- **air_conditioning**: エアコンの音
- **traffic**: 交通騒音
- **keyboard**: キーボードタイピング音
- **paper_rustling**: 紙をめくる音
- **phone_ringing**: 電話の着信音
- **construction**: 工事音
- **conversation**: 他の会話
- **electronic**: 電子機器のノイズ

#### 照明環境の評価
- **lighting_type**:
  - **natural**: 自然光（窓からの光）
  - **artificial**: 人工照明（蛍光灯、LEDなど）
  - **mixed**: 自然光と人工照明の組み合わせ
- **lighting_quality**:
  - **excellent**: 十分で均一な照明
  - **good**: 良好な照明、軽微な問題
  - **fair**: 普通の照明、一部暗い
  - **poor**: 不十分な照明、暗い部分が多い

#### 技術的品質の評価
- **compression_artifacts**:
  - **none**: 圧縮による劣化なし
  - **minimal**: わずかな劣化
  - **moderate**: 中程度の劣化
  - **significant**: 重大な劣化、品質に影響

#### 文字起こし処理への影響
- **audio_clarity**:
  - **excellent**: 非常にクリア、処理に最適
  - **good**: クリア、標準的な処理で対応可能
  - **fair**: やや不明瞭、注意深い処理が必要
  - **poor**: 不明瞭、高度な処理が必要
- **processing_difficulty**:
  - **easy**: 標準的な処理で高品質な結果
  - **moderate**: 一部調整が必要
  - **difficult**: 大幅な調整や前処理が必要
  - **very_difficult**: 特別な処理技術が必要

{custom_instructions}

## 使用例
```
入力: 自宅からのオンライン会議動画
出力:
{
    "recording_environment": "home",
    "acoustic_environment": {
        "echo_level": "minimal",
        "background_noise": "moderate",
        "noise_types": ["air_conditioning", "keyboard"]
    },
    "lighting_environment": {
        "lighting_type": "mixed",
        "lighting_quality": "fair",
        "consistency": "variable"
    },
    "technical_quality": {
        "video_resolution": "1080p",
        "frame_rate": "30fps",
        "compression_artifacts": "minimal"
    },
    "transcription_impact": {
        "audio_clarity": "good",
        "processing_difficulty": "moderate"
    },
    "environment_notes": "自宅環境での録画。背景ノイズはあるが音声は概ね明瞭。"
}
```

## 注意事項
- 音声と映像の両方から環境を総合的に判断してください
- 文字起こし処理への影響を重視して評価してください
- 技術的な詳細は推定で構いませんが、合理的な根拠に基づいてください
- 環境の特徴が文字起こし品質に与える影響を明確にしてください
- 不確実な場合は保守的な評価を行ってください