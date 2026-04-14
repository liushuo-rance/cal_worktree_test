"""
CLI命令模块
提供导入、查询、报表、导出、员工管理（含软删除）等命令
"""

import csv
import json
import os
import re
import sqlite3
from datetime import date, datetime
from typing import Any, Dict, List, Optional


class CLIError(Exception):
    """CLI命令异常"""
    pass


def _get_db_path() -> str:
    """获取默认数据库路径"""
    return os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "overtime.db"
    )


def import_file(
    conn: sqlite3.Connection,
    file_path: str,
    employee_id: str,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    导入Markdown文件

    Args:
        conn: 数据库连接
        file_path: 文件路径
        employee_id: 员工ID
        verbose: 是否输出详细信息

    Returns:
        导入结果

    Raises:
        CLIError: 文件不存在或导入失败
    """
    if not os.path.exists(file_path):
        raise CLIError(f"文件不存在: {file_path}")

    from src.services.ai_parser_service import parse_with_ai, _normalize_overtime_type
    from src.services.parse_result_processor import process_parse_results
    from src.services.storage_service import _create_comp_off_balance

    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取有效行
    valid_lines: List[str] = []
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('#') or line.startswith('##'):
            continue
        if re.match(r'^(累计|余额|剩余)\s*[:：]', line):
            continue
        valid_lines.append(line)

    # 创建导入会话 (使用 v8 schema 的列名: file_path, processed_records, error_records)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO import_sessions
        (employee_id, file_path, total_records, processed_records, error_records)
        VALUES (?, ?, 0, 0, 0)
    """, (employee_id, os.path.basename(file_path)))
    session_id = cursor.lastrowid

    if not valid_lines:
        cursor.execute("""
            UPDATE import_sessions
            SET total_records = 0, processed_records = 0, error_records = 0
            WHERE id = ?
        """, (session_id,))
        conn.commit()
        return {
            'success': True,
            'import_session_id': session_id,
            'total_records': 0,
            'success_count': 0,
            'failed_count': 0,
            'file_path': file_path,
            'employee_id': employee_id
        }

    # AI解析
    ai_result = parse_with_ai(valid_lines)
    parsed_records = ai_result.get('records', [])
    parse_error = ai_result.get('error')

    if parse_error or not parsed_records:
        failed_count = len(valid_lines)
        cursor.execute("""
            UPDATE import_sessions
            SET total_records = ?, processed_records = 0, error_records = ?
            WHERE id = ?
        """, (len(valid_lines), failed_count, session_id))
        conn.commit()
        return {
            'success': True,
            'import_session_id': session_id,
            'total_records': len(valid_lines),
            'success_count': 0,
            'failed_count': failed_count,
            'file_path': file_path,
            'employee_id': employee_id,
            'parse_error': parse_error or 'AI未返回任何解析结果'
        }

    # 后处理解析结果
    processed_records = process_parse_results(parsed_records)

    success_count = 0
    failed_count = 0
    errors: List[str] = []

    try:
        for record in processed_records:
            record_type = record.get('type', 'unknown')
            record_date = record.get('parsed_date')
            hours = record.get('parsed_hours') or 0
            content = record.get('content', '')
            subtype = record.get('overtime_type') or record.get('leave_type') or ''

            if not record_date:
                failed_count += 1
                errors.append(f"缺少日期: {record.get('raw_line', '')}")
                continue

            # 转换时长
            duration_hours = int(hours)
            duration_minutes = int(round((hours - duration_hours) * 60))
            total_minutes = duration_hours * 60 + duration_minutes

            if record_type == 'overtime':
                overtime_type = _normalize_overtime_type(subtype or 'weekday_evening')
                cursor.execute("""
                    INSERT INTO overtime_records
                    (employee_id, work_date, duration_hours, duration_minutes,
                     total_minutes, overtime_type, description, raw_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (employee_id, record_date, duration_hours, duration_minutes,
                      total_minutes, overtime_type, content, content))

                if overtime_type == 'weekend':
                    _create_comp_off_balance(
                        conn, employee_id, record_date, total_minutes
                    )
                success_count += 1

            elif record_type == 'leave':
                leave_type = subtype or 'personal'
                cursor.execute("""
                    INSERT INTO leave_records
                    (employee_id, leave_date, duration_hours, duration_minutes,
                     total_minutes, leave_type, description, raw_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (employee_id, record_date, duration_hours, duration_minutes,
                      total_minutes, leave_type, content, content))
                success_count += 1

            elif record_type == 'comp_off':
                cursor.execute("""
                    INSERT INTO comp_off_usage_records
                    (employee_id, usage_date, duration_hours, duration_minutes,
                     total_minutes, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (employee_id, record_date, duration_hours, duration_minutes,
                      total_minutes, content))
                success_count += 1

            else:
                failed_count += 1
                errors.append(f"未知类型 '{record_type}': {record.get('raw_line', '')}")

        # 更新导入会话统计
        cursor.execute("""
            UPDATE import_sessions
            SET total_records = ?,
                processed_records = ?,
                error_records = ?
            WHERE id = ?
        """, (len(processed_records), success_count, failed_count, session_id))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise CLIError(f"导入失败: {str(e)}")

    return {
        'success': True,
        'import_session_id': session_id,
        'total_records': len(processed_records),
        'success_count': success_count,
        'failed_count': failed_count,
        'file_path': file_path,
        'employee_id': employee_id,
        'errors': errors[:10]
    }


def import_excel_csv(
    conn: sqlite3.Connection,
    file_path: str,
    employee_id: str,
    file_format: str = 'auto',
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    导入CSV/Excel文件

    Args:
        conn: 数据库连接
        file_path: 文件路径
        employee_id: 员工ID
        file_format: 文件格式 (auto/csv/xlsx)
        dry_run: 是否只预览不写入

    Returns:
        导入结果
    """
    from src.services.import_service import (
        read_csv_file,
        read_excel_file,
        normalize_import_rows
    )
    from src.services.storage_service import store_batch_records, StorageError

    if not os.path.exists(file_path):
        raise CLIError(f"文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if file_format == 'auto':
        if ext == '.csv':
            file_format = 'csv'
        elif ext in ('.xlsx', '.xls'):
            file_format = 'xlsx'
        else:
            raise CLIError(f"无法识别的文件格式: {ext}")

    if file_format == 'csv':
        raw_rows = read_csv_file(file_path)
    elif file_format == 'xlsx':
        raw_rows = read_excel_file(file_path)
    else:
        raise CLIError(f"不支持的文件格式: {file_format}")

    result = normalize_import_rows(raw_rows, employee_id=employee_id)
    normalized_records = result.get('records', [])
    errors = result.get('errors', [])

    # 将 normalize_import_rows 输出字段映射为 storage_service 期望的字段
    records = []
    for rec in normalized_records:
        mapped = {
            'type': rec.get('type'),
            'employee_id': rec.get('employee_id'),
            'date': rec.get('parsed_date'),
            'hours': rec.get('parsed_hours', 0),
            'overtime_type': rec.get('overtime_type'),
            'leave_type': rec.get('leave_type'),
            'description': rec.get('content', ''),
        }
        records.append(mapped)

    if dry_run:
        return {
            'success': True,
            'dry_run': True,
            'file_path': file_path,
            'employee_id': employee_id,
            'record_count': len(records),
            'error_count': len(errors),
            'records': records,
            'errors': errors
        }

    if errors:
        return {
            'success': False,
            'file_path': file_path,
            'employee_id': employee_id,
            'record_count': len(records),
            'error_count': len(errors),
            'errors': errors
        }

    try:
        store_result = store_batch_records(conn, records)
        return {
            'success': True,
            'file_path': file_path,
            'employee_id': employee_id,
            'record_count': len(records),
            'success_count': store_result.get('success_count', 0),
            'failed_count': store_result.get('failed_count', 0),
            'errors': errors
        }
    except StorageError as e:
        raise CLIError(f"批量存储失败: {e}") from e


def query_records(
    conn: sqlite3.Connection,
    employee_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """
    查询记录

    Args:
        conn: 数据库连接
        employee_id: 员工ID（可选）
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
        status: 状态筛选（可选）

    Returns:
        查询结果
    """
    cursor = conn.cursor()

    query = "SELECT * FROM overtime_records WHERE 1=1"
    params = []

    if employee_id:
        query += " AND employee_id = ?"
        params.append(employee_id)

    if start_date:
        query += " AND work_date >= ?"
        params.append(start_date.isoformat())

    if end_date:
        query += " AND work_date <= ?"
        params.append(end_date.isoformat())

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY work_date"

    cursor.execute(query, params)
    records = [dict(row) for row in cursor.fetchall()]

    return {
        'success': True,
        'records': records,
        'count': len(records)
    }


def generate_report(
    conn: sqlite3.Connection,
    employee_id: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    report_type: str = 'monthly'
) -> Dict[str, Any]:
    """
    生成报表

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        year: 年份
        month: 月份
        report_type: 报表类型 (monthly/comp_off/salary)

    Returns:
        报表结果
    """
    from src.services.report_service import (
        generate_monthly_report,
        generate_comp_off_report,
        generate_salary_report
    )

    if report_type == 'monthly':
        if year is None or month is None:
            now = date.today()
            year = year or now.year
            month = month or now.month
        report = generate_monthly_report(conn, employee_id, year, month)
    elif report_type == 'comp_off':
        report = generate_comp_off_report(conn, employee_id)
    elif report_type == 'salary':
        if year is None or month is None:
            now = date.today()
            year = year or now.year
            month = month or now.month
        report = generate_salary_report(conn, employee_id, year, month)
    else:
        raise CLIError(f"未知的报表类型: {report_type}")

    return {
        'success': True,
        'report_type': report_type,
        'report': report
    }


def export_data(
    conn: sqlite3.Connection,
    data_type: str,
    employee_id: str,
    format: str = 'csv',
    output_path: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None
) -> Dict[str, Any]:
    """
    导出数据

    Args:
        conn: 数据库连接
        data_type: 数据类型 (overtime/leave/comp_off/report_monthly/report_salary/report_comp_off)
        employee_id: 员工ID
        format: 导出格式 (csv/xlsx/pdf/json)
        output_path: 输出路径（可选，默认写入当前目录）
        year: 年份（报表类型需要）
        month: 月份（报表类型需要）

    Returns:
        导出结果

    Raises:
        CLIError: 格式不支持或导出失败
    """
    from src.services.export_service import (
        export_to_csv,
        export_to_excel,
        export_report_to_pdf,
        ExportError
    )
    from src.services.report_service import (
        generate_monthly_report,
        generate_comp_off_report,
        generate_salary_report,
        ReportError
    )

    format = format.lower()
    if format not in ('csv', 'xlsx', 'pdf', 'json'):
        raise CLIError(f"不支持的格式: {format}")

    cursor_emp = conn.cursor()
    cursor_emp.execute("SELECT name FROM employees WHERE employee_id = ?", (employee_id,))
    row_emp = cursor_emp.fetchone()
    employee_name = (row_emp['name'] if row_emp else '').replace('/', '').replace('\\', '').replace(':', '').replace('*', '').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '')

    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{employee_id}_{employee_name}_{data_type}_{timestamp}.{format}"

    # 原始数据导出
    if data_type in ('overtime', 'leave', 'comp_off'):
        cursor = conn.cursor()
        if data_type == 'overtime':
            cursor.execute(
                "SELECT * FROM overtime_records WHERE employee_id = ? ORDER BY work_date",
                (employee_id,)
            )
        elif data_type == 'leave':
            cursor.execute(
                "SELECT * FROM leave_records WHERE employee_id = ? ORDER BY leave_date",
                (employee_id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM comp_off_usage_records WHERE employee_id = ? ORDER BY usage_date",
                (employee_id,)
            )
        records = [dict(row) for row in cursor.fetchall()]

        if format == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=2, default=str, ensure_ascii=False)
        elif format == 'csv':
            if not records:
                csv_bytes = b''
            else:
                columns = [(k, k) for k in records[0].keys()]
                csv_bytes = export_to_csv(records, columns)
            output = b""
            output += f"员工: {employee_name} ({employee_id})\n\n".encode('utf-8-sig')
            output += csv_bytes or b''
            with open(output_path, 'wb') as f:
                f.write(output)
        elif format == 'xlsx':
            if not records:
                records = []
            columns = [(k, k) for k in (records[0].keys() if records else ['id'])]
            excel_bytes = export_to_excel({
                f"{employee_name}-{data_type}": {"columns": columns, "data": records}
            })
            with open(output_path, 'wb') as f:
                f.write(excel_bytes or b'')
        elif format == 'pdf':
            raise CLIError("原始记录暂不支持PDF导出，请使用报表类型")

        return {
            'success': True,
            'format': format,
            'output_path': output_path,
            'record_count': len(records)
        }

    # 报表导出
    if data_type == 'report_monthly':
        if year is None or month is None:
            raise CLIError("月度报表导出需要提供 year 和 month")
        try:
            report = generate_monthly_report(conn, employee_id, year, month)
        except ReportError as e:
            raise CLIError(f"生成月度报表失败: {e}") from e

        columns = [
            ("date", "日期"),
            ("weekday", "星期"),
            ("type", "类型"),
            ("hours", "时长(小时)"),
            ("description", "说明"),
        ]
        ot_data = []
        for row in report.get("overtime_details", []):
            ot_data.append({
                "date": row.get("date", ""),
                "weekday": row.get("weekday", ""),
                "type": row.get("type", ""),
                "hours": row.get("hours", 0),
                "description": row.get("description", ""),
            })
        leave_data = []
        for row in report.get("leave_details", []):
            leave_data.append({
                "date": row.get("date", ""),
                "weekday": row.get("weekday", ""),
                "type": row.get("type", ""),
                "hours": row.get("hours", 0),
                "description": "",
            })

        if format == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str, ensure_ascii=False)
        elif format == 'csv':
            csv_content = b""
            csv_content += f"员工: {employee_name} ({employee_id})\n\n".encode('utf-8-sig')
            csv_content += b"\n\xe5\x8a\xa0\xe7\x8f\xad\xe6\x98\x8e\xe7\xbb\x86\n"
            csv_content += export_to_csv(ot_data, columns) or b""
            csv_content += b"\n\xe8\xaf\xb7\xe5\x81\xbf\xe6\x98\x8e\xe7\xbb\x86\n"
            csv_content += export_to_csv(leave_data, columns) or b""
            with open(output_path, 'wb') as f:
                f.write(csv_content)
        elif format == 'xlsx':
            excel_bytes = export_to_excel({
                "加班明细": {"columns": columns, "data": ot_data},
                "请假明细": {"columns": columns, "data": leave_data},
            })
            with open(output_path, 'wb') as f:
                f.write(excel_bytes or b'')
        elif format == 'pdf':
            pdf_bytes = export_report_to_pdf(report, 'monthly')
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes or b'')

    elif data_type == 'report_salary':
        if year is None or month is None:
            raise CLIError("工资报表导出需要提供 year 和 month")
        try:
            report = generate_salary_report(conn, employee_id, year, month)
        except ReportError as e:
            raise CLIError(f"生成工资报表失败: {e}") from e

        columns = [
            ("item", "项目"),
            ("hours", "加班时长(小时)"),
            ("multiplier", "倍数"),
            ("amount", "金额(元)"),
        ]
        data = [
            {
                "item": "工作日加班",
                "hours": report["weekday_overtime"]["hours"],
                "multiplier": report["weekday_overtime"]["multiplier"],
                "amount": report["weekday_overtime"]["amount"],
            },
            {
                "item": "周末加班",
                "hours": report["weekend_overtime"]["hours"],
                "multiplier": report["weekend_overtime"]["multiplier"],
                "amount": report["weekend_overtime"]["amount"],
            },
            {
                "item": "节假日加班",
                "hours": report["holiday_overtime"]["hours"],
                "multiplier": report["holiday_overtime"]["multiplier"],
                "amount": report["holiday_overtime"]["amount"],
            },
            {
                "item": "合计",
                "hours": "",
                "multiplier": "",
                "amount": report["total_amount"],
            },
        ]

        if format == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str, ensure_ascii=False)
        elif format == 'csv':
            csv_bytes = export_to_csv(data, columns)
            output = b""
            output += f"员工: {employee_name} ({employee_id})\n\n".encode('utf-8-sig')
            output += csv_bytes or b''
            with open(output_path, 'wb') as f:
                f.write(output)
        elif format == 'xlsx':
            excel_bytes = export_to_excel({
                "工资计算": {"columns": columns, "data": data}
            })
            with open(output_path, 'wb') as f:
                f.write(excel_bytes or b'')
        elif format == 'pdf':
            pdf_bytes = export_report_to_pdf(report, 'salary')
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes or b'')

    elif data_type == 'report_comp_off':
        try:
            report = generate_comp_off_report(conn, employee_id)
        except ReportError as e:
            raise CLIError(f"生成调休报表失败: {e}") from e

        columns = [
            ("acquired_date", "获得日期"),
            ("hours", "剩余时长(小时)"),
            ("expiry_date", "到期日期"),
            ("status", "状态"),
        ]
        data = []
        for row in report.get("balance_items", []):
            data.append({
                "acquired_date": row.get("acquired_date", ""),
                "hours": row.get("hours", 0),
                "expiry_date": row.get("expiry_date") or "-",
                "status": row.get("status", ""),
            })

        if format == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str, ensure_ascii=False)
        elif format == 'csv':
            csv_bytes = export_to_csv(data, columns)
            output = b""
            output += f"员工: {employee_name} ({employee_id})\n\n".encode('utf-8-sig')
            output += csv_bytes or b''
            with open(output_path, 'wb') as f:
                f.write(output)
        elif format == 'xlsx':
            excel_bytes = export_to_excel({
                "调休余额": {"columns": columns, "data": data}
            })
            with open(output_path, 'wb') as f:
                f.write(excel_bytes or b'')
        elif format == 'pdf':
            pdf_bytes = export_report_to_pdf(report, 'comp_off')
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes or b'')
    else:
        raise CLIError(f"不支持的导出数据类型: {data_type}")

    return {
        'success': True,
        'data_type': data_type,
        'format': format,
        'output_path': output_path
    }


