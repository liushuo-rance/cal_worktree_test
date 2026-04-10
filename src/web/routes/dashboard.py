"""
Dashboard路由
首页统计概览
"""

import sqlite3
import sys
import os

from flask import Blueprint, render_template

from web.utils import get_db

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from services.report_service import generate_overtime_ranking

bp = Blueprint('dashboard', __name__)


@bp.route('/')
def index():
    """首页/Dashboard"""
    conn = get_db()
    cursor = conn.cursor()

    # 获取统计信息
    stats = {
        'total_employees': 0,
        'total_overtime_records': 0,
        'total_leave_records': 0,
        'pending_reviews': 0
    }

    compliance_rate = 100.0
    pending_anomalies = 0
    try:
        cursor.execute("SELECT COUNT(*) as count FROM employees")
        stats['total_employees'] = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM overtime_records")
        stats['total_overtime_records'] = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM leave_records")
        stats['total_leave_records'] = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM import_records WHERE status = 'pending'")
        stats['pending_reviews'] = cursor.fetchone()['count']

        # 计算待处理异常数：导入待审批 + 调休待审批
        cursor.execute("SELECT COUNT(*) as count FROM import_records WHERE status = 'pending'")
        pending_imports = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM comp_off_usage_records WHERE status = 'pending'")
        pending_comp_off = cursor.fetchone()['count']

        pending_anomalies = pending_imports + pending_comp_off
        # 合规健康度：每个未处理异常扣 5 分，最低 0
        compliance_rate = max(0.0, 100.0 - pending_anomalies * 5.0)

        # 默认显示当年排名（全年，不按月）
        from datetime import datetime
        current_year = datetime.now().year
        ranking_report = generate_overtime_ranking(conn, year=current_year, month=None)
    except sqlite3.Error:
        ranking_report = None
    finally:
        conn.close()

    return render_template(
        'dashboard.html',
        stats=stats,
        ranking_report=ranking_report,
        compliance_rate=compliance_rate,
        pending_anomalies=pending_anomalies
    )
