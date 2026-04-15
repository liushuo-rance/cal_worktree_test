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
    'reviewing',   # 审批中
    'completed',   # 已完成
    'failed'       # 失败
]


def _migrate_import_sessions(conn: sqlite3.Connection) -> None:
    """
    迁移 import_sessions 表：如果旧表缺少 employee_id 列或 CHECK 约束不包含 reviewing，
    则通过重命名+重建表的方式升级，保留历史数据。
    """
    cursor = conn.cursor()

    # 检查表是否存在
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='import_sessions'"
    )
    if not cursor.fetchone():
        return

    # 检查是否已有 employee_id 列
    cursor.execute("PRAGMA table_info(import_sessions)")
    columns = {row[1] for row in cursor.fetchall()}
    if 'employee_id' in columns:
        return

    # 需要迁移：禁用外键、重命名旧表、创建新表、复制数据
    import_status_values = ', '.join([f"'{s}'" for s in IMPORT_STATUS])
    cursor.execute("PRAGMA foreign_keys = OFF")

    cursor.execute("ALTER TABLE import_sessions RENAME TO _old_import_sessions")
    cursor.execute(f"""
        CREATE TABLE import_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            employee_id TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ({import_status_values})),
            total_records INTEGER DEFAULT 0,
            processed_records INTEGER DEFAULT 0,
            error_records INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    cursor.execute("""
        INSERT INTO import_sessions
            (id, file_path, employee_id, status, total_records,
             processed_records, error_records, created_at, completed_at)
        SELECT
            id, file_path, NULL, status, total_records,
            processed_records, error_records, created_at, completed_at
        FROM _old_import_sessions
    """)
    cursor.execute("DROP TABLE _old_import_sessions")
    cursor.execute("PRAGMA foreign_keys = ON")


def _migrate_comp_off_balances(conn: sqlite3.Connection) -> None:
    """
    迁移旧版 comp_off_balances 表：将 total_hours/used_hours/used_minutes
    转换为 total_minutes/remaining_minutes，并添加 source_overtime_id 列。
    """
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='comp_off_balances'"
    )
    if not cursor.fetchone():
        return

    cursor.execute("PRAGMA table_info(comp_off_balances)")
    columns = {row[1] for row in cursor.fetchall()}
    if 'source_overtime_id' in columns:
        return

    comp_off_status_values = ', '.join([f"'{s}'" for s in COMP_OFF_STATUS])
    cursor.execute("PRAGMA foreign_keys = OFF")
    cursor.execute("ALTER TABLE comp_off_balances RENAME TO _old_comp_off_balances")
    cursor.execute(f"""
        CREATE TABLE comp_off_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            source_overtime_id INTEGER,
            acquired_date DATE NOT NULL,
            expiry_date DATE,
            total_minutes INTEGER NOT NULL CHECK(total_minutes >= 0),
            remaining_minutes INTEGER NOT NULL CHECK(remaining_minutes >= 0),
            status TEXT DEFAULT 'active'
                CHECK(status IN ({comp_off_status_values})),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        )
    """)

    cursor.execute("PRAGMA table_info(_old_comp_off_balances)")
    old_columns = {row[1] for row in cursor.fetchall()}

    select_parts = []
    for col in ['id', 'employee_id', 'source_overtime_id', 'acquired_date', 'expiry_date',
                'total_minutes', 'remaining_minutes', 'status', 'created_at', 'updated_at']:
        if col == 'source_overtime_id':
            select_parts.append('NULL')
        elif col == 'total_minutes':
            select_parts.append('COALESCE(total_hours, 0) * 60 + COALESCE(total_minutes, 0)')
        elif col == 'remaining_minutes':
            select_parts.append(
                'MAX(0, COALESCE(total_hours, 0) * 60 + COALESCE(total_minutes, 0) '
                '- (COALESCE(used_hours, 0) * 60 + COALESCE(used_minutes, 0)))'
            )
        elif col in old_columns:
            select_parts.append(col)
        else:
            if col == 'status':
                select_parts.append("'active'")
            elif col in ('created_at', 'updated_at'):
                select_parts.append('CURRENT_TIMESTAMP')
            else:
                select_parts.append('NULL')

    cursor.execute(f"""
        INSERT INTO comp_off_balances
            (id, employee_id, source_overtime_id, acquired_date, expiry_date,
             total_minutes, remaining_minutes, status, created_at, updated_at)
        SELECT
            {', '.join(select_parts)}
        FROM _old_comp_off_balances
    """)
    cursor.execute("DROP TABLE _old_comp_off_balances")
    cursor.execute("PRAGMA foreign_keys = ON")


def _migrate_comp_off_usage_records(conn: sqlite3.Connection) -> None:
    """
    迁移旧版 comp_off_usage_records 表：添加 balance_id、used_minutes、
    status 和 source_import_id 列。
    """
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='comp_off_usage_records'"
    )
    if not cursor.fetchone():
        return

    cursor.execute("PRAGMA table_info(comp_off_usage_records)")
    columns = {row[1] for row in cursor.fetchall()}
    if 'balance_id' in columns and 'status' in columns:
        return

    cursor.execute("PRAGMA foreign_keys = OFF")
    cursor.execute("ALTER TABLE comp_off_usage_records RENAME TO _old_comp_off_usage_records")
    cursor.execute("""
        CREATE TABLE comp_off_usage_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            balance_id INTEGER,
            used_minutes INTEGER NOT NULL DEFAULT 0 CHECK(used_minutes >= 0),
            usage_date DATE NOT NULL,
            leave_record_id INTEGER,
            duration_hours INTEGER NOT NULL CHECK(duration_hours >= 0),
            duration_minutes INTEGER NOT NULL
                CHECK(duration_minutes >= 0 AND duration_minutes < 60),
            total_minutes INTEGER NOT NULL CHECK(total_minutes > 0),
            description TEXT,
            source_import_id INTEGER,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
            FOREIGN KEY (balance_id) REFERENCES comp_off_balances(id),
            FOREIGN KEY (leave_record_id) REFERENCES leave_records(id)
        )
    """)
    cursor.execute("PRAGMA table_info(_old_comp_off_usage_records)")
    old_columns = {row[1] for row in cursor.fetchall()}

    select_parts = []
    for col in ['id', 'employee_id', 'balance_id', 'used_minutes', 'usage_date',
                'leave_record_id', 'duration_hours', 'duration_minutes',
                'total_minutes', 'description', 'source_import_id', 'status', 'created_at']:
        if col == 'balance_id':
            select_parts.append('NULL')
        elif col == 'used_minutes':
            select_parts.append('COALESCE(total_minutes, 0)')
        elif col == 'status':
            if 'status' in old_columns:
                select_parts.append(col)
            else:
                select_parts.append("'approved'")
        elif col in old_columns:
            select_parts.append(col)
        else:
            if col == 'created_at':
                select_parts.append('CURRENT_TIMESTAMP')
            else:
                select_parts.append('NULL')

    cursor.execute(f"""
        INSERT INTO comp_off_usage_records
            (id, employee_id, balance_id, used_minutes, usage_date,
             leave_record_id, duration_hours, duration_minutes,
             total_minutes, description, source_import_id, status, created_at)
        SELECT
            {', '.join(select_parts)}
        FROM _old_comp_off_usage_records
    """)
    cursor.execute("DROP TABLE _old_comp_off_usage_records")
    cursor.execute("PRAGMA foreign_keys = ON")


def _migrate_employees_for_soft_delete(conn: sqlite3.Connection) -> None:
    """
    迁移 employees 表：如果缺少 is_active 列，
    则通过重命名+重建表的方式添加，保留历史数据。
    """
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='employees'"
    )
    if not cursor.fetchone():
        return

    cursor.execute("PRAGMA table_info(employees)")
    columns = {row[1] for row in cursor.fetchall()}
    if 'is_active' in columns:
        return

    cursor.execute("PRAGMA foreign_keys = OFF")
    cursor.execute("ALTER TABLE employees RENAME TO _old_employees")
    cursor.execute("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            department TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        INSERT INTO employees
            (id, employee_id, name, department, is_active, created_at, updated_at)
        SELECT
            id, employee_id, name, department, 1, created_at, updated_at
        FROM _old_employees
    """)
    cursor.execute("DROP TABLE _old_employees")
    cursor.execute("PRAGMA foreign_keys = ON")


