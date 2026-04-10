# CLI 命令参考文档

> 本文档描述命令行接口(CLI)的所有可用命令。

---

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档名称 | CLI 命令参考文档 |
| 版本 | 1.0 |
| 创建日期 | 2026-04-09 |
| 状态 | 初稿 |

---

## 2. CLI 概述

命令行接口提供系统管理和数据操作的命令行工具。

### 2.1 使用方式

```bash
# 方式1: 直接运行模块
python -m src.cli.commands <command> [options]

# 方式2: 通过主程序
python run_web.py cli <command> [options]
```

### 2.2 通用选项

| 选项 | 说明 | 示例 |
|------|------|------|
| `--help` | 显示帮助信息 | `python -m src.cli.commands --help` |
| `--version` | 显示版本 | `python -m src.cli.commands --version` |
| `--verbose` | 详细输出 | `python -m src.cli.commands import --verbose` |

---

## 3. 命令列表

### 3.1 数据导入命令

#### `import`

导入 Markdown 文件到系统。

```bash
python -m src.cli.commands import <file_path> --employee-id <id> [options]
```

**参数**:

| 参数 | 必需 | 说明 | 示例 |
|------|------|------|------|
| `file_path` | 是 | Markdown 文件路径 | `./records/january.md` |
| `--employee-id` | 是 | 员工ID | `--employee-id E001` |
| `--verbose` | 否 | 详细输出 | `--verbose` |

**示例**:

```bash
# 基础导入
python -m src.cli.commands import ./employee_ot_record/xuchen.md --employee-id E001

# 详细输出
python -m src.cli.commands import ./records/jan.md --employee-id E002 --verbose
```

---

### 3.2 数据查询命令

#### `query`

查询加班记录。

```bash
python -m src.cli.commands query [options]
```

**选项**:

| 选项 | 说明 | 示例 |
|------|------|------|
| `--employee-id` | 按员工筛选 | `--employee-id E001` |
| `--start-date` | 开始日期 | `--start-date 2025-01-01` |
| `--end-date` | 结束日期 | `--end-date 2025-01-31` |
| `--status` | 状态筛选 | `--status pending` |
| `--format` | 输出格式 | `--format table` (可选: json, csv) |

**示例**:

```bash
# 查询所有记录
python -m src.cli.commands query

# 查询特定员工
python -m src.cli.commands query --employee-id E001

# 查询日期范围
python -m src.cli.commands query --start-date 2025-01-01 --end-date 2025-01-31

# JSON 输出
python -m src.cli.commands query --employee-id E001 --format json
```

---

### 3.3 报表生成命令

#### `report`

生成各类报表。

```bash
python -m src.cli.commands report <type> [options]
```

**子命令**:

| 子命令 | 说明 |
|--------|------|
| `monthly` | 月度加班报表 |
| `comp-off` | 调休余额报表 |
| `salary` | 工资计算报表 |

**月度报表选项**:

```bash
python -m src.cli.commands report monthly --employee-id <id> --year <year> --month <month>
```

| 选项 | 必需 | 说明 |
|------|------|------|
| `--employee-id` | 是 | 员工ID |
| `--year` | 是 | 年份 |
| `--month` | 是 | 月份 (1-12) |

**示例**:

```bash
# 生成月度报表
python -m src.cli.commands report monthly --employee-id E001 --year 2025 --month 1

# 生成调休余额报表
python -m src.cli.commands report comp-off --employee-id E001

# 生成工资计算表
python -m src.cli.commands report salary --employee-id E001 --year 2025 --month 1
```

---

### 3.4 数据导出命令

#### `export`

导出数据到文件。

```bash
python -m src.cli.commands export [options]
```

**选项**:

| 选项 | 说明 | 示例 |
|------|------|------|
| `--employee-id` | 按员工筛选 | `--employee-id E001` |
| `--start-date` | 开始日期 | `--start-date 2025-01-01` |
| `--end-date` | 结束日期 | `--end-date 2025-12-31` |
| `--format` | 导出格式 | `--format json` (json, csv, xlsx) |
| `--output` | 输出文件 | `--output ./export/data.json` |

**示例**:

```bash
# 导出所有记录为 JSON
python -m src.cli.commands export --format json --output ./export/all.json

# 导出特定员工 CSV
python -m src.cli.commands export --employee-id E001 --format csv --output ./export/e001.csv

# 导出年度数据
python -m src.cli.commands export --start-date 2025-01-01 --end-date 2025-12-31 --format xlsx
```

---

### 3.5 工资计算命令

#### `calculate-salary`

计算员工加班工资。

```bash
python -m src.cli.commands calculate-salary --month <YYYY-MM> [options]
```

**选项**:

| 选项 | 说明 | 必需 |
|------|------|------|
| `--month` | 月份 (YYYY-MM) | 是 |
| `--employee-id` | 特定员工 | 否 |
| `--all` | 所有员工 | 否 |
| `--output` | 输出文件 | 否 |

**示例**:

```bash
# 计算单个员工
python -m src.cli.commands calculate-salary --month 2025-01 --employee-id E001

# 计算所有员工
python -m src.cli.commands calculate-salary --month 2025-01 --all

# 导出计算结果
python -m src.cli.commands calculate-salary --month 2025-01 --all --output ./salary_202501.json
```

---

### 3.6 节假日管理命令

#### `holidays`

管理节假日数据。

```bash
python -m src.cli.commands holidays <subcommand> [options]
```

**子命令**:

| 子命令 | 说明 |
|--------|------|
| `list` | 列出节假日 |
| `import` | 从文本导入 |
| `check` | 检查配置 |

**列表示例**:

