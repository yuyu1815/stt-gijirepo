import json
import os
import re
from datetime import datetime

def get_class_info(file_path):
    """ファイル名から授業情報を取得する関数"""
    # settings.jsonから時間割を読み込む
    try:
        with open('settings.json', 'r', encoding='utf-8') as f:
            settings = json.load(f)
            schedule = settings.get('schedule', {})
    except Exception as e:
        print(f"時間割の読み込みに失敗しました: {str(e)}")
        # 読み込みに失敗した場合はデフォルト値を使用
        schedule = {}

    # ファイル名を取得
    filename = os.path.basename(file_path)

    # 日付と時間を抽出する正規表現パターン
    # 例: "20240520_0930.mp3" や "2024年05月20日 09:30～11:00.mp3" などのパターンに対応
    date_time_pattern = re.compile(r'(\d{4})年(\d{2})月(\d{2})日\s+(\d{2}):(\d{2})～(\d{2}):(\d{2})')

    # 年-月-日 時間-分-秒.mp3 形式のパターン (例: "2025-04-14 13-35-31.mp3")
    new_date_time_pattern = re.compile(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2})-(\d{2})-(\d{2})')

    # 日付と時間が含まれているか確認
    date_time_match = date_time_pattern.search(filename)

    # 新しいフォーマットでの日付と時間の確認
    if not date_time_match:
        date_time_match = new_date_time_pattern.search(filename)
    if date_time_match:
        year = date_time_match.group(1)
        month = date_time_match.group(2)
        day = date_time_match.group(3)
        start_hour = date_time_match.group(4)
        start_min = date_time_match.group(5)

        # 新しいフォーマットかどうかを確認
        is_new_format = new_date_time_pattern.search(filename) is not None

        if is_new_format:
            # 新しいフォーマットの場合は秒も取得
            seconds = date_time_match.group(6)

            # 日付と時間の文字列を作成
            date_str = f"{year}年{month}月{day}日"
            time_str = f"{start_hour}:{start_min}:{seconds}"
            datetime_str = f"{date_str} {time_str}"
        else:
            # 元のフォーマットの場合は終了時間も取得
            end_hour = date_time_match.group(6)
            end_min = date_time_match.group(7)

            # 日付と時間の文字列を作成
            date_str = f"{year}年{month}月{day}日"
            time_str = f"{start_hour}:{start_min}～{end_hour}:{end_min}"
            datetime_str = f"{date_str} {time_str}"

        # 開始時間を数値に変換（比較用）
        start_time_minutes = int(start_hour) * 60 + int(start_min)

        # 授業時間帯の定義（分単位）
        class_times = [
            {"period": "1限", "start": 9*60+30},  # 9:30
            {"period": "2限", "start": 11*60+10}, # 11:10
            {"period": "3限", "start": 13*60+40}, # 13:40
            {"period": "4限", "start": 15*60+20}  # 15:20
        ]

        # 最も近い授業時間帯を見つける
        closest_period = None
        min_diff = float('inf')

        for class_time in class_times:
            diff = abs(start_time_minutes - class_time["start"])
            if diff < min_diff:
                min_diff = diff
                closest_period = class_time["period"]

        # 日付から曜日を計算する
        try:
            # 年月日を整数に変換
            year_int = int(year)
            month_int = int(month)
            day_int = int(day)

            # datetimeオブジェクトを作成
            date_obj = datetime(year_int, month_int, day_int)

            # 曜日を取得（0:月曜日, 1:火曜日, ..., 6:日曜日）
            weekday = date_obj.weekday()

            # 曜日の日本語名に変換
            weekday_names = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
            day_of_week = weekday_names[weekday]

            # 土曜日と日曜日の場合は授業がないため、デフォルト値を返す
            if weekday >= 5:  # 5:土曜日, 6:日曜日
                print(f"注意: {day_of_week}は授業がありません")
                return {"name": "不明", "teacher": "不明", "datetime": datetime_str}
        except (ValueError, IndexError) as e:
            print(f"日付の解析エラー: {e}")
            return {"name": "不明", "teacher": "不明", "datetime": datetime_str}

        # 曜日と時限から授業情報を取得
        if day_of_week in schedule and closest_period in schedule[day_of_week]:
            class_info = schedule[day_of_week][closest_period].copy()
            class_info["datetime"] = datetime_str
            return class_info

    # 授業変更を示す正規表現パターン
    # 例: "変更_新しい授業名" や "変更：新しい授業名" などのパターンに対応
    change_pattern = re.compile(r'変更[_:：\s]+(.*?)(\.[^.]+$|\s|$)')
    change_match = change_pattern.search(filename)
    if change_match:
        class_name = change_match.group(1).strip()
        return {"name": class_name, "teacher": "不明", "datetime": "不明"}

    # 科目名を直接含むファイル名の処理
    # 例: "科目名_20240520.mp3" や "科目名.mp3" などのパターンに対応
    for day_of_week, periods in schedule.items():
        for period, class_info in periods.items():
            class_name = class_info.get("name", "")
            if class_name and class_name in filename:
                result = class_info.copy()
                result["datetime"] = "不明"
                return result

    # 情報が取得できなかった場合はデフォルト値を返す
    return {"name": "不明", "teacher": "不明", "datetime": "不明"}