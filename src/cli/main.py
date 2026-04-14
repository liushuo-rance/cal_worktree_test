"""
CLI 命令行入口
支持通过 argparse 直接运行 src/cli/commands.py
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import date
from typing import Any, Dict, List, Optional

# 确保项目根目录在路径中
try:
    from src.cli.commands import (
        CLIError,
        import_file,
        import_excel_csv,
        query_records,
        generate_report,
        export_data,
        calculate_salary,
        list_holidays,
        check_holiday_config,
        query_comp_off,
        mark_expired_comp_off,
        notify_comp_off_expiry,
        list_employees,
        create_employee,
        get_employee,
        list_reviews,
        approve_review_item,
        reject_review_item,
        import_holidays_from_text,
        delete_holiday,
        delete_year_holidays,
        delete_overtime_record_cli,
        delete_employee,
        get_stats,
    )
except ImportError:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from src.cli.commands import (
        CLIError,
        import_file,
        import_excel_csv,
        query_records,
        generate_report,
        export_data,
        calculate_salary,
        list_holidays,
        check_holiday_config,
        query_comp_off,
        mark_expired_comp_off,
        notify_comp_off_expiry,
        list_employees,
        create_employee,
        get_employee,
        list_reviews,
        approve_review_item,
        reject_review_item,
        import_holidays_from_text,
        delete_holiday,
        delete_year_holidays,
        delete_overtime_record_cli,
        delete_employee,
        get_stats,
    )


def _get_db_connection(db_path: str) -> sqlite3.Connection:
    """获取数据库连接"""
    os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _output_result(result: Dict[str, Any], fmt: str) -> None:
    """输出结果"""
    if fmt == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        # table 格式：简单键值对
        def _print_dict(d: Dict[str, Any], indent: int = 0) -> None:
            prefix = "  " * indent
            for k, v in d.items():
                if isinstance(v, dict):
                    print(f"{prefix}{k}:")
                    _print_dict(v, indent + 1)
                elif isinstance(v, list):
                    print(f"{prefix}{k}: [{len(v)} items]")
                    for i, item in enumerate(v):
                        if isinstance(item, dict):
                            print(f"{prefix}  [{i}]:")
                            _print_dict(item, indent + 2)
                        else:
                            print(f"{prefix}  [{i}]: {item}")
                else:
                    print(f"{prefix}{k}: {v}")
        _print_dict(result)


def _parse_date_maybe(s: Optional[str]) -> Optional[date]:
    """解析日期字符串为 date 对象"""
    if not s:
        return None
    from datetime import datetime
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError as exc:
        raise CLIError(f"日期格式错误: {s}，应为 YYYY-MM-DD") from exc


def _cmd_import(args: argparse.Namespace) -> int:
    """导入命令"""
    file_path = args.file
    if file_path == '-':
        content = sys.stdin.read()
        if not content:
            print("错误: 标准输入为空", file=sys.stderr)
            return 1
        # 写入临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            file_path = f.name
        try:
            conn = _get_db_connection(args.db)
            try:
                result = import_file(conn, file_path, args.employee)
                _output_result(result, args.format)
                return 0
            finally:
                conn.close()
        finally:
            os.unlink(file_path)
    else:
        conn = _get_db_connection(args.db)
        try:
            result = import_file(conn, file_path, args.employee)
            _output_result(result, args.format)
            return 0
        finally:
            conn.close()


def _cmd_import_excel_csv(args: argparse.Namespace) -> int:
    """导入CSV/Excel命令"""
    conn = _get_db_connection(args.db)
    try:
        result = import_excel_csv(
            conn,
            args.file_path,
            args.employee_id,
            file_format=args.file_format,
            dry_run=args.dry_run
        )
        _output_result(result, args.format_out)
        return 0
    finally:
        conn.close()


def _cmd_query(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        start = _parse_date_maybe(args.start_date)
        end = _parse_date_maybe(args.end_date)
        result = query_records(conn, employee_id=args.employee, start_date=start, end_date=end)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_report(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = generate_report(
            conn,
            employee_id=args.employee,
            year=args.year,
            month=args.month,
            report_type=args.type
        )
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_export(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = export_data(
            conn,
            data_type=args.data_type,
            employee_id=args.employee,
            format=args.format_out or 'csv',
            output_path=args.output,
            year=args.year,
            month=args.month
        )
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_salary(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = calculate_salary(conn, args.employee, args.year, args.month)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_holidays(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = list_holidays(conn, year=args.year)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_check_holiday(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = check_holiday_config(conn, month=args.month)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_comp_off(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = query_comp_off(conn, args.employee)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_mark_expired(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = mark_expired_comp_off(conn)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_notify(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = notify_comp_off_expiry(conn, threshold=args.threshold, dry_run=args.dry_run)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_employee_list(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = list_employees(conn)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_employee_create(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = create_employee(conn, args.id, args.name, args.department)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_employee_get(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = get_employee(conn, args.employee_id)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_review_list(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = list_reviews(conn, status=args.status)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_review_approve(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = approve_review_item(conn, args.id, args.note)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_review_reject(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = reject_review_item(conn, args.id, args.reason)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_holiday_import(args: argparse.Namespace) -> int:
    text = args.text if args.text else sys.stdin.read()
    if not text.strip():
        print("错误: 请输入节假日文本（通过 --text 或标准输入）", file=sys.stderr)
        return 1
    conn = _get_db_connection(args.db)
    try:
        year = args.year
        result = import_holidays_from_text(conn, text, year=year)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_holiday_delete(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = delete_holiday(conn, args.date)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_holiday_delete_year(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = delete_year_holidays(conn, args.year)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_overtime_delete(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = delete_overtime_record_cli(conn, args.id)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_delete_employee(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = delete_employee(conn, args.employee_id)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _cmd_stats(args: argparse.Namespace) -> int:
    conn = _get_db_connection(args.db)
    try:
        result = get_stats(conn)
        _output_result(result, args.format)
        return 0
    finally:
        conn.close()


def _add_global_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--db', default='data/overtime.db', help='SQLite 数据库路径 (默认: data/overtime.db)')
    parser.add_argument('--format', choices=('json', 'table'), default='json', help='输出格式 (默认: json)')


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        prog='ot-cli',
        description='加班记录分析系统 CLI'
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # import
    p_import = subparsers.add_parser('import', help='导入 Markdown 文件')
    _add_global_args(p_import)
    p_import.add_argument('--file', required=True, help='文件路径，使用 "-" 从标准输入读取')
    p_import.add_argument('--employee', required=True, help='员工ID')

    # import-excel-csv
    p_import_excel = subparsers.add_parser('import-excel-csv', help='导入 CSV/Excel 文件')
    _add_global_args(p_import_excel)
    p_import_excel.add_argument('file_path', help='文件路径')
    p_import_excel.add_argument('employee_id', help='员工ID')
    p_import_excel.add_argument('--file-format', default='auto', choices=['auto', 'csv', 'xlsx'],
                                help='文件格式')
    p_import_excel.add_argument('--dry-run', action='store_true', help='仅预览不写入')

    # query
    p_query = subparsers.add_parser('query', help='查询加班记录')
    _add_global_args(p_query)
    p_query.add_argument('--employee', help='员工ID')
    p_query.add_argument('--start-date', help='开始日期 YYYY-MM-DD')
    p_query.add_argument('--end-date', help='结束日期 YYYY-MM-DD')

    # report
    p_report = subparsers.add_parser('report', help='生成报表')
    _add_global_args(p_report)
    p_report.add_argument('--employee', required=True, help='员工ID')
    p_report.add_argument('--type', choices=('monthly', 'comp_off', 'salary'), default='monthly', help='报表类型')
    p_report.add_argument('--year', type=int, help='年份')
    p_report.add_argument('--month', type=int, help='月份')

    # export
    p_export = subparsers.add_parser('export', help='导出数据或报表')
    _add_global_args(p_export)
    p_export.add_argument('data_type',
                          choices=['overtime', 'leave', 'comp_off',
                                   'report_monthly', 'report_salary', 'report_comp_off'],
                          help='数据类型')
    p_export.add_argument('--employee', required=True, help='员工ID')
    p_export.add_argument('--format-out', default='csv', choices=['csv', 'xlsx', 'pdf', 'json'],
                          help='导出格式')
    p_export.add_argument('--output', help='输出文件路径')
    p_export.add_argument('--year', type=int, help='年份')
    p_export.add_argument('--month', type=int, help='月份')

    # salary
    p_salary = subparsers.add_parser('salary', help='计算工资')
    _add_global_args(p_salary)
    p_salary.add_argument('--employee', required=True, help='员工ID')
    p_salary.add_argument('--year', required=True, type=int, help='年份')
    p_salary.add_argument('--month', required=True, type=int, help='月份')

    # holidays
    p_holidays = subparsers.add_parser('holidays', help='列出节假日')
    _add_global_args(p_holidays)
    p_holidays.add_argument('--year', required=True, type=int, help='年份')

    # check-holiday
    p_check = subparsers.add_parser('check-holiday', help='检查节假日配置')
    _add_global_args(p_check)
    p_check.add_argument('--month', required=True, help='月份 YYYY-MM')

    # comp-off
    p_comp = subparsers.add_parser('comp-off', help='查询调休余额')
    _add_global_args(p_comp)
    p_comp.add_argument('--employee', required=True, help='员工ID')

    # mark-expired-comp-off
    p_mark = subparsers.add_parser('mark-expired-comp-off', help='标记过期调休')
    _add_global_args(p_mark)

    # notify
    p_notify = subparsers.add_parser('notify', help='发送调休到期提醒')
    _add_global_args(p_notify)
    p_notify.add_argument('--threshold', type=int, default=30, help='到期天数阈值')
    p_notify.add_argument('--dry-run', action='store_true', help='仅预览不发送')

    # employee
    p_emp = subparsers.add_parser('employee', help='员工管理')
    emp_sub = p_emp.add_subparsers(dest='emp_command', required=True)

    p_emp_list = emp_sub.add_parser('list', help='列出员工')
    _add_global_args(p_emp_list)

    p_emp_create = emp_sub.add_parser('create', help='创建员工')
    _add_global_args(p_emp_create)
    p_emp_create.add_argument('--id', required=True, help='员工ID')
    p_emp_create.add_argument('--name', required=True, help='姓名')
    p_emp_create.add_argument('--department', help='部门')

    p_emp_get = emp_sub.add_parser('get', help='查看员工详情')
    _add_global_args(p_emp_get)
    p_emp_get.add_argument('employee_id', help='员工ID')

    # review
    p_rev = subparsers.add_parser('review', help='审批队列管理')
    rev_sub = p_rev.add_subparsers(dest='rev_command', required=True)

    p_rev_list = rev_sub.add_parser('list', help='列出审批项')
    _add_global_args(p_rev_list)
    p_rev_list.add_argument('--status', default='pending', choices=('pending', 'approved', 'rejected', 'all'), help='状态过滤')

    p_rev_approve = rev_sub.add_parser('approve', help='批准审批项')
    _add_global_args(p_rev_approve)
    p_rev_approve.add_argument('--id', required=True, type=int, help='审批项ID')
    p_rev_approve.add_argument('--note', help='审批备注')

    p_rev_reject = rev_sub.add_parser('reject', help='拒绝审批项')
    _add_global_args(p_rev_reject)
    p_rev_reject.add_argument('--id', required=True, type=int, help='审批项ID')
    p_rev_reject.add_argument('--reason', help='拒绝原因')

    # holiday-import
    p_hi = subparsers.add_parser('holiday-import', help='从文本导入节假日')
    _add_global_args(p_hi)
    p_hi.add_argument('--year', type=int, help='年份（可选）')
    p_hi.add_argument('--text', help='节假日文本（若不提供则从标准输入读取）')

    # holiday-delete
    p_hd = subparsers.add_parser('holiday-delete', help='删除指定日期节假日')
    _add_global_args(p_hd)
    p_hd.add_argument('--date', required=True, help='日期 YYYY-MM-DD')

    # holiday-delete-year
    p_hdy = subparsers.add_parser('holiday-delete-year', help='删除整年节假日')
    _add_global_args(p_hdy)
    p_hdy.add_argument('--year', required=True, type=int, help='年份')

    # overtime-delete
    p_od = subparsers.add_parser('overtime-delete', help='删除加班记录')
    _add_global_args(p_od)
    p_od.add_argument('--id', required=True, type=int, help='记录ID')

    # delete-employee
    p_de = subparsers.add_parser('delete_employee', help='删除员工（软删除）')
    _add_global_args(p_de)
    p_de.add_argument('employee_id', help='员工ID')

    # stats
    p_stats = subparsers.add_parser('stats', help='系统统计')
    _add_global_args(p_stats)

    args = parser.parse_args(argv)

    handlers = {
        'import': _cmd_import,
        'import-excel-csv': _cmd_import_excel_csv,
        'query': _cmd_query,
        'report': _cmd_report,
        'export': _cmd_export,
        'salary': _cmd_salary,
        'holidays': _cmd_holidays,
        'check-holiday': _cmd_check_holiday,
        'comp-off': _cmd_comp_off,
        'mark-expired-comp-off': _cmd_mark_expired,
        'notify': _cmd_notify,
        'holiday-import': _cmd_holiday_import,
        'holiday-delete': _cmd_holiday_delete,
        'holiday-delete-year': _cmd_holiday_delete_year,
        'overtime-delete': _cmd_overtime_delete,
        'delete_employee': _cmd_delete_employee,
        'stats': _cmd_stats,
    }

    # employee 子命令
    if args.command == 'employee':
        emp_handlers = {
            'list': _cmd_employee_list,
            'create': _cmd_employee_create,
            'get': _cmd_employee_get,
        }
        handler = emp_handlers.get(args.emp_command)
    elif args.command == 'review':
        rev_handlers = {
            'list': _cmd_review_list,
            'approve': _cmd_review_approve,
            'reject': _cmd_review_reject,
        }
        handler = rev_handlers.get(args.rev_command)
    else:
        handler = handlers.get(args.command)

    if handler is None:
        print(f"未知命令: {args.command}", file=sys.stderr)
        return 1

    try:
        return handler(args)
    except CLIError as e:
        result = {'success': False, 'error': str(e)}
        _output_result(result, args.format)
        return 1
    except Exception as e:
        result = {'success': False, 'error': f"内部错误: {str(e)}"}
        _output_result(result, args.format)
        return 1


if __name__ == '__main__':
    sys.exit(main())