def calculate_salary(
    conn: sqlite3.Connection,
    employee_id: str,
    year: int,
    month: int
) -> Dict[str, Any]:
    """
    计算工资

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        year: 年份
        month: 月份

    Returns:
        工资计算结果
    """
    from src.services.report_service import generate_salary_report

    report = generate_salary_report(conn, employee_id, year, month)

    return {
        'success': True,
        'salary_report': report
    }


def list_holidays(
    conn: sqlite3.Connection,
    year: int
) -> Dict[str, Any]:
    """
    列出节假日

    Args:
        conn: 数据库连接
        year: 年份

    Returns:
        节假日列表
    """
    # 查询节假日数据
    cursor = conn.cursor()

    # 检查是否存在holiday_config表
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='holiday_config'
    """)

    if cursor.fetchone():
        cursor.execute("""
            SELECT * FROM holiday_config
            WHERE strftime('%Y', holiday_date) = ?
            ORDER BY holiday_date
        """, (str(year),))
        holidays = [dict(row) for row in cursor.fetchall()]
    else:
        holidays = []

    return {
        'success': True,
        'year': year,
        'holidays': holidays,
        'count': len(holidays)
    }


def check_holiday_config(
    conn: sqlite3.Connection,
    month: str
) -> Dict[str, Any]:
    """
    检查节假日配置

    Args:
        conn: 数据库连接
        month: 月份 (YYYY-MM格式)

    Returns:
        检查结果
    """
    # 解析年月
    try:
        year, mon = month.split('-')
    except ValueError:
        raise CLIError(f"月份格式错误: {month}, 应为 YYYY-MM")

    cursor = conn.cursor()

    # 检查是否存在holiday_config表
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='holiday_config'
    """)

    has_config = cursor.fetchone() is not None

    return {
        'success': True,
        'month': month,
        'has_holiday_config': has_config,
        'check_result': {
            'config_exists': has_config,
            'year': int(year),
            'month': int(mon)
        }
    }


