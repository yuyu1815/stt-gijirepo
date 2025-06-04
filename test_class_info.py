import sys
import re
from pathlib import Path
import datetime

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).parent))

from src.services.class_info import class_info_service

def test_estimate_period_from_time():
    """Test the _estimate_period_from_time method"""
    # Test times that fall within a period
    assert class_info_service._estimate_period_from_time(9, 0) == "1"  # 9:00 -> 1限 (8:50-10:30)
    assert class_info_service._estimate_period_from_time(11, 0) == "2"  # 11:00 -> 2限 (10:40-12:20)
    assert class_info_service._estimate_period_from_time(14, 0) == "3"  # 14:00 -> 3限 (13:10-14:50)

    # Test times that don't fall within any period
    assert class_info_service._estimate_period_from_time(8, 0) == "1"  # 8:00 -> closest to 1限 (8:50)
    assert class_info_service._estimate_period_from_time(10, 35) == "2"  # 10:35 -> closest to 2限 (10:40)
    assert class_info_service._estimate_period_from_time(12, 45) == "3"  # 12:45 -> closest to 3限 (13:10)
    assert class_info_service._estimate_period_from_time(23, 0) == "7"  # 23:00 -> closest to 7限 (20:30)

def test_extract_period_from_filename():
    """Test the _extract_period_from_filename method"""
    # Test filenames with explicit period information
    assert class_info_service._extract_period_from_filename("lecture_1限_topic") == "1"
    assert class_info_service._extract_period_from_filename("lecture_period2_topic") == "2"
    assert class_info_service._extract_period_from_filename("lecture_p3_topic") == "3"

    # Test filenames with time information
    assert class_info_service._extract_period_from_filename("lecture_09:00_topic") == "1"
    assert class_info_service._extract_period_from_filename("lecture_11-00_topic") == "2"

    # Debug the problematic filename
    test_filename = "2025-05-26 11-14-15"
    print(f"\nDebugging filename: {test_filename}")
    pattern = r'^\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}$'
    print(f"Regex match: {bool(re.match(pattern, test_filename))}")
    print(f"Parts after split: {test_filename.split(' ')}")
    if len(test_filename.split(' ')) == 2:
        time_parts = test_filename.split(' ')[1].split('-')
        print(f"Time parts: {time_parts}")
        if len(time_parts) >= 2:
            hour, minute = int(time_parts[0]), int(time_parts[1])
            print(f"Hour: {hour}, Minute: {minute}")
            period = class_info_service._estimate_period_from_time(hour, minute)
            print(f"Estimated period: {period}")

    result = class_info_service._extract_period_from_filename(test_filename)
    print(f"Result of _extract_period_from_filename: {result}")

    # Now run the assertion
    assert result == "2"  # 11:14 -> closest to 2限 (10:40-12:20)

    assert class_info_service._extract_period_from_filename("2025-05-26 08-30-00") == "1"  # 8:30 -> closest to 1限 (8:50)

def test_get_class_info_from_filename():
    """Test the get_class_info_from_filename method"""
    # Test with a filename that includes date and time
    class_info = class_info_service.get_class_info_from_filename("2025-05-26 11-14-15")
    print(f"Class info for '2025-05-26 11-14-15': {class_info}")

    # Test with a filename that includes only date
    class_info = class_info_service.get_class_info_from_filename("20250526")
    print(f"Class info for '20250526': {class_info}")

if __name__ == "__main__":
    print("Testing _estimate_period_from_time method...")
    test_estimate_period_from_time()
    print("All _estimate_period_from_time tests passed!")

    print("\nTesting _extract_period_from_filename method...")
    test_extract_period_from_filename()
    print("All _extract_period_from_filename tests passed!")

    print("\nTesting get_class_info_from_filename method...")
    test_get_class_info_from_filename()
    print("All tests completed!")