def _migrate_overtime_records_for_employment_status(conn: sqlite3.Connection) -> None:
    """
    迁移 overtime_records 表：如果缺少 employment_status 列，
    则通过重命名+重建表的方式添加，保留历史数据。
    """
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='overtime_records'"
    )
    if not cursor.fetchone():
        return

    cursor.execute("PRAGMA table_info(overtime_records)")
    columns = {row[1] for row in cursor.fetchall()}
    if 'employment_status' in columns:
        return

    overtime_type_values = ', '.join([f"'{t}'" for t in OVERTIME_TYPES])
    cursor.execute("PRAGMA foreign_keys = OFF")
    cursor.execute("ALTER TABLE overtime_records RENAME TO _old_overtime_records")
    cursor.execute(f"""
        CREATE TABLE overtime_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            work_date DATE NOT NULL,
            overtime_type TEXT CHECK(overtime_type IN ({overtime_type_values})),
            duration_hours INTEGER NOT NULL CHECK(duration_hours >= 0),
            duration_minutes INTEGER NOT NULL
                CHECK(duration_minutes >= 0 AND duration_minutes < 60),
            total_minutes INTEGER NOT NULL CHECK(total_minutes > 0),
            description TEXT,
            raw_text TEXT,
            source_import_id INTEGER,
            employment_status TEXT DEFAULT 'active'
                CHECK(employment_status IN ('active', 'inactive')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        )
    """)
    cursor.execute("""
        INSERT INTO overtime_records
            (id, employee_id, work_date, overtime_type, duration_hours, duration_minutes,
             total_minutes, description, raw_text, source_import_id, employment_status,
             created_at, updated_at)
        SELECT
            id, employee_id, work_date, overtime_type, duration_hours, duration_minutes,
            total_minutes, description, raw_text, source_import_id, 'active',
            created_at, updated_at
        FROM _old_overtime_records
    """)
    cursor.execute("DROP TABLE _old_overtime_records")
    cursor.execute("PRAGMA foreign_keys = ON")


