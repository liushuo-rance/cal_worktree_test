"""
文件导入服务
支持CSV/Excel文件读取与标准化，输出与AI解析结果一致的结构
"""

import csv
from datetime import date, datetime
from typing import Dict, Any, List, Optional, Tuple

# 尝试导入openpyxl（读取Excel）
try:
    import openpyxl

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

# 列名映射：支持中文/英文别名（大小写不敏感）
COLUMN_ALIASES = {
    "date": ["date", "日期", "时间", "work_date", "leave_date", "usage_date"],
    "employee_id": ["employee_id", "员工id", "工号", "emp_id"],
    "hours": ["hours", "时长", "小时", "duration_hours"],
    "minutes": ["minutes", "分钟", "duration_minutes"],
    "type": ["type", "类型", "record_type", "overtime_type", "leave_type"],
    "subtype": ["subtype", "子类型"],
    "description": ["description", "描述", "备注", "content"],
}

# 合法的overtime_type值
VALID_OVERTIME_TYPES = {
    "weekday_morning",
    "weekday_lunch",
    "weekday_evening",
    "weekend",
    "holiday",
}

# 合法的leave_type值
VALID_LEAVE_TYPES = {
    "personal",
    "sick",
    "annual",
    "marriage",
    "maternity",
    "bereavement",
    "other",
}


def _build_alias_map(headers: List[str]) -> Dict[str, str]:
    """根据表头构建列别名映射（大小写不敏感）"""
    result: Dict[str, str] = {}
    lower_headers = [h.strip().lower() for h in headers]
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            alias_lower = alias.strip().lower()
            if alias_lower in lower_headers:
                idx = lower_headers.index(alias_lower)
                result[canonical] = headers[idx]
                break
    return result


def _parse_date(value: Any) -> Optional[str]:
    """解析日期，返回YYYY-MM-DD格式字符串或None"""
    if value is None or value == "":
        return None

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, datetime):
        return value.date().isoformat()

    text = str(value).strip()
    if not text:
        return None

    # 常见分隔符统一为-
    normalized = text.replace(".", "-").replace("/", "-")

    # 尝试YYYY-MM-DD
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(normalized, fmt).date().isoformat()
        except ValueError:
            continue

    # 尝试自动解析
    try:
        dt = datetime.fromisoformat(normalized)
        return dt.date().isoformat()
    except ValueError:
        pass

    return None


def _parse_hours(value: Any) -> Optional[float]:
    """解析小时数，返回浮点数或None"""
    if value is None or value == "":
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        pass

    # 尝试解析中文描述，如"2.5小时"、"2小时30分"、"半天"、"一天"
    text = text.replace("小时", "h").replace("分钟", "m").replace("分", "m")
    if text == "半天":
        return 4.0
    if text in ("一天", "全天"):
        return 8.0

    # 尝试提取数字部分
    import re

    match = re.search(r"(\d+(?:\.\d+)?)\s*h", text)
    if match:
        hours = float(match.group(1))
        minutes_match = re.search(r"(\d+)\s*m", text)
        if minutes_match:
            hours += int(minutes_match.group(1)) / 60.0
        return round(hours, 2)

    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(1))

    return None


def _parse_minutes(value: Any) -> int:
    """解析分钟数，返回整数"""
    if value is None or value == "":
        return 0

    if isinstance(value, (int, float)):
        return int(round(float(value)))

    text = str(value).strip()
    if not text:
        return 0

    try:
        return int(round(float(text)))
    except ValueError:
        pass

    return 0


def _normalize_overtime_type(subtype: Optional[str]) -> str:
    """将overtime_type规范化到数据库允许的合法值"""
    if subtype in VALID_OVERTIME_TYPES:
        return subtype
    # 常见别名映射
    alias_map = {
        "工作日早上": "weekday_morning",
        "早上": "weekday_morning",
        "上午": "weekday_morning",
        "工作日午休": "weekday_lunch",
        "午休": "weekday_lunch",
        "中午": "weekday_lunch",
        "工作日晚上": "weekday_evening",
        "晚上": "weekday_evening",
        "下午": "weekday_evening",
        "工作日": "weekday_evening",
        "周末": "weekend",
        "节假日": "holiday",
        "法定假日": "holiday",
    }
    if subtype:
        lower = subtype.strip().lower()
        if lower in alias_map:
            return alias_map[lower]
    return "weekday_evening"


def _normalize_leave_type(subtype: Optional[str]) -> str:
    """将leave_type规范化到合法值"""
    if subtype in VALID_LEAVE_TYPES:
        return subtype
    alias_map = {
        "事假": "personal",
        "病假": "sick",
        "年假": "annual",
        "年休": "annual",
        "婚假": "marriage",
        "产假": "maternity",
        "丧假": "bereavement",
    }
    if subtype:
        lower = subtype.strip().lower()
        if lower in alias_map:
            return alias_map[lower]
    return "personal"


def _infer_type(row_type: Optional[str], subtype: Optional[str]) -> str:
    """根据type或subtype推断记录大类型"""
    if not row_type:
        if subtype:
            lower_sub = subtype.strip().lower()
            if lower_sub in VALID_OVERTIME_TYPES or lower_sub in (
                "weekday_morning",
                "weekday_lunch",
                "weekday_evening",
                "weekend",
                "holiday",
                "早上",
                "上午",
                "中午",
                "晚上",
                "下午",
                "周末",
                "节假日",
            ):
                return "overtime"
            if lower_sub in VALID_LEAVE_TYPES or lower_sub in (
                "事假",
                "病假",
                "年假",
                "婚假",
                "产假",
                "丧假",
            ):
                return "leave"
        return "overtime"

    lower_type = row_type.strip().lower()
    if lower_type in ("overtime", "加班"):
        return "overtime"
    if lower_type in ("leave", "请假", "休假"):
        return "leave"
    if lower_type in ("comp_off", "调休", "补休"):
        return "comp_off"

    # 尝试根据英文关键词判断
    if "overtime" in lower_type or "weekday" in lower_type or "weekend" in lower_type or "holiday" in lower_type:
        return "overtime"
    if "leave" in lower_type:
        return "leave"
    if "comp" in lower_type:
        return "comp_off"

    return "overtime"


