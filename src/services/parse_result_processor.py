"""
解析结果处理器
提供置信度分级、异常检测、结果验证功能
"""

from datetime import date
from typing import Dict, Any, List, Tuple


def classify_confidence_level(parse_result: Dict[str, Any]) -> str:
    """
    根据解析结果分类置信度级别

    Args:
        parse_result: 解析结果字典

    Returns:
        置信度级别: HIGH/MEDIUM/LOW
    """
    confidence = parse_result.get('confidence', 0)
    record_type = parse_result.get('type', 'unknown')
    parsed_date = parse_result.get('parsed_date')
    parsed_hours = parse_result.get('parsed_hours')

    # 未知类型直接返回LOW
    if record_type == 'unknown':
        return 'LOW'

    # 根据置信度分数判断（优先）
    if confidence >= 0.8:
        return 'HIGH'
    elif confidence >= 0.6:
        return 'MEDIUM'

    # 低置信度时，检查关键信息缺失
    if parsed_date is None or parsed_hours is None:
        return 'LOW'

    return 'LOW'


def detect_anomalies(parse_result: Dict[str, Any]) -> List[str]:
    """
    检测解析结果中的异常

    Args:
        parse_result: 解析结果字典

    Returns:
        异常列表
    """
    anomalies = []

    record_type = parse_result.get('type')
    parsed_date = parse_result.get('parsed_date')
    parsed_hours = parse_result.get('parsed_hours')
    overtime_type = parse_result.get('overtime_type')

    # 检查超长加班
    if parsed_hours is not None and parsed_hours > 12:
        anomalies.append(f"加班时长过长: {parsed_hours}小时")

    # 检查未来日期
    if parsed_date is not None and isinstance(parsed_date, date):
        if parsed_date > date.today():
            anomalies.append(f"未来日期: {parsed_date}")

    # 检查周末但标记为工作日加班
    if record_type == 'overtime' and parsed_date is not None and isinstance(parsed_date, date):
        weekday = parsed_date.weekday()
        weekday_types = ['weekday_morning', 'weekday_lunch', 'weekday_evening']
        if weekday >= 5 and overtime_type in weekday_types:
            anomalies.append("周末日期但标记为工作日加班类型")

    return anomalies


def validate_parse_result(parse_result: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    验证解析结果的有效性

    Args:
        parse_result: 解析结果字典

    Returns:
        (是否有效, 错误列表)
    """
    errors = []

    # 检查必需字段
    if 'type' not in parse_result:
        errors.append("Missing type field")

    if 'parsed_date' not in parse_result:
        errors.append("Missing date field")

    if 'parsed_hours' in parse_result:
        hours = parse_result['parsed_hours']
        if hours is not None and hours < 0:
            errors.append("时长不能为负数")

    # 检查类型特定字段
    record_type = parse_result.get('type')
    if record_type == 'overtime' and 'overtime_type' not in parse_result:
        errors.append("加班记录缺少overtime_type")

    if record_type == 'leave' and 'leave_type' not in parse_result:
        errors.append("请假记录缺少leave_type")

    return len(errors) == 0, errors


def process_parse_results(
    parse_results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    批量处理解析结果

    Args:
        parse_results: 解析结果列表

    Returns:
        处理后的结果列表（添加了置信度级别和异常标记）
    """
    processed = []

    for result in parse_results:
        # 创建副本避免修改原始数据
        processed_result = result.copy()

        # 分类置信度
        confidence_level = classify_confidence_level(result)
        processed_result['confidence_level'] = confidence_level

        # 检测异常
        anomalies = detect_anomalies(result)
        processed_result['anomalies'] = anomalies
        processed_result['has_anomaly'] = len(anomalies) > 0

        # 验证结果
        is_valid, errors = validate_parse_result(result)
        processed_result['is_valid'] = is_valid
        processed_result['validation_errors'] = errors

        processed.append(processed_result)

    return processed
