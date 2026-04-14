"""
通知中心路由
"""

import sqlite3
from flask import Blueprint, render_template, redirect, url_for, flash, request

from web.utils import get_db

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.notification_service import get_notification_stats, send_comp_off_expiry_notification
from services.email_service import build_email_config

bp = Blueprint('notifications', __name__, url_prefix='/notifications')


@bp.route('/')
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


@bp.route('/send/comp-off-expiry', methods=['POST'])
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
