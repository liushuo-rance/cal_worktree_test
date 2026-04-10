# 运维手册

> 本文档为运维人员提供系统部署、监控和故障处理指南。

---

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档名称 | 运维手册 |
| 版本 | 1.0 |
| 创建日期 | 2026-04-09 |
| 状态 | 初稿 |

---

## 2. 系统概述

### 2.1 系统架构

加班记录分析系统是一个基于 Flask 的 Web 应用，使用 SQLite 作为数据库。

```
┌─────────────────────────────────────┐
│           用户浏览器                 │
└─────────────┬───────────────────────┘
              │ HTTP
┌─────────────▼───────────────────────┐
│        Flask Web Server             │
│        (127.0.0.1:5001)            │
├─────────────────────────────────────┤
│  - 加班记录管理                      │
│  - AI 智能解析                       │
│  - 工资计算                          │
│  - 调休管理                          │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│      SQLite Database                │
│      (data/overtime.db)            │
└─────────────────────────────────────┘
```

### 2.2 关键进程

| 进程 | 命令 | 说明 |
|------|------|------|
| Web 服务 | `python run_web.py` | Flask 开发服务器 |
| 日志文件 | `logs/app.log` | 应用日志 |
| 数据库 | `data/overtime.db` | SQLite 数据库 |

---

## 3. 部署流程

### 3.1 首次部署

```bash
# 1. 下载代码
cd /opt
git clone <repository-url> ot-calculation
cd ot-calculation

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install flask flask-session pytest pytest-cov
pip install pytest-playwright playwright
playwright install chromium

# 4. 设置环境变量
export SECRET_KEY="$(openssl rand -base64 32)"
export FLASK_ENV="production"
export DATABASE="/var/lib/ot-calculation/data.db"

# 5. 创建数据目录
mkdir -p /var/lib/ot-calculation
mkdir -p /var/log/ot-calculation
mkdir -p /var/lib/ot-calculation/.flask_session

# 6. 启动应用
python run_web.py
```

### 3.2 使用 systemd 服务

创建 `/etc/systemd/system/ot-calculation.service`:

```ini
[Unit]
Description=Overtime Calculation System
After=network.target

[Service]
Type=simple
User=ot-calc
WorkingDirectory=/opt/ot-calculation
Environment=SECRET_KEY=your-secret-key
Environment=FLASK_ENV=production
Environment=DATABASE=/var/lib/ot-calculation/data.db
ExecStart=/opt/ot-calculation/venv/bin/python run_web.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable ot-calculation
sudo systemctl start ot-calculation
```

### 3.3 使用 Docker（可选）

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 复制代码
COPY . .

# 安装依赖
RUN pip install flask flask-session

# 创建目录
RUN mkdir -p /app/data /app/logs /app/.flask_session

# 暴露端口
EXPOSE 5001

# 启动命令
CMD ["python", "run_web.py"]
```

构建和运行：

```bash
docker build -t ot-calculation .
docker run -d -p 5001:5001 \
  -v /var/lib/ot-calculation:/app/data \
  -e SECRET_KEY=your-secret \
  ot-calculation
```

---

## 4. 健康检查

### 4.1 服务状态检查

```bash
# 检查进程
ps aux | grep "run_web.py"

# 检查端口
netstat -tlnp | grep 5001
lsof -i :5001

# HTTP 健康检查
curl -f http://127.0.0.1:5001/ || echo "Service Down"
```

### 4.2 日志检查

```bash
# 查看最近的错误
tail -f logs/app.log | grep ERROR

# 查看特定日期的日志
grep "2026-04-08" logs/app.log

# 统计错误数量
grep -c ERROR logs/app.log
```

### 4.3 数据库检查

```bash
# 检查数据库文件大小
ls -lh data/overtime.db

# 检查数据库完整性
sqlite3 data/overtime.db "PRAGMA integrity_check;"

# 查看表统计
sqlite3 data/overtime.db ".tables"
sqlite3 data/overtime.db "SELECT COUNT(*) FROM employees;"
```

---

## 5. 备份与恢复

### 5.1 数据库备份

```bash
#!/bin/bash
# backup.sh - 数据库备份脚本

BACKUP_DIR="/backup/ot-calculation"
DATE=$(date +%Y%m%d_%H%M%S)
DB_FILE="data/overtime.db"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 备份数据库
cp "$DB_FILE" "$BACKUP_DIR/overtime_${DATE}.db"

# 压缩备份
gzip "$BACKUP_DIR/overtime_${DATE}.db"

# 保留最近 30 天的备份
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/overtime_${DATE}.db.gz"
```

### 5.2 自动备份（cron）

```bash
# 编辑 crontab
crontab -e

# 添加每日凌晨 2 点备份
0 2 * * * /opt/ot-calculation/scripts/backup.sh >> /var/log/ot-calculation-backup.log 2>&1
```

### 5.3 数据恢复

```bash
# 1. 停止服务
sudo systemctl stop ot-calculation

# 2. 备份当前数据（以防万一）
cp data/overtime.db data/overtime.db.bak.$(date +%Y%m%d)

# 3. 恢复备份
gunzip /backup/ot-calculation/overtime_20260408_020000.db.gz
cp /backup/ot-calculation/overtime_20260408_020000.db data/overtime.db

# 4. 验证数据库
sqlite3 data/overtime.db "PRAGMA integrity_check;"

# 5. 启动服务
sudo systemctl start ot-calculation
```

---

## 6. 监控告警

### 6.1 基础监控

```bash
# 检查服务是否运行
#!/bin/bash
# health_check.sh

if ! curl -sf http://127.0.0.1:5001/ > /dev/null; then
    echo "$(date): Service is down!" >> /var/log/health_check.log
    # 发送告警（邮件/短信/钉钉）
    # send_alert.sh
