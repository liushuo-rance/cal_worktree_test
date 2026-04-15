"""
报表路由
"""

import re
import sqlite3
import sys
import os
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, render_template, redirect, url_for, request, Response

from web.utils import get_db
from web.decorators import login_required, admin_required, self_or_admin

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.report_service import (
    generate_monthly_report,
    generate_comp_off_report,
    generate_salary_report,
    generate_overtime_ranking,
    ReportError
)
from services.export_service import (
    export_to_csv,
    export_to_excel,
    export_report_to_pdf,
    ExportError
)

bp = Blueprint('reports', __name__, url_prefix='/reports')


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|]', '', name)


def _make_file_response(data: bytes, filename: str, content_type: str) -> Response:
    """构建文件下载响应，支持中文文件名（RFC 5987）"""
    ascii_filename = filename.encode('ascii', 'ignore').decode('ascii') or 'download'
    encoded_filename = quote(filename, safe='')
    disposition = (
        f"attachment; filename=\"{ascii_filename}\"; "
        f"filename*=UTF-8''{encoded_filename}"
    )
    return Response(
        data,
        mimetype=content_type,
        headers={"Content-Disposition": disposition}
    )


def _monthly_report_to_structures(report: dict):
    """将月度报表数据转换为导出服务需要的结构"""
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

    return columns, ot_data, leave_data


def _salary_report_to_structures(report: dict):
    """将工资报表数据转换为导出服务需要的结构"""
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
    return columns, data


def _comp_off_report_to_structures(report: dict):
    """将调休报表数据转换为导出服务需要的结构"""
    columns = [
        ("acquired_date", "获得日期"),
        ("source_overtime_date", "来源加班日期"),
        ("total_hours", "总时长(小时)"),
        ("used_hours", "已使用(小时)"),
        ("remaining_hours", "剩余时长(小时)"),
        ("expiry_date", "到期日期"),
        ("status", "状态"),
    ]

    data = []
    for row in report.get("active_balances", []):
        data.append({
            "acquired_date": row.get("acquired_date", ""),
            "source_overtime_date": row.get("source_overtime_date") or "-",
            "total_hours": row.get("total_hours", 0),
            "used_hours": row.get("used_hours", 0),
            "remaining_hours": row.get("remaining_hours", 0),
            "expiry_date": row.get("expiry_date") or "-",
            "status": row.get("status", ""),
        })
    return columns, data


# ---------------------------------------------------------------------------
# 页面路由
# ---------------------------------------------------------------------------

