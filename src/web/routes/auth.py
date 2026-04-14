"""
认证路由
提供登录、登出、当前用户信息查询
"""

import sqlite3

from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from werkzeug.security import check_password_hash

from web.utils import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')


def _is_api_request() -> bool:
    """判断当前请求是否为 API/JSON 请求"""
    if request.is_json:
        return True
    accept = request.headers.get('Accept', '')
    if 'application/json' in accept:
        return True
    return False


def _json_response(success: bool, data=None, error=None, message='', status=200):
    """构造统一 JSON 响应"""
    return (
        jsonify(
            {
                'success': success,
                'data': data,
                'error': error,
                'message': message,
            }
        ),
        status,
    )


@bp.route('/login/', methods=['GET', 'POST'])
def login_page():
    """登录页面（Web 场景）"""
    if request.method == 'GET':
        return render_template('auth/login.html')

    # POST 处理（兼容表单提交）
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    if not username or not password:
        return render_template('auth/login.html', error='用户名和密码不能为空')

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1",
            (username,),
        )
        user = cursor.fetchone()
    finally:
        conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return render_template(
            'auth/login.html', error='用户名或密码错误', username=username
        )

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['employee_id'] = user['employee_id']
    session.modified = True

    next_url = request.args.get('next') or url_for('dashboard.index')
    return redirect(next_url)


@bp.route('/login', methods=['POST'])
def api_login():
    """API 登录接口"""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return _json_response(
            False,
            error='VALIDATION_ERROR',
            message='用户名和密码不能为空',
            status=400,
        )

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1",
            (username,),
        )
        user = cursor.fetchone()
    finally:
        conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return _json_response(
            False,
            error='INVALID_CREDENTIALS',
            message='用户名或密码错误',
            status=401,
        )

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['employee_id'] = user['employee_id']
    session.modified = True

    return _json_response(
        True,
        data={
            'user_id': user['id'],
            'username': user['username'],
            'role': user['role'],
            'employee_id': user['employee_id'],
        },
        message='登录成功',
        status=200,
    )


@bp.route('/logout', methods=['POST'])
def logout():
    """登出接口"""
    session.clear()
    if _is_api_request():
        return _json_response(True, message='登出成功')
    return redirect(url_for('auth.login_page'))


@bp.route('/logout/', methods=['POST'])
def logout_page():
    """Web 表单登出（兼容带斜杠）"""
    session.clear()
    return redirect(url_for('auth.login_page'))


@bp.route('/me', methods=['GET'])
def me():
    """获取当前登录用户信息"""
    user_id = session.get('user_id')
    if not user_id:
        return _json_response(
            False,
            error='UNAUTHORIZED',
            message='请先登录',
            status=401,
        )

    return _json_response(
        True,
        data={
            'user_id': user_id,
            'username': session.get('username'),
            'role': session.get('role'),
            'employee_id': session.get('employee_id'),
        },
        message='',
    )
