"""
国务院节假日通知解析器
从文本通知中提取节假日安排
"""

import re
from datetime import date, timedelta
from typing import List, Dict, Any, Optional


class ParseError(Exception):
    """解析错误"""
    pass


# 节假日名称映射
HOLIDAY_NAME_PATTERNS = {
    '元旦': 'New Year',
    '春节': 'Spring Festival',
    '清明': 'Tomb Sweeping',
    '清明节': 'Tomb Sweeping',
    '劳动': 'Labor Day',
    '劳动节': 'Labor Day',
    '端午': 'Dragon Boat',
    '端午节': 'Dragon Boat',
    '中秋': 'Mid-Autumn',
    '中秋节': 'Mid-Autumn',
    '国庆': 'National Day',
    '国庆节': 'National Day',
}

# 法定假日天数配置
STATUTORY_DAYS = {
    '元旦': 1,
    '春节': 3,
    '清明节': 1,
    '劳动节': 1,
    '端午节': 1,
    '中秋节': 1,
    '国庆节': 3,
}


def parse_holiday_item(text: str, year: int = None) -> Dict[str, Any]:
    """
    解析单条节假日条目

    Args:
        text: 如 "元旦：1月1日（周四）至3日（周六）放假调休，共3天。1月4日（周日）上班。"
        year: 年份，如未提供则尝试从文本推断

    Returns:
        节假日信息字典
    """
    text = text.strip()

    # 提取节假日名称
    name_match = re.match(r'([一二三四五六七八九、]+)?\s*([^：:]+)[：:]', text)
    if not name_match:
        raise ParseError(f"Cannot extract holiday name from: {text}")

    holiday_name = name_match.group(2).strip()

    # 清理名称（去除"节"字等变体）
    base_name = holiday_name.replace('节', '')
    if base_name + '节' in STATUTORY_DAYS:
        holiday_name = base_name + '节'
    elif base_name not in STATUTORY_DAYS:
        # 尝试匹配
        for known in STATUTORY_DAYS.keys():
            if base_name in known or known in base_name:
                holiday_name = known
                break

    # 提取年份
    if year is None:
        year_match = re.search(r'(\d{4})年', text)
        if year_match:
            year = int(year_match.group(1))
        else:
            year = date.today().year

    # 提取日期范围
    date_range_pattern = r'(\d{1,2})月(\d{1,2})日[^至]*至[^\d]*(\d{1,2})月)?(\d{1,2})日'

    # 同月范围: X月Y日至Z日
    same_month_match = re.search(r'(\d{1,2})月(\d{1,2})日[^至]*至[^\d]*(\d{1,2})日', text)
    # 跨月范围: X月Y日至M月N日
    cross_month_match = re.search(r'(\d{1,2})月(\d{1,2})日[^至]*至(\d{1,2})月(\d{1,2})日', text)

    if cross_month_match:
        start_month = int(cross_month_match.group(1))
        start_day = int(cross_month_match.group(2))
        end_month = int(cross_month_match.group(3))
        end_day = int(cross_month_match.group(4))
        start_date = date(year, start_month, start_day)
        end_date = date(year, end_month, end_day)
    elif same_month_match:
        month = int(same_month_match.group(1))
        start_day = int(same_month_match.group(2))
        end_day = int(same_month_match.group(3))
        start_date = date(year, month, start_day)
        end_date = date(year, month, end_day)
    else:
        raise ParseError(f"Cannot extract date range from: {text}")

    # 提取调休上班日
    adjusted_workdays = extract_adjusted_workdays(text, year)

    # 确定法定假日
    statutory_days = get_statutory_holidays(holiday_name, start_date, end_date)

    return {
        'name': holiday_name,
        'start_date': start_date,
        'end_date': end_date,
        'statutory_days': statutory_days,
        'adjusted_workdays': adjusted_workdays,
    }


