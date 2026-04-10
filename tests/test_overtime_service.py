"""
加班统计服务测试
测试内容:
1. 加班记录CRUD
2. 按类型统计（工作日延时/周末/法定假日）
3. 月度/年度汇总
4. 员工排名
"""

import pytest
from datetime import date
import sqlite3


@pytest.fixture
def memory_db():
    """内存数据库，带完整Schema"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # 创建完整Schema
    conn.executescript("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            employee_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            daily_salary REAL DEFAULT 300.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        );

        CREATE TABLE holiday_config (
            id INTEGER PRIMARY KEY,
            holiday_date DATE UNIQUE,
            holiday_name TEXT,
            holiday_type TEXT,
            year INTEGER
        );

        INSERT INTO employees (employee_id, name, daily_salary) VALUES
            ('EMP001', '张三', 300.0),
            ('EMP002', '李四', 350.0),
            ('EMP003', '王五', 280.0);

        -- 2026年节假日
        INSERT INTO holiday_config VALUES
            (NULL, '2026-01-01', '元旦', 'statutory', 2026),
            (NULL, '2026-01-02', '元旦调休', 'adjusted_holiday', 2026),
            (NULL, '2026-02-17', '春节', 'statutory', 2026),
            (NULL, '2026-02-18', '春节', 'statutory', 2026),
            (NULL, '2026-02-19', '春节', 'statutory', 2026),
            (NULL, '2026-05-01', '劳动节', 'statutory', 2026);
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_overtime_records(memory_db):
    """插入样本加班记录"""
    records = [
        # EMP001 的记录
        ('EMP001', '2026-01-05', 2, 30, 150, 'weekday_evening', '晚上加班'),  # 周一晚上
        ('EMP001', '2026-01-10', 4, 0, 240, 'weekend', '周六加班'),  # 周六
        ('EMP001', '2026-01-01', 3, 0, 180, 'holiday', '元旦加班'),  # 法定假日
        ('EMP001', '2026-01-12', 1, 0, 60, 'weekday_morning', '早到'),  # 周一早晨

        # EMP002 的记录
        ('EMP002', '2026-01-06', 3, 0, 180, 'weekday_evening', '周二晚上'),
        ('EMP002', '2026-01-11', 5, 0, 300, 'weekend', '周日加班'),

        # EMP003 的记录
        ('EMP003', '2026-01-07', 2, 0, 120, 'weekday_evening', '周三晚上'),
    ]

    cursor = memory_db.cursor()
    for r in records:
        cursor.execute("""
            INSERT INTO overtime_records
            (employee_id, work_date, duration_hours, duration_minutes, total_minutes, overtime_type, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, r)
    memory_db.commit()
    return memory_db


class TestOvertimeRecordCRUD:
    """加班记录CRUD测试"""

    def test_create_overtime_record(self, memory_db):
        from src.services.overtime_service import create_overtime_record

        record_id = create_overtime_record(
            memory_db,
            employee_id='EMP001',
            work_date=date(2026, 1, 15),
            hours=2,
            minutes=30,
            overtime_type='weekday_evening',
            description='项目上线'
        )

        assert record_id is not None

        # 验证数据库
        cursor = memory_db.cursor()
        cursor.execute(
            "SELECT * FROM overtime_records WHERE id = ?",
            (record_id,)
        )
        row = cursor.fetchone()
        assert row['employee_id'] == 'EMP001'
        assert row['total_minutes'] == 150
        assert row['overtime_type'] == 'weekday_evening'

    def test_create_record_invalid_employee(self, memory_db):
        from src.services.overtime_service import create_overtime_record, OvertimeServiceError

        with pytest.raises(OvertimeServiceError):
            create_overtime_record(
                memory_db,
                employee_id='INVALID',
                work_date=date(2026, 1, 15),
                hours=2,
                minutes=0
            )

    def test_get_employee_overtime(self, sample_overtime_records):
        from src.services.overtime_service import get_employee_overtime

        records = get_employee_overtime(sample_overtime_records, 'EMP001')

        assert len(records) == 4
        assert all(r['employee_id'] == 'EMP001' for r in records)

    def test_delete_overtime_record(self, sample_overtime_records):
        from src.services.overtime_service import delete_overtime_record

        # 获取第一条记录ID
        cursor = sample_overtime_records.cursor()
        cursor.execute("SELECT id FROM overtime_records WHERE employee_id = 'EMP001' LIMIT 1")
        record_id = cursor.fetchone()['id']

        delete_overtime_record(sample_overtime_records, record_id)

        # 验证已删除
        cursor.execute("SELECT * FROM overtime_records WHERE id = ?", (record_id,))
        assert cursor.fetchone() is None


