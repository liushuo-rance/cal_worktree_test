"""
工资计算服务测试
测试内容:
1. 1.5倍/2倍/3倍工资计算（符合《劳动法》第44条）
2. 调休抵扣后的应付工资
3. 月度工资明细
4. 加班费税率处理
"""

import pytest
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
            daily_salary REAL NOT NULL,
            hourly_salary REAL NOT NULL,
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
            description TEXT
        );

        CREATE TABLE comp_off_balances (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            total_minutes INTEGER NOT NULL,
            remaining_minutes INTEGER NOT NULL,
            expiry_date DATE
        );

        CREATE TABLE comp_off_usage (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            balance_id INTEGER NOT NULL,
            used_minutes INTEGER NOT NULL,
            used_date DATE NOT NULL
        );

        CREATE TABLE leave_records (
            id INTEGER PRIMARY KEY,
            employee_id TEXT NOT NULL,
            leave_date DATE NOT NULL,
            duration_hours INTEGER NOT NULL,
            duration_minutes INTEGER DEFAULT 0,
            total_minutes INTEGER NOT NULL,
            leave_type TEXT NOT NULL,
            comp_off_deduction_minutes INTEGER DEFAULT 0,
            cash_deduction_minutes INTEGER DEFAULT 0
        );

        -- 插入员工，日薪300元，时薪37.5元
        INSERT INTO employees (employee_id, name, daily_salary, hourly_salary) VALUES
            ('EMP001', '张三', 300.0, 37.5),
            ('EMP002', '李四', 400.0, 50.0);
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_salary_data(memory_db):
    """插入样本工资计算数据"""
    cursor = memory_db.cursor()

    # 插入加班记录（各种类型）
    # 根据《劳动法》第44条：
    # - 工作日延时：1.5倍
    # - 休息日：2倍
    # - 法定假日：3倍
    overtime_records = [
        # EMP001 - 2026年1月
        # 工作日延时加班（1.5倍）
        (1, 'EMP001', '2026-01-05', 2, 30, 150, 'weekday_evening'),  # 2.5h * 1.5 = 3.75h
        (2, 'EMP001', '2026-01-06', 3, 0, 180, 'weekday_morning'),   # 3h * 1.5 = 4.5h
        # 周末加班（2倍）
        (3, 'EMP001', '2026-01-10', 4, 0, 240, 'weekend'),           # 4h * 2 = 8h
        (4, 'EMP001', '2026-01-11', 2, 0, 120, 'weekend'),           # 2h * 2 = 4h
        # 法定假日加班（3倍）
        (5, 'EMP001', '2026-01-01', 3, 0, 180, 'holiday'),           # 3h * 3 = 9h

        # EMP002 - 2026年1月
        (6, 'EMP002', '2026-01-05', 4, 0, 240, 'weekday_evening'),   # 4h * 1.5 = 6h
        (7, 'EMP002', '2026-01-17', 5, 0, 300, 'weekend'),           # 5h * 2 = 10h
    ]
    for r in overtime_records:
        cursor.execute("""
            INSERT INTO overtime_records (id, employee_id, work_date, duration_hours,
                duration_minutes, total_minutes, overtime_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, r)

    # 插入调休余额（EMP001有480分钟=8小时可用）
    balances = [
        (1, 'EMP001', 240, 240, '2026-07-10'),  # 4小时
        (2, 'EMP001', 240, 240, '2026-07-17'),  # 4小时
        (3, 'EMP002', 300, 150, '2026-07-11'),  # 2.5小时已用150分钟
    ]
    for b in balances:
        cursor.execute("""
            INSERT INTO comp_off_balances (id, employee_id, total_minutes, remaining_minutes, expiry_date)
            VALUES (?, ?, ?, ?, ?)
        """, b)

    # 插入请假记录
    # EMP001请假半天（4小时），可以用调休抵扣
    leave_records = [
        (1, 'EMP001', '2026-01-20', 4, 0, 240, 'personal', 240, 0),  # 全部用调休抵扣
        (2, 'EMP001', '2026-01-21', 2, 0, 120, 'sick', 120, 0),      # 全部用调休抵扣
        (3, 'EMP002', '2026-01-22', 3, 0, 180, 'personal', 150, 30), # 部分抵扣，30分钟扣工资
    ]
    for l in leave_records:
        cursor.execute("""
            INSERT INTO leave_records (id, employee_id, leave_date, duration_hours,
                duration_minutes, total_minutes, leave_type, comp_off_deduction_minutes, cash_deduction_minutes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, l)

    # 插入调休使用记录
    usage_records = [
        (1, 'EMP001', 1, 240, '2026-01-20'),  # 抵扣1月20日请假
        (2, 'EMP001', 2, 120, '2026-01-21'),  # 抵扣1月21日请假
        (3, 'EMP002', 3, 150, '2026-01-22'),  # 抵扣1月22日请假
    ]
    for u in usage_records:
        cursor.execute("""
            INSERT INTO comp_off_usage (id, employee_id, balance_id, used_minutes, used_date)
            VALUES (?, ?, ?, ?, ?)
        """, u)

    memory_db.commit()
    return memory_db


class TestOvertimeRateCalculation:
    """加班费率计算测试（符合《劳动法》第44条）"""

    def test_weekday_overtime_rate(self):
        """工作日延时加班：1.5倍工资"""
        from src.services.salary_service import calculate_overtime_pay

        # EMP001时薪37.5元，工作日晚班2.5小时
        pay = calculate_overtime_pay(
            hourly_rate=37.5,
            minutes=150,  # 2.5小时
            overtime_type='weekday_evening'
        )

        # 2.5h * 1.5倍 * 37.5元 = 140.625元
        expected = 150 / 60 * 1.5 * 37.5
        assert pay == pytest.approx(expected, 0.01)

    def test_weekend_overtime_rate(self):
        """休息日加班：2倍工资"""
        from src.services.salary_service import calculate_overtime_pay

        # EMP001周末加班4小时
        pay = calculate_overtime_pay(
            hourly_rate=37.5,
            minutes=240,  # 4小时
            overtime_type='weekend'
        )

        # 4h * 2倍 * 37.5元 = 300元
        expected = 240 / 60 * 2 * 37.5
        assert pay == pytest.approx(expected, 0.01)

    def test_holiday_overtime_rate(self):
        """法定假日加班：3倍工资"""
        from src.services.salary_service import calculate_overtime_pay

        # EMP001法定假日加班3小时
        pay = calculate_overtime_pay(
            hourly_rate=37.5,
            minutes=180,  # 3小时
            overtime_type='holiday'
        )

        # 3h * 3倍 * 37.5元 = 337.5元
        expected = 180 / 60 * 3 * 37.5
        assert pay == pytest.approx(expected, 0.01)

    def test_morning_overtime_rate(self):
        """早晨加班：1.5倍工资"""
        from src.services.salary_service import calculate_overtime_pay

        pay = calculate_overtime_pay(
            hourly_rate=37.5,
            minutes=120,  # 2小时
            overtime_type='weekday_morning'
        )

        # 2h * 1.5倍 * 37.5元 = 112.5元
        expected = 120 / 60 * 1.5 * 37.5
        assert pay == pytest.approx(expected, 0.01)


class TestMonthlySalaryCalculation:
    """月度工资计算测试"""

    def test_calculate_monthly_overtime_pay(self, sample_salary_data):
        from src.services.salary_service import calculate_monthly_overtime_pay

        result = calculate_monthly_overtime_pay(
            sample_salary_data,
            employee_id='EMP001',
            year=2026,
            month=1
        )

        # EMP001加班明细：
        # - 工作日晚班：150分钟 * 1.5倍 = 225分钟等值
        # - 工作早晨：180分钟 * 1.5倍 = 270分钟等值
        # - 周末1：240分钟 * 2倍 = 480分钟等值
        # - 周末2：120分钟 * 2倍 = 240分钟等值
        # - 法定假日：180分钟 * 3倍 = 540分钟等值
        # 总计等值分钟：225 + 270 + 480 + 240 + 540 = 1755分钟 = 29.25小时
        # 应付：29.25 * 37.5 = 1096.875元

        assert result['total_minutes'] == 870  # 实际加班时长
        assert result['equivalent_minutes'] == 1755  # 等值分钟（按倍数计算）
        assert result['total_pay'] == pytest.approx(1096.875, 0.01)

        # 验证分类明细
        breakdown = result['breakdown']
        assert breakdown['weekday']['minutes'] == 330  # 150 + 180
        assert breakdown['weekday']['pay'] == pytest.approx(330 / 60 * 1.5 * 37.5, 0.01)
        assert breakdown['weekend']['minutes'] == 360  # 240 + 120
        assert breakdown['weekend']['pay'] == pytest.approx(360 / 60 * 2 * 37.5, 0.01)
        assert breakdown['holiday']['minutes'] == 180
        assert breakdown['holiday']['pay'] == pytest.approx(180 / 60 * 3 * 37.5, 0.01)

    def test_calculate_monthly_leave_deduction(self, sample_salary_data):
        from src.services.salary_service import calculate_monthly_leave_deduction

        result = calculate_monthly_leave_deduction(
            sample_salary_data,
            employee_id='EMP001',
            year=2026,
            month=1
        )

        # EMP001请假：
        # - 1月20日请假4小时，全部用调休抵扣
        # - 1月21日请假2小时，全部用调休抵扣
        # 现金扣除应为0

        assert result['total_leave_minutes'] == 360  # 6小时
        assert result['comp_off_covered_minutes'] == 360  # 全部抵扣
        assert result['cash_deduction_minutes'] == 0
        assert result['cash_deduction_amount'] == 0

    def test_calculate_monthly_leave_partial_deduction(self, sample_salary_data):
        from src.services.salary_service import calculate_monthly_leave_deduction

        result = calculate_monthly_leave_deduction(
            sample_salary_data,
            employee_id='EMP002',
            year=2026,
            month=1
        )

        # EMP002请假3小时，150分钟用调休抵扣，30分钟扣工资
        # 30分钟 = 0.5小时，扣工资：0.5 * 50 = 25元

        assert result['total_leave_minutes'] == 180
        assert result['comp_off_covered_minutes'] == 150
        assert result['cash_deduction_minutes'] == 30
        assert result['cash_deduction_amount'] == pytest.approx(30 / 60 * 50, 0.01)


class TestSalaryStatement:
    """工资单生成测试"""

    def test_generate_monthly_salary_statement(self, sample_salary_data):
        from src.services.salary_service import generate_monthly_salary_statement

        statement = generate_monthly_salary_statement(
            sample_salary_data,
            employee_id='EMP001',
            year=2026,
            month=1
        )

        assert statement['employee_id'] == 'EMP001'
        assert statement['employee_name'] == '张三'
        assert statement['year'] == 2026
        assert statement['month'] == 1
        assert statement['base_salary'] == 300.0  # 日薪

        # 加班费
        assert 'overtime_pay' in statement
        assert statement['overtime_pay'] > 0

        # 请假扣除
        assert 'leave_deduction' in statement

        # 净额
        assert 'net_overtime_pay' in statement
        assert statement['net_overtime_pay'] == statement['overtime_pay'] - statement['leave_deduction']

    def test_salary_statement_details(self, sample_salary_data):
        from src.services.salary_service import generate_monthly_salary_statement

        statement = generate_monthly_salary_statement(
            sample_salary_data,
            employee_id='EMP001',
            year=2026,
            month=1
        )

        # 验证明细
        assert 'details' in statement
        details = statement['details']

        # 加班明细
        assert 'overtime_records' in details
        assert len(details['overtime_records']) == 5  # EMP001有5条加班记录

        # 请假明细
        assert 'leave_records' in details
        assert len(details['leave_records']) == 2  # EMP001有2条请假记录


class TestBatchSalaryCalculation:
    """批量工资计算测试"""

    def test_calculate_department_salary(self, sample_salary_data):
        from src.services.salary_service import calculate_department_salary

        results = calculate_department_salary(
            sample_salary_data,
            year=2026,
            month=1
        )

        assert len(results) == 2  # 两个员工

        # EMP001
        emp001 = next(r for r in results if r['employee_id'] == 'EMP001')
        assert emp001['overtime_pay'] > 0

        # EMP002
        emp002 = next(r for r in results if r['employee_id'] == 'EMP002')
        assert emp002['overtime_pay'] > 0

    def test_calculate_department_total(self, sample_salary_data):
        from src.services.salary_service import calculate_department_total

        total = calculate_department_total(
            sample_salary_data,
            year=2026,
            month=1
        )

        # EMP001加班费：约1096.88元
        # EMP002加班费：
        #   - 工作日晚班：240分钟 * 1.5 = 360分钟等值 = 6 * 50 = 300元
        #   - 周末：300分钟 * 2 = 600分钟等值 = 10 * 50 = 500元
        #   总计：800元
        # 扣除：30分钟 * 50元/小时 = 25元
        # EMP002净额：775元

        assert total['total_employees'] == 2
        assert total['total_overtime_pay'] > 0
        assert total['total_leave_deduction'] >= 0
        assert total['total_net_pay'] == total['total_overtime_pay'] - total['total_leave_deduction']


class TestSalaryValidation:
    """工资计算验证测试"""

    def test_invalid_employee(self, sample_salary_data):
        from src.services.salary_service import calculate_monthly_overtime_pay, SalaryServiceError

        with pytest.raises(SalaryServiceError):
            calculate_monthly_overtime_pay(
                sample_salary_data,
                employee_id='INVALID',
                year=2026,
                month=1
            )

    def test_negative_salary_rejected(self):
        from src.services.salary_service import validate_salary_input, SalaryServiceError

        with pytest.raises(SalaryServiceError):
            validate_salary_input(hourly_rate=-10)

    def test_zero_salary_rejected(self):
        from src.services.salary_service import validate_salary_input, SalaryServiceError

        with pytest.raises(SalaryServiceError):
            validate_salary_input(hourly_rate=0)
