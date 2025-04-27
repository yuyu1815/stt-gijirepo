import argparse
import os
import sys
import json
from notion_uploader import NotionUploader
import re

def main():
    """
    Notionのデータベースやページの構造を取得するメインスクリプト
    """
    parser = argparse.ArgumentParser(description='Notionのデータベースやページの構造を取得する')
    parser.add_argument('--database', type=str, help='データベースIDを指定してデータベースの構造を取得', default=None)
    parser.add_argument('--page', type=str, help='ページIDを指定してページのプロパティを取得', default=None)
    parser.add_argument('--blocks', type=str, help='ページIDまたはブロックIDを指定してブロック内容を取得', default=None)
    parser.add_argument('--url', type=str, help='NotionのデータベースまたはページのURLを指定', default=None)
    parser.add_argument('--recursive', action='store_true', help='ブロック内容を再帰的に取得する（--blocksと共に使用）')
    parser.add_argument('--output', type=str, help='結果を保存するJSONファイルのパス', default=None)
    parser.add_argument('--token-file', type=str, help='Notionトークンを含むファイルのパス', default="settings.json")
    args = parser.parse_args()

    # 少なくとも1つのオプションが指定されていることを確認
    if not (args.database or args.page or args.blocks or args.url):
        parser.print_help()
        print("\nエラー: --database、--page、--blocks、または--urlのいずれかを指定してください。")
        sys.exit(1)

    # トークンファイルの存在確認
    if not os.path.exists(args.token_file):
        print(f"エラー: トークンファイル '{args.token_file}' が見つかりません。")
        sys.exit(1)

    try:
        # NotionUploaderのインスタンスを作成
        uploader = NotionUploader(settings_file=args.token_file)
        result = None

        # データベース構造の取得
        if args.database:
            db_id = extract_notion_id(args.database, id_type='database')
            if len(db_id.replace("-", "")) == 32:
                pass  # UUID形式はそのまま
            else:
                print("エラー: 無効なデータベースIDです。NotionのURLまたはUUID形式のIDを指定してください。")
                sys.exit(1)
            print(f"データベース '{args.database}' の構造を取得しています...")
            result = uploader.get_database_structure(db_id)
            print_database_structure(result)

        # ページプロパティの取得
        if args.page:
            page_id = extract_notion_id(args.page, id_type='page')
            print(f"ページ '{args.page}' のプロパティを取得しています...")
            result = uploader.get_page_properties(page_id)
            print_page_properties(result)

        # ブロック内容の取得
        if args.blocks:
            block_id = extract_notion_id(args.blocks, id_type='block')
            print(f"ブロック '{args.blocks}' の内容を取得しています...")
            result = uploader.get_block_children(block_id, recursive=args.recursive)
            print_blocks(result, indent=0)

        # --urlが指定された場合は自動判別
        if args.url:
            # URLからIDを抽出
            notion_id = extract_notion_id(args.url)
            # URLがデータベースかページかを判定（簡易判定: /database/含むか）
            if "/database/" in args.url or args.url.startswith("https://www.notion.so/" ) and ("?v=" in args.url or "/table?" in args.url):
                db_id = notion_id
                print(f"データベースURL '{args.url}' の構造を取得しています...")
                result = uploader.get_database_structure(db_id)
                print_database_structure(result)
            else:
                page_id = notion_id
                print(f"ページURL '{args.url}' のプロパティを取得しています...")
                result = uploader.get_page_properties(page_id)
                print_page_properties(result)

        # 結果をJSONファイルに保存
        if args.output and result:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"結果を '{args.output}' に保存しました。")

    except Exception as e:
        print(f"エラー: {str(e)}")
        sys.exit(1)

