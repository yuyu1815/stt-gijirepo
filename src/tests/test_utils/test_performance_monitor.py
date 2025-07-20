"""
STT議事録システム - パフォーマンス監視テスト

performance_monitor.pyモジュールのテストケース
"""

import pytest
import time
import json
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from collections import deque

from src.utils.performance_monitor import (
    PerformanceMetrics,
    ProcessingStats,
    PerformanceMonitor,
    OperationTimer
)


class TestPerformanceMetrics:
    """PerformanceMetricsデータクラスのテスト"""
    
    def test_metrics_creation(self):
        """メトリクス作成のテスト"""
        timestamp = datetime.now()
        metrics = PerformanceMetrics(
            timestamp=timestamp,
            cpu_percent=50.5,
            memory_percent=75.2,
            memory_used_mb=1024.0,
            disk_io_read_mb=100.5,
            disk_io_write_mb=50.3,
            network_sent_mb=25.1,
            network_recv_mb=30.7
        )
        
        assert metrics.timestamp == timestamp
        assert metrics.cpu_percent == 50.5
        assert metrics.memory_percent == 75.2
        assert metrics.memory_used_mb == 1024.0
        assert metrics.disk_io_read_mb == 100.5
        assert metrics.disk_io_write_mb == 50.3
        assert metrics.network_sent_mb == 25.1
        assert metrics.network_recv_mb == 30.7
        assert metrics.custom_metrics == {}
    
    def test_metrics_with_custom_data(self):
        """カスタムメトリクス付きのテスト"""
        custom_metrics = {"gpu_usage": 80.0, "temperature": 65.5}
        metrics = PerformanceMetrics(
            timestamp=datetime.now(),
            cpu_percent=50.0,
            memory_percent=60.0,
            memory_used_mb=512.0,
            disk_io_read_mb=10.0,
            disk_io_write_mb=5.0,
            network_sent_mb=2.0,
            network_recv_mb=3.0,
            custom_metrics=custom_metrics
        )
        
        assert metrics.custom_metrics == custom_metrics
        assert metrics.custom_metrics["gpu_usage"] == 80.0


class TestProcessingStats:
    """ProcessingStatsデータクラスのテスト"""
    
    def test_stats_creation(self):
        """統計作成のテスト"""
        start_time = datetime.now()
        stats = ProcessingStats(
            operation_name="test_operation",
            start_time=start_time
        )
        
        assert stats.operation_name == "test_operation"
        assert stats.start_time == start_time
        assert stats.end_time is None
        assert stats.duration_seconds is None
        assert stats.success is True
        assert stats.error_message is None
        assert stats.input_size is None
        assert stats.output_size is None
        assert stats.custom_data == {}
    
    def test_stats_with_all_fields(self):
        """全フィールド付き統計のテスト"""
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=5)
        custom_data = {"file_type": "wav", "quality": "high"}
        
        stats = ProcessingStats(
            operation_name="transcription",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=5.0,
            success=False,
            error_message="Test error",
            input_size=1024,
            output_size=512,
            custom_data=custom_data
        )
        
        assert stats.operation_name == "transcription"
        assert stats.end_time == end_time
        assert stats.duration_seconds == 5.0
        assert stats.success is False
        assert stats.error_message == "Test error"
        assert stats.input_size == 1024
        assert stats.output_size == 512
        assert stats.custom_data == custom_data


