"""
时间工具函数
提供时间转换、工作时间判断、加班计算等功能
"""

from datetime import time
from enum import Enum


class TimePeriod(Enum):
    """时间段类型"""
    WORK_TIME = "work_time"              # 正常工作时间
    WEEKDAY_MORNING = "weekday_morning"  # 工作日早晨加班 (08:30之前)
    WEEKDAY_LUNCH = "weekday_lunch"      # 工作日午休加班 (12:00-13:00)
    WEEKDAY_EVENING = "weekday_evening"  # 工作日晚间加班 (17:30之后)
    WEEKEND = "weekend"                  # 周末
    HOLIDAY = "holiday"                  # 法定节假日
    LUNCH = "lunch"                      # 午休时间


# 工作时间定义
WORK_SCHEDULE = {
    "morning_start": time(8, 30),
    "morning_end": time(12, 0),
    "afternoon_start": time(13, 0),
    "afternoon_end": time(17, 30),
}


def hours_minutes_to_total_minutes(hours: int, minutes: int) -> int:
    """
    将小时和分钟转换为总分钟数
    自动处理分钟进位（如90分钟=1小时30分钟）

    Args:
        hours: 小时数（可以为0，但不能为负）
        minutes: 分钟数（可以为0，支持>=60自动进位）

    Returns:
        总分钟数
    """
    if hours < 0:
        raise ValueError("hours cannot be negative")
    if minutes < 0:
        raise ValueError("minutes cannot be negative")

    return hours * 60 + minutes


def total_minutes_to_hours_minutes(total_minutes: int) -> tuple[int, int]:
    """
    将总分钟数转换为小时和分钟

    Args:
        total_minutes: 总分钟数

    Returns:
        (小时, 分钟) 元组
    """
    if total_minutes < 0:
        raise ValueError("total_minutes cannot be negative")

    hours = total_minutes // 60
    minutes = total_minutes % 60
    return (hours, minutes)


def validate_time_duration(hours: int, minutes: int) -> None:
    """
    验证时长是否有效
    所有时间值必须为正数，且分钟在0-59范围内

    Args:
        hours: 小时数
        minutes: 分钟数

    Raises:
        ValueError: 验证失败时抛出
    """
    if hours < 0:
        raise ValueError("hours cannot be negative")
    if minutes < 0:
        raise ValueError("minutes cannot be negative")
    if minutes >= 60:
        raise ValueError("minutes must be between 0 and 59")
    if hours == 0 and minutes == 0:
        raise ValueError("duration must be greater than 0")


def is_work_time(t: time) -> bool:
    """
    判断给定时间是否在工作时间内
    工作时间: 08:30-12:00, 13:00-17:30

    Args:
        t: 要判断的时间

    Returns:
        是否在工作时间内
    """
    morning_start = WORK_SCHEDULE["morning_start"]
    morning_end = WORK_SCHEDULE["morning_end"]
    afternoon_start = WORK_SCHEDULE["afternoon_start"]
    afternoon_end = WORK_SCHEDULE["afternoon_end"]

    # 上午工作时间: 08:30 <= t <= 12:00
    if morning_start <= t <= morning_end:
        return True

    # 下午工作时间: 13:00 <= t <= 17:30
    if afternoon_start <= t <= afternoon_end:
        return True

    return False


def get_time_period(t: time) -> TimePeriod | str:
    """
    获取给定时间所属的时间段类型

    Args:
        t: 要判断的时间

    Returns:
        时间段类型枚举值
    """
    morning_start = WORK_SCHEDULE["morning_start"]
    morning_end = WORK_SCHEDULE["morning_end"]
    afternoon_start = WORK_SCHEDULE["afternoon_start"]
    afternoon_end = WORK_SCHEDULE["afternoon_end"]

    # 早晨加班: 08:30之前
    if t < morning_start:
        return TimePeriod.WEEKDAY_MORNING

    # 午休时间: 12:00-13:00
    if morning_end < t < afternoon_start:
        return TimePeriod.LUNCH

    # 午休加班 (精确在午休时段内)
    if morning_end <= t <= afternoon_start:
        if t == morning_end or t == afternoon_start:
            # 边界点算作午休时段
            return TimePeriod.LUNCH
        return TimePeriod.WEEKDAY_LUNCH

    # 晚间加班: 17:30之后
    if t > afternoon_end:
        return TimePeriod.WEEKDAY_EVENING

    # 工作时间
    if morning_start <= t <= morning_end or afternoon_start <= t <= afternoon_end:
        return TimePeriod.WORK_TIME

    # 默认
    return TimePeriod.WORK_TIME


def calculate_overtime_hours(
    start_time: time,
    end_time: time,
    include_lunch: bool = False
) -> tuple[int, int, int]:
    """
    计算加班时长
    根据工作时间规则，只计算标准工作时间之外的时段

    Args:
        start_time: 开始时间
        end_time: 结束时间
        include_lunch: 是否计算午休时段（默认False，跨工作时间时不计算午休）

    Returns:
        (小时, 分钟, 总分钟数) 元组
    """
    morning_start = WORK_SCHEDULE["morning_start"]
    morning_end = WORK_SCHEDULE["morning_end"]
    afternoon_start = WORK_SCHEDULE["afternoon_start"]
    afternoon_end = WORK_SCHEDULE["afternoon_end"]

    total_overtime_minutes = 0

    # 将时间转换为分钟数便于计算
    def time_to_minutes(t: time) -> int:
        return t.hour * 60 + t.minute

    start_min = time_to_minutes(start_time)
    end_min = time_to_minutes(end_time)

    morning_start_min = time_to_minutes(morning_start)
    morning_end_min = time_to_minutes(morning_end)
    afternoon_start_min = time_to_minutes(afternoon_start)
    afternoon_end_min = time_to_minutes(afternoon_end)

    # 计算早晨加班 (开始时间到08:30)
    if start_min < morning_start_min:
        # 结束时间早于08:30，全部算早晨加班；否则只算到08:30
        if end_min <= morning_start_min:
            total_overtime_minutes += end_min - start_min
        else:
            total_overtime_minutes += morning_start_min - start_min

    # 计算午休加班 (12:00-13:00之间的部分)
    # 只有当明确指定include_lunch=True时才计算（如"中午12:30-13:00加班"）
    if include_lunch and end_min > morning_end_min and start_min < afternoon_start_min:
        lunch_start = max(start_min, morning_end_min)
        lunch_end = min(end_min, afternoon_start_min)
        if lunch_end > lunch_start:
            total_overtime_minutes += lunch_end - lunch_start

    # 计算晚间加班 (17:30之后)
    if end_min > afternoon_end_min:
        # 开始时间晚于17:30，全部算晚间加班；否则只算17:30之后的部分
        if start_min >= afternoon_end_min:
            total_overtime_minutes += end_min - start_min
        else:
            total_overtime_minutes += end_min - afternoon_end_min

    # 转换为时分格式
    hours, minutes = total_minutes_to_hours_minutes(total_overtime_minutes)
    return (hours, minutes, total_overtime_minutes)
