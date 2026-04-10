"""
审批会话管理服务
提供人工审核队列、审批操作、报告生成功能
"""

from typing import Dict, Any, List, Optional
import sqlite3


class ReviewServiceError(Exception):
    """审批服务异常"""
    pass


def get_pending_reviews(conn: sqlite3.Connection, session_id: int) -> List[Dict[str, Any]]:
    """
    获取指定会话的所有待审核记录

    Args:
        conn: 数据库连接
        session_id: 导入会话ID

    Returns:
        待审核记录列表
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM review_queue
        WHERE import_session_id = ? AND status = 'pending'
        ORDER BY id
    """, (session_id,))

    return [dict(row) for row in cursor.fetchall()]


def get_next_pending_review(conn: sqlite3.Connection, session_id: int) -> Optional[Dict[str, Any]]:
    """
    获取下一个待审核记录

    Args:
        conn: 数据库连接
        session_id: 导入会话ID

    Returns:
        下一条待审核记录，如果没有则返回None
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM review_queue
        WHERE import_session_id = ? AND status = 'pending'
        ORDER BY id
        LIMIT 1
    """, (session_id,))

    row = cursor.fetchone()
    return dict(row) if row else None


def get_review_by_id(conn: sqlite3.Connection, review_id: int) -> Optional[Dict[str, Any]]:
    """
    根据ID获取审核记录

    Args:
        conn: 数据库连接
        review_id: 审核记录ID

    Returns:
        审核记录，如果不存在则返回None
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM review_queue WHERE id = ?
    """, (review_id,))

    row = cursor.fetchone()
    return dict(row) if row else None


def approve_review(
    conn: sqlite3.Connection,
    review_id: int,
    reviewer_note: str = '',
    modifications: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    审批通过

    Args:
        conn: 数据库连接
        review_id: 审核记录ID
        reviewer_note: 审核备注
        modifications: 修改内容

    Returns:
        操作结果

    Raises:
        ReviewServiceError: 记录不存在或已处理
    """
    cursor = conn.cursor()

    # 检查记录是否存在且为pending状态
    cursor.execute("""
        SELECT status FROM review_queue WHERE id = ?
    """, (review_id,))

    row = cursor.fetchone()
    if not row:
        raise ReviewServiceError(f"审核记录 {review_id} 不存在")

    if row['status'] != 'pending':
        raise ReviewServiceError(f"审核记录 {review_id} 已处理，状态: {row['status']}")

    # 应用修改
    if modifications:
        if 'hours' in modifications:
            cursor.execute("""
                UPDATE review_queue
                SET parsed_hours = ?
                WHERE id = ?
            """, (modifications['hours'], review_id))

    # 更新状态
    cursor.execute("""
        UPDATE review_queue
        SET status = 'approved',
            reviewer_note = ?,
            reviewed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (reviewer_note, review_id))

    conn.commit()

    return {'success': True, 'review_id': review_id}


