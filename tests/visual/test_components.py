"""
组件级视觉测试
测试独立UI组件的视觉呈现
"""
import pytest
from playwright.sync_api import Page


class TestFormComponents:
    """表单组件视觉测试"""

    def test_file_upload_component(self, page: Page, base_url: str):
        """测试文件上传组件"""
        page.goto(f"{base_url}/records/import/")

        # 聚焦到上传区域
        upload_area = page.locator("input[type='file']").first
        if upload_area.is_visible():
            # 模拟hover状态
            upload_area.hover()
            page.wait_for_timeout(300)

            screenshot_path = "tests/visual/screenshots/component-file-upload.png"
            page.screenshot(path=screenshot_path)
            print(f"✓ 文件上传组件截图已保存")

    def test_select_dropdown(self, page: Page, base_url: str):
        """测试下拉选择组件"""
        page.goto(f"{base_url}/records/import/")

        # 打开下拉框
        select = page.locator("select").first
        if select.is_visible():
            select.click()
            page.wait_for_timeout(500)

            screenshot_path = "tests/visual/screenshots/component-select-dropdown.png"
            page.screenshot(path=screenshot_path)
            print(f"✓ 下拉选择组件截图已保存")

    def test_form_validation_states(self, page: Page, base_url: str):
        """测试表单验证状态"""
        page.goto(f"{base_url}/records/import/")

        # 直接提交表单触发验证
        submit = page.locator("button[type='submit']").first
        if submit.is_visible():
            submit.click()
            page.wait_for_timeout(500)

            screenshot_path = "tests/visual/screenshots/component-form-validation.png"
            page.screenshot(path=screenshot_path)
            print(f"✓ 表单验证状态截图已保存")


class TestNavigationComponents:
    """导航组件视觉测试"""

    def test_main_navigation(self, page: Page, base_url: str):
        """测试主导航栏"""
        page.goto(base_url)

        # 只截取导航栏部分
        nav = page.locator("nav, header").first
        if nav.is_visible():
            screenshot_path = "tests/visual/screenshots/component-navigation.png"
            nav.screenshot(path=screenshot_path)
            print(f"✓ 导航栏组件截图已保存")

    def test_mobile_navigation_menu(self, mobile_page: Page, base_url: str):
        """测试移动端导航菜单"""
        mobile_page.goto(base_url)

        # 点击汉堡菜单
        menu_btn = mobile_page.locator("button[aria-label='menu'], .menu-btn, .navbar-toggler").first
        if menu_btn.is_visible():
            menu_btn.click()
            mobile_page.wait_for_timeout(500)

            screenshot_path = "tests/visual/screenshots/component-mobile-nav.png"
            mobile_page.screenshot(path=screenshot_path)
            print(f"✓ 移动端导航截图已保存")


class TestDataTableComponents:
    """数据表格组件视觉测试"""

    def test_table_header(self, page: Page, base_url: str):
        """测试表格表头"""
        page.goto(f"{base_url}/employees")
        page.wait_for_load_state("networkidle")

        # 只截取表头
        thead = page.locator("thead").first
        if thead.is_visible():
            screenshot_path = "tests/visual/screenshots/component-table-header.png"
            thead.screenshot(path=screenshot_path)
            print(f"✓ 表格表头截图已保存")

    def test_table_row_hover(self, page: Page, base_url: str):
        """测试表格行hover效果"""
        page.goto(f"{base_url}/employees")
        page.wait_for_load_state("networkidle")

        # hover第一行数据
        first_row = page.locator("tbody tr").first
        if first_row.is_visible():
            first_row.hover()
            page.wait_for_timeout(300)

            screenshot_path = "tests/visual/screenshots/component-table-row-hover.png"
            first_row.screenshot(path=screenshot_path)
            print(f"✓ 表格行hover截图已保存")


class TestButtonComponents:
    """按钮组件视觉测试"""

    def test_primary_button(self, page: Page, base_url: str):
        """测试主按钮样式"""
        page.goto(f"{base_url}/records/import/")

        primary_btn = page.locator("button[type='submit'], .btn-primary").first
        if primary_btn.is_visible():
            screenshot_path = "tests/visual/screenshots/component-button-primary.png"
            primary_btn.screenshot(path=screenshot_path)
            print(f"✓ 主按钮截图已保存")

    def test_button_hover_state(self, page: Page, base_url: str):
        """测试按钮hover状态"""
        page.goto(f"{base_url}/records/import/")

        btn = page.locator("button").first
        if btn.is_visible():
            btn.hover()
            page.wait_for_timeout(300)

            screenshot_path = "tests/visual/screenshots/component-button-hover.png"
            btn.screenshot(path=screenshot_path)
            print(f"✓ 按钮hover截图已保存")


