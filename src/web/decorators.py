"""
权限装饰器
提供登录校验、管理员校验、自己或管理员校验
"""

from functools import wraps

from flask import session, redirect, url_for, request, abort, jsonify


def _is_api_request() -> bool:
    """判断当前请求是否为 API/JSON 请求"""
    if request.is_json:
        return True
    if request.path.startswith('/api/'):
        return True
    accept = request.headers.get('Accept', '')
    if 'application/json' in accept:
        return True
    return False


def _unauthorized_response():
    """返回未登录的统一响应"""
    if _is_api_request():
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "error": "UNAUTHORIZED",
                    "message": "请先登录",
                }
            ),
            401,
        )
    return redirect(url_for('auth.login_page', next=request.url))


def _forbidden_response():
    """返回无权限的统一响应"""
    if _is_api_request():
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "error": "FORBIDDEN",
                    "message": "您没有权限访问该资源",
                }
            ),
            403,
        )
    abort(403)


def login_required(f):
    """检查用户是否已登录"""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return _unauthorized_response()
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    """检查用户是否为管理员"""

    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            return _forbidden_response()
        return f(*args, **kwargs)

    return decorated


def self_or_admin(f):
    """用于需要绑定 employee_id 的路由，普通用户只能访问自己的数据"""

    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if session.get('role') == 'admin':
            return f(*args, **kwargs)
        target_employee_id = kwargs.get('employee_id')
        if target_employee_id and target_employee_id != session.get('employee_id'):
            return _forbidden_response()
        return f(*args, **kwargs)

    return decorated
