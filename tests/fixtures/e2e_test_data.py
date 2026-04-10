"""
E2E测试数据生成器
提供测试数据生成和样本文件内容
"""

from datetime import date, timedelta
from typing import List, Dict, Any


def create_sample_employee() -> Dict[str, Any]:
    """创建样本员工数据"""
    return {
        'employee_id': 'EMP001',
        'name': '张三',
        'department': '技术部',
        'daily_salary': 300.0,
        'hourly_salary': 37.5
    }


def create_second_employee() -> Dict[str, Any]:
    """创建第二个样本员工"""
    return {
        'employee_id': 'EMP002',
        'name': '李四',
        'department': '产品部',
        'daily_salary': 350.0,
        'hourly_salary': 43.75
    }


def create_sample_overtime_records() -> List[Dict[str, Any]]:
    """创建样本加班记录数据"""
    return [
        {
            'date': date(2026, 1, 5),  # 周一
            'hours': 3,
            'minutes': 30,
            'type': 'weekday_evening',
            'description': '项目上线加班'
        },
        {
            'date': date(2026, 1, 10),  # 周六
            'hours': 4,
            'minutes': 0,
            'type': 'weekend',
            'description': '周末值班'
        },
        {
            'date': date(2026, 1, 17),  # 周六
            'hours': 6,
            'minutes': 0,
            'type': 'weekend',
            'description': '系统维护'
        },
        {
            'date': date(2026, 1, 1),  # 元旦
            'hours': 8,
            'minutes': 0,
            'type': 'holiday',
            'description': '节假日值班'
        }
    ]


def create_sample_leave_records() -> List[Dict[str, Any]]:
    """创建样本请假记录数据"""
    return [
        {
            'date': date(2026, 1, 20),
            'hours': 4,
            'minutes': 0,
            'type': 'personal',
            'description': '事假半天'
        },
        {
            'date': date(2026, 1, 25),
            'hours': 8,
            'minutes': 0,
            'type': 'sick',
            'description': '病假一天'
        }
    ]


def create_sample_markdown_content() -> str:
    """创建样本Markdown文件内容"""
    return """# 加班记录

## 2026年1月

### 1月5日 周一
晚上加班3.5小时，项目上线

### 1月10日 周六
周末值班4小时

### 1月17日 周六
系统维护6小时

### 1月20日 周三
请假半天（4小时）

### 1月25日 周一
病假一天（8小时）

### 1月1日 元旦
节假日值班8小时
"""


def create_holiday_notification_2026() -> str:
    """创建2026年节假日通知文本"""
    return """
国务院办公厅关于2026年部分节假日安排的通知

各省、自治区、直辖市人民政府，国务院各部委、各直属机构：

经国务院批准，现将2026年元旦、春节、清明节、劳动节、端午节、中秋节和国庆节放假调休日期的具体安排通知如下。

一、元旦：1月1日（周四）放假，共1天。

二、春节：2月17日（周二）至2月23日（周一）放假调休，共7天。2月14日（周六）、2月15日（周日）上班。

三、清明节：4月4日（周六）至4月6日（周一）放假，共3天。

四、劳动节：5月1日（周五）至5月5日（周二）放假调休，共5天。4月26日（周日）、5月9日（周六）上班。

五、端午节：6月19日（周五）至6月21日（周日）放假，共3天。

六、中秋节：9月25日（周五）至9月27日（周日）放假，共3天。

七、国庆节：10月1日（周四）至10月7日（周三）放假调休，共7天。9月27日（周日）、10月10日（周六）上班。

节假日期间，各地区、各部门要妥善安排好值班和安全、保卫、疫情防控等工作，遇有重大突发事件，要按规定及时报告并妥善处置，确保人民群众祥和平安度过节日假期。

国务院办公厅
2025年11月25日
"""


def create_mixed_records_markdown() -> str:
    """创建包含多种记录类型的Markdown内容"""
    return """# 员工考勤记录

## 员工信息
- 工号: EMP001
- 姓名: 张三
- 部门: 技术部

## 2026年1月记录

### 加班记录

**1月5日（周一）**
- 时间: 晚上19:00-22:30
- 时长: 3.5小时
- 项目: 系统上线支持

**1月10日（周六）**
- 时间: 全天
- 时长: 8小时
- 项目: 周末值班

**1月17日（周六）**
- 时间: 上午9:00-下午15:00
- 时长: 6小时
- 项目: 数据库迁移

**1月1日（元旦）**
- 时间: 全天
- 时长: 8小时
- 项目: 节假日值班

### 请假记录

**1月20日（周三）**
- 类型: 事假
- 时长: 4小时（半天）
- 原因: 处理个人事务

**1月25日（周一）**
- 类型: 病假
- 时长: 8小时（一天）
- 原因: 感冒发烧
"""


