"""
STT議事録システム - クラス情報処理テスト

class_info.pyモジュールのテストケース
"""

import pytest
import json
import tempfile
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from src.utils.class_info import (
    get_class_info,
    extract_class_period,
    parse_datetime_from_filename
)


class TestGetClassInfo:
    """get_class_info関数のテスト"""
    
    def create_test_settings(self, temp_dir: str) -> str:
        """テスト用設定ファイルを作成"""
        settings = {
            "schedule": {
                "月曜日": {
                    "1限": {"name": "数学", "teacher": "田中先生"},
                    "2限": {"name": "英語", "teacher": "佐藤先生"},
                    "3限": {"name": "物理", "teacher": "鈴木先生"},
                    "4限": {"name": "化学", "teacher": "高橋先生"}
                },
                "火曜日": {
                    "1限": {"name": "国語", "teacher": "山田先生"},
                    "2限": {"name": "歴史", "teacher": "中村先生"}
                },
                "水曜日": {
                    "3限": {"name": "生物", "teacher": "小林先生"}
                }
            }
        }
        
        settings_file = os.path.join(temp_dir, "test_settings.json")
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        
        return settings_file
    
    def test_standard_datetime_format(self):
        """標準的な日時フォーマットのテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_file = self.create_test_settings(temp_dir)
            
            # 月曜日1限のファイル名
            file_path = "/test/2024年05月20日 09:30～11:00.mp3"
            result = get_class_info(file_path, settings_file)
            
            assert result["name"] == "数学"
            assert result["teacher"] == "田中先生"
            assert "2024年05月20日 09:30～11:00" in result["datetime"]
    
    def test_new_datetime_format(self):
        """新しい日時フォーマットのテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_file = self.create_test_settings(temp_dir)
            
            # 火曜日2限のファイル名（新フォーマット）
            file_path = "/test/2024-05-21 11-10-30.mp3"
            result = get_class_info(file_path, settings_file)
            
            assert result["name"] == "歴史"
            assert result["teacher"] == "中村先生"
            assert "2024年05月21日 11:10:30" in result["datetime"]
    
    def test_class_period_detection(self):
        """授業時限検出のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_file = self.create_test_settings(temp_dir)
            
            # 各時限のテスト
            test_cases = [
                ("2024年05月20日 09:30～11:00.mp3", "数学"),  # 1限
                ("2024年05月20日 11:10～12:50.mp3", "英語"),  # 2限
                ("2024年05月20日 13:40～15:20.mp3", "物理"),  # 3限
                ("2024年05月20日 15:20～17:00.mp3", "化学"),  # 4限
            ]
            
            for filename, expected_subject in test_cases:
                result = get_class_info(f"/test/{filename}", settings_file)
                assert result["name"] == expected_subject
    
    def test_weekend_detection(self):
        """土日の検出テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_file = self.create_test_settings(temp_dir)
            
            # 土曜日のファイル名
            file_path = "/test/2024年05月25日 09:30～11:00.mp3"  # 2024/5/25は土曜日
            result = get_class_info(file_path, settings_file)
            
            assert result["name"] == "不明"
            assert result["teacher"] == "不明"
    
    def test_settings_file_not_found(self):
        """設定ファイルが見つからない場合のテスト"""
        file_path = "/test/2024年05月20日 09:30～11:00.mp3"
        result = get_class_info(file_path, "nonexistent_settings.json")
        
        assert result["name"] == "不明"
        assert result["teacher"] == "不明"
    
    def test_invalid_settings_file(self):
        """無効な設定ファイルのテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 無効なJSONファイルを作成
            invalid_settings = os.path.join(temp_dir, "invalid.json")
            with open(invalid_settings, 'w') as f:
                f.write("invalid json content")
            
            file_path = "/test/2024年05月20日 09:30～11:00.mp3"
            result = get_class_info(file_path, invalid_settings)
            
            assert result["name"] == "不明"
            assert result["teacher"] == "不明"
    
    def test_change_pattern_detection(self):
        """授業変更パターンの検出テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_file = self.create_test_settings(temp_dir)
            
            test_cases = [
                "変更_特別講義.mp3",
                "変更：臨時授業.mp3",
                "変更 補講.mp3",
            ]
            
            expected_names = ["特別講義", "臨時授業", "補講"]
            
            for filename, expected_name in zip(test_cases, expected_names):
                result = get_class_info(f"/test/{filename}", settings_file)
                assert result["name"] == expected_name
                assert result["teacher"] == "不明"
                assert result["datetime"] == "不明"
    
    def test_subject_name_in_filename(self):
        """ファイル名に科目名が含まれる場合のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_file = self.create_test_settings(temp_dir)
            
            # 科目名が含まれるファイル名
            file_path = "/test/数学_録音.mp3"
            result = get_class_info(file_path, settings_file)
            
            assert result["name"] == "数学"
            assert result["teacher"] == "田中先生"
            assert result["datetime"] == "不明"
    
    def test_no_match_default_values(self):
        """マッチしない場合のデフォルト値テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_file = self.create_test_settings(temp_dir)
            
            file_path = "/test/unknown_file.mp3"
            result = get_class_info(file_path, settings_file)
            
            assert result["name"] == "不明"
            assert result["teacher"] == "不明"
            assert result["datetime"] == "不明"
    
    def test_invalid_date_handling(self):
        """無効な日付の処理テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_file = self.create_test_settings(temp_dir)
            
            # 無効な日付（13月）
            file_path = "/test/2024年13月32日 09:30～11:00.mp3"
            result = get_class_info(file_path, settings_file)
            
            assert result["name"] == "不明"
            assert result["teacher"] == "不明"
    
    def test_closest_period_calculation(self):
        """最も近い時限の計算テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_file = self.create_test_settings(temp_dir)
            
            # 1限と2限の中間時刻（10:20）
            file_path = "/test/2024年05月20日 10:20～11:00.mp3"
            result = get_class_info(file_path, settings_file)
            
            # 1限（9:30）の方が近いので数学になるはず
            assert result["name"] == "数学"


