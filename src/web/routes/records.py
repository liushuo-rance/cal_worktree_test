"""
记录导入路由
支持文件上传、解析预览、确认导入三步流程
"""

import sqlite3
import re
import json
import uuid
from datetime import date, datetime
from typing import List, Dict, Any, Optional

from flask import (
    Blueprint, render_template, request, flash, redirect,
    url_for, session, jsonify, Response, stream_with_context,
    current_app
)

from web.utils import get_db
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from parsers.date_parser import parse_date, parse_date_range, DateParseError
from parsers.hours_parser import parse_hours
from parsers.type_parser import classify_record_type
from services.parse_result_processor import process_parse_results
from services.ai_parser_service import parse_with_ai, _normalize_overtime_type, get_ai_parser, AI_PARSER_BATCH_SIZE
from services.holiday_service import get_date_type
from services.review_service import add_to_review_queue
from services.storage_service import _create_comp_off_balance
from services import import_service as import_svc

bp = Blueprint('records', __name__, url_prefix='/records')


def _hours_to_duration(hours_float: float) -> tuple:
    """
    将浮点小时拆分为整数小时和分钟
    例如 2.5 -> (2, 30), 4.0 -> (4, 0)
    """
    total_minutes = int(round(hours_float * 60))
    return total_minutes // 60, total_minutes % 60


def update_parse_progress(session_key: str, step: str, message: str, progress: int):
    """更新解析进度到 session"""
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


def parse_record_line(line: str, line_num: int = 0) -> Optional[Dict[str, Any]]:
    """
    解析单行记录（本地解析器回退）

    Args:
        line: 原始行文本，如 "2025.01.15 晚上加班2小时，完成项目文档"
        line_num: 行号

    Returns:
        解析结果字典，解析失败返回 None
    """
    original_line = line.strip()
    if not original_line or original_line.startswith('#') or original_line.startswith('##'):
        return None

    line = re.sub(r'\*\*', '', original_line)

    result = {
        'raw_line': original_line,
        'line_num': line_num,
        'type': 'unknown',
        'confidence': 0.0,
        'parsed_hours': None,
        'parsed_date': None,
        'weekday': None
    }

    date_match = re.match(r'^(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})[,，\s]+(.*)$', line)
    if date_match:
        date_str = date_match.group(1)
        content = date_match.group(2)
        try:
            parsed_date = parse_date(date_str)
            result['parsed_date'] = parsed_date.isoformat()
            result['date_str'] = date_str
            weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            result['weekday'] = weekdays[parsed_date.weekday()]
        except DateParseError:
            result['date_str'] = date_str
            result['parse_error'] = '日期解析失败'
    else:
        range_match = re.match(r'^(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}\s*[-~至]\s*\d{1,2})[,，\s]+(.*)$', line)
        if range_match:
            date_str = range_match.group(1)
            content = range_match.group(2)
            result['date_str'] = date_str
            result['is_range'] = True
            try:
                start_date, end_date = parse_date_range(date_str)
                result['parsed_date'] = start_date.isoformat()
                result['end_date'] = end_date.isoformat()
            except DateParseError as e:
                result['parse_error'] = f'日期范围解析失败: {str(e)}'
        else:
            content = line
            result['parse_error'] = '未找到日期'

    afternoon_evening_match = re.search(r'(下午|晚上)\s*\d+\.?\d*\s*小时', content)
    if afternoon_evening_match and '请假' not in content and '调休' not in content and '休假' not in content:
        result['type'] = 'overtime'
        result['overtime_type'] = 'weekday_evening'
        result['confidence'] = 0.85
    else:
        type_result = classify_record_type(content)
        result.update(type_result)

    if result['type'] in ['overtime', 'leave', 'comp_off']:
        hours_result = parse_hours(content)
        if hours_result:
            hours, minutes, total_minutes = hours_result
            result['parsed_hours'] = hours + minutes / 60
            result['total_minutes'] = total_minutes
        else:
            if result['type'] == 'leave':
                result['parsed_hours'] = 8.0
            elif result['type'] == 'comp_off':
                result['parsed_hours'] = 4.0

    result['content'] = content
    return result


def _extract_valid_lines(content: str) -> tuple:
    """提取有效行和原始行号"""
    valid_lines = []
    line_numbers = []
    for line_num, line in enumerate(content.split('\n'), 1):
        line = line.strip()
        if not line:
            continue
        if line.startswith('#') or line.startswith('##'):
            continue
        if re.match(r'^(累计|余额|剩余)\s*[:：]', line):
            continue
        valid_lines.append(line)
        line_numbers.append(line_num)
    return valid_lines, line_numbers


