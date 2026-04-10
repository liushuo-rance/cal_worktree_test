"""
视觉测试配置文件
"""
import pytest
from typing import Generator
from playwright.sync_api import Page, Browser, BrowserContext


@pytest.fixture(scope="session")
def base_url() -> str:
    """测试服务器基础URL"""
    return "http://127.0.0.1:5001"


@pytest.fixture(scope="function")
def page(browser: Browser) -> Generator[Page, None, None]:
    """
    创建新页面实例
    每个测试函数使用独立页面
    """
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        device_scale_factor=1,
    )

    # 启用截图和视频录制（可选）
    page = context.new_page()

    yield page

    context.close()


@pytest.fixture(scope="function")
def mobile_page(browser: Browser) -> Generator[Page, None, None]:
    """移动端页面配置"""
    context = browser.new_context(
        viewport={"width": 375, "height": 667},
        device_scale_factor=2,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
    )
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="function")
def tablet_page(browser: Browser) -> Generator[Page, None, None]:
    """平板页面配置"""
    context = browser.new_context(
        viewport={"width": 768, "height": 1024},
        device_scale_factor=2,
    )
    page = context.new_page()
    yield page
    context.close()
