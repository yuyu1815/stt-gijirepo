"""
ストレージ管理モジュール

このモジュールは、ファイルの保存や読み込みなどのストレージ関連の機能を提供します。
"""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .config import config_manager
from .logger import logger


class StorageManager:
    """ストレージ管理クラス"""

    def __init__(self):
        """初期化"""
        self.base_output_dir = Path(config_manager.get("output_dir", "output"))
        self._ensure_output_dirs()

    def _ensure_output_dirs(self) -> None:
        """
        出力ディレクトリの存在を確認し、必要に応じて作成
        """
        # 基本出力ディレクトリ
        if not self.base_output_dir.exists():
            self.base_output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"出力ディレクトリを作成しました: {self.base_output_dir}")

        # サブディレクトリ
        subdirs = ["transcripts", "minutes", "images", "reports"]
        for subdir in subdirs:
            path = self.base_output_dir / subdir
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                logger.info(f"サブディレクトリを作成しました: {path}")

    def get_output_dir(self, subdir: Optional[str] = None) -> Path:
        """
        出力ディレクトリを取得
        
        Args:
            subdir: サブディレクトリ名
            
        Returns:
            出力ディレクトリのパス
        """
        if subdir:
            output_dir = self.base_output_dir / subdir
            if not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)
            return output_dir
        return self.base_output_dir

    def get_lecture_output_dir(self, lecture_id: str, subdir: Optional[str] = None) -> Path:
        """
        講義ごとの出力ディレクトリを取得
        
        Args:
            lecture_id: 講義ID
            subdir: サブディレクトリ名
            
        Returns:
            講義ごとの出力ディレクトリのパス
        """
        lecture_dir = self.base_output_dir / lecture_id
        if not lecture_dir.exists():
            lecture_dir.mkdir(parents=True, exist_ok=True)
            
        if subdir:
            subdir_path = lecture_dir / subdir
            if not subdir_path.exists():
                subdir_path.mkdir(parents=True, exist_ok=True)
            return subdir_path
            
        return lecture_dir

    def save_text(self, content: str, file_path: Union[str, Path]) -> Path:
        """
        テキストファイルを保存
        
        Args:
            content: 保存するテキスト内容
            file_path: 保存先ファイルパス
            
        Returns:
            保存したファイルのパス
        """
        file_path = Path(file_path)
        
        # ディレクトリが存在しない場合は作成
        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        logger.debug(f"テキストファイルを保存しました: {file_path}")
        return file_path

    def save_json(self, data: Any, file_path: Union[str, Path]) -> Path:
        """
        JSONファイルを保存
        
        Args:
            data: 保存するデータ
            file_path: 保存先ファイルパス
            
        Returns:
            保存したファイルのパス
        """
        file_path = Path(file_path)
        
        # ディレクトリが存在しない場合は作成
        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        logger.debug(f"JSONファイルを保存しました: {file_path}")
        return file_path

    def load_text(self, file_path: Union[str, Path]) -> str:
        """
        テキストファイルを読み込む
        
        Args:
            file_path: 読み込むファイルパス
            
        Returns:
            ファイルの内容
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.warning(f"ファイルが存在しません: {file_path}")
            return ""
            
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        logger.debug(f"テキストファイルを読み込みました: {file_path}")
        return content

    def load_json(self, file_path: Union[str, Path]) -> Any:
        """
        JSONファイルを読み込む
        
        Args:
            file_path: 読み込むファイルパス
            
        Returns:
            読み込んだデータ
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.warning(f"ファイルが存在しません: {file_path}")
            return {}
            
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        logger.debug(f"JSONファイルを読み込みました: {file_path}")
        return data

    def copy_file(self, src_path: Union[str, Path], dest_path: Union[str, Path]) -> Path:
        """
        ファイルをコピー
        
        Args:
            src_path: コピー元ファイルパス
            dest_path: コピー先ファイルパス
            
        Returns:
            コピー先ファイルのパス
        """
        src_path = Path(src_path)
        dest_path = Path(dest_path)
        
        if not src_path.exists():
            logger.error(f"コピー元ファイルが存在しません: {src_path}")
            raise FileNotFoundError(f"コピー元ファイルが存在しません: {src_path}")
            
        # ディレクトリが存在しない場合は作成
        if not dest_path.parent.exists():
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
        shutil.copy2(src_path, dest_path)
        logger.debug(f"ファイルをコピーしました: {src_path} -> {dest_path}")
        return dest_path

    def move_file(self, src_path: Union[str, Path], dest_path: Union[str, Path]) -> Path:
        """
        ファイルを移動
        
        Args:
            src_path: 移動元ファイルパス
            dest_path: 移動先ファイルパス
            
        Returns:
            移動先ファイルのパス
        """
        src_path = Path(src_path)
        dest_path = Path(dest_path)
        
        if not src_path.exists():
            logger.error(f"移動元ファイルが存在しません: {src_path}")
            raise FileNotFoundError(f"移動元ファイルが存在しません: {src_path}")
            
        # ディレクトリが存在しない場合は作成
        if not dest_path.parent.exists():
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
        shutil.move(src_path, dest_path)
        logger.debug(f"ファイルを移動しました: {src_path} -> {dest_path}")
        return dest_path

    def delete_file(self, file_path: Union[str, Path]) -> bool:
        """
        ファイルを削除
        
        Args:
            file_path: 削除するファイルパス
            
        Returns:
            削除に成功した場合はTrue、それ以外はFalse
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.warning(f"削除対象のファイルが存在しません: {file_path}")
            return False
            
        file_path.unlink()
        logger.debug(f"ファイルを削除しました: {file_path}")
        return True

    def list_files(self, directory: Union[str, Path], pattern: str = "*") -> List[Path]:
        """
        ディレクトリ内のファイル一覧を取得
        
        Args:
            directory: 対象ディレクトリ
            pattern: ファイル名パターン
            
        Returns:
            ファイルパスのリスト
        """
        directory = Path(directory)
        
        if not directory.exists():
            logger.warning(f"ディレクトリが存在しません: {directory}")
            return []
            
        files = list(directory.glob(pattern))
        return files

    def create_temp_dir(self) -> Path:
        """
        一時ディレクトリを作成
        
        Returns:
            作成した一時ディレクトリのパス
        """
        temp_base = Path(config_manager.get("temp_dir", "temp"))
        if not temp_base.exists():
            temp_base.mkdir(parents=True, exist_ok=True)
            
        # タイムスタンプを含む一時ディレクトリ名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = temp_base / f"temp_{timestamp}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"一時ディレクトリを作成しました: {temp_dir}")
        return temp_dir

    def cleanup_temp_dir(self, temp_dir: Union[str, Path]) -> None:
        """
        一時ディレクトリを削除
        
        Args:
            temp_dir: 削除する一時ディレクトリ
        """
        temp_dir = Path(temp_dir)
        
        if not temp_dir.exists():
            logger.warning(f"削除対象の一時ディレクトリが存在しません: {temp_dir}")
            return
            
        shutil.rmtree(temp_dir)
        logger.debug(f"一時ディレクトリを削除しました: {temp_dir}")


# シングルトンインスタンス
storage_manager = StorageManager()