"""
时长解析器
支持多种时长描述格式解析
"""

import re
from typing import Optional, Tuple


# 中文数字映射
CHINESE_NUMBERS = {
    '一': 1,
    '二': 2,
    '两': 2,
    '三': 3,
    '四': 4,
    '五': 5,
    '六': 6,
    '七': 7,
    '八': 8,
    '九': 9,
    '十': 10,
    '半': 0.5,
}


def parse_hours(text: str) -> Optional[Tuple[int, int, int]]:
    """
    解析时长字符串，返回 (小时, 分钟, 总分钟数)

    Args:
        text: 时长描述文本

    Returns:
        (小时, 分钟, 总分钟数) 元组，解析失败返回 None
    """
    if not text:
        return None

    text = text.strip()

    # 1. 尝试匹配 "X小时Y分钟" (优先匹配完整格式)
    match = re.search(r'(\d+)\s*小时\s*(\d+)\s*分钟', text)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        total_minutes = hours * 60 + minutes
        return (hours, minutes, total_minutes)

    # 2. 尝试匹配 "X小时" 或 "X.5小时"
    match = re.search(r'(\d+\.?\d*)\s*小时', text)
    if match:
        hours = float(match.group(1))
        total_minutes = int(hours * 60)
        h, m = divmod(total_minutes, 60)
        return (h, m, total_minutes)

    # 3. 尝试匹配 "X分钟"
    match = re.search(r'(\d+)\s*分钟', text)
    if match:
        minutes = int(match.group(1))
        return (0, minutes, minutes)

    # 4. 尝试匹配关键词 "半天"
    if '半天' in text:
        return (4, 0, 240)

    # 5. 尝试匹配关键词 "一天/全天"
    if '一天' in text or '全天' in text:
        return (8, 0, 480)

    # 6. 尝试匹配 "X天" (阿拉伯数字)
    match = re.search(r'(\d+)\s*天', text)
    if match:
        days = int(match.group(1))
        total_hours = days * 8
        return (total_hours, 0, total_hours * 60)

    # 7. 尝试匹配中文数字天数
    match = re.search(r'([一二两三四五六七八九十])\s*天', text)
    if match:
        days = CHINESE_NUMBERS.get(match.group(1), 1)
        total_hours = days * 8
        return (total_hours, 0, total_hours * 60)

    # 无法解析
    return None


def extract_duration_text(line: str) -> Optional[str]:
    """
    从行文本中提取时长描述部分

    Args:
        line: 原始行文本

    Returns:
        时长描述文本，无则返回 None
    """
    if not line:
        return None

    # 去除日期部分，获取剩余内容
    remaining = line

    # 匹配并去除日期范围
    range_pattern = r'^\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}\s*[-~至]\s*(?:\d{1,2}[.\-/])?\d{1,2}[,，\s]+'
    match = re.match(range_pattern, line)
    if match:
        remaining = line[match.end():].strip()
    else:
        # 匹配并去除单日期
        single_pattern = r'^\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}[,，\s]+'
        match = re.match(single_pattern, line)
        if match:
            remaining = line[match.end():].strip()
        else:
            # 匹配并去除中文日期
            chinese_pattern = r'^\d{4}年\d{1,2}月\d{1,2}日[,，\s]+'
            match = re.match(chinese_pattern, line)
            if match:
                remaining = line[match.end():].strip()

    # 检查剩余内容是否包含时长信息
    duration_keywords = [
        r'\d+\.?\d*\s*小时',
        r'\d+\s*分钟',
        r'半天',
        r'一天|全天',
        r'[一二两三四五六七八九十]\s*天',
        r'\d+\s*天',
    ]

    for pattern in duration_keywords:
        if re.search(pattern, remaining):
            return remaining

    return None
