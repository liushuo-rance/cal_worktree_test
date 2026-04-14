"""
通知中心 API 路由测试
"""

import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest


@pytest.fixture
def client(tmp_path):
    """创建测试客户端，使用独立临时数据库"""
    from web import create_app

    db_path = str(tmp_path / "test_notifications.db")
    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
        'SESSION_TYPE': 'filesystem',
        'SECRET_KEY': 'test-secret',
    })

    with app.app_context():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("INSERT INTO employees (employee_id, name, department) VALUES (?, ?, ?)",
                     ('EMP001', '张三', '技术部'))
        conn.execute("INSERT INTO employees (employee_id, name, department) VALUES (?, ?, ?)",
                     ('EMP002', '李四', '产品部'))
        conn.executemany("""
            INSERT INTO notifications (employee_id, type, title, content, is_read, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now', ?))
        """, [
            ('EMP001', 'system', '系统通知1', '内容1', 0, '-10 minutes'),
            ('EMP001', 'compliance_warning', '预警', '加班预警内容', 0, '-5 minutes'),
            ('EMP001', 'system', '系统通知2', '内容2', 1, '+1 minutes'),
            ('EMP002', 'system', '系统通知3', '内容3', 0, '-1 minutes'),
        ])
        conn.commit()
        conn.close()

    return app.test_client()


class TestNotificationsApi:
    """通知 API 测试"""

    def test_unread_count(self, client):
        response = client.get('/notifications/api/unread-count')
        assert response.status_code == 200
        data = response.get_json()
        assert data['unread_count'] == 3

    def test_list_all(self, client):
        response = client.get('/notifications/api/list?filter=all')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 4
        # 按 created_at DESC 排序，最新的是系统通知2（now）
        assert data[0]['title'] == '系统通知2'

    def test_list_unread(self, client):
        response = client.get('/notifications/api/list?filter=unread')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 3
        for item in data:
            assert item['is_read'] is False

    def test_list_read(self, client):
        response = client.get('/notifications/api/list?filter=read')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['is_read'] is True

    def test_mark_read(self, client):
        response = client.post('/notifications/api/mark-read/1')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # 验证未读数减少
        response = client.get('/notifications/api/unread-count')
        assert response.get_json()['unread_count'] == 2

    def test_mark_all_read(self, client):
        response = client.post('/notifications/api/mark-all-read')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        response = client.get('/notifications/api/unread-count')
        assert response.get_json()['unread_count'] == 0

        response = client.get('/notifications/api/list?filter=unread')
        assert response.get_json() == []

    def test_delete(self, client):
        response = client.post('/notifications/api/delete/1')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        response = client.get('/notifications/api/list?filter=all')
        assert len(response.get_json()) == 3

    def test_inbox_page(self, client):
        response = client.get('/notifications/inbox')
        assert response.status_code == 200
        assert 'text/html' in response.content_type