class TestOvertimeStatistics:
    """加班统计测试"""

    def test_get_monthly_summary(self, sample_overtime_records):
        from src.services.overtime_service import get_monthly_summary

        summary = get_monthly_summary(sample_overtime_records, 2026, 1)

        assert summary['year'] == 2026
        assert summary['month'] == 1
        assert summary['total_records'] == 7
        assert summary['total_hours'] > 0

    def test_get_employee_monthly_summary(self, sample_overtime_records):
        from src.services.overtime_service import get_employee_monthly_summary

        summary = get_employee_monthly_summary(
            sample_overtime_records, 'EMP001', 2026, 1
        )

        assert summary['employee_id'] == 'EMP001'
        assert summary['total_records'] == 4
        # 总分钟数：150 + 240 + 180 + 60 = 630
        assert summary['total_minutes'] == 630
        assert summary['total_hours'] == 10.5

    def test_get_summary_by_type(self, sample_overtime_records):
        from src.services.overtime_service import get_summary_by_type

        type_summary = get_summary_by_type(sample_overtime_records, 'EMP001', 2026, 1)

        # EMP001 的记录类型分布
        assert type_summary['weekday_evening']['count'] == 1
        assert type_summary['weekday_evening']['minutes'] == 150
        assert type_summary['weekend']['count'] == 1
        assert type_summary['weekend']['minutes'] == 240
        assert type_summary['holiday']['count'] == 1
        assert type_summary['holiday']['minutes'] == 180
        assert type_summary['weekday_morning']['count'] == 1


class TestOvertimeRanking:
    """加班排名测试"""

    def test_get_overtime_ranking(self, sample_overtime_records):
        from src.services.overtime_service import get_overtime_ranking

        ranking = get_overtime_ranking(sample_overtime_records, 2026, 1)

        # EMP001: 630分钟, EMP002: 480分钟, EMP003: 120分钟
        assert len(ranking) == 3
        assert ranking[0]['employee_id'] == 'EMP001'
        assert ranking[0]['total_minutes'] == 630
        assert ranking[1]['employee_id'] == 'EMP002'
        assert ranking[2]['employee_id'] == 'EMP003'

    def test_get_overtime_ranking_limit(self, sample_overtime_records):
        from src.services.overtime_service import get_overtime_ranking

        ranking = get_overtime_ranking(sample_overtime_records, 2026, 1, limit=2)

        assert len(ranking) == 2
        assert ranking[0]['employee_id'] == 'EMP001'


class TestOvertimeTypeClassification:
    """加班类型分类测试"""

    def test_classify_overtime_type_weekday_evening(self, memory_db):
        from src.services.overtime_service import classify_overtime_type

        # 周一晚上加班
        result = classify_overtime_type(memory_db, date(2026, 1, 5), 19, 0)
        assert result == 'weekday_evening'

    def test_classify_overtime_type_weekend(self, memory_db):
        from src.services.overtime_service import classify_overtime_type

        # 周六
        result = classify_overtime_type(memory_db, date(2026, 1, 10), 14, 0)
        assert result == 'weekend'

    def test_classify_overtime_type_holiday(self, memory_db):
        from src.services.overtime_service import classify_overtime_type

        # 元旦法定假日
        result = classify_overtime_type(memory_db, date(2026, 1, 1), 10, 0)
        assert result == 'holiday'

    def test_classify_overtime_type_weekday_morning(self, memory_db):
        from src.services.overtime_service import classify_overtime_type

        # 周一早上7点
        result = classify_overtime_type(memory_db, date(2026, 1, 5), 7, 0)
        assert result == 'weekday_morning'


class TestOvertimeValidation:
    """加班记录验证测试"""

    def test_validate_overtime_duration_positive(self):
        from src.services.overtime_service import validate_overtime_duration

        # 正常时长
        assert validate_overtime_duration(2, 30) is True
        assert validate_overtime_duration(0, 30) is True  # 只有30分钟

    def test_validate_overtime_duration_zero(self):
        from src.services.overtime_service import validate_overtime_duration, OvertimeServiceError

        with pytest.raises(OvertimeServiceError):
            validate_overtime_duration(0, 0)

    def test_validate_overtime_duration_negative(self):
        from src.services.overtime_service import validate_overtime_duration, OvertimeServiceError

        with pytest.raises(OvertimeServiceError):
            validate_overtime_duration(-1, 0)

