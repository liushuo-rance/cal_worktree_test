"""
CLI命令测试
测试内容:
1. import命令 - 导入Markdown文件
2. query命令 - 查询统计
3. report命令 - 生成报表
4. export命令 - 导出数据
"""

import csv
import os
import pytest
import sqlite3
import tempfile
from datetime import date
from unittest.mock import patch


@pytest.fixture
def memory_db():
    """内存数据库，带完整Schema"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            employee_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            daily_salary REAL DEFAULT 300.0,
            hourly_salary REAL DEFAULT 37.5,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE overtime_records (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            work_date DATE NOT NULL,
            duration_hours INTEGER NOT NULL,
            duration_minutes INTEGER NOT NULL DEFAULT 0,
            total_minutes INTEGER NOT NULL,
            overtime_type TEXT NOT NULL,
            description TEXT,
            raw_text TEXT,
            source_import_id INTEGER,
            employment_status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE import_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            employee_id TEXT,
            status TEXT DEFAULT 'pending',
            total_records INTEGER DEFAULT 0,
            processed_records INTEGER DEFAULT 0,
            error_records INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
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

        CREATE TABLE leave_records (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            leave_date DATE NOT NULL,
            duration_hours INTEGER NOT NULL,
            duration_minutes INTEGER DEFAULT 0,
            total_minutes INTEGER NOT NULL,
            leave_type TEXT NOT NULL,
            description TEXT,
            raw_text TEXT,
            source_import_id INTEGER
        );

        CREATE TABLE comp_off_usage_records (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            balance_id INTEGER,
            used_minutes INTEGER DEFAULT 0,
            usage_date DATE NOT NULL,
            leave_record_id INTEGER,
            duration_hours INTEGER NOT NULL,
            duration_minutes INTEGER DEFAULT 0,
            total_minutes INTEGER NOT NULL,
            description TEXT,
            source_import_id INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO employees (employee_id, name) VALUES
            ('EMP001', '张三'),
            ('xuchen', '徐晨');
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_md_file():
    """创建临时Markdown文件"""
    content = """# 加班记录

2025.10.22，晚上3.5小时
2025.10.23，晚上4小时
2025.10.24，请假半天
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(content)
        filepath = f.name

    yield filepath

    # 清理
    if os.path.exists(filepath):
        os.unlink(filepath)


class TestImportCommand:
    """导入命令测试"""

    def test_import_single_file(self, memory_db, sample_md_file):
        from src.cli.commands import import_file

        result = import_file(memory_db, file_path=sample_md_file, employee_id='xuchen')

        assert result['success'] is True
        assert 'import_session_id' in result

    def test_import_invalid_file(self, memory_db):
        from src.cli.commands import import_file, CLIError

        with pytest.raises(CLIError):
            import_file(memory_db, file_path='/nonexistent/file.md', employee_id='xuchen')


class TestQueryCommand:
    """查询命令测试"""

    def test_query_employee_records(self, memory_db):
        from src.cli.commands import query_records

        # 先插入一条记录
        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2025-10-22', 3, 30, 210, 'weekday_evening')
        """)
        memory_db.commit()

        result = query_records(memory_db, employee_id='EMP001')

        assert result['success'] is True
        assert len(result['records']) > 0

    def test_query_with_date_range(self, memory_db):
        from src.cli.commands import query_records

        # 插入记录
        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2025-10-22', 3, 30, 210, 'weekday_evening')
        """)
        memory_db.commit()

        result = query_records(
            memory_db,
            employee_id='EMP001',
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 31)
        )

        assert result['success'] is True
        assert len(result['records']) >= 1