def query_comp_off(
    conn: sqlite3.Connection,
    employee_id: str
) -> Dict[str, Any]:
    """
    查询调休余额

    Args:
        conn: 数据库连接
        employee_id: 员工ID

    Returns:
        调休余额信息
    """
    from src.services.report_service import generate_comp_off_report

    report = generate_comp_off_report(conn, employee_id)

    return {
        'success': True,
        'balance': report
    }


def mark_expired_comp_off(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    标记已过期的调休

    Args:
        conn: 数据库连接

    Returns:
        操作结果
    """
    cursor = conn.cursor()

    # 检查是否存在comp_off_balances表
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='comp_off_balances'
    """)

    if not cursor.fetchone():
        return {
            'success': True,
            'marked_count': 0
        }

    # 标记已过期的调休
    today = date.today().isoformat()
    cursor.execute("""
        UPDATE comp_off_balances
        SET status = 'expired'
        WHERE expiry_date < ?
          AND status = 'active'
    """, (today,))

    marked_count = cursor.rowcount
    conn.commit()

    return {
        'success': True,
        'marked_count': marked_count
    }


def notify_comp_off_expiry(
    conn: sqlite3.Connection,
    threshold: int = 30,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    发送调休到期提醒通知

    Args:
        conn: 数据库连接
        threshold: 到期天数阈值
        dry_run: 是否只预览不发送

    Returns:
        发送结果
    """
    from src.services.notification_service import send_comp_off_expiry_notification
    from src.services.email_service import build_email_config

    email_config = build_email_config()

    if not email_config['is_configured']:
        raise CLIError("SMTP 或 HR 通知邮箱未配置，请检查环境变量")

    if dry_run:
        from src.services.comp_off_service import get_expiring_balances
        balances = get_expiring_balances(conn, days_threshold=threshold)
        return {
            'success': True,
            'dry_run': True,
            'threshold': threshold,
            'recipient_count': len(email_config['hr_emails']),
            'recipients': email_config['hr_emails'],
            'balances_found': len(balances)
        }

    result = send_comp_off_expiry_notification(
        conn,
        recipient_emails=email_config['hr_emails'],
        days_threshold=threshold,
        trigger_mode='manual'
    )

    return {
        'success': result['success'],
        'sent_count': result['sent_count'],
        'failed_count': result['failed_count'],
        'balances_found': result['balances_found']
    }


# ---------------------------------------------------------------------------
# v5 新增 CLI 函数
# ---------------------------------------------------------------------------

def list_employees(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    列出所有员工

    Args:
        conn: 数据库连接

    Returns:
        员工列表
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees ORDER BY name")
    employees = [dict(row) for row in cursor.fetchall()]

    return {
        'success': True,
        'employees': employees,
        'count': len(employees)
    }


def create_employee(
    conn: sqlite3.Connection,
    employee_id: str,
    name: str,
    department: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建新员工

    Args:
        conn: 数据库连接
        employee_id: 员工ID
        name: 姓名
        department: 部门

    Returns:
        创建结果
    """
    if not employee_id:
        raise CLIError("员工ID不能为空")
    if not name:
        raise CLIError("姓名不能为空")

    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO employees (employee_id, name, department)
            VALUES (?, ?, ?)
        """, (employee_id, name, department))
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise CLIError(f"员工ID {employee_id} 已存在") from e
    except sqlite3.Error as e:
        conn.rollback()
        raise CLIError(f"创建员工失败: {str(e)}") from e

    return {
        'success': True,
        'employee_id': employee_id,
        'name': name,
        'department': department
    }


def get_employee(conn: sqlite3.Connection, employee_id: str) -> Dict[str, Any]:
    """
    获取员工详情

    Args:
        conn: 数据库连接
        employee_id: 员工ID

    Returns:
        员工详情及最近记录
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,))
    row = cursor.fetchone()

    if not row:
        raise CLIError(f"员工不存在: {employee_id}")

    employee = dict(row)

    cursor.execute("""
        SELECT * FROM overtime_records
        WHERE employee_id = ?
        ORDER BY work_date DESC
        LIMIT 10
    """, (employee_id,))
    overtime_records = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT * FROM leave_records
        WHERE employee_id = ?
        ORDER BY leave_date DESC
        LIMIT 10
    """, (employee_id,))
    leave_records = [dict(r) for r in cursor.fetchall()]

    return {
        'success': True,
        'employee': employee,
        'overtime_records': overtime_records,
        'leave_records': leave_records
    }


def list_reviews(
    conn: sqlite3.Connection,
    status: str = 'pending'
) -> Dict[str, Any]:
    """
    列出审批队列

    Args:
        conn: 数据库连接
        status: 状态过滤 (pending/approved/rejected/all)

    Returns:
        审批列表
    """
    cursor = conn.cursor()

    query = """
        SELECT rq.*, isess.file_path
        FROM review_queue rq
        JOIN import_sessions isess ON rq.import_session_id = isess.id
    """
    params = []

    if status != 'all':
        query += " WHERE rq.status = ?"
        params.append(status)

    query += " ORDER BY rq.created_at"

    cursor.execute(query, params)
    reviews = [dict(row) for row in cursor.fetchall()]

    return {
        'success': True,
        'reviews': reviews,
        'count': len(reviews),
        'status': status
    }


def approve_review_item(
    conn: sqlite3.Connection,
    review_id: int,
    reviewer_note: Optional[str] = None
) -> Dict[str, Any]:
    """
    批准审批项

    Args:
        conn: 数据库连接
        review_id: 审批项ID
        reviewer_note: 审批备注

    Returns:
        操作结果
    """
    from src.services.review_service import approve_review, ReviewServiceError

    try:
        approve_review(conn, review_id, reviewer_note=reviewer_note or '')
    except ReviewServiceError as e:
        raise CLIError(str(e)) from e

    return {
        'success': True,
        'review_id': review_id,
        'action': 'approved'
    }


def reject_review_item(
    conn: sqlite3.Connection,
    review_id: int,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    拒绝审批项

    Args:
        conn: 数据库连接
        review_id: 审批项ID
        reason: 拒绝原因

    Returns:
        操作结果
    """
    from src.services.review_service import reject_review, ReviewServiceError

    try:
        reject_review(conn, review_id, reason=reason or '')
    except ReviewServiceError as e:
        raise CLIError(str(e)) from e

    return {
        'success': True,
        'review_id': review_id,
        'action': 'rejected'
    }


