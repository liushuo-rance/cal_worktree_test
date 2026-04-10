"""
Web模块工具函数
提供数据库连接等公共功能
"""

import sqlite3
from flask import current_app


def get_db():
    """
    获取数据库连接

    Returns:
        sqlite3.Connection: 数据库连接对象
    """
    db_path = current_app.config['DATABASE']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