def _apply_holiday_correction(conn: sqlite3.Connection, records: List[Dict[str, Any]]) -> None:
    """根据节假日配置修正 overtime_type / leave_type"""
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
                ai_subtype = record.get('overtime_type')
                if ai_subtype not in ('weekday_morning', 'weekday_lunch', 'weekday_evening', 'weekday_mixed'):
                    record['overtime_type'] = 'weekday_evening'
        elif record.get('type') == 'leave':
            if not record.get('leave_type'):
                record['leave_type'] = 'personal'


def _mark_duplicates(conn: sqlite3.Connection, employee_id: str, records: List[Dict[str, Any]]) -> int:
    """标记数据库中已存在的重复记录，返回重复数量"""
    cursor = conn.cursor()
    duplicate_count = 0
    for record in records:
        parsed_date = record.get('parsed_date')
        rtype = record.get('type')
        if not parsed_date or rtype == 'unknown':
            record['is_duplicate'] = False
            continue
        existing = None
        if rtype == 'overtime':
            subtype = record.get('overtime_type', 'weekday_evening')
            cursor.execute(
                "SELECT duration_hours, duration_minutes, total_minutes, description FROM overtime_records WHERE employee_id = ? AND work_date = ? AND overtime_type = ?",
                (employee_id, parsed_date, subtype)
            )
            existing = cursor.fetchone()
        elif rtype == 'leave':
            subtype = record.get('leave_type', 'personal')
            cursor.execute(
                "SELECT duration_hours, duration_minutes, total_minutes, description FROM leave_records WHERE employee_id = ? AND leave_date = ? AND leave_type = ?",
                (employee_id, parsed_date, subtype)
            )
            existing = cursor.fetchone()
        elif rtype == 'comp_off':
            cursor.execute(
                "SELECT duration_hours, duration_minutes, total_minutes, description FROM comp_off_usage_records WHERE employee_id = ? AND usage_date = ?",
                (employee_id, parsed_date)
            )
            existing = cursor.fetchone()
        if existing:
            record['is_duplicate'] = True
            record['duplicate_existing'] = dict(existing)
            duplicate_count += 1
        else:
            record['is_duplicate'] = False
    return duplicate_count


def _is_spreadsheet(filename: str) -> bool:
    """判断文件名是否为CSV或Excel文件"""
    if not filename:
        return False
    lower_name = filename.lower()
    return lower_name.endswith('.csv') or lower_name.endswith('.xlsx') or lower_name.endswith('.xls')


def _process_spreadsheet_file(file, employee_id: str) -> Dict[str, Any]:
    """
    处理CSV/Excel文件上传，返回可直接写入session的预览数据

    Returns:
        {
            'records': List[Dict],
            'duplicate_count': int,
            'errors': List[str],
            'filename': str,
        }
    """
    import tempfile

    filename = file.filename
    suffix = os.path.splitext(filename)[1].lower()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        if suffix == '.csv':
            raw_rows = import_svc.read_csv_file(tmp_path)
        else:
            raw_rows = import_svc.read_excel_file(tmp_path)

        normalize_result = import_svc.normalize_import_rows(raw_rows, employee_id=employee_id)
        records = normalize_result.get('records', [])
        errors = normalize_result.get('errors', [])

        conn = get_db()
        try:
            _apply_holiday_correction(conn, records)
            duplicate_count = _mark_duplicates(conn, employee_id, records)
        finally:
            conn.close()

        from services.parse_result_processor import process_parse_results
        processed_records = process_parse_results(records)

        return {
            'records': processed_records,
            'duplicate_count': duplicate_count,
            'errors': [e['message'] for e in errors],
            'filename': filename,
        }
    finally:
        os.unlink(tmp_path)


