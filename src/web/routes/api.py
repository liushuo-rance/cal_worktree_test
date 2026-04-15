"""
REST API 路由
提供 JSON 格式的批量导入等接口
"""

import sqlite3
from typing import Any, Dict, List

from flask import Blueprint, request, jsonify

from web.utils import get_db
from web.decorators import admin_required
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from services import import_service as import_svc
from services.holiday_service import get_date_type
from services.storage_service import store_batch_records, StorageError

bp = Blueprint('api', __name__, url_prefix='/api/v1')


def _apply_holiday_correction_to_records(records: List[Dict[str, Any]]) -> None:
    """根据节假日配置修正 overtime_type"""
    from datetime import date

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
                    ai_subtype = record.get('overtime_type')
                    if ai_subtype not in ('weekday_morning', 'weekday_lunch', 'weekday_evening', 'weekday_mixed'):
                        record['overtime_type'] = 'weekday_evening'
            elif record.get('type') == 'leave':
                if not record.get('leave_type'):
                    record['leave_type'] = 'personal'
    finally:
        conn.close()


def _adapt_records_for_storage(normalized_records: List[Dict[str, Any]], employee_id: str) -> List[Dict[str, Any]]:
    """将 normalize_import_rows 输出转换为 store_batch_records 输入格式"""
    adapted = []
    for record in normalized_records:
        adapted_record = {
            'type': record.get('type'),
            'employee_id': record.get('employee_id') or employee_id,
            'date': record.get('parsed_date'),
            'hours': record.get('parsed_hours', 0),
            'description': record.get('content', ''),
        }
        if record.get('type') == 'overtime':
            adapted_record['overtime_type'] = record.get('overtime_type', 'weekday_evening')
        elif record.get('type') == 'leave':
            adapted_record['leave_type'] = record.get('leave_type', 'personal')
        adapted.append(adapted_record)
    return adapted


@bp.route('/records/import/', methods=['POST'])
@admin_required
def api_import_records():
    """
    JSON 批量导入接口

    Request Body:
        {
            "employee_id": "EMP001",
            "records": [
                {"date": "2026-04-01", "hours": 3.5, "type": "overtime", "description": "..."},
                ...
            ]
        }

    Response:
        {"success": true, "imported_count": 10, "errors": []}
    """
    data = request.get_json(silent=True) or {}
    employee_id = data.get('employee_id')
    records = data.get('records')

    if not employee_id or not isinstance(employee_id, str):
        return jsonify({
            "success": False,
            "imported_count": 0,
            "errors": ["缺少或无效的 employee_id"]
        }), 400

    if not isinstance(records, list):
        return jsonify({
            "success": False,
            "imported_count": 0,
            "errors": ["records 必须是数组"]
        }), 400

    if not records:
        return jsonify({
            "success": False,
            "imported_count": 0,
            "errors": ["records 不能为空"]
        }), 400

    # 复用 import_service 进行标准化
    normalize_result = import_svc.normalize_import_rows(records, employee_id=employee_id)
    normalized_records = normalize_result.get('records', [])
    normalize_errors = normalize_result.get('errors', [])

    errors = [e['message'] for e in normalize_errors]

    if not normalized_records:
        return jsonify({
            "success": False,
            "imported_count": 0,
            "errors": errors or ["没有可导入的有效记录"]
        }), 400

    # 节假日修正
    _apply_holiday_correction_to_records(normalized_records)

    # 转换为 storage_service 需要的格式
    storage_records = _adapt_records_for_storage(normalized_records, employee_id)

    conn = get_db()
    try:
        result = store_batch_records(conn, storage_records)
        imported_count = result.get('success_count', 0)
    except StorageError as e:
        return jsonify({
            "success": False,
            "imported_count": 0,
            "errors": errors + [str(e)]
        }), 500
    finally:
        conn.close()

    return jsonify({
        "success": True,
        "imported_count": imported_count,
        "errors": errors
    })
