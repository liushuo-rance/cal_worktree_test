"""
节假日服务
提供日期类型判断、节假日管理功能
"""

import sqlite3
from datetime import date
from typing import Optional


def get_date_type(conn: sqlite3.Connection, check_date: date) -> str:
    """
    获取日期类型

    Args:
        conn: 数据库连接
        check_date: 要检查的日期

    Returns:
        日期类型: workday/weekend/statutory_holiday/adjusted_holiday/adjusted_workday
    """
    # 先查数据库
    cursor = conn.cursor()
    cursor.execute(
        "SELECT holiday_type FROM holiday_config WHERE holiday_date = ?",
        (check_date.isoformat(),)
    )
    row = cursor.fetchone()

    if row:
        holiday_type = row['holiday_type']
        if holiday_type == 'statutory':
            return 'statutory_holiday'
        elif holiday_type == 'adjusted_holiday':
            return 'adjusted_holiday'
        elif holiday_type == 'adjusted_workday':
            return 'adjusted_workday'

    # 数据库没有，按星期判断
    weekday = check_date.weekday()
    if weekday >= 5:  # 周六=5, 周日=6
        return 'weekend'
    else:
        return 'workday'


def is_workday(conn: sqlite3.Connection, check_date: date) -> bool:
    """
    判断是否为工作日

    Args:
        conn: 数据库连接
        check_date: 要检查的日期

    Returns:
        是否为工作日
    """
    date_type = get_date_type(conn, check_date)
    return date_type in ('workday', 'adjusted_workday')


def save_holiday(conn: sqlite3.Connection, holiday_date: date, name: str,
                 holiday_type: str, year: int) -> None:
    """
    保存节假日

    Args:
        conn: 数据库连接
        holiday_date: 节假日日期
        name: 节假日名称
        holiday_type: 节假日类型
        year: 年份
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO holiday_config (holiday_date, holiday_name, holiday_type, year)
        VALUES (?, ?, ?, ?)
    """, (holiday_date.isoformat(), name, holiday_type, year))
    conn.commit()


def delete_holiday(conn: sqlite3.Connection, holiday_date: date) -> None:
    """
    删除节假日

    Args:
        conn: 数据库连接
        holiday_date: 节假日日期
    """
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM holiday_config WHERE holiday_date = ?",
        (holiday_date.isoformat(),)
    )
    conn.commit()


def get_overtime_type(conn: sqlite3.Connection, check_date: date) -> str:
    """
    获取加班类型

    Args:
        conn: 数据库连接
        check_date: 要检查的日期

    Returns:
        加班类型: weekday/weekend/holiday
    """
    date_type = get_date_type(conn, check_date)

    if date_type == 'statutory_holiday':
        return 'holiday'
    elif date_type in ('weekend', 'adjusted_holiday'):
        return 'weekend'
    else:
        return 'weekday'