def parse_file_content(content: str, session_key: str = None) -> Dict[str, Any]:
    """
    解析文件内容，优先使用AI大模型解析，失败时回退到本地解析器

    Args:
        content: 文件内容
        session_key: session key用于进度跟踪

    Returns:
        包含解析结果、prompt、response的字典
    """
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
        if line.startswith('#') or line.startswith('##'):
            continue
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

    # 1. 尝试 AI 解析
    try:
        if session_key:
            update_parse_progress(session_key, 'ai_connect', '🔌 连接Claude AI大模型...', 20)
            update_parse_progress(session_key, 'ai_start', f'🤖 AI大模型正在解析 {len(valid_lines)} 行记录...', 25)

        ai_result = parse_with_ai(valid_lines)

        if session_key:
            prompt_val = ai_result.get('prompt', '')
            response_val = ai_result.get('response', '')
            error_val = ai_result.get('error', '')
            session['ai_parse_details'] = {
                'prompt': prompt_val,
                'response': response_val,
                'error': error_val
            }
            session.modified = True

        if ai_result.get('error'):
            error_msg = ai_result['error']
            if session_key:
                update_parse_progress(session_key, 'ai_error', f'❌ AI解析失败: {error_msg[:100]}', 100)
            # 继续回退到本地解析器
            raise Exception(error_msg)

        records = ai_result.get('records', [])
        if not records:
            if session_key:
                update_parse_progress(session_key, 'ai_empty', '⚠️ AI返回空结果', 100)
            raise Exception('AI未返回任何解析结果')

        if session_key:
            batch_size = AI_PARSER_BATCH_SIZE
            batch_count = (len(valid_lines) + batch_size - 1) // batch_size
            update_parse_progress(session_key, 'ai_batches',
                f'📦 共分{batch_count}批解析（共{len(valid_lines)}行，每批{batch_size}行）', 35)
            for i, record in enumerate(records[:3]):
                line_preview = valid_lines[i][:30] if i < len(valid_lines) else ''
                update_parse_progress(session_key, 'ai_progress',
                    f'✓ 第{i+1}行: {line_preview}... → {record.get("type", "unknown")}', 40 + i * 10)
            update_parse_progress(session_key, 'ai_done',
                f'✓ AI大模型解析完成！识别 {len(records)} 条记录', 60)

        for i, record in enumerate(records):
            if i < len(line_numbers):
                record['line_num'] = line_numbers[i]

        if session_key:
            update_parse_progress(session_key, 'process', '📊 分析置信度和异常...', 75)

        conn = get_db()
        try:
            _apply_holiday_correction(conn, records)
        finally:
            conn.close()

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
    except Exception:
        pass

    # 2. AI 失败或返回空，回退到本地解析器
    if session_key:
        update_parse_progress(session_key, 'fallback', '🔄 AI解析失败，回退到本地解析器...', 50)

    fallback_records = []
    for i, line in enumerate(valid_lines):
        parsed = parse_record_line(line, line_numbers[i])
        if parsed:
            fallback_records.append(parsed)

    if fallback_records:
        conn = get_db()
        try:
            _apply_holiday_correction(conn, fallback_records)
        finally:
            conn.close()
        processed_records = process_parse_results(fallback_records)
        if session_key:
            update_parse_progress(session_key, 'complete', f'🎉 本地解析完成！共{len(processed_records)}条', 100)
        return {
            'records': processed_records,
            'prompt': '',
            'response': '',
            'error': None
        }

    return {
        'records': [],
        'prompt': '',
        'response': '',
        'error': '未找到有效记录行'
    }


@bp.route('/import/', methods=['GET', 'POST'])
def import_records():
    """导入记录页面 - 第一步：上传和预览"""
    if request.method == 'POST':
        employee_id = request.form.get('employee_id')
        if not employee_id:
            flash('请选择员工', 'error')
            return redirect(request.url)

        file = request.files.get('file')
        text_content = request.form.get('text_content', '').strip()

        if file and file.filename:
            filename = file.filename
        elif text_content:
            filename = '直接输入'
        else:
            flash('请选择文件或输入文本内容', 'error')
            return redirect(request.url)

        # 获取员工信息
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM employees WHERE employee_id = ?", (employee_id,))
        row = cursor.fetchone()
        conn.close()
        employee_name = row['name'] if row else 'Unknown'

        # CSV/Excel 走导入服务直接解析
        if file and file.filename and _is_spreadsheet(filename):
            result = _process_spreadsheet_file(file, employee_id)
            records = result['records']
            duplicate_count = result['duplicate_count']
            errors = result['errors']

            db_conn = get_db()
            cursor = db_conn.cursor()
            cursor.execute(
                "INSERT INTO import_sessions (file_path, employee_id, status, total_records, processed_records, error_records, completed_at) VALUES (?, ?, 'completed', ?, ?, ?, CURRENT_TIMESTAMP)",
                (filename, employee_id, len(records), len(records), len(errors))
            )
            import_session_id = cursor.lastrowid
            db_conn.commit()
            db_conn.close()
            session['current_import_session_id'] = import_session_id

            session['import_preview'] = {
                'employee_id': employee_id,
                'employee_name': employee_name,
                'filename': filename,
                'records': records,
                'total_count': len(records),
                'high_confidence': len([r for r in records if r.get('confidence_level') == 'HIGH']),
                'medium_confidence': len([r for r in records if r.get('confidence_level') == 'MEDIUM']),
                'low_confidence': len([r for r in records if r.get('confidence_level') == 'LOW']),
                'has_anomalies': any(r.get('has_anomaly') for r in records),
                'duplicate_count': duplicate_count,
                'is_complete': True,
            }
            session['ai_parse_details'] = {'prompt': '', 'response': '', 'error': None}
            session.modified = True

            if errors:
                for err in errors[:5]:
                    flash(err, 'warning')

            return redirect(url_for('records.import_preview'))

        # Markdown / 纯文本 走 AI 解析流程
        if file and file.filename:
            content = file.read().decode('utf-8')
        else:
            content = text_content

        valid_lines, line_numbers = _extract_valid_lines(content)
        if not valid_lines:
            flash('未找到有效记录行', 'error')
            return redirect(request.url)

        session_key = str(uuid.uuid4())[:8]
        session['current_parse_key'] = session_key
        session[f'parse_progress_{session_key}'] = []

        # 创建导入会话
        db_conn = get_db()
        cursor = db_conn.cursor()
        cursor.execute(
            "INSERT INTO import_sessions (file_path, employee_id, status, total_records) VALUES (?, ?, 'pending', ?)",
            (filename, employee_id, len(valid_lines))
        )
        import_session_id = cursor.lastrowid
        db_conn.commit()
        db_conn.close()
        session['current_import_session_id'] = import_session_id

        session[f'import_stream_{session_key}'] = {
            'employee_id': employee_id,
            'filename': filename,
            'content': content,
            'valid_lines': valid_lines,
            'line_numbers': line_numbers,
            'import_session_id': import_session_id,
        }

        session['import_preview'] = {
            'employee_id': employee_id,
            'employee_name': employee_name,
            'filename': filename,
            'records': [],
            'total_count': len(valid_lines),
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0,
            'has_anomalies': False,
            'duplicate_count': 0,
            'is_complete': False,
        }
        session['ai_parse_details'] = {'prompt': '', 'response': '', 'error': None}
        session.modified = True

        return redirect(url_for('records.import_preview'))

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


