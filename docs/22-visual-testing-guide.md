# 视觉测试完整指南

> 本文档详细介绍如何在加班记录分析系统中使用 Playwright 进行视觉回归测试。

---

## 📋 目录

1. [快速开始](#快速开始)
2. [测试结构](#测试结构)
3. [编写视觉测试](#编写视觉测试)
4. [运行测试](#运行测试)
5. [截图管理](#截图管理)
6. [CI/CD 集成](#cicd-集成)
7. [故障排除](#故障排除)

---

## 快速开始

### 1. 安装依赖

```bash
# 安装 Playwright Python 库
pip install pytest-playwright playwright

# 安装浏览器（只需执行一次）
playwright install chromium

# 可选：安装所有浏览器
playwright install
```

### 2. 启动应用

```bash
# 在后台启动 Flask 应用
python run_web.py &

# 等待服务启动
sleep 3
```

### 3. 运行测试

```bash
# 运行所有视觉测试
python -m pytest tests/visual/ -v

# 运行特定测试文件
python -m pytest tests/visual/test_critical_pages.py -v

# 运行组件测试
python -m pytest tests/visual/test_components.py -v
```

---

## 测试结构

### 目录组织

```
tests/visual/
├── __init__.py                      # 模块初始化
├── conftest.py                      # 共享 fixtures
├── test_critical_pages.py           # 核心页面测试
├── test_components.py               # 组件级测试
└── screenshots/                     # 生成的截图
    ├── dashboard.png
    ├── employee-list.png
    └── ...
```

### Fixtures 说明

```python
# conftest.py 提供的 fixtures

@pytest.fixture
def page(browser) -> Page:
    """桌面端页面实例 (1440x900)"""
    
@pytest.fixture
def mobile_page(browser) -> Page:
    """移动端页面实例 (375x667)"""
    
@pytest.fixture
def tablet_page(browser) -> Page:
    """平板页面实例 (768x1024)"""
    
@pytest.fixture
def base_url() -> str:
    """应用基础 URL: http://127.0.0.1:5001"""
```

---

## 编写视觉测试

### 基础页面测试

```python
from playwright.sync_api import Page

def test_page_visual(page: Page, base_url: str):
    """基础视觉测试模板"""
    # 1. 访问页面
    page.goto(f"{base_url}/your-page")
    
    # 2. 等待关键元素
    page.wait_for_selector("h1", timeout=5000)
    
    # 3. 截图
    page.screenshot(
        path="tests/visual/screenshots/your-page.png",
        full_page=True  # 整页截图
    )
```

### 响应式测试

```python
def test_responsive_design(page: Page, base_url: str):
    """响应式测试 - 多个断点"""
    viewports = [
        {"name": "mobile", "width": 375, "height": 667},
        {"name": "tablet", "width": 768, "height": 1024},
        {"name": "desktop", "width": 1440, "height": 900},
    ]
    
    for vp in viewports:
        page.set_viewport_size({
            "width": vp["width"],
            "height": vp["height"]
        })
        
        page.goto(f"{base_url}/your-page")
        
        page.screenshot(
            path=f"tests/visual/screenshots/your-page-{vp['name']}.png"
        )
```

### 组件级测试

```python
def test_component_isolated(page: Page, base_url: str):
    """组件级视觉测试"""
    page.goto(f"{base_url}/your-page")
    
    # 只截取特定组件
    component = page.locator(".your-component").first
    
    component.screenshot(
        path="tests/visual/screenshots/component-name.png"
    )
```

### 交互状态测试

```python
def test_hover_state(page: Page, base_url: str):
    """测试 hover 状态"""
    page.goto(f"{base_url}/your-page")
    
    # 找到元素并 hover
    button = page.locator("button.primary").first
    button.hover()
    
    # 等待动画完成
    page.wait_for_timeout(300)
    
    # 截图
    button.screenshot(path="tests/visual/screenshots/button-hover.png")
```

---

## 运行测试

### 基本命令

| 命令 | 说明 |
|------|------|
| `pytest tests/visual/` | 运行所有视觉测试 |
| `pytest tests/visual/ -v` | 显示详细输出 |
| `pytest tests/visual/ -s` | 显示 print 输出 |
| `pytest tests/visual/ --headed` | 显示浏览器窗口（非无头模式） |
| `pytest tests/visual/ -k "dashboard"` | 只运行包含 dashboard 的测试 |

### 特定测试

```bash
# 运行特定文件
pytest tests/visual/test_critical_pages.py

# 运行特定类
pytest tests/visual/test_critical_pages.py::TestDashboardPage

# 运行特定方法
pytest tests/visual/test_critical_pages.py::TestDashboardPage::test_dashboard_loads_correctly

# 运行多个匹配
pytest tests/visual/ -k "mobile or tablet"
```

### 调试选项

```bash
# 有界面模式（看到浏览器操作）
pytest tests/visual/ --headed

# 慢速模式（每个操作延迟）
pytest tests/visual/ --slowmo 1000

# 保留浏览器打开（调试用）
pytest tests/visual/ --headed --slowmo 500

# 显示追踪
pytest tests/visual/ --tracing=on
```

---

## 截图管理

### 截图选项

```python
# 整页截图
page.screenshot(path="full.png", full_page=True)

# 元素截图
element.screenshot(path="element.png")

# 指定区域
page.screenshot(path="clip.png", clip={"x": 0, "y": 0, "width": 800, "height": 600})

# 带遮罩（隐藏动态内容）
page.screenshot(
    path="masked.png",
    mask=[page.locator(".timestamp"), page.locator(".random-id")]
)

# 指定类型和质量
page.screenshot(path="quality.png", type="jpeg", quality=80)
```

### 处理动态内容

```python
# 方法1: 隐藏动态元素
def test_with_hidden_dynamic(page: Page, base_url: str):
    page.goto(f"{base_url}/dashboard")
    
    # 使用 CSS 隐藏时间戳等动态内容
    page.add_style_tag(content="""
        .timestamp, .current-time, .random-id {
            visibility: hidden !important;
        }
    """)
    
    page.screenshot(path="tests/visual/screenshots/dashboard.png")

# 方法2: 使用遮罩
def test_with_mask(page: Page, base_url: str):
    page.goto(f"{base_url}/dashboard")
    
    page.screenshot(
        path="tests/visual/screenshots/dashboard.png",
        mask=[
            page.locator(".timestamp"),
            page.locator(".live-counter"),
        ]
    )

# 方法3: 等待网络空闲
def test_wait_for_stable(page: Page, base_url: str):
    page.goto(f"{base_url}/dashboard")
    
    # 等待所有网络请求完成
    page.wait_for_load_state("networkidle")
    
    page.screenshot(path="tests/visual/screenshots/dashboard.png")
```

---

## CI/CD 集成

### GitHub Actions 配置

```yaml
# .github/workflows/visual-tests.yml
name: Visual Regression Tests

on: [push, pull_request]

jobs:
  visual-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest-playwright
          playwright install chromium
      
      - name: Start Flask app
        run: |
          python run_web.py &
          sleep 3
      
      - name: Run visual tests
        run: pytest tests/visual/ -v
      
      - name: Upload screenshots
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: visual-test-screenshots
          path: tests/visual/screenshots/
```

### 截图对比基线

```bash
# 更新基线截图（UI 有意变更时）
pytest tests/visual/ --update-snapshots

# 只更新特定测试的基线
pytest tests/visual/test_critical_pages.py::TestDashboardPage --update-snapshots
```

---

## 故障排除

### 常见问题

#### 1. 浏览器启动失败

```
Error: Executable doesn't exist
```

**解决:**
```bash
# 重新安装浏览器
playwright install chromium

# 或强制重新安装
playwright install --force chromium
```

#### 2. 连接被拒绝

```
Error: net::ERR_CONNECTION_REFUSED
```

**解决:**
```bash
# 确保 Flask 应用已启动
python run_web.py &
sleep 3

# 检查端口
lsof -i :5001
```

#### 3. 选择器找不到元素

```
TimeoutError: waiting for selector ".stat-card"
```

**解决:**
```python
# 使用更通用的选择器
page.wait_for_selector(".container", timeout=10000)

# 或等待多个选择器中的任意一个
page.wait_for_selector(".card, .panel, .container")

# 检查元素是否真的存在
elements = page.locator(".stat-card").all()
print(f"找到 {len(elements)} 个元素")
```

#### 4. 截图不一致

**原因:**
- 动态内容（时间戳、随机ID）
- 字体渲染差异
- 动画未完成

**解决:**
```python
# 隐藏动态内容
page.evaluate("""
    document.querySelectorAll('.timestamp').forEach(el => {
        el.style.visibility = 'hidden';
    });
""")

# 等待动画完成
page.wait_for_timeout(500)

# 使用遮罩
page.screenshot(path="test.png", mask=[page.locator(".dynamic")])
```

---

## 最佳实践

### ✅ 应该做的

1. **使用语义化选择器**
   ```python
   # ✅ 好
   page.locator("button:has-text('提交')")
   page.locator("[data-testid='submit-button']")
   
   # ❌ 避免
   page.locator(".btn-xyz-123")  # 易变的 class
   ```

2. **等待元素可见再截图**
   ```python
   element = page.locator(".card").first
   element.wait_for(state="visible")
   element.screenshot(path="card.png")
   ```

3. **使用 fixtures 复用配置**
   ```python
   @pytest.fixture
   def logged_in_page(page, base_url):
       page.goto(f"{base_url}/login")
       page.fill("[name=username]", "test")
       page.fill("[name=password]", "test")
       page.click("button[type=submit]")
       return page
   ```

### ❌ 应该避免的

1. **不要在测试中使用固定等待**
   ```python
   # ❌ 避免
   import time
   time.sleep(5)
   
   # ✅ 推荐
   page.wait_for_selector(".loaded", timeout=5000)
   ```

2. **不要测试实现细节**
   ```python
   # ❌ 避免
   assert page.evaluate("window.innerWidth") == 1440
   
   # ✅ 推荐
   page.set_viewport_size({"width": 1440, "height": 900})
   ```

---

## 相关资源

- [Playwright Python 文档](https://playwright.dev/python/)
- [pytest-playwright 文档](https://github.com/microsoft/playwright-pytest)
- [视觉回归测试最佳实践](https://playwright.dev/python/docs/test-snapshots)

---

**最后更新**: 2026-04-08  
**维护者**: Claude Code
