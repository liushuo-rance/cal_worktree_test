"""
节假日通知解析器测试
测试内容:
1. 节假日条目解析
2. 调休上班日识别
3. 完整通知文本解析
4. 错误处理
"""

import pytest
from datetime import date


class TestHolidayItemParsing:
    """单条节假日解析测试"""

    def test_new_year_holiday(self):
        """元旦假期解析"""
        from src.parsers.holiday_notification_parser import parse_holiday_item
        result = parse_holiday_item("元旦：1月1日（周四）至3日（周六）放假调休，共3天。1月4日（周日）上班。")

        assert result['name'] == '元旦'
        assert result['start_date'] == date(2026, 1, 1)
        assert result['end_date'] == date(2026, 1, 3)
        assert result['statutory_days'] == [date(2026, 1, 1)]  # 元旦当天法定
        assert result['adjusted_workdays'] == [date(2026, 1, 4)]

    def test_labor_day_holiday(self):
        """劳动节假期解析"""
        from src.parsers.holiday_notification_parser import parse_holiday_item
        result = parse_holiday_item("劳动节：5月1日（周五）至5日（周二）放假调休，共5天。5月9日（周六）上班。")

        assert result['name'] == '劳动节'
        assert result['start_date'] == date(2026, 5, 1)
        assert result['end_date'] == date(2026, 5, 5)
        assert date(2026, 5, 1) in result['statutory_days']  # 5.1法定
        assert result['adjusted_workdays'] == [date(2026, 5, 9)]

    def test_national_day_holiday(self):
        """国庆节假期解析"""
        from src.parsers.holiday_notification_parser import parse_holiday_item
        result = parse_holiday_item("国庆节：10月1日（周四）至7日（周三）放假调休，共7天。9月20日（周日）、10月10日（周六）上班。")

        assert result['name'] == '国庆节'
        assert result['start_date'] == date(2026, 10, 1)
        assert result['end_date'] == date(2026, 10, 7)
        assert date(2026, 10, 1) in result['statutory_days']
        assert date(2026, 10, 2) in result['statutory_days']
        assert date(2026, 10, 3) in result['statutory_days']
        assert result['adjusted_workdays'] == [date(2026, 9, 20), date(2026, 10, 10)]

    def test_single_day_holiday(self):
        """单日假期解析（如清明）"""
        from src.parsers.holiday_notification_parser import parse_holiday_item
        result = parse_holiday_item("清明节：4月4日（周六）至6日（周一）放假，共3天。")

        assert result['name'] == '清明节'
        assert result['start_date'] == date(2026, 4, 4)
        assert result['end_date'] == date(2026, 4, 6)
        assert result['statutory_days'] == [date(2026, 4, 4)]  # 清明当天法定
        assert result['adjusted_workdays'] == []


class TestFullNotificationParsing:
    """完整通知文本解析测试"""

    @pytest.fixture
    def sample_notification_2026(self):
        return """国务院办公厅关于2026年部分节假日安排的通知发布：
一、元旦：1月1日（周四）至3日（周六）放假调休，共3天。1月4日（周日）上班。
二、春节：2月15日（农历腊月二十八、周日）至23日（农历正月初七、周一）放假调休，共9天。2月14日（周六）、2月28日（周六）上班。
三、清明节：4月4日（周六）至6日（周一）放假，共3天。
四、劳动节：5月1日（周五）至5日（周二）放假调休，共5天。5月9日（周六）上班。
五、端午节：6月19日（周五）至21日（周日）放假，共3天。
六、中秋节：9月25日（周五）至27日（周日）放假，共3天。
七、国庆节：10月1日（周四）至7日（周三）放假调休，共7天。9月20日（周日）、10月10日（周六）上班。"""

    def test_parse_full_notification(self, sample_notification_2026):
        """解析完整通知文本"""
        from src.parsers.holiday_notification_parser import parse_notification
        holidays = parse_notification(sample_notification_2026, year=2026)

        assert len(holidays) == 7

        # 验证元旦
        new_year = next(h for h in holidays if h['name'] == '元旦')
        assert new_year['start_date'] == date(2026, 1, 1)

        # 验证春节
        spring = next(h for h in holidays if h['name'] == '春节')
        assert spring['start_date'] == date(2026, 2, 15)

    def test_extract_holiday_dates(self, sample_notification_2026):
        """提取所有节假日日期"""
        from src.parsers.holiday_notification_parser import extract_all_holiday_dates
        dates = extract_all_holiday_dates(sample_notification_2026, year=2026)

        # 应该包含所有节假日和调休上班日
        assert date(2026, 1, 1) in dates  # 元旦
        assert date(2026, 1, 4) in dates  # 调休上班
        assert date(2026, 5, 1) in dates  # 劳动节
        assert date(2026, 5, 9) in dates  # 调休上班


class TestStatutoryHolidayIdentification:
    """法定节假日识别测试"""

    def test_new_year_statutory(self):
        """元旦法定1天"""
        from src.parsers.holiday_notification_parser import get_statutory_holidays
        result = get_statutory_holidays("元旦", date(2026, 1, 1), date(2026, 1, 3))
        assert result == [date(2026, 1, 1)]

    def test_labor_day_statutory(self):
        """劳动节法定1天"""
        from src.parsers.holiday_notification_parser import get_statutory_holidays
        result = get_statutory_holidays("劳动节", date(2026, 5, 1), date(2026, 5, 5))
        assert result == [date(2026, 5, 1)]

    def test_national_day_statutory(self):
        """国庆节法定3天"""
        from src.parsers.holiday_notification_parser import get_statutory_holidays
        result = get_statutory_holidays("国庆节", date(2026, 10, 1), date(2026, 10, 7))
        assert result == [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)]

    def test_spring_festival_statutory(self):
        """春节法定3天（除夕、初一、初二）"""
        from src.parsers.holiday_notification_parser import get_statutory_holidays
        # 2026年春节：2月15日（腊月二十八）至23日（正月初七）
        # 法定应该是除夕(2/17)、初一(2/18)、初二(2/19)
        result = get_statutory_holidays("春节", date(2026, 2, 15), date(2026, 2, 23))
        assert date(2026, 2, 17) in result  # 除夕
        assert date(2026, 2, 18) in result  # 初一
        assert date(2026, 2, 19) in result  # 初二


class TestAdjustedWorkdayExtraction:
    """调休上班日提取测试"""

    def test_single_adjusted_workday(self):
        """单个调休上班日"""
        from src.parsers.holiday_notification_parser import extract_adjusted_workdays
        result = extract_adjusted_workdays("1月4日（周日）上班。", year=2026)
        assert result == [date(2026, 1, 4)]

    def test_multiple_adjusted_workdays(self):
        """多个调休上班日"""
        from src.parsers.holiday_notification_parser import extract_adjusted_workdays
        result = extract_adjusted_workdays("2月14日（周六）、2月28日（周六）上班。", year=2026)
        assert result == [date(2026, 2, 14), date(2026, 2, 28)]


class TestParserErrors:
    """解析错误处理测试"""

    def test_empty_notification(self):
        """空通知文本"""
        from src.parsers.holiday_notification_parser import parse_notification
        result = parse_notification("", year=2026)
        assert result == []

    def test_invalid_holiday_item(self):
        """无法识别的节假日条目"""
        from src.parsers.holiday_notification_parser import parse_holiday_item, ParseError
        with pytest.raises(ParseError):
            parse_holiday_item("无效的节假日描述")
