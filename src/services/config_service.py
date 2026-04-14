"""
应用配置服务
支持从数据库读取配置，缺失时回退到环境变量
"""

import os
import sqlite3
from typing import Dict, Any, Optional


# 配置项默认值与对应的环境变量名
_CONFIG_DEFAULTS: Dict[str, str] = {
    "VOLCES_API_KEY": "",
    "VOLCES_BASE_URL": "https://ark.cn-beijing.volces.com/api/v3",
    "VOLCES_MODEL": "",
    "SMTP_HOST": "",
    "SMTP_PORT": "587",
    "SMTP_USER": "",
    "SMTP_PASSWORD": "",
    "SMTP_FROM": "",
    "HR_NOTIFICATION_EMAIL": "",
}


def get_config(conn: sqlite3.Connection, key: str, default: Optional[str] = None) -> str:
    """
    读取单个配置项，优先从数据库获取，缺失时回退环境变量和默认值

    Args:
        conn: 数据库连接
        key: 配置键名
        default: 额外默认值

    Returns:
        配置值字符串
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT config_value FROM app_config WHERE config_key = ?",
        (key,)
    )
    row = cursor.fetchone()

    if row is not None and row["config_value"] is not None:
        return row["config_value"]

    env_default = _CONFIG_DEFAULTS.get(key, "")
    return os.environ.get(key, default if default is not None else env_default)


def set_config(conn: sqlite3.Connection, key: str, value: str) -> None:
    """
    写入或更新单个配置项

    Args:
        conn: 数据库连接
        key: 配置键名
        value: 配置值
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO app_config (config_key, config_value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(config_key) DO UPDATE SET
            config_value = excluded.config_value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (key, value)
    )
    conn.commit()


def get_all_configs(conn: sqlite3.Connection) -> Dict[str, str]:
    """
    获取所有已知配置项的当前值（数据库 + 环境变量回退）

    Args:
        conn: 数据库连接

    Returns:
        配置字典
    """
    result: Dict[str, str] = {}
    for key in _CONFIG_DEFAULTS:
        result[key] = get_config(conn, key)
    return result


def build_email_config(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    构建邮件配置字典（从配置服务读取）

    Args:
        conn: 数据库连接

    Returns:
        邮件配置字典
    """
    host = get_config(conn, "SMTP_HOST")
    port_str = get_config(conn, "SMTP_PORT")
    try:
        port = int(port_str) if port_str else 587
    except ValueError:
        port = 587

    user = get_config(conn, "SMTP_USER")
    password = get_config(conn, "SMTP_PASSWORD")
    from_addr = get_config(conn, "SMTP_FROM")
    if not from_addr:
        from_addr = user

    hr_raw = get_config(conn, "HR_NOTIFICATION_EMAIL")
    hr_emails = [e.strip() for e in hr_raw.split(",") if e.strip()] if hr_raw else []

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_addr": from_addr,
        "hr_emails": hr_emails,
        "is_configured": bool(host and user and password and hr_emails),
    }


def build_ai_config(conn: sqlite3.Connection) -> Dict[str, str]:
    """
    构建 AI 解析配置字典

    Args:
        conn: 数据库连接

    Returns:
        AI 配置字典
    """
    base_url = get_config(conn, "VOLCES_BASE_URL")
    if not base_url:
        base_url = _CONFIG_DEFAULTS["VOLCES_BASE_URL"]

    return {
        "api_key": get_config(conn, "VOLCES_API_KEY"),
        "base_url": base_url,
        "model": get_config(conn, "VOLCES_MODEL"),
    }
