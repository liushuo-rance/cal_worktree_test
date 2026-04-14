"""
Web集成测试
测试完整的用户流程
"""

import pytest
import sys
import os
import tempfile
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def test_db():
    """创建测试数据库"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    # Initialize schema
    from db.schema import init_database, create_views
    init_database(conn)
    create_views(conn)

    # Add test employee
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO employees (employee_id, name, department) VALUES (?, ?, ?)",
        ('EMP001', 'Test User', 'IT')
    )
    conn.commit()

    yield path

    os.unlink(path)


@pytest.fixture
def client(test_db):
    """创建带数据库的测试客户端"""
    from web import create_app
    app = create_app({
        'TESTING': True,
        'DATABASE': test_db
    })
    return app.test_client()


class TestDashboardIntegration:
    """测试Dashboard集成"""

    def test_dashboard_shows_statistics(self, client):
        """测试Dashboard显示统计数据"""
        response = client.get('/')
        assert response.status_code == 200


class TestEmployeeIntegration:
    """测试员工管理集成"""

    def test_employees_list_shows_employees(self, client):
        """测试员工列表显示员工"""
        response = client.get('/employees/')
        assert response.status_code == 200

    def test_employee_detail_shows_info(self, client):
        """测试员工详情显示信息"""
        response = client.get('/employees/EMP001/')
        assert response.status_code == 200


class TestImportIntegration:
    """测试导入功能集成"""

    def test_import_page_loads(self, client):
        """测试导入页面加载"""
        response = client.get('/records/import/')
        assert response.status_code == 200


class TestReportIntegration:
    """测试报表集成"""

    def test_monthly_report_loads(self, client):
        """测试月度报表加载"""
        response = client.get('/reports/monthly/EMP001/2024/01/')
        assert response.status_code == 200

    def test_comp_off_report_loads(self, client):
        """测试调休余额报表加载"""
        response = client.get('/reports/comp-off/EMP001/')
        assert response.status_code == 200

    def test_salary_report_loads(self, client):
        """测试工资报表加载"""
        response = client.get('/reports/salary/EMP001/2024/01/')
        assert response.status_code == 200


class TestHolidayIntegration:
    """测试节假日集成"""

    def test_holidays_list_loads(self, client):
        """测试节假日列表加载"""
        response = client.get('/holidays/')
        assert response.status_code == 200


class TestAssistantIntegration:
    """测试 AI 助手集成"""

    def test_stream_returns_tool_call_record_event(self, client, monkeypatch):
        """SSE 流中应包含 tool_call_record 事件"""
        from services.assistant_service import AssistantService

        def mock_chat_stream(self, messages, db_conn):
            yield {"type": "status", "status": "thinking", "message": "AI 正在思考..."}
            yield {"type": "tool_call_record", "api_name": "query_records", "arguments": {"employee_id": "EMP001"}}
            yield {"type": "status", "status": "calling_api", "api_name": "query_records", "message": "正在调用 query_records..."}
            yield {"type": "tool_result", "api_name": "query_records", "result": {"success": True, "data": []}}
            yield {
                "type": "done",
                "full_text": "查询完成",
                "messages": messages + [
                    {"role": "tool_call", "content": "调用了 query_records", "api_name": "query_records", "arguments": {"employee_id": "EMP001"}},
                    {"role": "assistant", "content": "查询完成"}
                ]
            }

        monkeypatch.setattr(AssistantService, 'chat_stream', mock_chat_stream)

        with client:
            response = client.post('/assistant/stream', json={"message": "查询 EMP001 的记录"})
            assert response.status_code == 200
            assert 'text/event-stream' in response.content_type

            data = response.data.decode('utf-8')
            assert '"type": "tool_call_record"' in data
            assert '"api_name": "query_records"' in data

        # 验证 session 已保存
        with client.session_transaction() as sess:
            msgs = sess.get('assistant_chat', [])
            tool_calls = [m for m in msgs if m.get('role') == 'tool_call']
            assert len(tool_calls) == 1
            assert tool_calls[0]['api_name'] == 'query_records'

    def test_assistant_page_renders_tool_call_history(self, client):
        """助手页面应渲染历史对话中的 tool_call 记录"""
        with client.session_transaction() as sess:
            sess['assistant_chat'] = [
                {"role": "user", "content": "查一下记录"},
                {"role": "tool_call", "content": "调用了 query_records", "api_name": "query_records", "arguments": {"employee_id": "EMP001"}},
                {"role": "assistant", "content": "找到了 0 条记录"},
            ]

        response = client.get('/assistant/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'build_circle' in html
        assert '"employee_id": "EMP001"' in html
