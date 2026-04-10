"""
工资计算服务
提供加班费计算、调休抵扣、月度工资单功能
符合《劳动法》第44条规定
"""

import sqlite3
from typing import Dict, Any, List


class SalaryServiceError(Exception):
    """工资服务错误"""
    pass


# 加班费率（根据《劳动法》第44条）
OVERTIME_RATES = {
    'weekday_morning': 1.5,  # 工作日延时
    'weekday_lunch': 1.5,    # 工作日午休
    'weekday_evening': 1.5,  # 工作日晚间
    'weekend': 2.0,          # 休息日
    'holiday': 3.0,          # 法定假日
}


def validate_salary_input(hourly_rate: float) -> bool:
    """
    验证工资输入

    Args:
        hourly_rate: 时薪

    Returns:
        是否有效

    Raises:
        SalaryServiceError: 输入无效
    """
    if hourly_rate <= 0:
        raise SalaryServiceError("时薪必须大于零")
    return True


def calculate_overtime_pay(
    hourly_rate: float,
    minutes: int,
    overtime_type: str
) -> float:
    """
    计算加班费

    根据《劳动法》第44条：
    - 工作日延时：1.5倍工资
    - 休息日：2倍工资
    - 法定假日：3倍工资

    Args:
        hourly_rate: 时薪
        minutes: 加班分钟数
        overtime_type: 加班类型

    Returns:
        加班费金额
    """
    rate = OVERTIME_RATES.get(overtime_type, 1.5)
    hours = minutes / 60
    return hours * rate * hourly_rate


def get_employee_hourly_rate(
    conn: sqlite3.Connection,
    employee_id: str
) -> float:
    """
    获取员工时薪

    Args:
        conn: 数据库连接
        employee_id: 员工ID

    Returns:
        时薪

    Raises:
        SalaryServiceError: 员工不存在
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT hourly_salary FROM employees WHERE employee_id = ?",
        (employee_id,)
    )

    row = cursor.fetchone()
    if not row:
        raise SalaryServiceError(f"员工不存在: {employee_id}")

    return row['hourly_salary']


def calculate_monthly_overtime_pay(
    conn: sqlite3.Connection,
    employee_id: str,
    year: int,
    month: int
) -> Dict[str, Any]:
    """
    计算月度加班费

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        year: 年份
        month: 月份

    Returns:
        加班费明细
    """
    hourly_rate = get_employee_hourly_rate(conn, employee_id)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            overtime_type,
            total_minutes
        FROM overtime_records
        WHERE employee_id = ?
          AND strftime('%Y', work_date) = ?
          AND strftime('%m', work_date) = ?
    """, (employee_id, str(year), f"{month:02d}"))

    # 按类型汇总
    breakdown = {
        'weekday': {'minutes': 0, 'pay': 0.0},
        'weekend': {'minutes': 0, 'pay': 0.0},
        'holiday': {'minutes': 0, 'pay': 0.0}
    }

    total_minutes = 0
    total_equivalent_minutes = 0
    total_pay = 0.0

    for row in cursor.fetchall():
        ot_type = row['overtime_type']
        minutes = row['total_minutes']
        rate = OVERTIME_RATES.get(ot_type, 1.5)

        pay = calculate_overtime_pay(hourly_rate, minutes, ot_type)

        # 分类统计
        if ot_type in ['weekday_morning', 'weekday_lunch', 'weekday_evening']:
            breakdown['weekday']['minutes'] += minutes
            breakdown['weekday']['pay'] += pay
        elif ot_type == 'weekend':
            breakdown['weekend']['minutes'] += minutes
            breakdown['weekend']['pay'] += pay
        elif ot_type == 'holiday':
            breakdown['holiday']['minutes'] += minutes
            breakdown['holiday']['pay'] += pay

        total_minutes += minutes
        total_equivalent_minutes += minutes * rate
        total_pay += pay

    return {
        'employee_id': employee_id,
        'year': year,
        'month': month,
        'hourly_rate': hourly_rate,
        'total_minutes': total_minutes,
        'equivalent_minutes': total_equivalent_minutes,
        'total_pay': total_pay,
        'breakdown': breakdown
    }


