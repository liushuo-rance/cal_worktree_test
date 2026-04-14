"""
导出服务测试
"""

import os
import tempfile

import pytest

from src.services.export_service import (
    ExportError,
    export_to_csv,
    export_to_excel,
    export_report_to_pdf,
    get_chinese_font,
)


class TestExportToCsv:
    """CSV 导出测试"""

    def test_export_to_csv_returns_bytes(self):
        data = [
            {"name": "张三", "hours": 3.5, "type": "weekday"},
            {"name": "李四", "hours": 5.0, "type": "weekend"},
        ]
        columns = [("name", "姓名"), ("hours", "加班时长"), ("type", "类型")]
        result = export_to_csv(data, columns)

        assert isinstance(result, bytes)
        # UTF-8 BOM
        assert result.startswith(b"\xef\xbb\xbf")
        text = result.decode("utf-8-sig")
        assert "姓名" in text
        assert "张三" in text
        assert "3.5" in text

    def test_export_to_csv_writes_file(self):
        data = [{"name": "王五", "hours": 2.0}]
        columns = [("name", "姓名"), ("hours", "加班时长")]

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name

        try:
            result = export_to_csv(data, columns, output_path=path)
            assert result is None
            with open(path, "rb") as f:
                content = f.read()
            assert content.startswith(b"\xef\xbb\xbf")
            text = content.decode("utf-8-sig")
            assert "王五" in text
        finally:
            os.unlink(path)

    def test_export_to_csv_empty_data(self):
        columns = [("name", "姓名")]
        result = export_to_csv([], columns)
        text = result.decode("utf-8-sig")
        lines = text.strip().split("\r\n")
        assert lines == ["姓名"]

    def test_export_to_csv_missing_key(self):
        data = [{"name": "张三"}]
        columns = [("name", "姓名"), ("hours", "时长")]
        result = export_to_csv(data, columns)
        text = result.decode("utf-8-sig")
        lines = text.strip().split("\r\n")
        assert lines[1] == "张三,"

    def test_export_to_csv_empty_columns_raises(self):
        with pytest.raises(ExportError):
            export_to_csv([], [])


class TestExportToExcel:
    """Excel 导出测试"""

    def test_export_to_excel_returns_bytes(self):
        sheets_data = {
            "加班记录": {
                "columns": [("date", "日期"), ("hours", "时长")],
                "data": [{"date": "2026-04-01", "hours": 3.5}],
            },
            "请假记录": {
                "columns": [("date", "日期"), ("days", "天数")],
                "data": [{"date": "2026-04-02", "days": 1}],
            },
        }
        result = export_to_excel(sheets_data)
        assert isinstance(result, bytes)
        assert result[:4] == b"PK\x03\x04"  # xlsx 文件头

    def test_export_to_excel_writes_file(self):
        sheets_data = {
            "Sheet1": {
                "columns": [("col", "列")],
                "data": [{"col": "值"}],
            }
        }
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            path = f.name

        try:
            result = export_to_excel(sheets_data, output_path=path)
            assert result is None
            with open(path, "rb") as f:
                content = f.read()
            assert content[:4] == b"PK\x03\x04"
        finally:
            os.unlink(path)

    def test_export_to_excel_empty_sheets(self):
        sheets_data = {
            "空表": {
                "columns": [("a", "A")],
                "data": [],
            }
        }
        result = export_to_excel(sheets_data)
        assert isinstance(result, bytes)


class TestExportReportToPdf:
    """PDF 报表导出测试"""

    def _monthly_report(self):
        return {
            "employee_id": "E001",
            "employee_name": "张三",
            "year": 2026,
            "month": 4,
            "overtime_details": [
                {
                    "date": "2026-04-05",
                    "weekday": "周六",
                    "hours": 4.0,
                    "type": "weekend",
                    "description": "项目上线",
                }
            ],
            "leave_details": [
                {
                    "date": "2026-04-10",
                    "weekday": "周五",
                    "hours": 8.0,
                    "days": 1.0,
                    "type": "personal",
                }
            ],
            "summary": {
                "weekday_hours": 0.0,
                "weekend_hours": 4.0,
                "holiday_hours": 0.0,
                "total_overtime_hours": 4.0,
                "leave_days": 1.0,
                "leave_hours": 8.0,
            },
        }

    def _salary_report(self):
        return {
            "employee_id": "E001",
            "employee_name": "张三",
            "year": 2026,
            "month": 4,
            "hourly_rate": 37.5,
            "weekday_overtime": {"hours": 10.0, "multiplier": 1.5, "amount": 562.5},
            "weekend_overtime": {"hours": 4.0, "multiplier": 2.0, "amount": 300.0},
            "holiday_overtime": {"hours": 0.0, "multiplier": 3.0, "amount": 0.0},
            "total_amount": 862.5,
        }

    def _comp_off_report(self):
        return {
            "employee_id": "E001",
            "employee_name": "张三",
            "summary": {
                "total_acquired_hours": 12.0,
                "total_available_hours": 8.0,
            },
            "warning_days": 30,
            "expiring_soon_hours": 4.0,
            "active_balances": [
                {"acquired_date": "2026-03-01", "total_hours": 8.0, "used_hours": 0.0, "remaining_hours": 8.0, "expiry_date": "2026-09-01", "status": "active"},
                {"acquired_date": "2026-04-01", "total_hours": 4.0, "used_hours": 0.0, "remaining_hours": 4.0, "expiry_date": "2026-04-20", "status": "active"},
            ],
            "expiring_items": [
                {"acquired_date": "2026-04-01", "total_hours": 4.0, "used_hours": 0.0, "remaining_hours": 4.0, "expiry_date": "2026-04-20", "status": "active"},
            ],
        }

    def test_export_monthly_pdf_returns_bytes(self):
        result = export_report_to_pdf(self._monthly_report(), "monthly")
        assert isinstance(result, bytes)
        assert result.startswith(b"%PDF")

    def test_export_salary_pdf_returns_bytes(self):
        result = export_report_to_pdf(self._salary_report(), "salary")
        assert isinstance(result, bytes)
        assert result.startswith(b"%PDF")

    def test_export_comp_off_pdf_returns_bytes(self):
        result = export_report_to_pdf(self._comp_off_report(), "comp_off")
        assert isinstance(result, bytes)
        assert result.startswith(b"%PDF")

    def test_export_pdf_writes_file(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name

        try:
            result = export_report_to_pdf(self._monthly_report(), "monthly", output_path=path)
            assert result is None
            with open(path, "rb") as f:
                content = f.read()
            assert content.startswith(b"%PDF")
        finally:
            os.unlink(path)

    def test_export_pdf_unsupported_type_raises(self):
        with pytest.raises(ExportError) as exc_info:
            export_report_to_pdf({}, "unknown")
        assert "不支持的报表类型" in str(exc_info.value)

    def test_export_comp_off_pdf_empty_items(self):
        report = {
            "employee_id": "E002",
            "employee_name": "李四",
            "summary": {
                "total_acquired_hours": 0.0,
                "total_available_hours": 0.0,
            },
            "warning_days": 30,
            "expiring_soon_hours": 0.0,
            "active_balances": [],
            "expiring_items": [],
        }
        result = export_report_to_pdf(report, "comp_off")
        assert isinstance(result, bytes)
        assert result.startswith(b"%PDF")


class TestGetChineseFont:
    """中文字体查找测试"""

    def test_get_chinese_font_returns_existing_path(self):
        path = get_chinese_font()
        assert os.path.isfile(path)
        # 常见扩展名
        assert path.lower().endswith((".ttc", ".ttf", ".otf"))
