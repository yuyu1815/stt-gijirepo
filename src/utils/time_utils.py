"""
時間関連のユーティリティ関数

このモジュールには、時間の変換やフォーマットに関するユーティリティ関数が含まれています。
"""

from ..infrastructure.logger import logger


def format_time(seconds: float) -> str:
    """
    秒を時間文字列にフォーマット

    Args:
        seconds: 秒数

    Returns:
        時間文字列（HH:MM:SS形式）
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def time_str_to_seconds(time_str: str) -> float:
    """
    時間文字列を秒に変換

    Args:
        time_str: 時間文字列（HH:MM:SS形式）

    Returns:
        秒数
    """
    parts = time_str.split(':')
    if len(parts) == 3:  # HH:MM:SS
        try:
            hours, minutes, seconds = map(float, parts)
            return hours * 3600 + minutes * 60 + seconds
        except ValueError:
            logger.warning(f"HH:MM:SS形式の時刻文字列のパースに失敗しました: {time_str}")
            return 0.0
    elif len(parts) == 2:  # MM:SS
        try:
            minutes, seconds = map(float, parts)
            return minutes * 60 + seconds
        except ValueError:
            logger.warning(f"MM:SS形式の時刻文字列のパースに失敗しました: {time_str}")
            return 0.0
    elif len(parts) == 1:  # SS
        try:
            return float(parts[0])
        except ValueError:
            logger.warning(f"SS形式の時刻文字列のパースに失敗しました: {time_str}")
            return 0.0
    else:
        # Handle H:MM:SS (single digit hour) which might be common
        if ':' in time_str:
            try:
                h, m, s = map(float, time_str.split(':'))
                if time_str.count(':') == 2:  # Assume H:MM:SS if three parts after split
                    return h * 3600 + m * 60 + s
            except ValueError:
                pass  # Fall through if this specific parsing fails
        logger.warning(f"予期しない時刻文字列形式です: {time_str}。秒として直接パースするか、0を返します。")
        try:
            return float(time_str)  # Try to parse as raw seconds as a last resort
        except ValueError:
            logger.error(f"無効な時刻文字列形式で、パースできません: {time_str}")
            return 0.0  # Default or raise more specific error