def import_holidays_from_text(
    conn: sqlite3.Connection,
    text: str,
    year: Optional[int] = None
) -> Dict[str, Any]:
    """
    从节假日通知文本导入节假日

    Args:
        conn: 数据库连接
        text: 通知文本
        year: 年份（可选，用于 fallback）

    Returns:
        导入结果
    """
    from src.parsers.holiday_notification_parser import parse_notification
    from datetime import datetime

    if not text.strip():
        raise CLIError("节假日文本不能为空")

    try:
        parsed_holidays = parse_notification(text)
    except Exception as e:
        raise CLIError(f"解析节假日文本失败: {str(e)}") from e

    if not parsed_holidays:
        raise CLIError("未能从文本中解析出节假日信息")

    cursor = conn.cursor()
    success_count = 0
    error_count = 0

    try:
        for holiday in parsed_holidays:
            try:
                name = holiday['name']
                holiday_year = holiday['start_date'].year
                start_date = holiday['start_date']
                end_date = holiday['end_date']
                statutory_days = holiday.get('statutory_days', [])
                adjusted_workdays = holiday.get('adjusted_workdays', [])

                # 删除同一年该节假日的旧数据
                cursor.execute("""
                    DELETE FROM holiday_config
                    WHERE holiday_name = ? AND year = ?
                """, (name, holiday_year))

                # 插入假期每一天
                current_date = start_date
                while current_date <= end_date:
                    if current_date in statutory_days:
                        holiday_type = 'statutory'
                    else:
                        holiday_type = 'adjusted_holiday'

                    cursor.execute("""
                        INSERT INTO holiday_config (holiday_date, holiday_name, holiday_type, year)
                        VALUES (?, ?, ?, ?)
                    """, (current_date, name, holiday_type, holiday_year))
                    success_count += 1
                    current_date = datetime.fromordinal(current_date.toordinal() + 1).date()

                # 插入调休上班日
                for workday in adjusted_workdays:
                    cursor.execute("""
                        INSERT INTO holiday_config (holiday_date, holiday_name, holiday_type, year)
                        VALUES (?, ?, ?, ?)
                    """, (workday, f"{name}调休", 'adjusted_workday', holiday_year))
                    success_count += 1

            except Exception:
                error_count += 1

        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise CLIError(f"数据库操作失败: {str(e)}") from e

    return {
        'success': True,
        'success_count': success_count,
        'error_count': error_count,
        'parsed_holidays': len(parsed_holidays)
    }


