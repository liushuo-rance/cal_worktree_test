#!/usr/bin/env python3
"""
加班记录管理系统 Web 启动脚本
"""
import os
import sys

# 添加 src 到 Python 路径
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from web import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print("   加班记录管理系统 - Web 界面")
    print("=" * 60)
    print()
    print("启动信息:")
    print(f"  - 项目根目录: {project_root}")
    print(f"  - 数据库路径: {app.config.get('DATABASE', 'data/overtime.db')}")
    print(f"  - 日志文件:   {os.path.join(project_root, 'logs', 'app.log')}")
    print()
    print("访问地址: http://127.0.0.1:5001")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    print()

    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True,
        use_reloader=True
    )
