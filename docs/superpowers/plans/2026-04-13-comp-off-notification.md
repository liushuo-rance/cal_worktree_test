# 调休到期提醒邮件通知系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为加班记录管理系统增加调休余额到期邮件提醒功能，支持 Web/CLI 手动触发和 APScheduler 每天自动触发。

**Architecture:** 新增独立的 `notification_service.py` + `email_service.py`，通过读取 `comp_off_balances` 生成 HTML 邮件并发送给 HR；发送记录写入 `notification_history` 表；Web 端提供通知中心页面和手动触发按钮；CLI 提供 `notify comp-off-expiry` 命令。

**Tech Stack:** Flask, Jinja2, smtplib, APScheduler, SQLite, pytest

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/db/schema.py` | 新增 `notification_history` 表 |
| `src/services/email_service.py` | SMTP 配置读取与邮件发送封装 |
| `src/services/notification_service.py` | 扫描到期余额、渲染邮件、写入历史、调度入口 |
| `src/cli/commands.py` | 新增 `notify_comp_off_expiry()` CLI 命令 |
| `src/web/routes/notifications.py` | Web 路由：通知中心、手动发送 |
| `src/web/templates/notifications/index.html` | 通知中心页面 |
| `src/web/templates/email/comp_off_expiry.html` | 邮件 HTML 模板 |
| `src/web/templates/reports/comp_off.html` | 右上角增加「到期提醒」快捷入口 |
| `src/web/templates/base.html` | Sidebar 增加「通知中心」导航项 |
| `src/web/__init__.py` | 集成 APScheduler，注册 notifications 蓝图 |
| `tests/test_notification_service.py` | 通知服务单元测试 |
| `tests/test_email_service.py` | 邮件服务单元测试 |
| `tests/test_web_notifications.py` | Web 路由测试 |

---

## Task 1: Database Schema — notification_history 表

**Files:**
- Modify: `src/db/schema.py`
- Test: `tests/test_db_schema.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_db_schema.py`,新增测试类：

```python
class TestNotificationHistorySchema:
    """通知历史表结构测试"""

    def test_notification_history_columns(self, initialized_db):
        """通知历史表应包含正确的列"""
        cursor = initialized_db.cursor()
        cursor.execute("PRAGMA table_info(notification_history)")
        columns = {row['name'] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'notification_type', 'trigger_mode', 'recipient_email',
            'employee_id', 'sent_at', 'status', 'error_message',
            'content_summary', 'days_threshold'
        }
        assert expected_columns.issubset(columns)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db_schema.py::TestNotificationHistorySchema::test_notification_history_columns -v`

Expected: FAIL — `no such table: notification_history`

- [ ] **Step 3: Implement schema change**

In `src/db/schema.py`,在 `init_database()` 函数末尾（索引创建之后、`conn.commit()` 之前）新增：

```python
    # 通知历史表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notification_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_type TEXT NOT NULL,
            trigger_mode TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            employee_id TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            error_message TEXT,
            content_summary TEXT,
            days_threshold INTEGER
        )
    """)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db_schema.py::TestNotificationHistorySchema::test_notification_history_columns -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/db/schema.py tests/test_db_schema.py
git commit -m "feat: add notification_history table"
```

---

## Task 2: Email Service

**Files:**
- Create: `src/services/email_service.py`
- Test: `tests/test_email_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_email_service.py`:

```python
"""
邮件服务测试
"""

import pytest
from unittest.mock import patch, MagicMock


class TestEmailService:
    """邮件服务测试"""

    def test_build_email_config_from_env(self):
        """应从环境变量构建邮件配置"""
        from src.services.email_service import build_email_config

        env = {
            'SMTP_HOST': 'smtp.example.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'user@example.com',
            'SMTP_PASSWORD': 'secret',
            'SMTP_FROM': 'noreply@example.com',
            'HR_NOTIFICATION_EMAIL': 'hr@example.com,admin@example.com'
        }

        config = build_email_config(env)
        assert config['host'] == 'smtp.example.com'
        assert config['port'] == 587
        assert config['user'] == 'user@example.com'
        assert config['password'] == 'secret'
        assert config['from_addr'] == 'noreply@example.com'
        assert config['hr_emails'] == ['hr@example.com', 'admin@example.com']

    def test_build_email_config_missing(self):
        """关键配置缺失时应返回不完整标记"""
        from src.services.email_service import build_email_config

        config = build_email_config({})
        assert config['is_configured'] is False

    @patch('src.services.email_service.smtplib.SMTP')
    def test_send_email_success(self, mock_smtp_class):
        """发送邮件成功"""
        from src.services.email_service import send_email

        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        result = send_email(
            to='hr@example.com',
            subject='Test Subject',
            html_body='<h1>Test</h1>',
            smtp_host='smtp.example.com',
            smtp_port=587,
            smtp_user='user@example.com',
            smtp_password='secret',
            from_addr='noreply@example.com'
        )

        assert result['success'] is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('user@example.com', 'secret')
        mock_server.send_message.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_email_service.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.email_service'`

- [ ] **Step 3: Implement email service**

Create `src/services/email_service.py`:

```python
"""
邮件发送服务
SMTP 配置读取与发送封装
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List