class TestReportCommand:
    """报表命令测试"""

    def test_generate_monthly_report(self, memory_db):
        from src.cli.commands import generate_report

        # 插入记录
        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2025-10-22', 3, 30, 210, 'weekday_evening')
        """)
        memory_db.commit()

        result = generate_report(memory_db, employee_id='EMP001', year=2025, month=10)

        assert result['success'] is True
        assert 'report' in result
        assert result['report']['employee_id'] == 'EMP001'

    def test_generate_comp_off_report(self, memory_db):
        from src.cli.commands import generate_report

        result = generate_report(memory_db, employee_id='EMP001', report_type='comp_off')

        assert result['success'] is True
        assert 'report' in result

    def test_generate_salary_report(self, memory_db):
        from src.cli.commands import generate_report

        # 插入记录
        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2025-10-22', 3, 30, 210, 'weekday_evening')
        """)
        memory_db.commit()

        result = generate_report(memory_db, employee_id='EMP001', report_type='salary', year=2025, month=10)

        assert result['success'] is True
        assert 'report' in result
        assert result['report_type'] == 'salary'

    def test_generate_report_default_year_month(self, memory_db):
        from src.cli.commands import generate_report

        # 插入记录
        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2025-10-22', 3, 30, 210, 'weekday_evening')
        """)
        memory_db.commit()

        # 不传递 year 和 month，应使用当前日期
        result = generate_report(memory_db, employee_id='EMP001', report_type='monthly')

        assert result['success'] is True
        assert 'report' in result

    def test_generate_report_invalid_type(self, memory_db):
        from src.cli.commands import generate_report, CLIError

        with pytest.raises(CLIError):
            generate_report(memory_db, employee_id='EMP001', report_type='invalid')


class TestImportExcelCsvCommand:
    """Excel/CSV导入命令测试"""

    def test_import_csv_success(self, memory_db, tmp_path):
        from src.cli.commands import import_excel_csv

        csv_path = tmp_path / "records.csv"
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "hours", "type", "description"])
            writer.writerow(["2025-10-22", "3.5", "overtime", "项目加班"])
            writer.writerow(["2025-10-23", "8", "leave", "事假"])

        result = import_excel_csv(memory_db, str(csv_path), "EMP001", file_format="csv")

        assert result['success'] is True
        assert result['record_count'] == 2

    def test_import_csv_dry_run(self, memory_db, tmp_path):
        from src.cli.commands import import_excel_csv

        csv_path = tmp_path / "records.csv"
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "hours", "type"])
            writer.writerow(["2025-10-22", "3", "overtime"])

        result = import_excel_csv(memory_db, str(csv_path), "EMP001", dry_run=True)

        assert result['success'] is True
        assert result['dry_run'] is True
        assert result['record_count'] == 1

    def test_import_invalid_file(self, memory_db):
        from src.cli.commands import import_excel_csv, CLIError

        with pytest.raises(CLIError):
            import_excel_csv(memory_db, "/nonexistent/file.csv", "EMP001")

    def test_import_invalid_format(self, memory_db, tmp_path):
        from src.cli.commands import import_excel_csv, CLIError

        txt_path = tmp_path / "records.txt"
        txt_path.write_text("hello")

        with pytest.raises(CLIError):
            import_excel_csv(memory_db, str(txt_path), "EMP001", file_format="auto")


class TestExportCommand:
    """导出命令测试"""

    def test_export_overtime_to_json(self, memory_db, tmp_path):
        from src.cli.commands import export_data

        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2025-10-22', 3, 30, 210, 'weekday_evening')
        """)
        memory_db.commit()

        output_path = tmp_path / "export.json"
        result = export_data(
            memory_db,
            data_type='overtime',
            employee_id='EMP001',
            format='json',
            output_path=str(output_path)
        )

        assert result['success'] is True
        assert os.path.exists(output_path)

    def test_export_overtime_to_csv(self, memory_db, tmp_path):
        from src.cli.commands import export_data

        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2025-10-22', 3, 30, 210, 'weekday_evening')
        """)
        memory_db.commit()

        output_path = tmp_path / "export.csv"
        result = export_data(
            memory_db,
            data_type='overtime',
            employee_id='EMP001',
            format='csv',
            output_path=str(output_path)
        )

        assert result['success'] is True
        assert os.path.exists(output_path)
        assert result['format'] == 'csv'

    def test_export_report_monthly_to_xlsx(self, memory_db, tmp_path):
        from src.cli.commands import export_data

        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2025-10-22', 3, 30, 210, 'weekday_evening')
        """)
        memory_db.commit()

        output_path = tmp_path / "monthly.xlsx"
        result = export_data(
            memory_db,
            data_type='report_monthly',
            employee_id='EMP001',
            format='xlsx',
            output_path=str(output_path),
            year=2025,
            month=10
        )

        assert result['success'] is True
        assert os.path.exists(output_path)
        assert result['format'] == 'xlsx'

    def test_export_report_salary_to_pdf(self, memory_db, tmp_path):
        from src.cli.commands import export_data

        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2025-10-22', 3, 30, 210, 'weekday_evening')
        """)
        memory_db.commit()

        output_path = tmp_path / "salary.pdf"
        result = export_data(
            memory_db,
            data_type='report_salary',
            employee_id='EMP001',
            format='pdf',
            output_path=str(output_path),
            year=2025,
            month=10
        )

        assert result['success'] is True
        assert os.path.exists(output_path)

    def test_export_invalid_format(self, memory_db):
        from src.cli.commands import export_data, CLIError

        with pytest.raises(CLIError):
            export_data(memory_db, data_type='overtime', employee_id='EMP001', format='invalid')

    def test_export_report_missing_year_month(self, memory_db):
        from src.cli.commands import export_data, CLIError

        with pytest.raises(CLIError):
            export_data(memory_db, data_type='report_monthly', employee_id='EMP001', format='csv')


class TestCalculateSalaryCommand:
    """工资计算命令测试"""

    def test_calculate_salary(self, memory_db):
        from src.cli.commands import calculate_salary

        # 插入加班记录
        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2025-10-22', 3, 30, 210, 'weekday_evening')
        """)
        memory_db.commit()

        result = calculate_salary(memory_db, employee_id='EMP001', year=2025, month=10)

        assert result['success'] is True
        assert 'salary_report' in result
        assert result['salary_report']['employee_id'] == 'EMP001'


