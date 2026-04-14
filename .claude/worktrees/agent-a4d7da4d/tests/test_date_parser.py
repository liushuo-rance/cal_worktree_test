"""
日期解析器测试
测试内容:
1. 单日期格式解析
2. 日期范围解析
3. 边界情况和错误处理
"""

import pytest
from datetime import date


class TestDateParserSingleDate:
    """单日期格式解析测试"""

    def test_standard_format(self):
        """标准格式: 2025.08.15"""
        from src.parsers.date_parser import parse_date
        result = parse_date("2025.08.15")
        assert result == date(2025, 8, 15)

    def test_no_leading_zero_month(self):
        """月份无前导零: 2025.9.18"""
        from src.parsers.date_parser import parse_date
        result = parse_date("2025.9.18")
        assert result == date(2025, 9, 18)

    def test_dash_separator(self):
        """横线分隔: 2025-09-10"""
        from src.parsers.date_parser import parse_date
        result = parse_date("2025-09-10")
        assert result == date(2025, 9, 10)

    def test_slash_separator(self):
        """斜杠分隔: 2025/10/25"""
        from src.parsers.date_parser import parse_date
        result = parse_date("2025/10/25")
        assert result == date(2025, 10, 25)

    def test_chinese_format(self):
        """中文格式: 2025年8月15日"""
        from src.parsers.date_parser import parse_date
        result = parse_date("2025年8月15日")
        assert result == date(2025, 8, 15)

    def test_partial_date_inherit_year(self):
        """缺少年份，从前一条继承"""
        from src.parsers.date_parser import parse_date_with_context
        result = parse_date_with_context("9.10", last_date=date(2025, 8, 15))
        assert result == date(2025, 9, 10)

    def test_partial_date_default_current_year(self):
        """缺少年份且无上下文，使用当前年"""
        from src.parsers.date_parser import parse_date_with_context
        result = parse_date_with_context("9.10", last_date=None)
        assert result.year == date.today().year
        assert result.month == 9
        assert result.day == 10


class TestDateParserRange:
    """日期范围解析测试"""

    def test_same_month_range(self):
        """同月日期范围: 2025.10.27-29"""
        from src.parsers.date_parser import parse_date_range
        start, end = parse_date_range("2025.10.27-29")
        assert start == date(2025, 10, 27)
        assert end == date(2025, 10, 29)

    def test_same_month_with_dash(self):
        """同月日期范围用横线: 2025-10-27~29"""
        from src.parsers.date_parser import parse_date_range
        start, end = parse_date_range("2025-10-27~29")
        assert start == date(2025, 10, 27)
        assert end == date(2025, 10, 29)

    def test_cross_month_range(self):
        """跨月日期范围: 2025.10.27-11.3"""
        from src.parsers.date_parser import parse_date_range
        start, end = parse_date_range("2025.10.27-11.3")
        assert start == date(2025, 10, 27)
        assert end == date(2025, 11, 3)

    def test_cross_month_chinese_separator(self):
        """跨月日期范围用"至": 2025.10.27至11.3"""
        from src.parsers.date_parser import parse_date_range
        start, end = parse_date_range("2025.10.27至11.3")
        assert start == date(2025, 10, 27)
        assert end == date(2025, 11, 3)


class TestDateParserErrors:
    """日期解析错误处理测试"""

    def test_invalid_month(self):
        """无效月份应该报错"""
        from src.parsers.date_parser import parse_date, DateParseError
        with pytest.raises(DateParseError):
            parse_date("2025.13.01")

    def test_invalid_day(self):
        """无效日期应该报错"""
        from src.parsers.date_parser import parse_date, DateParseError
        with pytest.raises(DateParseError):
            parse_date("2025.02.30")

    def test_invalid_format(self):
        """无法识别的格式应该报错"""
        from src.parsers.date_parser import parse_date, DateParseError
        with pytest.raises(DateParseError):
            parse_date("invalid date")

    def test_empty_string(self):
        """空字符串应该报错"""
        from src.parsers.date_parser import parse_date, DateParseError
        with pytest.raises(DateParseError):
            parse_date("")


class TestDateExtractor:
    """从行文本中提取日期测试"""

    def test_extract_date_from_line(self):
        """从完整行中提取日期"""
        from src.parsers.date_parser import extract_date_from_line
        date_part, remaining = extract_date_from_line("2025.08.15，下午请假回老家")
        assert date_part == "2025.08.15"
        assert remaining == "下午请假回老家"

    def test_extract_date_range_from_line(self):
        """从完整行中提取日期范围"""
        from src.parsers.date_parser import extract_date_from_line
        date_part, remaining = extract_date_from_line("2025.10.27-29，请假三天")
        assert date_part == "2025.10.27-29"
        assert remaining == "请假三天"

    def test_no_date_in_line(self):
        """行中无日期应该返回None"""
        from src.parsers.date_parser import extract_date_from_line
        result = extract_date_from_line("下午请假回老家")
        assert result is None

    def test_end_date_before_start(self):
        """结束日期在开始日期之前应该报错"""
        from src.parsers.date_parser import parse_date_range, DateParseError
        with pytest.raises(DateParseError):
            parse_date_range("2025.10.29-27")  # 29日到27日

    def test_invalid_partial_date(self):
        """无效的部分日期应该报错"""
        from src.parsers.date_parser import parse_partial_date, DateParseError
        with pytest.raises(DateParseError):
            parse_partial_date("13.45", 2025)  # 13月无效

    def test_cross_month_invalid_day(self):
        """跨月范围无效日期应该报错"""
        from src.parsers.date_parser import parse_date_range, DateParseError
        with pytest.raises(DateParseError):
            parse_date_range("2025.02.27-03.32")  # 32日无效

    def test_extract_only_date_no_content(self):
        """提取日期后无内容的情况"""
        from src.parsers.date_parser import extract_date_from_line
        result = extract_date_from_line("2025.08.15")
        assert result is None  # 没有分隔符和后续内容
