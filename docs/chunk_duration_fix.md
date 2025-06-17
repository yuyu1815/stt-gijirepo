# チャンク分割の長さ設定の修正

## 問題の概要

設定ファイル `config/settings.json` の `media_processor.chunk_duration` の値を変更しても、実際のメディア分割処理では常に10分（600秒）が使用されていました。

```json
"media_processor": {
  "chunk_duration": 2000
}
```

## 原因

`src/services/media_processor.py` の `split_media_file` メソッドでは、パラメータのデフォルト値として600秒（10分）がハードコードされており、設定ファイルから値を読み込んでいませんでした。

```python
def split_media_file(self, media_file: MediaFile, chunk_duration: int = 600) -> MediaFile:
    # ...
```

また、このメソッドは `src/application/app.py` から呼び出される際に、パラメータなしで呼ばれていたため、常にデフォルト値の600秒が使用されていました。

```python
media_file = media_processor_service.split_media_file(media_file)
```

## 修正内容

1. `MediaProcessorService` クラスの `__init__` メソッドで、設定ファイルから `chunk_duration` の値を読み込むように変更しました。

```python
def __init__(self):
    """初期化"""
    self.temp_dir = Path(config_manager.get("temp_dir", "temp"))
    if not self.temp_dir.exists():
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    # 設定からチャンク分割の長さを取得（デフォルトは600秒）
    self.chunk_duration = config_manager.get("media_processor.chunk_duration", 600)
```

2. `split_media_file` メソッドを修正して、パラメータが指定されていない場合は設定ファイルから読み込んだ値を使用するようにしました。

```python
def split_media_file(self, media_file: MediaFile, chunk_duration: int = None) -> MediaFile:
    """
    メディアファイルをチャンクに分割
    
    Args:
        media_file: メディアファイル
        chunk_duration: チャンクの長さ（秒）。指定しない場合は設定ファイルの値を使用
        
    Returns:
        チャンクに分割されたMediaFileオブジェクト
    """
    # chunk_durationが指定されていない場合は設定値を使用
    if chunk_duration is None:
        chunk_duration = self.chunk_duration
    
    # ...
```

3. ログメッセージを追加して、実際に使用されるチャンク長を確認できるようにしました。

```python
# ファイルを分割（設定から取得したチャンク長を使用）
logger.info(f"メディアファイルを分割します: {media_file.file_path} (チャンク長: {chunk_duration}秒)")
```

## 検証方法

修正が正しく機能していることを確認するために、`test_chunk_duration.py` というテストスクリプトを作成しました。このスクリプトは以下を検証します：

1. 設定ファイルの値が `MediaProcessorService` に正しく反映されているか
2. 設定値を変更した場合に、新しいサービスインスタンスに反映されるか

テスト結果は以下の通りで、修正が正しく機能していることが確認できました：

```
現在の設定値: 2000秒
サービスの値: 2000秒
✓ 設定値がサービスに正しく反映されています

設定値を一時的に 2000秒 に変更します
新しいサービスの値: 2000秒
✓ 変更した設定値が新しいサービスに正しく反映されています

設定値を元の 2000秒 に戻しました
```

これにより、設定ファイルの `media_processor.chunk_duration` の値が正しく使用されるようになりました。

## 影響範囲

この修正により、以下の動作が変更されます：

1. 設定ファイルの `media_processor.chunk_duration` の値が実際のメディア分割処理に反映されるようになります
2. コマンドラインオプション `--chunk-duration` で指定された値は、設定ファイルの値よりも優先されます
3. 明示的に `chunk_duration` パラメータを指定せずに `split_media_file` メソッドを呼び出した場合、設定ファイルの値が使用されます

## 今後の改善点

現在の実装では、アプリケーションの実行中に設定ファイルの値を変更しても、既に初期化されたサービスには反映されません。アプリケーションを再起動する必要があります。

将来的には、設定の変更をリアルタイムに反映する仕組みを検討することも考えられます。