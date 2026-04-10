"""
报表生成服务测试
测试内容:
1. 个人月度报表生成
2. 调休余额报表
3. 工资计算表
"""

import pytest
from datetime import date
import sqlite3


@pytest.fixture
def memory_db():
    """内存数据库，带完整Schema和测试数据"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            employee_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            daily_salary REAL DEFAULT 300.0,
            hourly_salary REAL DEFAULT 37.5
        );

        CREATE TABLE overtime_records (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            work_date DATE NOT NULL,
            duration_hours INTEGER NOT NULL,
            duration_minutes INTEGER NOT NULL DEFAULT 0,
            total_minutes INTEGER NOT NULL,
            overtime_type TEXT NOT NULL,
            description TEXT
        );

        CREATE TABLE leave_records (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            leave_date DATE NOT NULL,
            duration_hours INTEGER NOT NULL,
            duration_minutes INTEGER DEFAULT 0,
            total_minutes INTEGER NOT NULL,
            leave_type TEXT NOT NULL
        );

        CREATE TABLE comp_off_balances (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            source_overtime_id INTEGER,
            acquired_date DATE NOT NULL,
            total_minutes INTEGER NOT NULL,
            remaining_minutes INTEGER NOT NULL,
            expiry_date DATE,
            status TEXT DEFAULT 'active'
        );

        -- 插入测试员工
        INSERT INTO employees (employee_id, name, hourly_salary) VALUES
            ('EMP001', '张三', 50.0),
            ('EMP002', '李四', 60.0);

        -- 插入加班记录
        INSERT INTO overtime_records
        (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type, description)
        VALUES
            ('EMP001', '2025-10-22', 1, 0, 60, 'weekday_lunch', '午餐会'),
            ('EMP001', '2025-10-23', 6, 30, 390, 'weekday_evening', '晚上加班'),
            ('EMP001', '2025-10-24', 7, 0, 420, 'weekday_evening', '早晚加班'),
            ('EMP001', '2025-10-25', 15, 0, 900, 'weekend', '全天加班'),
            ('EMP001', '2025-10-26', 15, 0, 900, 'weekend', '全天加班');

        -- 插入请假记录
        INSERT INTO leave_records
        (employee_id, leave_date, duration_hours, duration_minutes, total_minutes, leave_type)
        VALUES
            ('EMP001', '2025-10-27', 8, 0, 480, 'annual'),
            ('EMP001', '2025-10-28', 8, 0, 480, 'annual'),
            ('EMP001', '2025-10-29', 8, 0, 480, 'annual');

        -- 插入调休余额
        INSERT INTO comp_off_balances
        (employee_id, source_overtime_id, acquired_date, total_minutes, remaining_minutes, expiry_date, status)
        VALUES
            ('EMP001', 4, '2025-10-25', 900, 900, '2026-04-25', 'active'),
            ('EMP001', 5, '2025-10-26', 900, 900, '2026-04-26', 'active');
    """)
    conn.commit()
    yield conn
    conn.close()


class TestPersonalMonthlyReport:
    """个人月度报表测试"""

    def test_generate_monthly_report(self, memory_db):
        from src.services.report_service import generate_monthly_report

        report = generate_monthly_report(memory_db, employee_id='EMP001', year=2025, month=10)

        assert report['employee_id'] == 'EMP001'
        assert report['employee_name'] == '张三'
        assert report['year'] == 2025
        assert report['month'] == 10
        assert 'overtime_details' in report
        assert 'summary' in report

    def test_report_overtime_details(self, memory_db):
        from src.services.report_service import generate_monthly_report

        report = generate_monthly_report(memory_db, employee_id='EMP001', year=2025, month=10)

        overtime_details = report['overtime_details']
        assert len(overtime_details) == 5  # 5条加班记录

        # 检查第一条记录
        first = overtime_details[0]
        assert first['date'] == '2025-10-22'
        assert first['hours'] == 1.0
        assert first['type'] == 'weekday_lunch'

    def test_report_summary(self, memory_db):
        from src.services.report_service import generate_monthly_report

        report = generate_monthly_report(memory_db, employee_id='EMP001', year=2025, month=10)

        summary = report['summary']
        assert summary['weekday_hours'] == 14.5  # 1 + 6.5 + 7
        assert summary['weekend_hours'] == 30.0  # 15 + 15
        assert summary['leave_days'] == 3

    def test_report_employee_not_found(self, memory_db):
        from src.services.report_service import generate_monthly_report, ReportError

        with pytest.raises(ReportError):
            generate_monthly_report(memory_db, employee_id='INVALID', year=2025, month=10)


