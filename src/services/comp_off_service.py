"""
调休余额服务
提供调休余额计算、FIFO抵扣、过期管理功能
兼容 src/db/schema.py 中的表结构
"""

import sqlite3
from datetime import date, timedelta
from typing import List, Dict, Any, Optional


class CompOffError(Exception):
    """调休服务错误"""
    pass


def _minutes_to_hours_minutes(total_minutes: int) -> tuple:
    """将总分钟数转换为小时和分钟"""
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return hours, minutes


def get_total_acquired(conn: sqlite3.Connection, employee_id: str) -> int:
    """
    获取累计获得的调休时长（分钟）
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(total_hours * 60 + total_minutes) as total
        FROM comp_off_balances
        WHERE employee_id = ?
    """, (employee_id,))

    row = cursor.fetchone()
    return row['total'] or 0


def get_total_used(conn: sqlite3.Connection, employee_id: str) -> int:
    """
    获取累计使用的调休时长（分钟）
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(used_hours * 60 + used_minutes) as total
        FROM comp_off_balances
        WHERE employee_id = ?
    """, (employee_id,))

    row = cursor.fetchone()
    return row['total'] or 0


def get_remaining_balance(conn: sqlite3.Connection, employee_id: str) -> int:
    """
    获取剩余调休余额（分钟）
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(
            (total_hours * 60 + total_minutes)
            - (used_hours * 60 + used_minutes)
        ) as total
        FROM comp_off_balances
        WHERE employee_id = ?
          AND status = 'active'
          AND (expiry_date IS NULL OR expiry_date >= date('now'))
    """, (employee_id,))

    row = cursor.fetchone()
    return row['total'] or 0


def get_balance_breakdown(
    conn: sqlite3.Connection,
    employee_id: str
) -> List[Dict[str, Any]]:
    """
    获取调休余额明细
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            id,
            acquired_date,
            total_hours,
            total_minutes,
            used_hours,
            used_minutes,
            expiry_date,
            status,
            (total_hours * 60 + total_minutes - used_hours * 60 - used_minutes) as remaining_minutes
        FROM comp_off_balances
        WHERE employee_id = ?
          AND status = 'active'
          AND (expiry_date IS NULL OR expiry_date >= date('now'))
          AND (total_hours * 60 + total_minutes - used_hours * 60 - used_minutes) > 0
        ORDER BY acquired_date ASC
    """, (employee_id,))

    return [dict(row) for row in cursor.fetchall()]


def deduct_comp_off(
    conn: sqlite3.Connection,
    employee_id: str,
    deduction_date: date,
    minutes_needed: int,
    leave_record_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    抵扣调休（FIFO算法）
    """
    # 检查总余额
    remaining = get_remaining_balance(conn, employee_id)
    if remaining < minutes_needed:
        raise CompOffError(
            f"调休余额不足: 需要{minutes_needed}分钟, 可用{remaining}分钟"
        )

    # 获取可用余额（按获取时间排序，FIFO）
    balances = get_balance_breakdown(conn, employee_id)

    deductions = []
    minutes_to_deduct = minutes_needed

    cursor = conn.cursor()

    for balance in balances:
        if minutes_to_deduct <= 0:
            break

        available = balance['remaining_minutes']
        deduct = min(available, minutes_to_deduct)

        # 计算新的 used_hours / used_minutes
        total_used_minutes = (balance['used_hours'] * 60 + balance['used_minutes']) + deduct
        new_used_hours, new_used_minutes = _minutes_to_hours_minutes(total_used_minutes)

        # 更新余额
        cursor.execute("""
            UPDATE comp_off_balances
            SET used_hours = ?, used_minutes = ?
            WHERE id = ?
        """, (new_used_hours, new_used_minutes, balance['id']))

        deductions.append({
            'balance_id': balance['id'],
            'acquired_date': balance['acquired_date'],
            'deducted_minutes': deduct,
            'remaining_after': available - deduct
        })

        minutes_to_deduct -= deduct

    conn.commit()

    return {
        'success': True,
        'deducted_minutes': minutes_needed,
        'deductions': deductions
    }


def create_pending_comp_off_request(
    conn: sqlite3.Connection,
    employee_id: str,
    usage_date: date,
    minutes_needed: int,
    description: str = '',
    leave_record_id: Optional[int] = None
) -> int:
    """
    创建待审批的调休申请
    不扣除 comp_off_balances，只写入 comp_off_usage_records 并标记为 pending
    """
    hours, minutes = _minutes_to_hours_minutes(minutes_needed)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO comp_off_usage_records
        (employee_id, usage_date, leave_record_id, duration_hours, duration_minutes,
         total_minutes, description, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
    """, (
        employee_id, usage_date.isoformat(), leave_record_id,
        hours, minutes, minutes_needed, description
    ))
    conn.commit()
    return cursor.lastrowid


