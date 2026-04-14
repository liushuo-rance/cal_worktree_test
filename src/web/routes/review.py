"""
审批队列路由
"""

import json
import sqlite3

from flask import Blueprint, render_template, request, flash, redirect, url_for

from web.utils import get_db
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from services.review_service import (
    approve_review,
    reject_review,
    ReviewServiceError,
)
from services.comp_off_service import (
    approve_comp_off_request,
    reject_comp_off_request,
    CompOffError,
)
from services.ai_parser_service import _normalize_overtime_type

bp = Blueprint('review', __name__, url_prefix='/review')


def _enrich_review_item(item: dict) -> dict:
    """将 review_queue 字段适配为模板期望的格式"""
    item = dict(item)
    item['record_type'] = item.get('parsed_type') or '未知'
    item['parsed_data'] = json.dumps({
        'type': item.get('parsed_type'),
        'date': item.get('parsed_date'),
        'hours': item.get('parsed_hours'),
        'minutes': item.get('parsed_minutes'),
        'confidence': item.get('confidence_level'),
        'score': item.get('confidence_score'),
        'anomalies': item.get('anomalies'),
    }, ensure_ascii=False, default=str)
    return item


def _store_review_record_to_db(conn: sqlite3.Connection, row: sqlite3.Row) -> None:
    """将审批通过的 review_queue 记录写入实际业务表"""
    cursor = conn.cursor()

    total_minutes = row['parsed_minutes'] or int(round((row['parsed_hours'] or 0) * 60))
    duration_hours = total_minutes // 60
    duration_minutes = total_minutes % 60
    record_type = row['parsed_type']
    record_subtype = row['parsed_subtype']
    record_date = row['parsed_date']
    employee_id = row['employee_id']
    raw_text = row['raw_text']
    import_session_id = row['import_session_id']

    if record_type == 'overtime' and record_date:
        overtime_type = _normalize_overtime_type(record_subtype or 'weekday_evening')
        cursor.execute(
            "SELECT id FROM overtime_records WHERE employee_id = ? AND work_date = ? AND overtime_type = ?",
            (employee_id, record_date, overtime_type)
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE overtime_records
                SET duration_hours = ?, duration_minutes = ?,
                    total_minutes = ?, description = ?, source_import_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (duration_hours, duration_minutes, total_minutes, raw_text, import_session_id, existing['id']))
        else:
            cursor.execute("""
                INSERT INTO overtime_records
                (employee_id, work_date, duration_hours, duration_minutes,
                 total_minutes, overtime_type, description, source_import_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (employee_id, record_date, duration_hours, duration_minutes,
                  total_minutes, overtime_type, raw_text, import_session_id))
            if overtime_type == 'weekend':
                cursor.execute("""
                    INSERT INTO comp_off_balances
                    (employee_id, acquired_date, expiry_date, total_minutes, remaining_minutes, status)
                    VALUES (?, ?, date(?, '+180 days'), ?, ?, 'active')
                """, (employee_id, record_date, record_date, total_minutes, total_minutes))

    elif record_type == 'leave' and record_date:
        leave_type = record_subtype or 'personal'
        cursor.execute(
            "SELECT id FROM leave_records WHERE employee_id = ? AND leave_date = ? AND leave_type = ?",
            (employee_id, record_date, leave_type)
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE leave_records
                SET duration_hours = ?, duration_minutes = ?,
                    total_minutes = ?, description = ?, source_import_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (duration_hours, duration_minutes, total_minutes, raw_text, import_session_id, existing['id']))
        else:
            cursor.execute("""
                INSERT INTO leave_records
                (employee_id, leave_date, duration_hours, duration_minutes,
                 total_minutes, leave_type, description, source_import_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (employee_id, record_date, duration_hours, duration_minutes,
                  total_minutes, leave_type, raw_text, import_session_id))

    elif record_type == 'comp_off' and record_date:
        cursor.execute(
            "SELECT id FROM comp_off_usage_records WHERE employee_id = ? AND usage_date = ?",
            (employee_id, record_date)
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE comp_off_usage_records
                SET duration_hours = ?, duration_minutes = ?,
                    total_minutes = ?, description = ?, source_import_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (duration_hours, duration_minutes, total_minutes, raw_text, import_session_id, existing['id']))
        else:
            cursor.execute("""
                INSERT INTO comp_off_usage_records
                (employee_id, usage_date, duration_hours, duration_minutes,
                 total_minutes, description, source_import_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (employee_id, record_date, duration_hours, duration_minutes,
                  total_minutes, raw_text, import_session_id))


@bp.route('/')
def review_queue():
    """审批队列"""
    conn = get_db()

    pending_items = []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rq.*, isess.file_path
            FROM review_queue rq
            JOIN import_sessions isess ON rq.import_session_id = isess.id
            WHERE rq.status = 'pending'
            ORDER BY rq.created_at
        """)
        rows = cursor.fetchall()
        pending_items = [_enrich_review_item(dict(row)) for row in rows]
    except Exception:
        pass
    finally:
        conn.close()

    return render_template('review.html', pending_items=pending_items)


@bp.route('/item/<int:item_id>/', methods=['GET', 'POST'])
def review_item(item_id):
    """单个审批项"""
    conn = get_db()

    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'approve':
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT rq.*, isess.employee_id, isess.file_path
                    FROM review_queue rq
                    JOIN import_sessions isess ON rq.import_session_id = isess.id
                    WHERE rq.id = ?
                """, (item_id,))
                row = cursor.fetchone()
                if not row:
                    raise ReviewServiceError(f"审核记录 {item_id} 不存在")
                if row['status'] != 'pending':
                    raise ReviewServiceError(f"审核记录 {item_id} 已处理，状态: {row['status']}")

                _store_review_record_to_db(conn, row)

                cursor.execute("""
                    UPDATE review_queue
                    SET status = 'approved',
                        reviewer_note = ?,
                        reviewed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, ('', item_id))
                conn.commit()
                flash('记录已批准并保存到系统', 'success')
            elif action == 'reject':
                reject_review(conn, item_id, reason='')
                flash('记录已拒绝', 'info')
        except ReviewServiceError as e:
            flash(str(e), 'error')
            conn.rollback()
        except Exception as e:
            flash(f'审批失败: {str(e)}', 'error')
            conn.rollback()
        finally:
            conn.close()
        return redirect(url_for('review.review_queue'))

    # 获取审批项详情
    item = None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rq.*, isess.file_path
            FROM review_queue rq
            JOIN import_sessions isess ON rq.import_session_id = isess.id
            WHERE rq.id = ?
        """, (item_id,))
        row = cursor.fetchone()
        if row:
            item = _enrich_review_item(dict(row))
    except Exception:
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
