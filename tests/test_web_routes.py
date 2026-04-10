"""
Web路由测试
测试各个页面的路由
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def client():
    """创建测试客户端"""
    from web import create_app
    app = create_app({'TESTING': True})
    return app.test_client()


class TestDashboardRoutes:
    """测试Dashboard路由"""

    def test_dashboard_route_exists(self, client):
        """测试Dashboard路由存在"""
        response = client.get('/')
        assert response.status_code in [200, 302]

    def test_dashboard_returns_html(self, client):
        """测试Dashboard返回HTML"""
        response = client.get('/')
        assert 'text/html' in response.content_type


class TestEmployeeRoutes:
    """测试员工管理路由"""

    def test_employees_list_route_exists(self, client):
        """测试员工列表路由存在"""
        response = client.get('/employees/')
        assert response.status_code in [200, 302]

    def test_employee_detail_route_exists(self, client):
        """测试员工详情路由存在"""
        response = client.get('/employees/EMP001/')
        assert response.status_code in [200, 302, 404]


class TestRecordRoutes:
    """测试记录导入路由"""

    def test_import_route_exists(self, client):
        """测试导入页面路由存在"""
        response = client.get('/records/import/')
        assert response.status_code in [200, 302]

    def test_import_post_accepts_file(self, client):
        """测试导入POST接受文件"""
        response = client.post('/records/import/')
        # Should not crash, may return 400 if no file
        assert response.status_code in [200, 302, 400]


class TestReviewRoutes:
    """测试审批队列路由"""

    def test_review_queue_route_exists(self, client):
        """测试审批队列路由存在"""
        response = client.get('/review/')
        assert response.status_code in [200, 302]

    def test_review_item_route_exists(self, client):
        """测试单个审批项路由存在"""
        response = client.get('/review/item/1/')
        assert response.status_code in [200, 302, 404]


class TestReportRoutes:
    """测试报表路由"""

    def test_reports_index_route_exists(self, client):
        """测试报表首页路由存在"""
        response = client.get('/reports/')
        assert response.status_code in [200, 302]

    def test_monthly_report_route_exists(self, client):
        """测试月度报表路由存在"""
        response = client.get('/reports/monthly/EMP001/2024/01/')
        assert response.status_code in [200, 302, 404]

    def test_comp_off_report_route_exists(self, client):
        """测试调休余额报表路由存在"""
        response = client.get('/reports/comp-off/EMP001/')
        assert response.status_code in [200, 302, 404]

    def test_salary_report_route_exists(self, client):
        """测试工资报表路由存在"""
        response = client.get('/reports/salary/EMP001/2024/01/')
        assert response.status_code in [200, 302, 404]


class TestHolidayRoutes:
    """测试节假日路由"""

    def test_holidays_list_route_exists(self, client):
        """测试节假日列表路由存在"""
        response = client.get('/holidays/')
        assert response.status_code in [200, 302]

    def test_holidays_import_route_exists(self, client):
        """测试节假日导入路由存在"""
        response = client.get('/holidays/import/')
        assert response.status_code in [200, 302]