def delete_holiday(conn: sqlite3.Connection, holiday_date: str) -> Dict[str, Any]:
    """
    删除指定日期的节假日

    Args:
        conn: 数据库连接
        holiday_date: 日期 (YYYY-MM-DD)

    Returns:
        删除结果
    """
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM holiday_config WHERE holiday_date = ?",
        (holiday_date,)
    )
    conn.commit()

    return {
        'success': True,
        'deleted_count': cursor.rowcount,
        'holiday_date': holiday_date
    }


def delete_year_holidays(conn: sqlite3.Connection, year: int) -> Dict[str, Any]:
    """
    删除指定年份的所有节假日

    Args:
        conn: 数据库连接
        year: 年份

    Returns:
        删除结果
    """
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM holiday_config WHERE year = ?",
        (year,)
    )
    conn.commit()
    deleted_count = cursor.rowcount

    return {
        'success': True,
        'deleted_count': deleted_count,
        'year': year
    }


def delete_overtime_record_cli(conn: sqlite3.Connection, record_id: int) -> Dict[str, Any]:
    """
    删除指定的加班记录

    Args:
        conn: 数据库连接
        record_id: 记录ID

    Returns:
        删除结果
    """
    from src.services.overtime_service import delete_overtime_record

    try:
        delete_overtime_record(conn, record_id)
    except Exception as e:
        raise CLIError(f"删除失败: {str(e)}") from e

    return {
        'success': True,
        'record_id': record_id
    }


