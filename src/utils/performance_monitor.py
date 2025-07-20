"""
STT議事録システム - パフォーマンス監視

システムのパフォーマンス監視、メトリクス収集、リソース使用量追跡などの機能を提供
"""

import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
import logging

from . import get_logger


@dataclass
class PerformanceMetrics:
    """パフォーマンスメトリクスデータクラス"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    custom_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingStats:
    """処理統計データクラス"""
    operation_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    input_size: Optional[int] = None
    output_size: Optional[int] = None
    custom_data: Dict[str, Any] = field(default_factory=dict)


class PerformanceMonitor:
    """パフォーマンス監視クラス"""
    
    def __init__(self, 
                 collection_interval: float = 1.0,
                 max_history_size: int = 1000,
                 enable_auto_collection: bool = True):
        """
        パフォーマンス監視の初期化
        
        Args:
            collection_interval: メトリクス収集間隔（秒）
            max_history_size: 履歴の最大保持数
            enable_auto_collection: 自動収集を有効にするか
        """
        self.logger = get_logger(__name__)
        self.collection_interval = collection_interval
        self.max_history_size = max_history_size
        
        # メトリクス履歴
        self.metrics_history: deque = deque(maxlen=max_history_size)
        self.processing_stats: List[ProcessingStats] = []
        
        # 統計情報
        self.operation_stats: Dict[str, List[float]] = defaultdict(list)
        self.error_counts: Dict[str, int] = defaultdict(int)
        
        # 監視状態
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # 初期システム情報
        self.initial_stats = self._get_system_stats()
        
        # 自動収集開始
        if enable_auto_collection:
            self.start_monitoring()
    
    def _get_system_stats(self) -> Dict[str, Any]:
        """現在のシステム統計を取得"""
        try:
            # CPU情報
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            
            # メモリ情報
            memory = psutil.virtual_memory()
            
            # ディスク情報
            disk_io = psutil.disk_io_counters()
            
            # ネットワーク情報
            network_io = psutil.net_io_counters()
            
            return {
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'memory_total_gb': memory.total / (1024**3),
                'memory_percent': memory.percent,
                'memory_used_mb': memory.used / (1024**2),
                'disk_read_mb': disk_io.read_bytes / (1024**2) if disk_io else 0,
                'disk_write_mb': disk_io.write_bytes / (1024**2) if disk_io else 0,
                'network_sent_mb': network_io.bytes_sent / (1024**2) if network_io else 0,
                'network_recv_mb': network_io.bytes_recv / (1024**2) if network_io else 0,
                'timestamp': datetime.now()
            }
        except Exception as e:
            self.logger.warning(f"システム統計取得エラー: {str(e)}")
            return {}
    
    def start_monitoring(self) -> None:
        """パフォーマンス監視を開始"""
        if self.is_monitoring:
            self.logger.warning("パフォーマンス監視は既に開始されています")
            return
        
        self.is_monitoring = True
        self.stop_event.clear()
        
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitor_thread.start()
        
        self.logger.info("パフォーマンス監視を開始しました")
    
    def stop_monitoring(self) -> None:
        """パフォーマンス監視を停止"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self.stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        
        self.logger.info("パフォーマンス監視を停止しました")
    
    def _monitoring_loop(self) -> None:
        """監視ループ"""
        while not self.stop_event.wait(self.collection_interval):
            try:
                metrics = self._collect_metrics()
                if metrics:
                    self.metrics_history.append(metrics)
            except Exception as e:
                self.logger.error(f"メトリクス収集エラー: {str(e)}")
    
    def _collect_metrics(self) -> Optional[PerformanceMetrics]:
        """現在のメトリクスを収集"""
        try:
            stats = self._get_system_stats()
            
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=stats.get('cpu_percent', 0.0),
                memory_percent=stats.get('memory_percent', 0.0),
                memory_used_mb=stats.get('memory_used_mb', 0.0),
                disk_io_read_mb=stats.get('disk_read_mb', 0.0),
                disk_io_write_mb=stats.get('disk_write_mb', 0.0),
                network_sent_mb=stats.get('network_sent_mb', 0.0),
                network_recv_mb=stats.get('network_recv_mb', 0.0)
            )
        except Exception as e:
            self.logger.error(f"メトリクス収集に失敗: {str(e)}")
            return None
    
    def start_operation(self, operation_name: str, input_size: Optional[int] = None) -> str:
        """操作の開始を記録"""
        operation_id = f"{operation_name}_{int(time.time() * 1000)}"
        
        stats = ProcessingStats(
            operation_name=operation_name,
            start_time=datetime.now(),
            input_size=input_size
        )
        
        # 一時的に辞書で管理（完了時にリストに追加）
        if not hasattr(self, '_active_operations'):
            self._active_operations = {}
        
        self._active_operations[operation_id] = stats
        
        self.logger.debug(f"操作開始: {operation_name} (ID: {operation_id})")
        return operation_id
    
    def end_operation(self, 
                     operation_id: str, 
                     success: bool = True,
                     error_message: Optional[str] = None,
                     output_size: Optional[int] = None,
                     custom_data: Optional[Dict[str, Any]] = None) -> None:
        """操作の終了を記録"""
        if not hasattr(self, '_active_operations') or operation_id not in self._active_operations:
            self.logger.warning(f"不明な操作ID: {operation_id}")
            return
        
        stats = self._active_operations.pop(operation_id)
        stats.end_time = datetime.now()
        stats.duration_seconds = (stats.end_time - stats.start_time).total_seconds()
        stats.success = success
        stats.error_message = error_message
        stats.output_size = output_size
        
        if custom_data:
            stats.custom_data.update(custom_data)
        
        # 統計に追加
        self.processing_stats.append(stats)
        self.operation_stats[stats.operation_name].append(stats.duration_seconds)
        
        if not success:
            self.error_counts[stats.operation_name] += 1
        
        self.logger.debug(f"操作完了: {stats.operation_name} ({stats.duration_seconds:.2f}秒)")
    
    def record_custom_metric(self, name: str, value: Any, timestamp: Optional[datetime] = None) -> None:
        """カスタムメトリクスを記録"""
        if not self.metrics_history:
            # 履歴がない場合は新しいメトリクスを作成
            metrics = PerformanceMetrics(
                timestamp=timestamp or datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                disk_io_read_mb=0.0,
                disk_io_write_mb=0.0,
                network_sent_mb=0.0,
                network_recv_mb=0.0
            )
            self.metrics_history.append(metrics)
        
        # 最新のメトリクスにカスタム値を追加
        latest_metrics = self.metrics_history[-1]
        latest_metrics.custom_metrics[name] = value
        
        self.logger.debug(f"カスタムメトリクス記録: {name} = {value}")
    
    def get_current_stats(self) -> Dict[str, Any]:
        """現在の統計情報を取得"""
        current_system = self._get_system_stats()
        
        return {
            'system': current_system,
            'monitoring': {
                'is_active': self.is_monitoring,
                'collection_interval': self.collection_interval,
                'history_size': len(self.metrics_history),
                'max_history_size': self.max_history_size
            },
            'operations': {
                'total_completed': len(self.processing_stats),
                'active_operations': len(getattr(self, '_active_operations', {})),
                'operation_types': list(self.operation_stats.keys()),
                'error_counts': dict(self.error_counts)
            }
        }
    
    def get_operation_summary(self, operation_name: Optional[str] = None) -> Dict[str, Any]:
        """操作の統計サマリーを取得"""
        if operation_name:
            # 特定の操作の統計
            durations = self.operation_stats.get(operation_name, [])
            errors = self.error_counts.get(operation_name, 0)
            
            if not durations:
                return {'operation_name': operation_name, 'no_data': True}
            
            return {
                'operation_name': operation_name,
                'total_executions': len(durations),
                'success_rate': (len(durations) - errors) / len(durations) * 100,
                'average_duration': sum(durations) / len(durations),
                'min_duration': min(durations),
                'max_duration': max(durations),
                'total_errors': errors
            }
        else:
            # 全操作の統計
            summary = {}
            for op_name in self.operation_stats.keys():
                summary[op_name] = self.get_operation_summary(op_name)
            return summary
    
    def get_resource_usage_trend(self, minutes: int = 10) -> Dict[str, List[Any]]:
        """指定時間内のリソース使用量トレンドを取得"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        recent_metrics = [
            m for m in self.metrics_history 
            if m.timestamp >= cutoff_time
        ]
        
        if not recent_metrics:
            return {}
        
        return {
            'timestamps': [m.timestamp.isoformat() for m in recent_metrics],
            'cpu_percent': [m.cpu_percent for m in recent_metrics],
            'memory_percent': [m.memory_percent for m in recent_metrics],
            'memory_used_mb': [m.memory_used_mb for m in recent_metrics],
            'disk_io_read_mb': [m.disk_io_read_mb for m in recent_metrics],
            'disk_io_write_mb': [m.disk_io_write_mb for m in recent_metrics]
        }
    
    def get_performance_alerts(self) -> List[Dict[str, Any]]:
        """パフォーマンスアラートを取得"""
        alerts = []
        
        if not self.metrics_history:
            return alerts
        
        latest = self.metrics_history[-1]
        
        # CPU使用率アラート
        if latest.cpu_percent > 90:
            alerts.append({
                'type': 'high_cpu',
                'severity': 'critical',
                'message': f'CPU使用率が高すぎます: {latest.cpu_percent:.1f}%',
                'value': latest.cpu_percent,
                'threshold': 90
            })
        elif latest.cpu_percent > 70:
            alerts.append({
                'type': 'high_cpu',
                'severity': 'warning',
                'message': f'CPU使用率が高めです: {latest.cpu_percent:.1f}%',
                'value': latest.cpu_percent,
                'threshold': 70
            })
        
        # メモリ使用率アラート
        if latest.memory_percent > 90:
            alerts.append({
                'type': 'high_memory',
                'severity': 'critical',
                'message': f'メモリ使用率が高すぎます: {latest.memory_percent:.1f}%',
                'value': latest.memory_percent,
                'threshold': 90
            })
        elif latest.memory_percent > 80:
            alerts.append({
                'type': 'high_memory',
                'severity': 'warning',
                'message': f'メモリ使用率が高めです: {latest.memory_percent:.1f}%',
                'value': latest.memory_percent,
                'threshold': 80
            })
        
        # エラー率アラート
        for op_name, durations in self.operation_stats.items():
            if len(durations) >= 5:  # 最低5回の実行がある場合のみ
                errors = self.error_counts.get(op_name, 0)
                error_rate = errors / len(durations) * 100
                
                if error_rate > 20:
                    alerts.append({
                        'type': 'high_error_rate',
                        'severity': 'critical',
                        'message': f'{op_name}のエラー率が高すぎます: {error_rate:.1f}%',
                        'operation': op_name,
                        'value': error_rate,
                        'threshold': 20
                    })
                elif error_rate > 10:
                    alerts.append({
                        'type': 'high_error_rate',
                        'severity': 'warning',
                        'message': f'{op_name}のエラー率が高めです: {error_rate:.1f}%',
                        'operation': op_name,
                        'value': error_rate,
                        'threshold': 10
                    })
        
        return alerts
    
    def export_metrics(self, format_type: str = 'json') -> str:
        """メトリクスをエクスポート"""
        data = {
            'export_timestamp': datetime.now().isoformat(),
            'system_info': self.initial_stats,
            'current_stats': self.get_current_stats(),
            'operation_summary': self.get_operation_summary(),
            'recent_metrics': [
                {
                    'timestamp': m.timestamp.isoformat(),
                    'cpu_percent': m.cpu_percent,
                    'memory_percent': m.memory_percent,
                    'memory_used_mb': m.memory_used_mb,
                    'custom_metrics': m.custom_metrics
                }
                for m in list(self.metrics_history)[-100:]  # 最新100件
            ],
            'processing_stats': [
                {
                    'operation_name': s.operation_name,
                    'start_time': s.start_time.isoformat(),
                    'end_time': s.end_time.isoformat() if s.end_time else None,
                    'duration_seconds': s.duration_seconds,
                    'success': s.success,
                    'error_message': s.error_message,
                    'input_size': s.input_size,
                    'output_size': s.output_size
                }
                for s in self.processing_stats[-50:]  # 最新50件
            ]
        }
        
        if format_type == 'json':
            import json
            return json.dumps(data, indent=2, ensure_ascii=False)
        else:
            return str(data)
    
    def __del__(self):
        """デストラクタ - 監視を停止"""
        try:
            self.stop_monitoring()
        except Exception:
            pass  # デストラクタでは例外を発生させない


# コンテキストマネージャーとしての使用をサポート
class OperationTimer:
    """操作時間測定用コンテキストマネージャー"""
    
    def __init__(self, monitor: PerformanceMonitor, operation_name: str, **kwargs):
        self.monitor = monitor
        self.operation_name = operation_name
        self.kwargs = kwargs
        self.operation_id = None
    
    def __enter__(self):
        self.operation_id = self.monitor.start_operation(self.operation_name, **self.kwargs)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        error_message = str(exc_val) if exc_val else None
        
        self.monitor.end_operation(
            self.operation_id,
            success=success,
            error_message=error_message
        )