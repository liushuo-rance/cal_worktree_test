"""
日期解析器
支持多种日期格式和日期范围解析
"""

import re
from datetime import date, datetime
from typing import Optional, Tuple


class DateParseError(Exception):
    """日期解析错误"""
    pass


# 单日期模式正则表达式
SINGLE_DATE_PATTERNS = [
    # 2025.08.15, 2025.9.18
    (r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', 'yyyy.m.d'),
    # 2025年8月15日
    (r'(\d{4})年(\d{1,2})月(\d{1,2})日', 'yyyy年m月d日'),
]

# 日期范围模式正则表达式
DATE_RANGE_PATTERNS = [
    # 2025.10.27-29 (同月)
    (r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s*[-~至]\s*(\d{1,2})', 'yyyy.m.d-d'),
    # 2025.10.27-11.3 (跨月)
    (r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s*[-~至]\s*(\d{1,2})[.\-/](\d{1,2})', 'yyyy.m.d-m.d'),
    # 2025.10.27至11.3 (中文分隔符跨月)
    (r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s*至\s*(\d{1,2})[.\-/](\d{1,2})', 'yyyy.m.d至m.d'),
]


def parse_date(date_str: str) -> date:
    """
    解析单日期字符串

    Args:
        date_str: 日期字符串，如 "2025.08.15"

    Returns:
        date对象

    Raises:
        DateParseError: 解析失败时抛出
    """
    date_str = date_str.strip()

    for pattern, fmt in SINGLE_DATE_PATTERNS:
        match = re.match(pattern, date_str)
        if match:
            year, month, day = map(int, match.groups())
            try:
                return date(year, month, day)
            except ValueError as e:
                raise DateParseError(f"Invalid date: {date_str} ({e})")

    raise DateParseError(f"Cannot parse date: {date_str}")


def parse_date_range(date_str: str) -> Tuple[date, date]:
    """
    解析日期范围字符串

    Args:
        date_str: 日期范围字符串，如 "2025.10.27-29"

    Returns:
        (开始日期, 结束日期) 元组

    Raises:
        DateParseError: 解析失败时抛出
    """
    date_str = date_str.strip()

    # 先尝试跨月范围匹配（必须优先，避免被同月模式错误匹配）
    # 格式: 2025.10.27-11.3 或 2025.10.27至11.3
    cross_month_pattern = r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s*[-~至]\s*(\d{1,2})[.\-/](\d{1,2})'
    match = re.match(cross_month_pattern, date_str)
    if match:
        year, start_month, start_day, end_month, end_day = map(int, match.groups())
        try:
            start_date = date(year, start_month, start_day)
            end_date = date(year, end_month, end_day)
            if end_date < start_date:
                raise DateParseError(f"End date before start date: {date_str}")
            return (start_date, end_date)
        except ValueError as e:
            raise DateParseError(f"Invalid date range: {date_str} ({e})")

    # 尝试同月范围匹配（结束日期只有日，没有月）
    # 格式: 2025.10.27-29
    same_month_pattern = r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s*[-~至]\s*(\d{1,2})'
    match = re.match(same_month_pattern, date_str)
    if match:
        year, month, start_day, end_day = map(int, match.groups())
        try:
            start_date = date(year, month, start_day)
            end_date = date(year, month, end_day)
            if end_date < start_date:
                raise DateParseError(f"End date before start date: {date_str}")
            return (start_date, end_date)
        except ValueError as e:
            raise DateParseError(f"Invalid date range: {date_str} ({e})")

    # 尝试跨月范围匹配
    cross_month_pattern = r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s*[-~至]\s*(\d{1,2})[.\-/](\d{1,2})'
    match = re.match(cross_month_pattern, date_str)
    if match:
        year, start_month, start_day, end_month, end_day = map(int, match.groups())
        try:
            start_date = date(year, start_month, start_day)
            end_date = date(year, end_month, end_day)
            if end_date < start_date:
                raise DateParseError(f"End date before start date: {date_str}")
            return (start_date, end_date)
        except ValueError as e:
            raise DateParseError(f"Invalid date range: {date_str} ({e})")

    raise DateParseError(f"Cannot parse date range: {date_str}")


def parse_partial_date(date_str: str, default_year: int) -> date:
    """
    解析缺少年份的日期字符串

    Args:
        date_str: 日期字符串，如 "9.10"
        default_year: 默认年份

    Returns:
        date对象

    Raises:
        DateParseError: 解析失败时抛出
    """
    date_str = date_str.strip()

    # 匹配 M.D 格式
    pattern = r'(\d{1,2})[.\-/](\d{1,2})'
    match = re.match(pattern, date_str)
    if match:
        month, day = map(int, match.groups())
        try:
            return date(default_year, month, day)
        except ValueError as e:
            raise DateParseError(f"Invalid partial date: {date_str} ({e})")

    raise DateParseError(f"Cannot parse partial date: {date_str}")


def parse_date_with_context(date_str: str, last_date: Optional[date] = None) -> date:
    """
    根据上下文解析日期（处理缺少年份的情况）

    Args:
        date_str: 日期字符串
        last_date: 上一条记录的日期，用于推断年份

    Returns:
        date对象
    """
    date_str = date_str.strip()

    # 首先尝试完整日期解析
    try:
        return parse_date(date_str)
    except DateParseError:
        pass

    # 尝试部分日期解析
    default_year = last_date.year if last_date else date.today().year
    return parse_partial_date(date_str, default_year)


def extract_date_from_line(line: str) -> Optional[Tuple[str, str]]:
    """
    从行文本中提取日期部分和剩余内容

    Args:
        line: 原始行文本

    Returns:
        (日期部分, 剩余内容) 元组，如果无日期则返回None
    """
    line = line.strip()

    # 尝试匹配日期范围
    range_pattern = r'^(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}\s*[-~至]\s*(?:\d{1,2}[.\-/])?\d{1,2})[,，\s]+(.*)$'
    match = re.match(range_pattern, line)
    if match:
        return (match.group(1), match.group(2))

    # 尝试匹配单日期
    single_pattern = r'^(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})[,，\s]+(.*)$'
    match = re.match(single_pattern, line)
    if match:
        return (match.group(1), match.group(2))

    # 尝试匹配中文格式日期
    chinese_pattern = r'^(\d{4}年\d{1,2}月\d{1,2}日)[,，\s]+(.*)$'
    match = re.match(chinese_pattern, line)
    if match:
        return (match.group(1), match.group(2))

    return None
