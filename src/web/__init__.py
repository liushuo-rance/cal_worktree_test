"""
Web模块
Flask应用工厂
"""

from flask import Flask
from flask_session import Session
import os
import sqlite3
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Add src to path for importing db.schema
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db.schema import init_database, create_views


def setup_logging(app):
    """配置日志记录"""
    # 日志目录
    log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, 'app.log')

    # 文件处理器 - 记录所有日志
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)

    # 控制台处理器 - 只记录 INFO 及以上
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    console_handler.setFormatter(console_formatter)

    # 配置根日志记录器
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.DEBUG)

    # 记录启动信息
    app.logger.info(f"日志文件位置: {log_file}")


def create_app(test_config=None):
    """
    创建Flask应用实例

    Args:
        test_config: 测试配置字典，用于测试时覆盖默认配置

    Returns:
        Flask应用实例
    """
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static'
    )

    # 配置日志
    setup_logging(app)

    # 默认配置
    default_db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'overtime.db')
    # Ensure data directory exists
    os.makedirs(os.path.dirname(default_db_path), exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
        DATABASE=default_db_path,
        # 服务器端session配置（文件系统存储，避免cookie 4KB限制）
        SESSION_TYPE='filesystem',
        SESSION_FILE_DIR=os.path.join(os.path.dirname(__file__), '..', '..', '.flask_session'),
        SESSION_PERMANENT=False,
        SESSION_USE_SIGNER=True,
    )
    # 确保session目录存在
    os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
    # 初始化服务器端session
    Session(app)

    # 加载测试配置或配置文件
    if test_config is None:
        # 加载实例配置（如果存在）
        app.config.from_pyfile('config.py', silent=True)
    else:
        # 加载测试配置
        app.config.from_mapping(test_config)

    # 确保实例文件夹存在
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # 初始化数据库
    def init_db():
        """初始化数据库表结构"""
        db_path = app.config['DATABASE']
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        init_database(conn)
        create_views(conn)
        conn.close()
        app.logger.info(f"数据库初始化完成: {db_path}")

    # 在应用启动时初始化数据库
    init_db()

    # 注册数据库连接
    def get_db():
        """获取数据库连接"""
        if 'db' not in app.extensions:
            db_path = app.config['DATABASE']
            # Ensure directory exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            app.extensions['db'] = sqlite3.connect(db_path)
            app.extensions['db'].row_factory = sqlite3.Row
        return app.extensions['db']

    @app.before_request
    def before_request():
        """每个请求前获取数据库连接"""
        get_db()

    @app.teardown_appcontext
    def close_db(exception):
        """关闭数据库连接"""
        db = app.extensions.pop('db', None)
        if db is not None:
            db.close()

    # 注册蓝图
    from web.routes import dashboard, employees, records, review, reports, holidays, api, notifications, assistant, settings
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(employees.bp)
    app.register_blueprint(records.bp)
    app.register_blueprint(review.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(holidays.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(notifications.bp)
    app.register_blueprint(assistant.bp)
    app.register_blueprint(settings.bp)

    # APScheduler 自动通知
    scheduler_enabled = os.environ.get('SCHEDULER_ENABLED', 'false').lower() == 'true'
    if scheduler_enabled:
        from apscheduler.schedulers.background import BackgroundScheduler
        from services.notification_service import run_scheduled_comp_off_notification

        scheduler = BackgroundScheduler()

        def scheduled_notification_job():
            db_path = app.config['DATABASE']
            conn = sqlite3.connect(db_path)
            try:
                run_scheduled_comp_off_notification(conn)
            except Exception as e:
                app.logger.error(f"定时调休提醒任务失败: {e}")
            finally:
                conn.close()

        scheduler.add_job(
            scheduled_notification_job,
            'cron',
            hour=9,
            minute=0,
            id='comp_off_expiry_notification',
            replace_existing=True
        )
        scheduler.start()
        app.logger.info("APScheduler 已启动: 每天 09:00 发送调休到期提醒")

    # 注册自定义模板过滤器
    @app.template_filter('strptime')
    def strptime_filter(value, format='%Y-%m-%d'):
        """将字符串解析为 datetime 对象"""
        if value is None:
            return None
        return datetime.strptime(value, format)

    @app.template_filter('strftime')
    def strftime_filter(value, format='%Y-%m-%d'):
        """将 datetime 对象格式化为字符串"""
        if value is None:
            return ''
        return value.strftime(format)

    @app.template_filter('weekday_name')
    def weekday_name_filter(value):
        """获取星期名称"""
        if value is None:
            return '-'
        weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        # value 可以是 datetime 对象或字符串
        if isinstance(value, str):
            dt = datetime.strptime(value, '%Y-%m-%d')
        else:
            dt = value
        # weekday(): Monday=0, Sunday=6
        return weekdays[dt.weekday()]

    return app