class TestHolidayCommand:
    """节假日管理命令测试"""

    def test_list_holidays(self, memory_db):
        from src.cli.commands import list_holidays

        result = list_holidays(memory_db, year=2026)

        assert result['success'] is True
        assert 'holidays' in result

    def test_list_holidays_with_table(self, memory_db):
        from src.cli.commands import list_holidays

        # 创建节假日表
        cursor = memory_db.cursor()
        cursor.execute("""
            CREATE TABLE holiday_config (
                id INTEGER PRIMARY KEY,
                holiday_date DATE NOT NULL,
                holiday_name TEXT NOT NULL,
                is_statutory BOOLEAN DEFAULT 0
            )
        """)
        cursor.execute("""
            INSERT INTO holiday_config (holiday_date, holiday_name, is_statutory)
            VALUES ('2026-01-01', '元旦', 1)
        """)
        memory_db.commit()

        result = list_holidays(memory_db, year=2026)

        assert result['success'] is True
        assert len(result['holidays']) == 1

    def test_check_holiday_config(self, memory_db):
        from src.cli.commands import check_holiday_config

        result = check_holiday_config(memory_db, month='2026-01')

        assert result['success'] is True
        assert 'check_result' in result

    def test_check_holiday_config_invalid_format(self, memory_db):
        from src.cli.commands import check_holiday_config, CLIError

        with pytest.raises(CLIError):
            check_holiday_config(memory_db, month='invalid')


class TestCompOffCommand:
    """调休管理命令测试"""

    def test_query_comp_off_balance(self, memory_db):
        from src.cli.commands import query_comp_off

        result = query_comp_off(memory_db, employee_id='EMP001')

        assert result['success'] is True
        assert 'balance' in result

    def test_mark_expired_comp_off(self, memory_db):
        from src.cli.commands import mark_expired_comp_off

        # 插入过期调休
        cursor = memory_db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comp_off_balances (
                id INTEGER PRIMARY KEY,
                employee_id TEXT NOT NULL,
                acquired_date DATE NOT NULL,
                total_minutes INTEGER NOT NULL,
                remaining_minutes INTEGER NOT NULL,
                expiry_date DATE,
                status TEXT DEFAULT 'active'
            )
        """)
        cursor.execute("""
            INSERT INTO comp_off_balances
            (employee_id, acquired_date, total_minutes, remaining_minutes, expiry_date, status)
            VALUES ('EMP001', '2025-01-01', 480, 480, '2025-06-01', 'active')
        """)
        memory_db.commit()

        result = mark_expired_comp_off(memory_db)

        assert result['success'] is True
        assert result['marked_count'] >= 0

    def test_mark_expired_comp_off_no_table(self, memory_db):
        from src.cli.commands import mark_expired_comp_off

        # 不创建 comp_off_balances 表
        result = mark_expired_comp_off(memory_db)

        assert result['success'] is True
        assert result['marked_count'] == 0


class TestEmployeeCommand:
    """员工命令测试"""

    def test_delete_employee(self, memory_db):
        from src.cli.commands import delete_employee

        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO employees (employee_id, name, is_active)
            VALUES ('EMP003', '李四', 1)
        """)
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type, employment_status)
            VALUES ('EMP003', '2025-10-22', 3, 30, 210, 'weekday_evening', 'active')
        """)
        memory_db.commit()

        result = delete_employee(memory_db, 'EMP003')

        assert result['success'] is True
        assert result['employee_id'] == 'EMP003'

        cursor.execute("SELECT is_active FROM employees WHERE employee_id = ?", ('EMP003',))
        row = cursor.fetchone()
        assert row['is_active'] == 0

        cursor.execute("SELECT employment_status FROM overtime_records WHERE employee_id = ?", ('EMP003',))
        row = cursor.fetchone()
        assert row['employment_status'] == 'inactive'

    def test_delete_nonexistent_employee(self, memory_db):
        from src.cli.commands import delete_employee, CLIError

        with pytest.raises(CLIError):
            delete_employee(memory_db, 'NONEXISTENT')


class TestNotifyCommand:
    """通知命令测试"""

    @patch.dict('os.environ', {
        'SMTP_HOST': 'smtp.example.com',
        'SMTP_PORT': '587',
        'SMTP_USER': 'user@example.com',
        'SMTP_PASSWORD': 'secret',
        'HR_NOTIFICATION_EMAIL': 'hr@example.com'
    }, clear=True)
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
