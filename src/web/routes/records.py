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
from services.holiday_service import get_date_type

bp = Blueprint('records', __name__, url_prefix='/records')


def _hours_to_duration(hours_float: float) -> tuple:
    """
    将浮点小时拆分为整数小时和分钟
    例如 2.5 -> (2, 30), 4.0 -> (4, 0)
    """
    total_minutes = int(round(hours_float * 60))
    return total_minutes // 60, total_minutes % 60


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
        # 处理文件上传（支持多文件）
        files = request.files.getlist('file')
        employee_id = request.form.get('employee_id')

        if not files or all(f.filename == '' for f in files):
            flash('没有选择文件', 'error')
            return redirect(request.url)

        if not employee_id:
            flash('请选择员工', 'error')
            return redirect(request.url)

        # 过滤掉空文件项
        files = [f for f in files if f.filename != '']
        if not files:
            flash('没有选择文件', 'error')
            return redirect(request.url)

        # 获取员工信息
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM employees WHERE employee_id = ?", (employee_id,))
        row = cursor.fetchone()
        conn.close()
        employee_name = row['name'] if row else 'Unknown'

        # 生成唯一会话key用于进度跟踪
        import uuid
        session_key = str(uuid.uuid4())[:8]
        session['current_parse_key'] = session_key
        session[f'parse_progress_{session_key}'] = []

        all_records = []
        combined_filename_parts = []
        combined_prompt = []
        combined_response = []
        first_error = None
        error_filename = None
        error_content = None

        try:
            for idx, file in enumerate(files):
                # 读取文件内容
                content = file.read().decode('utf-8')
                combined_filename_parts.append(file.filename)

                # 解析记录（仅AI解析）
                file_session_key = f"{session_key}_{idx}"
                parse_result = parse_file_content(content, session_key=file_session_key)

                # 收集 prompt / response
                if parse_result.get('prompt'):
                    combined_prompt.append(f"=== {file.filename} ===\n{parse_result['prompt']}")
                if parse_result.get('response'):
                    combined_response.append(f"=== {file.filename} ===\n{parse_result['response']}")

                # 检查是否有错误
                if parse_result.get('error'):
                    first_error = parse_result['error']
                    error_filename = file.filename
                    error_content = content[:2000]
                    break

                records = parse_result.get('records', [])
                if not records:
                    first_error = 'AI未返回任何解析结果'
                    error_filename = file.filename
                    error_content = content[:2000]
                    break

                all_records.extend(records)

            # 如果任一文件解析失败，渲染错误页面
            if first_error:
                return render_template('import_error.html',
                    error=first_error,
                    prompt='\n\n'.join(combined_prompt),
                    response='\n\n'.join(combined_response),
                    filename=error_filename,
                    employee_id=employee_id,
                    employee_name=employee_name,
                    file_content=error_content or ''
                )

            if not all_records:
                error_msg = 'AI未返回任何解析结果'
                return render_template('import_error.html',
                    error=error_msg,
                    prompt='\n\n'.join(combined_prompt),
                    response='\n\n'.join(combined_response),
                    filename=combined_filename_parts[0] if combined_filename_parts else 'unknown',
                    employee_id=employee_id,
                    employee_name=employee_name,
                    file_content=''
                )

            # 生成组合文件名描述
            if len(combined_filename_parts) == 1:
                combined_filename = combined_filename_parts[0]
            elif len(combined_filename_parts) <= 3:
                combined_filename = ', '.join(combined_filename_parts) + f" ({len(combined_filename_parts)} 个文件)"
            else:
                combined_filename = ', '.join(combined_filename_parts[:3]) + f"... ({len(combined_filename_parts)} 个文件)"

            # 保存AI解析详情到session
            if combined_prompt or combined_response:
                session['ai_parse_details'] = {
                    'prompt': '\n\n'.join(combined_prompt),
                    'response': '\n\n'.join(combined_response),
                    'error': ''
                }
                session.modified = True

            # 存储到 session，供确认页面使用
            session['import_preview'] = {
                'employee_id': employee_id,
                'employee_name': employee_name,
                'filename': combined_filename,
                'records': all_records,
                'total_count': len(all_records),
                'high_confidence': len([r for r in all_records if r.get('confidence_level') == 'HIGH']),
                'medium_confidence': len([r for r in all_records if r.get('confidence_level') == 'MEDIUM']),
                'low_confidence': len([r for r in all_records if r.get('confidence_level') == 'LOW']),
                'has_anomalies': any(r.get('has_anomaly') for r in all_records),
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
    cursor = conn.cursor()
    success_count = 0
    error_count = 0
    insert_count = 0
    update_count = 0

    try:
        # 创建导入会话
        cursor.execute("""
            INSERT INTO import_sessions
            (file_path, status, total_records, processed_records, error_records)
            VALUES (?, 'pending', ?, 0, 0)
        """, (preview_data.get('filename', 'unknown'), len(records_to_store)))
        session_id = cursor.lastrowid

        for record in records_to_store:
            try:
                record_type = record['type']
                record_date = record['date']
                hours, minutes = _hours_to_duration(record.get('hours', 0))
                total_minutes = hours * 60 + minutes
                description = record.get('description', '')

                if record_type == 'overtime':
                    overtime_type = record.get('overtime_type', 'weekday_evening')
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
                                created_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (hours, minutes, total_minutes, description, session_id, existing['id']))
                        update_count += 1
                    else:
                        cursor.execute("""
                            INSERT INTO overtime_records
                            (employee_id, work_date, duration_hours, duration_minutes,
                             total_minutes, overtime_type, description, source_import_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            employee_id, record_date, hours, minutes,
                            total_minutes, overtime_type,
                            description, session_id
                        ))
                        insert_count += 1
                    success_count += 1
                elif record_type == 'leave':
                    leave_type = record.get('leave_type', 'personal')
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
                                created_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (hours, minutes, total_minutes, description, session_id, existing['id']))
                        update_count += 1
                    else:
                        cursor.execute("""
                            INSERT INTO leave_records
                            (employee_id, leave_date, duration_hours, duration_minutes,
                             total_minutes, leave_type, description, source_import_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            employee_id, record_date, hours, minutes,
                            total_minutes, leave_type,
                            description, session_id
                        ))
                        insert_count += 1
                    success_count += 1
                elif record_type == 'comp_off':
                    cursor.execute(
                        "SELECT id FROM comp_off_usage_records WHERE employee_id = ? AND usage_date = ?",
                        (employee_id, record_date)
                    )
                    existing = cursor.fetchone()
                    if existing:
                        cursor.execute("""
                            UPDATE comp_off_usage_records
                            SET duration_hours = ?, duration_minutes = ?,
                                total_minutes = ?, description = ?,
                                created_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (hours, minutes, total_minutes, description, existing['id']))
                        update_count += 1
                    else:
                        cursor.execute("""
                            INSERT INTO comp_off_usage_records
                            (employee_id, usage_date, duration_hours, duration_minutes,
                             total_minutes, description)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            employee_id, record_date, hours, minutes,
                            total_minutes, description
                        ))
                        insert_count += 1
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                errors.append(str(e))

        # 更新导入会话统计
        cursor.execute("""
            UPDATE import_sessions
            SET processed_records = ?, error_records = ?,
                status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (success_count, error_count, session_id))

        conn.commit()

        # 清除 session
        session.pop('import_preview', None)
        session.pop('ai_parse_details', None)

        flash(f'导入完成: 成功 {success_count} 条 (新增 {insert_count} 条, 更新 {update_count} 条), 失败 {error_count} 条', 'success')
        if errors:
            for error in errors[:5]:
                flash(error, 'warning')

    except Exception as e:
        conn.rollback()
        flash(f'导入失败: {str(e)}', 'error')
        flash('您可以返回预览页面检查数据后重试，或取消导入', 'info')
        # 保留 session 中的预览数据，让用户可以重试
        return redirect(url_for('records.import_preview'))
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
        # 处理文件上传（支持多文件，与主导入逻辑保持一致）
        files = request.files.getlist('file')

        if not files or all(f.filename == '' for f in files):
            flash('没有选择文件', 'error')
            return redirect(request.url)

        files = [f for f in files if f.filename != '']
        if not files:
            flash('没有选择文件', 'error')
            return redirect(request.url)

        all_records = []
        combined_filename_parts = []
        first_error = None

        try:
            for file in files:
                content = file.read().decode('utf-8')
                combined_filename_parts.append(file.filename)
                parse_result = parse_file_content(content)

                if parse_result.get('error'):
                    first_error = f"{file.filename}: {parse_result['error']}"
                    break

                records = parse_result.get('records', [])
                if not records:
                    first_error = f"{file.filename}: AI未返回任何解析结果"
                    break

                all_records.extend(records)

            if first_error:
                flash(first_error, 'error')
                return redirect(request.url)

            if not all_records:
                flash('未从文件中解析出任何记录', 'warning')
                return redirect(request.url)

            if len(combined_filename_parts) == 1:
                combined_filename = combined_filename_parts[0]
            elif len(combined_filename_parts) <= 3:
                combined_filename = ', '.join(combined_filename_parts) + f" ({len(combined_filename_parts)} 个文件)"
            else:
                combined_filename = ', '.join(combined_filename_parts[:3]) + f"... ({len(combined_filename_parts)} 个文件)"

            session['import_preview'] = {
                'employee_id': employee_id,
                'employee_name': employee['name'],
                'filename': combined_filename,
                'records': all_records,
                'total_count': len(all_records),
                'high_confidence': len([r for r in all_records if r.get('confidence_level') == 'HIGH']),
                'medium_confidence': len([r for r in all_records if r.get('confidence_level') == 'MEDIUM']),
                'low_confidence': len([r for r in all_records if r.get('confidence_level') == 'LOW']),
                'has_anomalies': any(r.get('has_anomaly') for r in all_records),
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


@bp.route('/search/')
def search_records():
    """全局记录查询页面 - 按日期范围和类型搜索跨员工记录"""
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    record_type = request.args.get('record_type', 'all').strip()
    employee_id = request.args.get('employee_id', '').strip()

    results = []
    employees = []

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT employee_id, name FROM employees ORDER BY name")
        employees = [dict(row) for row in cursor.fetchall()]

        has_filter = start_date and end_date

        if has_filter:
            types_to_query = []
            if record_type == 'all':
                types_to_query = ['overtime', 'leave', 'comp_off']
            elif record_type in ('overtime', 'leave', 'comp_off'):
                types_to_query = [record_type]

            for rt in types_to_query:
                if rt == 'overtime':
                    sql = """
                        SELECT
                            o.id,
                            o.employee_id,
                            e.name as employee_name,
                            o.work_date as record_date,
                            'overtime' as record_type,
                            o.overtime_type as subtype,
                            o.duration_hours,
                            o.duration_minutes,
                            o.description
                        FROM overtime_records o
                        JOIN employees e ON o.employee_id = e.employee_id
                        WHERE o.work_date BETWEEN ? AND ?
                    """
                    params = [start_date, end_date]
                    if employee_id:
                        sql += " AND o.employee_id = ?"
                        params.append(employee_id)
                    sql += " ORDER BY o.work_date DESC"
                    cursor.execute(sql, params)

                elif rt == 'leave':
                    sql = """
                        SELECT
                            l.id,
                            l.employee_id,
                            e.name as employee_name,
                            l.leave_date as record_date,
                            'leave' as record_type,
                            l.leave_type as subtype,
                            l.duration_hours,
                            l.duration_minutes,
                            l.description
                        FROM leave_records l
                        JOIN employees e ON l.employee_id = e.employee_id
                        WHERE l.leave_date BETWEEN ? AND ?
                    """
                    params = [start_date, end_date]
                    if employee_id:
                        sql += " AND l.employee_id = ?"
                        params.append(employee_id)
                    sql += " ORDER BY l.leave_date DESC"
                    cursor.execute(sql, params)

                elif rt == 'comp_off':
                    sql = """
                        SELECT
                            c.id,
                            c.employee_id,
                            e.name as employee_name,
                            c.usage_date as record_date,
                            'comp_off' as record_type,
                            '' as subtype,
                            c.duration_hours,
                            c.duration_minutes,
                            c.description
                        FROM comp_off_usage_records c
                        JOIN employees e ON c.employee_id = e.employee_id
                        WHERE c.usage_date BETWEEN ? AND ?
                    """
                    params = [start_date, end_date]
                    if employee_id:
                        sql += " AND c.employee_id = ?"
                        params.append(employee_id)
                    sql += " ORDER BY c.usage_date DESC"
                    cursor.execute(sql, params)

                rows = [dict(row) for row in cursor.fetchall()]
                results.extend(rows)
    except sqlite3.Error as e:
        flash(f'查询失败: {e}', 'error')
    finally:
        conn.close()

    return render_template(
        'record_search.html',
        results=results,
        employees=employees,
        start_date=start_date,
        end_date=end_date,
        record_type=record_type,
        employee_id=employee_id
    )