def read_csv_file(file_path: str) -> List[Dict[str, Any]]:
    """
    读取CSV文件，返回原始行字典列表

    Args:
        file_path: CSV文件路径

    Returns:
        原始行字典列表
    """
    rows: List[Dict[str, Any]] = []
    with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
        # 尝试自动检测分隔符
        sample = f.read(8192)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        reader = csv.DictReader(f, dialect=dialect)
        for row in reader:
            rows.append({k: v for k, v in row.items() if k is not None})
    return rows


def read_excel_file(file_path: str) -> List[Dict[str, Any]]:
    """
    读取Excel文件（.xlsx/.xls），返回原始行字典列表

    Args:
        file_path: Excel文件路径

    Returns:
        原始行字典列表
    """
    if not HAS_OPENPYXL:
        raise ImportError("缺少openpyxl依赖，无法读取Excel文件")

    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active
    if ws is None:
        return []

    rows: List[Dict[str, Any]] = []
    headers: List[str] = []
    for idx, row in enumerate(ws.iter_rows(values_only=True)):
        if idx == 0:
            headers = [str(cell).strip() if cell is not None else "" for cell in row]
            continue
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        row_dict: Dict[str, Any] = {}
        for h, cell in zip(headers, row):
            row_dict[h] = cell
        rows.append(row_dict)
    return rows


def normalize_import_rows(
    rows: List[Dict[str, Any]], employee_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    将原始行字典列表转换为与AI解析结果一致的结构

    Args:
        rows: 原始行字典列表
        employee_id: 可选的默认员工ID

    Returns:
        {"records": [...], "errors": [...]}
    """
    if not rows:
        return {"records": [], "errors": []}

    headers = list(rows[0].keys())
    alias_map = _build_alias_map(headers)

    records: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for idx, row in enumerate(rows):
        # 跳过完全空行
        if all(v is None or str(v).strip() == "" for v in row.values()):
            continue

        date_col = alias_map.get("date")
        emp_col = alias_map.get("employee_id")
        hours_col = alias_map.get("hours")
        minutes_col = alias_map.get("minutes")
        type_col = alias_map.get("type")
        subtype_col = alias_map.get("subtype")
        desc_col = alias_map.get("description")

        # 提取日期
        raw_date = row.get(date_col) if date_col else None
        parsed_date = _parse_date(raw_date)
        if not parsed_date:
            errors.append({"row": idx, "message": f"第{idx + 1}行日期解析失败: {raw_date}"})
            continue

        # 提取员工ID
        row_employee_id = None
        if emp_col:
            row_employee_id = str(row.get(emp_col)).strip() if row.get(emp_col) is not None else None
        row_employee_id = row_employee_id or employee_id

        # 提取时长
        raw_hours = row.get(hours_col) if hours_col else None
        parsed_hours = _parse_hours(raw_hours)
        total_minutes = 0
        if parsed_hours is not None:
            total_minutes = int(round(parsed_hours * 60))

        if minutes_col:
            extra_minutes = _parse_minutes(row.get(minutes_col))
            total_minutes += extra_minutes

        if total_minutes == 0:
            errors.append({"row": idx, "message": f"第{idx + 1}行无法解析时长"})
            continue

        if parsed_hours is not None and minutes_col:
            # hours和minutes同时存在时，重新计算总分钟数和parsed_hours
            total_minutes = int(round(parsed_hours * 60)) + _parse_minutes(row.get(minutes_col))
            parsed_hours = round(total_minutes / 60.0, 2)
        elif parsed_hours is None and total_minutes > 0:
            parsed_hours = round(total_minutes / 60.0, 2)

        # 提取类型
        raw_type = str(row.get(type_col)).strip() if type_col and row.get(type_col) is not None else None
        raw_subtype = str(row.get(subtype_col)).strip() if subtype_col and row.get(subtype_col) is not None else None
        if not raw_subtype and raw_type:
            # 若subtype为空但type有值，且type不是大类，尝试将type作为subtype
            lower_type = raw_type.lower()
            if lower_type not in ("overtime", "加班", "leave", "请假", "休假", "comp_off", "调休", "补休"):
                raw_subtype = raw_type
                raw_type = None

        record_type = _infer_type(raw_type, raw_subtype)

        overtime_type: Optional[str] = None
        leave_type: Optional[str] = None

        if record_type == "overtime":
            overtime_type = _normalize_overtime_type(raw_subtype)
        elif record_type == "leave":
            leave_type = _normalize_leave_type(raw_subtype)

        # 提取描述
        description = ""
        if desc_col:
            desc_val = row.get(desc_col)
            if desc_val is not None:
                description = str(desc_val).strip()

        # 构建标准化记录（与AI解析结果格式一致）
        record = {
            "type": record_type,
            "overtime_type": overtime_type,
            "leave_type": leave_type,
            "parsed_date": parsed_date,
            "parsed_hours": parsed_hours,
            "total_minutes": total_minutes,
            "content": description,
            "confidence": 1.0,
            "confidence_level": "HIGH",
            "has_anomaly": False,
            "anomalies": [],
            "validation_errors": [],
            "is_valid": True,
        }

        if row_employee_id:
            record["employee_id"] = row_employee_id

        records.append(record)

    return {"records": records, "errors": errors}
