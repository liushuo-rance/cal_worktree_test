"""
系统设置路由
提供 Web 界面配置 AI 解析、SMTP 邮件、通知等参数
"""

import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash

from web.utils import get_db
from web.decorators import admin_required

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.config_service import get_all_configs, set_config, build_email_config, build_ai_config

bp = Blueprint('settings', __name__, url_prefix='/settings')


@bp.route('/')
@admin_required
def settings_index():
    """系统设置首页"""
    conn = get_db()
    try:
        configs = get_all_configs(conn)
        ai_config = build_ai_config(conn)
        email_config = build_email_config(conn)
    finally:
        conn.close()

    return render_template(
        'settings/index.html',
        configs=configs,
        ai_configured=bool(ai_config['api_key'] and ai_config['model']),
        email_configured=email_config['is_configured']
    )


@bp.route('/save', methods=['POST'])
@admin_required
def settings_save():
    """保存系统设置"""
    conn = get_db()
    try:
        def _set_or_skip(key: str, value: str, skip_empty: bool = False) -> None:
            """若 skip_empty 为 True 且值为空，则保留现有配置"""
            if skip_empty and not value:
                return
            set_config(conn, key, value)

        # AI 配置
        _set_or_skip('VOLCES_API_KEY', request.form.get('volces_api_key', '').strip(), skip_empty=True)
        _set_or_skip('VOLCES_BASE_URL', request.form.get('volces_base_url', '').strip(), skip_empty=True)
        _set_or_skip('VOLCES_MODEL', request.form.get('volces_model', '').strip())

        # SMTP 配置
        smtp_host = request.form.get('smtp_host', '').strip()
        smtp_port = request.form.get('smtp_port', '587').strip()
        # 国内邮箱通常强制 SSL (465)，自动修正常见误填
        if smtp_port == '587' and any(h in smtp_host for h in ('163.com', '126.com', 'qq.com')):
            smtp_port = '465'

        _set_or_skip('SMTP_HOST', smtp_host)
        _set_or_skip('SMTP_PORT', smtp_port, skip_empty=True)
        _set_or_skip('SMTP_USER', request.form.get('smtp_user', '').strip())
        _set_or_skip('SMTP_PASSWORD', request.form.get('smtp_password', '').strip(), skip_empty=True)
        _set_or_skip('SMTP_FROM', request.form.get('smtp_from', '').strip())

        # 通知配置
        _set_or_skip('HR_NOTIFICATION_EMAIL', request.form.get('hr_notification_email', '').strip())

        flash('系统设置已保存', 'success')
    except sqlite3.Error as e:
        flash(f'保存失败: {str(e)}', 'error')
    finally:
        conn.close()

    return redirect(url_for('settings.settings_index'))
