# 用户认证与权限控制 API 对接文档

> 版本：v1.0  
> 适用分支：`user_dev`  
> 目标：为加班记录分析系统引入用户登录、权限隔离与角色控制机制

---

## 1. 概述

### 1.1 认证方式
- **Session-Based 认证**：复用现有 `Flask-Session` 配置，基于服务器端文件系统 Session 存储用户登录状态。
- **密码存储**：使用 `werkzeug.security` 的 `generate_password_hash` / `check_password_hash`，默认采用 `pbkdf2:sha256` 算法。
- **登录态维护**：用户成功登录后，将 `user_id`、`username`、`role`、`employee_id` 写入 session；请求时通过 `session.get('user_id')` 判断是否已登录。

### 1.2 角色定义

| 角色 | 标识值 | 说明 |
|------|--------|------|
| 管理员 | `admin` | 可查看所有页面、所有员工数据、系统设置 |
| 普通用户 | `user` | 仅可查看与自己关联的员工加班数据，无法访问管理功能 |

### 1.3 未登录拦截策略
- 在 `app.before_request` 或 `@bp.before_request` 中统一校验 `session.get('user_id')`。
- 若未登录，非 API 请求重定向到 `/auth/login/`；API 请求返回 `401 Unauthorized` JSON。
- 静态资源（`static/`）、登录页（`/auth/login/`）本身允许匿名访问。

---

## 2. 数据模型

### 2.1 `users` 表（新增）

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,          -- 登录账号（建议用工号或邮箱）
    password_hash TEXT NOT NULL,            -- 密码哈希
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin', 'user')),
    employee_id TEXT,                       -- 关联的员工编号（普通用户必填，管理员可选）
    is_active INTEGER DEFAULT 1,            -- 是否启用（0=禁用）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE SET NULL
);
```

### 2.2 与 `employees` 的关系

- **管理员（`admin`）**：`employee_id` 可为 `NULL`，表示不绑定特定员工，拥有全局视图。
- **普通用户（`user`）**：`employee_id` 必须非空，且对应 `employees.employee_id`。登录后所有数据查询需自动附加 `WHERE employee_id = ?` 过滤条件。
- 一个员工可以被多个用户绑定（例如主管和员工本人共用同一员工数据），但通常建议 1:1。

### 2.3 初始管理员账号（建议）

在 `users` 表创建后，建议通过初始化脚本或 CLI 插入默认管理员：

```sql
INSERT INTO users (username, password_hash, role, employee_id, is_active)
VALUES ('admin', '<hash>', 'admin', NULL, 1);
```

> 注：`password_hash` 需使用 `generate_password_hash('your_password')` 生成。

---

## 3. API 端点定义

### 3.1 通用请求/响应格式

**Content-Type**：`application/json`（API 端点）或 `application/x-www-form-urlencoded`（Web 表单兼容）

**通用响应结构**：

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "message": "操作成功"
}
```

**错误响应结构**：

```json
{
  "success": false,
  "data": null,
  "error": "INVALID_CREDENTIALS",
  "message": "用户名或密码错误"
}
```

### 3.2 错误码一览

| 错误码 | HTTP 状态 | 说明 |
|--------|-----------|------|
| `INVALID_CREDENTIALS` | 401 | 用户名或密码错误 |
| `ACCOUNT_DISABLED` | 403 | 账号已被禁用 |
| `UNAUTHORIZED` | 401 | 未登录或 Session 已过期 |
| `FORBIDDEN` | 403 | 已登录但无权限访问该资源 |
| `VALIDATION_ERROR` | 400 | 请求参数校验失败 |
| `NOT_FOUND` | 404 | 用户或关联员工不存在 |
| `SERVER_ERROR` | 500 | 服务器内部错误 |

---

### 3.3 POST /auth/login

**描述**：用户登录

**请求参数**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | 是 | 用户名/工号 |
| `password` | string | 是 | 明文密码 |

**请求示例**：

```json
POST /auth/login
Content-Type: application/json

{
  "username": "E078",
  "password": "123456"
}
```

**成功响应 (200)**：

```json
{
  "success": true,
  "data": {
    "user_id": 3,
    "username": "E078",
    "role": "user",
    "employee_id": "E078"
  },
  "error": null,
  "message": "登录成功"
}
```

**失败响应示例 (401)**：

```json
{
  "success": false,
  "data": null,
  "error": "INVALID_CREDENTIALS",
  "message": "用户名或密码错误"
}
```

**后端逻辑要点**：
1. 查询 `users` 表，校验 `username` 是否存在且 `is_active = 1`。
2. 使用 `check_password_hash(password_hash, password)` 校验密码。
3. 校验通过后写入 session：`session['user_id'] = user.id`、`session['username'] = user.username`、`session['role'] = user.role`、`session['employee_id'] = user.employee_id`。
4. Web 场景下可直接重定向到首页 `/`。

---

### 3.4 POST /auth/logout

**描述**：用户登出，清除 Session

**请求参数**：无

**请求示例**：