```bash
# 列出所有节假日
python -m src.cli.commands holidays list

# 列出特定年份
python -m src.cli.commands holidays list --year 2025
```

**导入示例**:

```bash
# 从文件导入
python -m src.cli.commands holidays import --file ./holidays_2025.txt --year 2025

# 交互式导入
python -m src.cli.commands holidays import --year 2025 --interactive
```

---

### 3.7 调休管理命令

#### `comp-off`

管理调休余额。

```bash
python -m src.cli.commands comp-off <subcommand> [options]
```

**子命令**:

| 子命令 | 说明 |
|--------|------|
| `balance` | 查询余额 |
| `use` | 记录调休使用 |
| `expiring` | 查询即将过期 |
| `mark-expired` | 标记过期 |

**查询余额**:

```bash
python -m src.cli.commands comp-off balance --employee-id E001
```

**记录调休使用**:

```bash
python -m src.cli.commands comp-off use --employee-id E001 --hours 8 --date 2025-02-15 --reason "个人事务"
```

**查询即将过期**:

```bash
# 查询30天内过期
python -m src.cli.commands comp-off expiring --within 30

# 生成提醒通知
python -m src.cli.commands comp-off expiring --within 30 --generate-notice
```

**标记过期**:

```bash
python -m src.cli.commands comp-off mark-expired
```

---

### 3.8 数据库管理命令

#### `init-db`

初始化数据库。

```bash
python -m src.cli.commands init-db [options]
```

**选项**:

| 选项 | 说明 |
|------|------|
| `--force` | 强制重新初始化（会清空数据） |

**示例**:

```bash
# 初始化数据库
python -m src.cli.commands init-db

# 强制重新初始化（危险！）
python -m src.cli.commands init-db --force
```

---

#### `backup`

备份数据库。

```bash
python -m src.cli.commands backup [options]
```

**选项**:

| 选项 | 说明 | 示例 |
|------|------|------|
| `--output` | 备份文件路径 | `--output ./backup/db_$(date +%Y%m%d).db` |

**示例**:

```bash
# 默认备份
python -m src.cli.commands backup

# 指定路径
python -m src.cli.commands backup --output ./backup/overtime_2025.db
```

---

## 4. 返回码

| 返回码 | 含义 | 说明 |
|--------|------|------|
| 0 | 成功 | 命令执行成功 |
| 1 | 通用错误 | 未分类的错误 |
| 2 | 参数错误 | 命令参数无效 |
| 3 | 文件错误 | 文件不存在或无法访问 |
| 4 | 数据库错误 | 数据库操作失败 |
| 5 | 解析错误 | 数据解析失败 |

---

## 5. 输出格式

### 5.1 表格格式 (默认)

```
╔═══════════════════════════════════════════════════════════════╗
║                     加班记录导入报告                           ║
╠═══════════════════════════════════════════════════════════════╣
│ 文件: employee_ot_record/xuchen.md                            │
│ 员工: 徐晨                                                    │
│ 导入时间: 2026-04-06 09:30:15                                 │
├───────────────────────────────────────────────────────────────┤
│ 解析统计                                                      │
│                                                               │
│   总记录数:        37                                         │
│   ├─ 成功解析:     35 (94.6%)                                │
│   └─ 解析失败:      2 (5.4%)                                 │
╚═══════════════════════════════════════════════════════════════╝
```

### 5.2 JSON 格式

```json
{
  "success": true,
  "import_session_id": 123,
  "total_records": 37,
  "success_count": 35,
  "failed_count": 2,
  "details": {
    "overtime_records": 28,
    "leave_records": 3,
    "comp_off_records": 4
  }
}
```

### 5.3 CSV 格式

```csv
date,type,hours,description
2025-01-15,overtime,2.5,晚上加班
2025-01-16,leave,4,请假半天
```

---

## 6. 故障排除

### 6.1 命令未找到

**症状**: `ModuleNotFoundError: No module named 'src'`

**解决**:

```bash
# 确保在项目根目录
pwd  # 应显示 .../002ot_calculation

# 设置 PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# 或使用相对导入
python -m src.cli.commands
```

### 6.2 数据库连接失败

**症状**: `sqlite3.OperationalError: unable to open database file`

**解决**:

```bash
# 检查数据库目录
mkdir -p data
chmod 755 data

# 初始化数据库
python -m src.cli.commands init-db
```

### 6.3 权限不足

**症状**: `Permission denied` 错误

**解决**:

```bash
# 检查文件权限
ls -la data/

# 修复权限
chmod 755 data logs .flask_session
```

---

## 7. 批量操作脚本示例

### 7.1 批量导入

```bash
#!/bin/bash
# batch_import.sh

EMPLOYEES=("E001:xuchen" "E002:zhangsan" "E003:lisi")

for emp in "${EMPLOYEES[@]}"; do
    IFS=':' read -r id name <<< "$emp"
    echo "Importing for $id ($name)..."
    python -m src.cli.commands import \
        ./employee_ot_record/${name}.md \
        --employee-id "$id"
done
```

### 7.2 月度报表批量生成

```bash
#!/bin/bash
# monthly_reports.sh

YEAR=2025
MONTH=1
EMPLOYEES=("E001" "E002" "E003")

for emp in "${EMPLOYEES[@]}"; do
    python -m src.cli.commands report monthly \
        --employee-id "$emp" \
        --year "$YEAR" \
        --month "$MONTH" \
        > "./reports/${emp}_${YEAR}_${MONTH}.txt"
done
```

---

## 8. 相关文档

- [11-operation-sop.md](./11-operation-sop.md) - 操作 SOP
- [27-runbook.md](./27-runbook.md) - 运维手册
- [25-api-reference.md](./25-api-reference.md) - Web API 参考
