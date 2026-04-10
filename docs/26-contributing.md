# 贡献指南

> 本文档为开发者提供开发环境搭建和代码贡献指南。

---

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档名称 | 贡献指南 |
| 版本 | 1.0 |
| 创建日期 | 2026-04-09 |
| 状态 | 初稿 |

---

## 2. 开发环境要求

### 2.1 系统要求

| 组件 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.9 | 3.12 |
| pip | 21.0 | 最新 |
| Git | 2.30 | 最新 |

### 2.2 操作系统

- macOS 10.15+
- Windows 10/11
- Linux (Ubuntu 20.04+)

---

## 3. 环境搭建

### 3.1 克隆仓库

```bash
git clone <repository-url>
cd 002ot_calculation
```

### 3.2 创建虚拟环境

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 3.3 安装依赖

```bash
# 安装 pytest
pip install pytest pytest-cov

# 安装 Playwright（用于视觉测试）
pip install pytest-playwright playwright
playwright install chromium

# 其他依赖根据提示安装
```

### 3.4 验证安装

```bash
# 运行测试验证
python3 -m pytest tests/ -v

# 启动 Web 应用
python3 run_web.py
```

---

## 4. 项目结构

```
002ot_calculation/
├── src/                          # 源代码
│   ├── cli/                      # 命令行接口
│   ├── db/                       # 数据库模块
│   ├── parsers/                  # 解析器
│   ├── services/                 # 业务服务
│   ├── utils/                    # 工具函数
│   └── web/                      # Web 应用
│       ├── routes/               # 路由处理
│       ├── static/               # 静态资源
│       └── templates/            # HTML 模板
├── tests/                        # 测试代码
│   ├── fixtures/                 # 测试数据
│   └── visual/                   # 视觉测试
├── docs/                         # 文档
├── data/                         # 数据库文件
└── logs/                         # 日志文件
```

---

## 5. 开发工作流

### 5.1 分支策略

```bash
# 创建功能分支
git checkout -b feature/your-feature-name

# 开发完成后提交
git add .
git commit -m "feat: add new feature"

# 推送到远程
git push origin feature/your-feature-name
```

### 5.2 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

| 类型 | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat: add AI parser service` |
| `fix` | Bug 修复 | `fix: correct date parsing` |
| `docs` | 文档更新 | `docs: update API reference` |
| `test` | 测试相关 | `test: add visual regression tests` |
| `refactor` | 代码重构 | `refactor: simplify parser logic` |
| `style` | 代码格式 | `style: fix indentation` |

### 5.3 代码审查清单

提交 PR 前请确认：

- [ ] 所有测试通过 (`pytest tests/`)
- [ ] 代码覆盖率不低于 80%
- [ ] 新增代码有对应测试
- [ ] 文档已同步更新
- [ ] 代码符合项目风格

---

## 6. 测试指南

### 6.1 运行测试

```bash
# 运行所有测试
python3 -m pytest tests/ -v

# 运行特定测试文件
python3 -m pytest tests/test_date_parser.py -v

# 运行特定测试类
python3 -m pytest tests/test_date_parser.py::TestDateParserSingleDate -v

# 运行特定测试方法
python3 -m pytest tests/test_date_parser.py::TestDateParserSingleDate::test_standard_format -v

# 运行并生成覆盖率报告
python3 -m pytest tests/ --cov=src --cov-report=term-missing

# 运行视觉测试
python3 -m pytest tests/visual/ -v
```

### 6.2 编写测试

```python
# tests/test_new_feature.py
import pytest
from src.services.new_service import new_function

class TestNewFeature:
    """新功能测试"""

    def test_happy_path(self):
        """测试正常场景"""
        result = new_function("valid_input")
        assert result == expected_output

    def test_edge_case(self):
        """测试边界条件"""
        result = new_function("")
        assert result is None

    def test_error_handling(self):
        """测试错误处理"""
        with pytest.raises(ValueError):
            new_function("invalid_input")
```

### 6.3 视觉测试

```python
# tests/visual/test_new_page.py
from playwright.sync_api import Page

def test_new_page_visual(page: Page, base_url: str):
    """新页面视觉测试"""
    page.goto(f"{base_url}/new-page")
    page.wait_for_selector("h1")
    page.screenshot(path="tests/visual/screenshots/new-page.png")
```

---

## 7. 代码风格

### 7.1 Python 规范

- 遵循 [PEP 8](https://pep8.org/) 规范
- 使用 4 空格缩进
- 行长度不超过 100 字符
- 使用有意义的变量名

### 7.2 文档字符串

```python
def parse_date(date_str: str) -> date:
    """
    解析日期字符串

    Args:
        date_str: 日期字符串，如 "2025.08.15"

    Returns:
        datetime.date 对象

    Raises:
        DateParseError: 日期格式无效时

    Examples:
        >>> parse_date("2025.08.15")
        datetime.date(2025, 8, 15)
    """
    # 实现代码
```

### 7.3 类型注解

```python
from typing import Dict, List, Optional

def process_records(
    records: List[Dict[str, Any]],
    employee_id: str,
    validate: bool = True
) -> Dict[str, int]:
    """
    处理记录列表

    Args:
        records: 记录字典列表
        employee_id: 员工ID
        validate: 是否验证数据

    Returns:
        处理结果统计
    """
```

---

## 8. 调试技巧

### 8.1 Flask 调试

```bash
# 启用调试模式
export FLASK_DEBUG=1
python run_web.py
```

### 8.2 数据库调试

```python
# 在代码中添加调试输出
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Query: {query}")
logger.debug(f"Params: {params}")
```

### 8.3 日志查看

```bash
# 实时查看日志
tail -f logs/app.log

# 查看最后 100 行
tail -n 100 logs/app.log | less
```

---

## 9. 常见问题

### 9.1 数据库锁定

**症状**: `sqlite3.OperationalError: database is locked`

**解决**:
```bash
# 关闭所有使用数据库的进程
# 重启应用
pkill -f "python run_web.py"
python run_web.py
```

### 9.2 模块导入错误

**症状**: `ModuleNotFoundError: No module named 'src'`

**解决**:
```bash
# 确保在正确目录运行
pwd  # 应该是 002ot_calculation 目录

# 检查 PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

### 9.3 测试失败

**症状**: 测试在本地通过但在 CI 失败

**解决**:
```bash
# 清除缓存
python3 -m pytest --cache-clear

# 重新安装依赖
pip install --force-reinstall pytest pytest-cov
```

---

## 10. 相关资源

- [07-testing-strategy.md](./07-testing-strategy.md) - 测试策略
- [24-env-config.md](./24-env-config.md) - 环境配置
- [25-api-reference.md](./25-api-reference.md) - API 参考
- [22-visual-testing-guide.md](./22-visual-testing-guide.md) - 视觉测试指南

---

## 11. 联系方式

如有问题，请通过以下方式联系：

- 提交 Issue
- 发送邮件
- 在讨论区提问
