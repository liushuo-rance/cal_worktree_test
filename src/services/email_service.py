"""
邮件发送服务
SMTP 配置读取与发送封装
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import Dict, Any, List, Optional
import sqlite3


def build_email_config(env: Dict[str, str] = None, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """
    从环境变量或数据库配置构建邮件配置

    Args:
        env: 环境变量字典，默认使用 os.environ
        conn: 数据库连接，若提供则优先从 config_service 读取

    Returns:
        邮件配置字典
    """
    if conn is not None:
        try:
            from services.config_service import build_email_config as _build_from_db
            return _build_from_db(conn)
        except Exception:
            pass

    if env is None:
        env = os.environ

    host = env.get('SMTP_HOST', '')
    port = int(env.get('SMTP_PORT', '587') or '587')
    user = env.get('SMTP_USER', '')
    password = env.get('SMTP_PASSWORD', '')
    from_addr = env.get('SMTP_FROM', user)
    hr_raw = env.get('HR_NOTIFICATION_EMAIL', '')
    hr_emails = [e.strip() for e in hr_raw.split(',') if e.strip()] if hr_raw else []

    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'from_addr': from_addr,
        'hr_emails': hr_emails,
        'is_configured': bool(host and user and password and hr_emails)
    }


def send_email(
    to: str,
    subject: str,
    html_body: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_addr: str = None
) -> Dict[str, Any]:
    """
    发送 HTML 邮件

    Args:
        to: 收件人邮箱
        subject: 邮件主题
        html_body: HTML 正文
        smtp_host: SMTP 服务器
        smtp_port: SMTP 端口
        smtp_user: SMTP 用户名
        smtp_password: SMTP 密码
        from_addr: 发件人邮箱（默认同 smtp_user）

    Returns:
        发送结果
    """
    if from_addr is None:
        from_addr = smtp_user

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = formataddr((from_addr, smtp_user)) if from_addr != smtp_user else smtp_user
    msg['To'] = to

    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()

        with server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}
