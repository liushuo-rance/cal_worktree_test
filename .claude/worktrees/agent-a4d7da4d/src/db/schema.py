"""
数据库Schema定义
包含所有表结构和初始化函数
"""

import sqlite3


# 加班类型枚举值
OVERTIME_TYPES = [
    'weekday_morning',   # 工作日早晨加班
    'weekday_lunch',     # 工作日午休加班
    'weekday_evening',   # 工作日晚间加班
    'weekend',           # 周末加班
    'holiday'            # 法定节假日加班
]

# 请假类型枚举值
LEAVE_TYPES = [
    'personal',   # 事假
    'sick',       # 病假
    'annual',     # 年假
    'other'       # 其他
]

# 节假日类型枚举值
HOLIDAY_TYPES = [
    'statutory',         # 法定节假日
    'adjusted_holiday',  # 调休形成的假期
    'adjusted_workday'   # 调休上班日
]

# 调休余额状态
COMP_OFF_STATUS = [
    'active',    # 有效
    'used',      # 已用完
    'expired'    # 已过期
]

# 导入会话状态
IMPORT_STATUS = [
    'pending',     # 待处理
    'processing',  # 处理中
    'completed',   # 已完成
    'failed'       # 失败
]


def init_database(conn: sqlite3.Connection) -> None:
    """
    初始化数据库表结构

    Args:
        conn: SQLite数据库连接
    """
    cursor = conn.cursor()

    # 员工表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            department TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 加班记录表
    overtime_type_values = ', '.join([f"'{t}'" for t in OVERTIME_TYPES])
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS overtime_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            date DATE NOT NULL,
            overtime_type TEXT CHECK(overtime_type IN ({overtime_type_values})),
            duration_hours INTEGER NOT NULL CHECK(duration_hours >= 0),
            duration_minutes INTEGER NOT NULL CHECK(duration_minutes >= 0 AND duration_minutes < 60),
            total_minutes INTEGER NOT NULL CHECK(total_minutes > 0),
            description TEXT,
            raw_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        )
    """)

    # 请假记录表
    leave_type_values = ', '.join([f"'{t}'" for t in LEAVE_TYPES])
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS leave_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            date_start DATE NOT NULL,
            date_end DATE NOT NULL,
            leave_type TEXT CHECK(leave_type IN ({leave_type_values})),
            duration_hours INTEGER NOT NULL CHECK(duration_hours >= 0),
            duration_minutes INTEGER NOT NULL CHECK(duration_minutes >= 0 AND duration_minutes < 60),
            total_minutes INTEGER NOT NULL CHECK(total_minutes > 0),
            description TEXT,
            raw_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        )
    """)

    # 调休余额表
    comp_off_status_values = ', '.join([f"'{s}'" for s in COMP_OFF_STATUS])
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS comp_off_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            acquired_date DATE NOT NULL,
            expiry_date DATE,
            total_hours INTEGER NOT NULL CHECK(total_hours >= 0),
            total_minutes INTEGER NOT NULL CHECK(total_minutes >= 0 AND total_minutes < 60),
            used_hours INTEGER NOT NULL DEFAULT 0 CHECK(used_hours >= 0),
            used_minutes INTEGER NOT NULL DEFAULT 0 CHECK(used_minutes >= 0 AND used_minutes < 60),
            status TEXT DEFAULT 'active' CHECK(status IN ({comp_off_status_values})),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        )
    """)

    # 调休使用记录表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comp_off_usage_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            usage_date DATE NOT NULL,
            leave_record_id INTEGER,
            duration_hours INTEGER NOT NULL CHECK(duration_hours >= 0),
            duration_minutes INTEGER NOT NULL CHECK(duration_minutes >= 0 AND duration_minutes < 60),
            total_minutes INTEGER NOT NULL CHECK(total_minutes > 0),
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
            FOREIGN KEY (leave_record_id) REFERENCES leave_records(id)
        )
    """)

    # 节假日配置表
    holiday_type_values = ', '.join([f"'{t}'" for t in HOLIDAY_TYPES])
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS holiday_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            holiday_date DATE NOT NULL UNIQUE,
            holiday_name TEXT NOT NULL,
            holiday_type TEXT CHECK(holiday_type IN ({holiday_type_values})),
            year INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 导入会话表
    import_status_values = ', '.join([f"'{s}'" for s in IMPORT_STATUS])
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS import_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ({import_status_values})),
            total_records INTEGER DEFAULT 0,
            processed_records INTEGER DEFAULT 0,
            error_records INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)

    # 导入记录详情表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS import_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            line_number INTEGER,
            raw_text TEXT,
            parsed_data TEXT,
            status TEXT DEFAULT 'pending',
            error_message TEXT,
            record_type TEXT,
            target_table TEXT,
            target_record_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES import_sessions(id)
        )
    """)

    # 创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_overtime_employee_date
        ON overtime_records(employee_id, date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_leave_employee_date
        ON leave_records(employee_id, date_start)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_comp_off_employee_status
        ON comp_off_balances(employee_id, status)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_holiday_year
        ON holiday_config(year)
    """)

    conn.commit()


def create_views(conn: sqlite3.Connection) -> None:
    """
    创建数据库视图

    Args:
        conn: SQLite数据库连接
    """
    cursor = conn.cursor()

    # 员工加班统计视图
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS v_employee_overtime_summary AS
        SELECT
            employee_id,
            strftime('%Y-%m', date) as month,
            overtime_type,
            COUNT(*) as record_count,
            SUM(duration_hours) as total_hours,
            SUM(duration_minutes) as total_minutes,
            SUM(total_minutes) as total_minutes_calculated
        FROM overtime_records
        GROUP BY employee_id, strftime('%Y-%m', date), overtime_type
    """)

    # 员工调休余额视图
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS v_employee_comp_off_balance AS
        SELECT
            employee_id,
            SUM(total_hours) as total_acquired_hours,
            SUM(total_minutes) as total_acquired_minutes,
            SUM(used_hours) as total_used_hours,
            SUM(used_minutes) as total_used_minutes,
            SUM(total_hours * 60 + total_minutes - used_hours * 60 - used_minutes) as remaining_minutes
        FROM comp_off_balances
        WHERE status = 'active'
        GROUP BY employee_id
    """)

    conn.commit()
