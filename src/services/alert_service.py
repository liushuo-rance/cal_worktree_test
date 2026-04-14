"""
加班合规预警服务
扫描月度加班时长并生成合规预警/告警通知
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Any


COMPLIANCE_WARNING_THRESHOLD = 30.0
COMPLIANCE_VIOLATION_THRESHOLD = 36.0


def scan_monthly_compliance(
    conn: sqlite3.Connection, year: int, month: int
) -> List[Dict[str, Any]]:
    """
    扫描指定月份的加班合规情况，为超出阈值的员工生成站内通知。

    Args:
        conn: 数据库连接
        year: 年份
        month: 月份

    Returns:
        生成的通知列表
    """
    cursor = conn.cursor()
    month_str = f"{year}-{month:02d}"

    cursor.execute("""
        SELECT
            employee_id,
            SUM(total_minutes) as total_minutes
        FROM overtime_records
        WHERE strftime('%Y-%m', work_date) = ?
        GROUP BY employee_id
    """, (month_str,))

    rows = cursor.fetchall()
    created_notifications: List[Dict[str, Any]] = []

    for row in rows:
        employee_id = row["employee_id"]
        total_hours = row["total_minutes"] / 60.0

        if total_hours < COMPLIANCE_WARNING_THRESHOLD:
            continue

        if total_hours >= COMPLIANCE_VIOLATION_THRESHOLD:
            notif_type = "compliance_violation"
            title = (
                f"加班合规告警：员工 {employee_id} 本月加班时长已超 {total_hours:.1f} 小时"
            )
        else:
            notif_type = "compliance_warning"
            title = (
                f"加班合规预警：员工 {employee_id} 本月加班时长已达 {total_hours:.1f} 小时"
            )

        content = (
            f"员工 {employee_id} 在 {year} 年 {month} 月的累计加班时长为 "
            f"{total_hours:.1f} 小时。根据劳动法规定，每月加班不得超过 36 小时，"
            f"请注意合理安排工作时间。"
        )

        # 去重：同一员工、同一月份、同一类型只生成一次
        cursor.execute("""
            SELECT id FROM notifications
            WHERE employee_id = ?
              AND type = ?
              AND content = ?
              AND created_at >= datetime('now', '-31 days')
            LIMIT 1
        """, (employee_id, notif_type, content))
        if cursor.fetchone():
            continue

        cursor.execute("""
            INSERT INTO notifications
            (employee_id, type, title, content)
            VALUES (?, ?, ?, ?)
        """, (employee_id, notif_type, title, content))
        conn.commit()

        created_notifications.append({
            "id": cursor.lastrowid,
            "employee_id": employee_id,
            "type": notif_type,
            "title": title,
            "content": content,
            "total_hours": round(total_hours, 2),
        })

    return created_notifications


def get_compliance_risk_count(conn: sqlite3.Connection) -> int:
    """
    获取当前月份加班时长达到或超过预警阈值（30小时）的员工数量。

    Args:
        conn: 数据库连接

    Returns:
        风险员工数量
    """
    now = datetime.now()
    month_str = f"{now.year}-{now.month:02d}"

    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as count FROM (
            SELECT employee_id
            FROM overtime_records
            WHERE strftime('%Y-%m', work_date) = ?
            GROUP BY employee_id
            HAVING SUM(total_minutes) >= ?
        )
    """, (month_str, int(COMPLIANCE_WARNING_THRESHOLD * 60)))

    row = cursor.fetchone()
    return row["count"] if row else 0
