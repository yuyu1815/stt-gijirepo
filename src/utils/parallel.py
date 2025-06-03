"""
並列処理モジュール

このモジュールは、並列処理のための機能を提供します。
マルチスレッドやマルチプロセスを使用した並列処理を実装します。
"""
import concurrent.futures
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

from ..infrastructure.config import config_manager
from ..infrastructure.logger import logger


class ParallelExecutionMode(Enum):
    """並列実行モード"""
    THREAD = auto()  # スレッドプール
    PROCESS = auto()  # プロセスプール


T = TypeVar('T')  # 戻り値の型変数
R = TypeVar('R')  # 結果の型変数


@dataclass
class TaskResult:
    """タスク実行結果"""
    task_id: str  # タスクID
    success: bool  # 成功したかどうか
    result: Optional[Any] = None  # 結果
    error: Optional[Exception] = None  # エラー
    execution_time: float = 0.0  # 実行時間（秒）


class ProgressTracker:
    """進捗追跡クラス"""

    def __init__(self, total_tasks: int):
        """
        初期化
        
        Args:
            total_tasks: 全タスク数
        """
        self.total_tasks = total_tasks
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.lock = threading.Lock()
        self.start_time = time.time()
        self.progress_callback = None

    def task_completed(self, success: bool = True) -> None:
        """
        タスク完了を記録
        
        Args:
            success: タスクが成功したかどうか
        """
        with self.lock:
            self.completed_tasks += 1
            if not success:
                self.failed_tasks += 1
                
            if self.progress_callback:
                self.progress_callback(self.completed_tasks, self.total_tasks)

    @property
    def progress(self) -> float:
        """
        進捗率を取得
        
        Returns:
            進捗率（0.0-1.0）
        """
        if self.total_tasks == 0:
            return 1.0
        return self.completed_tasks / self.total_tasks

    @property
    def progress_percent(self) -> int:
        """
        進捗率をパーセントで取得
        
        Returns:
            進捗率（0-100）
        """
        return int(self.progress * 100)

    @property
    def elapsed_time(self) -> float:
        """
        経過時間を取得
        
        Returns:
            経過時間（秒）
        """
        return time.time() - self.start_time

    @property
    def estimated_remaining_time(self) -> Optional[float]:
        """
        推定残り時間を取得
        
        Returns:
            推定残り時間（秒）、計算できない場合はNone
        """
        if self.completed_tasks == 0 or self.progress == 0:
            return None
            
        elapsed = self.elapsed_time
        estimated_total = elapsed / self.progress
        return estimated_total - elapsed

    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        """
        進捗コールバックを設定
        
        Args:
            callback: 進捗コールバック関数 (completed_tasks, total_tasks) -> None
        """
        self.progress_callback = callback


