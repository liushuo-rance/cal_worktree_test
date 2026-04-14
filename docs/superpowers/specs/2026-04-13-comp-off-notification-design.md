# 调休到期提醒邮件通知系统设计文档

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档名称 | 调休到期提醒邮件通知系统设计文档 |
| 版本 | 1.0 |
| 创建日期 | 2026-04-13 |
| 状态 | 已评审通过 |

---

## 2. 项目概述

### 2.1 背景
加班记录分析系统目前支持 Web 端查看调休余额和到期提醒，但缺乏自动化的通知能力。HR 部门需要每天手动登录系统查询即将过期的调休余额，容易遗漏。根据 SOP-005「调休余额管理与到期提醒」以及项目完成报告的中期建议，系统需要建立邮件通知机制。

### 2.2 设计目标
1. 在调休余额即将过期（默认 30 天内）时，自动发送邮件提醒给 HR/管理员。
2. 支持 Web 端手动触发，以及 CLI 命令手动触发。
3. 保留发送历史记录，便于审计和排查。
4. 通知系统与现有业务逻辑解耦，不修改核心调休抵扣数据。

---

## 3. 通知范围与规则

### 3.1 触发条件
- 扫描对象：`comp_off_balances` 表中 `status = 'active'` 且 `remaining_minutes > 0` 的记录。
- 到期阈值：距离 `expiry_date` ≤ 30 天（可配置）。
- 扫描逻辑：直接复用 `comp_off_service.get_expiring_balances()`。

### 3.2 收件人
- 第一阶段：仅发送给 HR/管理员邮箱。
- 不支持直接发给员工本人（后续扩展可选）。
- 配置方式：环境变量 `HR_NOTIFICATION_EMAIL`，支持逗号分隔多个邮箱。

### 3.3 发送时机
| 触发方式 | 说明 |
|---|---|
| 自动定时 | 每天上午 9:00 自动扫描并发送（APScheduler） |
| Web 手动 | 通知中心页面提供「立即发送」按钮 |
| CLI 手动 | `python -m src.cli.commands notify comp-off-expiry` |

---

## 4. 技术架构

### 4.1 新增/修改的文件

```
src/
├── services/
│   ├── notification_service.py    # 扫描、渲染、调度入口
│   └── email_service.py           # SMTP 封装
├── web/routes/
│   └── notifications.py           # Web 路由：通知中心 + 手动发送
├── cli/
│   └── commands.py                # 新增 notify 子命令
├── web/templates/
│   └── email/
│       └── comp_off_expiry.html   # 邮件 HTML 模板
├── db/schema.py                   # 新增 notification_history 表
└── web/__init__.py                # 集成 APScheduler
```

### 4.2 技术选型
- **调度器**：APScheduler（BackgroundScheduler），轻量、与 Flask 集成简单。
- **邮件发送**：Python 标准库 `smtplib` + `email.mime`，无需额外重依赖。
- **模板渲染**：Jinja2（Flask 自带），邮件模板也走 Jinja2。
- **第一阶段不做**：短信、微信、Push。

---

## 5. 数据库设计

### 5.1 notification_history 表

```sql
CREATE TABLE IF NOT EXISTS notification_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_type TEXT NOT NULL,        -- 'comp_off_expiry'
    trigger_mode TEXT NOT NULL,             -- 'scheduled' | 'manual'
    recipient_email TEXT NOT NULL,
    employee_id TEXT,                       -- 汇总通知可为 NULL
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,                   -- 'success' | 'failed'
    error_message TEXT,
    content_summary TEXT,                   -- 摘要，如"3人共5条余额即将到期"
    days_threshold INTEGER                  -- 本次扫描阈值天数
);
```

设计原则：
- 纯日志/审计表，不耦合业务表。
- 预留 `employee_id` 字段，未来若按员工单独发送可复用。
- `content_summary` 让非技术人员快速了解发送内容。

---

## 6. 邮件内容与模板规范

### 6.1 邮件主题
```
调休余额到期提醒 - 2026-04-13
```

### 6.2 邮件正文结构
1. **汇总卡片**
   - 共计 N 位员工、M 条余额记录将在 X 天内过期。
2. **明细表格**
   | 员工姓名 | 获得日期 | 剩余时长 | 到期日期 | 剩余天数 |
