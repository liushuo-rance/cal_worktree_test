"""
通知中心路由
"""

import sqlite3
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify

from web.utils import get_db
from web.decorators import admin_required

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.notification_service import get_notification_stats, send_comp_off_expiry_notification
from services.email_service import build_email_config

bp = Blueprint('notifications', __name__, url_prefix='/notifications')


@bp.route('/')
@admin_required
def notification_center():
    """通知中心首页"""
    conn = get_db()
    try:
        stats = get_notification_stats(conn)
    except sqlite3.Error as e:
        stats = {
            'total_sent': 0,
            'last_sent_at': None,
            'last_status': None,
            'last_summary': None,
            'recent_history': []
        }

    email_config = build_email_config(conn=conn)
    conn.close()

    return render_template(
        'notifications/index.html',
        stats=stats,
        email_configured=email_config['is_configured'],
        hr_emails=email_config['hr_emails']
    )


@bp.route('/inbox')
def inbox():
    """站内通知收件箱"""
    return render_template('notifications/inbox.html')


@bp.route('/api/unread-count')
def api_unread_count():
    """获取未读通知数量"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as count FROM notifications WHERE is_read = 0
    """)
    row = cursor.fetchone()
    conn.close()
    return jsonify({'unread_count': row['count'] if row else 0})


@bp.route('/api/list')
def api_list():
    """获取通知列表，支持筛选"""
    filter_param = request.args.get('filter', 'all')
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT id, employee_id, type, title, content, is_read, created_at
        FROM notifications
    """
    params: tuple = ()

    if filter_param == 'unread':
        query += " WHERE is_read = 0"
    elif filter_param == 'read':
        query += " WHERE is_read = 1"

    query += " ORDER BY created_at DESC, id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    notifications = [
        {
            'id': row['id'],
            'employee_id': row['employee_id'],
            'type': row['type'],
            'title': row['title'],
            'content': row['content'],
            'is_read': bool(row['is_read']),
            'created_at': row['created_at'],
        }
        for row in rows
    ]

    return jsonify(notifications)


@bp.route('/api/mark-read/<int:notification_id>', methods=['POST'])
def api_mark_read(notification_id: int):
    """标记单条通知为已读"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ?",
        (notification_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@bp.route('/api/mark-all-read', methods=['POST'])
def api_mark_all_read():
    """标记所有通知为已读"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1")
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@bp.route('/api/delete/<int:notification_id>', methods=['POST'])
def api_delete(notification_id: int):
    """删除单条通知"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@bp.route('/send/comp-off-expiry', methods=['POST'])
@admin_required
def send_comp_off_expiry():
    """手动发送调休到期提醒"""
    conn = get_db()
    email_config = build_email_config(conn=conn)

    if not email_config['is_configured']:
        flash('未配置邮件收件人，请联系管理员', 'error')
        conn.close()
        return redirect(url_for('notifications.notification_center'))

    try:
        result = send_comp_off_expiry_notification(
            conn,
            recipient_emails=email_config['hr_emails'],
            trigger_mode='manual'
        )

        if result['success']:
            flash(f'提醒邮件发送成功，共 {result["balances_found"]} 条到期余额', 'success')
        else:
            flash('部分邮件发送失败，请查看日志', 'warning')
    except Exception as e:
        flash(f'发送失败: {str(e)}', 'error')
    finally:
        conn.close()

    return redirect(url_for('notifications.notification_center'))