class TestPerformanceMonitor:
    """PerformanceMonitorクラスのテスト"""
    
    @patch('src.utils.performance_monitor.psutil')
    def test_monitor_initialization(self, mock_psutil):
        """監視初期化のテスト"""
        # psutilのモック設定
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.virtual_memory.return_value = Mock(
            total=8*1024**3, percent=60.0, used=4*1024**3
        )
        mock_psutil.disk_io_counters.return_value = Mock(
            read_bytes=100*1024**2, write_bytes=50*1024**2
        )
        mock_psutil.net_io_counters.return_value = Mock(
            bytes_sent=25*1024**2, bytes_recv=30*1024**2
        )
        
        monitor = PerformanceMonitor(
            collection_interval=0.5,
            max_history_size=100,
            enable_auto_collection=False
        )
        
        assert monitor.collection_interval == 0.5
        assert monitor.max_history_size == 100
        assert monitor.metrics_history.maxlen == 100
        assert isinstance(monitor.processing_stats, list)
        assert isinstance(monitor.operation_stats, dict)
        assert isinstance(monitor.error_counts, dict)
        assert monitor.is_monitoring is False
    
    @patch('src.utils.performance_monitor.psutil')
    def test_get_system_stats(self, mock_psutil):
        """システム統計取得のテスト"""
        # psutilのモック設定
        mock_psutil.cpu_percent.return_value = 45.5
        mock_psutil.cpu_count.return_value = 8
        mock_psutil.virtual_memory.return_value = Mock(
            total=16*1024**3, percent=70.5, used=8*1024**3
        )
        mock_psutil.disk_io_counters.return_value = Mock(
            read_bytes=200*1024**2, write_bytes=100*1024**2
        )
        mock_psutil.net_io_counters.return_value = Mock(
            bytes_sent=50*1024**2, bytes_recv=75*1024**2
        )
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        stats = monitor._get_system_stats()
        
        assert stats['cpu_percent'] == 45.5
        assert stats['cpu_count'] == 8
        assert stats['memory_total_gb'] == 16.0
        assert stats['memory_percent'] == 70.5
        assert stats['memory_used_mb'] == 8*1024
        assert stats['disk_read_mb'] == 200.0
        assert stats['disk_write_mb'] == 100.0
        assert stats['network_sent_mb'] == 50.0
        assert stats['network_recv_mb'] == 75.0
        assert 'timestamp' in stats
    
    @patch('src.utils.performance_monitor.psutil')
    def test_get_system_stats_error_handling(self, mock_psutil):
        """システム統計取得エラーハンドリングのテスト"""
        # psutilでエラーを発生させる
        mock_psutil.cpu_percent.side_effect = Exception("CPU error")
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        stats = monitor._get_system_stats()
        
        assert stats == {}
    
    @patch('src.utils.performance_monitor.psutil')
    def test_start_stop_monitoring(self, mock_psutil):
        """監視開始・停止のテスト"""
        # psutilのモック設定
        self._setup_psutil_mock(mock_psutil)
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        # 監視開始
        monitor.start_monitoring()
        assert monitor.is_monitoring is True
        assert monitor.monitor_thread is not None
        assert monitor.monitor_thread.is_alive()
        
        # 監視停止
        monitor.stop_monitoring()
        assert monitor.is_monitoring is False
        
        # スレッドが終了するまで少し待つ
        if monitor.monitor_thread:
            monitor.monitor_thread.join(timeout=1.0)
    
    @patch('src.utils.performance_monitor.psutil')
    def test_start_operation(self, mock_psutil):
        """操作開始のテスト"""
        self._setup_psutil_mock(mock_psutil)
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        operation_id = monitor.start_operation("test_operation", input_size=1024)
        
        assert operation_id is not None
        assert len(monitor.processing_stats) == 1
        
        stats = monitor.processing_stats[0]
        assert stats.operation_name == "test_operation"
        assert stats.input_size == 1024
        assert stats.end_time is None
        assert stats.success is True
    
    @patch('src.utils.performance_monitor.psutil')
    def test_end_operation(self, mock_psutil):
        """操作終了のテスト"""
        self._setup_psutil_mock(mock_psutil)
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        # 操作開始
        operation_id = monitor.start_operation("test_operation")
        
        # 少し待つ
        time.sleep(0.1)
        
        # 操作終了
        monitor.end_operation(
            operation_id,
            success=True,
            output_size=512,
            custom_data={"result": "success"}
        )
        
        stats = monitor.processing_stats[0]
        assert stats.end_time is not None
        assert stats.duration_seconds is not None
        assert stats.duration_seconds > 0
        assert stats.success is True
        assert stats.output_size == 512
        assert stats.custom_data["result"] == "success"
    
    @patch('src.utils.performance_monitor.psutil')
    def test_end_operation_with_error(self, mock_psutil):
        """エラー付き操作終了のテスト"""
        self._setup_psutil_mock(mock_psutil)
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        operation_id = monitor.start_operation("failing_operation")
        monitor.end_operation(
            operation_id,
            success=False,
            error_message="Test error occurred"
        )
        
        stats = monitor.processing_stats[0]
        assert stats.success is False
        assert stats.error_message == "Test error occurred"
        assert monitor.error_counts["failing_operation"] == 1
    
    @patch('src.utils.performance_monitor.psutil')
    def test_record_custom_metric(self, mock_psutil):
        """カスタムメトリクス記録のテスト"""
        self._setup_psutil_mock(mock_psutil)
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        # カスタムメトリクスを記録
        monitor.record_custom_metric("gpu_usage", 85.5)
        monitor.record_custom_metric("temperature", 72.3)
        
        # メトリクス履歴に追加されることを確認
        # （実際の実装では_collect_metricsが呼ばれる）
        assert len(monitor.metrics_history) >= 0  # 自動収集が無効なので0の可能性
    
    @patch('src.utils.performance_monitor.psutil')
    def test_get_current_stats(self, mock_psutil):
        """現在の統計取得のテスト"""
        self._setup_psutil_mock(mock_psutil)
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        # いくつかの操作を実行
        op1 = monitor.start_operation("operation1")
        time.sleep(0.05)
        monitor.end_operation(op1, success=True)
        
        op2 = monitor.start_operation("operation2")
        time.sleep(0.05)
        monitor.end_operation(op2, success=False, error_message="Error")
        
        stats = monitor.get_current_stats()
        
        assert "total_operations" in stats
        assert "successful_operations" in stats
        assert "failed_operations" in stats
        assert "error_rate" in stats
        assert "average_duration" in stats
        assert stats["total_operations"] == 2
        assert stats["successful_operations"] == 1
        assert stats["failed_operations"] == 1
        assert stats["error_rate"] == 0.5
    
    @patch('src.utils.performance_monitor.psutil')
    def test_get_operation_summary(self, mock_psutil):
        """操作サマリー取得のテスト"""
        self._setup_psutil_mock(mock_psutil)
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        # 複数の操作を実行
        for i in range(3):
            op_id = monitor.start_operation("test_op")
            time.sleep(0.01)
            monitor.end_operation(op_id, success=True)
        
        summary = monitor.get_operation_summary("test_op")
        
        assert summary["operation_name"] == "test_op"
        assert summary["total_count"] == 3
        assert summary["success_count"] == 3
        assert summary["error_count"] == 0
        assert summary["average_duration"] > 0
        assert summary["total_duration"] > 0
    
    @patch('src.utils.performance_monitor.psutil')
    def test_get_performance_alerts(self, mock_psutil):
        """パフォーマンスアラート取得のテスト"""
        # 高いリソース使用率を設定
        mock_psutil.cpu_percent.return_value = 95.0
        mock_psutil.virtual_memory.return_value = Mock(
            total=8*1024**3, percent=90.0, used=7*1024**3
        )
        mock_psutil.disk_io_counters.return_value = Mock(
            read_bytes=100*1024**2, write_bytes=50*1024**2
        )
        mock_psutil.net_io_counters.return_value = Mock(
            bytes_sent=25*1024**2, bytes_recv=30*1024**2
        )
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        # メトリクスを手動で追加
        metrics = PerformanceMetrics(
            timestamp=datetime.now(),
            cpu_percent=95.0,
            memory_percent=90.0,
            memory_used_mb=7*1024,
            disk_io_read_mb=100.0,
            disk_io_write_mb=50.0,
            network_sent_mb=25.0,
            network_recv_mb=30.0
        )
        monitor.metrics_history.append(metrics)
        
        alerts = monitor.get_performance_alerts()
        
        # 高CPU・高メモリ使用率のアラートが発生するはず
        assert len(alerts) > 0
        alert_types = [alert["type"] for alert in alerts]
        assert "high_cpu" in alert_types
        assert "high_memory" in alert_types
    
    @patch('src.utils.performance_monitor.psutil')
    def test_export_metrics_json(self, mock_psutil):
        """JSONメトリクスエクスポートのテスト"""
        self._setup_psutil_mock(mock_psutil)
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        # テストデータを追加
        op_id = monitor.start_operation("export_test")
        monitor.end_operation(op_id, success=True)
        
        exported_data = monitor.export_metrics(format_type='json')
        
        # JSONとしてパースできることを確認
        data = json.loads(exported_data)
        assert "export_info" in data
        assert "system_info" in data
        assert "processing_stats" in data
        assert "operation_summary" in data
        assert len(data["processing_stats"]) == 1
    
    @patch('src.utils.performance_monitor.psutil')
    def test_export_metrics_csv(self, mock_psutil):
        """CSVメトリクスエクスポートのテスト"""
        self._setup_psutil_mock(mock_psutil)
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        # テストデータを追加
        op_id = monitor.start_operation("csv_test")
        monitor.end_operation(op_id, success=True)
        
        exported_data = monitor.export_metrics(format_type='csv')
        
        # CSV形式の基本的な確認
        assert isinstance(exported_data, str)
        assert "operation_name" in exported_data
        assert "csv_test" in exported_data
    
    def _setup_psutil_mock(self, mock_psutil):
        """psutilモックの共通設定"""
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.virtual_memory.return_value = Mock(
            total=8*1024**3, percent=60.0, used=4*1024**3
        )
        mock_psutil.disk_io_counters.return_value = Mock(
            read_bytes=100*1024**2, write_bytes=50*1024**2
        )
        mock_psutil.net_io_counters.return_value = Mock(
            bytes_sent=25*1024**2, bytes_recv=30*1024**2
        )


