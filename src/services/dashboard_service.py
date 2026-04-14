"""
Dashboard 服务
提供首页最近活动、统计摘要等数据
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional


def get_recent_activities(
    conn: sqlite3.Connection,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    获取最近活动列表

    活动来源：
    - 新员工入职 (employees.created_at)
    - 记录导入 (import_sessions.completed_at)
    - 审批通过 (review_queue.reviewed_at WHERE status='approved')

    Args:
        conn: 数据库连接
        limit: 返回最大条数

    Returns:
        活动列表，按时间降序排列
    """
    activities = []
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

    for row in cursor.fetchall():
        activities.append({
            'type': 'employee_added',
            'title': '新员工入职',
            'description': f"{row['name']}已添加到系统",
            'employee_id': row['employee_id'],
            'employee_name': row['name'],
            'timestamp': row['created_at'],
        })

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

    for row in cursor.fetchall():
        emp_name = row['employee_name'] or row['employee_id'] or '系统'
        total = row['total_records'] or 0
        activities.append({
            'type': 'record_imported',
            'title': '导入记录',
            'description': f"{total}条记录已导入 ({emp_name})",
            'employee_id': row['employee_id'],
            'employee_name': emp_name,
            'total_records': total,
            'timestamp': row['completed_at'],
        })

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

    for row in cursor.fetchall():
        raw_text = row['raw_text'] or '审批申请'
        activities.append({
            'type': 'review_approved',
            'title': '审批通过',
            'description': raw_text,
            'parsed_type': row['parsed_type'],
            'parsed_subtype': row['parsed_subtype'],
            'timestamp': row['reviewed_at'],
        })

    # 统一按时间降序排列
    def _parse_ts(ts: Optional[str]) -> datetime:
        if not ts:
            return datetime.min
        try:
            return datetime.fromisoformat(ts.replace(' ', 'T'))
        except (ValueError, AttributeError):
            return datetime.min

    activities.sort(key=lambda a: _parse_ts(a.get('timestamp')), reverse=True)

    return activities[:limit]


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
