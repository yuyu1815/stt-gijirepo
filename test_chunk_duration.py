import os
from pathlib import Path
from src.infrastructure.config import config_manager
from src.services.media_processor import media_processor_service

def test_chunk_duration():
    """
    チャンク分割の長さ設定のテスト
    
    設定ファイルのmedia_processor.chunk_durationの値が
    正しく使用されているかを確認します。
    """
    # 現在の設定値を取得
    current_chunk_duration = config_manager.get("media_processor.chunk_duration", 600)
    print(f"現在の設定値: {current_chunk_duration}秒")
    
    # MediaProcessorServiceのchunk_duration値を確認
    service_chunk_duration = media_processor_service.chunk_duration
    print(f"サービスの値: {service_chunk_duration}秒")
    
    # 値が一致するか確認
    if current_chunk_duration == service_chunk_duration:
        print("✓ 設定値がサービスに正しく反映されています")
    else:
        print("✗ 設定値がサービスに反映されていません")
    
    # 設定値を一時的に変更してテスト
    test_value = 2000
    print(f"\n設定値を一時的に {test_value}秒 に変更します")
    
    # 設定を変更
    config_manager.set("media_processor.chunk_duration", test_value)
    
    # サービスを再初期化（実際のアプリケーションでは再起動が必要）
    from src.services.media_processor import MediaProcessorService
    test_service = MediaProcessorService()
    
    # 新しいサービスのchunk_duration値を確認
    test_service_chunk_duration = test_service.chunk_duration
    print(f"新しいサービスの値: {test_service_chunk_duration}秒")
    
    # 値が一致するか確認
    if test_value == test_service_chunk_duration:
        print("✓ 変更した設定値が新しいサービスに正しく反映されています")
    else:
        print("✗ 変更した設定値が新しいサービスに反映されていません")
    
    # 設定を元に戻す
    config_manager.set("media_processor.chunk_duration", current_chunk_duration)
    print(f"\n設定値を元の {current_chunk_duration}秒 に戻しました")

if __name__ == "__main__":
    test_chunk_duration()