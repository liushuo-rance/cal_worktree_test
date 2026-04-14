"""
类型识别器
基于关键词和模式识别记录类型
"""

import re
from typing import Dict, Any


# 类型识别规则
TYPE_RULES = {
    'overtime': {
        'keywords': ['晚上', '早', '中午', '加班', '小时'],
        'patterns': [
            (r'晚上\s*\d+\.?\d*\s*小时', 'weekday_evening', 0.9),
            (r'早\s*\d+\s*点', 'weekday_morning', 0.85),
            (r'中午\s*\d+[:：]\d+', 'weekday_lunch', 0.85),
            (r'早\s*\d+\s*到\s*晚\s*\d+', 'weekday_mixed', 0.8),
            (r'\d+\.?\d*\s*小时', None, 0.7),
        ],
        'base_confidence': 0.7
    },
    'leave': {
        'keywords': ['请假', '休假', '事假', '病假', '年假'],
        'patterns': [
            (r'请假\s*[半天一天]', 'personal', 0.95),
            (r'请假\s*\d+\s*天', 'personal', 0.95),
            (r'病假', 'sick', 0.95),
            (r'年假', 'annual', 0.95),
            (r'休假', 'personal', 0.9),
        ],
        'base_confidence': 0.9
    },
    'comp_off': {
        'keywords': ['调休', '补休'],
        'patterns': [
            (r'调休\s*[半天一天]', None, 0.95),
            (r'调休\s*\d+\s*天', None, 0.95),
            (r'补休', None, 0.9),
        ],
        'base_confidence': 0.9
    },
    'reference_only': {
        'keywords': ['累计', '余额', '剩余'],
        'patterns': [
            (r'累计\s*\d+\.?\d*\s*小时', None, 0.7),
            (r'余额\s*\d+', None, 0.6),
            (r'剩余\s*\d+', None, 0.6),
        ],
        'base_confidence': 0.6
    }
}


def calculate_confidence(text: str, record_type: str) -> float:
    """
    计算识别置信度

    Args:
        text: 原始文本
        record_type: 识别到的类型

    Returns:
        置信度分数 (0-1)
    """
    confidence = TYPE_RULES[record_type]['base_confidence']

    # 根据匹配到的模式调整置信度
    if record_type in TYPE_RULES and 'patterns' in TYPE_RULES[record_type]:
        for pattern, subtype, pattern_confidence in TYPE_RULES[record_type]['patterns']:
            if re.search(pattern, text):
                return pattern_confidence

    return confidence


def classify_record_type(text: str) -> Dict[str, Any]:
    """
    识别记录类型

    Args:
        text: 记录描述文本

    Returns:
        包含类型、子类型、置信度的字典
    """
    if not text:
        return {
            'type': 'unknown',
            'confidence': 0.0
        }

    text = text.strip()

    # 按优先级检查各类型
    for record_type in ['leave', 'comp_off', 'reference_only', 'overtime']:
        rules = TYPE_RULES[record_type]

        # 检查关键词
        keyword_match = any(kw in text for kw in rules['keywords'])

        # 检查模式
        pattern_match = None
        subtype = None
        for pattern, st, _ in rules.get('patterns', []):
            if re.search(pattern, text):
                pattern_match = pattern
                subtype = st
                break

        # 如果匹配到关键词或模式
        if keyword_match or pattern_match:
            confidence = calculate_confidence(text, record_type)

            result = {
                'type': record_type,
                'confidence': confidence
            }

            # 添加子类型信息
            if record_type == 'overtime' and subtype:
                result['overtime_type'] = subtype
            elif record_type == 'leave' and subtype:
                result['leave_type'] = subtype

            return result

    # 无法识别
    return {
        'type': 'unknown',
        'confidence': 0.3
    }
