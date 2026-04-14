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