@bp.route('/import/stream/')
def import_stream():
    """SSE 流式 AI 解析"""
    session_key = request.args.get('key') or session.get('current_parse_key')
    if not session_key:
        def _error_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': '会话不存在'})}\n\n"
        return Response(_error_stream(), mimetype='text/event-stream')

    stream_data = session.get(f'import_stream_{session_key}')
    if not stream_data:
        def _error_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': '没有待解析的数据'})}\n\n"
        return Response(_error_stream(), mimetype='text/event-stream')

    session['current_parse_key'] = session_key
    session[f'parse_progress_{session_key}'] = []

    def event_stream():
        valid_lines = stream_data['valid_lines']
        line_numbers = stream_data['line_numbers']
        employee_id = stream_data['employee_id']
        filename = stream_data['filename']

        update_parse_progress(session_key, 'start', '🚀 开始AI大模型解析...', 5)
        yield f"data: {json.dumps({'type': 'progress', 'step': 'start', 'message': '开始解析...', 'progress': 5})}\n\n"

        update_parse_progress(session_key, 'extract_done', f'✓ 提取完成，有效行数: {len(valid_lines)}', 15)
        yield f"data: {json.dumps({'type': 'progress', 'step': 'extract', 'message': f'提取完成，有效行数: {len(valid_lines)}', 'progress': 15})}\n\n"

        parser = get_ai_parser()
        all_results = []
        all_responses = []
        total_batches = (len(valid_lines) + AI_PARSER_BATCH_SIZE - 1) // AI_PARSER_BATCH_SIZE

        full_prompt = parser._build_prompt(valid_lines)
        session['ai_parse_details'] = {'prompt': full_prompt, 'response': '', 'error': None}
        session.modified = True
        current_app.session_interface.save_session(
            current_app, session, current_app.response_class()
        )

        conn = get_db()
        try:
            for batch_start in range(0, len(valid_lines), AI_PARSER_BATCH_SIZE):
                batch_end = min(batch_start + AI_PARSER_BATCH_SIZE, len(valid_lines))
                batch_lines = valid_lines[batch_start:batch_end]
                current_batch = batch_start // AI_PARSER_BATCH_SIZE + 1

                update_parse_progress(session_key, 'ai_connect', f'🔌 连接Claude AI大模型... 批次 {current_batch}/{total_batches}', 20)
                progress_pct = 20 + int((current_batch - 1) * 40 / max(total_batches, 1))
                yield f"data: {json.dumps({'type': 'progress', 'step': 'ai_connect', 'message': f'连接模型 批次 {current_batch}/{total_batches}', 'progress': progress_pct})}\n\n"

                for event in parser._parse_batch_stream(batch_lines, batch_start):
                    if event['type'] == 'chunk':
                        yield f"data: {json.dumps({'type': 'chunk', 'content': event['content']})}\n\n"
                    elif event['type'] == 'done':
                        batch_records = event['records']
                        for record in batch_records:
                            if record.get('type') == 'overtime':
                                record['overtime_type'] = _normalize_overtime_type(record.get('overtime_type'))
                        for i, record in enumerate(batch_records):
                            absolute_idx = batch_start + i
                            if absolute_idx < len(line_numbers):
                                record['line_num'] = line_numbers[absolute_idx]

                        # 节假日修正 + 重复检测
                        _apply_holiday_correction(conn, batch_records)
                        _mark_duplicates(conn, employee_id, batch_records)

                        all_results.extend(batch_records)
                        all_responses.append(event['response'])

                        processed_batch = process_parse_results(batch_records)
                        preview_data = session.get('import_preview')
                        if preview_data:
                            preview_data['records'].extend(processed_batch)
                            preview_data['high_confidence'] = len([r for r in preview_data['records'] if r.get('confidence_level') == 'HIGH'])
                            preview_data['medium_confidence'] = len([r for r in preview_data['records'] if r.get('confidence_level') == 'MEDIUM'])
                            preview_data['low_confidence'] = len([r for r in preview_data['records'] if r.get('confidence_level') == 'LOW'])
                            preview_data['has_anomalies'] = any(r.get('has_anomaly') for r in preview_data['records'])
                            preview_data['duplicate_count'] = len([r for r in preview_data['records'] if r.get('is_duplicate')])
                            session['import_preview'] = preview_data
                            session.modified = True
                            current_app.session_interface.save_session(
                                current_app, session, current_app.response_class()
                            )

                        session['ai_parse_details'] = {
                            'prompt': full_prompt,
                            'response': '\n---\n'.join(all_responses),
                            'error': None
                        }
                        session.modified = True
                        current_app.session_interface.save_session(
                            current_app, session, current_app.response_class()
                        )

                        progress_pct = 20 + int(current_batch * 40 / max(total_batches, 1))
                        update_parse_progress(session_key, 'ai_done', f'✓ 批次 {current_batch}/{total_batches} 解析完成', progress_pct)
                        yield f"data: {json.dumps({'type': 'progress', 'step': 'ai_done', 'message': f'批次 {current_batch}/{total_batches} 解析完成', 'progress': progress_pct})}\n\n"
                        yield f"data: {json.dumps({'type': 'batch_done', 'records': processed_batch, 'completed': len(all_results), 'total': len(valid_lines), 'stats': {'high_confidence': preview_data['high_confidence'], 'medium_confidence': preview_data['medium_confidence'], 'low_confidence': preview_data['low_confidence'], 'has_anomalies': preview_data['has_anomalies']}})}\n\n"
                    elif event['type'] == 'error':
                        update_parse_progress(session_key, 'ai_error', f'❌ AI解析失败: {event["message"]}', 100)
                        yield f"data: {json.dumps({'type': 'error', 'message': event['message']})}\n\n"
                        return

            # AI 全部完成后，再次全量重复检测和节假日修正（确保跨批次数据一致）
            _apply_holiday_correction(conn, all_results)
            _mark_duplicates(conn, employee_id, all_results)

            update_parse_progress(session_key, 'process', '📊 分析置信度和异常...', 75)
            yield f"data: {json.dumps({'type': 'progress', 'step': 'process', 'message': '分析置信度和异常...', 'progress': 75})}\n\n"

            processed_records = process_parse_results(all_results)
            full_response = '\n---\n'.join(all_responses)
            full_prompt = parser._build_prompt(valid_lines)

            preview_data = session.get('import_preview', {})
            preview_data.update({
                'records': processed_records,
                'total_count': len(processed_records),
                'high_confidence': len([r for r in processed_records if r.get('confidence_level') == 'HIGH']),
                'medium_confidence': len([r for r in processed_records if r.get('confidence_level') == 'MEDIUM']),
                'low_confidence': len([r for r in processed_records if r.get('confidence_level') == 'LOW']),
                'has_anomalies': any(r.get('has_anomaly') for r in processed_records),
                'duplicate_count': len([r for r in processed_records if r.get('is_duplicate')]),
                'is_complete': True,
            })
            session['import_preview'] = preview_data
            session['ai_parse_details'] = {
                'prompt': full_prompt,
                'response': full_response,
                'error': ''
            }
            session.modified = True
            current_app.session_interface.save_session(
                current_app, session, current_app.response_class()
            )

            high = len([r for r in processed_records if r.get('confidence_level') == 'HIGH'])
            medium = len([r for r in processed_records if r.get('confidence_level') == 'MEDIUM'])
            low = len([r for r in processed_records if r.get('confidence_level') == 'LOW'])
            update_parse_progress(session_key, 'complete', f'🎉 完成！共{len(processed_records)}条 高:{high} 中:{medium} 低:{low}', 100)
            yield f"data: {json.dumps({'type': 'progress', 'step': 'complete', 'message': '解析完成', 'progress': 100})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'prompt': full_prompt, 'response': full_response})}\n\n"

        except Exception as e:
            error_msg = f'解析异常: {str(e)}'
            update_parse_progress(session_key, 'ai_error', f'❌ {error_msg[:100]}', 100)
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
        finally:
            conn.close()

    return Response(stream_with_context(event_stream()), mimetype='text/event-stream')


