"""
STT議事録システム - メインワークフローテスト

メインワークフローの統合テスト、エラーハンドリング、状態遷移のテスト
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# パッケージパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from workflows.stt_workflow import (
    create_stt_workflow,
    execute_stt_workflow,
    execute_batch_processing,
    get_workflow_state
)
from workflows.state import STTState, STTConfig


class TestSTTWorkflow:
    """STTワークフローのテストクラス"""
    
    @pytest.mark.integration
    def test_create_stt_workflow(self):
        """ワークフロー作成のテスト"""
        workflow = create_stt_workflow()
        
        # ワークフローが正常に作成されることを確認
        assert workflow is not None
        assert hasattr(workflow, 'invoke')
        assert hasattr(workflow, 'get_graph')
    
    @pytest.mark.integration
    def test_execute_stt_workflow_audio_file(self, sample_audio_file, test_config, mock_gemini_service, mock_audio_processor, mock_file_utils):
        """音声ファイルのワークフロー実行テスト"""
        with patch('workflows.nodes.transcription.GeminiService', return_value=mock_gemini_service), \
             patch('workflows.nodes.file_analysis.AudioProcessor', return_value=mock_audio_processor), \
             patch('workflows.nodes.file_analysis.FileUtils', return_value=mock_file_utils):
            
            result = execute_stt_workflow(
                file_path=str(sample_audio_file),
                config=test_config,
                upload_to_notion=False
            )
            
            # 基本的な結果の確認
            assert isinstance(result, dict)
            assert 'final_status' in result
            assert 'session_id' in result
            assert 'processing_log' in result
            assert len(result['errors']) == 0
    
    @pytest.mark.integration
    def test_execute_stt_workflow_video_file(self, sample_video_file, test_config, mock_gemini_service, mock_video_processor, mock_file_utils):
        """動画ファイルのワークフロー実行テスト"""
        with patch('workflows.nodes.video_processing.VideoProcessor', return_value=mock_video_processor), \
             patch('workflows.nodes.transcription.GeminiService', return_value=mock_gemini_service), \
             patch('workflows.nodes.file_analysis.FileUtils', return_value=mock_file_utils):
            
            result = execute_stt_workflow(
                file_path=str(sample_video_file),
                config=test_config,
                upload_to_notion=False
            )
            
            # 動画処理の結果確認
            assert isinstance(result, dict)
            assert result.get('file_type') == 'video'
            assert 'is_video_dark' in result
    
    @pytest.mark.integration
    def test_execute_stt_workflow_with_notion_upload(self, sample_audio_file, test_config, mock_gemini_service, mock_notion_client, mock_audio_processor, mock_file_utils):
        """Notionアップロード付きワークフロー実行テスト"""
        with patch('workflows.nodes.transcription.GeminiService', return_value=mock_gemini_service), \
             patch('workflows.nodes.notion_upload.NotionClient', return_value=mock_notion_client), \
             patch('workflows.nodes.file_analysis.AudioProcessor', return_value=mock_audio_processor), \
             patch('workflows.nodes.file_analysis.FileUtils', return_value=mock_file_utils):
            
            result = execute_stt_workflow(
                file_path=str(sample_audio_file),
                config=test_config,
                upload_to_notion=True
            )
            
            # Notionアップロードの結果確認
            assert result['upload_to_notion'] is True
            assert 'notion_page_id' in result
            mock_notion_client.create_page.assert_called_once()
    
    @pytest.mark.integration
    def test_execute_batch_processing(self, sample_audio_file, sample_video_file, test_config, mock_gemini_service, mock_audio_processor, mock_video_processor, mock_file_utils):
        """バッチ処理のテスト"""
        file_paths = [str(sample_audio_file), str(sample_video_file)]
        
        with patch('workflows.nodes.transcription.GeminiService', return_value=mock_gemini_service), \
             patch('workflows.nodes.file_analysis.AudioProcessor', return_value=mock_audio_processor), \
             patch('workflows.nodes.video_processing.VideoProcessor', return_value=mock_video_processor), \
             patch('workflows.nodes.file_analysis.FileUtils', return_value=mock_file_utils):
            
            results = execute_batch_processing(
                file_paths=file_paths,
                config=test_config,
                max_concurrent=2
            )
            
            # バッチ処理結果の確認
            assert isinstance(results, list)
            assert len(results) == 2
            
            for result in results:
                assert isinstance(result, dict)
                assert 'final_status' in result
                assert 'session_id' in result
    
    @pytest.mark.unit
    def test_workflow_state_transitions(self, test_state):
        """ワークフロー状態遷移のテスト"""
        # 初期状態の確認
        assert test_state['processing_stage'] == 'initialized'
        assert test_state['final_status'] == 'initialized'
        assert len(test_state['errors']) == 0
        
        # 状態更新のシミュレーション
        test_state['processing_stage'] = 'file_analysis'
        test_state['file_type'] = 'audio'
        test_state['processing_log'].append('ファイル解析完了')
        
        assert test_state['processing_stage'] == 'file_analysis'
        assert test_state['file_type'] == 'audio'
        assert 'ファイル解析完了' in test_state['processing_log']
    
    @pytest.mark.unit
    def test_error_handling_invalid_file(self, test_config):
        """無効ファイルのエラーハンドリングテスト"""
        invalid_file_path = "/nonexistent/file.wav"
        
        result = execute_stt_workflow(
            file_path=invalid_file_path,
            config=test_config,
            upload_to_notion=False
        )
        
        # エラーが適切に処理されることを確認
        assert result['final_status'] == 'error'
        assert len(result['errors']) > 0
        assert any('ファイルが見つかりません' in error or 'not found' in error.lower() 
                  for error in result['errors'])
    
    @pytest.mark.unit
    def test_error_handling_api_failure(self, sample_audio_file, test_config, mock_audio_processor, mock_file_utils):
        """API失敗時のエラーハンドリングテスト"""
        # Gemini APIの失敗をシミュレート
        mock_gemini_service = Mock()
        mock_gemini_service.transcribe_audio.side_effect = Exception("API Error")
        
        with patch('workflows.nodes.transcription.GeminiService', return_value=mock_gemini_service), \
             patch('workflows.nodes.file_analysis.AudioProcessor', return_value=mock_audio_processor), \
             patch('workflows.nodes.file_analysis.FileUtils', return_value=mock_file_utils):
            
            result = execute_stt_workflow(
                file_path=str(sample_audio_file),
                config=test_config,
                upload_to_notion=False
            )
            
            # API エラーが適切に処理されることを確認
            assert result['final_status'] == 'error'
            assert len(result['errors']) > 0
            assert any('API Error' in error for error in result['errors'])
    
    @pytest.mark.unit
    def test_workflow_routing_audio_file(self, test_state):
        """音声ファイルのルーティングテスト"""
        from workflows.stt_workflow import should_process_video, should_split_audio, should_upload_to_notion
        
        # 音声ファイルの状態設定
        test_state['file_type'] = 'audio'
        test_state['audio_duration'] = 300.0  # 5分
        test_state['upload_to_notion'] = False
        
        # ルーティング判定のテスト
        assert should_process_video(test_state) == "audio_splitting"
        assert should_split_audio(test_state) == "transcription"  # 5分なので分割不要
        assert should_upload_to_notion(test_state) == "END"
    
    @pytest.mark.unit
    def test_workflow_routing_video_file(self, test_state):
        """動画ファイルのルーティングテスト"""
        from workflows.stt_workflow import should_process_video, should_split_audio
        
        # 動画ファイルの状態設定
        test_state['file_type'] = 'video'
        test_state['is_video_dark'] = True
        test_state['audio_duration'] = 1800.0  # 30分
        
        # ルーティング判定のテスト
        assert should_process_video(test_state) == "video_processing"
        assert should_split_audio(test_state) == "audio_splitting"  # 30分なので分割必要
    
    @pytest.mark.unit
    def test_workflow_routing_long_audio(self, test_state):
        """長時間音声のルーティングテスト"""
        from workflows.stt_workflow import should_split_audio
        
        # 長時間音声の状態設定
        test_state['file_type'] = 'audio'
        test_state['audio_duration'] = 3000.0  # 50分
        
        # 分割が必要と判定されることを確認
        assert should_split_audio(test_state) == "audio_splitting"
    
    @pytest.mark.integration
    def test_workflow_performance_monitoring(self, sample_audio_file, test_config, performance_monitor, mock_gemini_service, mock_audio_processor, mock_file_utils):
        """ワークフローのパフォーマンス監視テスト"""
        with patch('workflows.nodes.transcription.GeminiService', return_value=mock_gemini_service), \
             patch('workflows.nodes.file_analysis.AudioProcessor', return_value=mock_audio_processor), \
             patch('workflows.nodes.file_analysis.FileUtils', return_value=mock_file_utils):
            
            # パフォーマンス監視を開始
            operation_id = performance_monitor.start_operation("stt_workflow_test")
            
            result = execute_stt_workflow(
                file_path=str(sample_audio_file),
                config=test_config,
                upload_to_notion=False
            )
            
            # パフォーマンス監視を終了
            performance_monitor.end_operation(operation_id, success=True)
            
            # パフォーマンスメトリクスの確認
            stats = performance_monitor.get_operation_summary("stt_workflow_test")
            assert stats['total_executions'] == 1
            assert stats['success_rate'] == 100.0
            assert stats['average_duration'] > 0
    
    @pytest.mark.slow
    def test_workflow_with_real_processing(self, sample_audio_file, test_config):
        """実際の処理を含むワークフローテスト（スロー）"""
        # 注意: このテストは実際のAPI呼び出しを行うため、
        # 適切なAPI キーが設定されている場合のみ実行される
        
        if not test_config.get('gemini_api_key') or test_config['gemini_api_key'] == 'test_api_key':
            pytest.skip("実際のAPI キーが設定されていません")
        
        result = execute_stt_workflow(
            file_path=str(sample_audio_file),
            config=test_config,
            upload_to_notion=False
        )
        
        # 実際の処理結果の確認
        assert result['final_status'] in ['success', 'partial']
        if result['final_status'] == 'success':
            assert result.get('transcription') is not None
            assert result.get('minutes') is not None
    
    @pytest.mark.unit
    def test_get_workflow_state(self):
        """ワークフロー状態取得のテスト"""
        state_info = get_workflow_state()
        
        # 状態情報の基本構造確認
        assert isinstance(state_info, dict)
        assert 'workflow_version' in state_info
        assert 'supported_formats' in state_info
        assert 'node_count' in state_info
        assert 'routing_functions' in state_info
    
    @pytest.mark.unit
    def test_workflow_config_validation(self, sample_audio_file):
        """ワークフロー設定検証のテスト"""
        # 無効な設定でのテスト
        invalid_config = STTConfig(
            gemini_api_key="",  # 空のAPIキー
            gemini_model="invalid_model",
            notion_token=None,
            max_audio_duration=-1,  # 無効な値
            chunk_size=0,  # 無効な値
            max_retries=-1,  # 無効な値
            retry_delay=-1.0,  # 無効な値
            min_confidence_threshold=2.0,  # 範囲外
            enable_quality_check=True,
            enable_hallucination_check=True,
            output_format="invalid_format",
            include_timestamps=True,
            include_speaker_labels=False,
            notion_database_id=None,
            notion_template_id=None
        )
        
        result = execute_stt_workflow(
            file_path=str(sample_audio_file),
            config=invalid_config,
            upload_to_notion=False
        )
        
        # 設定エラーが適切に処理されることを確認
        assert result['final_status'] == 'error'
        assert len(result['errors']) > 0


class TestWorkflowEdgeCases:
    """ワークフローのエッジケーステスト"""
    
    @pytest.mark.unit
    def test_empty_file_handling(self, temp_dir, test_config):
        """空ファイルの処理テスト"""
        empty_file = temp_dir / "empty.wav"
        empty_file.write_bytes(b"")
        
        result = execute_stt_workflow(
            file_path=str(empty_file),
            config=test_config,
            upload_to_notion=False
        )
        
        assert result['final_status'] == 'error'
        assert any('empty' in error.lower() or '空' in error for error in result['errors'])
    
    @pytest.mark.unit
    def test_very_large_file_handling(self, temp_dir, test_config):
        """非常に大きなファイルの処理テスト"""
        large_file = temp_dir / "large.wav"
        # 3GBのダミーファイル（実際には作成しない）
        
        with patch('os.path.getsize', return_value=3 * 1024 * 1024 * 1024):
            result = execute_stt_workflow(
                file_path=str(large_file),
                config=test_config,
                upload_to_notion=False
            )
            
            assert result['final_status'] == 'error'
            assert any('size' in error.lower() or 'サイズ' in error for error in result['errors'])
    
    @pytest.mark.unit
    def test_unsupported_format_handling(self, temp_dir, test_config):
        """サポートされていない形式の処理テスト"""
        unsupported_file = temp_dir / "test.xyz"
        unsupported_file.write_bytes(b"dummy data")
        
        result = execute_stt_workflow(
            file_path=str(unsupported_file),
            config=test_config,
            upload_to_notion=False
        )
        
        assert result['final_status'] == 'error'
        assert any('format' in error.lower() or 'supported' in error.lower() or 
                  '形式' in error or 'サポート' in error for error in result['errors'])
    
    @pytest.mark.unit
    def test_concurrent_workflow_execution(self, sample_audio_file, test_config, mock_gemini_service, mock_audio_processor, mock_file_utils):
        """並行ワークフロー実行のテスト"""
        import threading
        import time
        
        results = []
        errors = []
        
        def run_workflow():
            try:
                with patch('workflows.nodes.transcription.GeminiService', return_value=mock_gemini_service), \
                     patch('workflows.nodes.file_analysis.AudioProcessor', return_value=mock_audio_processor), \
                     patch('workflows.nodes.file_analysis.FileUtils', return_value=mock_file_utils):
                    
                    result = execute_stt_workflow(
                        file_path=str(sample_audio_file),
                        config=test_config,
                        upload_to_notion=False
                    )
                    results.append(result)
            except Exception as e:
                errors.append(str(e))
        
        # 3つの並行スレッドでワークフローを実行
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=run_workflow)
            threads.append(thread)
            thread.start()
        
        # すべてのスレッドの完了を待機
        for thread in threads:
            thread.join(timeout=10)
        
        # 結果の確認
        assert len(errors) == 0, f"並行実行でエラーが発生: {errors}"
        assert len(results) == 3
        
        for result in results:
            assert isinstance(result, dict)
            assert 'session_id' in result
            # 各実行で異なるセッションIDが生成されることを確認
            session_ids = [r['session_id'] for r in results]
            assert len(set(session_ids)) == 3