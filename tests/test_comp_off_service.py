"""
调休余额服务测试
测试内容:
1. 调休余额计算（总获得-已使用）
2. FIFO抵扣算法
3. 过期提醒
4. 周末加班自动生成调休
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
            name TEXT NOT NULL
        );

        CREATE TABLE overtime_records (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            work_date DATE NOT NULL,
            duration_hours INTEGER NOT NULL,
            duration_minutes INTEGER NOT NULL DEFAULT 0,
            total_minutes INTEGER NOT NULL,
            overtime_type TEXT NOT NULL
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        );

        CREATE TABLE comp_off_usage_records (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            balance_id INTEGER,
            used_minutes INTEGER NOT NULL DEFAULT 0,
            usage_date DATE NOT NULL,
            leave_record_id INTEGER,
            duration_hours INTEGER NOT NULL DEFAULT 0,
            duration_minutes INTEGER NOT NULL DEFAULT 0,
            total_minutes INTEGER NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (balance_id) REFERENCES comp_off_balances(id)
        );

        CREATE TABLE leave_records (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            leave_date DATE NOT NULL,
            duration_hours INTEGER NOT NULL,
            duration_minutes INTEGER DEFAULT 0,
            total_minutes INTEGER NOT NULL,
            leave_type TEXT NOT NULL,
            comp_off_deduction_minutes INTEGER DEFAULT 0
        );

        INSERT INTO employees (employee_id, name) VALUES
            ('EMP001', '张三'),
            ('EMP002', '李四');
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_comp_off_data(memory_db):
    """插入样本调休数据"""
    cursor = memory_db.cursor()

    # 先插入周末加班记录
    overtime_records = [
        (1, 'EMP001', '2026-01-10', 4, 0, 240, 'weekend'),  # 周六
        (2, 'EMP001', '2026-01-17', 3, 0, 180, 'weekend'),  # 周六
        (3, 'EMP001', '2026-01-24', 2, 0, 120, 'weekend'),  # 周六
        (4, 'EMP002', '2026-01-11', 5, 0, 300, 'weekend'),  # 周日
    ]
    for r in overtime_records:
        cursor.execute("""
            INSERT INTO overtime_records (id, employee_id, work_date, duration_hours,
                duration_minutes, total_minutes, overtime_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, r)

    # 插入调休余额（来自周末加班）
    # 注意：周末加班1:1生成调休余额
    balances = [
        # EMP001 的调休余额
        (1, 'EMP001', 1, '2026-01-10', 240, 120, '2026-07-10'),  # 剩余120分钟
        (2, 'EMP001', 2, '2026-01-17', 180, 180, '2026-07-17'),  # 未使用
        (3, 'EMP001', 3, '2026-01-24', 120, 0, '2026-07-24'),    # 已用完
        # EMP002 的调休余额
        (4, 'EMP002', 4, '2026-01-11', 300, 300, '2026-07-11'),  # 未使用
    ]
    for b in balances:
        cursor.execute("""
            INSERT INTO comp_off_balances (id, employee_id, source_overtime_id,
                acquired_date, total_minutes, remaining_minutes, expiry_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, b)

    # 插入调休使用记录
    usage_records = [
        (1, 'EMP001', 1, 60, '2026-02-05'),   # 使用第一条余额60分钟
        (2, 'EMP001', 1, 60, '2026-02-20'),   # 再使用第一条余额60分钟（共120，用完）
        (3, 'EMP001', 3, 120, '2026-02-10'),  # 使用第三条余额120分钟（用完）
    ]
    for u in usage_records:
        cursor.execute("""
            INSERT INTO comp_off_usage_records
            (id, employee_id, balance_id, used_minutes, usage_date, total_minutes, status)
            VALUES (?, ?, ?, ?, ?, ?, 'approved')
        """, (u[0], u[1], u[2], u[3], u[4], u[3]))

    memory_db.commit()
    return memory_db


class TestCompOffBalanceCalculation:
    """调休余额计算测试"""

    def test_get_total_acquired(self, sample_comp_off_data):
        from src.services.comp_off_service import get_total_acquired

        # EMP001: 240 + 180 + 120 = 540分钟
        total = get_total_acquired(sample_comp_off_data, 'EMP001')
        assert total == 540

    def test_get_total_used(self, sample_comp_off_data):
        from src.services.comp_off_service import get_total_used

        # EMP001: 60 + 60 + 120 = 240分钟
        total = get_total_used(sample_comp_off_data, 'EMP001')
        assert total == 240

    def test_get_remaining_balance(self, sample_comp_off_data):
        from src.services.comp_off_service import get_remaining_balance

        # EMP001: 总获得540 - 已用240 = 300分钟
        remaining = get_remaining_balance(sample_comp_off_data, 'EMP001')
        assert remaining == 300

    def test_get_balance_breakdown(self, sample_comp_off_data):
        from src.services.comp_off_service import get_balance_breakdown

        breakdown = get_balance_breakdown(sample_comp_off_data, 'EMP001')

        # 应该有两条有效余额（第三条remaining=0）
        assert len(breakdown) == 2
        # 按日期排序
        assert breakdown[0]['acquired_date'] == '2026-01-10'
        assert breakdown[0]['remaining_minutes'] == 120
        assert breakdown[1]['acquired_date'] == '2026-01-17'
        assert breakdown[1]['remaining_minutes'] == 180


class TestCompOffFIFODeduction:
    """FIFO调休抵扣测试"""

    def test_deduct_comp_off_basic(self, sample_comp_off_data):
        from src.services.comp_off_service import deduct_comp_off

        # 抵扣4小时（240分钟）
        result = deduct_comp_off(
            sample_comp_off_data,
            employee_id='EMP001',
            deduction_date=date(2026, 3, 1),
            minutes_needed=240
        )

        # 应该使用最早的余额：第一条120分钟 + 第二条180分钟中的120分钟
        assert result['success'] is True
        assert result['deducted_minutes'] == 240
        assert len(result['deductions']) == 2

        # 验证第一条余额已用完
        cursor = sample_comp_off_data.cursor()
        cursor.execute("SELECT remaining_minutes FROM comp_off_balances WHERE id = 1")
        assert cursor.fetchone()['remaining_minutes'] == 0

        # 验证第二条余额还剩60分钟
        cursor.execute("SELECT remaining_minutes FROM comp_off_balances WHERE id = 2")
        assert cursor.fetchone()['remaining_minutes'] == 60

    def test_deduct_comp_off_insufficient_balance(self, sample_comp_off_data):
        from src.services.comp_off_service import deduct_comp_off, CompOffError

        # 尝试抵扣超过余额的量
        with pytest.raises(CompOffError):
            deduct_comp_off(
                sample_comp_off_data,
                employee_id='EMP001',
                deduction_date=date(2026, 3, 1),
                minutes_needed=1000  # 远超可用余额
            )

    def test_deduct_comp_off_partial(self, sample_comp_off_data):
        from src.services.comp_off_service import deduct_comp_off

        # 只抵扣60分钟
        result = deduct_comp_off(
            sample_comp_off_data,
            employee_id='EMP001',
            deduction_date=date(2026, 3, 1),
            minutes_needed=60
        )

        assert result['success'] is True
        assert result['deducted_minutes'] == 60
        assert len(result['deductions']) == 1

        # 验证第一条余额还剩60分钟
        cursor = sample_comp_off_data.cursor()
        cursor.execute("SELECT remaining_minutes FROM comp_off_balances WHERE id = 1")
        assert cursor.fetchone()['remaining_minutes'] == 60

    def test_deduct_comp_off_exact_amount(self, sample_comp_off_data):
        from src.services.comp_off_service import deduct_comp_off

        # 精确抵扣第一条余额的120分钟
        result = deduct_comp_off(
            sample_comp_off_data,
            employee_id='EMP001',
            deduction_date=date(2026, 3, 1),
            minutes_needed=120
        )

        assert result['success'] is True
        assert result['deducted_minutes'] == 120
        assert len(result['deductions']) == 1

        # 验证第一条余额已用完
        cursor = sample_comp_off_data.cursor()
        cursor.execute("SELECT remaining_minutes FROM comp_off_balances WHERE id = 1")
        assert cursor.fetchone()['remaining_minutes'] == 0


class TestCompOffExpiry:
    """调休过期测试"""

    def test_get_expiring_balances(self, sample_comp_off_data):
        from src.services.comp_off_service import get_expiring_balances

        # 查询即将在30天内过期的余额（假设当前日期是2026-06-15）
        expiring = get_expiring_balances(
            sample_comp_off_data,
            reference_date=date(2026, 6, 15),
            days_threshold=30
        )

        # 2026-07-10, 2026-07-17, 2026-07-24, 2026-07-11 都即将过期
        assert len(expiring) >= 1

    def test_expire_balance(self, sample_comp_off_data):
        from src.services.comp_off_service import expire_balance

        # 将第一条余额标记为过期
        expire_balance(sample_comp_off_data, balance_id=1)

        cursor = sample_comp_off_data.cursor()
        cursor.execute("SELECT status FROM comp_off_balances WHERE id = 1")
        assert cursor.fetchone()['status'] == 'expired'


class TestCompOffGeneration:
    """调休生成测试（周末加班自动生成调休）"""

    def test_create_comp_off_from_weekend(self, memory_db):
        from src.services.comp_off_service import create_comp_off_from_overtime

        # 先插入一条周末加班记录
        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records (employee_id, work_date, duration_hours,
                duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2026-01-10', 4, 0, 240, 'weekend')
        """)
        overtime_id = cursor.lastrowid
        memory_db.commit()

        # 生成调休余额
        balance_id = create_comp_off_from_overtime(memory_db, overtime_id)

        assert balance_id is not None

        # 验证调休余额
        cursor.execute("SELECT * FROM comp_off_balances WHERE id = ?", (balance_id,))
        row = cursor.fetchone()
        assert row['employee_id'] == 'EMP001'
        assert row['total_minutes'] == 240
        assert row['remaining_minutes'] == 240
        assert row['acquired_date'] == '2026-01-10'

    def test_weekday_overtime_no_comp_off(self, memory_db):
        from src.services.comp_off_service import create_comp_off_from_overtime, CompOffError

        # 插入工作日加班记录
        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records (employee_id, work_date, duration_hours,
                duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2026-01-05', 2, 0, 120, 'weekday_evening')
        """)
        overtime_id = cursor.lastrowid
        memory_db.commit()

        # 工作日加班不应生成调休
        with pytest.raises(CompOffError):
            create_comp_off_from_overtime(memory_db, overtime_id)

    def test_holiday_overtime_no_comp_off(self, memory_db):
        from src.services.comp_off_service import create_comp_off_from_overtime, CompOffError

        # 插入法定假日加班记录
        cursor = memory_db.cursor()
        cursor.execute("""
            INSERT INTO overtime_records (employee_id, work_date, duration_hours,
                duration_minutes, total_minutes, overtime_type)
            VALUES ('EMP001', '2026-01-01', 3, 0, 180, 'holiday')
        """)
        overtime_id = cursor.lastrowid
        memory_db.commit()

        # 法定假日加班不应生成调休
        with pytest.raises(CompOffError):
            create_comp_off_from_overtime(memory_db, overtime_id)


class TestLeaveCompOffDeduction:
    """请假时的调休抵扣测试"""

    def test_apply_comp_off_to_leave(self, sample_comp_off_data):
        from src.services.comp_off_service import apply_comp_off_to_leave

        # 请假4小时
        result = apply_comp_off_to_leave(
            sample_comp_off_data,
            employee_id='EMP001',
            leave_date=date(2026, 3, 15),
            leave_minutes=240
        )

        assert result['success'] is True
        assert result['covered_minutes'] == 240
        assert result['cash_deduction_minutes'] == 0  # 全部用调休抵扣

    def test_apply_comp_off_partial(self, sample_comp_off_data):
        from src.services.comp_off_service import apply_comp_off_to_leave

        # EMP001有300分钟余额，请假8小时（480分钟）
        result = apply_comp_off_to_leave(
            sample_comp_off_data,
            employee_id='EMP001',
            leave_date=date(2026, 3, 15),
            leave_minutes=480
        )

        assert result['success'] is True
        assert result['covered_minutes'] == 300  # 只有300分钟调休
        assert result['cash_deduction_minutes'] == 180  # 剩余180分钟扣工资

    def test_apply_comp_off_no_balance(self, sample_comp_off_data):
        from src.services.comp_off_service import apply_comp_off_to_leave

        # EMP002没有调休余额（或未设置）
        result = apply_comp_off_to_leave(
            sample_comp_off_data,
            employee_id='EMP002',
            leave_date=date(2026, 3, 15),
            leave_minutes=240
        )

        # EMP002有300分钟余额
        assert result['success'] is True
        assert result['covered_minutes'] == 240
        assert result['cash_deduction_minutes'] == 0
