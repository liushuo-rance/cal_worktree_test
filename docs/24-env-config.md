# 环境变量与配置文档

> 本文档描述系统的环境变量和配置选项。

---

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档名称 | 环境变量与配置文档 |
| 版本 | 1.0 |
| 创建日期 | 2026-04-09 |
| 状态 | 初稿 |

---

## 2. 环境变量

### 2.1 核心环境变量

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `SECRET_KEY` | 否 | `'dev'` | Flask 应用密钥，用于 session 加密。生产环境必须设置 |
| `DATABASE` | 否 | `./data/overtime.db` | SQLite 数据库文件路径 |
| `SESSION_TYPE` | 否 | `'filesystem'` | Session 存储类型 |
| `SESSION_FILE_DIR` | 否 | `./.flask_session` | Session 文件存储目录 |
| `FLASK_ENV` | 否 | `'development'` | Flask 运行环境 (`development` 或 `production`) |
| `FLASK_DEBUG` | 否 | `True` | 是否启用调试模式 |

### 2.2 AI 解析服务配置（硬编码）

> ⚠️ **注意**: 以下配置在 `src/services/ai_parser_service.py` 中硬编码，如需修改请直接编辑代码。

| 配置项 | 当前值 | 说明 |
|--------|--------|------|
| API 提供商 | 火山引擎 (Volces) | 字节跳动旗下云服务 |
| Base URL | `https://ark.cn-beijing.volces.com/api/v3` | API 端点 |
| Model | `ep-20260331092634-wfnm8` | 模型端点 ID |
| API Key | (硬编码) | 认证密钥 |

---

## 3. Flask 应用配置

### 3.1 默认配置项

```python
# src/web/__init__.py 中的默认配置

app.config.from_mapping(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
    DATABASE=default_db_path,  # ./data/overtime.db
    SESSION_TYPE='filesystem',
    SESSION_FILE_DIR='./.flask_session',
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
)
```

### 3.2 配置文件加载

Flask 会按以下顺序加载配置：

1. **默认配置** (`app.config.from_mapping`)
2. **实例配置文件** (`instance/config.py`) - 如果存在
3. **测试配置** - 运行测试时传入

### 3.3 自定义配置文件示例

创建 `instance/config.py`：

```python
# instance/config.py

SECRET_KEY = 'your-production-secret-key-here'
DATABASE = '/var/lib/ot-calculation/data.db'

# 日志级别
LOG_LEVEL = 'INFO'

# 其他自定义配置
```

---

## 4. 数据库配置

### 4.1 SQLite 数据库路径

| 环境 | 默认路径 |
|------|----------|
| 开发 | `./data/overtime.db` |
| 测试 | `./instance/test.db` |
| 生产 | 通过 `DATABASE` 环境变量指定 |

### 4.2 数据库初始化

```bash
# 数据库会在应用启动时自动初始化
python run_web.py

# 或手动初始化（通过 CLI）
python -m cli.commands init-db
```

---

## 5. 日志配置

### 5.1 日志文件位置

| 环境 | 日志路径 |
|------|----------|
| 所有环境 | `./logs/app.log` |

### 5.2 日志配置参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 日志级别 | DEBUG | 文件日志记录所有级别 |
| 控制台级别 | INFO | 控制台只记录 INFO 及以上 |
| 最大文件大小 | 10 MB | 单日志文件上限 |
| 备份数量 | 5 | 保留 5 个历史日志文件 |
| 编码 | UTF-8 | 支持中文日志 |

### 5.3 日志格式

**文件日志格式：**
```
2026-04-08 10:30:15,123 - module_name - INFO - 日志消息
```

**控制台日志格式：**
```
INFO: 日志消息
```

---

## 6. Session 配置

### 6.1 服务器端 Session

系统使用 Flask-Session 实现服务器端 session 存储：

| 参数 | 值 | 说明 |
|------|-----|------|
| SESSION_TYPE | filesystem | 文件系统存储 |
| SESSION_FILE_DIR | ./.flask_session | session 文件目录 |
| SESSION_PERMANENT | False | 非持久化 session |
| SESSION_USE_SIGNER | True | 启用签名验证 |

### 6.2 Session 用途

- 存储导入预览数据
- 记录解析进度
- 保存用户操作状态

---

## 7. 开发环境设置

### 7.1 最小开发配置

```bash
# 1. 设置环境变量
export SECRET_KEY="dev-secret-key"
export FLASK_ENV="development"
export FLASK_DEBUG="1"

# 2. 启动应用
python run_web.py
```

### 7.2 生产环境配置

```bash
# 生产环境必须设置的变量
export SECRET_KEY="$(openssl rand -base64 32)"
export FLASK_ENV="production"
export FLASK_DEBUG="0"
export DATABASE="/var/lib/ot-calculation/production.db"
```

---

## 8. 配置验证

### 8.1 检查配置加载

```python
# 在 Flask shell 中检查
from web import create_app
app = create_app()

# 查看所有配置
for key in app.config:
    print(f"{key}: {app.config[key]}")
```

### 8.2 配置优先级测试

```bash
# 测试环境变量覆盖
SECRET_KEY="test-key" python -c "
from web import create_app
app = create_app()
print(f'SECRET_KEY: {app.config[\"SECRET_KEY\"]}')
"
```

---

## 9. 故障排除

### 9.1 配置未生效

**症状**: 修改环境变量后配置未改变

**解决**:
1. 检查环境变量是否正确导出：`echo $SECRET_KEY`
2. 重启 Flask 应用
3. 检查是否有 `instance/config.py` 覆盖

### 9.2 Session 目录权限

**症状**: `Permission denied` 错误

**解决**:
```bash
# 创建 session 目录并设置权限
mkdir -p .flask_session
chmod 755 .flask_session
```

### 9.3 数据库路径错误

**症状**: `unable to open database file`

**解决**:
```bash
# 确保数据目录存在
mkdir -p data
chmod 755 data
```

---

## 10. 相关文档

- [08-deployment.md](./08-deployment.md) - 部署与运维
- [26-contributing.md](./26-contributing.md) - 开发环境搭建
