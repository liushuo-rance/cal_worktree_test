"""
API 路由测试
测试 REST API 的 JSON 批量导入接口
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

    db_path = str(tmp_path / "test_api.db")
    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
        'SESSION_TYPE': 'filesystem',
        'SECRET_KEY': 'test-secret',
    })

    # 预置测试员工
    with app.app_context():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("INSERT INTO employees (employee_id, name, department) VALUES (?, ?, ?)",
                     ('EMP001', '张三', '技术部'))
        conn.execute("INSERT INTO employees (employee_id, name, department) VALUES (?, ?, ?)",
                     ('EMP002', '李四', '产品部'))
        conn.commit()
        conn.close()

    return app.test_client()


class TestApiImportRecords:
    """测试 /api/v1/records/import/ 接口"""

    def test_success_import_overtime_and_leave(self, client):
        payload = {
            "employee_id": "EMP001",
            "records": [
                {"date": "2026-04-01", "hours": 3.5, "type": "overtime", "description": "晚上加班"},
                {"date": "2026-04-02", "hours": 8.0, "type": "leave", "description": "事假"},
            ]
        }
        response = client.post(
            '/api/v1/records/import/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['imported_count'] == 2
        assert data['errors'] == []

    def test_missing_employee_id_returns_400(self, client):
        payload = {
            "records": [
                {"date": "2026-04-01", "hours": 3.5, "type": "overtime"}
            ]
        }
        response = client.post(
            '/api/v1/records/import/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert "employee_id" in data['errors'][0]

    def test_records_must_be_list(self, client):
        payload = {
            "employee_id": "EMP001",
            "records": "not_a_list"
        }
        response = client.post(
            '/api/v1/records/import/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert "数组" in data['errors'][0]

    def test_empty_records_returns_400(self, client):
        payload = {
            "employee_id": "EMP001",
            "records": []
        }
        response = client.post(
            '/api/v1/records/import/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert "为空" in data['errors'][0]

    def test_invalid_date_skipped_with_error(self, client):
        payload = {
            "employee_id": "EMP001",
            "records": [
                {"date": "bad-date", "hours": 3.5, "type": "overtime"},
                {"date": "2026-04-03", "hours": 2.0, "type": "overtime"},
            ]
        }
        response = client.post(
            '/api/v1/records/import/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['imported_count'] == 1
        assert len(data['errors']) == 1
        assert "日期解析失败" in data['errors'][0]

    def test_nonexistent_employee_returns_500(self, client):
        payload = {
            "employee_id": "NOBODY",
            "records": [
                {"date": "2026-04-01", "hours": 3.5, "type": "overtime"}
            ]
        }
        response = client.post(
            '/api/v1/records/import/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False
        assert data['imported_count'] == 0
        assert "不存在" in data['errors'][0]

    def test_comp_off_record_imported(self, client):
        payload = {
            "employee_id": "EMP001",
            "records": [
                {"date": "2026-04-05", "hours": 4.0, "type": "comp_off", "description": "调休半天"}
            ]
        }
        response = client.post(
            '/api/v1/records/import/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['imported_count'] == 1

    def test_chinese_headers_supported(self, client):
        payload = {
            "employee_id": "EMP002",
            "records": [
                {"日期": "2026-04-10", "时长": 2.5, "类型": "overtime", "描述": "项目加班"}
            ]
        }
        response = client.post(
            '/api/v1/records/import/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['imported_count'] == 1
        assert data['errors'] == []

    def test_all_invalid_records_returns_400(self, client):
        payload = {
            "employee_id": "EMP001",
            "records": [
                {"date": "invalid1", "hours": 3.5, "type": "overtime"},
                {"date": "invalid2", "hours": 2.0, "type": "overtime"},
            ]
        }
        response = client.post(
            '/api/v1/records/import/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['imported_count'] == 0
        assert len(data['errors']) == 2

    def test_get_not_allowed(self, client):
        response = client.get('/api/v1/records/import/')
        assert response.status_code == 405