def delete_employee(
    conn: sqlite3.Connection,
    employee_id: str
) -> Dict[str, Any]:
    """
    删除员工（软删除）

    Args:
        conn: 数据库连接
        employee_id: 员工ID

    Returns:
        删除结果

    Raises:
        CLIError: 员工不存在或删除失败
    """
    from src.services.storage_service import delete_employee_service, StorageError

    try:
        result = delete_employee_service(conn, employee_id)
    except StorageError as e:
        raise CLIError(str(e)) from e

    return {
        'success': True,
        'employee_id': employee_id,
        'affected_records': result.get('affected_records', 0)
    }


def get_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    获取系统统计信息

    Args:
        conn: 数据库连接

    Returns:
        统计信息
    """
    cursor = conn.cursor()

    def _count(table: str, where: str = '') -> int:
        # 检查表是否存在
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        if not cursor.fetchone():
            return 0
        sql = f"SELECT COUNT(*) as count FROM {table}"
        if where:
            sql += f" WHERE {where}"
        cursor.execute(sql)
        row = cursor.fetchone()
        return row['count'] if row else 0

    stats = {
        'total_employees': _count('employees'),
        'total_overtime_records': _count('overtime_records'),
        'total_leave_records': _count('leave_records'),
        'pending_reviews': _count('review_queue', "status = 'pending'"),
    }

    return {
        'success': True,
        'stats': stats
    }


# ---------------------------------------------------------------------------
# CLI入口（可直接运行）
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='加班记录管理系统 CLI')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # import_excel_csv
    import_parser = subparsers.add_parser('import_excel_csv', help='导入CSV/Excel文件')
    import_parser.add_argument('file_path', help='文件路径')
    import_parser.add_argument('employee_id', help='员工ID')
    import_parser.add_argument('--format', default='auto', choices=['auto', 'csv', 'xlsx'],
                               help='文件格式')
    import_parser.add_argument('--dry-run', action='store_true', help='仅预览不写入')
    import_parser.add_argument('--db', default=None, help='数据库路径')

    # export
    export_parser = subparsers.add_parser('export', help='导出数据或报表')
    export_parser.add_argument('data_type',
                               choices=['overtime', 'leave', 'comp_off',
                                        'report_monthly', 'report_salary', 'report_comp_off'],
                               help='数据类型')
    export_parser.add_argument('employee_id', help='员工ID')
    export_parser.add_argument('--format', default='csv', choices=['csv', 'xlsx', 'pdf', 'json'],
                               help='导出格式')
    export_parser.add_argument('--output', default=None, help='输出路径')
    export_parser.add_argument('--year', type=int, default=None, help='年份')
    export_parser.add_argument('--month', type=int, default=None, help='月份')
    export_parser.add_argument('--db', default=None, help='数据库路径')

    # report
    report_parser = subparsers.add_parser('report', help='生成报表')
    report_parser.add_argument('employee_id', help='员工ID')
    report_parser.add_argument('--type', default='monthly', choices=['monthly', 'salary', 'comp_off'],
                               help='报表类型')
    report_parser.add_argument('--year', type=int, default=None, help='年份')
    report_parser.add_argument('--month', type=int, default=None, help='月份')
    report_parser.add_argument('--db', default=None, help='数据库路径')

    # notify
    notify_parser = subparsers.add_parser('notify', help='发送调休到期提醒')
    notify_parser.add_argument('--threshold', type=int, default=30, help='到期天数阈值')
    notify_parser.add_argument('--dry-run', action='store_true', help='仅预览不发送')
    notify_parser.add_argument('--db', default=None, help='数据库路径')

    # delete_employee
    delete_emp_parser = subparsers.add_parser('delete_employee', help='删除员工（软删除）')
    delete_emp_parser.add_argument('employee_id', help='员工ID')
    delete_emp_parser.add_argument('--db', default=None, help='数据库路径')

    args = parser.parse_args()

    db_path = args.db or _get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        if args.command == 'import_excel_csv':
            result = import_excel_csv(
                conn, args.file_path, args.employee_id,
                file_format=args.format, dry_run=args.dry_run
            )
            print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
        elif args.command == 'export':
            result = export_data(
                conn, args.data_type, args.employee_id,
                format=args.format, output_path=args.output,
                year=args.year, month=args.month
            )
            print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
        elif args.command == 'report':
            result = generate_report(
                conn, args.employee_id,
                report_type=args.type, year=args.year, month=args.month
            )
            print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
        elif args.command == 'notify':
            result = notify_comp_off_expiry(
                conn, threshold=args.threshold, dry_run=args.dry_run
            )
            print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
        elif args.command == 'delete_employee':
            result = delete_employee(conn, args.employee_id)
            print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
        else:
            parser.print_help()
    except CLIError as e:
        print(f"错误: {e}")
    finally:
        conn.close()