def build_email_config(env: Dict[str, str] = None) -> Dict[str, Any]:
    """
    从环境变量构建邮件配置

    Args:
        env: 环境变量字典，默认使用 os.environ

    Returns:
        邮件配置字典
    """
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
    msg['From'] = from_addr
    msg['To'] = to

    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_email_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/email_service.py tests/test_email_service.py
git commit -m "feat: add email service with SMTP wrapper"
```

---

## Task 3: Notification Service

**Files:**
- Create: `src/services/notification_service.py`
- Create: `src/web/templates/email/comp_off_expiry.html`
- Test: `tests/test_notification_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_notification_service.py`:

```python
"""
通知服务测试
"""

import pytest
from datetime import date
import sqlite3
from unittest.mock import patch, MagicMock


@pytest.fixture
def memory_db():
    """内存数据库"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            employee_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL
        );
        CREATE TABLE comp_off_balances (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            acquired_date DATE NOT NULL,
            total_minutes INTEGER NOT NULL,
            remaining_minutes INTEGER NOT NULL,
            expiry_date DATE,
            status TEXT DEFAULT 'active'
        );
        CREATE TABLE notification_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_type TEXT NOT NULL,
            trigger_mode TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            employee_id TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            error_message TEXT,
            content_summary TEXT,
            days_threshold INTEGER
        );
        INSERT INTO employees (employee_id, name) VALUES
            ('EMP001', '张三'),
            ('EMP002', '李四');
        INSERT INTO comp_off_balances (employee_id, acquired_date, total_minutes, remaining_minutes, expiry_date, status)
        VALUES
            ('EMP001', '2026-01-10', 240, 120, '2026-07-10', 'active'),
            ('EMP002', '2026-01-11', 300, 300, '2026-07-11', 'active');
    """)
    conn.commit()
    yield conn
    conn.close()


class TestNotificationService:
    """通知服务测试"""

    def test_get_notification_stats(self, memory_db):
        """应能读取通知发送历史统计"""
        from src.services.notification_service import get_notification_stats

        stats = get_notification_stats(memory_db)
        assert stats['total_sent'] == 0
        assert stats['last_sent_at'] is None

    @patch('src.services.notification_service.send_email')
    def test_send_comp_off_expiry_notification(self, mock_send_email, memory_db):
        """手动触发应正确发送邮件并记录历史"""
        from src.services.notification_service import send_comp_off_expiry_notification

        mock_send_email.return_value = {'success': True}

        result = send_comp_off_expiry_notification(
            memory_db,
            recipient_emails=['hr@example.com'],
            reference_date=date(2026, 6, 15),
            days_threshold=30,
            trigger_mode='manual'
        )

        assert result['success'] is True
        assert result['sent_count'] == 1
        mock_send_email.assert_called_once()

        # 验证历史记录
        cursor = memory_db.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM notification_history")
        assert cursor.fetchone()['count'] == 1

    @patch('src.services.notification_service.send_email')
    def test_send_with_no_expiring_balances(self, mock_send_email, memory_db):
        """无到期余额时也应发送一封汇总邮件"""
        from src.services.notification_service import send_comp_off_expiry_notification

        mock_send_email.return_value = {'success': True}

        result = send_comp_off_expiry_notification(
            memory_db,
            recipient_emails=['hr@example.com'],
            reference_date=date(2026, 1, 1),
            days_threshold=30,
            trigger_mode='manual'
        )

        assert result['success'] is True
        assert result['sent_count'] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_notification_service.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.notification_service'`

- [ ] **Step 3: Create email template**

