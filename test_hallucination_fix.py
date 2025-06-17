"""
MediaChunkハッシュ可能性修正のテスト

このスクリプトは、MediaChunkクラスのハッシュ可能性の修正をテストします。
"""
from pathlib import Path
from src.domain.media import MediaChunk, MediaFile, MediaType
from src.domain.transcription import TranscriptionResult, TranscriptionSegment, TranscriptionStatus
from src.services.hallucination import hallucination_service
from src.infrastructure.logger import logger

def test_media_chunk_hashability():
    """
    MediaChunkのハッシュ可能性をテストする関数
    
    MediaChunkオブジェクトをディクショナリのキーとして使用できるかテストします。
    """
    # テスト用のMediaChunkオブジェクトを作成
    chunk1 = MediaChunk(
        start_time=0.0,
        end_time=600.0,
        file_path=Path("test_chunk_1.mp3"),
        index=0
    )
    
    chunk2 = MediaChunk(
        start_time=600.0,
        end_time=1200.0,
        file_path=Path("test_chunk_2.mp3"),
        index=1
    )
    
    # ディクショナリのキーとして使用できるかテスト
    chunk_dict = {
        chunk1: "チャンク1の値",
        chunk2: "チャンク2の値"
    }
    
    # 正しく取得できるかテスト
    try:
        value1 = chunk_dict[chunk1]
        value2 = chunk_dict[chunk2]
        print(f"✓ MediaChunkをディクショナリのキーとして使用できます")
        print(f"  チャンク1の値: {value1}")
        print(f"  チャンク2の値: {value2}")
    except Exception as e:
        print(f"✗ MediaChunkをディクショナリのキーとして使用できません: {e}")
        return False
    
    return True

def test_hallucination_check_with_chunks():
    """
    チャンクを持つメディアファイルのハルシネーションチェックをテストする関数
    
    MediaChunkオブジェクトがハッシュ可能であることを確認するため、
    ハルシネーションチェック処理を実行します。
    """
    print("\nチャンクを持つメディアファイルのハルシネーションチェックをテストします...")
    
    # テスト用のMediaFileオブジェクトを作成
    media_file = MediaFile(
        file_path=Path("test_media.mp4"),
        media_type=MediaType.VIDEO,
        duration=3000.0  # 50分の長いメディア
    )
    
    # チャンクを追加
    chunk1 = MediaChunk(
        start_time=0.0,
        end_time=600.0,
        file_path=Path("test_chunk_1.mp3"),
        index=0
    )
    
    chunk2 = MediaChunk(
        start_time=600.0,
        end_time=1200.0,
        file_path=Path("test_chunk_2.mp3"),
        index=1
    )
    
    media_file.chunks = [chunk1, chunk2]
    
    # テスト用のTranscriptionResultオブジェクトを作成
    transcription_result = TranscriptionResult(
        source_file=Path("test_media.mp4"),
        status=TranscriptionStatus.COMPLETED
    )
    
    # セグメントを追加
    segment1 = TranscriptionSegment(
        text="これはテストセグメント1です。",
        start_time=10.0,
        end_time=15.0
    )
    
    segment2 = TranscriptionSegment(
        text="これはテストセグメント2です。",
        start_time=700.0,
        end_time=705.0
    )
    
    transcription_result.segments = [segment1, segment2]
    
    # ハルシネーションチェックを実行
    try:
        logger.info("ハルシネーションチェックを実行します...")
        hallucination_service._group_segments_by_chunks(transcription_result.segments, media_file.chunks)
        print("✓ _group_segments_by_chunksメソッドが正常に実行されました")
        return True
    except Exception as e:
        print(f"✗ ハルシネーションチェックに失敗しました: {e}")
        return False

if __name__ == "__main__":
    print("MediaChunkハッシュ可能性修正のテストを開始します...")
    
    # 基本的なハッシュ可能性テスト
    basic_test_result = test_media_chunk_hashability()
    
    # ハルシネーションチェックテスト
    hallucination_test_result = test_hallucination_check_with_chunks()
    
    # 結果を表示
    if basic_test_result and hallucination_test_result:
        print("\n✓ すべてのテストが成功しました！MediaChunkは正しくハッシュ可能になりました。")
    else:
        print("\n✗ テストに失敗しました。修正が必要です。")