class ParallelExecutor:
    """並列実行クラス"""

    def __init__(self, mode: ParallelExecutionMode = ParallelExecutionMode.THREAD, 
                max_workers: Optional[int] = None):
        """
        初期化
        
        Args:
            mode: 並列実行モード
            max_workers: 最大ワーカー数（Noneの場合は自動設定）
        """
        self.mode = mode
        self.max_workers = max_workers or self._get_default_workers()
        self.executor = None
        self.futures = {}  # タスクIDとFutureのマッピング
        self.results = {}  # タスクIDと結果のマッピング
        self.progress_tracker = None

    def _get_default_workers(self) -> int:
        """
        デフォルトのワーカー数を取得
        
        Returns:
            ワーカー数
        """
        # 設定から取得
        if self.mode == ParallelExecutionMode.THREAD:
            return config_manager.get("parallel.thread_workers", 4)
        else:
            return config_manager.get("parallel.process_workers", 2)

    def _create_executor(self) -> None:
        """エグゼキュータを作成"""
        if self.executor is not None:
            return
            
        if self.mode == ParallelExecutionMode.THREAD:
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
            logger.debug(f"スレッドプールエグゼキュータを作成しました（ワーカー数: {self.max_workers}）")
        else:
            self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers)
            logger.debug(f"プロセスプールエグゼキュータを作成しました（ワーカー数: {self.max_workers}）")

    def _task_done_callback(self, task_id: str, future: Future) -> None:
        """
        タスク完了時のコールバック
        
        Args:
            task_id: タスクID
            future: Future
        """
        try:
            result = future.result()
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = e
            logger.error(f"タスク {task_id} の実行中にエラーが発生しました: {e}")
            
        # 結果を記録
        execution_time = time.time() - self.futures[task_id][1]
        task_result = TaskResult(
            task_id=task_id,
            success=success,
            result=result,
            error=error,
            execution_time=execution_time
        )
        self.results[task_id] = task_result
        
        # 進捗を更新
        if self.progress_tracker:
            self.progress_tracker.task_completed(success)
            
        logger.debug(f"タスク {task_id} が完了しました（成功: {success}, 実行時間: {execution_time:.2f}秒）")

    def submit_task(self, task_id: str, func: Callable[..., R], *args, **kwargs) -> Future:
        """
        タスクを投入
        
        Args:
            task_id: タスクID
            func: 実行する関数
            *args: 関数の位置引数
            **kwargs: 関数のキーワード引数
            
        Returns:
            Future
        """
        if self.executor is None:
            self._create_executor()
            
        future = self.executor.submit(func, *args, **kwargs)
        self.futures[task_id] = (future, time.time())  # Futureと開始時間を記録
        
        # コールバックを設定
        future.add_done_callback(lambda f: self._task_done_callback(task_id, f))
        
        logger.debug(f"タスク {task_id} を投入しました")
        return future

    def map(self, func: Callable[[T], R], items: List[T], task_id_prefix: str = "task") -> List[TaskResult]:
        """
        リストの各要素に関数を適用
        
        Args:
            func: 適用する関数
            items: 入力リスト
            task_id_prefix: タスクIDのプレフィックス
            
        Returns:
            タスク結果のリスト
        """
        if not items:
            return []
            
        # 進捗トラッカーを初期化
        self.progress_tracker = ProgressTracker(len(items))
        
        # タスクを投入
        for i, item in enumerate(items):
            task_id = f"{task_id_prefix}_{i}"
            self.submit_task(task_id, func, item)
            
        # 全タスクの完了を待機
        self.wait_all()
        
        # 結果を返す（投入順に）
        return [self.results[f"{task_id_prefix}_{i}"] for i in range(len(items))]

    def execute_tasks(self, tasks: Dict[str, Tuple[Callable[..., R], List, Dict]]) -> Dict[str, TaskResult]:
        """
        複数のタスクを実行
        
        Args:
            tasks: タスクの辞書 {task_id: (func, args, kwargs)}
            
        Returns:
            タスク結果の辞書 {task_id: TaskResult}
        """
        if not tasks:
            return {}
            
        # 進捗トラッカーを初期化
        self.progress_tracker = ProgressTracker(len(tasks))
        
        # タスクを投入
        for task_id, (func, args, kwargs) in tasks.items():
            self.submit_task(task_id, func, *args, **kwargs)
            
        # 全タスクの完了を待機
        self.wait_all()
        
        return self.results

    def wait_all(self) -> None:
        """全タスクの完了を待機"""
        if not self.futures:
            return
            
        # 全てのFutureを取得
        futures = [future for future, _ in self.futures.values()]
        
        # 完了を待機
        concurrent.futures.wait(futures)
        
        logger.debug("全タスクが完了しました")

    def wait_any(self) -> Optional[str]:
        """
        いずれかのタスクの完了を待機
        
        Returns:
            完了したタスクのID、タスクがない場合はNone
        """
        if not self.futures:
            return None
            
        # 全てのFutureを取得
        futures = {future: task_id for task_id, (future, _) in self.futures.items()}
        
        # いずれかの完了を待機
        done, _ = concurrent.futures.wait(
            futures.keys(), 
            return_when=concurrent.futures.FIRST_COMPLETED
        )
        
        if done:
            completed_future = next(iter(done))
            return futures[completed_future]
            
        return None

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """
        タスクの結果を取得
        
        Args:
            task_id: タスクID
            
        Returns:
            タスク結果、タスクが存在しない場合はNone
        """
        return self.results.get(task_id)

    def get_all_results(self) -> Dict[str, TaskResult]:
        """
        全タスクの結果を取得
        
        Returns:
            タスク結果の辞書 {task_id: TaskResult}
        """
        return self.results.copy()

    def get_progress(self) -> float:
        """
        進捗率を取得
        
        Returns:
            進捗率（0.0-1.0）
        """
        if self.progress_tracker:
            return self.progress_tracker.progress
        return 0.0

    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        """
        進捗コールバックを設定
        
        Args:
            callback: 進捗コールバック関数 (completed_tasks, total_tasks) -> None
        """
        if self.progress_tracker:
            self.progress_tracker.set_progress_callback(callback)

    def shutdown(self, wait: bool = True) -> None:
        """
        エグゼキュータをシャットダウン
        
        Args:
            wait: 実行中のタスクの完了を待機するかどうか
        """
        if self.executor:
            self.executor.shutdown(wait=wait)
            self.executor = None
            logger.debug("エグゼキュータをシャットダウンしました")

    def __enter__(self):
        """コンテキストマネージャのエントリーポイント"""
        self._create_executor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャの終了処理"""
        self.shutdown()


# 便利な関数
def parallel_map(func: Callable[[T], R], items: List[T], 
                mode: ParallelExecutionMode = ParallelExecutionMode.THREAD,
                max_workers: Optional[int] = None) -> List[R]:
    """
    リストの各要素に関数を並列適用
    
    Args:
        func: 適用する関数
        items: 入力リスト
        mode: 並列実行モード
        max_workers: 最大ワーカー数
        
    Returns:
        結果のリスト
    """
    with ParallelExecutor(mode=mode, max_workers=max_workers) as executor:
        results = executor.map(func, items)
        
    # 成功したタスクの結果のみを返す
    return [r.result for r in results if r.success]


def parallel_execute(tasks: Dict[str, Tuple[Callable[..., R], List, Dict]],
                    mode: ParallelExecutionMode = ParallelExecutionMode.THREAD,
                    max_workers: Optional[int] = None) -> Dict[str, Union[R, Exception]]:
    """
    複数のタスクを並列実行
    
    Args:
        tasks: タスクの辞書 {task_id: (func, args, kwargs)}
        mode: 並列実行モード
        max_workers: 最大ワーカー数
        
    Returns:
        結果の辞書 {task_id: result or exception}
    """
    with ParallelExecutor(mode=mode, max_workers=max_workers) as executor:
        task_results = executor.execute_tasks(tasks)
        
    # 結果を整形
    results = {}
    for task_id, result in task_results.items():
        if result.success:
            results[task_id] = result.result
        else:
            results[task_id] = result.error
            
    return results