def get_expected_salary_calculation() -> Dict[str, Any]:
    """获取预期工资计算结果"""
    # 时薪 37.5
    hourly_rate = 37.5

    return {
        'weekday_overtime': {
            'minutes': 210,  # 3.5小时
            'rate': 1.5,
            'pay': 3.5 * 1.5 * hourly_rate  # 196.875
        },
        'weekend_overtime': {
            'minutes': 840,  # 14小时 (8+6)
            'rate': 2.0,
            'pay': 14 * 2.0 * hourly_rate  # 1050.0
        },
        'holiday_overtime': {
            'minutes': 480,  # 8小时
            'rate': 3.0,
            'pay': 8 * 3.0 * hourly_rate  # 900.0
        },
        'total_overtime_pay': 196.875 + 1050.0 + 900.0,  # 2146.875
        'leave_deduction': {
            'personal': 4 * hourly_rate,  # 150.0
            'sick': 8 * hourly_rate  # 300.0
        }
    }


def create_test_dates() -> Dict[str, date]:
    """创建测试日期"""
    return {
        'weekday': date(2026, 1, 5),  # 周一
        'weekend_saturday': date(2026, 1, 10),  # 周六
        'weekend_sunday': date(2026, 1, 11),  # 周日
        'holiday': date(2026, 1, 1),  # 元旦
        'adjusted_workday': date(2026, 2, 14),  # 春节调休上班
        'adjusted_holiday': date(2026, 2, 17),  # 春节调休放假
    }


def create_holiday_config_2026() -> List[Dict[str, Any]]:
    """创建2026年节假日配置数据"""
    return [
        # 元旦
        {'date': date(2026, 1, 1), 'name': '元旦', 'type': 'statutory', 'year': 2026},

        # 春节
        {'date': date(2026, 2, 17), 'name': '春节', 'type': 'statutory', 'year': 2026},
        {'date': date(2026, 2, 18), 'name': '春节', 'type': 'statutory', 'year': 2026},
        {'date': date(2026, 2, 19), 'name': '春节', 'type': 'statutory', 'year': 2026},
        {'date': date(2026, 2, 20), 'name': '春节调休', 'type': 'adjusted_holiday', 'year': 2026},
        {'date': date(2026, 2, 21), 'name': '春节调休', 'type': 'adjusted_holiday', 'year': 2026},
        {'date': date(2026, 2, 22), 'name': '春节调休', 'type': 'adjusted_holiday', 'year': 2026},
        {'date': date(2026, 2, 23), 'name': '春节调休', 'type': 'adjusted_holiday', 'year': 2026},
        {'date': date(2026, 2, 14), 'name': '春节调休上班', 'type': 'adjusted_workday', 'year': 2026},
        {'date': date(2026, 2, 15), 'name': '春节调休上班', 'type': 'adjusted_workday', 'year': 2026},

        # 清明节
        {'date': date(2026, 4, 4), 'name': '清明节', 'type': 'statutory', 'year': 2026},
        {'date': date(2026, 4, 5), 'name': '清明节调休', 'type': 'adjusted_holiday', 'year': 2026},
        {'date': date(2026, 4, 6), 'name': '清明节调休', 'type': 'adjusted_holiday', 'year': 2026},

        # 劳动节
        {'date': date(2026, 5, 1), 'name': '劳动节', 'type': 'statutory', 'year': 2026},
        {'date': date(2026, 5, 2), 'name': '劳动节调休', 'type': 'adjusted_holiday', 'year': 2026},
        {'date': date(2026, 5, 3), 'name': '劳动节调休', 'type': 'adjusted_holiday', 'year': 2026},
        {'date': date(2026, 5, 4), 'name': '劳动节调休', 'type': 'adjusted_holiday', 'year': 2026},
        {'date': date(2026, 5, 5), 'name': '劳动节调休', 'type': 'adjusted_holiday', 'year': 2026},
        {'date': date(2026, 4, 26), 'name': '劳动节调休上班', 'type': 'adjusted_workday', 'year': 2026},
        {'date': date(2026, 5, 9), 'name': '劳动节调休上班', 'type': 'adjusted_workday', 'year': 2026},
    ]
