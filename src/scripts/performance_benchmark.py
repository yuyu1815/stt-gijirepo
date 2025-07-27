#!/usr/bin/env python3
"""
STT議事録システム - パフォーマンスベンチマークスクリプト

システムの性能測定とベンチマークテストを実行
"""

import os
import sys
import json
import time
import psutil
import argparse
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_logging
from src.utils.performance_monitor import PerformanceMonitor
from src.utils.retry_utils import method_error_handler
from src.utils.error_handling import STTError
from src.workflows.stt_workflow import execute_stt_workflow
from src.workflows.state import create_default_config
from src.core.audio_processing import AudioProcessor
from src.core.ai_services import GeminiService


class PerformanceBenchmark:
    """パフォーマンスベンチマークを管理するクラス"""
    
    def __init__(self, config_path: Optional[str] = None, output_file: Optional[str] = None):
        """
        ベンチマーククラスの初期化
        
        Args:
            config_path: 設定ファイルのパス
            output_file: 結果出力ファイルのパス
        """
        self.logger = logging.getLogger(__name__)
        self.output_file = output_file
        self.performance_monitor = PerformanceMonitor()
        
        # 設定の読み込み
        if config_path and Path(config_path).exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = create_default_config()
        
        # ベンチマーク結果
        self.benchmark_results = {
            "timestamp": datetime.now().isoformat(),
            "system_info": self._get_system_info(),
            "tests": {}
        }
        
        # テスト用音声ファイル
        self.test_files = []
        
    @method_error_handler(STTError, "ベンチマーク実行に失敗")
    def run_all_benchmarks(self) -> Dict[str, Any]:
        """
        全てのベンチマークテストを実行
        
        Returns:
            ベンチマーク結果
        """
        self.logger.info("パフォーマンスベンチマークを開始します")
        
        try:
            # テスト用ファイルの準備
            self._prepare_test_files()
            
            # 1. 音声処理ベンチマーク
            self._benchmark_audio_processing()
            
            # 2. AI処理ベンチマーク
            self._benchmark_ai_processing()
            
            # 3. ワークフローベンチマーク
            self._benchmark_workflow()
            
            # 4. 並列処理ベンチマーク
            self._benchmark_concurrent_processing()
            
            # 5. メモリ使用量ベンチマーク
            self._benchmark_memory_usage()
            
            # 6. ストレステスト
            self._benchmark_stress_test()
            
            # 結果の保存
            self._save_results()
            
            self.logger.info("ベンチマークが完了しました")
            return self.benchmark_results
        finally:
            # テスト用ファイルのクリーンアップ
            self._cleanup_test_files()
    
    def _get_system_info(self) -> Dict[str, Any]:
        """システム情報の取得"""
        return {
            "cpu_count": psutil.cpu_count(),
            "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "disk_usage": psutil.disk_usage('/').total,
            "python_version": sys.version,
            "platform": sys.platform
        }
    
    def _prepare_test_files(self):
        """テスト用音声ファイルの準備"""
        self.logger.info("テスト用ファイルを準備しています...")
        
        from pydub import AudioSegment
        
        # 異なる長さの音声ファイルを生成
        durations = [30, 120, 300, 600, 1200]  # 30秒、2分、5分、10分、20分
        
        for duration in durations:
            # 無音音声を生成
            audio = AudioSegment.silent(duration=duration * 1000)
            
            # 一時ファイルとして保存
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            audio.export(temp_file.name, format="wav")
            
            self.test_files.append({
                "path": temp_file.name,
                "duration": duration,
                "size": os.path.getsize(temp_file.name)
            })
        
        self.logger.info(f"{len(self.test_files)}個のテストファイルを準備しました")
    
    @method_error_handler(STTError, "テストファイルのクリーンアップに失敗")
    def _cleanup_test_files(self):
        """テスト用ファイルのクリーンアップ"""
        for test_file in self.test_files:
            file_path = test_file["path"]
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except Exception as e:
                    self.logger.warning(f"テストファイルの削除に失敗: {file_path} - {e}")
    
    def _benchmark_audio_processing(self):
        """音声処理のベンチマーク"""
        self.logger.info("音声処理ベンチマークを実行中...")
        
        processor = AudioProcessor()
        results = []
        
        for test_file in self.test_files:
            file_path = test_file["path"]
            duration = test_file["duration"]
            
            # 音声読み込みベンチマーク
            start_time = time.time()
            audio = processor.load_audio(file_path)
            load_time = time.time() - start_time
            
            # メタデータ取得ベンチマーク
            start_time = time.time()
            metadata = processor.get_audio_metadata(file_path)
            metadata_time = time.time() - start_time
            
            # 音声分割ベンチマーク（長い音声のみ）
            split_time = 0
            if duration > 300:  # 5分以上
                start_time = time.time()
                chunks = processor.split_audio(audio, chunk_duration=300)
                split_time = time.time() - start_time
            
            # 正規化ベンチマーク
            start_time = time.time()
            normalized = processor.normalize_audio(audio)
            normalize_time = time.time() - start_time
            
            results.append({
                "duration": duration,
                "file_size": test_file["size"],
                "load_time": load_time,
                "metadata_time": metadata_time,
                "split_time": split_time,
                "normalize_time": normalize_time,
                "total_time": load_time + metadata_time + split_time + normalize_time
            })
        
        self.benchmark_results["tests"]["audio_processing"] = {
            "results": results,
            "summary": {
                "avg_load_time": statistics.mean([r["load_time"] for r in results]),
                "avg_metadata_time": statistics.mean([r["metadata_time"] for r in results]),
                "avg_normalize_time": statistics.mean([r["normalize_time"] for r in results]),
                "total_files_processed": len(results)
            }
        }
    
    def _benchmark_ai_processing(self):
        """AI処理のベンチマーク"""
        self.logger.info("AI処理ベンチマークを実行中...")
        
        # APIキーが設定されていない場合はスキップ
        if not self.config.get("gemini_api_key") or self.config["gemini_api_key"] == "your_gemini_api_key_here":
            self.logger.warning("APIキーが設定されていないため、AI処理ベンチマークをスキップします")
            self.benchmark_results["tests"]["ai_processing"] = {"skipped": True, "reason": "No API key"}
            return
        
        try:
            service = GeminiService(
                api_key=self.config["gemini_api_key"],
                model_name=self.config.get("gemini_model", "gemini-1.5-pro")
            )
            
            results = []
            
            # 短い音声ファイルのみでテスト（APIコスト削減のため）
            short_files = [f for f in self.test_files if f["duration"] <= 120]
            
            for test_file in short_files:
                file_path = test_file["path"]
                duration = test_file["duration"]
                
                # 文字起こしベンチマーク
                start_time = time.time()
                try:
                    transcription = service.transcribe_audio(file_path)
                    transcription_time = time.time() - start_time
                    transcription_success = True
                except Exception as e:
                    transcription_time = time.time() - start_time
                    transcription_success = False
                    self.logger.warning(f"文字起こしに失敗: {e}")
                
                # 品質チェックベンチマーク（文字起こしが成功した場合のみ）
                quality_check_time = 0
                if transcription_success and transcription:
                    start_time = time.time()
                    try:
                        quality_result = service.check_transcription_quality(transcription, duration)
                        quality_check_time = time.time() - start_time
                    except Exception as e:
                        quality_check_time = time.time() - start_time
                        self.logger.warning(f"品質チェックに失敗: {e}")
                
                results.append({
                    "duration": duration,
                    "transcription_time": transcription_time,
                    "transcription_success": transcription_success,
                    "quality_check_time": quality_check_time,
                    "total_time": transcription_time + quality_check_time
                })
                
                # API制限を考慮して少し待機
                time.sleep(1)
            
            self.benchmark_results["tests"]["ai_processing"] = {
                "results": results,
                "summary": {
                    "avg_transcription_time": statistics.mean([r["transcription_time"] for r in results]),
                    "success_rate": sum(1 for r in results if r["transcription_success"]) / len(results),
                    "total_api_calls": len(results)
                }
            }
            
        except Exception as e:
            self.logger.error(f"AI処理ベンチマークでエラー: {e}")
            self.benchmark_results["tests"]["ai_processing"] = {"error": str(e)}
    
    def _benchmark_workflow(self):
        """ワークフロー全体のベンチマーク"""
        self.logger.info("ワークフローベンチマークを実行中...")
        
        # APIキーが設定されていない場合はスキップ
        if not self.config.get("gemini_api_key") or self.config["gemini_api_key"] == "your_gemini_api_key_here":
            self.logger.warning("APIキーが設定されていないため、ワークフローベンチマークをスキップします")
            self.benchmark_results["tests"]["workflow"] = {"skipped": True, "reason": "No API key"}
            return
        
        results = []
        
        # 短い音声ファイルのみでテスト
        short_files = [f for f in self.test_files if f["duration"] <= 60]
        
        for test_file in short_files:
            file_path = test_file["path"]
            duration = test_file["duration"]
            
            start_time = time.time()
            memory_before = psutil.Process().memory_info().rss
            
            try:
                # ワークフロー実行
                result = execute_stt_workflow(
                    file_path=file_path,
                    config=self.config,
                    upload_to_notion=False
                )
                
                execution_time = time.time() - start_time
                memory_after = psutil.Process().memory_info().rss
                memory_used = memory_after - memory_before
                
                success = result.get("final_status") == "success"
                
                results.append({
                    "duration": duration,
                    "execution_time": execution_time,
                    "memory_used": memory_used,
                    "success": success,
                    "processing_stages": len(result.get("processing_log", [])),
                    "errors": len(result.get("errors", []))
                })
                
            except Exception as e:
                execution_time = time.time() - start_time
                results.append({
                    "duration": duration,
                    "execution_time": execution_time,
                    "memory_used": 0,
                    "success": False,
                    "error": str(e)
                })
                self.logger.warning(f"ワークフロー実行に失敗: {e}")
            
            # API制限を考慮して待機
            time.sleep(2)
        
        if results:
            self.benchmark_results["tests"]["workflow"] = {
                "results": results,
                "summary": {
                    "avg_execution_time": statistics.mean([r["execution_time"] for r in results]),
                    "avg_memory_used": statistics.mean([r["memory_used"] for r in results]),
                    "success_rate": sum(1 for r in results if r["success"]) / len(results),
                    "total_workflows": len(results)
                }
            }
    
    def _benchmark_concurrent_processing(self):
        """並列処理のベンチマーク"""
        self.logger.info("並列処理ベンチマークを実行中...")
        
        processor = AudioProcessor()
        
        # 異なる並列数でテスト
        thread_counts = [1, 2, 4, 8]
        results = []
        
        for thread_count in thread_counts:
            # 短い音声ファイルを使用
            test_files = [f for f in self.test_files if f["duration"] <= 120]
            
            start_time = time.time()
            memory_before = psutil.Process().memory_info().rss
            
            def process_file(file_info):
                try:
                    audio = processor.load_audio(file_info["path"])
                    normalized = processor.normalize_audio(audio)
                    return {"success": True, "duration": file_info["duration"]}
                except Exception as e:
                    return {"success": False, "error": str(e)}
            
            # 並列処理実行
            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                futures = [executor.submit(process_file, f) for f in test_files]
                concurrent_results = [future.result() for future in as_completed(futures)]
            
            execution_time = time.time() - start_time
            memory_after = psutil.Process().memory_info().rss
            memory_used = memory_after - memory_before
            
            success_count = sum(1 for r in concurrent_results if r["success"])
            
            results.append({
                "thread_count": thread_count,
                "execution_time": execution_time,
                "memory_used": memory_used,
                "files_processed": len(test_files),
                "success_count": success_count,
                "success_rate": success_count / len(test_files),
                "throughput": len(test_files) / execution_time
            })
        
        self.benchmark_results["tests"]["concurrent_processing"] = {
            "results": results,
            "summary": {
                "best_throughput": max(r["throughput"] for r in results),
                "optimal_thread_count": max(results, key=lambda x: x["throughput"])["thread_count"]
            }
        }
    
    def _benchmark_memory_usage(self):
        """メモリ使用量のベンチマーク"""
        self.logger.info("メモリ使用量ベンチマークを実行中...")
        
        processor = AudioProcessor()
        results = []
        
        for test_file in self.test_files:
            file_path = test_file["path"]
            duration = test_file["duration"]
            
            # メモリ使用量を監視しながら処理
            memory_samples = []
            
            def monitor_memory():
                while not stop_monitoring:
                    memory_samples.append(psutil.Process().memory_info().rss)
                    time.sleep(0.1)
            
            stop_monitoring = False
            monitor_thread = threading.Thread(target=monitor_memory)
            monitor_thread.start()
            
            try:
                # 音声処理実行
                audio = processor.load_audio(file_path)
                normalized = processor.normalize_audio(audio)
                
                if duration > 300:  # 長い音声は分割
                    chunks = processor.split_audio(audio, chunk_duration=300)
                
            finally:
                stop_monitoring = True
                monitor_thread.join()
            
            if memory_samples:
                results.append({
                    "duration": duration,
                    "file_size": test_file["size"],
                    "peak_memory": max(memory_samples),
                    "avg_memory": statistics.mean(memory_samples),
                    "memory_samples": len(memory_samples)
                })
        
        if results:
            self.benchmark_results["tests"]["memory_usage"] = {
                "results": results,
                "summary": {
                    "peak_memory_usage": max(r["peak_memory"] for r in results),
                    "avg_memory_usage": statistics.mean([r["avg_memory"] for r in results]),
                    "memory_efficiency": min(r["peak_memory"] / r["file_size"] for r in results if r["file_size"] > 0)
                }
            }
    
    def _benchmark_stress_test(self):
        """ストレステスト"""
        self.logger.info("ストレステストを実行中...")
        
        processor = AudioProcessor()
        
        # 連続処理テスト
        iterations = 50
        start_time = time.time()
        memory_before = psutil.Process().memory_info().rss
        
        success_count = 0
        error_count = 0
        
        # 最も短いファイルを使用
        test_file = min(self.test_files, key=lambda x: x["duration"])
        
        for i in range(iterations):
            try:
                audio = processor.load_audio(test_file["path"])
                normalized = processor.normalize_audio(audio)
                success_count += 1
            except Exception as e:
                error_count += 1
                if i < 5:  # 最初の5回のエラーのみログ出力
                    self.logger.warning(f"ストレステスト {i+1} でエラー: {e}")
        
        execution_time = time.time() - start_time
        memory_after = psutil.Process().memory_info().rss
        memory_used = memory_after - memory_before
        
        self.benchmark_results["tests"]["stress_test"] = {
            "iterations": iterations,
            "execution_time": execution_time,
            "memory_used": memory_used,
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": success_count / iterations,
            "throughput": success_count / execution_time,
            "avg_time_per_iteration": execution_time / iterations
        }
    
    def _save_results(self):
        """結果の保存"""
        if self.output_file:
            output_path = Path(self.output_file)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"benchmark_results_{timestamp}.json")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.benchmark_results, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"ベンチマーク結果を保存しました: {output_path}")
        
        # サマリーをコンソールに出力
        self._print_summary()
    
    def _print_summary(self):
        """結果サマリーの出力"""
        print("\n" + "="*60)
        print("パフォーマンスベンチマーク結果サマリー")
        print("="*60)
        
        # システム情報
        sys_info = self.benchmark_results["system_info"]
        print(f"CPU: {sys_info['cpu_count']}コア")
        print(f"メモリ: {sys_info['memory_total'] / (1024**3):.1f}GB")
        
        # テスト結果
        tests = self.benchmark_results["tests"]
        
        if "audio_processing" in tests:
            audio = tests["audio_processing"]["summary"]
            print(f"\n音声処理:")
            print(f"  平均読み込み時間: {audio['avg_load_time']:.3f}秒")
            print(f"  平均正規化時間: {audio['avg_normalize_time']:.3f}秒")
        
        if "ai_processing" in tests and "summary" in tests["ai_processing"]:
            ai = tests["ai_processing"]["summary"]
            print(f"\nAI処理:")
            print(f"  平均文字起こし時間: {ai['avg_transcription_time']:.3f}秒")
            print(f"  成功率: {ai['success_rate']:.1%}")
        
        if "workflow" in tests and "summary" in tests["workflow"]:
            workflow = tests["workflow"]["summary"]
            print(f"\nワークフロー:")
            print(f"  平均実行時間: {workflow['avg_execution_time']:.3f}秒")
            print(f"  平均メモリ使用量: {workflow['avg_memory_used'] / (1024**2):.1f}MB")
            print(f"  成功率: {workflow['success_rate']:.1%}")
        
        if "concurrent_processing" in tests:
            concurrent = tests["concurrent_processing"]["summary"]
            print(f"\n並列処理:")
            print(f"  最高スループット: {concurrent['best_throughput']:.2f}ファイル/秒")
            print(f"  最適スレッド数: {concurrent['optimal_thread_count']}")
        
        if "stress_test" in tests:
            stress = tests["stress_test"]
            print(f"\nストレステスト:")
            print(f"  成功率: {stress['success_rate']:.1%}")
            print(f"  スループット: {stress['throughput']:.2f}処理/秒")
        
        print("="*60)


@method_error_handler(STTError, "ベンチマークメイン関数に失敗", passthrough_exceptions=[KeyboardInterrupt])
def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(
        description="STT議事録システム パフォーマンスベンチマーク"
    )
    parser.add_argument(
        "--config",
        help="設定ファイルのパス"
    )
    parser.add_argument(
        "--output",
        help="結果出力ファイルのパス"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="ログレベル"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="クイックテスト（短時間で完了）"
    )
    
    args = parser.parse_args()
    
    # ログ設定
    setup_logging(level=args.log_level)
    logger = logging.getLogger(__name__)
    
    # ベンチマーク実行
    benchmark = PerformanceBenchmark(
        config_path=args.config,
        output_file=args.output
    )
    
    if args.quick:
        logger.info("クイックベンチマークモードで実行します")
        # クイックモードの実装（必要に応じて）
    
    results = benchmark.run_all_benchmarks()
    
    if "error" in results:
        logger.error("ベンチマークが失敗しました")
        return 1
    else:
        logger.info("ベンチマークが正常に完了しました")
        return 0


if __name__ == "__main__":
    sys.exit(main())