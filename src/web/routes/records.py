"""
记录导入路由
支持文件上传、解析预览、确认导入三步流程
"""

import sqlite3
import re
from datetime import date
from typing import List, Dict, Any, Optional

from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify

from web.utils import get_db
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from parsers.date_parser import parse_date, parse_date_range, DateParseError
from parsers.hours_parser import parse_hours
from parsers.type_parser import classify_record_type
from services.parse_result_processor import process_parse_results
from services.ai_parser_service import parse_with_ai
from services.storage_service import store_batch_records_with_session, StorageError
from services.holiday_service import get_date_type

bp = Blueprint('records', __name__, url_prefix='/records')


def parse_record_line(line: str, line_num: int = 0) -> Optional[Dict[str, Any]]:
    """
    解析单行记录

    Args:
        line: 原始行文本，如 "2025.01.15 晚上加班2小时，完成项目文档"
        line_num: 行号

    Returns:
        解析结果字典，解析失败返回 None
    """
    original_line = line.strip()  # 保留原始行用于显示
    if not original_line or original_line.startswith('#') or original_line.startswith('##'):
        return None

    # 移除 Markdown 加粗标记（用于解析）
    line = re.sub(r'\*\*', '', original_line)

    result = {
        'raw_line': original_line,  # 100%原始MD行内容
        'line_num': line_num,
        'type': 'unknown',
        'confidence': 0.0,
        'parsed_hours': None,
        'parsed_date': None,
        'weekday': None  # 星期几
    }

    # 提取日期
    date_match = re.match(r'^(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})[,，\s]+(.*)$', line)
    if date_match:
        date_str = date_match.group(1)
        content = date_match.group(2)

        try:
            parsed_date = parse_date(date_str)
            result['parsed_date'] = parsed_date
            result['date_str'] = date_str
            # 计算星期几
            weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            result['weekday'] = weekdays[parsed_date.weekday()]
        except DateParseError:
            result['date_str'] = date_str
            result['parse_error'] = '日期解析失败'
    else:
        # 尝试匹配日期范围
        range_match = re.match(r'^(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}\s*[-~至]\s*\d{1,2})[,，\s]+(.*)$', line)
        if range_match:
            date_str = range_match.group(1)
            content = range_match.group(2)
            result['date_str'] = date_str
            result['is_range'] = True
            try:
                start_date, end_date = parse_date_range(date_str)
                result['parsed_date'] = start_date
                result['end_date'] = end_date
            except DateParseError as e:
                result['parse_error'] = f'日期范围解析失败: {str(e)}'
        else:
            content = line
            result['parse_error'] = '未找到日期'

    # 类型识别
    # 特殊处理：下午xx小时、晚上xx小时 默认是加班（工作日晚上）
    afternoon_evening_match = re.search(r'(下午|晚上)\s*\d+\.?\d*\s*小时', content)
    if afternoon_evening_match and '请假' not in content and '调休' not in content and '休假' not in content:
        result['type'] = 'overtime'
        result['overtime_type'] = 'weekday_evening'
        result['confidence'] = 0.85
    else:
        type_result = classify_record_type(content)
        result.update(type_result)

    # 提取时长
    if result['type'] in ['overtime', 'leave', 'comp_off']:
        hours_result = parse_hours(content)
        if hours_result:
            hours, minutes, total_minutes = hours_result
            result['parsed_hours'] = hours + minutes / 60
            result['total_minutes'] = total_minutes
        else:
            # 默认值
            if result['type'] == 'leave':
                result['parsed_hours'] = 8.0  # 请假默认1天
            elif result['type'] == 'comp_off':
                result['parsed_hours'] = 4.0  # 调休默认半天

    result['content'] = content
    return result


def update_parse_progress(session_key: str, step: str, message: str, progress: int):
    """更新解析进度到session"""
    import time
    progress_data = session.get(f'parse_progress_{session_key}', [])
    progress_data.append({
        'timestamp': time.strftime('%H:%M:%S'),
        'step': step,
        'message': message,
        'progress': progress
    })
    session[f'parse_progress_{session_key}'] = progress_data
    session.modified = True


