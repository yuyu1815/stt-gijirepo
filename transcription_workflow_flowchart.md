# 文字お越しのフローチャート

このドキュメントは、現在の文字お越し（文字起こし）システムのワークフローを図解したものです。

## 全体的なフロー

```mermaid
flowchart TD
    Start([開始]) --> InputFile[メディアファイル入力]
    InputFile --> ProcessMedia[メディアファイル処理]
    ProcessMedia --> IsVideo{動画ファイル？}
    
    IsVideo -- はい --> IsDarkVideo{暗い動画？}
    IsDarkVideo -- はい --> ExtractAudio[音声抽出]
    IsDarkVideo -- いいえ --> IsLongMedia{長時間メディア？}
    IsVideo -- いいえ --> IsLongMedia
    
    ExtractAudio --> IsLongMedia
    
    IsLongMedia -- はい --> SplitMedia[メディアファイル分割]
    IsLongMedia -- いいえ --> TranscribeSingle[単一ファイル文字起こし]
    
    SplitMedia --> HasChunks{チャンクあり？}
    HasChunks -- はい --> TranscribeChunks[チャンク文字起こし]
    HasChunks -- いいえ --> TranscribeSingle
    
    TranscribeChunks --> CombineTranscriptions[文字起こし結果結合]
    CombineTranscriptions --> HallucinationCheck[ハルシネーションチェック]
    TranscribeSingle --> HallucinationCheck
    
    HallucinationCheck --> GenerateMinutes[議事録生成]
    GenerateMinutes --> End([終了])
```

## 詳細なフロー

### 1. メディアファイル処理

```mermaid
flowchart TD
    Start([開始]) --> InputFile[メディアファイル入力]
    InputFile --> ProcessMedia[メディアファイル処理]
    ProcessMedia --> DetermineType[メディアタイプ判定]
    DetermineType --> GetDuration[長さ取得]
    GetDuration --> IsVideo{動画ファイル？}
    
    IsVideo -- はい --> CheckQuality[動画品質判定]
    CheckQuality --> IsDarkVideo{暗い動画？}
    IsDarkVideo -- はい --> ExtractAudio[音声抽出]
    IsDarkVideo -- いいえ --> IsLongMedia{長時間メディア？}
    
    IsVideo -- いいえ --> IsLongMedia
    ExtractAudio --> IsLongMedia
    
    IsLongMedia -- いいえ --> End([次のステップへ])
    IsLongMedia -- はい --> SplitMedia[メディアファイル分割]
    SplitMedia --> End
```

### 2. メディアファイル分割

```mermaid
flowchart TD
    Start([開始]) --> IsLongMedia{長時間メディア？}
    IsLongMedia -- いいえ --> End([分割なし])
    IsLongMedia -- はい --> CreateOutputDir[出力ディレクトリ作成]
    CreateOutputDir --> SplitFile[ファイル分割]
    SplitFile --> CreateChunks[チャンク情報作成]
    CreateChunks --> UpdateMediaFile[MediaFileオブジェクト更新]
    UpdateMediaFile --> End2([分割完了])
```

### 3. 文字起こしプロセス

```mermaid
flowchart TD
    Start([開始]) --> HasChunks{チャンクあり？}
    
    HasChunks -- いいえ --> TranscribeSingle[単一ファイル文字起こし]
    HasChunks -- はい --> InitChunkResults[チャンク結果初期化]
    
    InitChunkResults --> ProcessEachChunk[各チャンク処理]
    ProcessEachChunk --> TranscribeChunk[チャンク文字起こし]
    TranscribeChunk --> AdjustTimestamps[タイムスタンプ調整]
    AdjustTimestamps --> CollectResults[結果収集]
    CollectResults --> AllChunksProcessed{全チャンク処理完了？}
    
    AllChunksProcessed -- いいえ --> ProcessEachChunk
    AllChunksProcessed -- はい --> CombineResults[結果結合]
    
    TranscribeSingle --> End([文字起こし完了])
    CombineResults --> End
```

### 4. 単一ファイル文字起こし

```mermaid
flowchart TD
    Start([開始]) --> LoadPrompt[プロンプト読み込み]
    LoadPrompt --> TranscribeWithGemini[Gemini APIで文字起こし]
    TranscribeWithGemini --> ParseTranscription[文字起こし結果パース]
    ParseTranscription --> SaveResult[結果保存]
    SaveResult --> End([文字起こし完了])
```

### 5. 文字起こし結果結合

```mermaid
flowchart TD
    Start([開始]) --> CollectSegments[全セグメント収集]
    CollectSegments --> SortByTimestamp[タイムスタンプでソート]
    SortByTimestamp --> CreateCombinedResult[結合結果作成]
    CreateCombinedResult --> SaveCombinedResult[結合結果保存]
    SaveCombinedResult --> End([結合完了])
```

### 6. ハルシネーションチェック

```mermaid
flowchart TD
    Start([開始]) --> IsLongMedia{長時間メディア？}
    
    IsLongMedia -- はい --> GroupSegments[セグメントをチャンクごとにグループ化]
    GroupSegments --> CheckEachChunk[各チャンクをチェック]
    CheckEachChunk --> CollectResults[結果収集]
    
    IsLongMedia -- いいえ --> CheckSingleFile[単一ファイルチェック]
    
    CheckSingleFile --> End([チェック完了])
    CollectResults --> End
```

### 7. 議事録生成

```mermaid
flowchart TD
    Start([開始]) --> InitializeMinutes[議事録基本情報設定]
    InitializeMinutes --> LoadPrompt[プロンプト読み込み]
    LoadPrompt --> GenerateWithGemini[Gemini APIで議事録内容生成]
    GenerateWithGemini --> ParseContent[内容をパース]
    ParseContent --> AddImages[画像追加]
    AddImages --> SaveMinutes[議事録保存]
    SaveMinutes --> End([議事録生成完了])
```

## 全体的なワークフロー

1. **メディアファイル処理**:
   - メディアファイルを入力として受け取る
   - メディアタイプ（音声/動画）を判定
   - ファイルの長さを取得
   - 動画の場合は品質を判定

2. **前処理**:
   - 暗い動画の場合は音声を抽出
   - 長時間メディア（40分以上）の場合はチャンクに分割

3. **文字起こし**:
   - チャンクがある場合は各チャンクを個別に文字起こし
   - チャンクがない場合は単一ファイルとして文字起こし
   - チャンクの文字起こし結果を結合（元のメディアファイルのパスを使用）

4. **ハルシネーションチェック**:
   - 文字起こし結果のハルシネーション（幻覚）をチェック
   - 重大度に応じて結果を分類

5. **議事録生成**:
   - 文字起こし結果から議事録の基本情報を設定
   - Gemini APIを使用して議事録内容を生成
   - 画像がある場合は追加
   - 議事録を保存

6. **出力**:
   - 生成された議事録をMarkdown形式で出力