@bp.route('/import/preview/')
def import_preview():
    """导入预览页面 - 第二步：查看和确认"""
    preview_data = session.get('import_preview')
    if not preview_data:
        flash('没有待导入的数据，请先上传文件', 'error')
        return redirect(url_for('records.import_records'))

    ai_details = session.get('ai_parse_details', {})
    stream_key = session.get('current_parse_key')
    is_complete = preview_data.get('is_complete', False)

    return render_template(
        'import_preview.html',
        preview=preview_data,
        ai_details=ai_details,
        stream_key=stream_key,
        is_complete=is_complete
    )


@bp.route('/import/confirm/', methods=['POST'])
def import_confirm():
    """确认导入 - 第三步：保存到数据库"""
    preview_data = session.get('import_preview')
    if not preview_data:
        flash('导入会话已过期，请重新上传文件', 'error')
        return redirect(url_for('records.import_records'))

    employee_id = preview_data['employee_id']
    import_session_id = session.get('current_import_session_id')
    preview_records = preview_data.get('records', [])

    records_data = request.form.to_dict(flat=False)
    record_indices = set()
    for key in records_data.keys():
        match = re.match(r'records\[(\d+)\]\[(\w+)\]', key)
        if match:
            record_indices.add(int(match.group(1)))

    if not record_indices:
        flash('没有要导入的记录', 'warning')
        return redirect(url_for('records.import_preview'))

    selected_indices = request.form.getlist('selected_records')
    selected_indices = set(int(i) for i in selected_indices)
    record_indices = record_indices.intersection(selected_indices)

    conn = get_db()
    cursor = conn.cursor()
    success_count = 0
    error_count = 0
    insert_count = 0
    update_count = 0
    skipped_duplicates = 0
    errors = []

    try:
        # 更新导入会话状态为 processing（如存在）
        if import_session_id:
            cursor.execute(
                "UPDATE import_sessions SET status = 'processing' WHERE id = ?",
                (import_session_id,)
            )

        for idx in sorted(record_indices):
            try:
                prefix = f'records[{idx}]'
                record_date = request.form.get(f'{prefix}[date]', '').strip()
                record_type = request.form.get(f'{prefix}[type]', '').strip()
                record_subtype = request.form.get(f'{prefix}[subtype]', '').strip()
                record_hours = request.form.get(f'{prefix}[hours]', '0').strip()
                record_content = request.form.get(f'{prefix}[content]', '').strip()
                duplicate_action = request.form.get(f'{prefix}[duplicate_action]', 'skip').strip()

                try:
                    hours = float(record_hours) if record_hours else 0
                except ValueError:
                    hours = 0

                duration_hours, duration_minutes = _hours_to_duration(hours)
                total_minutes = duration_hours * 60 + duration_minutes

                if not record_date:
                    error_count += 1
                    errors.append(f"记录#{idx + 1}: 缺少日期")
                    continue

                original_record = preview_records[idx] if idx < len(preview_records) else {}
                needs_review = (
                    original_record.get('confidence_level') == 'LOW' or
                    original_record.get('has_anomaly') is True
                )

                if not record_type or (record_type == 'unknown' and not needs_review):
                    error_count += 1
                    errors.append(f"记录#{idx + 1}: 缺少类型")
                    continue

                # 重复且跳过
                is_dup = original_record.get('is_duplicate', False)
                if is_dup and duplicate_action == 'skip':
                    skipped_duplicates += 1
                    continue

                if needs_review and import_session_id:
                    anomalies = original_record.get('anomalies')
                    if isinstance(anomalies, list):
                        anomalies = ', '.join(str(a) for a in anomalies)
                    elif anomalies is None:
                        anomalies = ''
                    else:
                        anomalies = str(anomalies)

                    add_to_review_queue(
                        conn,
                        import_session_id=import_session_id,
                        raw_text=record_content,
                        parsed_type=record_type,
                        parsed_subtype=record_subtype,
                        parsed_date=record_date,
                        parsed_hours=hours,
                        parsed_minutes=total_minutes,
                        confidence_level=original_record.get('confidence_level'),
                        confidence_score=original_record.get('confidence'),
                        anomalies=anomalies
                    )
                    success_count += 1
                    continue

                if record_type == 'overtime':
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
                        """, (duration_hours, duration_minutes, total_minutes, record_content, import_session_id, existing['id']))
                        update_count += 1
                    else:
                        cursor.execute("""
                            INSERT INTO overtime_records
                            (employee_id, work_date, duration_hours, duration_minutes,
                             total_minutes, overtime_type, description, source_import_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (employee_id, record_date, duration_hours, duration_minutes,
                              total_minutes, overtime_type, record_content, import_session_id))
                        insert_count += 1
                    success_count += 1

                    # 周末加班生成调休余额
                    if overtime_type == 'weekend':
                        record_id = cursor.lastrowid if not existing else existing['id']
                        _create_comp_off_balance(
                            conn, employee_id, record_id, record_date, total_minutes
                        )

                elif record_type == 'leave':
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
                        """, (duration_hours, duration_minutes, total_minutes, record_content, import_session_id, existing['id']))
                        update_count += 1
                    else:
                        cursor.execute("""
                            INSERT INTO leave_records
                            (employee_id, leave_date, duration_hours, duration_minutes,
                             total_minutes, leave_type, description, source_import_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (employee_id, record_date, duration_hours, duration_minutes,
                              total_minutes, leave_type, record_content, import_session_id))
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
                                total_minutes = ?, description = ?, source_import_id = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (duration_hours, duration_minutes, total_minutes, record_content, import_session_id, existing['id']))
                        update_count += 1
                    else:
                        cursor.execute("""
                            INSERT INTO comp_off_usage_records
                            (employee_id, usage_date, duration_hours, duration_minutes,
                             total_minutes, description, source_import_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (employee_id, record_date, duration_hours, duration_minutes,
                              total_minutes, record_content, import_session_id))
                        insert_count += 1
                    success_count += 1

                else:
                    error_count += 1
                    errors.append(f"记录#{idx + 1}: 未知的记录类型 '{record_type}'")

            except Exception as e:
                error_count += 1
                errors.append(f"记录#{idx + 1}: {str(e)}")

        # 更新导入会话统计
        if import_session_id:
            cursor.execute("""
                UPDATE import_sessions
                SET status = 'completed', processed_records = ?, error_records = ?,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (success_count, error_count, import_session_id))

        conn.commit()

        session.pop('import_preview', None)
        session.pop('current_import_session_id', None)
        session.pop('current_parse_key', None)

        skip_msg = f"，跳过重复 {skipped_duplicates} 条" if skipped_duplicates else ""
        flash(f'导入完成: 成功 {success_count} 条 (新增 {insert_count} 条, 更新 {update_count} 条){skip_msg}，失败 {error_count} 条', 'success')
        if errors:
            for error in errors[:5]:
                flash(error, 'warning')

    except Exception as e:
        conn.rollback()
        flash(f'导入失败: {str(e)}', 'error')
        flash('您可以返回预览页面检查数据后重试，或取消导入', 'info')
        return redirect(url_for('records.import_preview'))
    finally:
        conn.close()

    return redirect(url_for('records.import_records'))


