"""
加班统计服务
提供加班记录管理、统计汇总、类型分类功能
"""

import sqlite3
from datetime import date
from typing import List, Dict, Any, Optional


class OvertimeServiceError(Exception):
    """加班服务错误"""
    pass


def validate_overtime_duration(hours: int, minutes: int) -> bool:
    """
    验证加班时长有效性

    Args:
        hours: 小时数
        minutes: 分钟数

    Returns:
        是否有效

    Raises:
        OvertimeServiceError: 时长无效
    """
    if hours < 0 or minutes < 0:
        raise OvertimeServiceError("时长不能为负数")

    if hours == 0 and minutes == 0:
        raise OvertimeServiceError("时长不能为零")

    if minutes >= 60:
        raise OvertimeServiceError("分钟数应在0-59之间")

    return True


def create_overtime_record(
    conn: sqlite3.Connection,
    employee_id: str,
    work_date: date,
    hours: int,
    minutes: int = 0,
    overtime_type: str = 'weekday_evening',
    description: str = ''
) -> int:
    """
    创建加班记录

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        work_date: 工作日期
        hours: 小时数
        minutes: 分钟数
        overtime_type: 加班类型
        description: 描述

    Returns:
        新记录ID

    Raises:
        OvertimeServiceError: 员工不存在或数据无效
    """
    # 验证员工存在
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM employees WHERE employee_id = ?",
        (employee_id,)
    )
    if not cursor.fetchone():
        raise OvertimeServiceError(f"员工不存在: {employee_id}")

    # 验证时长
    validate_overtime_duration(hours, minutes)

    # 计算总分钟数
    total_minutes = hours * 60 + minutes

    cursor.execute(
        """
        INSERT INTO overtime_records
        (employee_id, work_date, duration_hours, duration_minutes,
         total_minutes, overtime_type, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (employee_id, work_date.isoformat(), hours, minutes,
         total_minutes, overtime_type, description)
    )
    conn.commit()

    return cursor.lastrowid


def get_employee_overtime(
    conn: sqlite3.Connection,
    employee_id: str,
    year: Optional[int] = None,
    month: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    获取员工加班记录

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        year: 筛选年份（可选）
        month: 筛选月份（可选）

    Returns:
        加班记录列表
    """
    cursor = conn.cursor()

    sql = """
        SELECT * FROM overtime_records
        WHERE employee_id = ?
    """
    params = [employee_id]

    if year:
        sql += " AND strftime('%Y', work_date) = ?"
        params.append(str(year))

    if month:
        sql += " AND strftime('%m', work_date) = ?"
        params.append(f"{month:02d}")

    sql += " ORDER BY work_date DESC"

    cursor.execute(sql, params)

    return [dict(row) for row in cursor.fetchall()]


def delete_overtime_record(conn: sqlite3.Connection, record_id: int) -> None:
    """
    删除加班记录

    Args:
        conn: 数据库连接
        record_id: 记录ID
    """
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM overtime_records WHERE id = ?",
        (record_id,)
    )
    conn.commit()


def get_monthly_summary(
    conn: sqlite3.Connection,
    year: int,
    month: int
) -> Dict[str, Any]:
    """
    获取月度加班汇总

    Args:
        conn: 数据库连接
        year: 年份
        month: 月份

    Returns:
        汇总数据
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total_records,
            SUM(total_minutes) as total_minutes,
            SUM(duration_hours) as total_hours,
            SUM(duration_minutes) as remaining_minutes
        FROM overtime_records
        WHERE strftime('%Y', work_date) = ?
          AND strftime('%m', work_date) = ?
    """, (str(year), f"{month:02d}"))

    row = cursor.fetchone()

    total_minutes = row['total_minutes'] or 0
    hours = total_minutes // 60
    minutes = total_minutes % 60

    return {
        'year': year,
        'month': month,
        'total_records': row['total_records'],
        'total_minutes': total_minutes,
        'total_hours': hours + minutes / 60,
        'employee_count': cursor.execute("""
            SELECT COUNT(DISTINCT employee_id) FROM overtime_records
            WHERE strftime('%Y', work_date) = ? AND strftime('%m', work_date) = ?
        """, (str(year), f"{month:02d}")).fetchone()[0]
    }


