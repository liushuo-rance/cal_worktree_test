"""
审批队列路由
"""

import sqlite3

from flask import Blueprint, render_template, request, flash, redirect, url_for

from web.utils import get_db
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from services.comp_off_service import (
    approve_comp_off_request,
    reject_comp_off_request,
    CompOffError,
)

bp = Blueprint('review', __name__, url_prefix='/review')


@bp.route('/')
def review_queue():
    """审批队列"""
    conn = get_db()
    cursor = conn.cursor()

    pending_items = []
    try:
        cursor.execute("""
            SELECT ir.*, isess.file_path
            FROM import_records ir
            JOIN import_sessions isess ON ir.session_id = isess.id
            WHERE ir.status = 'pending'
            ORDER BY ir.created_at
        """)
        pending_items = [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return render_template('review.html', pending_items=pending_items)


@bp.route('/item/<int:item_id>/', methods=['GET', 'POST'])
def review_item(item_id):
    """单个审批项"""
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'approve':
            # 批准记录
            cursor.execute(
                "UPDATE import_records SET status = 'approved' WHERE id = ?",
                (item_id,)
            )
            conn.commit()
            flash('记录已批准', 'success')
        elif action == 'reject':
            # 拒绝记录
            cursor.execute(
                "UPDATE import_records SET status = 'rejected' WHERE id = ?",
                (item_id,)
            )
            conn.commit()
            flash('记录已拒绝', 'info')
        conn.close()
        return redirect(url_for('review.review_queue'))

    # 获取审批项详情
    item = None
    try:
        cursor.execute("""
            SELECT ir.*, isess.file_path
            FROM import_records ir
            JOIN import_sessions isess ON ir.session_id = isess.id
            WHERE ir.id = ?
        """, (item_id,))
        row = cursor.fetchone()
        if row:
            item = dict(row)
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return render_template('review_item.html', item=item)


@bp.route('/comp-off/')
def comp_off_review_queue():
    """调休审批队列"""
    conn = get_db()
    cursor = conn.cursor()

    pending_requests = []
    try:
        cursor.execute("""
            SELECT
                c.id,
                c.employee_id,
                e.name as employee_name,
                c.usage_date,
                c.duration_hours,
                c.duration_minutes,
                c.total_minutes,
                c.description,
                c.status,
                c.created_at
            FROM comp_off_usage_records c
            JOIN employees e ON c.employee_id = e.employee_id
            WHERE c.status = 'pending'
            ORDER BY c.created_at
        """)
        pending_requests = [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return render_template('review_comp_off.html', pending_requests=pending_requests)


@bp.route('/comp-off/<int:request_id>/approve/', methods=['POST'])
def comp_off_approve(request_id):
    """批准调休申请"""
    conn = get_db()
    try:
        result = approve_comp_off_request(conn, request_id)
        flash(f'调休申请 #{request_id} 已批准，扣除余额 {result["deducted_minutes"]} 分钟', 'success')
    except CompOffError as e:
        flash(str(e), 'error')
    finally:
        conn.close()

    return redirect(url_for('review.comp_off_review_queue'))


@bp.route('/comp-off/<int:request_id>/reject/', methods=['POST'])
def comp_off_reject(request_id):
    """拒绝调休申请"""
    conn = get_db()
    try:
        reject_comp_off_request(conn, request_id)
        flash(f'调休申请 #{request_id} 已拒绝', 'info')
    except CompOffError as e:
        flash(str(e), 'error')
    finally:
        conn.close()

    return redirect(url_for('review.comp_off_review_queue'))