fi
```

### 6.2 日志监控

```bash
# 监控错误日志增长
#!/bin/bash
# monitor_errors.sh

ERROR_COUNT=$(grep -c "ERROR" logs/app.log)
if [ "$ERROR_COUNT" -gt 100 ]; then
    echo "High error count: $ERROR_COUNT" | mail -s "Alert" admin@example.com
fi
```

### 6.3 磁盘空间监控

```bash
# 检查磁盘空间
DISK_USAGE=$(df -h /opt/ot-calculation | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "Disk usage is ${DISK_USAGE}%" | mail -s "Disk Alert" admin@example.com
fi
```

---

## 7. 故障处理

### 7.1 服务无法启动

**症状**: 执行 `python run_web.py` 后报错

**排查步骤**:

```bash
# 1. 检查 Python 版本
python3 --version  # 应为 3.9+

# 2. 检查依赖
pip list | grep flask

# 3. 检查端口占用
lsof -i :5001

# 4. 检查日志
tail -n 50 logs/app.log

# 5. 检查权限
ls -la data/
ls -la logs/
```

**常见解决**:

```bash
# 端口被占用
pkill -f "python run_web.py"
python run_web.py

# 权限不足
chmod 755 data logs .flask_session
```

### 7.2 数据库损坏

**症状**: `sqlite3.DatabaseError: database disk image is malformed`

**解决**:

```bash
# 1. 备份损坏的数据库
cp data/overtime.db data/overtime.db.corrupt.$(date +%Y%m%d)

# 2. 尝试修复
sqlite3 data/overtime.db ".dump" | sqlite3 data/overtime_fixed.db

# 3. 验证修复后的数据库
sqlite3 data/overtime_fixed.db "PRAGMA integrity_check;"

# 4. 替换原数据库
mv data/overtime_fixed.db data/overtime.db

# 5. 重启服务
```

### 7.3 内存不足

**症状**: 系统变慢，OOM 错误

**解决**:

```bash
# 1. 查看内存使用
free -h
ps aux --sort=-%mem | head

# 2. 重启服务释放内存
sudo systemctl restart ot-calculation

# 3. 限制内存使用（systemd）
# 在 service 文件中添加
# MemoryLimit=512M
```

### 7.4 AI 解析超时

**症状**: 导入记录时超时

**排查**:

```bash
# 1. 检查网络连接
ping ark.cn-beijing.volces.com

# 2. 检查日志
grep "AI Parser" logs/app.log

# 3. 测试少量数据
# 修改 BATCH_SIZE 为 1，MAX_LINES 为 1
```

---

## 8. 性能优化

### 8.1 数据库优化

```sql
-- 添加索引优化查询
CREATE INDEX IF NOT EXISTS idx_overtime_employee_date 
ON overtime_records(employee_id, work_date);

CREATE INDEX IF NOT EXISTS idx_leave_employee_date 
ON leave_records(employee_id, date);

-- 分析表
ANALYZE;

-- 清理未使用的空间
VACUUM;
```

### 8.2 日志轮转

```bash
# 配置 logrotate
# /etc/logrotate.d/ot-calculation

/opt/ot-calculation/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 ot-calc ot-calc
    sharedscripts
    postrotate
        systemctl reload ot-calculation
    endscript
}
```

### 8.3 Session 清理

```bash
# 定期清理过期 session 文件
#!/bin/bash
# clean_session.sh

find /var/lib/ot-calculation/.flask_session -type f -mtime +7 -delete
echo "$(date): Cleaned old sessions" >> /var/log/session_cleanup.log
```

---

## 9. 升级维护

### 9.1 代码更新

```bash
# 1. 备份当前版本
cd /opt/ot-calculation
cp -r . /backup/ot-calculation-$(date +%Y%m%d)

# 2. 拉取最新代码
git pull origin main

# 3. 安装新依赖
source venv/bin/activate
pip install -r requirements.txt  # 如果有

# 4. 数据库迁移（如果有）
# 执行迁移脚本

# 5. 重启服务
sudo systemctl restart ot-calculation

# 6. 验证
sleep 5
curl http://127.0.0.1:5001/
```

### 9.2 回滚流程

```bash
# 1. 停止服务
sudo systemctl stop ot-calculation

# 2. 恢复代码
cd /opt/ot-calculation
git reset --hard <previous-commit>

# 或从备份恢复
cp -r /backup/ot-calculation-20260408/. .

# 3. 恢复数据库（如果需要）
cp /backup/ot-calculation/overtime_20260408.db data/overtime.db

# 4. 启动服务
sudo systemctl start ot-calculation
```

---

## 10. 安全检查

### 10.1 文件权限检查

```bash
# 检查敏感文件权限
ls -la data/overtime.db  # 应为 600
ls -la instance/config.py  # 应为 600

# 修复权限
chmod 600 data/overtime.db
chmod 600 instance/config.py
chmod 700 data/
```

### 10.2 密钥轮换

```bash
# 生成新密钥
NEW_KEY=$(openssl rand -base64 32)

# 更新环境变量
export SECRET_KEY="$NEW_KEY"

# 重启服务
sudo systemctl restart ot-calculation
```

---

## 11. 联系信息

| 角色 | 联系方式 | 职责 |
|------|----------|------|
| 系统管理员 | admin@example.com | 服务器维护 |
| 数据库管理员 | dba@example.com | 数据备份恢复 |
| 开发团队 | dev@example.com | 代码问题 |

---

## 12. 相关文档

- [08-deployment.md](./08-deployment.md) - 部署文档
- [24-env-config.md](./24-env-config.md) - 环境配置
- [11-operation-sop.md](./11-operation-sop.md) - 操作 SOP
