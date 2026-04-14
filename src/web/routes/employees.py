"""
员工管理路由
"""

import os
import sys
import sqlite3
import logging
import calendar
from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, abort

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from web.utils import get_db
from services.storage_service import delete_employee_service

bp = Blueprint('employees', __name__, url_prefix='/employees')
logger = logging.getLogger(__name__)


@bp.route('/')
def list_employees():
    """员工列表"""
    conn = get_db()
    cursor = conn.cursor()

    employees = []
    try:
        cursor.execute("SELECT * FROM employees ORDER BY is_active DESC, name")
        employees = [dict(row) for row in cursor.fetchall()]
        logger.info(f"查询到 {len(employees)} 名员工")
    except sqlite3.Error as e:
        logger.error(f"查询员工列表失败: {e}")
        flash('查询员工列表失败', 'error')
    finally:
        conn.close()

    return render_template('employees.html', employees=employees)


@bp.route('/create/', methods=['POST'])
def create_employee():
    """创建员工"""
    employee_id = request.form.get('employee_id', '').strip()
    name = request.form.get('name', '').strip()
    department = request.form.get('department', '').strip()

    logger.info(f"尝试创建员工: ID={employee_id}, 姓名={name}, 部门={department}")

    # 验证输入
    if not employee_id:
        logger.warning("创建员工失败: 员工ID为空")
        flash('员工ID不能为空', 'error')
        return redirect(url_for('employees.list_employees'))

    if not name:
        logger.warning("创建员工失败: 姓名为空")
        flash('姓名不能为空', 'error')
        return redirect(url_for('employees.list_employees'))

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO employees (employee_id, name, department)
            VALUES (?, ?, ?)
        """, (employee_id, name, department))
        conn.commit()
        logger.info(f"员工创建成功: {employee_id} - {name}")
        flash(f'员工 {name} 创建成功', 'success')
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"创建员工失败: 员工ID {employee_id} 已存在 - {e}")
        flash(f'员工ID {employee_id} 已存在', 'error')
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"创建员工失败: {e}")
        flash('创建员工失败', 'error')
    finally:
        conn.close()

    return redirect(url_for('employees.list_employees'))


@bp.route('/<employee_id>/delete/', methods=['POST'])
def delete_employee(employee_id):
    """删除员工（软删除）"""
    try:
        delete_employee_service(get_db(), employee_id)
        flash('员工已删除', 'success')
    except Exception as e:
        logger.error(f"删除员工失败: {e}")
        flash('删除员工失败', 'error')
    return redirect(url_for('employees.list_employees'))


@bp.route('/<employee_id>/')
def employee_detail(employee_id):
    """员工详情"""
    conn = get_db()
    cursor = conn.cursor()

    employee = None
    overtime_records = []
    leave_records = []
    comp_off_records = []
    heatmap_data = []
    heatmap_year = request.args.get('year', type=int) or datetime.now().year
    heatmap_month = request.args.get('month', type=int) or datetime.now().month

    try:
        cursor.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,))
        row = cursor.fetchone()
        if row:
            employee = dict(row)

            # 获取加班记录
            cursor.execute("""
                SELECT * FROM overtime_records
                WHERE employee_id = ?
                ORDER BY work_date DESC
                LIMIT 10
            """, (employee_id,))
            overtime_records = [dict(row) for row in cursor.fetchall()]

            # 获取请假记录
            cursor.execute("""
                SELECT * FROM leave_records
                WHERE employee_id = ?
                ORDER BY leave_date DESC
                LIMIT 10
            """, (employee_id,))
            leave_records = [dict(row) for row in cursor.fetchall()]

            # 获取调休记录
            cursor.execute("""
                SELECT * FROM comp_off_usage_records
                WHERE employee_id = ?
                ORDER BY usage_date DESC
                LIMIT 10
            """, (employee_id,))
            comp_off_records = [dict(row) for row in cursor.fetchall()]

            # 获取当月热力图数据
            start_date = f"{heatmap_year}-{heatmap_month:02d}-01"
            if heatmap_month == 12:
                next_month_start = f"{heatmap_year + 1}-01-01"
            else:
                next_month_start = f"{heatmap_year}-{heatmap_month + 1:02d}-01"

            cursor.execute("""
                SELECT work_date,
                       SUM(duration_hours * 60 + duration_minutes) AS total_minutes,
                       GROUP_CONCAT(DISTINCT overtime_type) AS types
                FROM overtime_records
                WHERE employee_id = ?
                  AND work_date >= ?
                  AND work_date < ?
                GROUP BY work_date
                ORDER BY work_date
            """, (employee_id, start_date, next_month_start))
            overtime_by_date = {row['work_date']: dict(row) for row in cursor.fetchall()}

            # 构建完整月份日历数据
            _, last_day = calendar.monthrange(heatmap_year, heatmap_month)
            first_weekday = calendar.monthrange(heatmap_year, heatmap_month)[0]  # 0=周一 在 calendar 中实际上是 0=周一
            # Python calendar.monthrange 返回 (weekday_of_first_day, number_of_days)
            # weekday: Monday is 0, Sunday is 6

            heatmap_data = []
            current = date(heatmap_year, heatmap_month, 1)
            for day_num in range(1, last_day + 1):
                day_str = current.strftime('%Y-%m-%d')
                day_record = overtime_by_date.get(day_str)
                total_minutes = day_record['total_minutes'] if day_record else 0
                types = day_record['types'].split(',') if day_record and day_record['types'] else []
                heatmap_data.append({
                    'date': day_str,
                    'day': day_num,
                    'weekday': current.weekday(),  # 0=周一, 6=周日
                    'total_minutes': total_minutes,
                    'types': types,
                })
                current += timedelta(days=1)

            logger.info(f"查询员工详情: {employee_id}, 加班 {len(overtime_records)} 条, 请假 {len(leave_records)} 条, 调休 {len(comp_off_records)} 条")
        else:
            logger.warning(f"员工不存在: {employee_id}")
            flash('员工不存在', 'error')
    except sqlite3.Error as e:
        logger.error(f"查询员工详情失败: {e}")
        flash('查询失败', 'error')
    finally:
        conn.close()

    return render_template(
        'employee_detail.html',
        employee=employee,
        overtime_records=overtime_records,
        leave_records=leave_records,
        comp_off_records=comp_off_records,
        heatmap_data=heatmap_data,
        heatmap_year=heatmap_year,
        heatmap_month=heatmap_month,
    )


@bp.route('/<employee_id>/records/')
def employee_records(employee_id):
    """员工记录管理页面"""
    conn = get_db()
    cursor = conn.cursor()

    employee = None
    overtime_records = []
    leave_records = []
    comp_off_records = []
    active_tab = request.args.get('tab', 'overtime')

    try:
        cursor.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,))
        row = cursor.fetchone()
        if row:
            employee = dict(row)

            cursor.execute("""
                SELECT * FROM overtime_records
                WHERE employee_id = ?
                ORDER BY work_date DESC
            """, (employee_id,))
            overtime_records = [dict(row) for row in cursor.fetchall()]

            cursor.execute("""
                SELECT * FROM leave_records
                WHERE employee_id = ?
                ORDER BY leave_date DESC
            """, (employee_id,))
            leave_records = [dict(row) for row in cursor.fetchall()]

            cursor.execute("""
                SELECT * FROM comp_off_usage_records
                WHERE employee_id = ?
                ORDER BY usage_date DESC
            """, (employee_id,))
            comp_off_records = [dict(row) for row in cursor.fetchall()]
        else:
            flash('员工不存在', 'error')
    except sqlite3.Error as e:
        logger.error(f"查询员工记录失败: {e}")
        flash('查询失败', 'error')
    finally:
        conn.close()

    # 检测当前 active_tab 内的重复记录（同一天 + 同类型 + 同时长）
    duplicate_groups = []
    if active_tab == 'overtime':
        groups = {}
        for r in overtime_records:
            key = (r.get('work_date'), r.get('overtime_type'), r.get('total_minutes'))
            groups.setdefault(key, []).append(r)
        duplicate_groups = [g for g in groups.values() if len(g) >= 2]
    elif active_tab == 'leave':
        groups = {}
        for r in leave_records:
            key = (r.get('leave_date'), r.get('leave_type'), r.get('total_minutes'))
            groups.setdefault(key, []).append(r)
        duplicate_groups = [g for g in groups.values() if len(g) >= 2]
    elif active_tab == 'comp_off':
        groups = {}
        for r in comp_off_records:
            key = (r.get('usage_date'), r.get('total_minutes'))
            groups.setdefault(key, []).append(r)
        duplicate_groups = [g for g in groups.values() if len(g) >= 2]

    return render_template(
        'employee_records.html',
        employee=employee,
        overtime_records=overtime_records,
        leave_records=leave_records,
        comp_off_records=comp_off_records,
        active_tab=active_tab,
        duplicate_groups=duplicate_groups
    )


@bp.route('/<employee_id>/records/create/', methods=['GET', 'POST'])
def create_record(employee_id):
    """创建员工记录"""
    record_type = request.args.get('type', 'overtime')
    if record_type not in ('overtime', 'leave', 'comp_off'):
        record_type = 'overtime'

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,))
    employee = cursor.fetchone()
    if not employee:
        conn.close()
        flash('员工不存在', 'error')
        return redirect(url_for('employees.list_employees'))

    if request.method == 'POST':
        record_date = request.form.get('record_date', '').strip()
        duration_hours = int(request.form.get('duration_hours', 0) or 0)
        duration_minutes = int(request.form.get('duration_minutes', 0) or 0)
        subtype = request.form.get('subtype', '').strip()
        description = request.form.get('description', '').strip()
        total_minutes = duration_hours * 60 + duration_minutes

        if not record_date:
            flash('日期不能为空', 'error')
            conn.close()
            return redirect(request.url)

        try:
            if record_type == 'overtime':
                cursor.execute("""
                    INSERT INTO overtime_records
                    (employee_id, work_date, overtime_type, duration_hours, duration_minutes,
                     total_minutes, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (employee_id, record_date, subtype or 'weekday_evening',
                      duration_hours, duration_minutes, total_minutes, description))
            elif record_type == 'leave':
                cursor.execute("""
                    INSERT INTO leave_records
                    (employee_id, leave_date, leave_type, duration_hours, duration_minutes,
                     total_minutes, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (employee_id, record_date, subtype or 'personal',
                      duration_hours, duration_minutes, total_minutes, description))
            elif record_type == 'comp_off':
                cursor.execute("""
                    INSERT INTO comp_off_usage_records
                    (employee_id, usage_date, duration_hours, duration_minutes,
                     total_minutes, description, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """, (employee_id, record_date, duration_hours, duration_minutes,
                      total_minutes, description))

            conn.commit()
            flash('记录创建成功', 'success')
            return redirect(url_for('employees.employee_records', employee_id=employee_id, tab=record_type))
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"创建记录失败: {e}")
            flash(f'创建失败: {e}', 'error')
        finally:
            conn.close()

        return redirect(request.url)

    conn.close()
    return render_template(
        'employee_record_form.html',
        employee=dict(employee),
        record=None,
        record_type=record_type,
        mode='create'
    )


@bp.route('/<employee_id>/records/<record_type>/<int:record_id>/edit/', methods=['GET', 'POST'])
def edit_record(employee_id, record_type, record_id):
    """编辑员工记录"""
    if record_type not in ('overtime', 'leave', 'comp_off'):
        abort(404)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,))
    employee = cursor.fetchone()
    if not employee:
        conn.close()
        flash('员工不存在', 'error')
        return redirect(url_for('employees.list_employees'))

    # 查询记录
    if record_type == 'overtime':
        cursor.execute("SELECT * FROM overtime_records WHERE id = ? AND employee_id = ?", (record_id, employee_id))
    elif record_type == 'leave':
        cursor.execute("SELECT * FROM leave_records WHERE id = ? AND employee_id = ?", (record_id, employee_id))
    else:
        cursor.execute("SELECT * FROM comp_off_usage_records WHERE id = ? AND employee_id = ?", (record_id, employee_id))

    record = cursor.fetchone()
    if not record:
        conn.close()
        flash('记录不存在', 'error')
        return redirect(url_for('employees.employee_records', employee_id=employee_id, tab=record_type))

    if request.method == 'POST':
        record_date = request.form.get('record_date', '').strip()
        duration_hours = int(request.form.get('duration_hours', 0) or 0)
        duration_minutes = int(request.form.get('duration_minutes', 0) or 0)
        subtype = request.form.get('subtype', '').strip()
        description = request.form.get('description', '').strip()
        total_minutes = duration_hours * 60 + duration_minutes

        if not record_date:
            flash('日期不能为空', 'error')
            conn.close()
            return redirect(request.url)

        try:
            if record_type == 'overtime':
                cursor.execute("""
                    UPDATE overtime_records
                    SET work_date = ?, overtime_type = ?, duration_hours = ?,
                        duration_minutes = ?, total_minutes = ?, description = ?
                    WHERE id = ? AND employee_id = ?
                """, (record_date, subtype or 'weekday_evening',
                      duration_hours, duration_minutes, total_minutes, description,
                      record_id, employee_id))
            elif record_type == 'leave':
                cursor.execute("""
                    UPDATE leave_records
                    SET leave_date = ?, leave_type = ?, duration_hours = ?,
                        duration_minutes = ?, total_minutes = ?, description = ?
                    WHERE id = ? AND employee_id = ?
                """, (record_date, subtype or 'personal',
                      duration_hours, duration_minutes, total_minutes, description,
                      record_id, employee_id))
            else:
                cursor.execute("""
                    UPDATE comp_off_usage_records
                    SET usage_date = ?, duration_hours = ?,
                        duration_minutes = ?, total_minutes = ?, description = ?
                    WHERE id = ? AND employee_id = ?
                """, (record_date, duration_hours, duration_minutes,
                      total_minutes, description, record_id, employee_id))

            conn.commit()
            flash('记录更新成功', 'success')
            return redirect(url_for('employees.employee_records', employee_id=employee_id, tab=record_type))
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"更新记录失败: {e}")
            flash(f'更新失败: {e}', 'error')
        finally:
            conn.close()

        return redirect(request.url)

    conn.close()
    return render_template(
        'employee_record_form.html',
        employee=dict(employee),
        record=dict(record),
        record_type=record_type,
        mode='edit'
    )


@bp.route('/<employee_id>/records/<record_type>/<int:record_id>/delete/', methods=['POST'])
def delete_record(employee_id, record_type, record_id):
    """删除员工记录"""
    if record_type not in ('overtime', 'leave', 'comp_off'):
        abort(404)

    conn = get_db()
    cursor = conn.cursor()

    try:
        if record_type == 'overtime':
            cursor.execute("DELETE FROM overtime_records WHERE id = ? AND employee_id = ?", (record_id, employee_id))
        elif record_type == 'leave':
            cursor.execute("DELETE FROM leave_records WHERE id = ? AND employee_id = ?", (record_id, employee_id))
        else:
            cursor.execute("DELETE FROM comp_off_usage_records WHERE id = ? AND employee_id = ?", (record_id, employee_id))

        conn.commit()
        flash('记录删除成功', 'success')
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"删除记录失败: {e}")
        flash(f'删除失败: {e}', 'error')
    finally:
        conn.close()

    return redirect(url_for('employees.employee_records', employee_id=employee_id, tab=record_type))

@bp.route('/<employee_id>/records/merge-duplicates/<record_type>/', methods=['POST'])
def merge_duplicates(employee_id, record_type):
    """合并重复记录：保留第一条并合并描述，删除其余"""
    if record_type not in ('overtime', 'leave', 'comp_off'):
        abort(404)

    record_ids = request.form.getlist('record_ids')
    if not record_ids:
        flash('未选择要合并的记录', 'warning')
        return redirect(url_for('employees.employee_records', employee_id=employee_id, tab=record_type))

    record_ids = [int(rid) for rid in record_ids]
    keep_id = min(record_ids)
    delete_ids = [rid for rid in record_ids if rid != keep_id]

    conn = get_db()
    cursor = conn.cursor()
    try:
        if record_type == 'overtime':
            table = 'overtime_records'
            date_col = 'work_date'
        elif record_type == 'leave':
            table = 'leave_records'
            date_col = 'leave_date'
        else:
            table = 'comp_off_usage_records'
            date_col = 'usage_date'

        placeholders = ','.join(['?' for _ in record_ids])
        cursor.execute(f"SELECT description FROM {table} WHERE id IN ({placeholders}) ORDER BY id", tuple(record_ids))
        descriptions = [row['description'] or '' for row in cursor.fetchall() if (row['description'] or '').strip()]
        merged_description = ' | '.join(dict.fromkeys(descriptions)) if descriptions else ''

        cursor.execute(f"UPDATE {table} SET description = ? WHERE id = ?", (merged_description, keep_id))
        if delete_ids:
            del_placeholders = ','.join(['?' for _ in delete_ids])
            cursor.execute(f"DELETE FROM {table} WHERE id IN ({del_placeholders})", tuple(delete_ids))
        conn.commit()
        flash(f'已合并 {len(record_ids)} 条重复记录为 1 条', 'success')
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"合并重复记录失败: {e}")
        flash('合并失败', 'error')
    finally:
        conn.close()

    return redirect(url_for('employees.employee_records', employee_id=employee_id, tab=record_type))


@bp.route('/<employee_id>/records/deduplicate/<record_type>/', methods=['POST'])
def deduplicate_records(employee_id, record_type):
    """去重：只保留第一条，删除其余重复记录"""
    if record_type not in ('overtime', 'leave', 'comp_off'):
        abort(404)

    record_ids = request.form.getlist('record_ids')
    if not record_ids:
        flash('未选择要去重的记录', 'warning')
        return redirect(url_for('employees.employee_records', employee_id=employee_id, tab=record_type))

    record_ids = [int(rid) for rid in record_ids]
    keep_id = min(record_ids)
    delete_ids = [rid for rid in record_ids if rid != keep_id]

    conn = get_db()
    cursor = conn.cursor()
    try:
        if record_type == 'overtime':
            table = 'overtime_records'
        elif record_type == 'leave':
            table = 'leave_records'
        else:
            table = 'comp_off_usage_records'

        if delete_ids:
            del_placeholders = ','.join(['?' for _ in delete_ids])
            cursor.execute(f"DELETE FROM {table} WHERE id IN ({del_placeholders})", tuple(delete_ids))
        conn.commit()
        flash(f'已保留 1 条记录，删除 {len(delete_ids)} 条重复记录', 'success')
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"去重失败: {e}")
        flash('去重失败', 'error')
    finally:
        conn.close()

    return redirect(url_for('employees.employee_records', employee_id=employee_id, tab=record_type))
