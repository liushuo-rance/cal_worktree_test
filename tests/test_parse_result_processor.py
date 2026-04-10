"""
解析结果处理器测试
测试内容:
1. 置信度分级（HIGH/MEDIUM/LOW）
2. 异常记录标记
3. 解析结果验证
"""

from datetime import date


class TestConfidenceClassification:
    """置信度分级测试"""

    def test_high_confidence_overtime(self):
        """高置信度加班记录"""
        from src.services.parse_result_processor import classify_confidence_level

        result = {
            'type': 'overtime',
            'parsed_date': date(2026, 1, 15),
            'parsed_hours': 3.5,
            'overtime_type': 'weekday_evening',
            'confidence': 0.95
        }

        level = classify_confidence_level(result)
        assert level == 'HIGH'

    def test_high_confidence_leave(self):
        """高置信度请假记录"""
        from src.services.parse_result_processor import classify_confidence_level

        result = {
            'type': 'leave',
            'parsed_date': date(2026, 1, 15),
            'parsed_hours': 4.0,
            'leave_type': 'personal',
            'confidence': 0.92
        }

        level = classify_confidence_level(result)
        assert level == 'HIGH'

    def test_medium_confidence_partial_parse(self):
        """中等置信度（部分解析成功）"""
        from src.services.parse_result_processor import classify_confidence_level

        result = {
            'type': 'overtime',
            'parsed_date': date(2026, 1, 15),
            'parsed_hours': None,  # 未解析出时长
            'overtime_type': 'weekday_evening',
            'confidence': 0.75
        }

        level = classify_confidence_level(result)
        assert level == 'MEDIUM'

    def test_medium_confidence_low_confidence_score(self):
        """中等置信度（置信度分数中等）"""
        from src.services.parse_result_processor import classify_confidence_level

        result = {
            'type': 'overtime',
            'parsed_date': date(2026, 1, 15),
            'parsed_hours': 2.0,
            'overtime_type': 'weekday_evening',
            'confidence': 0.65
        }

        level = classify_confidence_level(result)
        assert level == 'MEDIUM'

    def test_low_confidence_unknown_type(self):
        """低置信度（未知类型）"""
        from src.services.parse_result_processor import classify_confidence_level

        result = {
            'type': 'unknown',
            'parsed_date': None,
            'parsed_hours': None,
            'confidence': 0.45
        }

        level = classify_confidence_level(result)
        assert level == 'LOW'

    def test_low_confidence_no_date(self):
        """低置信度（无日期）"""
        from src.services.parse_result_processor import classify_confidence_level

        result = {
            'type': 'overtime',
            'parsed_date': None,
            'parsed_hours': 3.0,
            'overtime_type': 'weekday_evening',
            'confidence': 0.55
        }

        level = classify_confidence_level(result)
        assert level == 'LOW'


class TestAnomalyDetection:
    """异常检测测试"""

    def test_anomaly_excessive_hours(self):
        """异常：加班时长过长（超过12小时）"""
        from src.services.parse_result_processor import detect_anomalies

        result = {
            'type': 'overtime',
            'parsed_date': date(2026, 1, 15),
            'parsed_hours': 15.0,
            'overtime_type': 'weekday_evening'
        }

        anomalies = detect_anomalies(result)
        assert len(anomalies) > 0
        assert any('时长' in a or 'hours' in a.lower() for a in anomalies)

    def test_anomaly_weekend_workday_type(self):
        """异常：周末但标记为工作日加班"""
        from src.services.parse_result_processor import detect_anomalies

        result = {
            'type': 'overtime',
            'parsed_date': date(2026, 1, 10),  # 周六
            'parsed_hours': 3.0,
            'overtime_type': 'weekday_evening'  # 错误标记
        }

        anomalies = detect_anomalies(result)
        assert len(anomalies) > 0

    def test_anomaly_future_date(self):
        """异常：未来日期"""
        from src.services.parse_result_processor import detect_anomalies

        result = {
            'type': 'overtime',
            'parsed_date': date(2027, 12, 31),  # 未来日期
            'parsed_hours': 3.0,
            'overtime_type': 'weekday_evening'
        }

        anomalies = detect_anomalies(result)
        assert len(anomalies) > 0
        assert any('未来' in a or 'future' in a.lower() for a in anomalies)

    def test_no_anomaly_normal(self):
        """正常记录无异常"""
        from src.services.parse_result_processor import detect_anomalies

        result = {
            'type': 'overtime',
            'parsed_date': date(2026, 1, 15),
            'parsed_hours': 3.0,
            'overtime_type': 'weekday_evening'
        }

        anomalies = detect_anomalies(result)
        assert len(anomalies) == 0


