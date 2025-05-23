import os
import json
import requests
import time
from datetime import datetime
from class_info_utils import get_class_info

class NotionUploader:
    def __init__(self, settings_file="settings.json", token_file=None):
        """
        Notionアップローダーの初期化

        Args:
            settings_file (str): 設定ファイルのパス
            token_file (str, optional): トークンファイルのパス（後方互換性のため）
        """
        self.settings = self._read_settings(settings_file)

        # 環境変数からトークンを取得（優先）
        self.token = os.environ.get("NOTION_TOKEN")

        # 環境変数が設定されていない場合は設定ファイルから取得
        if not self.token:
            self.token = self.settings["notion"]["token"]

            # トークンがプレースホルダーの場合は警告
            if self.token == "YOUR_NOTION_TOKEN":
                print("警告: Notion APIトークンが設定されていません。環境変数NOTION_TOKENを設定するか、settings.jsonを更新してください。")

        self.notion_url = os.environ.get("NOTION_URL") or self.settings["notion"].get("url", "")
        # database_idは環境変数から取得するか、urlから抽出する
        self.database_id = os.environ.get("NOTION_DATABASE_ID")
        if not self.database_id and self.notion_url:
            self.database_id = self.extract_notion_id(self.notion_url)

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        self.base_url = "https://api.notion.com/v1"

    def _read_settings(self, settings_file):
        """
        設定ファイルから設定を読み取る

        Args:
            settings_file (str): 設定ファイルのパス

        Returns:
            dict: 設定情報
        """
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
                return settings
        except Exception as e:
            raise Exception(f"設定ファイルの読み取りに失敗しました: {str(e)}")

    def get_database_structure(self, database_id):
        """
        データベースの構造（プロパティなど）を取得する

        Args:
            database_id (str): データベースID

        Returns:
            dict: データベースの構造情報
        """
        # APIリクエストの送信
        response = requests.get(
            f"{self.base_url}/databases/{database_id}",
            headers=self.headers
        )

        if response.status_code != 200:
            raise Exception(f"データベース情報の取得に失敗しました: {response.text}")

        database = response.json()

        # データベースの構造情報を整形
        structure = {
            "title": database.get("title", [{}])[0].get("plain_text", "無題のデータベース") if database.get("title") else "無題のデータベース",
            "properties": {}
        }

        # プロパティ情報を抽出
        for prop_name, prop_data in database.get("properties", {}).items():
            prop_type = prop_data.get("type", "unknown")
            structure["properties"][prop_name] = {
                "type": prop_type,
                "id": prop_data.get("id", "")
            }

            # プロパティタイプに応じた追加情報
            if prop_type == "select":
                options = []
                for option in prop_data.get("select", {}).get("options", []):
                    options.append({
                        "name": option.get("name", ""),
                        "color": option.get("color", "")
                    })
                structure["properties"][prop_name]["options"] = options
            elif prop_type == "multi_select":
                options = []
                for option in prop_data.get("multi_select", {}).get("options", []):
                    options.append({
                        "name": option.get("name", ""),
                        "color": option.get("color", "")
                    })
                structure["properties"][prop_name]["options"] = options
            elif prop_type == "relation":
                structure["properties"][prop_name]["database_id"] = prop_data.get("relation", {}).get("database_id", "")

        return structure

    def create_page(self, database_id, title, content, subject_number=None, class_period=None, class_date=None, max_blocks=100):
        """
        講義ノートをNotionデータベースに作成

        Args:
            database_id (str): データベースID
            title (str): 講義ノートのタイトル（科目名）
            content (str): 講義ノートの内容（マークダウン形式）
            subject_number (str, optional): 科目番号（選択肢リストから選択）
            class_period (int, optional): 時間割（何時間目の授業か）
            class_date (str, optional): 日付（授業の日次、YYYY-MM-DD形式）
            max_blocks (int): 最大ブロック数（Notionの制限は100）

        Returns:
            dict: 作成されたページの情報
        """
        # マークダウンをNotionブロックに変換
        all_blocks = self._markdown_to_blocks(content, None)  # すべてのブロックを取得

        # 最初の100ブロック（またはmax_blocks指定の数）を使用してページを作成
        first_blocks = all_blocks[:min(max_blocks, len(all_blocks))]
        remaining_blocks = all_blocks[min(max_blocks, len(all_blocks)):]

        # ページプロパティの設定
        properties = {
            "科目": {
                "title": [
                    {
                        "text": {
                            "content": title
                        }
                    }
                ]
            }
        }

        # 科目番号が指定されている場合は設定
        if subject_number:
            properties["科目番号"] = {
                "select": {
                    "name": subject_number
                }
            }

        # 時間割が指定されている場合は設定
        if class_period:
            properties["時間割"] = {
                "number": class_period
            }

        # 日付が指定されている場合は設定
        if class_date:
            properties["日付"] = {
                "date": {
                    "start": class_date
                }
            }

        # contextプロパティはNotionデータベースに存在しないため、コメントアウト
        # 長いテキストはリッチテキスト形式で設定するが、データベースに対応するプロパティが必要
        # properties["context"] = {
        #     "rich_text": [
        #         {
        #             "text": {
        #                 "content": content[:2000] if content else ""  # Notionの制限に合わせて最初の2000文字だけ
        #             }
        #         }
        #     ]
        # }

        # リクエストデータの作成
        data = {
            "parent": {"database_id": database_id},
            "properties": properties,
            "children": first_blocks
        }

        # APIリクエストの送信
        response = requests.post(
            f"{self.base_url}/pages",
            headers=self.headers,
            json=data
        )

        if response.status_code != 200:
            raise Exception(f"ページの作成に失敗しました: {response.text}")

        result = response.json()

        # 残りのブロックがある場合は、追加のリクエストで追加
        if remaining_blocks:
            page_id = result["id"]
            self._append_blocks(page_id, remaining_blocks, max_blocks)

        return result

    def _markdown_to_blocks(self, markdown_text, max_blocks=100):
        """
        マークダウンテキストをNotionブロックに変換

        Args:
            markdown_text (str): マークダウン形式のテキスト
            max_blocks (int): 最大ブロック数（Notionの制限は100）。Noneの場合は制限なし。

        Returns:
            list: Notionブロックのリスト
        """
        blocks = []
        lines = markdown_text.split("\n")
        i = 0

        # max_blocksがNoneの場合は、すべての行を処理
        limit = float('inf') if max_blocks is None else max_blocks

        # コードブロックの状態を追跡
        in_code_block = False
        code_content = ""
        code_language = ""
        code_block_line_count = 0
        MAX_CODE_BLOCK_LINES = 1000  # コードブロックの最大行数（安全策）

        # 太字のテキストを処理する関数
        def process_bold_text(text):
            """
            テキスト内の太字（**text**）を処理し、適切なrich_textオブジェクトのリストを返す
            テキストが長い場合は2000文字以下のチャンクに分割する

            Args:
                text (str): 処理するテキスト

            Returns:
                list: rich_textオブジェクトのリスト
            """
            MAX_CONTENT_LENGTH = 2000

            if "**" not in text:
                # 太字がない場合は単純なテキストを返す
                # 2000文字を超える場合は分割
                if len(text) <= MAX_CONTENT_LENGTH:
                    return [{"type": "text", "text": {"content": text}}]
                else:
                    rich_text_list = []
                    for i in range(0, len(text), MAX_CONTENT_LENGTH):
                        chunk = text[i:i+MAX_CONTENT_LENGTH]
                        rich_text_list.append({"type": "text", "text": {"content": chunk}})
                    return rich_text_list

            rich_text_list = []
            segments = []

            # テキストを**で分割
            parts = text.split("**")

            # 分割されたパーツを処理
            for i, part in enumerate(parts):
                if part:  # 空でない場合
                    # 偶数インデックスは通常テキスト、奇数インデックスは太字
                    is_bold = i % 2 == 1

                    # 長いテキストを分割
                    if len(part) <= MAX_CONTENT_LENGTH:
                        rich_text_list.append({
                            "type": "text", 
                            "text": {"content": part},
                            "annotations": {"bold": is_bold}
                        })
                    else:
                        for j in range(0, len(part), MAX_CONTENT_LENGTH):
                            chunk = part[j:j+MAX_CONTENT_LENGTH]
                            rich_text_list.append({
                                "type": "text", 
                                "text": {"content": chunk},
                                "annotations": {"bold": is_bold}
                            })

            return rich_text_list

        while i < len(lines) and len(blocks) < limit:
            line = lines[i].strip()

            # コードブロックの処理
            if line.startswith("```"):
                if not in_code_block:
                    # コードブロックの開始
                    in_code_block = True
                    code_content = ""
                    code_block_line_count = 0  # 行数カウンタをリセット
                    # 言語の取得（```python など）
                    code_language = line[3:].strip()
                    # 言語が指定されていない場合や無効な言語の場合は "plain text" を使用
                    if not code_language or code_language == "```":
                        code_language = "plain text"
                    i += 1
                    continue
                else:
                    # コードブロックの終了
                    in_code_block = False

                    # コードコンテンツを2000文字以下のチャンクに分割
                    MAX_CONTENT_LENGTH = 2000
                    code_chunks = []

                    for j in range(0, len(code_content), MAX_CONTENT_LENGTH):
                        code_chunks.append(code_content[j:j+MAX_CONTENT_LENGTH])

                    # 各チャンクをリッチテキストとして追加
                    rich_text_chunks = []
                    for chunk in code_chunks:
                        rich_text_chunks.append({"type": "text", "text": {"content": chunk}})

                    blocks.append({
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": rich_text_chunks,
                            "language": code_language if code_language else "plain text"
                        }
                    })
                    i += 1
                    continue

            if in_code_block:
                # コードブロック内の行を追加
                code_content += line + "\n"
                code_block_line_count += 1

                # 安全策：コードブロックの行数が最大値を超えた場合、強制的に終了
                if code_block_line_count >= MAX_CODE_BLOCK_LINES:
                    print(f"警告: コードブロックが最大行数（{MAX_CODE_BLOCK_LINES}行）に達しました。強制的に終了します。")
                    in_code_block = False

                    # コードコンテンツを2000文字以下のチャンクに分割
                    MAX_CONTENT_LENGTH = 2000
                    code_chunks = []

                    for j in range(0, len(code_content), MAX_CONTENT_LENGTH):
                        code_chunks.append(code_content[j:j+MAX_CONTENT_LENGTH])

                    # 各チャンクをリッチテキストとして追加
                    rich_text_chunks = []
                    for chunk in code_chunks:
                        rich_text_chunks.append({"type": "text", "text": {"content": chunk}})

                    blocks.append({
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": rich_text_chunks,
                            "language": code_language if code_language else "plain text"
                        }
                    })

                i += 1
                continue

            # 空行はスキップ
            if not line:
                i += 1
                continue

            # 見出しの処理
            if line.startswith("# "):
                blocks.append({
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": process_bold_text(line[2:])
                    }
                })
            elif line.startswith("## "):
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": process_bold_text(line[3:])
                    }
                })
            elif line.startswith("### "):
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": process_bold_text(line[4:])
                    }
                })

            # リストの処理
            elif line.startswith("- ") or line.startswith("* "):
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": process_bold_text(line[2:])
                    }
                })
            elif line.startswith("> "):
                blocks.append({
                    "object": "block",
                    "type": "quote",
                    "quote": {
                        "rich_text": process_bold_text(line[2:])
                    }
                })
            # 番号付きリストの処理（1. 2. など）
            elif line[0].isdigit() and len(line) > 1 and line[1] == '.' and line[2] == ' ':
                blocks.append({
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {
                        "rich_text": process_bold_text(line[3:])
                    }
                })
            # 通常の段落
            else:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": process_bold_text(line)
                    }
                })

            i += 1

        print(f"現在のノード数: {len(blocks)}")
        return blocks

    def _append_blocks(self, page_id, blocks, max_blocks=100):
        """
        既存のNotionページにブロックを追加

        Args:
            page_id (str): ページID
            blocks (list): 追加するブロックのリスト
            max_blocks (int): 1回のリクエストで追加する最大ブロック数（Notionの制限は100）

        Returns:
            None
        """
        # ブロックを最大max_blocks個ずつに分割して追加
        for i in range(0, len(blocks), max_blocks):
            batch = blocks[i:i + max_blocks]

            # APIリクエストの送信
            response = requests.patch(
                f"{self.base_url}/blocks/{page_id}/children",
                headers=self.headers,
                json={"children": batch}
            )

            if response.status_code != 200:
                raise Exception(f"ブロックの追加に失敗しました: {response.text}")

            print(f"ブロックを追加しました（{i+1}～{i+len(batch)}）")

            # APIレート制限を考慮して少し待機
            time.sleep(0.5)

    def upload_lecture_note(self, database_id, title, content, subject_number=None, class_period=None, class_date=None, max_blocks=100):
        """
        講義ノートをNotionにアップロード

        Args:
            database_id (str): データベースID
            title (str): 講義ノートのタイトル（科目名）
            content (str): 講義ノートの内容（マークダウン形式）
            subject_number (str, optional): 科目番号（選択肢リストから選択）
            class_period (int, optional): 時間割（何時間目の授業か）
            class_date (str, optional): 日付（授業の日次、YYYY-MM-DD形式）
            max_blocks (int): 最大ブロック数（Notionの制限は100）

        Returns:
            dict: アップロード結果
        """
        try:
            # Notionにページを作成
            result = self.create_page(database_id, title, content, subject_number, class_period, class_date, max_blocks)

            return {
                "success": True,
                "message": f"講義ノート「{title}」をNotionにアップロードしました",
                "page_id": result["id"],
                "url": result["url"]
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"講義ノートのアップロードに失敗しました: {str(e)}"
            }

    def upload_minutes(self, file_path, database_id, max_blocks=100, create_json=True):
        """
        議事録ファイルをNotionにアップロード

        Args:
            file_path (str): 議事録ファイルのパス
            database_id (str): データベースID
            max_blocks (int): 最大ブロック数（Notionの制限は100）
            create_json (bool): Notion用のJSONファイルを作成するかどうか

        Returns:
            dict: アップロード結果
        """
        # upload_lecture_note_from_fileを呼び出す（互換性のため）
        return self.upload_lecture_note_from_file(database_id, file_path, None, max_blocks, create_json)

    def upload_lecture_note_from_file(self, database_id, file_path, subject_number=None, max_blocks=100, create_json=True):
        """
        ファイルから講義ノートをNotionにアップロード

        Args:
            database_id (str): データベースID
            file_path (str): 講義ノートファイルのパス
            subject_number (str, optional): 科目番号（選択肢リストから選択）
            max_blocks (int): 最大ブロック数（Notionの制限は100）
            create_json (bool): Notion用のJSONファイルを作成するかどうか

        Returns:
            dict: アップロード結果
        """
        try:
            # ファイルの読み込み
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # get_class_info関数を使用して授業情報を取得
            class_info = get_class_info(file_path)

            # 科目情報を正しい形式で設定
            class_name = class_info.get("name", "不明")
            datetime_str = class_info.get("datetime", "")

            # 科目番号を設定（科目名から選択）
            if not subject_number:
                # 科目名から適切な選択肢を選ぶ
                subject_options = [
                    "Webアプリケーション演習",
                    "データベース開発演習",
                    "専攻Ⅰ(データサイエンス)",
                    "ＡＩプログラミング演習Ⅰ",
                    "UML",
                    "情報処理講座Ⅱ",
                    "IoT演習Ⅰ",
                    "ビジネスプレゼン演習Ⅰ",
                    "Javascript＆AjaxⅠ",
                    "webアプリケーション"
                ]

                # 最も一致する科目名を探す
                best_match = None
                for option in subject_options:
                    if option.lower() in class_name.lower() or class_name.lower() in option.lower():
                        best_match = option
                        break

                # 一致するものがなければデフォルト値を使用
                subject_number = best_match if best_match else "情報処理講座Ⅱ"

            # 時間割（何時間目）を設定
            class_period = None
            period_number = None

            # 日付を設定
            class_date = None

            if datetime_str:
                # 日付文字列から年月日を抽出してYYYY-MM-DD形式に変換
                import re
                date_match = re.search(r'(\d{4})年(\d{2})月(\d{2})日', datetime_str)
                if date_match:
                    year = date_match.group(1)
                    month = date_match.group(2)
                    day = date_match.group(3)
                    class_date = f"{year}-{month}-{day}"

                    # 日付から曜日を計算
                    try:
                        year_int = int(year)
                        month_int = int(month)
                        day_int = int(day)
                        date_obj = datetime(year_int, month_int, day_int)
                        weekday = date_obj.weekday()
                        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
                        day_of_week = f"({weekday_names[weekday]})"
                    except Exception as e:
                        print(f"曜日の計算エラー: {str(e)}")
                        day_of_week = ""

                # 時間から何時間目かを推定
                time_match = re.search(r'(\d{2}):(\d{2})', datetime_str)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2))
                    time_minutes = hour * 60 + minute

                    # 授業時間帯の定義（分単位）
                    class_times = [
                        {"period": "1限目", "number": 1, "start": 9*60+30},  # 9:30
                        {"period": "2限目", "number": 2, "start": 11*60+10}, # 11:10
                        {"period": "3限目", "number": 3, "start": 13*60+40}, # 13:40
                        {"period": "4限目", "number": 4, "start": 15*60+20}  # 15:20
                    ]

                    # 最も近い授業時間帯を見つける
                    closest_period = None
                    period_number = None
                    min_diff = float('inf')

                    for class_time in class_times:
                        diff = abs(time_minutes - class_time["start"])
                        if diff < min_diff:
                            min_diff = diff
                            closest_period = class_time["period"]
                            period_number = class_time["number"]

                    class_period = period_number

            # 科目タイトルを生成
            month_day = ""
            if class_date:
                # class_dateからMM/DDを抽出
                date_parts = class_date.split("-")
                if len(date_parts) == 3:
                    month_day = f"{date_parts[1]}/{date_parts[2]}"

            period_str = f"{class_period}限目" if class_period else ""
            title = class_name  # 科目名をタイトルとして使用

            if title == "":
                # 情報が取得できなかった場合はファイル名を使用
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                title = base_name

            # Notion用のJSONファイルを作成
            if create_json:
                # 出力ディレクトリの設定を読み込む
                output_dir = "."  # デフォルトは現在のディレクトリ
                try:
                    with open('settings.json', 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                        if "output" in settings:
                            if "json_directory" in settings["output"]:
                                output_dir = settings["output"]["json_directory"]
                            elif "directory" in settings["output"]:
                                output_dir = settings["output"]["directory"]
                            # ディレクトリが存在しない場合は作成
                            if not os.path.exists(output_dir):
                                os.makedirs(output_dir)
                except Exception as e:
                    print(f"警告: 出力ディレクトリの設定の読み込みに失敗しました: {str(e)}")

                # ファイル名のみを取得
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                json_file_path = os.path.join(output_dir, f"{base_name}_notion.json")

                json_data = {
                    "科目": title,
                    "科目番号": subject_number,
                    "時間割": class_period,
                    "日付": class_date,
                    "context": content
                }

                with open(json_file_path, "w", encoding="utf-8") as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
                print(f"Notion用のJSONファイルを {json_file_path} に保存しました。")

            # Notionにアップロード
            return self.upload_lecture_note(database_id, title, content, subject_number, class_period, class_date, max_blocks)

        except Exception as e:
            return {
                "success": False,
                "message": f"講義ノートのアップロードに失敗しました: {str(e)}"
            }

    def extract_notion_id(self, value):
        """
        NotionのURLまたはID文字列からID部分を抽出する

        Args:
            value (str): NotionのURLまたはID文字列

        Returns:
            str: 抽出されたID
        """
        if not value:
            return value

        import re
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

    def upload_lecture_note_from_json(self, database_id, json_file_path):
        """
        JSONファイルから講義ノートをNotionにアップロード

        Args:
            database_id (str): データベースID
            json_file_path (str): JSONファイルのパス

        Returns:
            dict: アップロード結果
        """
        try:
            # JSONファイルの読み込み
            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 必須フィールドの確認
            if "科目" not in data:
                return {
                    "success": False,
                    "message": "JSONファイルに「科目」フィールドがありません"
                }

            # JSONファイルにURLが含まれている場合は、そのURLからデータベースIDを抽出
            if "url" in data or "database_url" in data:
                url = data.get("url") or data.get("database_url")
                extracted_db_id = self.extract_notion_id(url)
                if extracted_db_id:
                    database_id = extracted_db_id
                    print(f"JSONファイルに指定されたURL '{url}' からデータベースID '{database_id}' を抽出しました。")

            title = data["科目"]
            subject_number = data.get("科目番号")
            class_period = data.get("時間割")  # 時間割（何時間目）
            class_date = data.get("日付")      # 日付（YYYY-MM-DD形式）
            content = data.get("content", "") or data.get("context", "")  # コンテンツがあれば取得（contentまたはcontext）

            # 科目番号が指定されていない場合、デフォルト値を設定
            if not subject_number:
                subject_number = "情報処理講座Ⅱ"  # デフォルト値

            # Notionにアップロード
            result = self.create_page(database_id, title, content, subject_number, class_period, class_date)

            return {
                "success": True,
                "message": f"講義ノート「{title}」をNotionにアップロードしました",
                "page_id": result["id"],
                "url": result["url"]
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"JSONからの講義ノートのアップロードに失敗しました: {str(e)}"
            }

# コマンドラインから実行する場合
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="講義ノートをNotionにアップロードするツール")
    parser.add_argument("file", help="アップロードする講義ノートファイルのパス")
    parser.add_argument("--database", "-d", help="NotionデータベースID（settings.jsonに設定されていない場合）")
    parser.add_argument("--subject", "-s", choices=["webアプリケーション", "DB設計"], help="科目番号")
    parser.add_argument("--settings", default="settings.json", help="設定ファイルのパス")
    parser.add_argument("--json", "-j", action="store_true", help="入力ファイルをJSON形式として処理する")
    parser.add_argument("--max-blocks", type=int, default=100, help="最大ブロック数（Notionの制限は100）")
    parser.add_argument("--create-json", action="store_true", help="Notion用のJSONファイルを作成する")

    args = parser.parse_args()

    # NotionUploaderのインスタンス化
    uploader = NotionUploader(settings_file=args.settings)

    # データベースIDの取得
    database_id = args.database
    if not database_id:
        # すでにuploader.database_idが設定されている場合はそれを使用
        if uploader.database_id:
            database_id = uploader.database_id
        else:
            print("エラー: データベースIDが指定されていません。コマンドラインで--databaseオプションを使用するか、NotionのURLを設定してください。")
            exit(1)

    # ファイルをアップロード
    if args.json:
        # JSONファイルとして処理
        result = uploader.upload_lecture_note_from_json(database_id, args.file)
    else:
        # 通常のマークダウンファイルとして処理
        result = uploader.upload_lecture_note_from_file(
            database_id, 
            args.file, 
            args.subject, 
            args.max_blocks, 
            args.create_json
        )

    # 結果を表示
    if result["success"]:
        print(result["message"])
        print(f"URL: {result['url']}")
    else:
        print(result["message"])
