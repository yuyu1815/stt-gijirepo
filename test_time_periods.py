import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).parent))

from src.services.class_info import class_info_service

def test_valid_time_periods():
    """Test valid time periods"""
    print("Testing valid time periods...")
    
    # Test times that fall within a period
    assert class_info_service._estimate_period_from_time(9, 0) == "1"  # 9:00 -> 1限 (8:50-10:30)
    assert class_info_service._estimate_period_from_time(11, 0) == "2"  # 11:00 -> 2限 (10:40-12:20)
    assert class_info_service._estimate_period_from_time(14, 0) == "3"  # 14:00 -> 3限 (13:10-14:50)
    
    print("All valid time period tests passed!")

def test_invalid_time_periods():
    """Test invalid time periods"""
    print("\nTesting invalid time periods...")
    
    # Test times that are far from any period
    try:
        class_info_service._estimate_period_from_time(3, 0)  # 3:00 AM is far from any period
        print("Error: Expected ValueError for 3:00 AM")
    except ValueError as e:
        print(f"Success: Got expected error for 3:00 AM: {e}")
    
    try:
        class_info_service._estimate_period_from_time(4, 30)  # 4:30 AM is far from any period
        print("Error: Expected ValueError for 4:30 AM")
    except ValueError as e:
        print(f"Success: Got expected error for 4:30 AM: {e}")
    
    print("All invalid time period tests completed!")

if __name__ == "__main__":
    print("Testing time periods from JSON...")
    
    # Print the time periods from the schedule
    time_periods = class_info_service._get_time_periods_from_schedule()
    print("Time periods from schedule:")
    for (start_hour, start_min), (end_hour, end_min), period in time_periods:
        print(f"Period {period}: {start_hour:02d}:{start_min:02d} - {end_hour:02d}:{end_min:02d}")
    
    # Run the tests
    test_valid_time_periods()
    test_invalid_time_periods()
    
    print("\nAll tests completed!")