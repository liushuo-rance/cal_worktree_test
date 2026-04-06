"""
农历转换器（简化版）
基于已知农历数据进行转换
实际生产环境应使用专业农历库（如 lunarcalendar）
"""

from datetime import date, timedelta
from typing import Tuple, Optional


class LunarConversionError(Exception):
    """农历转换错误"""
    pass


# 已知节日日期对照表（2025-2027年）
KNOWN_FESTIVALS = {
    2025: {
        '春节': date(2025, 1, 29),
        '端午节': date(2025, 5, 31),
        '中秋节': date(2025, 10, 6),
    },
    2026: {
        '春节': date(2026, 2, 17),
        '端午节': date(2026, 6, 19),
        '中秋节': date(2026, 9, 25),
    },
    2027: {
        '春节': date(2027, 2, 6),
        '端午节': date(2027, 6, 9),
        '中秋节': date(2027, 9, 15),
    }
}

# 农历月份天数（2025-2027）
# 格式: [正月, 二月, 三月, 四月, 五月, 六月, 七月, 八月, 九月, 十月, 冬月, 腊月, 闰月]
LUNAR_MONTH_DAYS = {
    2025: [29, 30, 29, 30, 29, 30, 29, 30, 30, 29, 30, 29, 30],  # 闰六月
    2026: [30, 29, 30, 29, 30, 29, 30, 29, 29, 30, 29, 30, 0],   # 无闰月,修正八月为29天
    2027: [29, 30, 29, 30, 29, 30, 29, 30, 29, 30, 30, 29, 0],   # 无闰月
}


def lunar_to_solar(lunar_year: int, lunar_month: int, lunar_day: int, is_leap: bool = False) -> date:
    """农历转公历（简化版）"""
    if not (1 <= lunar_month <= 12):
        raise LunarConversionError(f"Invalid lunar month: {lunar_month}")

    if lunar_year not in KNOWN_FESTIVALS:
        raise LunarConversionError(f"Year {lunar_year} not supported")

    spring_festival = KNOWN_FESTIVALS[lunar_year]['春节']
    month_days = LUNAR_MONTH_DAYS.get(lunar_year, [30, 29, 30, 29, 30, 29, 30, 29, 30, 29, 30, 29, 0])
    leap_month = 6 if lunar_year == 2025 else 0

    days_diff = 0
    for m in range(1, lunar_month):
        days_diff += month_days[m - 1]

    if leap_month > 0 and lunar_month > leap_month:
        days_diff += month_days[12]

    if is_leap:
        if lunar_month != leap_month:
            raise LunarConversionError(f"Month {lunar_month} is not a leap month")
        days_diff += month_days[lunar_month - 1]

    # 验证日期有效性
    month_len = month_days[lunar_month - 1]
    if is_leap:
        month_len = month_days[12] if lunar_year == 2025 else 30
    if not (1 <= lunar_day <= month_len):
        raise LunarConversionError(f"Invalid lunar day: {lunar_day} for month {lunar_month}")

    days_diff += lunar_day - 1
    return spring_festival + timedelta(days=days_diff)


def solar_to_lunar(solar_date: date) -> Tuple[int, int, int, bool]:
    """公历转农历（简化版）"""
    year = solar_date.year

    if year not in KNOWN_FESTIVALS:
        raise LunarConversionError(f"Year {year} not supported")

    spring_festival = KNOWN_FESTIVALS[year]['春节']

    if solar_date < spring_festival:
        year -= 1
        if year not in KNOWN_FESTIVALS:
            raise LunarConversionError(f"Previous year {year} not supported")
        spring_festival = KNOWN_FESTIVALS[year]['春节']

    days_diff = (solar_date - spring_festival).days
    month_days = LUNAR_MONTH_DAYS.get(year, [30, 29, 30, 29, 30, 29, 30, 29, 30, 29, 30, 29, 0])
    leap_month = 6 if year == 2025 else 0

    month = 1
    is_leap = False
    remaining_days = days_diff

    while month <= 12:
        month_len = month_days[month - 1]

        if month == leap_month and remaining_days >= month_len:
            leap_len = month_days[12]
            if remaining_days < month_len + leap_len:
                is_leap = True
                day = remaining_days - month_len + 1
                return (year, month, day, is_leap)

        if remaining_days < month_len:
            day = remaining_days + 1
            return (year, month, day, is_leap)

        remaining_days -= month_len
        month += 1

    raise LunarConversionError(f"Date conversion failed for {solar_date}")


def get_festival_date(festival_name: str, year: int) -> Optional[date]:
    """获取节日公历日期"""
    if year not in KNOWN_FESTIVALS:
        raise LunarConversionError(f"Year {year} not supported")

    festivals = KNOWN_FESTIVALS[year]
    name_map = {
        '春节': '春节', '端午': '端午节', '端午节': '端午节',
        '中秋': '中秋节', '中秋节': '中秋节',
    }

    standard_name = name_map.get(festival_name)
    if not standard_name or standard_name not in festivals:
        raise LunarConversionError(f"Unknown festival: {festival_name}")

    return festivals[standard_name]