class TestCompOffBalanceReport:
    """调休余额报表测试"""

    def test_generate_comp_off_report(self, memory_db):
        from src.services.report_service import generate_comp_off_report

        report = generate_comp_off_report(memory_db, employee_id='EMP001')

        assert report['employee_id'] == 'EMP001'
        assert report['total_hours'] == 30.0  # 15 + 15
        assert 'balance_items' in report

    def test_comp_off_balance_items(self, memory_db):
        from src.services.report_service import generate_comp_off_report

        report = generate_comp_off_report(memory_db, employee_id='EMP001')

        items = report['balance_items']
        assert len(items) == 2

        # 检查第一条调休余额
        first = items[0]
        assert first['acquired_date'] == '2025-10-25'
        assert first['hours'] == 15.0
        assert first['expiry_date'] == '2026-04-25'
        assert first['status'] == 'active'

    def test_comp_off_with_expiry_warning(self, memory_db):
        from src.services.report_service import generate_comp_off_report
        from datetime import datetime, timedelta

        # 添加即将到期的调休
        cursor = memory_db.cursor()
        expiry_date = datetime.now() + timedelta(days=15)
        cursor.execute("""
            INSERT INTO comp_off_balances
            (employee_id, acquired_date, total_minutes, remaining_minutes, expiry_date, status)
            VALUES (?, ?, 480, 480, ?, 'active')
        """, ('EMP001', date(2026, 1, 1), expiry_date.date()))
        memory_db.commit()

        report = generate_comp_off_report(memory_db, employee_id='EMP001', warning_days=30)

        assert report['expiring_soon_hours'] > 0
        assert len(report['expiring_items']) > 0


class TestSalaryCalculationReport:
    """工资计算表测试"""

    def test_generate_salary_report(self, memory_db):
        from src.services.report_service import generate_salary_report

        report = generate_salary_report(memory_db, employee_id='EMP001', year=2025, month=10)

        assert report['employee_id'] == 'EMP001'
        assert report['hourly_rate'] == 50.0
        assert 'weekday_overtime' in report
        assert 'weekend_overtime' in report
        assert 'total_amount' in report

    def test_salary_weekday_calculation(self, memory_db):
        from src.services.report_service import generate_salary_report

        report = generate_salary_report(memory_db, employee_id='EMP001', year=2025, month=10)

        weekday = report['weekday_overtime']
        assert weekday['hours'] == 14.5
        assert weekday['multiplier'] == 1.5
        # 14.5 * 50 * 1.5 = 1087.5
        assert weekday['amount'] == 1087.5

    def test_salary_weekend_calculation(self, memory_db):
        from src.services.report_service import generate_salary_report

        report = generate_salary_report(memory_db, employee_id='EMP001', year=2025, month=10)

        weekend = report['weekend_overtime']
        assert weekend['hours'] == 30.0
        assert weekend['multiplier'] == 2.0
        # 30 * 50 * 2.0 = 3000.0
        assert weekend['amount'] == 3000.0

    def test_salary_total_amount(self, memory_db):
        from src.services.report_service import generate_salary_report

        report = generate_salary_report(memory_db, employee_id='EMP001', year=2025, month=10)

        # 工作日: 1087.5, 周末: 3000.0
        assert report['total_amount'] == 4087.5


class TestDepartmentReport:
    """部门统计报表测试"""

    def test_generate_department_summary(self, memory_db):
        from src.services.report_service import generate_department_summary

        report = generate_department_summary(memory_db, year=2025, month=10)

        assert 'employees' in report
        assert 'department_totals' in report

    def test_department_employee_list(self, memory_db):
        from src.services.report_service import generate_department_summary

        report = generate_department_summary(memory_db, year=2025, month=10)

        employees = report['employees']
        assert len(employees) >= 1

        # 检查EMP001的数据
        emp001 = next((e for e in employees if e['employee_id'] == 'EMP001'), None)
        assert emp001 is not None
        assert emp001['total_overtime_hours'] == 44.5


class TestReportExport:
    """报表导出测试"""

    def test_export_to_dict(self, memory_db):
        from src.services.report_service import generate_monthly_report, export_report_to_dict

        report = generate_monthly_report(memory_db, employee_id='EMP001', year=2025, month=10)
        export_data = export_report_to_dict(report)

        assert isinstance(export_data, dict)
        assert 'employee_id' in export_data
        assert 'summary' in export_data
