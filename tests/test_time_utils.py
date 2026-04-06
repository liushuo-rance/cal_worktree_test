"""
时间工具函数测试
测试内容:
1. 时分与总分钟数互转
2. 工作时间判断
3. 加班时段分类
"""

import pytest
from datetime import time, datetime


class TestTimeConversion:
    """时间转换测试"""

    def test_hours_minutes_to_total_minutes_normal(self):
        """正常时分转总分钟数"""
        from src.utils.time_utils import hours_minutes_to_total_minutes
        assert hours_minutes_to_total_minutes(3, 30) == 210
        assert hours_minutes_to_total_minutes(2, 0) == 120
        assert hours_minutes_to_total_minutes(0, 45) == 45

    def test_hours_minutes_with_carry(self):
        """分钟超过60，自动进位"""
        from src.utils.time_utils import hours_minutes_to_total_minutes
        assert hours_minutes_to_total_minutes(2, 90) == 210  # 2h90m = 3h30m
        assert hours_minutes_to_total_minutes(0, 150) == 150  # 0h150m = 2h30m

    def test_total_minutes_to_hours_minutes(self):
        """总分钟数转时分"""
        from src.utils.time_utils import total_minutes_to_hours_minutes
        assert total_minutes_to_hours_minutes(210) == (3, 30)
        assert total_minutes_to_hours_minutes(120) == (2, 0)
        assert total_minutes_to_hours_minutes(45) == (0, 45)
        assert total_minutes_to_hours_minutes(0) == (0, 0)

    def test_time_conversion_roundtrip(self):
        """转换双向验证"""
        from src.utils.time_utils import (
            hours_minutes_to_total_minutes,
            total_minutes_to_hours_minutes
        )
        for hours, minutes in [(3, 30), (0, 45), (24, 0), (0, 0)]:
            total = hours_minutes_to_total_minutes(hours, minutes)
            back_hours, back_minutes = total_minutes_to_hours_minutes(total)
            assert back_hours == hours
            assert back_minutes == minutes


class TestWorkHoursCheck:
    """工作时间判断测试"""

    def test_morning_work_time(self):
        """上午工作时间: 08:30-12:00"""
        from src.utils.time_utils import is_work_time, get_time_period, TimePeriod

        # 工作时间内的时刻
        assert is_work_time(time(8, 30)) is True
        assert is_work_time(time(10, 0)) is True
        assert is_work_time(time(12, 0)) is True

        # 工作时间外的时刻
        assert is_work_time(time(8, 0)) is False
        assert is_work_time(time(8, 29)) is False

        # 时段判断 - 上午工作时间返回 WORK_TIME
        assert get_time_period(time(10, 0)) == TimePeriod.WORK_TIME

    def test_afternoon_work_time(self):
        """下午工作时间: 13:00-17:30"""
        from src.utils.time_utils import is_work_time, get_time_period, TimePeriod

        # 工作时间内的时刻
        assert is_work_time(time(13, 0)) is True
        assert is_work_time(time(15, 30)) is True
        assert is_work_time(time(17, 30)) is True

        # 工作时间外的时刻
        assert is_work_time(time(12, 30)) is False
        assert is_work_time(time(18, 0)) is False

        # 时段判断 - 下午工作时间返回 WORK_TIME
        assert get_time_period(time(15, 0)) == TimePeriod.WORK_TIME

    def test_lunch_break_not_work_time(self):
        """午休时间: 12:00-13:00 不算工作时间"""
        from src.utils.time_utils import is_work_time, get_time_period, TimePeriod

        # 12:00 是上午工作结束时间，属于工作时间
        assert is_work_time(time(12, 0)) is True
        # 午休期间不算工作时间
        assert is_work_time(time(12, 30)) is False
        # 13:00 是下午工作开始时间，属于工作时间
        assert is_work_time(time(13, 0)) is True

        # 午休时段返回 LUNCH
        assert get_time_period(time(12, 30)) == TimePeriod.LUNCH

    def test_overtime_periods(self):
        """加班时段判断"""
        from src.utils.time_utils import get_time_period, TimePeriod

        # 早晨加班: 08:30之前
        assert get_time_period(time(7, 0)) == TimePeriod.WEEKDAY_MORNING
        assert get_time_period(time(8, 0)) == TimePeriod.WEEKDAY_MORNING

        # 午休时间: 12:00-13:00 返回 LUNCH
        assert get_time_period(time(12, 30)) == TimePeriod.LUNCH

        # 晚间加班: 17:30之后
        assert get_time_period(time(18, 0)) == TimePeriod.WEEKDAY_EVENING
        assert get_time_period(time(20, 0)) == TimePeriod.WEEKDAY_EVENING

        # 工作时间
        assert get_time_period(time(10, 0)) == TimePeriod.WORK_TIME
        assert get_time_period(time(15, 0)) == TimePeriod.WORK_TIME


class TestOvertimeCalculation:
    """加班时长计算测试"""

    def test_calculate_overtime_from_period(self):
        """从时间段计算加班时长"""
        from src.utils.time_utils import calculate_overtime_hours

        # 早晨加班: 07:00-08:30 = 1.5h
        result = calculate_overtime_hours(time(7, 0), time(8, 30))
        assert result == (1, 30, 90)  # hours, minutes, total_minutes

        # 晚间加班: 17:30-20:00 = 2.5h
        result = calculate_overtime_hours(time(17, 30), time(20, 0))
        assert result == (2, 30, 150)

        # 午休加班: 12:30-13:00 = 0.5h（需要明确指定include_lunch=True）
        result = calculate_overtime_hours(time(12, 30), time(13, 0), include_lunch=True)
        assert result == (0, 30, 30)

    def test_cross_work_hours_calculation(self):
        """跨工作时间的加班计算"""
        from src.utils.time_utils import calculate_overtime_hours

        # 早7到晚10，只计算加班时段
        # 07:00-08:30 (1.5h) + 17:30-22:00 (4.5h) = 6h
        result = calculate_overtime_hours(time(7, 0), time(22, 0))
        assert result == (6, 0, 360)


class TestValidation:
    """输入验证测试"""

    def test_negative_hours_rejected(self):
        """负小时数应该被拒绝"""
        from src.utils.time_utils import validate_time_duration

        with pytest.raises(ValueError, match="hours cannot be negative"):
            validate_time_duration(-1, 30)

    def test_negative_minutes_rejected(self):
        """负分钟数应该被拒绝"""
        from src.utils.time_utils import validate_time_duration

        with pytest.raises(ValueError, match="minutes cannot be negative"):
            validate_time_duration(1, -30)

    def test_minutes_out_of_range_rejected(self):
        """分钟数超过59应该被拒绝"""
        from src.utils.time_utils import validate_time_duration

        with pytest.raises(ValueError, match="minutes must be between 0 and 59"):
            validate_time_duration(1, 60)

    def test_zero_duration_rejected(self):
        """零时长应该被拒绝"""
        from src.utils.time_utils import validate_time_duration

        with pytest.raises(ValueError, match="duration must be greater than 0"):
            validate_time_duration(0, 0)

    def test_valid_duration_accepted(self):
        """有效时长应该通过验证"""
        from src.utils.time_utils import validate_time_duration

        # 不应该抛出异常
        validate_time_duration(1, 30)
        validate_time_duration(0, 45)
        validate_time_duration(8, 0)
