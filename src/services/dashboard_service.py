"""
Dashboard 服务
提供首页最近活动、统计摘要等数据
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional


def get_recent_activities(
    conn: sqlite3.Connection,
    limit: int = 1
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    获取最近活动

    固定返回三个类别的最近一条记录：
    - record_imported: 记录导入
    - employee_added: 员工入职
    - review_approved: 审批通过

    Args:
        conn: 数据库连接
        limit: 每类返回最大条数（默认1）

    Returns:
        按类型分类的活动字典，无数据时值为 None
    """
    activities: Dict[str, Optional[Dict[str, Any]]] = {
        'record_imported': None,
        'employee_added': None,
        'review_approved': None,
    }
    cursor = conn.cursor()

    # 1. 新员工入职
    cursor.execute("""
        SELECT
            employee_id,
            name,
            created_at
        FROM employees
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    row = cursor.fetchone()
    if row:
        activities['employee_added'] = {
            'type': 'employee_added',
            'title': '新员工入职',
            'description': f"{row['name']}已添加到系统",
            'employee_id': row['employee_id'],
            'employee_name': row['name'],
            'timestamp': row['created_at'],
        }

    # 2. 记录导入 (completed 状态)
    cursor.execute("""
        SELECT
            s.id,
            s.employee_id,
            s.total_records,
            s.completed_at,
            e.name as employee_name
        FROM import_sessions s
        LEFT JOIN employees e ON s.employee_id = e.employee_id
        WHERE s.status = 'completed'
          AND s.completed_at IS NOT NULL
        ORDER BY s.completed_at DESC
        LIMIT ?
    """, (limit,))

    row = cursor.fetchone()
    if row:
        emp_name = row['employee_name'] or row['employee_id'] or '系统'
        total = row['total_records'] or 0
        activities['record_imported'] = {
            'type': 'record_imported',
            'title': '导入记录',
            'description': f"{total}条记录已导入 ({emp_name})",
            'employee_id': row['employee_id'],
            'employee_name': emp_name,
            'total_records': total,
            'timestamp': row['completed_at'],
        }

    # 3. 审批通过
    cursor.execute("""
        SELECT
            q.id,
            q.raw_text,
            q.parsed_type,
            q.parsed_subtype,
            q.reviewed_at
        FROM review_queue q
        WHERE q.status = 'approved'
          AND q.reviewed_at IS NOT NULL
        ORDER BY q.reviewed_at DESC
        LIMIT ?
    """, (limit,))

    row = cursor.fetchone()
    if row:
        raw_text = row['raw_text'] or '审批申请'
        activities['review_approved'] = {
            'type': 'review_approved',
            'title': '审批通过',
            'description': raw_text,
            'parsed_type': row['parsed_type'],
            'parsed_subtype': row['parsed_subtype'],
            'timestamp': row['reviewed_at'],
        }

    return activities


def format_relative_time(timestamp: Optional[str]) -> str:
    """
    将时间戳格式化为相对时间描述

    Args:
        timestamp: ISO 格式时间字符串

    Returns:
        相对时间描述（如"10分钟前"、"1小时前"、"昨天"）
    """
    if not timestamp:
        return '刚刚'

    try:
        dt = datetime.fromisoformat(timestamp.replace(' ', 'T'))
    except (ValueError, AttributeError):
        return '刚刚'

    now = datetime.now()
    delta = now - dt

    if delta.total_seconds() < 60:
        return '刚刚'
    elif delta.total_seconds() < 3600:
        minutes = int(delta.total_seconds() // 60)
        return f'{minutes}分钟前'
    elif delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() // 3600)
        return f'{hours}小时前'
    elif delta.total_seconds() < 172800:
        return '昨天'
    elif delta.days < 7:
        return f'{delta.days}天前'
    else:
        return dt.strftime('%Y-%m-%d')