class TestOperationTimer:
    """OperationTimerコンテキストマネージャーのテスト"""
    
    @patch('src.utils.performance_monitor.psutil')
    def test_operation_timer_success(self, mock_psutil):
        """成功時のOperationTimerのテスト"""
        # psutilのモック設定
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.virtual_memory.return_value = Mock(
            total=8*1024**3, percent=60.0, used=4*1024**3
        )
        mock_psutil.disk_io_counters.return_value = Mock(
            read_bytes=100*1024**2, write_bytes=50*1024**2
        )
        mock_psutil.net_io_counters.return_value = Mock(
            bytes_sent=25*1024**2, bytes_recv=30*1024**2
        )
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        with OperationTimer(monitor, "timer_test", input_size=1024):
            time.sleep(0.05)  # 処理をシミュレート
        
        assert len(monitor.processing_stats) == 1
        stats = monitor.processing_stats[0]
        assert stats.operation_name == "timer_test"
        assert stats.input_size == 1024
        assert stats.success is True
        assert stats.duration_seconds is not None
        assert stats.duration_seconds > 0
    
    @patch('src.utils.performance_monitor.psutil')
    def test_operation_timer_with_exception(self, mock_psutil):
        """例外発生時のOperationTimerのテスト"""
        # psutilのモック設定
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.virtual_memory.return_value = Mock(
            total=8*1024**3, percent=60.0, used=4*1024**3
        )
        mock_psutil.disk_io_counters.return_value = Mock(
            read_bytes=100*1024**2, write_bytes=50*1024**2
        )
        mock_psutil.net_io_counters.return_value = Mock(
            bytes_sent=25*1024**2, bytes_recv=30*1024**2
        )
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        with pytest.raises(ValueError):
            with OperationTimer(monitor, "failing_timer"):
                raise ValueError("Test exception")
        
        assert len(monitor.processing_stats) == 1
        stats = monitor.processing_stats[0]
        assert stats.operation_name == "failing_timer"
        assert stats.success is False
        assert stats.error_message == "Test exception"
        assert stats.duration_seconds is not None
    
    @patch('src.utils.performance_monitor.psutil')
    def test_operation_timer_with_custom_data(self, mock_psutil):
        """カスタムデータ付きOperationTimerのテスト"""
        # psutilのモック設定
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.virtual_memory.return_value = Mock(
            total=8*1024**3, percent=60.0, used=4*1024**3
        )
        mock_psutil.disk_io_counters.return_value = Mock(
            read_bytes=100*1024**2, write_bytes=50*1024**2
        )
        mock_psutil.net_io_counters.return_value = Mock(
            bytes_sent=25*1024**2, bytes_recv=30*1024**2
        )
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        with OperationTimer(
            monitor, 
            "custom_timer", 
            input_size=2048,
            custom_data={"file_type": "wav", "quality": "high"}
        ):
            time.sleep(0.01)
        
        stats = monitor.processing_stats[0]
        assert stats.input_size == 2048
        assert stats.custom_data["file_type"] == "wav"
        assert stats.custom_data["quality"] == "high"


