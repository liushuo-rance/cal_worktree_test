"""
报表路由
"""

import sqlite3
import sys
import os

from flask import Blueprint, render_template, request

from web.utils import get_db

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.report_service import (
    generate_monthly_report,
    generate_comp_off_report,
    generate_salary_report,
    generate_overtime_ranking,
    ReportError
)

bp = Blueprint('reports', __name__, url_prefix='/reports')


@bp.route('/')
def reports_index():
    """报表首页"""
    conn = get_db()
    cursor = conn.cursor()

    employees = []
    try:
        cursor.execute("SELECT employee_id, name FROM employees ORDER BY name")
        employees = [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return render_template('reports/index.html', employees=employees)


@bp.route('/monthly/<employee_id>/<int:year>/<int:month>/')
def monthly_report(employee_id, year, month):
    """月度报表"""
    conn = get_db()
    try:
        report = generate_monthly_report(conn, employee_id, year, month)
    except ReportError as e:
        report = None
        error = str(e)
    finally:
        conn.close()

    return render_template(
        'reports/monthly.html',
        report=report,
        error=error if not report else None,
        year=year,
        month=month,
        employee_id=employee_id
    )


@bp.route('/comp-off/<employee_id>/')
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


@bp.route('/salary/<employee_id>/<int:year>/<int:month>/')
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