def approve_comp_off_request(
    conn: sqlite3.Connection,
    request_id: int
) -> Dict[str, Any]:
    """
    批准调休申请：执行余额扣除，并将状态更新为 approved
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT employee_id, usage_date, total_minutes, leave_record_id, status
        FROM comp_off_usage_records
        WHERE id = ?
    """, (request_id,))
    row = cursor.fetchone()
    if not row:
        raise CompOffError(f"调休申请不存在: {request_id}")

    if row['status'] != 'pending':
        raise CompOffError(f"只能批准待审批的申请，当前状态: {row['status']}")

    employee_id = row['employee_id']
    usage_date = date.fromisoformat(row['usage_date'])
    minutes_needed = row['total_minutes']
    leave_record_id = row['leave_record_id']

    # 执行余额扣除
    deduction_result = deduct_comp_off(
        conn, employee_id, usage_date, minutes_needed, leave_record_id
    )

    # 更新状态
    cursor.execute("""
        UPDATE comp_off_usage_records
        SET status = 'approved'
        WHERE id = ?
    """, (request_id,))
    conn.commit()

    deduction_result['request_id'] = request_id
    return deduction_result


def reject_comp_off_request(
    conn: sqlite3.Connection,
    request_id: int
) -> None:
    """
    拒绝调休申请：仅将状态更新为 rejected，不扣除余额
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT status FROM comp_off_usage_records WHERE id = ?
    """, (request_id,))
    row = cursor.fetchone()
    if not row:
        raise CompOffError(f"调休申请不存在: {request_id}")

    if row['status'] != 'pending':
        raise CompOffError(f"只能拒绝待审批的申请，当前状态: {row['status']}")

    cursor.execute("""
        UPDATE comp_off_usage_records
        SET status = 'rejected'
        WHERE id = ?
    """, (request_id,))
    conn.commit()


def get_expiring_balances(
    conn: sqlite3.Connection,
    reference_date: Optional[date] = None,
    days_threshold: int = 30
) -> List[Dict[str, Any]]:
    """
    获取即将过期的调休余额
    """
    if reference_date is None:
        reference_date = date.today()

    expiry_threshold = reference_date + timedelta(days=days_threshold)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            b.id,
            b.employee_id,
            e.name as employee_name,
            b.acquired_date,
            (b.total_hours * 60 + b.total_minutes - b.used_hours * 60 - b.used_minutes) as remaining_minutes,
            b.expiry_date,
            julianday(b.expiry_date) - julianday(?) as days_remaining
        FROM comp_off_balances b
        JOIN employees e ON b.employee_id = e.employee_id
        WHERE b.status = 'active'
          AND (b.total_hours * 60 + b.total_minutes - b.used_hours * 60 - b.used_minutes) > 0
          AND b.expiry_date IS NOT NULL
          AND b.expiry_date <= ?
          AND b.expiry_date >= ?
        ORDER BY b.expiry_date ASC
    """, (reference_date.isoformat(), expiry_threshold.isoformat(),
          reference_date.isoformat()))

    return [dict(row) for row in cursor.fetchall()]


def expire_balance(conn: sqlite3.Connection, balance_id: int) -> None:
    """
    将余额标记为过期
    """
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE comp_off_balances
        SET status = 'expired'
        WHERE id = ?
    """, (balance_id,))
    conn.commit()


def create_comp_off_from_overtime(
    conn: sqlite3.Connection,
    overtime_id: int
) -> int:
    """
    从周末加班记录创建调休余额
    """
    cursor = conn.cursor()

    # 获取加班记录
    cursor.execute("""
        SELECT employee_id, work_date, total_minutes, overtime_type
        FROM overtime_records
        WHERE id = ?
    """, (overtime_id,))

    row = cursor.fetchone()
    if not row:
        raise CompOffError(f"加班记录不存在: {overtime_id}")

    # 只有周末加班才生成调休
    if row['overtime_type'] != 'weekend':
        raise CompOffError(
            f"只有周末加班才能生成调休, 当前类型: {row['overtime_type']}"
        )

    employee_id = row['employee_id']
    work_date = row['work_date']
    total_minutes = row['total_minutes']
    total_hours, remaining_minutes = _minutes_to_hours_minutes(total_minutes)

    # 计算过期日期（6个月后）
    work_date_obj = date.fromisoformat(work_date)
    expiry_date = work_date_obj + timedelta(days=180)

    # 创建调休余额
    cursor.execute(
        """
        INSERT INTO comp_off_balances
        (employee_id, acquired_date, expiry_date,
         total_hours, total_minutes, used_hours, used_minutes)
        VALUES (?, ?, ?, ?, ?, 0, 0)
        """,
        (employee_id, work_date, expiry_date.isoformat(),
         total_hours, remaining_minutes)
    )

    conn.commit()
    return cursor.lastrowid


def apply_comp_off_to_leave(
    conn: sqlite3.Connection,
    employee_id: str,
    leave_date: date,
    leave_minutes: int,
    leave_record_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    将调休应用到请假
    创建 pending 状态的调休申请, 不立即扣除余额
    """
    remaining_balance = get_remaining_balance(conn, employee_id)

    # 计算可用抵扣
    available = min(remaining_balance, leave_minutes)
    cash_deduction = leave_minutes - available

    result = {
        'success': True,
        'leave_minutes': leave_minutes,
        'covered_minutes': 0,
        'cash_deduction_minutes': cash_deduction
    }

    if available > 0:
        # 创建待审批的调休申请, 不立即扣减余额
        request_id = create_pending_comp_off_request(
            conn, employee_id, leave_date, available, '', leave_record_id
        )
        result['covered_minutes'] = available
        result['pending_request_id'] = request_id

    return result
