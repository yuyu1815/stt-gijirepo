"""
授業情報サービス

このモジュールは、ファイル名から日付・時間情報を抽出し、曜日と時限から授業情報（科目名、教員名）を取得するサービスを提供します。
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..infrastructure.config import config_manager
from ..infrastructure.logger import logger
from ..infrastructure.storage import storage_manager


class ClassInfoService:
    """授業情報サービスクラス"""

    def __init__(self):
        """初期化"""
        self.schedule_path = config_manager.get("class_info.schedule_path", "config/schedule.json")
        self.schedule = self._load_schedule()

    def _load_schedule(self) -> Dict:
        """
        授業スケジュールを読み込む
        
        Returns:
            授業スケジュール辞書
        """
        schedule_path = Path(self.schedule_path)
        
        if not schedule_path.exists():
            logger.warning(f"授業スケジュールファイルが見つかりません: {schedule_path}")
            # デフォルトのスケジュールを作成
            default_schedule = self._create_default_schedule()
            
            # ディレクトリが存在しない場合は作成
            if not schedule_path.parent.exists():
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                
            # デフォルトスケジュールを保存
            with open(schedule_path, "w", encoding="utf-8") as f:
                json.dump(default_schedule, f, ensure_ascii=False, indent=2)
                
            logger.info(f"デフォルトの授業スケジュールを作成しました: {schedule_path}")
            return default_schedule
            
        try:
            with open(schedule_path, "r", encoding="utf-8") as f:
                schedule = json.load(f)
                
            logger.info(f"授業スケジュールを読み込みました: {schedule_path}")
            return schedule
        except Exception as e:
            logger.error(f"授業スケジュールの読み込みに失敗しました: {e}")
            return self._create_default_schedule()

    def _create_default_schedule(self) -> Dict:
        """
        デフォルトの授業スケジュールを作成
        
        Returns:
            デフォルトの授業スケジュール辞書
        """
        # 曜日
        days = ["月", "火", "水", "木", "金", "土", "日"]
        
        # 時限
        periods = ["1", "2", "3", "4", "5", "6", "7"]
        
        # デフォルトスケジュール
        schedule = {}
        
        for day in days:
            schedule[day] = {}
            for period in periods:
                schedule[day][period] = {
                    "subject": f"{day}曜{period}限の授業",
                    "lecturer": f"{day}曜{period}限の講師",
                    "room": f"{day}曜{period}限の教室",
                    "notes": ""
                }
                
        # 特別な授業や休講情報
        schedule["special"] = {}
        
        return schedule

    def get_class_info_from_filename(self, file_path: Union[str, Path]) -> Dict:
        """
        ファイル名から授業情報を取得
        
        Args:
            file_path: ファイルパス
            
        Returns:
            授業情報の辞書
        """
        file_path = Path(file_path)
        filename = file_path.stem
        
        # 日付情報を抽出
        date_info = self._extract_date_from_filename(filename)
        
        if not date_info:
            logger.warning(f"ファイル名から日付情報を抽出できませんでした: {filename}")
            return {
                "subject": "不明",
                "lecturer": "不明",
                "date": None,
                "day_of_week": None,
                "period": None
            }
            
        # 曜日を取得
        date = date_info["date"]
        day_of_week = self._get_day_of_week(date)
        
        # 時限を抽出
        period = self._extract_period_from_filename(filename)
        
        if not period:
            logger.warning(f"ファイル名から時限情報を抽出できませんでした: {filename}")
            return {
                "subject": "不明",
                "lecturer": "不明",
                "date": date,
                "day_of_week": day_of_week,
                "period": None
            }
            
        # 授業情報を取得
        class_info = self._get_class_info(date, day_of_week, period)
        
        # 結果を返す
        return {
            "subject": class_info.get("subject", "不明"),
            "lecturer": class_info.get("lecturer", "不明"),
            "room": class_info.get("room", "不明"),
            "date": date,
            "day_of_week": day_of_week,
            "period": period,
            "notes": class_info.get("notes", "")
        }

    def _extract_date_from_filename(self, filename: str) -> Optional[Dict]:
        """
        ファイル名から日付情報を抽出
        
        Args:
            filename: ファイル名
            
        Returns:
            日付情報の辞書、抽出できない場合はNone
        """
        # パターン1: YYYYMMDD形式
        pattern1 = r"(\d{4})(\d{2})(\d{2})"
        match1 = re.search(pattern1, filename)
        if match1:
            year, month, day = map(int, match1.groups())
            try:
                date = datetime(year, month, day)
                return {"date": date, "pattern": "YYYYMMDD"}
            except ValueError:
                pass
                
        # パターン2: YYYY-MM-DD形式
        pattern2 = r"(\d{4})[_\-](\d{2})[_\-](\d{2})"
        match2 = re.search(pattern2, filename)
        if match2:
            year, month, day = map(int, match2.groups())
            try:
                date = datetime(year, month, day)
                return {"date": date, "pattern": "YYYY-MM-DD"}
            except ValueError:
                pass
                
        # パターン3: YYYY年MM月DD日形式
        pattern3 = r"(\d{4})年(\d{1,2})月(\d{1,2})日"
        match3 = re.search(pattern3, filename)
        if match3:
            year, month, day = map(int, match3.groups())
            try:
                date = datetime(year, month, day)
                return {"date": date, "pattern": "YYYY年MM月DD日"}
            except ValueError:
                pass
                
        # パターン4: MM-DD形式（年は現在の年と仮定）
        pattern4 = r"(\d{2})[_\-](\d{2})"
        match4 = re.search(pattern4, filename)
        if match4:
            month, day = map(int, match4.groups())
            try:
                current_year = datetime.now().year
                date = datetime(current_year, month, day)
                return {"date": date, "pattern": "MM-DD"}
            except ValueError:
                pass
                
        # 日付情報が見つからない場合
        return None

    def _extract_period_from_filename(self, filename: str) -> Optional[str]:
        """
        ファイル名から時限情報を抽出
        
        Args:
            filename: ファイル名
            
        Returns:
            時限情報、抽出できない場合はNone
        """
        # パターン1: N限形式
        pattern1 = r"(\d)限"
        match1 = re.search(pattern1, filename)
        if match1:
            return match1.group(1)
            
        # パターン2: periodN形式
        pattern2 = r"period(\d)"
        match2 = re.search(pattern2, filename, re.IGNORECASE)
        if match2:
            return match2.group(1)
            
        # パターン3: pN形式
        pattern3 = r"p(\d)"
        match3 = re.search(pattern3, filename, re.IGNORECASE)
        if match3:
            return match3.group(1)
            
        # 時間から時限を推定
        time_pattern = r"(\d{2})[:\-](\d{2})"
        time_match = re.search(time_pattern, filename)
        if time_match:
            hour, minute = map(int, time_match.groups())
            return self._estimate_period_from_time(hour, minute)
            
        # 時限情報が見つからない場合
        return None

    def _estimate_period_from_time(self, hour: int, minute: int) -> Optional[str]:
        """
        時間から時限を推定
        
        Args:
            hour: 時
            minute: 分
            
        Returns:
            推定された時限、推定できない場合はNone
        """
        # 時間帯と時限のマッピング
        time_periods = [
            ((8, 50), (10, 30), "1"),   # 1限: 8:50-10:30
            ((10, 40), (12, 20), "2"),  # 2限: 10:40-12:20
            ((13, 10), (14, 50), "3"),  # 3限: 13:10-14:50
            ((15, 0), (16, 40), "4"),   # 4限: 15:00-16:40
            ((16, 50), (18, 30), "5"),  # 5限: 16:50-18:30
            ((18, 40), (20, 20), "6"),  # 6限: 18:40-20:20
            ((20, 30), (22, 10), "7"),  # 7限: 20:30-22:10
        ]
        
        # 時間を分に変換
        time_in_minutes = hour * 60 + minute
        
        # 各時限の時間帯と比較
        for (start_hour, start_min), (end_hour, end_min), period in time_periods:
            start_time = start_hour * 60 + start_min
            end_time = end_hour * 60 + end_min
            
            if start_time <= time_in_minutes <= end_time:
                return period
                
        # 該当する時限がない場合
        return None

    def _get_day_of_week(self, date: datetime) -> str:
        """
        日付から曜日を取得
        
        Args:
            date: 日付
            
        Returns:
            曜日（"月", "火", "水", "木", "金", "土", "日"）
        """
        # 曜日のマッピング
        days = ["月", "火", "水", "木", "金", "土", "日"]
        
        # 日付から曜日のインデックスを取得（0:月曜, 1:火曜, ..., 6:日曜）
        # datetimeの曜日は0が月曜ではなく0が月曜なので調整
        weekday = date.weekday()
        
        return days[weekday]

    def _get_class_info(self, date: datetime, day_of_week: str, period: str) -> Dict:
        """
        日付、曜日、時限から授業情報を取得
        
        Args:
            date: 日付
            day_of_week: 曜日
            period: 時限
            
        Returns:
            授業情報の辞書
        """
        # 日付文字列
        date_str = date.strftime("%Y-%m-%d")
        
        # 特別な授業情報があるか確認
        if "special" in self.schedule and date_str in self.schedule["special"]:
            special_info = self.schedule["special"][date_str]
            
            # 特定の時限の情報があるか確認
            if period in special_info:
                return special_info[period]
                
        # 通常の授業情報を取得
        if day_of_week in self.schedule and period in self.schedule[day_of_week]:
            return self.schedule[day_of_week][period]
            
        # 該当する授業情報がない場合
        return {
            "subject": "不明",
            "lecturer": "不明",
            "room": "不明",
            "notes": ""
        }

    def update_schedule(self, schedule: Dict) -> bool:
        """
        授業スケジュールを更新
        
        Args:
            schedule: 新しい授業スケジュール
            
        Returns:
            更新に成功した場合はTrue、それ以外はFalse
        """
        try:
            # スケジュールを更新
            self.schedule = schedule
            
            # ファイルに保存
            schedule_path = Path(self.schedule_path)
            
            # ディレクトリが存在しない場合は作成
            if not schedule_path.parent.exists():
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                
            with open(schedule_path, "w", encoding="utf-8") as f:
                json.dump(schedule, f, ensure_ascii=False, indent=2)
                
            logger.info(f"授業スケジュールを更新しました: {schedule_path}")
            return True
        except Exception as e:
            logger.error(f"授業スケジュールの更新に失敗しました: {e}")
            return False

    def add_special_class(self, date: Union[datetime, str], period: str, class_info: Dict) -> bool:
        """
        特別な授業情報を追加
        
        Args:
            date: 日付（datetime型または"YYYY-MM-DD"形式の文字列）
            period: 時限
            class_info: 授業情報
            
        Returns:
            追加に成功した場合はTrue、それ以外はFalse
        """
        try:
            # 日付文字列に変換
            if isinstance(date, datetime):
                date_str = date.strftime("%Y-%m-%d")
            else:
                date_str = date
                
            # 特別な授業情報がない場合は初期化
            if "special" not in self.schedule:
                self.schedule["special"] = {}
                
            # 日付の特別情報がない場合は初期化
            if date_str not in self.schedule["special"]:
                self.schedule["special"][date_str] = {}
                
            # 授業情報を追加
            self.schedule["special"][date_str][period] = class_info
            
            # ファイルに保存
            schedule_path = Path(self.schedule_path)
            with open(schedule_path, "w", encoding="utf-8") as f:
                json.dump(self.schedule, f, ensure_ascii=False, indent=2)
                
            logger.info(f"特別な授業情報を追加しました: {date_str} {period}限")
            return True
        except Exception as e:
            logger.error(f"特別な授業情報の追加に失敗しました: {e}")
            return False

    def get_schedule(self) -> Dict:
        """
        授業スケジュールを取得
        
        Returns:
            授業スケジュール辞書
        """
        return self.schedule


# シングルトンインスタンス
class_info_service = ClassInfoService()