"""
Dashboard路由
首页统计概览
"""

import sqlite3

from flask import Blueprint, render_template

from web.utils import get_db

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
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return render_template('dashboard.html', stats=stats)