Create `src/web/templates/email/comp_off_expiry.html`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>调休余额到期提醒</title>
    <style>
        body { font-family: Inter, -apple-system, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }
        .container { max-width: 640px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 24px; }
        .header { font-size: 18px; font-weight: 700; color: #000666; margin-bottom: 16px; }
        .summary { background: #f3f2fe; border-radius: 6px; padding: 16px; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th { background: #000666; color: #ffffff; text-align: left; padding: 10px 8px; }
        td { border-bottom: 1px solid #e2e1ed; padding: 10px 8px; }
        .numeric { text-align: right; }
        .footer { margin-top: 24px; font-size: 12px; color: #767683; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">调休余额到期提醒 - {{ reference_date }}</div>

    <div class="summary">
        <strong>汇总：</strong>共 <strong>{{ employee_count }}</strong> 位员工、<strong>{{ record_count }}</strong> 条调休余额将在 <strong>{{ days_threshold }}</strong> 天内到期。
    </div>

    {% if balances %}
    <table>
        <thead>
            <tr>
                <th>员工姓名</th>
                <th>获得日期</th>
                <th class="numeric">剩余时长（小时）</th>
                <th>到期日期</th>
                <th class="numeric">剩余天数</th>
            </tr>
        </thead>
        <tbody>
            {% for b in balances %}
            <tr>
                <td>{{ b.employee_name }}</td>
                <td>{{ b.acquired_date }}</td>
                <td class="numeric">{{ "%.2f"|format(b.remaining_minutes / 60) }}</td>
                <td>{{ b.expiry_date }}</td>
                <td class="numeric">{{ b.days_remaining|int }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p style="text-align:center; color:#767683;">今日暂无即将到期的调休余额。</p>
    {% endif %}

    <div class="footer">
        本邮件由加班记录分析系统自动生成。<br>
        如需查看最新详情，请登录系统查看「调休余额」报表。
    </div>
</div>
</body>
</html>
```

- [ ] **Step 4: Implement notification service**

Create `src/services/notification_service.py`:

```python
"""
通知服务
调休到期提醒的扫描、渲染、发送与历史记录
"""

import os
import sqlite3
from datetime import date
from typing import List, Dict, Any, Optional

from flask import current_app, render_template_string
from jinja2 import Environment, PackageLoader, select_autoescape

from src.services.comp_off_service import get_expiring_balances
from src.services.email_service import build_email_config, send_email


env = Environment(
    loader=PackageLoader('web', 'templates/email'),
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

    email_config = build_email_config()
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
    email_config = build_email_config()
    if not email_config['is_configured']:
        current_app.logger.warning("调休到期自动提醒跳过：SMTP 或 HR 邮箱未配置")
        return {'success': False, 'reason': 'email_not_configured'}

    return send_comp_off_expiry_notification(
        conn,
        recipient_emails=email_config['hr_emails'],
        trigger_mode='scheduled'
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_notification_service.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/services/notification_service.py src/web/templates/email/comp_off_expiry.html tests/test_notification_service.py
git commit -m "feat: add notification service for comp-off expiry reminders"
```

---

## Task 4: CLI Notify Command

**Files:**
- Modify: `src/cli/commands.py`
- Test: `tests/test_cli_commands.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_cli_commands.py`，新增测试类：

```python
class TestNotifyCommand:
    """通知命令测试"""

    def test_notify_comp_off_expiry(self, memory_db):
        from src.cli.commands import notify_comp_off_expiry

        # 先创建 notification_history 表
        cursor = memory_db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_type TEXT NOT NULL,
                trigger_mode TEXT NOT NULL,
                recipient_email TEXT NOT NULL,
                employee_id TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                error_message TEXT,
                content_summary TEXT,
                days_threshold INTEGER
            )
        """)
        memory_db.commit()

        result = notify_comp_off_expiry(memory_db, threshold=30, dry_run=True)
        assert result['success'] is True
        assert result['dry_run'] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_commands.py::TestNotifyCommand::test_notify_comp_off_expiry -v`

Expected: FAIL — `ImportError: cannot import name 'notify_comp_off_expiry'`

- [ ] **Step 3: Implement CLI command**

在 `src/cli/commands.py` 末尾追加：

```python
def notify_comp_off_expiry(
    conn: sqlite3.Connection,
    threshold: int = 30,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    发送调休到期提醒通知

    Args:
        conn: 数据库连接
        threshold: 到期天数阈值
        dry_run: 是否只预览不发送

    Returns:
        发送结果
    """
    from src.services.notification_service import send_comp_off_expiry_notification
    from src.services.email_service import build_email_config

    email_config = build_email_config()

    if not email_config['is_configured']:
        raise CLIError("SMTP 或 HR 通知邮箱未配置，请检查环境变量")

    if dry_run:
        from src.services.comp_off_service import get_expiring_balances
        balances = get_expiring_balances(conn, days_threshold=threshold)
        return {
            'success': True,
            'dry_run': True,
            'threshold': threshold,
            'recipient_count': len(email_config['hr_emails']),
            'recipients': email_config['hr_emails'],
            'balances_found': len(balances)
        }

    result = send_comp_off_expiry_notification(
        conn,
        recipient_emails=email_config['hr_emails'],
        days_threshold=threshold,
        trigger_mode='manual'
    )

    return {
        'success': result['success'],
        'sent_count': result['sent_count'],
        'failed_count': result['failed_count'],
        'balances_found': result['balances_found']
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_commands.py::TestNotifyCommand::test_notify_comp_off_expiry -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cli/commands.py tests/test_cli_commands.py
git commit -m "feat: add CLI notify comp-off-expiry command"
```

---

## Task 5: Web Routes — Notification Center

**Files:**
- Create: `src/web/routes/notifications.py`
- Test: `tests/test_web_notifications.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_notifications.py`:

```python
"""
通知中心 Web 路由测试
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestNotificationRoutes:
    """通知路由测试"""

    @pytest.fixture
    def client(self):
        from web import create_app
        app = create_app({'TESTING': True})
        return app.test_client()

    def test_notification_center_page(self, client):
        response = client.get('/notifications/')
        assert response.status_code == 200
        assert '通知中心' in response.data.decode('utf-8')

    def test_manual_send_without_config(self, client):
        response = client.post('/notifications/send/comp-off-expiry', follow_redirects=True)
        assert response.status_code == 200
        assert '未配置' in response.data.decode('utf-8')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_notifications.py -v`

Expected: FAIL — `404 NOT FOUND` for `/notifications/`

- [ ] **Step 3: Implement notification routes**

Create `src/web/routes/notifications.py`:

```python
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
    finally:
        conn.close()

    email_config = build_email_config()

    return render_template(
        'notifications/index.html',
        stats=stats,
        email_configured=email_config['is_configured'],
        hr_emails=email_config['hr_emails']
    )


@bp.route('/send/comp-off-expiry', methods=['POST'])
def send_comp_off_expiry():
    """手动发送调休到期提醒"""
    email_config = build_email_config()

    if not email_config['is_configured']:
        flash('未配置邮件收件人，请联系管理员', 'error')
        return redirect(url_for('notifications.notification_center'))

    conn = get_db()
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_notifications.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/web/routes/notifications.py tests/test_web_notifications.py
git commit -m "feat: add notification center web routes"
```

---

## Task 6: HTML Templates

**Files:**
- Create: `src/web/templates/notifications/index.html`
- Modify: `src/web/templates/reports/comp_off.html`
- Modify: `src/web/templates/base.html`

- [ ] **Step 1: Create notification center template**

Create `src/web/templates/notifications/index.html`:

```html
{% extends "base.html" %}

{% block title %}通知中心 - 加班记录管理系统{% endblock %}
{% block page_title %}通知中心{% endblock %}

{% block content %}
<nav class="breadcrumb mb-4">
    <a href="{{ url_for('dashboard.index') }}">首页</a>
    <span class="material-symbols-outlined breadcrumb-separator" style="font-size: 16px;">chevron_right</span>
    <span class="breadcrumb-current">通知中心</span>
</nav>

<div class="content-card mb-6">
    <div class="content-card-body">
        <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div>
                <h1 class="text-headline-sm font-headline font-bold text-on-surface">调休到期提醒</h1>
                <p class="text-body-md text-on-surface-variant mt-2">自动或手动发送调休余额到期邮件给 HR</p>
            </div>
        </div>
    </div>
</div>

<!-- Config Status -->
<div class="mb-6">
    {% if email_configured %}
    <div class="alert alert-success" role="alert">
        <span class="material-symbols-outlined">check_circle</span>
        <span>邮件已配置，收件人：{{ hr_emails | join('、') }}</span>
    </div>
    {% else %}
    <div class="alert alert-warning" role="alert">
        <span class="material-symbols-outlined">warning</span>
        <span>SMTP 或 HR 通知邮箱未配置，自动提醒和手动发送均不可用</span>
    </div>
    {% endif %}
</div>

<!-- Stats Cards -->
<div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
    <div class="stat-card primary">
        <div class="stat-card-header">
            <span class="stat-card-label">累计发送</span>
            <span class="material-symbols-outlined stat-card-icon">send</span>
        </div>
        <div class="stat-card-value">{{ stats.total_sent }}</div>
        <div class="stat-card-footer text-on-surface-variant">封</div>
    </div>
    <div class="stat-card">
        <div class="stat-card-header">
            <span class="stat-card-label">上次发送时间</span>
            <span class="material-symbols-outlined stat-card-icon">schedule</span>
        </div>
        <div class="stat-card-value">{{ stats.last_sent_at or '-' }}</div>
        <div class="stat-card-footer text-on-surface-variant">{{ stats.last_status or '' }}</div>
    </div>
    <div class="stat-card">
        <div class="stat-card-header">
            <span class="stat-card-label">上次摘要</span>
            <span class="material-symbols-outlined stat-card-icon">description</span>
        </div>
        <div class="stat-card-value text-body-md pt-2">{{ stats.last_summary or '-' }}</div>
    </div>
</div>

<!-- Action -->
<div class="content-card mb-8">
    <div class="content-card-header">
        <h5 class="content-card-title">
            <span class="material-symbols-outlined inline-icon">mail</span>
            手动发送
        </h5>
    </div>
    <div class="content-card-body">
        <form action="{{ url_for('notifications.send_comp_off_expiry') }}" method="POST">
            <button type="submit" class="btn btn-primary" {% if not email_configured %}disabled{% endif %}>
                <span class="material-symbols-outlined">send</span>
                立即发送调休到期提醒
            </button>
        </form>
        <p class="text-body-sm text-on-surface-variant mt-4">每天上午 9:00 系统会自动扫描并发送提醒。</p>
    </div>
</div>

<!-- History -->
<div class="content-card">
    <div class="content-card-header">
        <h5 class="content-card-title">
            <span class="material-symbols-outlined inline-icon">history</span>
            最近发送记录
        </h5>
    </div>
    <div class="content-card-body p-0">
        <div class="data-table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>发送时间</th>
                        <th>触发方式</th>
                        <th>收件人</th>
                        <th>状态</th>
                        <th>摘要</th>
                    </tr>
                </thead>
                <tbody>
                    {% for h in stats.recent_history %}
                    <tr>
                        <td>{{ h.sent_at }}</td>
                        <td>{{ '自动' if h.trigger_mode == 'scheduled' else '手动' }}</td>
                        <td>{{ h.recipient_email }}</td>
                        <td>
                            {% if h.status == 'success' %}
                            <span class="chip chip-success">成功</span>
                            {% else %}
                            <span class="chip chip-error">失败</span>
                            {% endif %}
                        </td>
                        <td>{{ h.content_summary or '-' }}</td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="5">
                            <div class="empty-state">
                                <span class="material-symbols-outlined empty-state-icon">inbox</span>
                                <h3 class="empty-state-title">暂无发送记录</h3>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Add shortcut button to comp_off report**

Edit `src/web/templates/reports/comp_off.html`,在返回列表链接旁边新增一个通知入口：

```html
            <div class="flex items-center gap-3">
                <a href="{{ url_for('notifications.notification_center') }}" class="btn btn-secondary btn-sm">
                    <span class="material-symbols-outlined text-sm">notifications</span>
                    到期提醒
                </a>
                <a href="{{ url_for('reports.reports_index') }}" class="btn btn-ghost btn-sm">
                    <span class="material-symbols-outlined text-sm">arrow_back</span>
                    返回列表
                </a>
            </div>
```

Replace the existing `<a href="{{ url_for('reports.reports_index') }}"...>` block in the Page Header section.

- [ ] **Step 3: Add sidebar nav item**

Edit `src/web/templates/base.html`,在 Sidebar nav 中节假日管理后面新增：

```html
            <a href="{{ url_for('notifications.notification_center') }}"
               class="sidebar-nav-item {% if request.endpoint and request.endpoint.startswith('notifications') %}active{% endif %}">
                <span class="material-symbols-outlined">notifications</span>
                <span>通知中心</span>
            </a>
```

Insert after the holidays nav item and before `</nav>`.

- [ ] **Step 4: Commit**

```bash
git add src/web/templates/notifications/index.html src/web/templates/reports/comp_off.html src/web/templates/base.html
git commit -m "feat: add notification center UI and sidebar nav"
```

---

## Task 7: Register Blueprint & APScheduler Integration

**Files:**
- Modify: `src/web/__init__.py`

- [ ] **Step 1: Register notifications blueprint**

Edit `src/web/__init__.py`：

1. 在 imports 区域新增：

```python
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
```

2. 在现有 `app.register_blueprint(...)` 代码块末尾新增：

```python
    from web.routes import dashboard, employees, records, review, reports, holidays, notifications
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(employees.bp)
    app.register_blueprint(records.bp)
    app.register_blueprint(review.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(holidays.bp)
    app.register_blueprint(notifications.bp)
```

(Replace the existing 6-line import and register block with this 7-line version.)

3. 在 `return app` 之前新增 APScheduler 启动逻辑：

```python
    # 启动 APScheduler 自动调度
    scheduler_enabled = os.environ.get('SCHEDULER_ENABLED', 'true').lower() == 'true'
    if scheduler_enabled and not app.config.get('TESTING'):
        try:
            from services.notification_service import run_scheduled_comp_off_notification

            def _scheduled_job():
                try:
                    db_path = app.config['DATABASE']
                    conn = sqlite3.connect(db_path)
                    conn.row_factory = sqlite3.Row
                    run_scheduled_comp_off_notification(conn)
                    conn.close()
                except Exception as e:
                    app.logger.error(f"定时调休提醒任务失败: {e}")

            scheduler = BackgroundScheduler()
            scheduler.add_job(
                id='comp_off_expiry_daily',
                func=_scheduled_job,
                trigger='cron',
                hour=9,
                minute=0
            )
            scheduler.start()
            app.logger.info("APScheduler 已启动，每日 9:00 执行调休到期提醒")
            atexit.register(lambda: scheduler.shutdown())
        except ImportError:
            app.logger.warning("APScheduler 未安装，自动调度未启用")
```

- [ ] **Step 2: Run tests to verify no regressions**

Run: `pytest tests/test_web_app.py tests/test_web_notifications.py -v`

Expected: PASS

- [ ] **Step 3: Add APScheduler to requirements**

Create or update `requirements.txt` in the project root to include:

```
APScheduler>=3.10.0
```

(If `requirements.txt` does not exist, create it with this line. If it exists, append it.)

- [ ] **Step 4: Commit**

```bash
git add src/web/__init__.py requirements.txt
git commit -m "feat: integrate APScheduler for daily comp-off expiry reminders"
```

---

## Task 8: Full Test Suite Run & Fixes

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`

Expected: All tests pass. If any fail, fix the root cause.

- [ ] **Step 2: Verify key scenarios manually (via test client)**

Run a quick script to confirm the notification center loads:

```python
from web import create_app
app = create_app({'TESTING': True})
with app.test_client() as c:
    r = c.get('/notifications/')
    print(r.status_code)
```

Expected: Prints `200`.

- [ ] **Step 3: Final commit if any fixes were made**

```bash
git add -A
git commit -m "fix: address test regressions from notification system" || echo "No changes to commit"
```

---

## Self-Review Checklist

### 1. Spec coverage
| Spec Section | Implementing Task |
|--------------|-------------------|
| `notification_history` 表 | Task 1 |
| SMTP 邮件发送封装 | Task 2 |
| 调休到期扫描 + 邮件渲染 + 历史记录 | Task 3 |
| CLI `notify` 命令 | Task 4 |
| Web 通知中心 + 手动发送 | Task 5, 6 |
| APScheduler 自动调度 | Task 7 |
| 错误处理（未配置、无数据、发送失败） | Tasks 3, 4, 5 |

### 2. Placeholder scan
- 无 TBD / TODO / "implement later" 等占位符。
- 所有代码块均包含可运行的实际代码。
- 测试用例包含具体的断言。

### 3. Type consistency
- `send_comp_off_expiry_notification()` 签名在 Task 3 和 Task 5 中一致。
- `build_email_config()` 返回的 `is_configured` 键在 Task 2、3、4、5 中一致使用。
- `notification_history` 表结构在 Task 1、3、4 测试 fixture 中一致。

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-13-comp-off-notification.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review

Which approach do you prefer?
