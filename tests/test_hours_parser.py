"""
时长解析器测试
测试内容:
1. 直接时长解析
2. 关键词时长解析（半天/一天）
3. 时间段计算
4. 边界情况和错误处理
"""

import pytest


class TestDirectHoursParsing:
    """直接时长解析测试"""

    def test_decimal_hours(self):
        """小数小时: 3.5小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("3.5小时")
        assert result == (3, 30, 210)  # hours, minutes, total_minutes

    def test_integer_hours(self):
        """整数小时: 4小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("4小时")
        assert result == (4, 0, 240)

    def test_hours_and_minutes(self):
        """时分格式: 1小时30分钟"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("1小时30分钟")
        assert result == (1, 30, 90)

    def test_only_minutes(self):
        """仅分钟: 45分钟"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("45分钟")
        assert result == (0, 45, 45)


class TestKeywordHoursParsing:
    """关键词时长解析测试"""

    def test_half_day(self):
        """半天 = 4小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("半天")
        assert result == (4, 0, 240)

    def test_full_day(self):
        """一天 = 8小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("一天")
        assert result == (8, 0, 480)

    def test_multi_days(self):
        """多天 = 天数 × 8小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("三天")
        assert result == (24, 0, 1440)

    def test_chinese_number_days(self):
        """中文数字天数"""
        from src.parsers.hours_parser import parse_hours
        assert parse_hours("一天") == (8, 0, 480)
        assert parse_hours("两天") == (16, 0, 960)
        assert parse_hours("五天") == (40, 0, 2400)

    def test_arabic_number_days(self):
        """阿拉伯数字天数: 3天"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("3天")
        assert result == (24, 0, 1440)

    def test_two_days_variant(self):
        """中文数字"两"天"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("两天")
        assert result == (16, 0, 960)


class TestTimeRangeParsing:
    """时间段计算测试"""

    def test_explicit_hours(self):
        """明确指定时长: 共15小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("早7到晚10共15小时")
        assert result == (15, 0, 900)

    def test_night_overtime(self):
        """晚间加班描述"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("晚上3.5小时")
        assert result == (3, 30, 210)

    def test_morning_overtime(self):
        """早晨加班描述"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("早7点到岗")
        # 从描述中无法直接计算时长，应返回None或需要额外信息
        assert result is None

    def test_time_range_morning_to_night(self):
        """早7到晚10自动计算15小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("2025.10.25，早7到晚10共15小时")
        assert result == (15, 0, 900)

    def test_time_range_digital_24h(self):
        """数字时间范围 18:00-20:00 = 2小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("晚上18:00-20:00")
        assert result == (2, 0, 120)

    def test_time_range_am_pm(self):
        """上午到下午时间范围 8点至17点 = 9小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("上午8点至下午5点")
        assert result == (9, 0, 540)

    def test_time_range_with_minutes(self):
        """带分钟的时间范围 7:30-22:30 = 15小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("早7:30到晚10:30")
        assert result == (15, 0, 900)

    def test_time_range_full_words(self):
        """完整中文描述 早上7点到晚上10点 = 15小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("早上7点到晚上10点")
        assert result == (15, 0, 900)

    def test_time_range_noon(self):
        """跨中午 上午9点到下午6点 = 9小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("上午9点到下午6点")
        assert result == (9, 0, 540)

    def test_time_range_short_ampm(self):
        """简写早晚 早8点-晚6点 = 10小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("早8点-晚6点")
        assert result == (10, 0, 600)

    def test_time_range_digital_tilde(self):
        """波浪线分隔 07:00~22:00 = 15小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("07:00~22:00")
        assert result == (15, 0, 900)

    def test_time_range_mixed_night(self):
        """晚间时段 晚上19:00到21:00 = 2小时"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("晚上19:00到21:00")
        assert result == (2, 0, 120)


class TestHoursParserErrors:
    """时长解析错误处理测试"""

    def test_invalid_format(self):
        """无法识别的格式"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("抵消了")
        assert result is None

    def test_empty_string(self):
        """空字符串"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("")
        assert result is None

    def test_no_hours_info(self):
        """无时长信息"""
        from src.parsers.hours_parser import parse_hours
        result = parse_hours("下午请假")
        assert result is None


class TestDurationExtraction:
    """从行文本中提取时长测试"""

    def test_extract_hours_from_line(self):
        """从完整行中提取时长"""
        from src.parsers.hours_parser import extract_duration_text
        result = extract_duration_text("2025.08.15，晚上3.5小时")
        assert result == "晚上3.5小时"

    def test_extract_days_from_line(self):
        """从行中提取天数"""
        from src.parsers.hours_parser import extract_duration_text
        result = extract_duration_text("2025.10.27-29，请假三天")
        assert result == "请假三天"

    def test_no_duration_in_line(self):
        """行中无时长信息"""
        from src.parsers.hours_parser import extract_duration_text
        result = extract_duration_text("2025.08.15，下午请假回老家")
        assert result is None

    def test_extract_from_chinese_date_line(self):
        """从中文日期格式行中提取时长"""
        from src.parsers.hours_parser import extract_duration_text
        result = extract_duration_text("2025年8月15日，晚上3.5小时")
        assert result == "晚上3.5小时"

    def test_extract_empty_line(self):
        """空字符串提取"""
        from src.parsers.hours_parser import extract_duration_text
        result = extract_duration_text("")
        assert result is None