def parse_file_content(content: str, session_key: str = None) -> Dict[str, Any]:
    """
    解析文件内容，仅使用AI大模型解析

    Args:
        content: 文件内容
        session_key: session key用于进度跟踪

    Returns:
        包含解析结果、prompt、response的字典
    """
    # 首先提取所有有效行
    if session_key:
        update_parse_progress(session_key, 'start', '🚀 开始AI大模型解析...', 5)

    valid_lines = []
    line_numbers = []
    lines = content.split('\n')
    total_lines = len(lines)

    if session_key:
        update_parse_progress(session_key, 'extract', f'📄 提取有效行（共{total_lines}行）...', 10)

    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        # 跳过标题行
        if line.startswith('#') or line.startswith('##'):
            continue
        # 跳过纯累计/余额行
        if re.match(r'^(累计|余额|剩余)\s*[:：]', line):
            continue
        valid_lines.append(line)
        line_numbers.append(line_num)

    if not valid_lines:
        return {
            'records': [],
            'prompt': '',
            'response': '',
            'error': '未找到有效记录行'
        }

    if session_key:
        update_parse_progress(session_key, 'extract_done', f'✓ 提取完成，有效行数: {len(valid_lines)}', 15)

    # 使用AI解析
    try:
        if session_key:
            update_parse_progress(session_key, 'ai_connect', '🔌 连接Claude AI大模型...', 20)
            update_parse_progress(session_key, 'ai_start', f'🤖 AI大模型正在解析 {len(valid_lines)} 行记录...', 25)

        print(f"使用AI解析 {len(valid_lines)} 行记录...")

        def _ai_progress(current_batch, total_batches):
            if session_key and total_batches > 0:
                progress = 30 + int((current_batch / total_batches) * 30)
                update_parse_progress(
                    session_key, 'ai_progress',
                    f'🤖 AI解析中... 批次 {current_batch}/{total_batches}', progress
                )

        ai_result = parse_with_ai(valid_lines, progress_callback=_ai_progress)

        # 保存完整的prompt和response到session
        if session_key:
            prompt_val = ai_result.get('prompt', '')
            response_val = ai_result.get('response', '')
            error_val = ai_result.get('error', '')
            print(f"[DEBUG] Saving ai_parse_details - prompt length: {len(prompt_val)}")
            print(f"[DEBUG] Saving ai_parse_details - response length: {len(response_val)}")
            print(f"[DEBUG] Saving ai_parse_details - response preview: {response_val[:200] if response_val else '(empty)'}")
            print(f"[DEBUG] Saving ai_parse_details - error: {error_val if error_val else 'None'}")
            session['ai_parse_details'] = {
                'prompt': prompt_val,
                'response': response_val,
                'error': error_val
            }
            session.modified = True
            print(f"[DEBUG] Session ai_parse_details saved successfully")

        # 检查是否有错误
        if ai_result.get('error'):
            error_msg = ai_result['error']
            if session_key:
                update_parse_progress(session_key, 'ai_error', f'❌ AI解析失败: {error_msg[:100]}', 100)
            return {
                'records': [],
                'prompt': ai_result.get('prompt', ''),
                'response': ai_result.get('response', ''),
                'error': error_msg
            }

        records = ai_result.get('records', [])

        if not records:
            if session_key:
                update_parse_progress(session_key, 'ai_empty', '⚠️ AI返回空结果', 100)
            return {
                'records': [],
                'prompt': ai_result.get('prompt', ''),
                'response': ai_result.get('response', ''),
                'error': 'AI未返回任何解析结果'
            }

        if session_key:
            update_parse_progress(session_key, 'ai_done',
                f'✓ AI大模型解析完成！识别 {len(records)} 条记录', 60)

        print(f"AI解析成功，返回 {len(records)} 条记录")

        # 更新line_num为实际文件行号（支持AI展开日期范围，多记录对应同一行）
        for record in records:
            batch_line_num = record.get('line_num', 0)
            if 1 <= batch_line_num <= len(line_numbers):
                record['line_num'] = line_numbers[batch_line_num - 1]

        # 根据节假日配置修正 overtime_type / leave_type
        conn = get_db()
        try:
            for record in records:
                parsed_date_str = record.get('parsed_date')
                if not parsed_date_str:
                    continue
                try:
                    d = date.fromisoformat(parsed_date_str)
                except ValueError:
                    continue

                if record.get('type') == 'overtime':
                    date_type = get_date_type(conn, d)
                    if date_type in ('weekend', 'adjusted_holiday'):
                        record['overtime_type'] = 'weekend'
                    elif date_type == 'statutory_holiday':
                        record['overtime_type'] = 'holiday'
                    elif date_type in ('workday', 'adjusted_workday'):
                        # 保留AI识别的工作日子类型，未识别则默认晚上
                        ai_subtype = record.get('overtime_type')
                        if ai_subtype not in ('weekday_morning', 'weekday_lunch', 'weekday_evening', 'weekday_mixed'):
                            record['overtime_type'] = 'weekday_evening'
                elif record.get('type') == 'leave':
                    if not record.get('leave_type'):
                        record['leave_type'] = 'personal'
        finally:
            conn.close()

        # 添加置信度分级和异常检测
        if session_key:
            update_parse_progress(session_key, 'process', '📊 分析置信度和异常...', 75)

        processed_records = process_parse_results(records)

        if session_key:
            high = len([r for r in processed_records if r.get('confidence_level') == 'HIGH'])
            medium = len([r for r in processed_records if r.get('confidence_level') == 'MEDIUM'])
            low = len([r for r in processed_records if r.get('confidence_level') == 'LOW'])
            update_parse_progress(session_key, 'complete', f'🎉 完成！共{len(processed_records)}条 高:{high} 中:{medium} 低:{low}', 100)

        return {
            'records': processed_records,
            'prompt': ai_result.get('prompt', ''),
            'response': ai_result.get('response', ''),
            'error': None
        }

    except Exception as e:
        error_msg = f"AI解析异常: {str(e)}"
        print(error_msg)
        if session_key:
            update_parse_progress(session_key, 'ai_error', f'❌ {error_msg[:100]}', 100)
        return {
            'records': [],
            'prompt': '',
            'response': '',
            'error': error_msg
        }


