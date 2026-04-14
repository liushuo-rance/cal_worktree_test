# CLI 模块参考文档

> 本文档描述 `src/cli/commands.py` 作为独立可执行 CLI 的使用方式。支持 `python3 src/cli/commands.py <command> [options]` 以及 `python3 -m src.cli <command> [options]`。

---

## 快速开始

### 获取帮助

```bash
python3 src/cli/commands.py --help
python3 src/cli/commands.py import --help
python3 -m src.cli --help
```

### 常用示例

```bash
# 导入文件
python3 src/cli/commands.py import --file ./records/xuchen.md --employee E001

# 通过标准输入导入（EOF / pipe）
cat ./records/xuchen.md | python3 src/cli/commands.py import --file - --employee E001
python3 src/cli/commands.py import --file - --employee E001 << 'EOF'
2025.10.22，晚上3.5小时
2025.10.23，请假半天
EOF

# 查询记录
python3 src/cli/commands.py query --employee E001 --start-date 2025-01-01 --end-date 2025-01-31

# 生成报表
python3 src/cli/commands.py report --employee E001 --type monthly --year 2025 --month 1

# 导出数据
python3 src/cli/commands.py export --employee E001 --format json --output ./export/e001.json

# 工资计算
python3 src/cli/commands.py salary --employee E001 --year 2025 --month 1

# 节假日管理
python3 src/cli/commands.py holidays --year 2025
python3 src/cli/commands.py check-holiday --month 2025-01

# 通过 stdin 导入节假日通知
python3 src/cli/commands.py holiday-import --year 2025 << 'EOF'
国务院办公厅关于2025年部分节假日安排的通知
一、元旦：1月1日（周三）放假1天，不调休。
EOF

# 调休管理
python3 src/cli/commands.py comp-off --employee E001
python3 src/cli/commands.py mark-expired-comp-off

# 员工管理
python3 src/cli/commands.py employee list
python3 src/cli/commands.py employee create --id E001 --name "张三" --department "技术部"
python3 src/cli/commands.py employee get E001
python3 src/cli/commands.py delete_employee E001

# 审批队列
python3 src/cli/commands.py review list
python3 src/cli/commands.py review approve --id 1
python3 src/cli/commands.py review reject --id 1 --reason "信息不完整"

# 删除加班记录
python3 src/cli/commands.py overtime-delete --id 123

# Dashboard 统计
python3 src/cli/commands.py stats
```

### 全局选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--db` | SQLite 数据库路径 | `data/overtime.db` |
| `--format` | 输出格式：`json` / `table` | `json` |

---

## 命令行参考

### `import`

导入 Markdown 文件或标准输入内容。

```bash
python3 src/cli/commands.py import --file PATH --employee EMPLOYEE_ID
```

| 参数 | 说明 |
|------|------|
| `--file PATH` | 文件路径，使用 `-` 表示从 stdin 读取 |
| `--employee EMPLOYEE_ID` | 员工 ID |

---

### `query`

查询加班记录。

```bash
python3 src/cli/commands.py query [--employee ID] [--start-date DATE] [--end-date DATE]
```

---

### `report`

生成报表。

```bash
python3 src/cli/commands.py report --employee ID --type {monthly,comp_off,salary} [--year Y] [--month M]
```

---

### `export`

导出员工加班记录。

```bash
python3 src/cli/commands.py export --employee ID --format {json,csv} [--output PATH]
```

---

### `salary`

计算加班工资。

```bash
python3 src/cli/commands.py salary --employee ID --year Y --month M
```

---

### `holidays`

列出指定年份的节假日。

```bash
python3 src/cli/commands.py holidays --year Y
```

---

### `check-holiday`

检查指定月份的节假日配置。

```bash
python3 src/cli/commands.py check-holiday --month YYYY-MM
```

---

### `comp-off`

查询员工调休余额。

```bash
python3 src/cli/commands.py comp-off --employee ID
```

---

### `mark-expired-comp-off`

标记已过期的调休余额。

```bash
python3 src/cli/commands.py mark-expired-comp-off
```

---

### `employee list`

列出所有员工。

```bash
python3 src/cli/commands.py employee list
```

---

### `employee create`

创建新员工。

```bash
python3 src/cli/commands.py employee create --id ID --name NAME [--department DEPT]
```

---

### `employee get`

查看员工详情及最近记录。

```bash
python3 src/cli/commands.py employee get ID
```

---

### `review list`

列出待审批的队列项。

```bash
python3 src/cli/commands.py review list
```

---

### `review approve`

批准审批项。

```bash
python3 src/cli/commands.py review approve --id ID [--note NOTE]
```

---

### `review reject`

拒绝审批项。

```bash
python3 src/cli/commands.py review reject --id ID [--reason REASON]
```

---

### `holiday-import`

从标准输入导入节假日通知文本。

```bash
python3 src/cli/commands.py holiday-import [--year Y] < notification.txt
cat notification.txt | python3 src/cli/commands.py holiday-import
```

---

### `holiday-delete`

删除指定日期的节假日记录。

```bash
python3 src/cli/commands.py holiday-delete --date YYYY-MM-DD
```

---

### `holiday-delete-year`

删除指定年份的所有节假日记录。

```bash
python3 src/cli/commands.py holiday-delete-year --year Y
```

---

### `overtime-delete`

删除指定的加班记录。

```bash
python3 src/cli/commands.py overtime-delete --id RECORD_ID
```

---

### `stats`

显示系统统计信息（Dashboard 数据）。

```bash
python3 src/cli/commands.py stats
```

---

## 故障排除

### 提示 `ModuleNotFoundError: No module named 'src'`

确保在项目根目录执行命令，或设置 `PYTHONPATH`：

```bash
export PYTHONPATH="$(pwd):$PYTHONPATH"
python3 src/cli/commands.py --help
```

### `sqlite3.OperationalError: unable to open database file`

检查 `data` 目录是否存在：

```bash
mkdir -p data
```

### AI 解析返回全部失败

检查输出 JSON 中的 `parse_error` 字段。常见原因：
- 网络不可达（火山方舟 API 无法访问）
- 文件内容为空或全部是跳过行（标题、汇总）
