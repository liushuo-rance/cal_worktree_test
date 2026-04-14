"""
存储服务测试
测试内容:
1. 记录分发到对应表
2. 周末加班自动生成调休余额
3. 数据库事务管理
4. 批量存储
"""

import pytest
from datetime import date
import sqlite3


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
            source_import_id INTEGER,
            employment_status TEXT DEFAULT 'active'
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
            source_import_id INTEGER
        );

        CREATE TABLE comp_off_balances (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            source_overtime_id INTEGER,
            acquired_date DATE NOT NULL,
            total_minutes INTEGER NOT NULL,
            remaining_minutes INTEGER NOT NULL,
            expiry_date DATE,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE import_sessions (
            id INTEGER PRIMARY KEY,
            file_path TEXT NOT NULL,
            employee_id TEXT,
            status TEXT DEFAULT 'pending',
            total_records INTEGER DEFAULT 0,
            processed_records INTEGER DEFAULT 0,
            error_records INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );

        INSERT INTO employees (employee_id, name) VALUES
            ('EMP001', '张三'),
            ('EMP002', '李四');
    """)
    conn.commit()
    yield conn
    conn.close()


class TestRecordDistribution:
    """记录分发测试"""

    def test_store_overtime_record(self, memory_db):
        from src.services.storage_service import store_overtime_record

        record_id = store_overtime_record(
            memory_db,
            employee_id='EMP001',
            work_date=date(2026, 1, 15),
            hours=3,
            minutes=30,
            overtime_type='weekday_evening',
            description='项目上线',
            import_id=1
        )

        assert record_id is not None

        # 验证存储
        cursor = memory_db.cursor()
        cursor.execute("SELECT * FROM overtime_records WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        assert row['employee_id'] == 'EMP001'
        assert row['total_minutes'] == 210
        assert row['overtime_type'] == 'weekday_evening'

    def test_store_leave_record(self, memory_db):
        from src.services.storage_service import store_leave_record

        record_id = store_leave_record(
            memory_db,
            employee_id='EMP001',
            leave_date=date(2026, 1, 16),
            hours=4,
            minutes=0,
            leave_type='personal',
            import_id=1
        )

        assert record_id is not None

        cursor = memory_db.cursor()
        cursor.execute("SELECT * FROM leave_records WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        assert row['employee_id'] == 'EMP001'
        assert row['total_minutes'] == 240
        assert row['leave_type'] == 'personal'

    def test_store_invalid_employee(self, memory_db):
        from src.services.storage_service import store_overtime_record, StorageError

        with pytest.raises(StorageError):
            store_overtime_record(
                memory_db,
                employee_id='INVALID',
                work_date=date(2026, 1, 15),
                hours=3,
                minutes=0
            )


class TestCompOffAutoGeneration:
    """调休自动生成测试"""

    def test_weekend_overtime_creates_comp_off(self, memory_db):
        from src.services.storage_service import store_overtime_record, get_comp_off_for_overtime

        # 存储周末加班记录
        overtime_id = store_overtime_record(
            memory_db,
            employee_id='EMP001',
            work_date=date(2026, 1, 10),  # 周六
            hours=4,
            minutes=0,
            overtime_type='weekend',
            description='周六加班'
        )

        # 验证自动生成调休余额
        comp_off = get_comp_off_for_overtime(memory_db, overtime_id)
        assert comp_off is not None
        assert comp_off['total_minutes'] == 240  # 4小时
        assert comp_off['remaining_minutes'] == 240

    def test_weekday_overtime_no_comp_off(self, memory_db):
        from src.services.storage_service import store_overtime_record, get_comp_off_for_overtime

        overtime_id = store_overtime_record(
            memory_db,
            employee_id='EMP001',
            work_date=date(2026, 1, 5),  # 周一
            hours=3,
            minutes=0,
            overtime_type='weekday_evening'
        )

        comp_off = get_comp_off_for_overtime(memory_db, overtime_id)
        assert comp_off is None

    def test_holiday_overtime_no_comp_off(self, memory_db):
        from src.services.storage_service import store_overtime_record, get_comp_off_for_overtime

        overtime_id = store_overtime_record(
            memory_db,
            employee_id='EMP001',
            work_date=date(2026, 1, 1),  # 元旦
            hours=3,
            minutes=0,
            overtime_type='holiday'
        )

        comp_off = get_comp_off_for_overtime(memory_db, overtime_id)
        assert comp_off is None


class TestTransactionManagement:
    """事务管理测试"""

    def test_transaction_rollback_on_error(self, memory_db):
        from src.services.storage_service import store_batch_records, StorageError

        records = [
            {'type': 'overtime', 'employee_id': 'EMP001', 'date': date(2026, 1, 15), 'hours': 3.0},
            {'type': 'overtime', 'employee_id': 'INVALID', 'date': date(2026, 1, 16), 'hours': 2.0},  # 无效员工
        ]

        with pytest.raises(StorageError):
            store_batch_records(memory_db, records)

        # 验证第一条也没有存储（事务回滚）
        cursor = memory_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM overtime_records")
        assert cursor.fetchone()[0] == 0

    def test_transaction_commit_success(self, memory_db):
        from src.services.storage_service import store_batch_records

        records = [
            {'type': 'overtime', 'employee_id': 'EMP001', 'date': date(2026, 1, 15), 'hours': 3.0,
             'overtime_type': 'weekday_evening'},
            {'type': 'overtime', 'employee_id': 'EMP002', 'date': date(2026, 1, 16), 'hours': 2.0,
             'overtime_type': 'weekday_evening'},
        ]

        result = store_batch_records(memory_db, records)

        assert result['success_count'] == 2
        assert result['failed_count'] == 0

        cursor = memory_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM overtime_records")
        assert cursor.fetchone()[0] == 2


class TestBatchStorage:
    """批量存储测试"""

    def test_store_mixed_records(self, memory_db):
        from src.services.storage_service import store_batch_records

        records = [
            {'type': 'overtime', 'employee_id': 'EMP001', 'date': date(2026, 1, 15), 'hours': 3.0,
             'overtime_type': 'weekday_evening'},
            {'type': 'leave', 'employee_id': 'EMP001', 'date': date(2026, 1, 16), 'hours': 4.0,
             'leave_type': 'personal'},
            {'type': 'overtime', 'employee_id': 'EMP002', 'date': date(2026, 1, 10), 'hours': 5.0,
             'overtime_type': 'weekend'},  # 会生成调休
        ]

        result = store_batch_records(memory_db, records)

        assert result['success_count'] == 3

        cursor = memory_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM overtime_records")
        assert cursor.fetchone()[0] == 2
        cursor.execute("SELECT COUNT(*) FROM leave_records")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT COUNT(*) FROM comp_off_balances")
        assert cursor.fetchone()[0] == 1  # 周末加班生成的调休

    def test_store_with_import_session(self, memory_db):
        from src.services.storage_service import store_batch_records_with_session

        records = [
            {'type': 'overtime', 'employee_id': 'EMP001', 'date': date(2026, 1, 15), 'hours': 3.0,
             'overtime_type': 'weekday_evening'},
        ]

        session_id = store_batch_records_with_session(
            memory_db,
            employee_id='EMP001',
            records=records,
            file_name='test.md'
        )

        assert session_id is not None

        cursor = memory_db.cursor()
        cursor.execute("SELECT * FROM import_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        assert row['total_records'] == 1
        assert row['processed_records'] == 1
        assert row['file_path'] == 'test.md'


class TestImportSession:
    """导入会话测试"""

    def test_create_import_session(self, memory_db):
        from src.services.storage_service import create_import_session

        session_id = create_import_session(
            memory_db,
            file_path='overtime_2026_01.md',
            employee_id='EMP001'
        )

        assert session_id is not None

        cursor = memory_db.cursor()
        cursor.execute("SELECT * FROM import_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        assert row['employee_id'] == 'EMP001'
        assert row['file_path'] == 'overtime_2026_01.md'

    def test_update_import_session_stats(self, memory_db):
        from src.services.storage_service import create_import_session, update_import_session_stats

        session_id = create_import_session(memory_db, file_path='test.md', employee_id='EMP001')

        update_import_session_stats(
            memory_db,
            session_id=session_id,
            total=10,
            processed=8,
            failed=2
        )

        cursor = memory_db.cursor()
        cursor.execute("SELECT * FROM import_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        assert row['total_records'] == 10
        assert row['processed_records'] == 8
        assert row['error_records'] == 2


class TestDeleteEmployee:
    """员工软删除测试"""

    def test_delete_employee_service(self, memory_db):
        from src.services.storage_service import delete_employee_service, store_overtime_record

        # 先插入一条加班记录
        store_overtime_record(
            memory_db,
            employee_id='EMP001',
            work_date=date(2026, 1, 15),
            hours=2,
            minutes=0,
            overtime_type='weekday_evening'
        )

        result = delete_employee_service(memory_db, employee_id='EMP001')

        assert result['success'] is True
        assert result['employee_id'] == 'EMP001'

        cursor = memory_db.cursor()
        cursor.execute("SELECT is_active FROM employees WHERE employee_id = ?", ('EMP001',))
        assert cursor.fetchone()['is_active'] == 0

        cursor.execute("SELECT employment_status FROM overtime_records WHERE employee_id = ?", ('EMP001',))
        for row in cursor.fetchall():
            assert row['employment_status'] == 'inactive'

    def test_delete_employee_service_not_found(self, memory_db):
        from src.services.storage_service import delete_employee_service, StorageError

        with pytest.raises(StorageError):
            delete_employee_service(memory_db, employee_id='INVALID')