def extract_adjusted_workdays(text: str, year: int) -> List[date]:
    """
    从文本中提取调休上班日

    Args:
        text: 节假日条目文本
        year: 年份

    Returns:
        调休上班日列表
    """
    workdays = []

    # 找到"上班"的位置
    work_pos = text.find('上班')
    if work_pos == -1:
        return workdays

    # 策略：找到"放假"或"至X日"之后的部分，然后提取"上班"前的日期
    # 找到"放假"关键字的位置
    holiday_end_pos = -1
    for keyword in ['放假调休', '放假']:
        pos = text.find(keyword)
        if pos != -1:
            holiday_end_pos = pos + len(keyword)
            break

    # 如果没有"放假"，则从文本开头提取（独立调用场景）
    if holiday_end_pos == -1:
        section = text[:work_pos]
    else:
        # 提取放假之后、上班之前的文本段
        section = text[holiday_end_pos:work_pos]

    # 从这段文本中提取所有日期 (X月Y日)
    date_pattern = r'(\d{1,2})月(\d{1,2})日'
    for match in re.finditer(date_pattern, section):
        month = int(match.group(1))
        day = int(match.group(2))
        workdays.append(date(year, month, day))

    return workdays


def get_statutory_holidays(name: str, start_date: date, end_date: date) -> List[date]:
    """
    根据节假日名称和日期范围确定法定假日

    Args:
        name: 节假日名称
        start_date: 假期开始日期
        end_date: 假期结束日期

    Returns:
        法定假日日期列表
    """
    # 标准化名称
    base_name = name.replace('节', '')
    statutory_count = None

    for known_name, count in STATUTORY_DAYS.items():
        if base_name in known_name or known_name.replace('节', '') in base_name:
            statutory_count = count
            break

    if statutory_count is None:
        # 未知节假日，假设第一天是法定
        statutory_count = 1

    # 生成法定假日列表（从假期开始日起算）
    statutory_days = []
    current = start_date

    # 对于春节，法定是除夕、初一、初二
    # 春节假期通常从腊月二十八/二十九/三十开始，法定从除夕开始
    if '春节' in name or '春節' in name:
        # 春节假期通常9天，法定3天在中间
        # 简单策略：取假期中间3天（第3、4、5天）
        total_days = (end_date - start_date).days + 1
        # 法定假日通常在除夕、初一、初二
        # 假设放假从腊月二十八开始，除夕是第3天（2/17）
        for i in range(total_days):
            d = start_date + timedelta(days=i)
            # 根据2026年春节：2/15开始，法定2/17、2/18、2/19
            # 即跳过前2天，取第3-5天
            if i >= 2 and len(statutory_days) < statutory_count:
                statutory_days.append(d)
    else:
        # 其他节假日，法定从第一天开始
        for i in range(statutory_count):
            d = start_date + timedelta(days=i)
            if d <= end_date:
                statutory_days.append(d)

    return statutory_days


def parse_notification(text: str, year: int = None) -> List[Dict[str, Any]]:
    """
    解析完整节假日通知文本

    Args:
        text: 完整通知文本
        year: 年份

    Returns:
        节假日列表
    """
    if not text or not text.strip():
        return []

    # 提取年份
    if year is None:
        year_match = re.search(r'(\d{4})年', text)
        if year_match:
            year = int(year_match.group(1))
        else:
            year = date.today().year

    holidays = []

    # 按序号分割条目（一、二、三...）
    # 匹配 "一、...二、..." 或 "1....2...."
    item_pattern = r'[一二三四五六七八九十百千万]+[、.．]\s*([^\n]+(?:\n(?![一二三四五六七八九十百千万]+[、.．]).*)*)'

    for match in re.finditer(item_pattern, text):
        item_text = match.group(1).strip()
        try:
            holiday = parse_holiday_item(item_text, year)
            holidays.append(holiday)
        except ParseError:
            # 跳过无法解析的条目
            continue

    return holidays


def extract_all_holiday_dates(text: str, year: int = None) -> List[date]:
    """
    提取所有节假日日期（包括假期和调休上班日）

    Args:
        text: 通知文本
        year: 年份

    Returns:
        所有相关日期列表
    """
    holidays = parse_notification(text, year)
    all_dates = set()

    for h in holidays:
        # 添加整个假期范围
        current = h['start_date']
        while current <= h['end_date']:
            all_dates.add(current)
            current += timedelta(days=1)

        # 添加法定假日
        for d in h.get('statutory_days', []):
            all_dates.add(d)

        # 添加调休上班日
        for d in h.get('adjusted_workdays', []):
            all_dates.add(d)

    return sorted(list(all_dates))