class TestCardComponents:
    """卡片组件视觉测试"""

    def test_stat_cards(self, page: Page, base_url: str):
        """测试统计卡片"""
        page.goto(base_url)

        # 查找卡片元素
        cards = page.locator(".card, [class*='card']")
        if cards.count() > 0:
            first_card = cards.first
            screenshot_path = "tests/visual/screenshots/component-stat-card.png"
            first_card.screenshot(path=screenshot_path)
            print(f"✓ 统计卡片截图已保存")

    def test_info_cards(self, page: Page, base_url: str):
        """测试信息卡片"""
        page.goto(f"{base_url}/employees")

        # 查找员工信息卡片
        cards = page.locator(".employee-card, .info-card, [class*='employee']").all()
        if len(cards) > 0:
            screenshot_path = "tests/visual/screenshots/component-info-card.png"
            cards[0].screenshot(path=screenshot_path)
            print(f"✓ 信息卡片截图已保存")


class TestModalComponents:
    """模态框组件视觉测试"""

    def test_edit_modal(self, page: Page, base_url: str):
        """测试编辑模态框"""
        page.goto(f"{base_url}/employees")
        page.wait_for_load_state("networkidle")

        # 查找并点击编辑按钮
        edit_btn = page.locator("button:has-text('编辑'), .edit-btn, a:has-text('编辑')").first
        if edit_btn.is_visible():
            edit_btn.click()
            page.wait_for_timeout(500)

            # 截图模态框
            modal = page.locator(".modal, [role='dialog'], .popup").first
            if modal.is_visible():
                screenshot_path = "tests/visual/screenshots/component-edit-modal.png"
                modal.screenshot(path=screenshot_path)
                print(f"✓ 编辑模态框截图已保存")

                # 关闭模态框
                page.keyboard.press("Escape")


class TestLoadingStates:
    """加载状态视觉测试"""

    def test_loading_spinner(self, page: Page, base_url: str):
        """测试加载动画"""
        page.goto(f"{base_url}/records/import/")

        # 模拟加载状态（如果有）
        page.evaluate("""
            // 添加临时loading元素用于测试
            const spinner = document.createElement('div');
            spinner.className = 'loading-spinner';
            spinner.innerHTML = '<div class="spinner"></div><span>加载中...</span>';
            document.body.appendChild(spinner);
        """)

        page.wait_for_timeout(300)

        spinner = page.locator(".loading-spinner").first
        if spinner.is_visible():
            screenshot_path = "tests/visual/screenshots/component-loading-spinner.png"
            spinner.screenshot(path=screenshot_path)
            print(f"✓ 加载动画截图已保存")

    def test_skeleton_screen(self, page: Page, base_url: str):
        """测试骨架屏"""
        page.goto(f"{base_url}/employees")

        # 在数据加载前截图（模拟骨架屏）
        page.evaluate("""
            document.body.innerHTML = `
                <div class="skeleton">
                    <div class="skeleton-header"></div>
                    <div class="skeleton-row"></div>
                    <div class="skeleton-row"></div>
                </div>
            `;
        """)

        page.wait_for_timeout(300)

        screenshot_path = "tests/visual/screenshots/component-skeleton.png"
        page.screenshot(path=screenshot_path)
        print(f"✓ 骨架屏截图已保存")


class TestEmptyStates:
    """空状态视觉测试"""

    def test_empty_table_state(self, page: Page, base_url: str):
        """测试空表格状态"""
        # 访问可能没有数据的页面
        page.goto(f"{base_url}/records/review")
        page.wait_for_load_state("networkidle")

        # 查找空状态提示
        empty_state = page.locator(".empty-state, .no-data, [class*='empty']").first
        if empty_state.is_visible():
            screenshot_path = "tests/visual/screenshots/component-empty-state.png"
            empty_state.screenshot(path=screenshot_path)
            print(f"✓ 空状态截图已保存")

    def test_error_state(self, page: Page, base_url: str):
        """测试错误状态"""
        # 访问不存在的页面触发404
        page.goto(f"{base_url}/non-existent-page")
        page.wait_for_load_state("networkidle")

        screenshot_path = "tests/visual/screenshots/component-error-state.png"
        page.screenshot(path=screenshot_path)
        print(f"✓ 错误状态截图已保存")
