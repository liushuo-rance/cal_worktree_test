"""
测试夹具包
包含E2E测试所需的测试数据和辅助函数
"""

from .e2e_test_data import (
    create_sample_employee,
    create_second_employee,
    create_sample_overtime_records,
    create_sample_leave_records,
    create_sample_markdown_content,
    create_holiday_notification_2026,
    create_mixed_records_markdown,
    get_expected_salary_calculation,
    create_test_dates,
    create_holiday_config_2026,
)

__all__ = [
    'create_sample_employee',
    'create_second_employee',
    'create_sample_overtime_records',
    'create_sample_leave_records',
    'create_sample_markdown_content',
    'create_holiday_notification_2026',
    'create_mixed_records_markdown',
    'get_expected_salary_calculation',
    'create_test_dates',
    'create_holiday_config_2026',
]
