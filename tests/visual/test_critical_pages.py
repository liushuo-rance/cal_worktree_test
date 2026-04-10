"""
关键页面视觉回归测试
测试系统核心页面的视觉呈现
"""
import pytest
from playwright.sync_api import Page, expect


class TestDashboardPage:
    """仪表盘页面视觉测试"""

    def test_dashboard_loads_correctly(self, page: Page, base_url: str):
        """测试仪表盘页面正常加载"""
        page.goto(base_url)

        # 等待关键元素加载
        page.wait_for_selector("h1", timeout=5000)

        # 验证页面标题
        title = page.locator("h1").first
        expect(title).to_be_visible()

        # 截图保存
        screenshot_path = "tests/visual/screenshots/dashboard.png"
        page.screenshot(path=screenshot_path, full_page=True)

        print(f"✓ 仪表盘截图已保存: {screenshot_path}")

    def test_dashboard_stats_cards(self, page: Page, base_url: str):
        """测试统计卡片显示"""
        page.goto(base_url)

        # 等待统计卡片加载
        page.wait_for_selector(".stat-card, .card, [class*='stat']", timeout=5000)

        # 截图
        screenshot_path = "tests/visual/screenshots/dashboard-stats.png"
        page.screenshot(path=screenshot_path, full_page=True)

        print(f"✓ 仪表盘统计截图已保存: {screenshot_path}")


class TestEmployeePages:
    """员工页面视觉测试"""

    def test_employee_list_page(self, page: Page, base_url: str):
        """测试员工列表页"""
        page.goto(f"{base_url}/employees")

        # 等待表格或列表加载
        page.wait_for_load_state("networkidle")

        # 隐藏动态内容（如操作按钮中的ID）
        page.evaluate("""
            document.querySelectorAll('td').forEach(td => {
                if (td.textContent.includes('@')) {
                    td.style.opacity = '0.5';
                }
            });
        """)

        screenshot_path = "tests/visual/screenshots/employee-list.png"
        page.screenshot(path=screenshot_path, full_page=True)

        print(f"✓ 员工列表截图已保存: {screenshot_path}")

    def test_employee_detail_page(self, page: Page, base_url: str):
        """测试员工详情页（假设第一个员工）"""
        # 先访问列表页获取第一个员工链接
        page.goto(f"{base_url}/employees")
        page.wait_for_load_state("networkidle")

        # 查找第一个员工链接并点击
        first_link = page.locator("a[href*='/employees/']").first
        if first_link.is_visible():
            first_link.click()
            page.wait_for_load_state("networkidle")

            screenshot_path = "tests/visual/screenshots/employee-detail.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"✓ 员工详情截图已保存: {screenshot_path}")
        else:
            print("⚠ 未找到员工链接，跳过详情页测试")


class TestImportPages:
    """导入功能页面视觉测试"""

    def test_import_form_page(self, page: Page, base_url: str):
        """测试导入表单页"""
        page.goto(f"{base_url}/records/import/")

        # 等待表单加载
        page.wait_for_selector("form, input[type='file']", timeout=5000)

        screenshot_path = "tests/visual/screenshots/import-form.png"
        page.screenshot(path=screenshot_path, full_page=True)

        print(f"✓ 导入表单截图已保存: {screenshot_path}")

    def test_import_form_with_validation(self, page: Page, base_url: str):
        """测试导入表单验证状态"""
        page.goto(f"{base_url}/records/import/")

        # 点击提交按钮触发表单验证（不选择文件）
        submit_btn = page.locator("button[type='submit'], input[type='submit']").first
        if submit_btn.is_visible():
            submit_btn.click()

            # 等待验证提示
            page.wait_for_timeout(500)

            screenshot_path = "tests/visual/screenshots/import-form-validation.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"✓ 导入表单验证截图已保存: {screenshot_path}")


class TestHolidaysPage:
    """节假日管理页面视觉测试"""

    def test_holidays_list_page(self, page: Page, base_url: str):
        """测试节假日列表页"""
        page.goto(f"{base_url}/holidays")

        page.wait_for_load_state("networkidle")

        screenshot_path = "tests/visual/screenshots/holidays-list.png"
        page.screenshot(path=screenshot_path, full_page=True)

        print(f"✓ 节假日列表截图已保存: {screenshot_path}")

    def test_holidays_import_page(self, page: Page, base_url: str):
        """测试节假日导入页"""
        page.goto(f"{base_url}/holidays/import")

        page.wait_for_load_state("networkidle")

        screenshot_path = "tests/visual/screenshots/holidays-import.png"
        page.screenshot(path=screenshot_path, full_page=True)

        print(f"✓ 节假日导入截图已保存: {screenshot_path}")


class TestReportsPage:
    """报表页面视觉测试"""

    def test_reports_index_page(self, page: Page, base_url: str):
        """测试报表首页"""
        page.goto(f"{base_url}/reports")

        page.wait_for_load_state("networkidle")

        screenshot_path = "tests/visual/screenshots/reports-index.png"
        page.screenshot(path=screenshot_path, full_page=True)

        print(f"✓ 报表首页截图已保存: {screenshot_path}")


class TestResponsiveDesign:
    """响应式设计视觉测试"""

    def test_dashboard_mobile(self, mobile_page: Page, base_url: str):
        """测试仪表盘移动端显示"""
        mobile_page.goto(base_url)
        mobile_page.wait_for_load_state("networkidle")

        screenshot_path = "tests/visual/screenshots/dashboard-mobile.png"
        mobile_page.screenshot(path=screenshot_path, full_page=True)

        print(f"✓ 仪表盘移动端截图已保存: {screenshot_path}")

    def test_employee_list_mobile(self, mobile_page: Page, base_url: str):
        """测试员工列表移动端显示"""
        mobile_page.goto(f"{base_url}/employees")
        mobile_page.wait_for_load_state("networkidle")

        screenshot_path = "tests/visual/screenshots/employee-list-mobile.png"
        mobile_page.screenshot(path=screenshot_path, full_page=True)

        print(f"✓ 员工列表移动端截图已保存: {screenshot_path}")

    def test_import_page_tablet(self, tablet_page: Page, base_url: str):
        """测试导入页面平板端显示"""
        tablet_page.goto(f"{base_url}/records/import/")
        tablet_page.wait_for_load_state("networkidle")

        screenshot_path = "tests/visual/screenshots/import-page-tablet.png"
        tablet_page.screenshot(path=screenshot_path, full_page=True)

        print(f"✓ 导入页面平板端截图已保存: {screenshot_path}")
