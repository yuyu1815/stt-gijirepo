import os
import sys
import shutil
import subprocess
import platform

def main():
    """
    upload_and_transcribe.pyを.exeファイルに変換し、必須ファイルを出力ディレクトリにコピーするスクリプト
    """
    print("upload_and_transcribe.pyを.exeファイルに変換しています...")
    
    # PyInstallerを使用してupload_and_transcribe.pyを.exeファイルに変換
    # --onefile: 1つの.exeファイルにまとめる
    # --name: 出力ファイル名
    # --noconsole: コンソールウィンドウを表示しない（GUIアプリの場合）
    # --add-data: 追加のデータファイルを含める
    pyinstaller_cmd = [
        "pyinstaller",
        "--onefile",
        "--name", "upload_and_transcribe",
        "upload_and_transcribe.py"
    ]
    
    # コマンドを実行
    subprocess.run(pyinstaller_cmd, check=True)
    
    print(".exeファイルの作成が完了しました。")
    
    # 出力ディレクトリのパス
    dist_dir = os.path.join(os.getcwd(), "dist")
    
    # 必須ファイルをコピー
    copy_required_files(dist_dir)
    
    print("すべての処理が完了しました。")
    print(f"出力ディレクトリ: {dist_dir}")

def copy_required_files(dist_dir):
    """
    必須ファイルを出力ディレクトリにコピーする関数
    
    Args:
        dist_dir (str): 出力ディレクトリのパス
    """
    print("必須ファイルをコピーしています...")
    
    # コピーするファイルとディレクトリのリスト
    files_to_copy = [
        "settings.json",
        "notion_uploader.py",
        "class_info_utils.py",
        "lang_utils.py"
    ]
    
    dirs_to_copy = [
        "PROMPT"
    ]
    
    # ファイルをコピー
    for file in files_to_copy:
        if os.path.exists(file):
            print(f"コピー中: {file}")
            shutil.copy2(file, os.path.join(dist_dir, file))
        else:
            print(f"警告: ファイル {file} が見つかりません。")
    
    # ディレクトリをコピー
    for dir_name in dirs_to_copy:
        if os.path.exists(dir_name) and os.path.isdir(dir_name):
            dest_dir = os.path.join(dist_dir, dir_name)
            print(f"コピー中: {dir_name}/")
            
            # ディレクトリが既に存在する場合は削除
            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir)
            
            # ディレクトリをコピー
            shutil.copytree(dir_name, dest_dir)
        else:
            print(f"警告: ディレクトリ {dir_name} が見つかりません。")
    
    # 出力ディレクトリとtempディレクトリを作成
    os.makedirs(os.path.join(dist_dir, "output"), exist_ok=True)
    os.makedirs(os.path.join(dist_dir, "temp"), exist_ok=True)
    os.makedirs(os.path.join(dist_dir, "temp_aac"), exist_ok=True)
    
    print("必須ファイルのコピーが完了しました。")

if __name__ == "__main__":
    main()