@bp.route('/import/', methods=['GET', 'POST'])
def import_records():
    """导入记录页面 - 第一步：上传和预览"""
    if request.method == 'POST':
        # 处理文件上传
        if 'file' not in request.files:
            flash('没有选择文件', 'error')
            return redirect(request.url)

        file = request.files['file']
        employee_id = request.form.get('employee_id')

        if file.filename == '':
            flash('没有选择文件', 'error')
            return redirect(request.url)

        if not employee_id:
            flash('请选择员工', 'error')
            return redirect(request.url)

        # 生成唯一会话key用于进度跟踪
        import uuid
        session_key = str(uuid.uuid4())[:8]
        session['current_parse_key'] = session_key
        session[f'parse_progress_{session_key}'] = []

        try:
            # 读取文件内容
            content = file.read().decode('utf-8')

            # 解析记录（仅AI解析）
            parse_result = parse_file_content(content, session_key=session_key)

            # 检查是否有错误
            if parse_result.get('error'):
                error_msg = parse_result['error']
                # 获取员工信息
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM employees WHERE employee_id = ?", (employee_id,))
                row = cursor.fetchone()
                conn.close()
                employee_name = row['name'] if row else 'Unknown'

                # 渲染错误页面，不跳转
                return render_template('import_error.html',
                    error=error_msg,
                    prompt=parse_result.get('prompt', ''),
                    response=parse_result.get('response', ''),
                    filename=file.filename,
                    employee_id=employee_id,
                    employee_name=employee_name,
                    file_content=content[:2000]  # 显示部分内容
                )

            records = parse_result.get('records', [])

            if not records:
                error_msg = 'AI未返回任何解析结果'
                # 获取员工信息
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM employees WHERE employee_id = ?", (employee_id,))
                row = cursor.fetchone()
                conn.close()
                employee_name = row['name'] if row else 'Unknown'

                # 渲染错误页面，不跳转
                return render_template('import_error.html',
                    error=error_msg,
                    prompt=parse_result.get('prompt', ''),
                    response=parse_result.get('response', ''),
                    filename=file.filename,
                    employee_id=employee_id,
                    employee_name=employee_name,
                    file_content=content[:2000]
                )

            # 获取员工信息
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM employees WHERE employee_id = ?", (employee_id,))
            row = cursor.fetchone()
            conn.close()

            employee_name = row['name'] if row else 'Unknown'

            # 存储到 session，供确认页面使用
            session['import_preview'] = {
                'employee_id': employee_id,
                'employee_name': employee_name,
                'filename': file.filename,
                'records': records,
                'total_count': len(records),
                'high_confidence': len([r for r in records if r.get('confidence_level') == 'HIGH']),
                'medium_confidence': len([r for r in records if r.get('confidence_level') == 'MEDIUM']),
                'low_confidence': len([r for r in records if r.get('confidence_level') == 'LOW']),
                'has_anomalies': any(r.get('has_anomaly') for r in records),
            }

            # 跳转到预览页面
            return redirect(url_for('records.import_preview'))

        except Exception as e:
            flash(f'文件解析失败: {str(e)}', 'error')
            return redirect(request.url)

    # 获取员工列表用于选择
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

    return render_template('import.html', employees=employees)