def _migrate_notifications_table(conn: sqlite3.Connection) -> None:
    """
    迁移 notifications 表：如果表不存在则创建它。
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
    )
    if cursor.fetchone():
        return

    notification_type_values = ', '.join([
        "'compliance_warning'", "'compliance_violation'", "'system'"
    ])
    cursor.execute(f"""
        CREATE TABLE notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ({notification_type_values})),
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        )
    """)
    cursor.execute("""
        CREATE INDEX idx_notifications_employee_read
        ON notifications(employee_id, is_read, created_at)
    """)
    conn.commit()


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
            is_active INTEGER DEFAULT 1,
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
            work_date DATE NOT NULL,
            overtime_type TEXT CHECK(overtime_type IN ({overtime_type_values})),
            duration_hours INTEGER NOT NULL CHECK(duration_hours >= 0),
            duration_minutes INTEGER NOT NULL
                CHECK(duration_minutes >= 0 AND duration_minutes < 60),
            total_minutes INTEGER NOT NULL CHECK(total_minutes > 0),
            description TEXT,
            raw_text TEXT,
            source_import_id INTEGER,
            employment_status TEXT DEFAULT 'active'
                CHECK(employment_status IN ('active', 'inactive')),
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
            leave_date DATE NOT NULL,
            leave_type TEXT CHECK(leave_type IN ({leave_type_values})),
            duration_hours INTEGER NOT NULL CHECK(duration_hours >= 0),
            duration_minutes INTEGER NOT NULL
                CHECK(duration_minutes >= 0 AND duration_minutes < 60),
            total_minutes INTEGER NOT NULL CHECK(total_minutes > 0),
            description TEXT,
            raw_text TEXT,
            source_import_id INTEGER,
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
            source_overtime_id INTEGER,
            acquired_date DATE NOT NULL,
            expiry_date DATE,
            total_minutes INTEGER NOT NULL CHECK(total_minutes >= 0),
            remaining_minutes INTEGER NOT NULL CHECK(remaining_minutes >= 0),
            status TEXT DEFAULT 'active'
                CHECK(status IN ({comp_off_status_values})),
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
            balance_id INTEGER,
            used_minutes INTEGER NOT NULL DEFAULT 0 CHECK(used_minutes >= 0),
            usage_date DATE NOT NULL,
            leave_record_id INTEGER,
            duration_hours INTEGER NOT NULL CHECK(duration_hours >= 0),
            duration_minutes INTEGER NOT NULL
                CHECK(duration_minutes >= 0 AND duration_minutes < 60),
            total_minutes INTEGER NOT NULL CHECK(total_minutes > 0),
            description TEXT,
            source_import_id INTEGER,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
            FOREIGN KEY (balance_id) REFERENCES comp_off_balances(id),
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
            employee_id TEXT,
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

    # 审批队列表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_session_id INTEGER NOT NULL,
            raw_text TEXT NOT NULL,
            parsed_type TEXT,
            parsed_subtype TEXT,
            parsed_date TEXT,
            parsed_hours REAL,
            parsed_minutes INTEGER,
            confidence_level TEXT,
            confidence_score REAL,
            anomalies TEXT,
            status TEXT DEFAULT 'pending',
            reviewer_note TEXT,
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (import_session_id) REFERENCES import_sessions(id)
        )
    """)

    # 创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_overtime_employee_date
        ON overtime_records(employee_id, work_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_review_queue_session_status
        ON review_queue(import_session_id, status)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_leave_employee_date
        ON leave_records(employee_id, leave_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_comp_off_employee_status
        ON comp_off_balances(employee_id, status)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_holiday_year
        ON holiday_config(year)
    """)

    # 通知历史表
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

    # 应用配置表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_config (
            config_key TEXT PRIMARY KEY NOT NULL,
            config_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 站内通知表
    notification_type_values = ', '.join([
        "'compliance_warning'", "'compliance_violation'", "'system'"
    ])
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ({notification_type_values})),
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        )
    """)

    # 用户表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin', 'user')),
            employee_id TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE SET NULL
        )
    """)

    # 创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_overtime_employee_date
        ON overtime_records(employee_id, work_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_review_queue_session_status
        ON review_queue(import_session_id, status)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_leave_employee_date
        ON leave_records(employee_id, leave_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_comp_off_employee_status
        ON comp_off_balances(employee_id, status)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_holiday_year
        ON holiday_config(year)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_notifications_employee_read
        ON notifications(employee_id, is_read, created_at)
    """)

    # 通知历史表
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

    # 迁移旧版 schema
    _migrate_import_sessions(conn)
    _migrate_comp_off_balances(conn)
    _migrate_comp_off_usage_records(conn)
    _migrate_comp_off_balances_if_needed(conn)
    _migrate_comp_off_usage_if_needed(conn)
    _migrate_employees_for_soft_delete(conn)
    _migrate_overtime_records_for_employment_status(conn)
    _migrate_notifications_table(conn)

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
            strftime('%Y-%m', work_date) as month,
            overtime_type,
            COUNT(*) as record_count,
            SUM(duration_hours) as total_hours,
            SUM(duration_minutes) as total_minutes,
            SUM(total_minutes) as total_minutes_calculated
        FROM overtime_records
        GROUP BY employee_id, strftime('%Y-%m', work_date), overtime_type
    """)

    # 员工调休余额视图
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS v_employee_comp_off_balance AS
        SELECT
            employee_id,
            SUM(total_minutes) / 60 as total_acquired_hours,
            SUM(total_minutes) % 60 as total_acquired_minutes,
            SUM(total_minutes - remaining_minutes) / 60 as total_used_hours,
            SUM(total_minutes - remaining_minutes) % 60 as total_used_minutes,
            SUM(remaining_minutes) as remaining_minutes
        FROM comp_off_balances
        WHERE status = 'active'
        GROUP BY employee_id
    """)

    conn.commit()