```json
POST /auth/logout
```

**成功响应 (200)**：

```json
{
  "success": true,
  "data": null,
  "error": null,
  "message": "登出成功"
}
```

**后端逻辑要点**：
1. 调用 `session.clear()` 或逐个删除认证相关键。
2. Web 场景下重定向到 `/auth/login/`。

---

### 3.5 GET /auth/me

**描述**：获取当前登录用户信息

**请求参数**：无（从 Session 读取）

**成功响应 (200)**：

```json
{
  "success": true,
  "data": {
    "user_id": 3,
    "username": "E078",
    "role": "user",
    "employee_id": "E078"
  },
  "error": null,
  "message": ""
}
```

**未登录响应 (401)**：

```json
{
  "success": false,
  "data": null,
  "error": "UNAUTHORIZED",
  "message": "请先登录"
}
```

---

## 4. 页面/路由权限矩阵

> 以下基于现有 `src/web/routes/` 中的路由整理。实现时需在对应 Blueprint 或视图函数上加保护装饰器。

### 4.1 访问权限图例
- **公开**：无需登录
- **登录**：任何已登录用户可访问
- **管理员**：仅 `role = 'admin'` 可访问
- **自己**：普通用户只能访问与自己 `employee_id` 关联的数据

### 4.2 Dashboard

| 路由 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/` | GET | 管理员 | 首页统计（含全员数据） |

> 普通用户建议登录后重定向到自己的报表页 `/reports/monthly/<employee_id>/`。

### 4.3 员工管理 (`/employees`)

| 路由 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/employees/` | GET | 管理员 | 员工列表 |
| `/employees/create/` | POST | 管理员 | 创建员工 |
| `/employees/<id>/delete/` | POST | 管理员 | 软删除员工 |
| `/employees/<id>/delete-permanent/` | POST | 管理员 | 硬删除员工 |
| `/employees/<id>/` | GET | 管理员/自己 | 员工详情；普通用户仅当 `id == session['employee_id']` |
| `/employees/<id>/records/` | GET | 管理员/自己 | 记录管理；同上 |
| `/employees/<id>/records/create/` | GET/POST | 管理员/自己 | 创建记录；同上 |
| `/employees/<id>/records/<type>/<rid>/edit/` | GET/POST | 管理员/自己 | 编辑记录；同上 |
| `/employees/<id>/records/<type>/<rid>/delete/` | POST | 管理员/自己 | 删除记录；同上 |
| `/employees/<id>/records/merge-duplicates/<type>/` | POST | 管理员/自己 | 合并重复；同上 |
| `/employees/<id>/records/deduplicate/<type>/` | POST | 管理员/自己 | 去重；同上 |

### 4.4 记录导入 (`/records`)

| 路由 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/records/import/` | GET/POST | 管理员 | Markdown/文件导入入口 |
| `/records/import/preview/` | POST | 管理员 | 导入预览 |
| `/records/import/stream/` | GET | 管理员 | SSE 导入进度流 |
| `/records/import/confirm/` | POST | 管理员 | 确认导入 |
| `/records/import/cancel/` | POST | 管理员 | 取消导入 |
| `/records/search/` | GET | 管理员 | 全局记录搜索 |
| `/records/sessions/` | GET | 管理员 | 导入会话列表 |
| `/records/sessions/<sid>/` | GET | 管理员 | 导入会话详情 |
| `/records/sessions/<sid>/delete/` | POST | 管理员 | 删除导入会话 |

> 普通用户不开放记录导入和全局搜索，防止越权写入或查看他人数据。

### 4.5 审批队列 (`/review`)

| 路由 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/review/` | GET | 管理员 | 审批队列列表 |
| `/review/<rid>/approve/` | POST | 管理员 | 通过审批 |
| `/review/<rid>/reject/` | POST | 管理员 | 拒绝审批 |
| `/review/comp-off/` | GET | 管理员 | 调休审批列表 |
| `/review/comp-off/<cid>/approve/` | POST | 管理员 | 通过调休申请 |
| `/review/comp-off/<cid>/reject/` | POST | 管理员 | 拒绝调休申请 |

### 4.6 报表中心 (`/reports`)

| 路由 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/reports/` | GET | 登录 | 报表首页（普通用户只能看到自己） |
| `/reports/monthly/<employee_id>/` | GET | 管理员/自己 | 月度报表 |
| `/reports/monthly/<employee_id>/<year>/<month>/` | GET | 管理员/自己 | 月度报表（指定年月） |
| `/reports/monthly/<employee_id>/<year>/<month>/export/` | GET | 管理员/自己 | 月度报表导出 |
| `/reports/comp-off/<employee_id>/` | GET | 管理员/自己 | 调休余额报表 |
| `/reports/comp-off/<employee_id>/export/` | GET | 管理员/自己 | 调休报表导出 |
| `/reports/salary/<employee_id>/<year>/<month>/` | GET | 管理员/自己 | 工资计算表 |
| `/reports/salary/<employee_id>/<year>/<month>/export/` | GET | 管理员/自己 | 工资报表导出 |
| `/reports/ranking/` | GET | 管理员 | 加班排名（含全员数据） |

### 4.7 节假日 (`/holidays`)

| 路由 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/holidays/` | GET | 管理员 | 节假日列表 |
| `/holidays/create/` | POST | 管理员 | 新增节假日 |
| `/holidays/import/` | POST | 管理员 | 批量导入节假日 |
| `/holidays/<hid>/delete/` | POST | 管理员 | 删除节假日 |

