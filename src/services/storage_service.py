"""
存储服务
提供记录分发、调休自动生成、事务管理功能
兼容 src/db/schema.py 中的表结构
"""

from datetime import date, timedelta
from typing import Dict, Any, List, Optional
import sqlite3


class StorageError(Exception):
    """存储服务异常"""
    pass


def _check_employee_exists(conn: sqlite3.Connection, employee_id: str) -> bool:
    """检查员工是否存在"""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM employees WHERE employee_id = ?",
        (employee_id,)
    )
    return cursor.fetchone() is not None


def _minutes_to_hours_minutes(total_minutes: int) -> tuple:
    """将总分钟数转换为小时和分钟"""
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return hours, minutes


def store_overtime_record(
    conn: sqlite3.Connection,
    employee_id: str,
    work_date: date,
    hours: int,
    minutes: int = 0,
    overtime_type: str = 'weekday_evening',
    description: str = '',
    import_id: Optional[int] = None
) -> int:
    """
    存储加班记录
    """
    if not _check_employee_exists(conn, employee_id):
        raise StorageError(f"员工 {employee_id} 不存在")

    total_minutes = hours * 60 + minutes

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO overtime_records
        (employee_id, work_date, duration_hours, duration_minutes, total_minutes,
         overtime_type, description, source_import_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        employee_id, work_date, hours, minutes, total_minutes,
        overtime_type, description, import_id
    ))

    record_id = cursor.lastrowid

    # 周末加班自动生成调休余额
    if overtime_type == 'weekend':
        _create_comp_off_balance(conn, employee_id, work_date, total_minutes)

    conn.commit()
    return record_id


def store_leave_record(
    conn: sqlite3.Connection,
    employee_id: str,
    leave_date: date,
    hours: int,
    minutes: int = 0,
    leave_type: str = 'personal',
    description: str = '',
    import_id: Optional[int] = None
) -> int:
    """
    存储请假记录
    """
    if not _check_employee_exists(conn, employee_id):
        raise StorageError(f"员工 {employee_id} 不存在")

    total_minutes = hours * 60 + minutes

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO leave_records
        (employee_id, leave_date, duration_hours, duration_minutes, total_minutes,
         leave_type, description, source_import_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        employee_id, leave_date, hours, minutes, total_minutes,
        leave_type, description, import_id
    ))

    conn.commit()
    return cursor.lastrowid


def store_comp_off_usage_record(
    conn: sqlite3.Connection,
    employee_id: str,
    usage_date: date,
    hours: int,
    minutes: int = 0,
    description: str = '',
    import_id: Optional[int] = None
) -> int:
    """
    存储调休使用记录
    """
    if not _check_employee_exists(conn, employee_id):
        raise StorageError(f"员工 {employee_id} 不存在")

    total_minutes = hours * 60 + minutes

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO comp_off_usage_records
        (employee_id, usage_date, duration_hours, duration_minutes, total_minutes,
         description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        employee_id, usage_date, hours, minutes, total_minutes,
        description
    ))

    conn.commit()
    return cursor.lastrowid


