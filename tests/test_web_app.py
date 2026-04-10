"""
Web应用基础测试
测试Flask应用创建和基本配置
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestWebAppCreation:
    """测试Web应用创建"""

    def test_web_module_imports(self):
        """测试web模块可以导入"""
        from web import create_app
        assert callable(create_app)

    def test_app_factory_creates_app(self):
        """测试应用工厂创建Flask应用"""
        from web import create_app
        app = create_app()
        assert app is not None

    def test_app_has_correct_name(self):
        """测试应用名称正确"""
        from web import create_app
        app = create_app()
        assert app.name == 'web'

    def test_app_is_in_testing_mode(self):
        """测试应用可以设置为测试模式"""
        from web import create_app
        app = create_app({'TESTING': True})
        assert app.config['TESTING'] is True


class TestWebAppClient:
    """测试Web应用客户端"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from web import create_app
        app = create_app({'TESTING': True})
        return app.test_client()

    def test_client_can_make_requests(self, client):
        """测试客户端可以发起请求"""
        response = client.get('/')
        assert response.status_code in [200, 302]  # 200 OK or 302 redirect


class TestDatabaseConfiguration:
    """测试数据库配置"""

    def test_app_has_database_path_config(self):
        """测试应用有数据库路径配置"""
        from web import create_app
        app = create_app({'TESTING': True})
        assert 'DATABASE' in app.config or 'SQLITE_PATH' in app.config


class TestTemplateConfiguration:
    """测试模板配置"""

    def test_app_has_template_folder(self):
        """测试应用配置了模板文件夹"""
        from web import create_app
        app = create_app({'TESTING': True})
        assert app.template_folder is not None

    def test_app_has_static_folder(self):
        """测试应用配置了静态文件夹"""
        from web import create_app
        app = create_app({'TESTING': True})
        assert app.static_folder is not None