def _migrate_comp_off_usage_if_needed(conn: sqlite3.Connection) -> None:
    """如果缺少 comp_off_usage 表，则创建它"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comp_off_usage'")
    if cursor.fetchone() is not None:
        return

    cursor.execute("""
        CREATE TABLE comp_off_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            balance_id INTEGER NOT NULL,
            used_minutes INTEGER NOT NULL CHECK(used_minutes > 0),
            used_date DATE NOT NULL,
            related_leave_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (balance_id) REFERENCES comp_off_balances(id)
        )
    """)
    conn.commit()


def seed_default_admin(conn: sqlite3.Connection, password: str = "admin123") -> None:
    """
    插入默认管理员账号（如果不存在）。

    Args:
        conn: SQLite 数据库连接
        password: 管理员密码，默认 admin123
    """
    from werkzeug.security import generate_password_hash

    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if cursor.fetchone():
        return

    password_hash = generate_password_hash(password)
    cursor.execute(
        """
        INSERT INTO users (username, password_hash, role, employee_id, is_active)
        VALUES (?, ?, 'admin', NULL, 1)
        """,
        ("admin", password_hash),
    )
    conn.commit()


def _migrate_comp_off_balances_if_needed(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(comp_off_balances)")
    columns = {row[1] for row in cursor.fetchall()}

    if not columns or 'remaining_minutes' in columns:
        return

    # Drop dependent views before renaming the table
    cursor.execute("DROP VIEW IF EXISTS v_employee_comp_off_balance")

    # Old schema detected: migrate data
    cursor.execute("ALTER TABLE comp_off_balances RENAME TO _old_comp_off_balances")

    comp_off_status_values = ', '.join([f"'{s}'" for s in COMP_OFF_STATUS])
    cursor.execute(f"""
        CREATE TABLE comp_off_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            source_overtime_id INTEGER,
            acquired_date DATE NOT NULL,
            expiry_date DATE,
            total_minutes INTEGER NOT NULL CHECK(total_minutes >= 0),
            remaining_minutes INTEGER NOT NULL CHECK(remaining_minutes >= 0),
            status TEXT DEFAULT 'active'
                CHECK(status IN ({comp_off_status_values})),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        )
    """)

    cursor.execute("""
        SELECT id, employee_id, acquired_date, expiry_date,
               total_hours, total_minutes, used_hours, used_minutes,
               status, created_at, updated_at
        FROM _old_comp_off_balances
    """)
    for row in cursor.fetchall():
        total_minutes = (row['total_hours'] or 0) * 60 + (row['total_minutes'] or 0)
        used_minutes = (row['used_hours'] or 0) * 60 + (row['used_minutes'] or 0)
        remaining = total_minutes - used_minutes
        if remaining < 0:
            remaining = 0
        cursor.execute("""
            INSERT INTO comp_off_balances
            (id, employee_id, acquired_date, expiry_date,
             total_minutes, remaining_minutes, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (row['id'], row['employee_id'], row['acquired_date'], row['expiry_date'],
              total_minutes, remaining, row['status'], row['created_at'], row['updated_at']))

    cursor.execute("DROP TABLE _old_comp_off_balances")
    conn.commit()
