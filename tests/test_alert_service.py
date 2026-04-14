"""
加班合规预警服务测试
"""

import pytest
import sqlite3
from datetime import date


@pytest.fixture
def memory_db():
    """内存数据库，包含员工和加班记录"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            employee_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL
        );
        CREATE TABLE overtime_records (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            work_date DATE NOT NULL,
            overtime_type TEXT,
            duration_hours INTEGER NOT NULL,
            duration_minutes INTEGER NOT NULL,
            total_minutes INTEGER NOT NULL
        );
        CREATE TABLE notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('compliance_warning', 'compliance_violation', 'system')),
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO employees (employee_id, name) VALUES
            ('EMP001', '张三'),
            ('EMP002', '李四'),
            ('EMP003', '王五');
    """)
    conn.commit()
    yield conn
    conn.close()


class TestScanMonthlyCompliance:
    """scan_monthly_compliance 测试"""

    def test_no_records_returns_empty(self, memory_db):
        from src.services.alert_service import scan_monthly_compliance

        result = scan_monthly_compliance(memory_db, 2026, 4)
        assert result == []

    def test_warning_generated_at_30_hours(self, memory_db):
        from src.services.alert_service import scan_monthly_compliance

        # 30 小时 = 1800 分钟
        memory_db.execute("""
            INSERT INTO overtime_records (employee_id, work_date, overtime_type, duration_hours, duration_minutes, total_minutes)
            VALUES ('EMP001', '2026-04-01', 'weekday_evening', 30, 0, 1800)
        """)
        memory_db.commit()

        result = scan_monthly_compliance(memory_db, 2026, 4)
        assert len(result) == 1
        assert result[0]['type'] == 'compliance_warning'
        assert 'EMP001' in result[0]['title']
        assert '30.0' in result[0]['title']

    def test_violation_generated_at_36_hours(self, memory_db):
        from src.services.alert_service import scan_monthly_compliance

        # 36 小时 = 2160 分钟
        memory_db.execute("""
            INSERT INTO overtime_records (employee_id, work_date, overtime_type, duration_hours, duration_minutes, total_minutes)
            VALUES ('EMP001', '2026-04-01', 'weekday_evening', 36, 0, 2160)
        """)
        memory_db.commit()

        result = scan_monthly_compliance(memory_db, 2026, 4)
        assert len(result) == 1
        assert result[0]['type'] == 'compliance_violation'
        assert 'EMP001' in result[0]['title']
        assert '36.0' in result[0]['title']

    def test_warning_generated_between_30_and_36(self, memory_db):
        from src.services.alert_service import scan_monthly_compliance

        # 32.5 小时 = 1950 分钟
        memory_db.execute("""
            INSERT INTO overtime_records (employee_id, work_date, overtime_type, duration_hours, duration_minutes, total_minutes)
            VALUES ('EMP001', '2026-04-10', 'weekday_evening', 32, 30, 1950)
        """)
        memory_db.commit()

        result = scan_monthly_compliance(memory_db, 2026, 4)
        assert len(result) == 1
        assert result[0]['type'] == 'compliance_warning'
        assert result[0]['total_hours'] == 32.5

    def test_multiple_employees(self, memory_db):
        from src.services.alert_service import scan_monthly_compliance

        memory_db.executemany("""
            INSERT INTO overtime_records (employee_id, work_date, overtime_type, duration_hours, duration_minutes, total_minutes)
            VALUES (?, '2026-04-05', 'weekday_evening', 40, 0, 2400)
        """, [('EMP001',), ('EMP002',)])
        memory_db.commit()

        result = scan_monthly_compliance(memory_db, 2026, 4)
        assert len(result) == 2
        types = {r['type'] for r in result}
        assert types == {'compliance_violation'}

    def test_duplicate_prevention(self, memory_db):
        from src.services.alert_service import scan_monthly_compliance

        memory_db.execute("""
            INSERT INTO overtime_records (employee_id, work_date, overtime_type, duration_hours, duration_minutes, total_minutes)
            VALUES ('EMP001', '2026-04-01', 'weekday_evening', 36, 0, 2160)
        """)
        memory_db.commit()

        result1 = scan_monthly_compliance(memory_db, 2026, 4)
        assert len(result1) == 1

        result2 = scan_monthly_compliance(memory_db, 2026, 4)
        assert len(result2) == 0

    def test_below_threshold_no_notification(self, memory_db):
        from src.services.alert_service import scan_monthly_compliance

        memory_db.execute("""
            INSERT INTO overtime_records (employee_id, work_date, overtime_type, duration_hours, duration_minutes, total_minutes)
            VALUES ('EMP001', '2026-04-01', 'weekday_evening', 20, 0, 1200)
        """)
        memory_db.commit()

        result = scan_monthly_compliance(memory_db, 2026, 4)
        assert result == []

    def test_content_includes_exact_hours(self, memory_db):
        from src.services.alert_service import scan_monthly_compliance

        memory_db.execute("""
            INSERT INTO overtime_records (employee_id, work_date, overtime_type, duration_hours, duration_minutes, total_minutes)
            VALUES ('EMP001', '2026-04-01', 'weekday_evening', 33, 0, 1980)
        """)
        memory_db.commit()

        result = scan_monthly_compliance(memory_db, 2026, 4)
        assert '33.0 小时' in result[0]['content']
        assert '36 小时' in result[0]['content']


class TestGetComplianceRiskCount:
    """get_compliance_risk_count 测试"""

    def test_zero_when_no_records(self, memory_db):
        from src.services.alert_service import get_compliance_risk_count

        count = get_compliance_risk_count(memory_db)
        assert count == 0

    def test_counts_employees_at_or_above_30h(self, memory_db):
        from src.services.alert_service import get_compliance_risk_count

        today = date.today()
        month_str = f"{today.year}-{today.month:02d}"

        memory_db.executemany("""
            INSERT INTO overtime_records (employee_id, work_date, overtime_type, duration_hours, duration_minutes, total_minutes)
            VALUES (?, ?, 'weekday_evening', 31, 0, 1860)
        """, [
            ('EMP001', f"{month_str}-01"),
            ('EMP002', f"{month_str}-02"),
        ])
        memory_db.commit()

        count = get_compliance_risk_count(memory_db)
        assert count == 2

    def test_does_not_count_below_threshold(self, memory_db):
        from src.services.alert_service import get_compliance_risk_count

        today = date.today()
        month_str = f"{today.year}-{today.month:02d}"

        memory_db.execute("""
            INSERT INTO overtime_records (employee_id, work_date, overtime_type, duration_hours, duration_minutes, total_minutes)
            VALUES ('EMP001', ?, 'weekday_evening', 20, 0, 1200)
        """, (f"{month_str}-01",))
        memory_db.commit()

        count = get_compliance_risk_count(memory_db)
        assert count == 0

    def test_counts_distinct_employees_only(self, memory_db):
        from src.services.alert_service import get_compliance_risk_count

        today = date.today()
        month_str = f"{today.year}-{today.month:02d}"

        memory_db.executemany("""
            INSERT INTO overtime_records (employee_id, work_date, overtime_type, duration_hours, duration_minutes, total_minutes)
            VALUES ('EMP001', ?, 'weekday_evening', 35, 0, 2100)
        """, [
            (f"{month_str}-01",),
            (f"{month_str}-02",),
        ])
        memory_db.commit()

        count = get_compliance_risk_count(memory_db)
        assert count == 1