def reject_review(
    conn: sqlite3.Connection,
    review_id: int,
    reason: str = ''
) -> Dict[str, Any]:
    """
    审批拒绝

    Args:
        conn: 数据库连接
        review_id: 审核记录ID
        reason: 拒绝原因

    Returns:
        操作结果

    Raises:
        ReviewServiceError: 记录不存在或已处理
    """
    cursor = conn.cursor()

    # 检查记录是否存在且为pending状态
    cursor.execute("""
        SELECT status FROM review_queue WHERE id = ?
    """, (review_id,))

    row = cursor.fetchone()
    if not row:
        raise ReviewServiceError(f"审核记录 {review_id} 不存在")

    if row['status'] != 'pending':
        raise ReviewServiceError(f"审核记录 {review_id} 已处理，状态: {row['status']}")

    # 更新状态
    cursor.execute("""
        UPDATE review_queue
        SET status = 'rejected',
            reviewer_note = ?,
            reviewed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (reason, review_id))

    conn.commit()

    return {'success': True, 'review_id': review_id}


def batch_approve(
    conn: sqlite3.Connection,
    review_ids: List[int],
    reviewer_note: str = ''
) -> Dict[str, Any]:
    """
    批量审批通过

    Args:
        conn: 数据库连接
        review_ids: 审核记录ID列表
        reviewer_note: 审核备注

    Returns:
        操作结果统计
    """
    success_count = 0

    for review_id in review_ids:
        try:
            approve_review(conn, review_id, reviewer_note)
            success_count += 1
        except ReviewServiceError:
            pass

    return {
        'success_count': success_count,
        'failed_count': len(review_ids) - success_count
    }


def batch_reject(
    conn: sqlite3.Connection,
    review_ids: List[int],
    reason: str = ''
) -> Dict[str, Any]:
    """
    批量审批拒绝

    Args:
        conn: 数据库连接
        review_ids: 审核记录ID列表
        reason: 拒绝原因

    Returns:
        操作结果统计
    """
    success_count = 0

    for review_id in review_ids:
        try:
            reject_review(conn, review_id, reason)
            success_count += 1
        except ReviewServiceError:
            pass

    return {
        'success_count': success_count,
        'failed_count': len(review_ids) - success_count
    }


def batch_approve_high_confidence(
    conn: sqlite3.Connection,
    session_id: int
) -> Dict[str, Any]:
    """
    自动批量通过高置信度记录

    Args:
        conn: 数据库连接
        session_id: 导入会话ID

    Returns:
        操作结果统计
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM review_queue
        WHERE import_session_id = ?
          AND status = 'pending'
          AND confidence_level = 'HIGH'
    """, (session_id,))

    review_ids = [row['id'] for row in cursor.fetchall()]

    return batch_approve(conn, review_ids, '系统自动审批：高置信度')


def generate_import_report(conn: sqlite3.Connection, session_id: int) -> Dict[str, Any]:
    """
    生成导入报告

    Args:
        conn: 数据库连接
        session_id: 导入会话ID

    Returns:
        报告统计
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) as total FROM review_queue WHERE import_session_id = ?
    """, (session_id,))
    total_records = cursor.fetchone()['total']

    cursor.execute("""
        SELECT COUNT(*) as count FROM review_queue
        WHERE import_session_id = ? AND status = 'approved'
    """, (session_id,))
    approved_count = cursor.fetchone()['count']

    cursor.execute("""
        SELECT COUNT(*) as count FROM review_queue
        WHERE import_session_id = ? AND status = 'rejected'
    """, (session_id,))
    rejected_count = cursor.fetchone()['count']

    cursor.execute("""
        SELECT COUNT(*) as count FROM review_queue
        WHERE import_session_id = ? AND status = 'pending'
    """, (session_id,))
    pending_count = cursor.fetchone()['count']

    return {
        'session_id': session_id,
        'total_records': total_records,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'pending_count': pending_count
    }


def generate_detailed_report(conn: sqlite3.Connection, session_id: int) -> Dict[str, Any]:
    """
    生成详细报告

    Args:
        conn: 数据库连接
        session_id: 导入会话ID

    Returns:
        详细报告，包含各状态记录列表
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM review_queue
        WHERE import_session_id = ? AND status = 'approved'
    """, (session_id,))
    approved_records = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT * FROM review_queue
        WHERE import_session_id = ? AND status = 'rejected'
    """, (session_id,))
    rejected_records = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT * FROM review_queue
        WHERE import_session_id = ? AND status = 'pending'
    """, (session_id,))
    pending_records = [dict(row) for row in cursor.fetchall()]

    return {
        'session_id': session_id,
        'approved_records': approved_records,
        'rejected_records': rejected_records,
        'pending_records': pending_records
    }


def start_review_session(conn: sqlite3.Connection, session_id: int) -> Dict[str, Any]:
    """
    开始审核会话

    Args:
        conn: 数据库连接
        session_id: 导入会话ID

    Returns:
        操作结果
    """
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE import_sessions
        SET status = 'reviewing'
        WHERE id = ?
    """, (session_id,))

    conn.commit()

    return {'success': True}


def complete_review_session(conn: sqlite3.Connection, session_id: int) -> Dict[str, Any]:
    """
    完成审核会话

    Args:
        conn: 数据库连接
        session_id: 导入会话ID

    Returns:
        操作结果

    Raises:
        ReviewServiceError: 还有未处理的记录
    """
    cursor = conn.cursor()

    # 检查是否还有pending记录
    cursor.execute("""
        SELECT COUNT(*) as count FROM review_queue
        WHERE import_session_id = ? AND status = 'pending'
    """, (session_id,))

    if cursor.fetchone()['count'] > 0:
        raise ReviewServiceError("还有未处理的审核记录")

    cursor.execute("""
        UPDATE import_sessions
        SET status = 'completed'
        WHERE id = ?
    """, (session_id,))

    conn.commit()

    return {'success': True}


def get_review_statistics(conn: sqlite3.Connection, session_id: int) -> Dict[str, Any]:
    """
    获取审核统计

    Args:
        conn: 数据库连接
        session_id: 导入会话ID

    Returns:
        统计数据
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
        FROM review_queue
        WHERE import_session_id = ?
    """, (session_id,))

    row = cursor.fetchone()
    total = row['total'] or 0
    approved = row['approved'] or 0
    rejected = row['rejected'] or 0
    pending = row['pending'] or 0

    approval_rate = approved / total if total > 0 else 0

    return {
        'total': total,
        'approved': approved,
        'rejected': rejected,
        'pending': pending,
        'approval_rate': approval_rate
    }


def get_confidence_distribution(conn: sqlite3.Connection, session_id: int) -> Dict[str, int]:
    """
    获取置信度分布

    Args:
        conn: 数据库连接
        session_id: 导入会话ID

    Returns:
        各置信度级别数量
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            confidence_level,
            COUNT(*) as count
        FROM review_queue
        WHERE import_session_id = ?
        GROUP BY confidence_level
    """, (session_id,))

    distribution = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}

    for row in cursor.fetchall():
        level = row['confidence_level']
        if level in distribution:
            distribution[level] = row['count']

    return distribution
