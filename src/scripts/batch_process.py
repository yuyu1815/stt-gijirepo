#!/usr/bin/env python3
"""
STT議事録システム - バッチ処理スクリプト

複数ファイルの一括処理、並列処理、進捗監視機能を提供
"""

import os
import sys
import argparse
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# パッケージパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from workflows.stt_workflow import execute_stt_workflow
from workflows.state import STTConfig, create_default_config
from utils.performance_monitor import PerformanceMonitor
from utils.logging_config import setup_logging
from utils import get_logger
from utils.retry_utils import method_error_handler
from utils.error_handling import STTError


class BatchProcessor:
    """バッチ処理を管理するクラス"""
    
    def __init__(self, config: STTConfig, max_concurrent: int = 3):
        """
        バッチプロセッサの初期化
        
        Args:
            config: STT設定
            max_concurrent: 最大並列処理数
        """
        self.config = config
        self.max_concurrent = max_concurrent
        self.logger = get_logger(__name__)
        self.performance_monitor = PerformanceMonitor(enable_auto_collection=True)
        
        # 処理統計
        self.total_files = 0
        self.processed_files = 0
        self.successful_files = 0
        self.failed_files = 0
        self.start_time = None
        self.results = []
    
    def discover_files(self, input_paths: List[str], recursive: bool = True) -> List[str]:
        """
        処理対象ファイルを発見
        
        Args:
            input_paths: 入力パスのリスト（ファイルまたはディレクトリ）
            recursive: 再帰的にディレクトリを探索するか
            
        Returns:
            処理対象ファイルパスのリスト
        """
        supported_extensions = {
            '.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.wma',  # 音声
            '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'  # 動画
        }
        
        discovered_files = []
        
        for input_path in input_paths:
            path = Path(input_path)
            
            if path.is_file():
                if path.suffix.lower() in supported_extensions:
                    discovered_files.append(str(path))
                else:
                    self.logger.warning(f"サポートされていない形式: {path}")
            
            elif path.is_dir():
                if recursive:
                    pattern = "**/*"
                else:
                    pattern = "*"
                
                for file_path in path.glob(pattern):
                    if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                        discovered_files.append(str(file_path))
            
            else:
                self.logger.error(f"存在しないパス: {path}")
        
        self.logger.info(f"発見されたファイル数: {len(discovered_files)}")
        return discovered_files
    
    @method_error_handler(STTError, "ファイル処理に失敗")
    def process_single_file(self, file_path: str, upload_to_notion: bool = False) -> Dict[str, Any]:
        """
        単一ファイルの処理
        
        Args:
            file_path: ファイルパス
            upload_to_notion: Notionアップロードフラグ
            
        Returns:
            処理結果
        """
        operation_id = self.performance_monitor.start_operation(
            "batch_file_processing",
            input_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0
        )
        
        self.logger.info(f"処理開始: {file_path}")
        
        # 処理実行
        result = execute_stt_workflow(
            file_path=file_path,
            config=self.config,
            upload_to_notion=upload_to_notion
        )
        
        # 結果の拡張
        result.update({
            'batch_info': {
                'processed_at': datetime.now().isoformat(),
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
            }
        })
        
        success = result.get('final_status') == 'success'
        
        self.performance_monitor.end_operation(
            operation_id,
            success=success,
            output_size=len(result.get('minutes', ''))
        )
        
        if success:
            self.successful_files += 1
            self.logger.info(f"処理成功: {file_path}")
        else:
            self.failed_files += 1
            self.logger.error(f"処理失敗: {file_path} - {result.get('errors', [])}")
        
        # 処理カウンタを更新
        self.processed_files += 1
        
        return result
        
    
    @method_error_handler(STTError, "バッチ処理に失敗")
    def process_batch(self, file_paths: List[str], upload_to_notion: bool = False) -> List[Dict[str, Any]]:
        """
        バッチ処理の実行
        
        Args:
            file_paths: 処理対象ファイルパスのリスト
            upload_to_notion: Notionアップロードフラグ
            
        Returns:
            処理結果のリスト
        """
        self.total_files = len(file_paths)
        self.processed_files = 0
        self.successful_files = 0
        self.failed_files = 0
        self.start_time = time.time()
        self.results = []
        
        self.logger.info(f"バッチ処理開始: {self.total_files}ファイル, 並列数: {self.max_concurrent}")
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # 全ファイルの処理を開始
            future_to_file = {
                executor.submit(self.process_single_file, file_path, upload_to_notion): file_path
                for file_path in file_paths
            }
            
            # 完了したタスクから結果を収集
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                
                # Future結果の取得（例外は伝播させる）
                result = future.result()
                self.results.append(result)
                
                # 進捗表示
                progress = (self.processed_files / self.total_files) * 100
                elapsed_time = time.time() - self.start_time
                
                self.logger.info(
                    f"進捗: {self.processed_files}/{self.total_files} ({progress:.1f}%) "
                    f"成功: {self.successful_files}, 失敗: {self.failed_files}, "
                    f"経過時間: {elapsed_time:.1f}秒"
                )
        
        total_time = time.time() - self.start_time
        self.logger.info(
            f"バッチ処理完了: 総時間 {total_time:.1f}秒, "
            f"成功 {self.successful_files}/{self.total_files}, "
            f"失敗 {self.failed_files}/{self.total_files}"
        )
        
        return self.results
    
    def generate_report(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        処理レポートの生成
        
        Args:
            output_path: レポート出力パス
            
        Returns:
            レポートデータ
        """
        total_time = time.time() - self.start_time if self.start_time else 0
        
        report = {
            'batch_summary': {
                'total_files': self.total_files,
                'processed_files': self.processed_files,
                'successful_files': self.successful_files,
                'failed_files': self.failed_files,
                'success_rate': (self.successful_files / self.total_files * 100) if self.total_files > 0 else 0,
                'total_processing_time': total_time,
                'average_time_per_file': total_time / self.processed_files if self.processed_files > 0 else 0,
                'generated_at': datetime.now().isoformat()
            },
            'performance_metrics': self.performance_monitor.get_operation_summary(),
            'system_stats': self.performance_monitor.get_current_stats(),
            'file_results': self.results
        }
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.logger.info(f"レポート出力: {output_path}")
        
        return report
    
    def cleanup(self):
        """リソースのクリーンアップ"""
        if self.performance_monitor:
            self.performance_monitor.stop_monitoring()


def create_config_from_args(args) -> STTConfig:
    """コマンドライン引数から設定を作成"""
    config = create_default_config()
    
    # 引数による設定の上書き
    if args.gemini_api_key:
        config['gemini_api_key'] = args.gemini_api_key
    
    if args.gemini_model:
        config['gemini_model'] = args.gemini_model
    
    if args.notion_token:
        config['notion_token'] = args.notion_token
    
    if args.notion_database_id:
        config['notion_database_id'] = args.notion_database_id
    
    if args.max_retries:
        config['max_retries'] = args.max_retries
    
    if args.chunk_size:
        config['chunk_size'] = args.chunk_size
    
    # 環境変数からの設定読み込み
    config['gemini_api_key'] = config['gemini_api_key'] or os.getenv('GEMINI_API_KEY', '')
    config['notion_token'] = config['notion_token'] or os.getenv('NOTION_TOKEN')
    config['notion_database_id'] = config['notion_database_id'] or os.getenv('NOTION_DATABASE_ID')
    
    return config


@method_error_handler(STTError, "バッチ処理メイン関数に失敗", passthrough_exceptions=[KeyboardInterrupt])
def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='STT議事録システム - バッチ処理スクリプト',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 単一ファイルの処理
  python batch_process.py audio.wav
  
  # 複数ファイルの処理
  python batch_process.py audio1.wav audio2.mp4 video.mov
  
  # ディレクトリの一括処理
  python batch_process.py /path/to/audio/files/ --recursive
  
  # Notionアップロード付き
  python batch_process.py /path/to/files/ --upload-notion --notion-database-id YOUR_DB_ID
  
  # 並列処理数の指定
  python batch_process.py /path/to/files/ --max-concurrent 5
  
  # 設定ファイルの使用
  python batch_process.py /path/to/files/ --config config.json
        """
    )
    
    # 基本引数
    parser.add_argument(
        'input_paths',
        nargs='+',
        help='処理対象のファイルまたはディレクトリパス'
    )
    
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='ディレクトリを再帰的に探索'
    )
    
    parser.add_argument(
        '--max-concurrent', '-c',
        type=int,
        default=3,
        help='最大並列処理数 (デフォルト: 3)'
    )
    
    parser.add_argument(
        '--upload-notion',
        action='store_true',
        help='Notionへのアップロードを有効化'
    )
    
    # 出力設定
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        help='出力ディレクトリ'
    )
    
    parser.add_argument(
        '--report-file',
        type=str,
        help='処理レポートの出力ファイル'
    )
    
    # API設定
    parser.add_argument(
        '--gemini-api-key',
        type=str,
        help='Gemini API キー'
    )
    
    parser.add_argument(
        '--gemini-model',
        type=str,
        help='Gemini モデル名'
    )
    
    parser.add_argument(
        '--notion-token',
        type=str,
        help='Notion インテグレーショントークン'
    )
    
    parser.add_argument(
        '--notion-database-id',
        type=str,
        help='Notion データベースID'
    )
    
    # 処理設定
    parser.add_argument(
        '--max-retries',
        type=int,
        help='最大リトライ回数'
    )
    
    parser.add_argument(
        '--chunk-size',
        type=int,
        help='音声分割サイズ（秒）'
    )
    
    # その他
    parser.add_argument(
        '--config',
        type=str,
        help='設定ファイルパス (JSON形式)'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='ログレベル'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='実際の処理を行わず、処理対象ファイルのみ表示'
    )
    
    args = parser.parse_args()
    
    # ログ設定
    setup_logging(level=args.log_level)
    logger = get_logger(__name__)
    
    # 設定の作成
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        config = STTConfig(**config_data)
    else:
        config = create_config_from_args(args)
    
    # バッチプロセッサの初期化
    processor = BatchProcessor(config, args.max_concurrent)
    
    try:
        # ファイル発見
        file_paths = processor.discover_files(args.input_paths, args.recursive)
        
        if not file_paths:
            logger.error("処理対象ファイルが見つかりませんでした")
            return 1
        
        # ドライラン
        if args.dry_run:
            logger.info("ドライランモード: 処理対象ファイル一覧")
            for i, file_path in enumerate(file_paths, 1):
                logger.info(f"{i:3d}: {file_path}")
            logger.info(f"合計: {len(file_paths)}ファイル")
            return 0
        
        # バッチ処理実行
        results = processor.process_batch(file_paths, args.upload_notion)
        
        # レポート生成
        report_path = args.report_file or f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report = processor.generate_report(report_path)
        
        # 結果サマリー表示
        summary = report['batch_summary']
        logger.info("=" * 60)
        logger.info("バッチ処理結果サマリー")
        logger.info("=" * 60)
        logger.info(f"総ファイル数: {summary['total_files']}")
        logger.info(f"処理済み: {summary['processed_files']}")
        logger.info(f"成功: {summary['successful_files']}")
        logger.info(f"失敗: {summary['failed_files']}")
        logger.info(f"成功率: {summary['success_rate']:.1f}%")
        logger.info(f"総処理時間: {summary['total_processing_time']:.1f}秒")
        logger.info(f"平均処理時間: {summary['average_time_per_file']:.1f}秒/ファイル")
        logger.info(f"レポート: {report_path}")
        logger.info("=" * 60)
        
        # 終了コード
        return 0 if summary['failed_files'] == 0 else 1
        
    finally:
        if processor:
            processor.cleanup()
            
    # KeyboardInterruptはpassthrough_exceptionsで処理されるため、ここでは明示的に処理しない


if __name__ == '__main__':
    sys.exit(main())