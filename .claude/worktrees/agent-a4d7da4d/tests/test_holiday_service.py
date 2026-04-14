"""
节假日服务测试
测试内容:
1. 日期类型判断
2. 节假日数据管理
3. 工作日/休息日判断
"""

import pytest
from datetime import date
import sqlite3


@pytest.fixture
def memory_db():
    """内存数据库"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE holiday_config (
            id INTEGER PRIMARY KEY,
            holiday_date DATE UNIQUE,
            holiday_name TEXT,
            holiday_type TEXT,
            year INTEGER
        )
    """)
    holidays = [
        ('2026-01-01', '元旦', 'statutory', 2026),
        ('2026-01-02', '元旦调休', 'adjusted_holiday', 2026),
        ('2026-01-04', '元旦调休上班', 'adjusted_workday', 2026),
        ('2026-05-01', '劳动节', 'statutory', 2026),
    ]
    conn.executemany(
        "INSERT INTO holiday_config VALUES (NULL, ?, ?, ?, ?)", holidays
    )
    conn.commit()
    yield conn
    conn.close()


class TestDateTypeCheck:
    """日期类型判断测试"""

    def test_statutory_holiday(self, memory_db):
        from src.services.holiday_service import get_date_type
        result = get_date_type(memory_db, date(2026, 1, 1))
        assert result == 'statutory_holiday'

    def test_adjusted_workday(self, memory_db):
        from src.services.holiday_service import get_date_type
        result = get_date_type(memory_db, date(2026, 1, 4))
        assert result == 'adjusted_workday'

    def test_normal_weekend(self, memory_db):
        from src.services.holiday_service import get_date_type
        result = get_date_type(memory_db, date(2026, 1, 10))  # 周六
        assert result == 'weekend'

    def test_normal_workday(self, memory_db):
        from src.services.holiday_service import get_date_type
        result = get_date_type(memory_db, date(2026, 1, 5))  # 周一
        assert result == 'workday'


class TestWorkdayCheck:
    """工作日判断测试"""

    def test_is_workday_true(self, memory_db):
        from src.services.holiday_service import is_workday
        assert is_workday(memory_db, date(2026, 1, 5)) is True

    def test_is_workday_false_holiday(self, memory_db):
        from src.services.holiday_service import is_workday
        assert is_workday(memory_db, date(2026, 1, 1)) is False

    def test_is_workday_true_adjusted(self, memory_db):
        from src.services.holiday_service import is_workday
        assert is_workday(memory_db, date(2026, 1, 4)) is True


class TestHolidayManagement:
    """节假日数据管理测试"""

    def test_save_holiday(self, memory_db):
        from src.services.holiday_service import save_holiday
        save_holiday(memory_db, date(2026, 4, 4), '清明节', 'statutory', 2026)

        cursor = memory_db.cursor()
        cursor.execute("SELECT * FROM holiday_config WHERE holiday_date = '2026-04-04'")
        assert cursor.fetchone() is not None

    def test_delete_holiday(self, memory_db):
        from src.services.holiday_service import delete_holiday
        delete_holiday(memory_db, date(2026, 1, 2))

        cursor = memory_db.cursor()
        cursor.execute("SELECT * FROM holiday_config WHERE holiday_date = '2026-01-02'")
        assert cursor.fetchone() is None


class TestOvertimeType:
    """加班类型判断测试"""

    def test_overtime_type_weekday(self, memory_db):
        from src.services.holiday_service import get_overtime_type
        result = get_overtime_type(memory_db, date(2026, 1, 5))
        assert result == 'weekday'

    def test_overtime_type_weekend(self, memory_db):
        from src.services.holiday_service import get_overtime_type
        result = get_overtime_type(memory_db, date(2026, 1, 10))
        assert result == 'weekend'

    def test_overtime_type_holiday(self, memory_db):
        from src.services.holiday_service import get_overtime_type
        result = get_overtime_type(memory_db, date(2026, 1, 1))
        assert result == 'holiday'