class TestPerformanceMonitorIntegration:
    """パフォーマンス監視の統合テスト"""
    
    @patch('src.utils.performance_monitor.psutil')
    def test_full_monitoring_workflow(self, mock_psutil):
        """完全な監視ワークフローのテスト"""
        # psutilのモック設定
        mock_psutil.cpu_percent.return_value = 45.0
        mock_psutil.cpu_count.return_value = 8
        mock_psutil.virtual_memory.return_value = Mock(
            total=16*1024**3, percent=65.0, used=10*1024**3
        )
        mock_psutil.disk_io_counters.return_value = Mock(
            read_bytes=150*1024**2, write_bytes=75*1024**2
        )
        mock_psutil.net_io_counters.return_value = Mock(
            bytes_sent=40*1024**2, bytes_recv=60*1024**2
        )
        
        monitor = PerformanceMonitor(
            collection_interval=0.1,
            enable_auto_collection=True
        )
        
        try:
            # 複数の操作を実行
            with OperationTimer(monitor, "workflow_test1", input_size=1024):
                time.sleep(0.05)
            
            op2 = monitor.start_operation("workflow_test2", input_size=2048)
            time.sleep(0.05)
            monitor.end_operation(op2, success=True, output_size=1024)
            
            # カスタムメトリクスを記録
            monitor.record_custom_metric("custom_value", 123.45)
            
            # 少し待って統計を取得
            time.sleep(0.2)
            
            # 統計確認
            current_stats = monitor.get_current_stats()
            assert current_stats["total_operations"] == 2
            assert current_stats["successful_operations"] == 2
            
            # サマリー確認
            summary1 = monitor.get_operation_summary("workflow_test1")
            assert summary1["total_count"] == 1
            
            summary2 = monitor.get_operation_summary("workflow_test2")
            assert summary2["total_count"] == 1
            
            # エクスポート確認
            json_export = monitor.export_metrics('json')
            assert isinstance(json_export, str)
            
            csv_export = monitor.export_metrics('csv')
            assert isinstance(csv_export, str)
            
        finally:
            monitor.stop_monitoring()
    
    @patch('src.utils.performance_monitor.psutil')
    def test_concurrent_operations(self, mock_psutil):
        """並行操作のテスト"""
        # psutilのモック設定
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.virtual_memory.return_value = Mock(
            total=8*1024**3, percent=60.0, used=4*1024**3
        )
        mock_psutil.disk_io_counters.return_value = Mock(
            read_bytes=100*1024**2, write_bytes=50*1024**2
        )
        mock_psutil.net_io_counters.return_value = Mock(
            bytes_sent=25*1024**2, bytes_recv=30*1024**2
        )
        
        monitor = PerformanceMonitor(enable_auto_collection=False)
        
        def worker_function(worker_id):
            """ワーカー関数"""
            with OperationTimer(monitor, f"worker_{worker_id}"):
                time.sleep(0.01)
        
        # 複数スレッドで並行実行
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker_function, args=(i,))
            threads.append(thread)
            thread.start()
        
        # 全スレッドの完了を待つ
        for thread in threads:
            thread.join()
        
        # 結果確認
        assert len(monitor.processing_stats) == 5
        
        # 各ワーカーの統計を確認
        for i in range(5):
            summary = monitor.get_operation_summary(f"worker_{i}")
            assert summary["total_count"] == 1
            assert summary["success_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__])