@bp.route('/import/preview/')
def import_preview():
    """导入预览页面 - 第二步：查看和确认"""
    preview_data = session.get('import_preview')

    if not preview_data:
        flash('没有待导入的数据，请先上传文件', 'error')
        return redirect(url_for('records.import_records'))

    # 获取AI解析详情
    ai_details = session.get('ai_parse_details', {})
    print(f"[DEBUG import_preview] ai_details keys: {ai_details.keys() if ai_details else 'empty'}")
    print(f"[DEBUG import_preview] response length: {len(ai_details.get('response', '')) if ai_details else 0}")
    print(f"[DEBUG import_preview] session keys: {list(session.keys())}")

    return render_template('import_preview.html', preview=preview_data, ai_details=ai_details)


@bp.route('/import/confirm/', methods=['POST'])
def import_confirm():
    """确认导入 - 第三步：保存到数据库"""
    preview_data = session.get('import_preview')

    if not preview_data:
        flash('导入会话已过期，请重新上传文件', 'error')
        return redirect(url_for('records.import_records'))

    employee_id = preview_data['employee_id']

    # 从表单获取编辑后的记录数据
    records_data = request.form.to_dict(flat=False)

    # 获取所有记录（通过records[index][field]格式）
    record_indices = set()
    for key in records_data.keys():
        match = re.match(r'records\[(\d+)\]\[(\w+)\]', key)
        if match:
            record_indices.add(int(match.group(1)))

    if not record_indices:
        flash('没有要导入的记录', 'warning')
        return redirect(url_for('records.import_preview'))

    # 获取选中的记录（通过checkbox）
    selected_indices = request.form.getlist('selected_records')
    selected_indices = set(int(i) for i in selected_indices)

    # 只保留选中的记录
    record_indices = record_indices.intersection(selected_indices)

    # 构建记录列表
    records_to_store = []
    errors = []

    for idx in sorted(record_indices):
        try:
            prefix = f'records[{idx}]'
            record_date_str = request.form.get(f'{prefix}[date]', '').strip()
            record_type = request.form.get(f'{prefix}[type]', '').strip()
            record_subtype = request.form.get(f'{prefix}[subtype]', '').strip()
            record_hours = request.form.get(f'{prefix}[hours]', '0').strip()
            record_content = request.form.get(f'{prefix}[content]', '').strip()

            if not record_date_str:
                errors.append(f"记录#{idx + 1}: 缺少日期")
                continue

            if not record_type or record_type == 'unknown':
                errors.append(f"记录#{idx + 1}: 缺少类型")
                continue

            try:
                hours = float(record_hours) if record_hours else 0
            except ValueError:
                hours = 0

            record_date = date.fromisoformat(record_date_str)

            store_record = {
                'type': record_type,
                'employee_id': employee_id,
                'date': record_date,
                'hours': hours,
                'description': record_content,
            }

            if record_type == 'overtime':
                store_record['overtime_type'] = record_subtype or 'weekday_evening'
            elif record_type == 'leave':
                store_record['leave_type'] = record_subtype or 'personal'
            elif record_type == 'comp_off':
                pass  # comp_off 只需要基础字段
            else:
                errors.append(f"记录#{idx + 1}: 未知的记录类型 '{record_type}'")
                continue

            records_to_store.append(store_record)

        except Exception as e:
            errors.append(f"记录#{idx + 1}: {str(e)}")

    if not records_to_store:
        flash('没有有效的记录可以导入，请检查数据', 'error')
        if errors:
            for error in errors[:5]:
                flash(error, 'warning')
        return redirect(url_for('records.import_preview'))

    conn = get_db()
    try:
        session_id = store_batch_records_with_session(
            conn,
            employee_id=employee_id,
            records=records_to_store,
            file_name=preview_data.get('filename', 'unknown')
        )

        # 清除 session
        session.pop('import_preview', None)
        session.pop('ai_parse_details', None)

        success_count = len(records_to_store)
        error_count = len(errors)

        flash(f'导入完成: 成功 {success_count} 条, 表单校验失败 {error_count} 条', 'success')
        if errors:
            for error in errors[:5]:
                flash(error, 'warning')

    except StorageError as e:
        flash(f'导入失败: {str(e)}', 'error')
    except Exception as e:
        flash(f'导入失败: {str(e)}', 'error')
    finally:
        conn.close()

    return redirect(url_for('records.import_records'))


