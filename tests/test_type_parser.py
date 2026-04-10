"""
类型识别器测试
测试内容:
1. 加班类型识别
2. 请假类型识别
3. 调休类型识别
4. 置信度计算
"""

class TestOvertimeTypeRecognition:
    """加班类型识别测试"""

    def test_evening_overtime(self):
        """晚间加班: 晚上X小时"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("晚上3.5小时")
        assert result['type'] == 'overtime'
        assert result['overtime_type'] == 'weekday_evening'
        assert result['confidence'] >= 0.8

    def test_morning_overtime(self):
        """早晨加班: 早X点到岗"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("早7点到岗")
        assert result['type'] == 'overtime'
        assert result['overtime_type'] == 'weekday_morning'
        assert result['confidence'] >= 0.8

    def test_lunch_overtime(self):
        """午休加班: 中午X点加班"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("中午12:30加班")
        assert result['type'] == 'overtime'
        assert result['overtime_type'] == 'weekday_lunch'
        assert result['confidence'] >= 0.8

    def test_time_range_overtime(self):
        """时间范围加班: 早X到晚Y"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("早7到晚10共15小时")
        assert result['type'] == 'overtime'
        assert result['confidence'] >= 0.8


class TestLeaveTypeRecognition:
    """请假类型识别测试"""

    def test_personal_leave(self):
        """事假识别"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("请假半天")
        assert result['type'] == 'leave'
        assert result['leave_type'] == 'personal'
        assert result['confidence'] >= 0.9

    def test_sick_leave(self):
        """病假识别"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("病假一天")
        assert result['type'] == 'leave'
        assert result['leave_type'] == 'sick'
        assert result['confidence'] >= 0.9

    def test_annual_leave(self):
        """年假识别"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("年假三天")
        assert result['type'] == 'leave'
        assert result['leave_type'] == 'annual'
        assert result['confidence'] >= 0.9


class TestCompOffRecognition:
    """调休类型识别测试"""

    def test_comp_off(self):
        """调休识别"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("调休三天")
        assert result['type'] == 'comp_off'
        assert result['confidence'] >= 0.9

    def test_comp_off_half_day(self):
        """调休半天"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("调休半天")
        assert result['type'] == 'comp_off'
        assert result['confidence'] >= 0.9


class TestReferenceOnlyRecognition:
    """仅参考类型识别测试"""

    def test_balance_declaration(self):
        """累计声明识别"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("累计48.5小时")
        assert result['type'] == 'reference_only'
        assert result['confidence'] >= 0.6


class TestUnknownType:
    """未知类型识别测试"""

    def test_unknown_type(self):
        """无法识别的类型"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("抵消了")
        assert result['type'] == 'unknown'
        assert result['confidence'] < 0.7

    def test_empty_string(self):
        """空字符串"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("")
        assert result['type'] == 'unknown'


class TestConfidenceCalculation:
    """置信度计算测试"""

    def test_high_confidence_leave(self):
        """请假类型应有高置信度"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("请假半天回老家")
        assert result['confidence'] >= 0.9

    def test_medium_confidence_overtime(self):
        """模糊加班描述应有中等置信度"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("午餐会1小时")
        # 边界情况，置信度可能较低
        assert result['confidence'] < 0.9

    def test_low_confidence_unknown(self):
        """无法识别应有低置信度"""
        from src.parsers.type_parser import classify_record_type
        result = classify_record_type("一些无关的文本")
        assert result['confidence'] < 0.7