3. **底部提示**
   - 本邮件由加班记录分析系统自动生成。
   - 如需查看最新详情，请登录系统查看「调休余额」报表。

### 6.3 样式规范
- 表头背景色：`#000666`（系统主色），白色字体。
- 数据行细边框，文本左对齐，时长右对齐。
- 整体简洁，兼容主流邮件客户端（避免复杂 CSS3 特性）。

---

## 7. Web 端交互

### 7.1 路由设计

```python
@bp.route('/')
def notification_center(): ...

@bp.route('/send/comp-off-expiry', methods=['POST'])
def send_comp_off_expiry(): ...
```

### 7.2 通知中心页面内容
- SMTP 配置状态指示（已配置 / 未配置邮箱）。
- 上次发送时间、发送结果、内容摘要。
- 最近 10 条发送历史列表。
- 「立即发送调休到期提醒」按钮。

### 7.3 快捷入口
在「调休余额」报表页面（`/reports/comp-off/<employee_id>/`）右上角增加快捷按钮，链接到通知中心。

### 7.4 错误处理
| 场景 | 处理 |
|---|---|
| 未配置 HR 邮箱 | Flash 提示「未配置收件人，请联系管理员」 |
| 无到期余额 | 发送「今日无即将到期余额」确认邮件（可配置开关） |
| SMTP 发送失败 | Flash 提示「发送失败」，记录 error_message 到历史表 |

---

## 8. CLI 命令实现

```bash
python -m src.cli.commands notify comp-off-expiry \
    [--threshold 30] \
    [--dry-run]
```

参数说明：
- `--threshold`：到期天数阈值，默认 30。
- `--dry-run`：仅打印扫描结果和收件人，不实际发送邮件。

---

## 9. 自动调度实现

### 9.1 调度器集成
- 在 Flask `create_app()` 中使用 `APScheduler.BackgroundScheduler` 启动定时任务。
- 任务 ID：`comp_off_expiry_daily`。
- Cron 表达式：`0 9 * * *`（每天上午 9:00）。

### 9.2 配置项
| 环境变量 | 说明 | 默认值 |
|---|---|---|
| `SMTP_HOST` | SMTP 服务器地址 | - |
| `SMTP_PORT` | SMTP 端口 | 587 |
| `SMTP_USER` | SMTP 用户名 | - |
| `SMTP_PASSWORD` | SMTP 密码 | - |
| `SMTP_FROM` | 发件人邮箱 | 同 SMTP_USER |
| `HR_NOTIFICATION_EMAIL` | HR 收件人，支持逗号分隔 | - |
| `SCHEDULER_ENABLED` | 是否启用自动调度 | true |

### 9.3 多实例兼容性
当前版本暂不处理多实例下的重复调度（后续可通过数据库分布式锁或独立 worker 解决）。

---

## 10. 边界情况与兼容性

| 场景 | 处理 |
|---|---|
| 未配置 SMTP | 手动触发时提示配置缺失；自动调度时记录 warning 日志并跳过 |
| 系统无到期余额 | 默认仍发送一封「今日无即将到期余额」确认邮件给 HR，避免「系统是不是坏了」的疑虑；可通过配置关闭 |
| openpyxl / APScheduler 未安装 | `requirements.txt` 已包含；启动时可选检查并提示 |
| 数据库连接失败 | Web 500 / CLI exit code 4，附带 traceback |
| 邮件发送部分失败（多收件人） | 每个邮箱独立尝试，成功和失败分别记录历史 |

---

## 11. 验收标准

- [ ] Web 端「通知中心」页面可访问，显示配置状态和发送历史
- [ ] Web 端「立即发送」按钮点击后成功发送邮件，并出现 Flash 提示
- [ ] CLI `notify comp-off-expiry` 命令可执行，支持 `--dry-run`
- [ ] 每天上午 9:00 自动触发扫描并发送邮件
- [ ] 邮件内容包含汇总信息和明细表格，样式符合规范
- [ ] 每次发送均记录到 `notification_history` 表
- [ ] 无到期余额时邮件不报错，内容显示「暂无即将到期余额」
- [ ] 相关功能通过测试覆盖

---

## 12. 相关文档

- [11-operation-sop.md](../../11-operation-sop.md) — SOP-005 调休余额管理与到期提醒
- [14-project-completion-report.md](../../14-project-completion-report.md) — 中期建议：邮件通知系统（调休到期提醒）