def print_database_structure(structure):
    """
    データベース構造を整形して表示
    """
    # 整形前のデータを表示
    print("\n=== 整形前のデータベース構造 ===")
    print(json.dumps(structure, ensure_ascii=False, indent=2))

    print("\n=== データベース構造 ===")
    print(f"タイトル: {structure['title']}")
    print("\nプロパティ:")
    for prop_name, prop_data in structure['properties'].items():
        prop_type = prop_data['type']
        print(f"  - {prop_name} ({prop_type})")

        # 選択肢タイプの場合は選択肢一覧を表示
        if prop_type in ['select', 'multi_select'] and 'options' in prop_data:
            print("    選択肢:")
            for option in prop_data['options']:
                print(f"      * {option['name']} ({option['color']})")

        # リレーションタイプの場合は関連データベースIDを表示
        if prop_type == 'relation' and 'database_id' in prop_data:
            print(f"    関連データベース: {prop_data['database_id']}")

def print_page_properties(properties):
    """
    ページプロパティを整形して表示
    """
    # 整形前のデータを表示
    print("\n=== 整形前のページプロパティ ===")
    print(json.dumps(properties, ensure_ascii=False, indent=2))

    print("\n=== ページプロパティ ===")
    for prop_name, prop_data in properties.items():
        prop_type = prop_data['type']
        prop_value = prop_data['value']

        # リストの場合は整形
        if isinstance(prop_value, list):
            if prop_value:
                value_str = ", ".join([str(v) for v in prop_value])
            else:
                value_str = "(空)"
        else:
            value_str = str(prop_value) if prop_value is not None else "(空)"

        print(f"  - {prop_name} ({prop_type}): {value_str}")

def print_blocks(blocks, indent=0):
    """
    ブロック内容を整形して表示（再帰的）
    """
    if indent == 0:
        # 整形前のデータを表示（最初の呼び出し時のみ）
        print("\n=== 整形前のブロック内容 ===")
        print(json.dumps(blocks, ensure_ascii=False, indent=2))

        print("\n=== ブロック内容 ===")

    for block in blocks:
        block_type = block['type']
        indent_str = "  " * indent

        # ブロックタイプに応じた表示
        if 'content' in block:
            content = block['content']
            if block_type == 'code':
                language = block.get('language', 'plain_text')
                print(f"{indent_str}- {block_type} ({language}):")
                code_lines = content.split('\n')
                for line in code_lines:
                    print(f"{indent_str}  {line}")
            else:
                print(f"{indent_str}- {block_type}: {content}")
        elif block_type == 'image':
            url = block.get('url', '(URL不明)')
            print(f"{indent_str}- {block_type}: {url}")
        elif block_type == 'table':
            width = block.get('table_width', 0)
            has_col_header = block.get('has_column_header', False)
            has_row_header = block.get('has_row_header', False)
            print(f"{indent_str}- {block_type}: 幅={width}, 列ヘッダー={has_col_header}, 行ヘッダー={has_row_header}")
        else:
            print(f"{indent_str}- {block_type}")

        # 子ブロックがある場合は再帰的に表示
        if 'children' in block and block['children']:
            print_blocks(block['children'], indent + 1)

def extract_notion_id(value, id_type=None):
    """
    NotionのURLまたはID文字列からID部分を抽出する
    id_type: 'database', 'page', 'block' など用途でヒントを与える（未使用可）
    """
    if not value:
        return value
    # UUID形式（32桁英数字、ハイフン有無）
    uuid_pattern = r"[0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    # Notion URLからID抽出
    match = re.search(uuid_pattern, value.replace("-", ""))
    if match:
        # ハイフン無し32桁 or ハイフン付きUUID
        raw_id = match.group(0)
        # ハイフン無しならハイフン付きに変換（標準UUIDフォーマット）
        if len(raw_id) == 32:
            # 標準UUIDフォーマット: 8-4-4-4-12
            return f"{raw_id[0:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:32]}"
        return raw_id
    # database_xxx形式
    if value.startswith("database_"):
        return value[len("database_"):]
    return value

if __name__ == "__main__":
    main()