@bp.route('/import/cancel/')
def import_cancel():
    """取消导入"""
    session.pop('import_preview', None)
    session.pop('current_import_session_id', None)
    session.pop('current_parse_key', None)
    flash('已取消导入', 'info')
    return redirect(url_for('records.import_records'))


@bp.route('/import/employee/<employee_id>/', methods=['GET', 'POST'])
def import_for_employee(employee_id: str):
    """为指定员工导入记录"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT employee_id, name FROM employees WHERE employee_id = ?", (employee_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        flash('员工不存在', 'error')
        return redirect(url_for('employees.list_employees'))

    employee = dict(row)

    if request.method == 'POST':
        file = request.files.get('file')
        text_content = request.form.get('text_content', '').strip()

        if file and file.filename:
            filename = file.filename
        elif text_content:
            filename = '直接输入'
        else:
            flash('请选择文件或输入文本内容', 'error')
            return redirect(request.url)

        # CSV/Excel 直接解析
        if file and file.filename and _is_spreadsheet(filename):
            result = _process_spreadsheet_file(file, employee_id)
            records = result['records']
            duplicate_count = result['duplicate_count']
            errors = result['errors']

            db_conn = get_db()
            cursor = db_conn.cursor()
            cursor.execute(
                "INSERT INTO import_sessions (file_path, employee_id, status, total_records, processed_records, error_records, completed_at) VALUES (?, ?, 'completed', ?, ?, ?, CURRENT_TIMESTAMP)",
                (filename, employee_id, len(records), len(records), len(errors))
            )
            import_session_id = cursor.lastrowid
            db_conn.commit()
            db_conn.close()
            session['current_import_session_id'] = import_session_id

            session['import_preview'] = {
                'employee_id': employee_id,
                'employee_name': employee['name'],
                'filename': filename,
                'records': records,
                'total_count': len(records),
                'high_confidence': len([r for r in records if r.get('confidence_level') == 'HIGH']),
                'medium_confidence': len([r for r in records if r.get('confidence_level') == 'MEDIUM']),
                'low_confidence': len([r for r in records if r.get('confidence_level') == 'LOW']),
                'has_anomalies': any(r.get('has_anomaly') for r in records),
                'duplicate_count': duplicate_count,
                'is_complete': True,
            }
            session['ai_parse_details'] = {'prompt': '', 'response': '', 'error': None}
            session.modified = True

            if errors:
                for err in errors[:5]:
                    flash(err, 'warning')

            return redirect(url_for('records.import_preview'))

        # Markdown / 文本 走AI解析流程
        if file and file.filename:
            content = file.read().decode('utf-8')
        else:
            content = text_content

        valid_lines, line_numbers = _extract_valid_lines(content)
        if not valid_lines:
            flash('未找到有效记录行', 'error')
            return redirect(request.url)

        session_key = str(uuid.uuid4())[:8]
        session['current_parse_key'] = session_key
        session[f'parse_progress_{session_key}'] = []

        db_conn = get_db()
        cursor = db_conn.cursor()
        cursor.execute(
            "INSERT INTO import_sessions (file_path, employee_id, status, total_records) VALUES (?, ?, 'pending', ?)",
            (filename, employee_id, len(valid_lines))
        )
        import_session_id = cursor.lastrowid
        db_conn.commit()
        db_conn.close()
        session['current_import_session_id'] = import_session_id

        session[f'import_stream_{session_key}'] = {
            'employee_id': employee_id,
            'filename': filename,
            'content': content,
            'valid_lines': valid_lines,
            'line_numbers': line_numbers,
            'import_session_id': import_session_id,
        }

        session['import_preview'] = {
            'employee_id': employee_id,
            'employee_name': employee['name'],
            'filename': filename,
            'records': [],
            'total_count': len(valid_lines),
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0,
            'has_anomalies': False,
            'duplicate_count': 0,
            'is_complete': False,
        }
        session['ai_parse_details'] = {'prompt': '', 'response': '', 'error': None}
        session.modified = True

        return redirect(url_for('records.import_preview'))

    return render_template('import.html', employees=[employee], selected_employee=employee)


@bp.route('/search/')
def search_records():
    """全局记录查询页面 - 按日期范围和类型搜索跨员工记录"""
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    record_type = request.args.get('record_type', 'all').strip()
    employee_id = request.args.get('employee_id', '').strip()

    results = []
    employees = []

    # 默认查询当前月份
    today = date.today()
    if not start_date and not end_date:
        start_date = today.replace(day=1).isoformat()
        end_date = today.isoformat()

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT employee_id, name FROM employees ORDER BY name")
        employees = [dict(row) for row in cursor.fetchall()]

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
                    WHERE 1=1
                """
                params = []
                if start_date:
                    sql += " AND o.work_date >= ?"
                    params.append(start_date)
                if end_date:
                    sql += " AND o.work_date <= ?"
                    params.append(end_date)
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
                    WHERE 1=1
                """
                params = []
                if start_date:
                    sql += " AND l.leave_date >= ?"
                    params.append(start_date)
                if end_date:
                    sql += " AND l.leave_date <= ?"
                    params.append(end_date)
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
                    WHERE 1=1
                """
                params = []
                if start_date:
                    sql += " AND c.usage_date >= ?"
                    params.append(start_date)
                if end_date:
                    sql += " AND c.usage_date <= ?"
                    params.append(end_date)
                if employee_id:
                    sql += " AND c.employee_id = ?"
                    params.append(employee_id)
                sql += " ORDER BY c.usage_date DESC"
                cursor.execute(sql, params)

            rows = [dict(row) for row in cursor.fetchall()]
            results.extend(rows)

        # 多类型混合时按日期统一降序
        if len(types_to_query) > 1:
            results.sort(key=lambda x: x.get('record_date') or '', reverse=True)
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


