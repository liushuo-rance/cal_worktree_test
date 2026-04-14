"""
报表生成服务
提供个人月度报表、调休余额报表、工资计算表功能
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional
import sqlite3


class ReportError(Exception):
    """报表服务异常"""
    pass


def _minutes_to_hours(minutes: int) -> float:
    """将分钟转换为小时（保留1位小数）"""
    return round(minutes / 60, 1)


def _get_employee_info(conn: sqlite3.Connection, employee_id: str) -> Optional[Dict[str, Any]]:
    """获取员工信息"""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM employees WHERE employee_id = ?",
        (employee_id,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _get_weekday_name(date_str: str) -> str:
    """获取星期几的中文名称"""
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    d = datetime.strptime(date_str, '%Y-%m-%d')
    return weekday_names[d.weekday()]


def generate_monthly_report(
    conn: sqlite3.Connection,
    employee_id: str,
    year: int,
    month: int
) -> Dict[str, Any]:
    """
    生成个人月度报表

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        year: 年份
        month: 月份

    Returns:
        月度报表数据

    Raises:
        ReportError: 员工不存在
    """
    employee = _get_employee_info(conn, employee_id)
    if not employee:
        raise ReportError(f"员工 {employee_id} 不存在")

    cursor = conn.cursor()

    # 查询加班记录
    cursor.execute("""
        SELECT * FROM overtime_records
        WHERE employee_id = ?
          AND strftime('%Y', work_date) = ?
          AND strftime('%m', work_date) = ?
        ORDER BY work_date
    """, (employee_id, str(year), f"{month:02d}"))

    overtime_records = []
    weekday_hours = 0.0
    weekend_hours = 0.0
    holiday_hours = 0.0

    for row in cursor.fetchall():
        record = dict(row)
        hours = _minutes_to_hours(record['total_minutes'])

        record_data = {
            'date': record['work_date'],
            'weekday': _get_weekday_name(record['work_date']),
            'hours': hours,
            'type': record['overtime_type'],
            'description': record['description'] or ''
        }
        overtime_records.append(record_data)

        # 分类统计
        if record['overtime_type'] == 'weekend':
            weekend_hours += hours
        elif record['overtime_type'] == 'holiday':
            holiday_hours += hours
        else:
            weekday_hours += hours

    # 查询请假记录
    cursor.execute("""
        SELECT * FROM leave_records
        WHERE employee_id = ?
          AND strftime('%Y', leave_date) = ?
          AND strftime('%m', leave_date) = ?
        ORDER BY leave_date
    """, (employee_id, str(year), f"{month:02d}"))

    leave_records = []
    leave_days = 0

    for row in cursor.fetchall():
        record = dict(row)
        hours = _minutes_to_hours(record['total_minutes'])
        days = hours / 8

        record_data = {
            'date': record['leave_date'],
            'weekday': _get_weekday_name(record['leave_date']),
            'hours': hours,
            'days': days,
            'type': record['leave_type']
        }
        leave_records.append(record_data)
        leave_days += days

    return {
        'employee_id': employee_id,
        'employee_name': employee['name'],
        'year': year,
        'month': month,
        'overtime_details': overtime_records,
        'leave_details': leave_records,
        'summary': {
            'weekday_hours': weekday_hours,
            'weekend_hours': weekend_hours,
            'holiday_hours': holiday_hours,
            'total_overtime_hours': weekday_hours + weekend_hours + holiday_hours,
            'leave_days': int(leave_days),
            'leave_hours': leave_days * 8
        }
    }


def generate_comp_off_report(
    conn: sqlite3.Connection,
    employee_id: str,
    warning_days: int = 30
) -> Dict[str, Any]:
    """
    生成调休余额报表

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        warning_days: 到期警告天数

    Returns:
        调休余额报表
    """
    cursor = conn.cursor()

    # 查询所有调休余额
    cursor.execute("""
        SELECT * FROM comp_off_balances
        WHERE employee_id = ? AND status = 'active'
        ORDER BY acquired_date
    """, (employee_id,))

    balance_items = []
    total_hours = 0.0
    expiring_soon_hours = 0.0
    expiring_items = []
    today = date.today()
    warning_date = today + timedelta(days=warning_days)

    for row in cursor.fetchall():
        record = dict(row)
        hours = _minutes_to_hours(record['remaining_minutes'])
        total_hours += hours

        item = {
            'acquired_date': record['acquired_date'],
            'hours': hours,
            'expiry_date': record['expiry_date'],
            'status': record['status']
        }
        balance_items.append(item)

        # 检查是否即将到期
        if record['expiry_date']:
            expiry = datetime.strptime(record['expiry_date'], '%Y-%m-%d').date()
            if expiry <= warning_date and expiry >= today:
                expiring_soon_hours += hours
                expiring_items.append(item)

    return {
        'employee_id': employee_id,
        'total_hours': total_hours,
        'balance_items': balance_items,
        'expiring_soon_hours': expiring_soon_hours,
        'expiring_items': expiring_items,
        'warning_days': warning_days
    }


def generate_salary_report(
    conn: sqlite3.Connection,
    employee_id: str,
    year: int,
    month: int
) -> Dict[str, Any]:
    """
    生成工资计算表

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        year: 年份
        month: 月份

    Returns:
        工资计算报表
    """
    employee = _get_employee_info(conn, employee_id)
    if not employee:
        raise ReportError(f"员工 {employee_id} 不存在")

    hourly_rate = employee.get('hourly_salary', 37.5)
    cursor = conn.cursor()

    # 查询各类加班记录
    cursor.execute("""
        SELECT overtime_type, SUM(total_minutes) as total_minutes
        FROM overtime_records
        WHERE employee_id = ?
          AND strftime('%Y', work_date) = ?
          AND strftime('%m', work_date) = ?
        GROUP BY overtime_type
    """, (employee_id, str(year), f"{month:02d}"))

    weekday_minutes = 0
    weekend_minutes = 0
    holiday_minutes = 0

    for row in cursor.fetchall():
        if row['overtime_type'] == 'weekend':
            weekend_minutes = row['total_minutes'] or 0
        elif row['overtime_type'] == 'holiday':
            holiday_minutes = row['total_minutes'] or 0
        else:
            weekday_minutes += (row['total_minutes'] or 0)

    # 计算各类加班工资
    weekday_hours = _minutes_to_hours(weekday_minutes)
    weekend_hours = _minutes_to_hours(weekend_minutes)
    holiday_hours = _minutes_to_hours(holiday_minutes)

    weekday_amount = weekday_hours * hourly_rate * 1.5
    weekend_amount = weekend_hours * hourly_rate * 2.0
    holiday_amount = holiday_hours * hourly_rate * 3.0

    total_amount = weekday_amount + weekend_amount + holiday_amount

    return {
        'employee_id': employee_id,
        'employee_name': employee['name'],
        'year': year,
        'month': month,
        'hourly_rate': hourly_rate,
        'weekday_overtime': {
            'hours': weekday_hours,
            'multiplier': 1.5,
            'amount': round(weekday_amount, 2)
        },
        'weekend_overtime': {
            'hours': weekend_hours,
            'multiplier': 2.0,
            'amount': round(weekend_amount, 2)
        },
        'holiday_overtime': {
            'hours': holiday_hours,
            'multiplier': 3.0,
            'amount': round(holiday_amount, 2)
        },
        'total_amount': round(total_amount, 2)
    }


def generate_department_summary(
    conn: sqlite3.Connection,
    year: int,
    month: int
) -> Dict[str, Any]:
    """
    生成部门统计报表

    Args:
        conn: 数据库连接
        year: 年份
        month: 月份

    Returns:
        部门统计报表
    """
    cursor = conn.cursor()

    # 获取所有员工
    cursor.execute("SELECT * FROM employees")
    employees_data = []

    for row in cursor.fetchall():
        employee = dict(row)
        emp_id = employee['employee_id']

        # 查询该员工当月加班统计
        cursor.execute("""
            SELECT SUM(total_minutes) as total_minutes
            FROM overtime_records
            WHERE employee_id = ?
              AND strftime('%Y', work_date) = ?
              AND strftime('%m', work_date) = ?
        """, (emp_id, str(year), f"{month:02d}"))

        result = cursor.fetchone()
        total_minutes = result['total_minutes'] or 0
        total_hours = _minutes_to_hours(total_minutes)

        employees_data.append({
            'employee_id': emp_id,
            'employee_name': employee['name'],
            'total_overtime_hours': total_hours
        })

    # 计算部门总计
    total_hours = sum(e['total_overtime_hours'] for e in employees_data)

    return {
        'year': year,
        'month': month,
        'employees': employees_data,
        'department_totals': {
            'total_employees': len(employees_data),
            'total_overtime_hours': total_hours
        }
    }


def export_report_to_dict(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    将报表导出为字典格式

    Args:
        report: 报表数据

    Returns:
        导出格式的字典
    """
    return report