@bp.route('/import/cancel/')
def import_cancel():
    """取消导入"""
    session.pop('import_preview', None)
    flash('已取消导入', 'info')
    return redirect(url_for('records.import_records'))


@bp.route('/import/employee/<employee_id>/', methods=['GET', 'POST'])
def import_for_employee(employee_id: str):
    """为指定员工导入记录"""
    conn = get_db()
    cursor = conn.cursor()

    # 获取员工信息
    cursor.execute("SELECT employee_id, name FROM employees WHERE employee_id = ?", (employee_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        flash('员工不存在', 'error')
        return redirect(url_for('employees.list_employees'))

    employee = dict(row)

    if request.method == 'POST':
        # 处理文件上传（与主导入逻辑相同）
        if 'file' not in request.files:
            flash('没有选择文件', 'error')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('没有选择文件', 'error')
            return redirect(request.url)

        try:
            content = file.read().decode('utf-8')
            records = parse_file_content(content)

            if not records:
                flash('未从文件中解析出任何记录', 'warning')
                return redirect(request.url)

            session['import_preview'] = {
                'employee_id': employee_id,
                'employee_name': employee['name'],
                'filename': file.filename,
                'records': records,
                'total_count': len(records),
                'high_confidence': len([r for r in records if r.get('confidence_level') == 'HIGH']),
                'medium_confidence': len([r for r in records if r.get('confidence_level') == 'MEDIUM']),
                'low_confidence': len([r for r in records if r.get('confidence_level') == 'LOW']),
                'has_anomalies': any(r.get('has_anomaly') for r in records),
            }

            return redirect(url_for('records.import_preview'))

        except Exception as e:
            flash(f'文件解析失败: {str(e)}', 'error')
            return redirect(request.url)

    return render_template('import.html', employees=[employee], selected_employee=employee)


@bp.route('/import/progress/')
def import_progress():
    """获取解析进度API"""
    session_key = session.get('current_parse_key')
    if not session_key:
        return jsonify({'progress': [], 'latest': None})

    progress_data = session.get(f'parse_progress_{session_key}', [])
    latest = progress_data[-1] if progress_data else None

    return jsonify({
        'progress': progress_data,
        'latest': latest,
        'total_steps': len(progress_data)
    })