class TestExtractClassPeriod:
    """extract_class_period関数のテスト"""
    
    def test_exact_class_times(self):
        """正確な授業時間のテスト"""
        test_cases = [
            (9*60+30, "1限"),   # 9:30
            (11*60+10, "2限"),  # 11:10
            (13*60+40, "3限"),  # 13:40
            (15*60+20, "4限"),  # 15:20
        ]
        
        for time_minutes, expected_period in test_cases:
            result = extract_class_period(time_minutes)
            assert result == expected_period
    
    def test_approximate_class_times(self):
        """近似的な授業時間のテスト"""
        test_cases = [
            (9*60+25, "1限"),   # 9:25 -> 1限に近い
            (9*60+35, "1限"),   # 9:35 -> 1限に近い
            (11*60+5, "2限"),   # 11:05 -> 2限に近い
            (11*60+15, "2限"),  # 11:15 -> 2限に近い
            (13*60+35, "3限"),  # 13:35 -> 3限に近い
            (13*60+45, "3限"),  # 13:45 -> 3限に近い
            (15*60+15, "4限"),  # 15:15 -> 4限に近い
            (15*60+25, "4限"),  # 15:25 -> 4限に近い
        ]
        
        for time_minutes, expected_period in test_cases:
            result = extract_class_period(time_minutes)
            assert result == expected_period
    
    def test_boundary_cases(self):
        """境界ケースのテスト"""
        # 1限と2限の中間（10:20）
        result = extract_class_period(10*60+20)
        assert result == "1限"  # 1限の方が近い
        
        # 2限と3限の中間（12:25）
        result = extract_class_period(12*60+25)
        assert result == "2限"  # 2限の方が近い
        
        # 3限と4限の中間（14:30）
        result = extract_class_period(14*60+30)
        assert result == "3限"  # 3限の方が近い
    
    def test_early_morning_time(self):
        """早朝時間のテスト"""
        result = extract_class_period(8*60)  # 8:00
        assert result == "1限"  # 1限が最も近い
    
    def test_late_evening_time(self):
        """夜間時間のテスト"""
        result = extract_class_period(18*60)  # 18:00
        assert result == "4限"  # 4限が最も近い


