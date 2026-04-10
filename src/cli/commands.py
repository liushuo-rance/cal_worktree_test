"""
CLI命令模块
提供导入、查询、报表、导出等命令
"""

import os
import json
from datetime import date
from typing import Dict, Any, Optional
import sqlite3


class CLIError(Exception):
    """CLI命令异常"""
    pass


def import_file(
    conn: sqlite3.Connection,
    file_path: str,
    employee_id: str,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    导入Markdown文件

    Args:
        conn: 数据库连接
        file_path: 文件路径
        employee_id: 员工ID
        verbose: 是否输出详细信息

    Returns:
        导入结果

    Raises:
        CLIError: 文件不存在或导入失败
    """
    if not os.path.exists(file_path):
        raise CLIError(f"文件不存在: {file_path}")

    # 创建导入会话
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO import_sessions
        (employee_id, file_name, total_records, success_records, failed_records)
        VALUES (?, ?, 0, 0, 0)
    """, (employee_id, os.path.basename(file_path)))

    session_id = cursor.lastrowid

    # TODO: 实际解析文件内容
    # 这里简化处理，实际应调用解析器

    conn.commit()

    return {
        'success': True,
        'import_session_id': session_id,
        'total_records': 0,
        'file_path': file_path,
        'employee_id': employee_id
    }


def query_records(
    conn: sqlite3.Connection,
    employee_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """
    查询记录

    Args:
        conn: 数据库连接
        employee_id: 员工ID（可选）
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
        status: 状态筛选（可选）

    Returns:
        查询结果
    """
    cursor = conn.cursor()

    query = "SELECT * FROM overtime_records WHERE 1=1"
    params = []

    if employee_id:
        query += " AND employee_id = ?"
        params.append(employee_id)

    if start_date:
        query += " AND work_date >= ?"
        params.append(start_date.isoformat())

    if end_date:
        query += " AND work_date <= ?"
        params.append(end_date.isoformat())

    query += " ORDER BY work_date"

    cursor.execute(query, params)
    records = [dict(row) for row in cursor.fetchall()]

    return {
        'success': True,
        'records': records,
        'count': len(records)
    }


def generate_report(
    conn: sqlite3.Connection,
    employee_id: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    report_type: str = 'monthly'
) -> Dict[str, Any]:
    """
    生成报表

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        year: 年份
        month: 月份
        report_type: 报表类型 (monthly/comp_off/salary)

    Returns:
        报表结果
    """
    from src.services.report_service import (
        generate_monthly_report,
        generate_comp_off_report,
        generate_salary_report
    )

    if report_type == 'monthly':
        if year is None or month is None:
            now = date.today()
            year = year or now.year
            month = month or now.month
        report = generate_monthly_report(conn, employee_id, year, month)
    elif report_type == 'comp_off':
        report = generate_comp_off_report(conn, employee_id)
    elif report_type == 'salary':
        if year is None or month is None:
            now = date.today()
            year = year or now.year
            month = month or now.month
        report = generate_salary_report(conn, employee_id, year, month)
    else:
        raise CLIError(f"未知的报表类型: {report_type}")

    return {
        'success': True,
        'report_type': report_type,
        'report': report
    }


def export_data(
    conn: sqlite3.Connection,
    employee_id: str,
    format: str = 'json',
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    导出数据

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        format: 导出格式 (json/csv)
        output_path: 输出路径（可选）

    Returns:
        导出结果

    Raises:
        CLIError: 格式不支持
    """
    if format not in ['json', 'csv']:
        raise CLIError(f"不支持的格式: {format}")

    # 查询数据
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM overtime_records WHERE employee_id = ?",
        (employee_id,)
    )
    records = [dict(row) for row in cursor.fetchall()]

    # 导出为JSON
    if format == 'json':
        data = json.dumps(records, indent=2, default=str)

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(data)

        return {
            'success': True,
            'format': format,
            'output_path': output_path,
            'record_count': len(records)
        }

    # CSV格式暂未实现
    return {
        'success': True,
        'format': format,
        'record_count': len(records)
    }


def calculate_salary(
    conn: sqlite3.Connection,
    employee_id: str,
    year: int,
    month: int
) -> Dict[str, Any]:
    """
    计算工资

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        year: 年份
        month: 月份

    Returns:
        工资计算结果
    """
    from src.services.report_service import generate_salary_report

    report = generate_salary_report(conn, employee_id, year, month)

    return {
        'success': True,
        'salary_report': report
    }


def list_holidays(
    conn: sqlite3.Connection,
    year: int
) -> Dict[str, Any]:
    """
    列出节假日

    Args:
        conn: 数据库连接
        year: 年份

    Returns:
        节假日列表
    """
    # 查询节假日数据
    cursor = conn.cursor()

    # 检查是否存在holiday_config表
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='holiday_config'
    """)

    if cursor.fetchone():
        cursor.execute("""
            SELECT * FROM holiday_config
            WHERE strftime('%Y', holiday_date) = ?
            ORDER BY holiday_date
        """, (str(year),))
        holidays = [dict(row) for row in cursor.fetchall()]
    else:
        holidays = []

    return {
        'success': True,
        'year': year,
        'holidays': holidays,
        'count': len(holidays)
    }


def check_holiday_config(
    conn: sqlite3.Connection,
    month: str
) -> Dict[str, Any]:
    """
    检查节假日配置

    Args:
        conn: 数据库连接
        month: 月份 (YYYY-MM格式)

    Returns:
        检查结果
    """
    # 解析年月
    try:
        year, mon = month.split('-')
    except ValueError:
        raise CLIError(f"月份格式错误: {month}, 应为 YYYY-MM")

    cursor = conn.cursor()

    # 检查是否存在holiday_config表
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='holiday_config'
    """)

    has_config = cursor.fetchone() is not None

    return {
        'success': True,
        'month': month,
        'has_holiday_config': has_config,
        'check_result': {
            'config_exists': has_config,
            'year': int(year),
            'month': int(mon)
        }
    }


def query_comp_off(
    conn: sqlite3.Connection,
    employee_id: str
) -> Dict[str, Any]:
    """
    查询调休余额

    Args:
        conn: 数据库连接
        employee_id: 员工ID

    Returns:
        调休余额信息
    """
    from src.services.report_service import generate_comp_off_report

    report = generate_comp_off_report(conn, employee_id)

    return {
        'success': True,
        'balance': report
    }


def mark_expired_comp_off(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    标记已过期的调休

    Args:
        conn: 数据库连接

    Returns:
        操作结果
    """
    cursor = conn.cursor()

    # 检查是否存在comp_off_balances表
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='comp_off_balances'
    """)

    if not cursor.fetchone():
        return {
            'success': True,
            'marked_count': 0
        }

    # 标记已过期的调休
    today = date.today().isoformat()
    cursor.execute("""
        UPDATE comp_off_balances
        SET status = 'expired'
        WHERE expiry_date < ?
          AND status = 'active'
    """, (today,))

    marked_count = cursor.rowcount
    conn.commit()

    return {
        'success': True,
        'marked_count': marked_count
    }