@bp.route('/sessions/')
def import_sessions():
    """导入会话列表页"""
    conn = get_db()
    cursor = conn.cursor()
    sessions = []
    try:
        cursor.execute(
            "SELECT * FROM import_sessions ORDER BY created_at DESC"
        )
        sessions = [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return render_template('import_sessions.html', sessions=sessions)


@bp.route('/sessions/<int:session_id>/delete/', methods=['POST'])
def delete_import_session(session_id: int):
    """批量删除某导入会话下的所有记录"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM overtime_records WHERE source_import_id = ?",
            (session_id,)
        )
        cursor.execute(
            "DELETE FROM leave_records WHERE source_import_id = ?",
            (session_id,)
        )
        cursor.execute(
            "DELETE FROM comp_off_usage_records WHERE source_import_id = ?",
            (session_id,)
        )
        cursor.execute(
            "DELETE FROM import_records WHERE session_id = ?",
            (session_id,)
        )
        cursor.execute(
            "DELETE FROM import_sessions WHERE id = ?",
            (session_id,)
        )
        conn.commit()
        flash(f'批次 #{session_id} 已成功撤回', 'success')
    except sqlite3.Error as e:
        conn.rollback()
        flash(f'撤回失败: {e}', 'error')
    finally:
        conn.close()

    return redirect(url_for('records.import_sessions'))


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