### 4.8 系统设置 (`/settings`)

| 路由 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/settings/` | GET | 管理员 | 设置首页 |
| `/settings/save` | POST | 管理员 | 保存设置 |

### 4.9 通知中心 (`/notifications`)

| 路由 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/notifications/` | GET | 管理员 | 通知列表 |
| `/notifications/send` | POST | 管理员 | 手动发送通知 |

### 4.10 AI 助手 (`/assistant`)

| 路由 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/assistant/` | GET | 管理员 | AI 助手页面 |
| `/assistant/chat` | POST | 管理员 | AI 对话接口 |

### 4.11 REST API (`/api/v1`)

| 路由 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/api/v1/records/import/` | POST | 管理员 | JSON 批量导入 |

---

## 5. 数据隔离规则（普通用户）

普通用户 (`role = 'user'`) 的访问控制核心逻辑：

### 5.1 装饰器设计建议

```python
from functools import wraps
from flask import session, redirect, url_for, abort, jsonify

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            # API 请求返回 JSON，页面请求重定向
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({"success": False, "error": "UNAUTHORIZED", "message": "请先登录"}), 401
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            abort(403)
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
            abort(403)
        return f(*args, **kwargs)
    return decorated
```

### 5.2 数据过滤原则

对于普通用户，所有涉及数据库查询的地方必须附加 `employee_id` 过滤：

- **员工详情/报表**：`WHERE employee_id = session['employee_id']`
- **记录查询**：`WHERE employee_id = session['employee_id']`
- **调休余额**：`WHERE employee_id = session['employee_id']`
- **加班排名**：普通用户不可见（全局对比涉及他人数据）
- **导入/审批/设置**：仅管理员可见

### 5.3 URL 硬编码防护

即使普通用户直接在浏览器输入 `/employees/E001/`，也必须在视图函数入口校验：

```python
if session.get('role') != 'admin' and employee_id != session.get('employee_id'):
    abort(403)
```

---

## 6. 前端对接建议

### 6.1 登录页
- URL：`/auth/login/`（新增模板 `templates/auth/login.html`）
- 表单字段：`username`、`password`
- 提交方式：`POST`（表单提交或 AJAX）
- 登录成功后：管理员跳转 `/`，普通用户跳转 `/reports/monthly/<employee_id>/`

### 6.2 导航栏适配
- 未登录：仅显示登录入口
- 管理员：显示完整导航（Dashboard、员工管理、记录导入、审批、报表、节假日、设置、通知）
- 普通用户：仅显示“我的报表”（月度/调休/工资）和“我的记录”，以及“登出”

### 6.3 权限提示
- 前端无需复杂权限树，统一依赖后端 `403` 拦截。
- 普通用户若误点管理员链接，后端返回 403，前端展示“您没有权限访问此页面”。

---

## 7. 实现检查清单

- [ ] 数据库：`src/db/schema.py` 新增 `users` 表及 `init_database` 中的建表逻辑
- [ ] 路由：`src/web/routes/auth.py` 新增 Login / Logout / Me 三个端点
- [ ] 模板：`src/web/templates/auth/login.html` 登录页面
- [ ] 注册蓝图：`src/web/__init__.py` 中 `app.register_blueprint(auth.bp)`
- [ ] 装饰器：`src/web/utils.py` 或 `src/web/decorators.py` 实现 `login_required`、`admin_required`、`self_or_admin`
- [ ] 权限覆盖：为以下路由加保护
  - `dashboard`：仅 admin
  - `employees.list_employees/create/delete*`：仅 admin
  - `employees.employee_detail/records*`：`self_or_admin`
  - `records.*`：仅 admin
  - `review.*`：仅 admin
  - `reports.*`：`self_or_admin`（除 ranking 仅 admin）
  - `holidays.*`：仅 admin
  - `settings.*`：仅 admin
  - `notifications.*`：仅 admin
  - `assistant.*`：仅 admin
  - `api.*`：仅 admin
- [ ] 初始数据：提供默认管理员账号插入脚本

---

## 附录：现有路由汇总（供参考）

基于当前代码已注册 Blueprint 及前缀：

| Blueprint | Prefix |
|-----------|--------|
| `dashboard` | `/` |
| `employees` | `/employees` |
| `records` | `/records` |
| `review` | `/review` |
| `reports` | `/reports` |
| `holidays` | `/holidays` |
| `api` | `/api/v1` |
| `notifications` | `/notifications` |
| `assistant` | `/assistant` |
| `settings` | `/settings` |