def _create_comp_off_balance(
    conn: sqlite3.Connection,
    employee_id: str,
    acquired_date: date,
    total_minutes: int,
    expiry_days: int = 180
) -> int:
    """
    创建调休余额记录
    """
    expiry_date = acquired_date + timedelta(days=expiry_days)
    total_hours, remaining_minutes = _minutes_to_hours_minutes(total_minutes)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO comp_off_balances
        (employee_id, acquired_date, expiry_date, total_hours, total_minutes,
         used_hours, used_minutes, status)
        VALUES (?, ?, ?, ?, ?, 0, 0, 'active')
    """, (
        employee_id, acquired_date, expiry_date,
        total_hours, remaining_minutes
    ))

    conn.commit()
    return cursor.lastrowid


def get_comp_off_for_overtime(
    conn: sqlite3.Connection,
    overtime_id: int
) -> Optional[Dict[str, Any]]:
    """
    获取加班记录对应的调休余额
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM comp_off_balances
        WHERE employee_id = (
            SELECT employee_id FROM overtime_records WHERE id = ?
        )
          AND acquired_date = (
            SELECT work_date FROM overtime_records WHERE id = ?
          )
    """, (overtime_id, overtime_id))

    row = cursor.fetchone()
    return dict(row) if row else None


def _store_overtime_record_no_commit(
    conn: sqlite3.Connection,
    employee_id: str,
    work_date: date,
    hours: int,
    minutes: int = 0,
    overtime_type: str = 'weekday_evening',
    description: str = '',
    import_id: Optional[int] = None
) -> int:
    """存储加班记录（不提交事务）"""
    total_minutes = hours * 60 + minutes

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO overtime_records
        (employee_id, work_date, duration_hours, duration_minutes, total_minutes,
         overtime_type, description, source_import_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        employee_id, work_date, hours, minutes, total_minutes,
        overtime_type, description, import_id
    ))

    record_id = cursor.lastrowid

    # 周末加班自动生成调休余额
    if overtime_type == 'weekend':
        _create_comp_off_balance(conn, employee_id, work_date, total_minutes)

    return record_id


def _store_leave_record_no_commit(
    conn: sqlite3.Connection,
    employee_id: str,
    leave_date: date,
    hours: int,
    minutes: int = 0,
    leave_type: str = 'personal',
    description: str = '',
    import_id: Optional[int] = None
) -> int:
    """存储请假记录（不提交事务）"""
    total_minutes = hours * 60 + minutes

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO leave_records
        (employee_id, leave_date, duration_hours, duration_minutes, total_minutes,
         leave_type, description, source_import_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        employee_id, leave_date, hours, minutes, total_minutes,
        leave_type, description, import_id
    ))

    return cursor.lastrowid


def _store_comp_off_usage_no_commit(
    conn: sqlite3.Connection,
    employee_id: str,
    usage_date: date,
    hours: int,
    minutes: int = 0,
    description: str = '',
    import_id: Optional[int] = None
) -> int:
    """存储调休使用记录（不提交事务）"""
    total_minutes = hours * 60 + minutes

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO comp_off_usage_records
        (employee_id, usage_date, duration_hours, duration_minutes, total_minutes,
         description)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        employee_id, usage_date, hours, minutes, total_minutes,
        description
    ))

    return cursor.lastrowid


def store_batch_records(
    conn: sqlite3.Connection,
    records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    批量存储记录
    """
    success_count = 0
    failed_count = 0

    try:
        for record in records:
            record_type = record.get('type')
            employee_id = record.get('employee_id')
            record_date = record.get('date')
            hours = record.get('hours', 0)

            # 检查员工存在性
            if not _check_employee_exists(conn, employee_id):
                raise StorageError(f"员工 {employee_id} 不存在")

            # 转换为整数小时和分钟
            total_minutes = int(round(hours * 60))
            int_hours = total_minutes // 60
            int_minutes = total_minutes % 60

            if record_type == 'overtime':
                _store_overtime_record_no_commit(
                    conn,
                    employee_id=employee_id,
                    work_date=record_date,
                    hours=int_hours,
                    minutes=int_minutes,
                    overtime_type=record.get('overtime_type', 'weekday_evening'),
                    description=record.get('description', '')
                )
                success_count += 1
            elif record_type == 'leave':
                _store_leave_record_no_commit(
                    conn,
                    employee_id=employee_id,
                    leave_date=record_date,
                    hours=int_hours,
                    minutes=int_minutes,
                    leave_type=record.get('leave_type', 'personal'),
                    description=record.get('description', '')
                )
                success_count += 1
            elif record_type == 'comp_off':
                _store_comp_off_usage_no_commit(
                    conn,
                    employee_id=employee_id,
                    usage_date=record_date,
                    hours=int_hours,
                    minutes=int_minutes,
                    description=record.get('description', '')
                )
                success_count += 1
            else:
                failed_count += 1

        # 所有记录成功后才提交
        conn.commit()

        return {
            'success_count': success_count,
            'failed_count': failed_count
        }

    except Exception as e:
        # 事务回滚
        conn.rollback()
        raise StorageError(f"批量存储失败: {str(e)}")


def store_batch_records_with_session(
    conn: sqlite3.Connection,
    employee_id: str,
    records: List[Dict[str, Any]],
    file_name: str
) -> int:
    """
    带导入会话的批量存储
    """
    # 创建导入会话
    session_id = create_import_session(conn, file_name)

    try:
        # 批量存储
        result = store_batch_records(conn, records)

        # 更新会话统计
        update_import_session_stats(
            conn,
            session_id=session_id,
            total=len(records),
            processed=result['success_count'],
            failed=result['failed_count']
        )

        # 标记会话完成
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE import_sessions
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (session_id,))
        conn.commit()

        return session_id

    except Exception as e:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE import_sessions
            SET status = 'failed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (session_id,))
        conn.commit()
        raise StorageError(f"批量存储失败: {str(e)}")


def create_import_session(
    conn: sqlite3.Connection,
    file_path: str
) -> int:
    """
    创建导入会话
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO import_sessions
        (file_path, status, total_records, processed_records, error_records)
        VALUES (?, 'pending', 0, 0, 0)
    """, (file_path,))

    conn.commit()
    return cursor.lastrowid


def update_import_session_stats(
    conn: sqlite3.Connection,
    session_id: int,
    total: int,
    processed: int,
    failed: int
) -> None:
    """
    更新导入会话统计
    """
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE import_sessions
        SET total_records = ?,
            processed_records = ?,
            error_records = ?
        WHERE id = ?
    """, (total, processed, failed, session_id))

    conn.commit()