@bp.route('/')
@login_required
def reports_index():
    """报表首页"""
    conn = get_db()
    cursor = conn.cursor()

    employees = []
    try:
        cursor.execute("SELECT employee_id, name, is_active FROM employees ORDER BY is_active DESC, name")
        employees = [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return render_template('reports/index.html', employees=employees)


@bp.route('/monthly/<employee_id>/')
@self_or_admin
def monthly_report_default(employee_id):
    """月度报表 - 默认当前年月"""
    now = datetime.now()
    return redirect(url_for('reports.monthly_report', employee_id=employee_id, year=now.year, month=now.month))


@bp.route('/monthly/<employee_id>/<int:year>/<int:month>/')
@self_or_admin
def monthly_report(employee_id, year, month):
    """月度报表"""
    conn = get_db()
    try:
        report = generate_monthly_report(conn, employee_id, year, month)
    except ReportError as e:
        report = None
        error = str(e)

    # 获取员工列表用于下拉选择
    cursor = conn.cursor()
    employees = []
    try:
        cursor.execute("SELECT employee_id, name, is_active FROM employees ORDER BY is_active DESC, name")
        employees = [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return render_template(
        'reports/monthly.html',
        report=report,
        error=error if not report else None,
        year=year,
        month=month,
        employee_id=employee_id,
        employees=employees
    )


@bp.route('/comp-off/<employee_id>/')
@self_or_admin
def comp_off_report(employee_id):
    """调休余额报表"""
    conn = get_db()
    try:
        report = generate_comp_off_report(conn, employee_id)
    except Exception as e:
        report = None
        error = str(e)
    finally:
        conn.close()

    return render_template(
        'reports/comp_off.html',
        report=report,
        error=error if not report else None,
        employee_id=employee_id
    )


@bp.route('/comp-off/<employee_id>/export/')
@self_or_admin
def comp_off_report_export(employee_id):
    """调休余额报表导出"""
    fmt = request.args.get('format', 'csv').lower()
    conn = get_db()
    try:
        report = generate_comp_off_report(conn, employee_id)
    except Exception as e:
        conn.close()
        return render_template('reports/comp_off.html', report=None, error=str(e), employee_id=employee_id)
    finally:
        if 'conn' in locals():
            conn.close()

    employee_name = _sanitize_filename(report.get('employee_name', ''))

    if fmt == 'csv':
        columns, data = _comp_off_report_to_structures(report)
        csv_bytes = export_to_csv(data, columns)
        output = b""
        output += f"员工: {report.get('employee_name', '')} ({employee_id})\n\n".encode('utf-8-sig')
        output += csv_bytes
        csv_bytes = output
        filename = f"{employee_id}_{employee_name}_comp_off_report.csv"
        return _make_file_response(csv_bytes, filename, "text/csv; charset=utf-8")

    if fmt == 'xlsx':
        columns, data = _comp_off_report_to_structures(report)
        name_label = employee_name or employee_id
        excel_bytes = export_to_excel({
            f"{name_label}-调休余额": {"columns": columns, "data": data},
        })
        filename = f"{employee_id}_{employee_name}_comp_off_report.xlsx"
        return _make_file_response(excel_bytes, filename, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if fmt == 'pdf':
        pdf_bytes = export_report_to_pdf(report, 'comp_off')
        filename = f"{employee_id}_{employee_name}_comp_off_report.pdf"
        return _make_file_response(pdf_bytes, filename, "application/pdf")

    return "\u4e0d\u652f\u6301\u7684\u683c\u5f0f", 400


@bp.route('/salary/<employee_id>/<int:year>/<int:month>/')
@self_or_admin
def salary_report(employee_id, year, month):
    """工资计算表"""
    conn = get_db()
    try:
        report = generate_salary_report(conn, employee_id, year, month)
    except ReportError as e:
        report = None
        error = str(e)
    finally:
        conn.close()

    return render_template(
        'reports/salary.html',
        report=report,
        error=error if not report else None,
        year=year,
        month=month,
        employee_id=employee_id
    )


@bp.route('/ranking/')
@admin_required
def overtime_ranking():
    """员工加班排名"""
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)

    # 默认显示全年排名
    from datetime import datetime
    now = datetime.now()
    if year is None:
        year = now.year

    conn = get_db()
    try:
        report = generate_overtime_ranking(conn, year=year, month=month)
    except Exception as e:
        report = None
        error = str(e)
    finally:
        conn.close()

    return render_template(
        'reports/ranking.html',
        report=report,
        error=error if not report else None,
        year=year,
        month=month if month is not None else ''
    )


# ---------------------------------------------------------------------------
# 导出路由
# ---------------------------------------------------------------------------

@bp.route('/monthly/<employee_id>/<int:year>/<int:month>/export/')
@self_or_admin
def monthly_report_export(employee_id, year, month):
    """月度报表导出"""
    fmt = request.args.get('format', 'csv').lower()
    conn = get_db()
    try:
        report = generate_monthly_report(conn, employee_id, year, month)
    except ReportError as e:
        conn.close()
        return render_template('reports/monthly.html', report=None, error=str(e), year=year, month=month, employee_id=employee_id, employees=[])
    finally:
        if 'conn' in locals():
            conn.close()

    employee_name = _sanitize_filename(report.get('employee_name', ''))

    if fmt == 'csv':
        columns, ot_data, leave_data = _monthly_report_to_structures(report)
        output = b""
        output += f"员工: {report.get('employee_name', '')} ({employee_id})\n".encode('utf-8-sig')
        output += f"文件名: {employee_id}_{employee_name}_{year}{month:02d}_月度报表.csv\n\n".encode('utf-8-sig')
        output += "加班明细\n".encode('utf-8-sig')
        output += export_to_csv(ot_data, columns) or b""
        output += "\n".encode('utf-8-sig')
        output += "请假明细\n".encode('utf-8-sig')
        output += export_to_csv(leave_data, columns) or b""
        filename = f"{employee_id}_{employee_name}_{year}{month:02d}_monthly_report.csv"
        return _make_file_response(output, filename, "text/csv; charset=utf-8")

    if fmt == 'xlsx':
        columns, ot_data, leave_data = _monthly_report_to_structures(report)
        name_label = employee_name or employee_id
        excel_bytes = export_to_excel({
            f"{name_label}-加班明细": {"columns": columns, "data": ot_data},
            f"{name_label}-请假明细": {"columns": columns, "data": leave_data},
        })
        filename = f"{employee_id}_{employee_name}_{year}{month:02d}_monthly_report.xlsx"
        return _make_file_response(excel_bytes, filename, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if fmt == 'pdf':
        pdf_bytes = export_report_to_pdf(report, 'monthly')
        filename = f"{employee_id}_{employee_name}_{year}{month:02d}_monthly_report.pdf"
        return _make_file_response(pdf_bytes, filename, "application/pdf")

    return "不支持的格式", 400

@bp.route('/salary/<employee_id>/<int:year>/<int:month>/export/')
@self_or_admin
def salary_report_export(employee_id, year, month):
    """工资报表导出"""
    fmt = request.args.get('format', 'csv').lower()
    conn = get_db()
    try:
        report = generate_salary_report(conn, employee_id, year, month)
    except ReportError as e:
        conn.close()
        return render_template('reports/salary.html', report=None, error=str(e), year=year, month=month, employee_id=employee_id)
    finally:
        if 'conn' in locals():
            conn.close()

    employee_name = _sanitize_filename(report.get('employee_name', ''))

    if fmt == 'csv':
        columns, data = _salary_report_to_structures(report)
        csv_bytes = export_to_csv(data, columns)
        output = b""
        output += f"员工: {report.get('employee_name', '')} ({employee_id})\n\n".encode('utf-8-sig')
        output += csv_bytes
        csv_bytes = output
        filename = f"{employee_id}_{employee_name}_{year}{month:02d}_salary_report.csv"
        return _make_file_response(csv_bytes, filename, "text/csv; charset=utf-8")

    if fmt == 'xlsx':
        columns, data = _salary_report_to_structures(report)
        name_label = employee_name or employee_id
        excel_bytes = export_to_excel({
            f"{name_label}-工资计算": {"columns": columns, "data": data},
        })
        filename = f"{employee_id}_{employee_name}_{year}{month:02d}_salary_report.xlsx"
        return _make_file_response(excel_bytes, filename, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if fmt == 'pdf':
        pdf_bytes = export_report_to_pdf(report, 'salary')
        filename = f"{employee_id}_{employee_name}_{year}{month:02d}_salary_report.pdf"
        return _make_file_response(pdf_bytes, filename, "application/pdf")

    return "\u4e0d\u652f\u6301\u7684\u683c\u5f0f", 400