class TestParseDatetimeFromFilename:
    """parse_datetime_from_filename関数のテスト"""
    
    def test_standard_format(self):
        """標準フォーマットのテスト"""
        filename = "2024年05月20日 09:30～11:00.mp3"
        result = parse_datetime_from_filename(filename)
        
        assert result is not None
        assert result["year"] == 2024
        assert result["month"] == 5
        assert result["day"] == 20
        assert result["hour"] == 9
        assert result["minute"] == 30
        assert result["format_type"] == 0
        assert isinstance(result["datetime"], datetime)
    
    def test_new_format(self):
        """新フォーマットのテスト"""
        filename = "2025-04-14 13-35-31.mp3"
        result = parse_datetime_from_filename(filename)
        
        assert result is not None
        assert result["year"] == 2025
        assert result["month"] == 4
        assert result["day"] == 14
        assert result["hour"] == 13
        assert result["minute"] == 35
        assert result["format_type"] == 1
        assert isinstance(result["datetime"], datetime)
    
    def test_compact_format(self):
        """コンパクトフォーマットのテスト"""
        filename = "20240520_0930.mp3"
        result = parse_datetime_from_filename(filename)
        
        assert result is not None
        assert result["year"] == 2024
        assert result["month"] == 5
        assert result["day"] == 20
        assert result["hour"] == 9
        assert result["minute"] == 30
        assert result["format_type"] == 2
        assert isinstance(result["datetime"], datetime)
    
    def test_weekday_calculation(self):
        """曜日計算のテスト"""
        # 2024年5月20日は月曜日（weekday=0）
        filename = "2024年05月20日 09:30～11:00.mp3"
        result = parse_datetime_from_filename(filename)
        
        assert result is not None
        assert result["weekday"] == 0  # 月曜日
    
    def test_invalid_date(self):
        """無効な日付のテスト"""
        invalid_filenames = [
            "2024年13月32日 09:30～11:00.mp3",  # 無効な月日
            "2024-02-30 10-00-00.mp3",          # 2月30日は存在しない
            "20240229_2500.mp3",                # 25時は存在しない
        ]
        
        for filename in invalid_filenames:
            result = parse_datetime_from_filename(filename)
            assert result is None
    
    def test_no_match(self):
        """マッチしないファイル名のテスト"""
        invalid_filenames = [
            "random_file.mp3",
            "audio_recording.wav",
            "2024-05-20.mp3",  # 時間が含まれていない
            "05月20日.mp3",     # 年が含まれていない
        ]
        
        for filename in invalid_filenames:
            result = parse_datetime_from_filename(filename)
            assert result is None
    
    def test_multiple_patterns_in_filename(self):
        """ファイル名に複数のパターンが含まれる場合のテスト"""
        # 最初にマッチするパターンが使用される
        filename = "2024年05月20日 09:30～11:00_2025-04-14 13-35-31.mp3"
        result = parse_datetime_from_filename(filename)
        
        assert result is not None
        assert result["year"] == 2024  # 最初のパターンが使用される
        assert result["format_type"] == 0
    
    def test_edge_case_dates(self):
        """エッジケースの日付テスト"""
        edge_cases = [
            ("2024年01月01日 00:00～01:00.mp3", 2024, 1, 1, 0, 0),    # 年始
            ("2024年12月31日 23:59～23:59.mp3", 2024, 12, 31, 23, 59), # 年末
            ("2024年02月29日 12:00～13:00.mp3", 2024, 2, 29, 12, 0),   # うるう年
        ]
        
        for filename, year, month, day, hour, minute in edge_cases:
            result = parse_datetime_from_filename(filename)
            assert result is not None
            assert result["year"] == year
            assert result["month"] == month
            assert result["day"] == day
            assert result["hour"] == hour
            assert result["minute"] == minute


class TestClassInfoIntegration:
    """クラス情報処理の統合テスト"""
    
    def test_full_workflow(self):
        """完全なワークフローのテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 設定ファイルを作成
            settings = {
                "schedule": {
                    "月曜日": {
                        "1限": {"name": "統合テスト科目", "teacher": "テスト先生"}
                    }
                }
            }
            
            settings_file = os.path.join(temp_dir, "integration_settings.json")
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False)
            
            # ファイル名から情報を抽出
            filename = "2024年05月20日 09:30～11:00.mp3"
            
            # 個別関数のテスト
            datetime_info = parse_datetime_from_filename(filename)
            assert datetime_info is not None
            
            period = extract_class_period(datetime_info["hour"] * 60 + datetime_info["minute"])
            assert period == "1限"
            
            # 統合関数のテスト
            class_info = get_class_info(f"/test/{filename}", settings_file)
            assert class_info["name"] == "統合テスト科目"
            assert class_info["teacher"] == "テスト先生"
    
    def test_error_recovery(self):
        """エラー回復のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 空の設定ファイル
            empty_settings = os.path.join(temp_dir, "empty.json")
            with open(empty_settings, 'w') as f:
                json.dump({}, f)
            
            # 無効な日付のファイル名
            filename = "2024年13月32日 09:30～11:00.mp3"
            result = get_class_info(f"/test/{filename}", empty_settings)
            
            # エラーが発生してもデフォルト値が返される
            assert result["name"] == "不明"
            assert result["teacher"] == "不明"
    
    def test_performance_with_large_schedule(self):
        """大きな時間割でのパフォーマンステスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 大きな時間割を作成
            large_schedule = {}
            weekdays = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日"]
            periods = ["1限", "2限", "3限", "4限"]
            
            for weekday in weekdays:
                large_schedule[weekday] = {}
                for period in periods:
                    large_schedule[weekday][period] = {
                        "name": f"{weekday}_{period}_科目",
                        "teacher": f"{weekday}_{period}_先生"
                    }
            
            settings_file = os.path.join(temp_dir, "large_settings.json")
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump({"schedule": large_schedule}, f, ensure_ascii=False)
            
            # 複数のファイル名でテスト
            test_files = [
                "2024年05月20日 09:30～11:00.mp3",  # 月曜日1限
                "2024年05月21日 11:10～12:50.mp3",  # 火曜日2限
                "2024年05月22日 13:40～15:20.mp3",  # 水曜日3限
            ]
            
            for filename in test_files:
                result = get_class_info(f"/test/{filename}", settings_file)
                assert result["name"] != "不明"
                assert result["teacher"] != "不明"


if __name__ == "__main__":
    pytest.main([__file__])