"""
通知服务
调休到期提醒的扫描、渲染、发送与历史记录
"""

import os
import sqlite3
from datetime import date
from typing import List, Dict, Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.services.comp_off_service import get_expiring_balances
from src.services.email_service import build_email_config, send_email


_email_template_dir = os.path.join(
    os.path.dirname(__file__), '..', 'web', 'templates', 'email'
)
env = Environment(
    loader=FileSystemLoader(_email_template_dir),
    autoescape=select_autoescape(['html', 'xml'])
)


def get_notification_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    获取通知发送历史统计

    Args:
        conn: 数据库连接

    Returns:
        统计信息
    """
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM notification_history")
    total_sent = cursor.fetchone()['total']

    cursor.execute("""
        SELECT sent_at, status, content_summary
        FROM notification_history
        ORDER BY sent_at DESC
        LIMIT 1
    """)
    last_row = cursor.fetchone()

    cursor.execute("""
        SELECT sent_at, status, content_summary, error_message
        FROM notification_history
        ORDER BY sent_at DESC
        LIMIT 10
    """)
    recent_history = [dict(row) for row in cursor.fetchall()]

    return {
        'total_sent': total_sent,
        'last_sent_at': last_row['sent_at'] if last_row else None,
        'last_status': last_row['status'] if last_row else None,
        'last_summary': last_row['content_summary'] if last_row else None,
        'recent_history': recent_history
    }


def _render_comp_off_email(
    balances: List[Dict[str, Any]],
    reference_date: date,
    days_threshold: int
) -> str:
    """
    渲染调休到期提醒邮件 HTML

    Args:
        balances: 即将过期的余额列表
        reference_date: 参考日期
        days_threshold: 阈值天数

    Returns:
        HTML 字符串
    """
    template = env.get_template('comp_off_expiry.html')
    return template.render(
        balances=balances,
        reference_date=reference_date.isoformat(),
        days_threshold=days_threshold,
        employee_count=len({b['employee_id'] for b in balances}),
        record_count=len(balances)
    )


def send_comp_off_expiry_notification(
    conn: sqlite3.Connection,
    recipient_emails: List[str],
    reference_date: Optional[date] = None,
    days_threshold: int = 30,
    trigger_mode: str = 'manual'
) -> Dict[str, Any]:
    """
    发送调休到期提醒邮件

    Args:
        conn: 数据库连接
        recipient_emails: 收件人邮箱列表
        reference_date: 参考日期（默认今天）
        days_threshold: 到期天数阈值
        trigger_mode: 触发方式 ('manual' | 'scheduled')

    Returns:
        发送结果
    """
    if reference_date is None:
        reference_date = date.today()

    balances = get_expiring_balances(conn, reference_date, days_threshold)

    html_body = _render_comp_off_email(balances, reference_date, days_threshold)
    subject = f"调休余额到期提醒 - {reference_date.isoformat()}"

    email_config = build_email_config(conn=conn)
    sent_count = 0
    failed_count = 0

    for email in recipient_emails:
        result = send_email(
            to=email,
            subject=subject,
            html_body=html_body,
            smtp_host=email_config['host'],
            smtp_port=email_config['port'],
            smtp_user=email_config['user'],
            smtp_password=email_config['password'],
            from_addr=email_config['from_addr']
        )

        summary = f"{len({b['employee_id'] for b in balances})}人共{len(balances)}条余额即将到期" if balances else "今日暂无即将到期余额"

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notification_history
            (notification_type, trigger_mode, recipient_email, status,
             error_message, content_summary, days_threshold)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            'comp_off_expiry',
            trigger_mode,
            email,
            'success' if result['success'] else 'failed',
            result.get('error') if not result['success'] else None,
            summary,
            days_threshold
        ))
        conn.commit()

        if result['success']:
            sent_count += 1
        else:
            failed_count += 1

    return {
        'success': failed_count == 0,
        'sent_count': sent_count,
        'failed_count': failed_count,
        'balances_found': len(balances)
    }


def run_scheduled_comp_off_notification(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    执行每日自动调休到期提醒（供调度器调用）

    Args:
        conn: 数据库连接

    Returns:
        发送结果
    """
    try:
        from flask import current_app
        logger = current_app.logger
    except RuntimeError:
        import logging
        logger = logging.getLogger(__name__)

    email_config = build_email_config(conn=conn)
    if not email_config['is_configured']:
        logger.warning("调休到期自动提醒跳过：SMTP 或 HR 邮箱未配置")
        return {'success': False, 'reason': 'email_not_configured'}

    return send_comp_off_expiry_notification(
        conn,
        recipient_emails=email_config['hr_emails'],
        trigger_mode='scheduled'
    )