def calculate_monthly_leave_deduction(
    conn: sqlite3.Connection,
    employee_id: str,
    year: int,
    month: int
) -> Dict[str, Any]:
    """
    计算月度请假扣除

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        year: 年份
        month: 月份

    Returns:
        请假扣除明细
    """
    hourly_rate = get_employee_hourly_rate(conn, employee_id)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            SUM(total_minutes) as total_leave_minutes,
            SUM(comp_off_deduction_minutes) as comp_off_covered,
            SUM(cash_deduction_minutes) as cash_deduction
        FROM leave_records
        WHERE employee_id = ?
          AND strftime('%Y', leave_date) = ?
          AND strftime('%m', leave_date) = ?
    """, (employee_id, str(year), f"{month:02d}"))

    row = cursor.fetchone()

    total_leave = row['total_leave_minutes'] or 0
    comp_off_covered = row['comp_off_covered'] or 0
    cash_deduction_minutes = row['cash_deduction'] or 0

    # 计算现金扣除（时薪 × 小时数）
    cash_deduction_amount = (cash_deduction_minutes / 60) * hourly_rate

    return {
        'employee_id': employee_id,
        'year': year,
        'month': month,
        'total_leave_minutes': total_leave,
        'comp_off_covered_minutes': comp_off_covered,
        'cash_deduction_minutes': cash_deduction_minutes,
        'cash_deduction_amount': cash_deduction_amount
    }


def generate_monthly_salary_statement(
    conn: sqlite3.Connection,
    employee_id: str,
    year: int,
    month: int
) -> Dict[str, Any]:
    """
    生成月度工资单

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        year: 年份
        month: 月份

    Returns:
        工资单
    """
    # 获取员工信息
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT employee_id, name, daily_salary, hourly_salary
        FROM employees
        WHERE employee_id = ?
        """,
        (employee_id,)
    )

    emp = cursor.fetchone()
    if not emp:
        raise SalaryServiceError(f"员工不存在: {employee_id}")

    # 计算加班费
    overtime = calculate_monthly_overtime_pay(conn, employee_id, year, month)

    # 计算请假扣除
    leave = calculate_monthly_leave_deduction(conn, employee_id, year, month)

    # 净加班费
    net_overtime_pay = overtime['total_pay'] - leave['cash_deduction_amount']

    # 获取明细记录
    cursor.execute("""
        SELECT
            work_date,
            duration_hours,
            duration_minutes,
            total_minutes,
            overtime_type,
            description
        FROM overtime_records
        WHERE employee_id = ?
          AND strftime('%Y', work_date) = ?
          AND strftime('%m', work_date) = ?
        ORDER BY work_date
    """, (employee_id, str(year), f"{month:02d}"))

    overtime_records = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT
            leave_date,
            duration_hours,
            duration_minutes,
            total_minutes,
            leave_type,
            comp_off_deduction_minutes,
            cash_deduction_minutes
        FROM leave_records
        WHERE employee_id = ?
          AND strftime('%Y', leave_date) = ?
          AND strftime('%m', leave_date) = ?
        ORDER BY leave_date
    """, (employee_id, str(year), f"{month:02d}"))

    leave_records = [dict(row) for row in cursor.fetchall()]

    return {
        'employee_id': employee_id,
        'employee_name': emp['name'],
        'year': year,
        'month': month,
        'base_salary': emp['daily_salary'],
        'hourly_rate': emp['hourly_salary'],
        'overtime_pay': overtime['total_pay'],
        'leave_deduction': leave['cash_deduction_amount'],
        'net_overtime_pay': net_overtime_pay,
        'details': {
            'overtime_records': overtime_records,
            'leave_records': leave_records,
            'overtime_breakdown': overtime['breakdown']
        }
    }


def calculate_department_salary(
    conn: sqlite3.Connection,
    year: int,
    month: int
) -> List[Dict[str, Any]]:
    """
    计算部门所有员工的工资

    Args:
        conn: 数据库连接
        year: 年份
        month: 月份

    Returns:
        员工工资列表
    """
    cursor = conn.cursor()
    cursor.execute("SELECT employee_id FROM employees")

    results = []
    for row in cursor.fetchall():
        emp_id = row['employee_id']
        try:
            statement = generate_monthly_salary_statement(conn, emp_id, year, month)
            results.append({
                'employee_id': emp_id,
                'employee_name': statement['employee_name'],
                'overtime_pay': statement['overtime_pay'],
                'leave_deduction': statement['leave_deduction'],
                'net_overtime_pay': statement['net_overtime_pay']
            })
        except SalaryServiceError:
            # 跳过无记录的员工
            pass

    return results


def calculate_department_total(
    conn: sqlite3.Connection,
    year: int,
    month: int
) -> Dict[str, Any]:
    """
    计算部门工资总计

    Args:
        conn: 数据库连接
        year: 年份
        month: 月份

    Returns:
        部门总计
    """
    salaries = calculate_department_salary(conn, year, month)

    total_overtime = sum(s['overtime_pay'] for s in salaries)
    total_deduction = sum(s['leave_deduction'] for s in salaries)

    return {
        'year': year,
        'month': month,
        'total_employees': len(salaries),
        'total_overtime_pay': total_overtime,
        'total_leave_deduction': total_deduction,
        'total_net_pay': total_overtime - total_deduction,
        'employee_details': salaries
    }
