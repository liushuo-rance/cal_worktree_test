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
