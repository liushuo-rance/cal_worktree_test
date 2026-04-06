"""
数据库Schema测试
测试内容:
1. 表结构验证
2. 约束验证（正数时间、外键等）
3. 索引验证
"""

import pytest
import sqlite3
from datetime import date, datetime


@pytest.fixture
def db_connection():
    """创建内存数据库连接"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def initialized_db(db_connection):
    """初始化数据库表结构"""
    from src.db.schema import init_database
    init_database(db_connection)
    return db_connection


class TestDatabaseInitialization:
    """数据库初始化测试"""

    def test_init_creates_tables(self, db_connection):
        """初始化应创建所有必要的表"""
        from src.db.schema import init_database
        init_database(db_connection)

        cursor = db_connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {
            'employees',
            'overtime_records',
            'leave_records',
            'comp_off_balances',
            'comp_off_usage_records',
            'holiday_config',
            'import_sessions',
            'import_records'
        }
        assert expected_tables.issubset(tables)


class TestOvertimeRecordsSchema:
    """加班记录表结构测试"""

    def test_overtime_records_columns(self, initialized_db):
        """加班记录表应包含正确的列"""
        cursor = initialized_db.cursor()
        cursor.execute("PRAGMA table_info(overtime_records)")
        columns = {row['name'] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'employee_id', 'date', 'overtime_type',
            'duration_hours', 'duration_minutes', 'total_minutes',
            'description', 'raw_text', 'created_at', 'updated_at'
        }
        assert expected_columns.issubset(columns)

    def test_positive_time_constraint(self, initialized_db):
        """时间值必须为正数"""
        cursor = initialized_db.cursor()

        # 尝试插入负小时数应失败
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO overtime_records
                (employee_id, date, overtime_type, duration_hours, duration_minutes, total_minutes)
                VALUES ('E001', '2025-10-24', 'weekday_evening', -1, 30, 90)
            """)

    def test_zero_duration_constraint(self, initialized_db):
        """零时长应该被拒绝"""
        cursor = initialized_db.cursor()

        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO overtime_records
                (employee_id, date, overtime_type, duration_hours, duration_minutes, total_minutes)
                VALUES ('E001', '2025-10-24', 'weekday_evening', 0, 0, 0)
            """)

    def test_overtime_type_enum_constraint(self, initialized_db):
        """加班类型必须是有效的枚举值"""
        cursor = initialized_db.cursor()

        # 有效类型应成功
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, date, overtime_type, duration_hours, duration_minutes, total_minutes)
            VALUES ('E001', '2025-10-24', 'weekday_evening', 3, 30, 210)
        """)
        initialized_db.commit()

        # 无效类型应失败
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO overtime_records
                (employee_id, date, overtime_type, duration_hours, duration_minutes, total_minutes)
                VALUES ('E001', '2025-10-25', 'invalid_type', 3, 30, 210)
            """)


class TestLeaveRecordsSchema:
    """请假记录表结构测试"""

    def test_leave_records_columns(self, initialized_db):
        """请假记录表应包含正确的列"""
        cursor = initialized_db.cursor()
        cursor.execute("PRAGMA table_info(leave_records)")
        columns = {row['name'] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'employee_id', 'date_start', 'date_end', 'leave_type',
            'duration_hours', 'duration_minutes', 'total_minutes',
            'description', 'raw_text', 'created_at', 'updated_at'
        }
        assert expected_columns.issubset(columns)

    def test_leave_type_values(self, initialized_db):
        """请假类型支持的有效值"""
        cursor = initialized_db.cursor()

        valid_types = ['personal', 'sick', 'annual', 'other']
        for leave_type in valid_types:
            cursor.execute("""
                INSERT INTO leave_records
                (employee_id, date_start, date_end, leave_type, duration_hours, duration_minutes, total_minutes)
                VALUES (?, '2025-10-24', '2025-10-24', ?, 8, 0, 480)
            """, (f'E_{leave_type}', leave_type))

        initialized_db.commit()

        cursor.execute("SELECT COUNT(*) FROM leave_records")
        assert cursor.fetchone()[0] == len(valid_types)


class TestCompOffBalanceSchema:
    """调休余额表结构测试"""

    def test_comp_off_balance_columns(self, initialized_db):
        """调休余额表应包含正确的列"""
        cursor = initialized_db.cursor()
        cursor.execute("PRAGMA table_info(comp_off_balances)")
        columns = {row['name'] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'employee_id', 'acquired_date', 'expiry_date',
            'total_hours', 'total_minutes', 'used_hours', 'used_minutes',
            'status', 'created_at', 'updated_at'
        }
        assert expected_columns.issubset(columns)

    def test_comp_off_balance_storage_positive(self, initialized_db):
        """调休余额存储为正数"""
        cursor = initialized_db.cursor()

        # 插入周末加班产生的调休余额
        cursor.execute("""
            INSERT INTO comp_off_balances
            (employee_id, acquired_date, expiry_date, total_hours, total_minutes, used_hours, used_minutes, status)
            VALUES ('E001', '2025-10-25', '2026-04-25', 15, 0, 0, 0, 'active')
        """)
        initialized_db.commit()

        cursor.execute("SELECT total_hours, total_minutes, used_hours, used_minutes FROM comp_off_balances WHERE employee_id = 'E001'")
        row = cursor.fetchone()
        assert row['total_hours'] == 15
        assert row['total_minutes'] == 0
        assert row['used_hours'] == 0
        assert row['used_minutes'] == 0


class TestCompOffUsageSchema:
    """调休使用记录表结构测试"""

    def test_comp_off_usage_columns(self, initialized_db):
        """调休使用记录表应包含正确的列"""
        cursor = initialized_db.cursor()
        cursor.execute("PRAGMA table_info(comp_off_usage_records)")
        columns = {row['name'] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'employee_id', 'usage_date', 'leave_record_id',
            'duration_hours', 'duration_minutes', 'total_minutes',
            'description', 'created_at'
        }
        assert expected_columns.issubset(columns)


class TestHolidayConfigSchema:
    """节假日配置表结构测试"""

    def test_holiday_config_columns(self, initialized_db):
        """节假日配置表应包含正确的列"""
        cursor = initialized_db.cursor()
        cursor.execute("PRAGMA table_info(holiday_config)")
        columns = {row['name'] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'holiday_date', 'holiday_name', 'holiday_type',
            'year', 'created_at'
        }
        assert expected_columns.issubset(columns)

    def test_holiday_type_enum(self, initialized_db):
        """节假日类型必须是有效的枚举值"""
        cursor = initialized_db.cursor()

        # 法定节假日
        cursor.execute("""
            INSERT INTO holiday_config (holiday_date, holiday_name, holiday_type, year)
            VALUES ('2026-01-01', '元旦', 'statutory', 2026)
        """)

        # 调休形成的假期
        cursor.execute("""
            INSERT INTO holiday_config (holiday_date, holiday_name, holiday_type, year)
            VALUES ('2026-01-02', '元旦调休', 'adjusted_holiday', 2026)
        """)

        # 调休上班日
        cursor.execute("""
            INSERT INTO holiday_config (holiday_date, holiday_name, holiday_type, year)
            VALUES ('2026-01-04', '元旦调休上班', 'adjusted_workday', 2026)
        """)

        initialized_db.commit()

        cursor.execute("SELECT COUNT(*) FROM holiday_config")
        assert cursor.fetchone()[0] == 3


class TestEmployeeSchema:
    """员工表结构测试"""

    def test_employee_columns(self, initialized_db):
        """员工表应包含正确的列"""
        cursor = initialized_db.cursor()
        cursor.execute("PRAGMA table_info(employees)")
        columns = {row['name'] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'employee_id', 'name', 'department',
            'created_at', 'updated_at'
        }
        assert expected_columns.issubset(columns)

    def test_employee_id_unique(self, initialized_db):
        """员工ID必须唯一"""
        cursor = initialized_db.cursor()

        cursor.execute("""
            INSERT INTO employees (employee_id, name, department)
            VALUES ('E001', '张三', '研发部')
        """)
        initialized_db.commit()

        # 重复ID应失败
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO employees (employee_id, name, department)
                VALUES ('E001', '李四', '市场部')
            """)


class TestImportSessionSchema:
    """导入会话表结构测试"""

    def test_import_session_columns(self, initialized_db):
        """导入会话表应包含正确的列"""
        cursor = initialized_db.cursor()
        cursor.execute("PRAGMA table_info(import_sessions)")
        columns = {row['name'] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'file_path', 'status', 'total_records',
            'processed_records', 'error_records', 'created_at', 'completed_at'
        }
        assert expected_columns.issubset(columns)