class TestParseResultValidation:
    """解析结果验证测试"""

    def test_validate_complete_result(self):
        """验证完整的解析结果"""
        from src.services.parse_result_processor import validate_parse_result

        result = {
            'type': 'overtime',
            'parsed_date': date(2026, 1, 15),
            'parsed_hours': 3.5,
            'overtime_type': 'weekday_evening',
            'raw_text': '2026.1.15 晚上3.5小时',
            'confidence': 0.9
        }

        is_valid, errors = validate_parse_result(result)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_missing_type(self):
        """验证失败：缺少类型"""
        from src.services.parse_result_processor import validate_parse_result

        result = {
            'parsed_date': date(2026, 1, 15),
            'parsed_hours': 3.5,
            'confidence': 0.9
        }

        is_valid, errors = validate_parse_result(result)
        assert is_valid is False
        assert any('type' in e.lower() for e in errors)

    def test_validate_missing_date(self):
        """验证失败：缺少日期"""
        from src.services.parse_result_processor import validate_parse_result

        result = {
            'type': 'overtime',
            'parsed_hours': 3.5,
            'confidence': 0.9
        }

        is_valid, errors = validate_parse_result(result)
        assert is_valid is False
        assert any('date' in e.lower() or '日期' in e for e in errors)

    def test_validate_negative_hours(self):
        """验证失败：负时长"""
        from src.services.parse_result_processor import validate_parse_result

        result = {
            'type': 'overtime',
            'parsed_date': date(2026, 1, 15),
            'parsed_hours': -2.0,
            'confidence': 0.9
        }

        is_valid, errors = validate_parse_result(result)
        assert is_valid is False


class TestProcessParseResults:
    """批量处理解析结果测试"""

    def test_process_multiple_results(self):
        """处理多条解析结果"""
        from src.services.parse_result_processor import process_parse_results

        results = [
            {
                'id': 1,
                'type': 'overtime',
                'parsed_date': date(2026, 1, 15),
                'parsed_hours': 3.5,
                'overtime_type': 'weekday_evening',
                'confidence': 0.95
            },
            {
                'id': 2,
                'type': 'leave',
                'parsed_date': date(2026, 1, 16),
                'parsed_hours': 4.0,
                'leave_type': 'personal',
                'confidence': 0.88
            },
            {
                'id': 3,
                'type': 'unknown',
                'parsed_date': None,
                'parsed_hours': None,
                'confidence': 0.4
            }
        ]

        processed = process_parse_results(results)

        assert len(processed) == 3
        assert processed[0]['confidence_level'] == 'HIGH'
        assert processed[1]['confidence_level'] == 'HIGH'
        assert processed[2]['confidence_level'] == 'LOW'

    def test_process_with_anomaly_flag(self):
        """处理结果包含异常标记"""
        from src.services.parse_result_processor import process_parse_results

        results = [
            {
                'id': 1,
                'type': 'overtime',
                'parsed_date': date(2026, 1, 15),
                'parsed_hours': 15.0,  # 异常时长
                'overtime_type': 'weekday_evening',
                'confidence': 0.95
            }
        ]

        processed = process_parse_results(results)

        assert processed[0]['has_anomaly'] is True
        assert len(processed[0]['anomalies']) > 0


class TestConfidenceThresholds:
    """置信度阈值测试"""

    def test_high_threshold(self):
        """高置信度阈值边界"""
        from src.services.parse_result_processor import classify_confidence_level

        # 0.8 应该是 HIGH
        result = {'confidence': 0.8, 'type': 'overtime', 'parsed_date': date(2026, 1, 15)}
        assert classify_confidence_level(result) == 'HIGH'

    def test_medium_threshold(self):
        """中等置信度阈值边界"""
        from src.services.parse_result_processor import classify_confidence_level

        # 0.6 应该是 MEDIUM
        result = {'confidence': 0.6, 'type': 'overtime', 'parsed_date': date(2026, 1, 15)}
        assert classify_confidence_level(result) == 'MEDIUM'

    def test_low_threshold(self):
        """低置信度阈值边界"""
        from src.services.parse_result_processor import classify_confidence_level

        # 低于 0.6 应该是 LOW
        result = {'confidence': 0.59, 'type': 'overtime', 'parsed_date': date(2026, 1, 15)}
        assert classify_confidence_level(result) == 'LOW'
