"""
pytestの設定ファイル

このファイルはpytestによって自動的に読み込まれ、テスト環境の設定に使用されます。
"""
import sys
import os
from pathlib import Path
import pytest

# プロジェクトルートをPythonパスに追加
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# カレントディレクトリをプロジェクトルートに設定
os.chdir(Path(__file__).parent)

# pytestのコレクションフックを追加
def pytest_configure(config):
    """
    pytestの設定を行うフック関数

    Args:
        config: pytestの設定オブジェクト
    """
    # テストディレクトリをPythonパスに追加
    test_dir = Path(__file__).parent / "src" / "tests"
    if str(test_dir) not in sys.path:
        sys.path.insert(0, str(test_dir))

# pytestのコレクションフックを追加
def pytest_collection_modifyitems(config, items):
    """
    テスト項目のコレクションを修正するフック関数

    Args:
        config: pytestの設定オブジェクト
        items: 収集されたテスト項目のリスト
    """
    # テスト項目が空の場合は、警告を表示
    if not items:
        print("警告: テスト項目が見つかりませんでした。")
        print(f"現在のPythonパス: {sys.path}")
        print(f"現在のディレクトリ: {os.getcwd()}")
