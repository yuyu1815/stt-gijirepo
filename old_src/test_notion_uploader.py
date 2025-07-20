import os
from notion_uploader import NotionUploader

def create_sample_lecture_note():
    """サンプルの講義ノートを作成する"""
    content = """# Webアプリケーション開発入門

## 1. HTMLの基礎

HTMLはWebページの構造を定義するマークアップ言語です。

### 主要なタグ

* `<html>`: HTML文書のルート要素
* `<head>`: メタデータを含むヘッダー部分
* `<body>`: 表示されるコンテンツ部分
* `<h1>` - `<h6>`: 見出し
* `<p>`: 段落
* `<a>`: リンク
* `<img>`: 画像

## 2. CSSの基礎

CSSはWebページのスタイルを定義するスタイルシート言語です。

### スタイルの適用方法

1. インラインスタイル
2. 内部スタイルシート
3. 外部スタイルシート

## 3. JavaScriptの基礎

JavaScriptはWebページに動的な機能を追加するためのプログラミング言語です。
"""
    
    # サンプルファイルを作成
    file_path = "sample_lecture_note.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return file_path

def test_upload_lecture_note():
    """講義ノートのアップロードをテストする"""
    # サンプルの講義ノートを作成
    file_path = create_sample_lecture_note()
    
    try:
        # NotionUploaderのインスタンス化
        uploader = NotionUploader()
        
        # 設定ファイルからデータベースIDを取得
        database_id = uploader.settings["notion"].get("database_id", "")
        
        # データベースIDが設定されているか確認
        if not database_id:
            print("エラー: settings.jsonにdatabase_idが設定されていません。")
            print("settings.jsonファイルを編集して、database_idを設定してください。")
            return
        
        # 講義ノートをアップロード
        result = uploader.upload_lecture_note_from_file(
            database_id, 
            file_path, 
            "webアプリケーション"
        )
        
        # 結果を表示
        if result["success"]:
            print("テスト成功: 講義ノートがNotionにアップロードされました。")
            print(f"URL: {result['url']}")
        else:
            print(f"テスト失敗: {result['message']}")
    
    finally:
        # テスト後にサンプルファイルを削除
        if os.path.exists(file_path):
            os.remove(file_path)

def test_direct_upload():
    """直接コンテンツをアップロードするテスト"""
    try:
        # NotionUploaderのインスタンス化
        uploader = NotionUploader()
        
        # 設定ファイルからデータベースIDを取得
        database_id = uploader.settings["notion"].get("database_id", "")
        
        # データベースIDが設定されているか確認
        if not database_id:
            print("エラー: settings.jsonにdatabase_idが設定されていません。")
            print("settings.jsonファイルを編集して、database_idを設定してください。")
            return
        
        # 直接コンテンツをアップロード
        title = "DB設計の基礎"
        content = """# DB設計の基礎

## 1. データベース設計の重要性

適切なデータベース設計は、アプリケーションのパフォーマンスと保守性に大きく影響します。

## 2. 正規化

正規化は、データの冗長性を減らし、データの整合性を向上させるプロセスです。

### 第一正規形 (1NF)
* 各列は原子的な値のみを含む
* 同じ種類のデータを複数列に繰り返さない
* 各行を一意に識別するキーがある

### 第二正規形 (2NF)
* 第一正規形を満たす
* 部分関数従属を持たない

### 第三正規形 (3NF)
* 第二正規形を満たす
* 推移的関数従属を持たない
"""
        
        # 講義ノートをアップロード
        result = uploader.upload_lecture_note(
            database_id, 
            title, 
            content, 
            "DB設計"
        )
        
        # 結果を表示
        if result["success"]:
            print("テスト成功: 講義ノートがNotionにアップロードされました。")
            print(f"URL: {result['url']}")
        else:
            print(f"テスト失敗: {result['message']}")
    
    except Exception as e:
        print(f"テスト中にエラーが発生しました: {str(e)}")

if __name__ == "__main__":
    print("=== 講義ノートアップロードのテスト ===")
    print("1. ファイルからのアップロードテスト")
    test_upload_lecture_note()
    
    print("\n2. 直接コンテンツのアップロードテスト")
    test_direct_upload()