def get_employee_monthly_summary(
    conn: sqlite3.Connection,
    employee_id: str,
    year: int,
    month: int
) -> Dict[str, Any]:
    """
    获取员工月度加班汇总

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        year: 年份
        month: 月份

    Returns:
        汇总数据
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total_records,
            SUM(total_minutes) as total_minutes
        FROM overtime_records
        WHERE employee_id = ?
          AND strftime('%Y', work_date) = ?
          AND strftime('%m', work_date) = ?
    """, (employee_id, str(year), f"{month:02d}"))

    row = cursor.fetchone()

    total_minutes = row['total_minutes'] or 0

    return {
        'employee_id': employee_id,
        'year': year,
        'month': month,
        'total_records': row['total_records'],
        'total_minutes': total_minutes,
        'total_hours': total_minutes / 60
    }


def get_summary_by_type(
    conn: sqlite3.Connection,
    employee_id: str,
    year: int,
    month: int
) -> Dict[str, Dict[str, Any]]:
    """
    按类型统计加班

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        year: 年份
        month: 月份

    Returns:
        各类型统计
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            overtime_type,
            COUNT(*) as count,
            SUM(total_minutes) as minutes
        FROM overtime_records
        WHERE employee_id = ?
          AND strftime('%Y', work_date) = ?
          AND strftime('%m', work_date) = ?
        GROUP BY overtime_type
    """, (employee_id, str(year), f"{month:02d}"))

    result = {}
    for row in cursor.fetchall():
        result[row['overtime_type']] = {
            'count': row['count'],
            'minutes': row['minutes'],
            'hours': (row['minutes'] or 0) / 60
        }

    # 确保所有类型都有条目
    for ot_type in ['weekday_morning', 'weekday_lunch', 'weekday_evening', 'weekend', 'holiday']:
        if ot_type not in result:
            result[ot_type] = {'count': 0, 'minutes': 0, 'hours': 0}

    return result


def get_overtime_ranking(
    conn: sqlite3.Connection,
    year: int,
    month: int,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    获取加班排名

    Args:
        conn: 数据库连接
        year: 年份
        month: 月份
        limit: 限制数量

    Returns:
        排名列表
    """
    cursor = conn.cursor()

    sql = """
        SELECT
            o.employee_id,
            e.name,
            COUNT(*) as record_count,
            SUM(o.total_minutes) as total_minutes
        FROM overtime_records o
        JOIN employees e ON o.employee_id = e.employee_id
        WHERE strftime('%Y', o.work_date) = ?
          AND strftime('%m', o.work_date) = ?
        GROUP BY o.employee_id, e.name
        ORDER BY total_minutes DESC
    """

    if limit:
        sql += f" LIMIT {limit}"

    cursor.execute(sql, (str(year), f"{month:02d}"))

    result = []
    rank = 1
    for row in cursor.fetchall():
        result.append({
            'rank': rank,
            'employee_id': row['employee_id'],
            'employee_name': row['name'],
            'record_count': row['record_count'],
            'total_minutes': row['total_minutes'],
            'total_hours': (row['total_minutes'] or 0) / 60
        })
        rank += 1

    return result


def classify_overtime_type(
    conn: sqlite3.Connection,
    work_date: date,
    hour: int,
    minute: int = 0
) -> str:
    """
    根据日期和时间分类加班类型

    Args:
        conn: 数据库连接
        work_date: 工作日期
        hour: 小时
        minute: 分钟

    Returns:
        加班类型
    """
    # 先检查是否为法定假日或调休假日
    cursor = conn.cursor()
    cursor.execute(
        "SELECT holiday_type FROM holiday_config WHERE holiday_date = ?",
        (work_date.isoformat(),)
    )
    row = cursor.fetchone()

    if row:
        holiday_type = row['holiday_type']
        if holiday_type == 'statutory':
            return 'holiday'
        elif holiday_type == 'adjusted_holiday':
            return 'weekend'  # 调休假日按周末算

    # 检查是否为周末
    weekday = work_date.weekday()
    if weekday >= 5:  # 周六=5, 周日=6
        return 'weekend'

    # 工作日，根据时间判断
    time_val = hour * 100 + minute

    if time_val < 830:  # 早上8:30之前
        return 'weekday_morning'
    elif 1200 <= time_val < 1300:  # 中午12:00-13:00
        return 'weekday_lunch'
    elif time_val >= 1730:  # 晚上17:30之后
        return 'weekday_evening'
    else:
        return 'weekday_evening'  # 默认晚间加班
