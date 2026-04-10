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

    try:
        cursor.execute("SELECT COUNT(*) as count FROM employees")
        stats['total_employees'] = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM overtime_records")
        stats['total_overtime_records'] = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM leave_records")
        stats['total_leave_records'] = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM import_records WHERE status = 'pending'")
        stats['pending_reviews'] = cursor.fetchone()['count']

        # 默认显示当年排名（全年，不按月）
        from datetime import datetime
        current_year = datetime.now().year
        ranking_report = generate_overtime_ranking(conn, year=current_year, month=None)
    except sqlite3.Error:
        ranking_report = None
    finally:
        conn.close()

    return render_template('dashboard.html', stats=stats, ranking_report=ranking_report)
