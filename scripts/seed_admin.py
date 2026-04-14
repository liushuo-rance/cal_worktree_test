#!/usr/bin/env python3
"""
初始化默认管理员账号脚本
用法:
    python scripts/seed_admin.py
    python scripts/seed_admin.py --password mypassword
"""

import argparse
import os
import sqlite3
import sys

# 将 src 加入路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from db.schema import seed_default_admin


def main():
    parser = argparse.ArgumentParser(description='创建默认管理员账号')
    parser.add_argument(
        '--password',
        default='admin123',
        help='管理员密码（默认: admin123）',
    )
    parser.add_argument(
        '--db',
        default=os.path.join(os.path.dirname(__file__), '..', 'data', 'overtime.db'),
        help='SQLite 数据库路径',
    )
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.db), exist_ok=True)
    conn = sqlite3.connect(args.db)
    try:
        seed_default_admin(conn, password=args.password)
        print(f"管理员账号 'admin' 已创建/已存在（密码: {args.password}）")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
