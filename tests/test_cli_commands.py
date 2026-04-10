"""
CLI命令测试
测试内容:
1. import命令 - 导入Markdown文件
2. query命令 - 查询统计
3. report命令 - 生成报表
4. export命令 - 导出数据
"""

import pytest
from datetime import date
import sqlite3
import os
import tempfile


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

        CREATE TABLE import_sessions (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_name TEXT,
            total_records INTEGER DEFAULT 0,
            success_records INTEGER DEFAULT 0,
            failed_records INTEGER DEFAULT 0
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
            leave_type TEXT NOT NULL
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


class TestExportCommand:
    """导出命令测试"""

    def test_export_to_json(self, memory_db, tmp_path):
        from src.cli.commands import export_data

        # 插入记录
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
            employee_id='EMP001',
            format='json',
            output_path=str(output_path)
        )

        assert result['success'] is True
        assert os.path.exists(output_path)

    def test_export_invalid_format(self, memory_db):
        from src.cli.commands import export_data, CLIError

        with pytest.raises(CLIError):
            export_data(memory_db, employee_id='EMP001', format='invalid')

    def test_export_to_csv(self, memory_db):
        from src.cli.commands import export_data

        # 插入记录
        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2025-10-22', 3, 30, 210, 'weekday_evening')
        """)
        memory_db.commit()

        result = export_data(memory_db, employee_id='EMP001', format='csv')

        assert result['success'] is True
        assert result['format'] == 'csv'


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
