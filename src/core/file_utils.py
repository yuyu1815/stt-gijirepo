"""
STT議事録システム - ファイル操作ユーティリティ

ファイル操作、パス管理、一時ファイル処理、ファイル検証などの機能を提供
"""

import os
import shutil
import tempfile
import hashlib
import mimetypes
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
import logging

from ..utils import get_logger, FileProcessingError


class FileUtils:
    """ファイル操作を担当するユーティリティクラス"""
    
    # サポートされるファイル形式
    SUPPORTED_AUDIO_FORMATS = {
        '.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.wma'
    }
    
    SUPPORTED_VIDEO_FORMATS = {
        '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'
    }
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.temp_files = []  # 一時ファイルの追跡
    
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """
        ファイルの検証
        
        Args:
            file_path: 検証するファイルのパス
            
        Returns:
            Dict: 検証結果
        """
        try:
            if not os.path.exists(file_path):
                raise FileProcessingError(f"ファイルが見つかりません: {file_path}")
            
            file_path = Path(file_path)
            file_size = file_path.stat().st_size
            file_extension = file_path.suffix.lower()
            
            # MIMEタイプの取得
            mime_type, _ = mimetypes.guess_type(str(file_path))
            
            # ファイル形式の判定
            is_audio = file_extension in self.SUPPORTED_AUDIO_FORMATS
            is_video = file_extension in self.SUPPORTED_VIDEO_FORMATS
            is_supported = is_audio or is_video
            
            # ファイルサイズの制限チェック（2GB）
            max_size = 2 * 1024 * 1024 * 1024  # 2GB
            size_ok = file_size <= max_size
            
            # 空ファイルのチェック
            is_empty = file_size == 0
            
            validation_result = {
                'file_path': str(file_path),
                'file_name': file_path.name,
                'file_size': file_size,
                'file_extension': file_extension,
                'mime_type': mime_type,
                'is_audio': is_audio,
                'is_video': is_video,
                'is_supported': is_supported,
                'size_ok': size_ok,
                'is_empty': is_empty,
                'is_valid': is_supported and size_ok and not is_empty
            }
            
            self.logger.info(f"ファイル検証完了: {file_path.name} - 有効={validation_result['is_valid']}")
            return validation_result
            
        except Exception as e:
            raise FileProcessingError(f"ファイル検証に失敗: {str(e)}")
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        ファイルの詳細情報を取得
        
        Args:
            file_path: ファイルのパス
            
        Returns:
            Dict: ファイル情報
        """
        try:
            file_path = Path(file_path)
            stat = file_path.stat()
            
            # ファイルハッシュの計算
            file_hash = self.calculate_file_hash(str(file_path))
            
            file_info = {
                'absolute_path': str(file_path.absolute()),
                'relative_path': str(file_path),
                'file_name': file_path.name,
                'file_stem': file_path.stem,
                'file_extension': file_path.suffix.lower(),
                'file_size': stat.st_size,
                'file_size_mb': round(stat.st_size / (1024 * 1024), 2),
                'created_time': stat.st_ctime,
                'modified_time': stat.st_mtime,
                'accessed_time': stat.st_atime,
                'file_hash': file_hash,
                'is_readable': os.access(file_path, os.R_OK),
                'is_writable': os.access(file_path, os.W_OK)
            }
            
            self.logger.debug(f"ファイル情報取得完了: {file_path.name}")
            return file_info
            
        except Exception as e:
            raise FileProcessingError(f"ファイル情報取得に失敗: {str(e)}")
    
    def calculate_file_hash(self, file_path: str, algorithm: str = 'md5') -> str:
        """
        ファイルのハッシュ値を計算
        
        Args:
            file_path: ファイルのパス
            algorithm: ハッシュアルゴリズム ('md5', 'sha1', 'sha256')
            
        Returns:
            str: ハッシュ値
        """
        try:
            hash_algorithms = {
                'md5': hashlib.md5(),
                'sha1': hashlib.sha1(),
                'sha256': hashlib.sha256()
            }
            
            if algorithm not in hash_algorithms:
                raise ValueError(f"サポートされていないハッシュアルゴリズム: {algorithm}")
            
            hasher = hash_algorithms[algorithm]
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            
            return hasher.hexdigest()
            
        except Exception as e:
            raise FileProcessingError(f"ファイルハッシュ計算に失敗: {str(e)}")
    
    def create_temp_file(self, suffix: str = '', prefix: str = 'stt_', dir: Optional[str] = None) -> str:
        """
        一時ファイルを作成
        
        Args:
            suffix: ファイル拡張子
            prefix: ファイル名プレフィックス
            dir: 一時ディレクトリ
            
        Returns:
            str: 一時ファイルのパス
        """
        try:
            temp_fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir)
            os.close(temp_fd)
            
            # 一時ファイルを追跡リストに追加
            self.temp_files.append(temp_path)
            
            self.logger.debug(f"一時ファイル作成: {temp_path}")
            return temp_path
            
        except Exception as e:
            raise FileProcessingError(f"一時ファイル作成に失敗: {str(e)}")
    
    def create_temp_directory(self, prefix: str = 'stt_', dir: Optional[str] = None) -> str:
        """
        一時ディレクトリを作成
        
        Args:
            prefix: ディレクトリ名プレフィックス
            dir: 親ディレクトリ
            
        Returns:
            str: 一時ディレクトリのパス
        """
        try:
            temp_dir = tempfile.mkdtemp(prefix=prefix, dir=dir)
            
            # 一時ディレクトリを追跡リストに追加
            self.temp_files.append(temp_dir)
            
            self.logger.debug(f"一時ディレクトリ作成: {temp_dir}")
            return temp_dir
            
        except Exception as e:
            raise FileProcessingError(f"一時ディレクトリ作成に失敗: {str(e)}")
    
    def copy_file(self, src_path: str, dst_path: str, overwrite: bool = False) -> str:
        """
        ファイルをコピー
        
        Args:
            src_path: コピー元ファイルパス
            dst_path: コピー先ファイルパス
            overwrite: 上書きを許可するか
            
        Returns:
            str: コピー先ファイルパス
        """
        try:
            if not os.path.exists(src_path):
                raise FileProcessingError(f"コピー元ファイルが見つかりません: {src_path}")
            
            if os.path.exists(dst_path) and not overwrite:
                raise FileProcessingError(f"コピー先ファイルが既に存在します: {dst_path}")
            
            # ディレクトリが存在しない場合は作成
            dst_dir = os.path.dirname(dst_path)
            if dst_dir:
                os.makedirs(dst_dir, exist_ok=True)
            
            shutil.copy2(src_path, dst_path)
            
            self.logger.info(f"ファイルコピー完了: {src_path} -> {dst_path}")
            return dst_path
            
        except Exception as e:
            raise FileProcessingError(f"ファイルコピーに失敗: {str(e)}")
    
    def move_file(self, src_path: str, dst_path: str, overwrite: bool = False) -> str:
        """
        ファイルを移動
        
        Args:
            src_path: 移動元ファイルパス
            dst_path: 移動先ファイルパス
            overwrite: 上書きを許可するか
            
        Returns:
            str: 移動先ファイルパス
        """
        try:
            if not os.path.exists(src_path):
                raise FileProcessingError(f"移動元ファイルが見つかりません: {src_path}")
            
            if os.path.exists(dst_path) and not overwrite:
                raise FileProcessingError(f"移動先ファイルが既に存在します: {dst_path}")
            
            # ディレクトリが存在しない場合は作成
            dst_dir = os.path.dirname(dst_path)
            if dst_dir:
                os.makedirs(dst_dir, exist_ok=True)
            
            shutil.move(src_path, dst_path)
            
            self.logger.info(f"ファイル移動完了: {src_path} -> {dst_path}")
            return dst_path
            
        except Exception as e:
            raise FileProcessingError(f"ファイル移動に失敗: {str(e)}")
    
    def delete_file(self, file_path: str, ignore_errors: bool = True) -> bool:
        """
        ファイルを削除
        
        Args:
            file_path: 削除するファイルのパス
            ignore_errors: エラーを無視するか
            
        Returns:
            bool: 削除成功の場合True
        """
        try:
            if os.path.exists(file_path):
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                
                self.logger.debug(f"ファイル削除完了: {file_path}")
                return True
            else:
                self.logger.debug(f"削除対象ファイルが存在しません: {file_path}")
                return True
                
        except Exception as e:
            if ignore_errors:
                self.logger.warning(f"ファイル削除に失敗（無視）: {file_path} - {str(e)}")
                return False
            else:
                raise FileProcessingError(f"ファイル削除に失敗: {str(e)}")
    
    def ensure_directory(self, dir_path: str) -> str:
        """
        ディレクトリの存在を確認し、必要に応じて作成
        
        Args:
            dir_path: ディレクトリパス
            
        Returns:
            str: ディレクトリパス
        """
        try:
            os.makedirs(dir_path, exist_ok=True)
            self.logger.debug(f"ディレクトリ確保完了: {dir_path}")
            return dir_path
            
        except Exception as e:
            raise FileProcessingError(f"ディレクトリ作成に失敗: {str(e)}")
    
    def get_available_filename(self, file_path: str) -> str:
        """
        利用可能なファイル名を取得（重複回避）
        
        Args:
            file_path: 希望するファイルパス
            
        Returns:
            str: 利用可能なファイルパス
        """
        try:
            if not os.path.exists(file_path):
                return file_path
            
            file_path = Path(file_path)
            stem = file_path.stem
            suffix = file_path.suffix
            parent = file_path.parent
            
            counter = 1
            while True:
                new_name = f"{stem}_{counter}{suffix}"
                new_path = parent / new_name
                
                if not os.path.exists(new_path):
                    return str(new_path)
                
                counter += 1
                
                # 無限ループ防止
                if counter > 1000:
                    raise FileProcessingError("利用可能なファイル名が見つかりません")
                    
        except Exception as e:
            raise FileProcessingError(f"利用可能ファイル名取得に失敗: {str(e)}")
    
    def get_disk_usage(self, path: str) -> Dict[str, int]:
        """
        ディスク使用量を取得
        
        Args:
            path: チェックするパス
            
        Returns:
            Dict: ディスク使用量情報
        """
        try:
            usage = shutil.disk_usage(path)
            
            return {
                'total': usage.total,
                'used': usage.used,
                'free': usage.free,
                'total_gb': round(usage.total / (1024**3), 2),
                'used_gb': round(usage.used / (1024**3), 2),
                'free_gb': round(usage.free / (1024**3), 2),
                'usage_percent': round((usage.used / usage.total) * 100, 2)
            }
            
        except Exception as e:
            raise FileProcessingError(f"ディスク使用量取得に失敗: {str(e)}")
    
    def cleanup_temp_files(self) -> int:
        """
        作成した一時ファイルをクリーンアップ
        
        Returns:
            int: 削除したファイル数
        """
        deleted_count = 0
        
        for temp_path in self.temp_files[:]:  # コピーを作成してイテレート
            try:
                if self.delete_file(temp_path, ignore_errors=True):
                    deleted_count += 1
                    self.temp_files.remove(temp_path)
            except Exception as e:
                self.logger.warning(f"一時ファイル削除失敗: {temp_path} - {str(e)}")
        
        if deleted_count > 0:
            self.logger.info(f"一時ファイルクリーンアップ完了: {deleted_count}ファイル削除")
        
        return deleted_count
    
    def get_file_type(self, file_path: str) -> str:
        """
        ファイルタイプを判定
        
        Args:
            file_path: ファイルパス
            
        Returns:
            str: ファイルタイプ ("audio", "video", "unknown")
        """
        try:
            validation = self.validate_file(file_path)
            
            if validation['is_audio']:
                return "audio"
            elif validation['is_video']:
                return "video"
            else:
                return "unknown"
                
        except Exception:
            return "unknown"
    
    def format_file_size(self, size_bytes: int) -> str:
        """
        ファイルサイズを人間が読みやすい形式にフォーマット
        
        Args:
            size_bytes: バイト数
            
        Returns:
            str: フォーマットされたサイズ
        """
        try:
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.1f} PB"
            
        except Exception:
            return "Unknown size"
    
    def __del__(self):
        """デストラクタ - 一時ファイルのクリーンアップ"""
        try:
            self.cleanup_temp_files()
        except Exception:
            pass  # デストラクタでは例外を発生させない