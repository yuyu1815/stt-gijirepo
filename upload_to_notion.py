import argparse
import os
import sys
from notion_uploader import NotionUploader

def main():
    """
    議事録ファイルをNotionにアップロードするメインスクリプト
    """
    parser = argparse.ArgumentParser(description='議事録ファイルをNotionにアップロードする')
    parser.add_argument('--file', type=str, help='議事録ファイルのパス', required=True)
    parser.add_argument('--parent', type=str, help='Notionの親ページまたはデータベースID', required=True)
    parser.add_argument('--token-file', type=str, help='Notionトークンを含むファイルのパス（後方互換性のため）', default="settings.json")
    parser.add_argument('--max-blocks', type=int, default=100, help='最大ブロック数（Notionの制限は100）')
    parser.add_argument('--create-json', action='store_true', help='Notion用のJSONファイルを作成する')
    args = parser.parse_args()

    # 議事録ファイルの存在確認
    if not os.path.exists(args.file):
        print(f"エラー: 議事録ファイル '{args.file}' が見つかりません。")
        sys.exit(1)

    # トークンファイルの存在確認
    if not os.path.exists(args.token_file):
        print(f"エラー: トークンファイル '{args.token_file}' が見つかりません。")
        sys.exit(1)

    try:
        # NotionUploaderのインスタンスを作成
        # settings.jsonをデフォルトとして使用し、後方互換性のためにtoken_fileも渡す
        uploader = NotionUploader(settings_file="settings.json", token_file=args.token_file if args.token_file != "settings.json" else None)

        # 議事録をアップロード
        print(f"議事録ファイル '{args.file}' をNotionにアップロードしています...")
        result = uploader.upload_lecture_note_from_file(
            args.parent,
            args.file,
            None,  # subject_number
            args.max_blocks,
            args.create_json
        )

        # 結果の表示
        if result["success"]:
            print(f"成功: {result['message']}")
            print(f"ページURL: {result['url']}")
        else:
            print(f"失敗: {result['message']}")
            sys.exit(1)

    except Exception as e:
        print(f"エラー: 予期しない問題が発生しました: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
