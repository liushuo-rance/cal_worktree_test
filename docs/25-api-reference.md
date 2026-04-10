# Web API 接口参考文档

> 本文档描述 Flask Web 应用的所有 HTTP 接口。

---

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档名称 | Web API 接口参考文档 |
| 版本 | 1.0 |
| 创建日期 | 2026-04-09 |
| 状态 | 初稿 |

---

## 2. 接口概述

### 2.1 基础信息

| 项目 | 内容 |
|------|------|
| 基础 URL | `http://127.0.0.1:5001` |
| 协议 | HTTP |
| 字符编码 | UTF-8 |
| 数据格式 | HTML / JSON |

### 2.2 Blueprint 结构

| Blueprint | URL 前缀 | 功能 |
|-----------|----------|------|
| `dashboard` | `/` | 仪表盘首页 |
| `employees` | `/employees` | 员工管理 |
| `records` | `/records` | 记录导入 |
| `review` | `/review` | 审批流程 |
| `reports` | `/reports` | 报表中心 |
| `holidays` | `/holidays` | 节假日管理 |

---

## 3. Dashboard API

### 3.1 获取首页

```http
GET /
```

**响应**: HTML 页面

**说明**: 系统仪表盘首页，显示统计概览

---

## 4. Employees API

### 4.1 获取员工列表

```http
GET /employees
```

**响应**: HTML 页面

**说明**: 显示所有员工列表

---

### 4.2 获取员工详情

```http
GET /employees/<employee_id>/
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| employee_id | string | 员工ID |

**响应**: HTML 页面

**说明**: 显示指定员工的详细信息和记录

---

### 4.3 创建员工

```http
POST /employees/create/
```

**Content-Type**: `application/x-www-form-urlencoded`

**参数**:
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| employee_id | string | 是 | 员工唯一标识 |
| name | string | 是 | 员工姓名 |
| department | string | 否 | 部门 |

**响应**: 重定向到员工列表

---

## 5. Records API

### 5.1 导入页面

```http
GET /records/import/
```

**响应**: HTML 页面

**说明**: 显示文件上传表单

---

### 5.2 提交导入

```http
POST /records/import/
```

**Content-Type**: `multipart/form-data`

**参数**:
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| employee_id | string | 是 | 目标员工ID |
| file | file | 是 | Markdown 文件 |

**响应**: 重定向到预览页面

---

### 5.3 获取导入进度

```http
GET /records/import/progress/
```

**响应**: `application/json`

```json
{
  "progress": [
    {
      "timestamp": "10:30:15",
      "step": "ai_start",
      "message": "AI解析中...",
      "progress": 25
    }
  ],
  "latest": { ... },
  "total_steps": 3
}
```

---

### 5.4 预览导入

```http
GET /records/import/preview/
```

**响应**: HTML 页面

**说明**: 显示 AI 解析结果预览

---

### 5.5 确认导入

```http
POST /records/import/confirm/
```

**Content-Type**: `application/x-www-form-urlencoded`

**参数**: 表单数据，包含解析后的记录数组

**响应**: 重定向到员工详情页

---

### 5.6 取消导入

```http
GET /records/import/cancel/
```

**响应**: 重定向到导入页面

---

### 5.7 为员工导入

```http
GET /records/import/employee/<employee_id>/
POST /records/import/employee/<employee_id>/
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| employee_id | string | 预填充的员工ID |

**响应**: HTML 页面 / 重定向

---

## 6. Review API

### 6.1 审批队列

```http
GET /review/
```

**响应**: HTML 页面

**说明**: 显示待审批记录列表

---

### 6.2 审批单项

```http
GET /review/item/<int:item_id>/
POST /review/item/<int:item_id>/
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| item_id | integer | 记录ID |

**POST 参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| action | string | `approve` 或 `reject` |
| comment | string | 审批意见 |

**响应**: HTML 页面 / 重定向

---

## 7. Reports API

### 7.1 报表首页

```http
GET /reports/
```

**响应**: HTML 页面

**说明**: 显示可用报表列表

---

### 7.2 月度报表

```http
GET /reports/monthly/<employee_id>/<year>/<month>/
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| employee_id | string | 员工ID |
| year | integer | 年份 |
| month | integer | 月份 (1-12) |

**响应**: HTML 页面

**说明**: 显示指定月份的加班报表

---

### 7.3 调休余额报表

```http
GET /reports/comp-off/<employee_id>/
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| employee_id | string | 员工ID |

**响应**: HTML 页面

**说明**: 显示员工调休余额明细

---

### 7.4 工资计算表

```http
GET /reports/salary/<employee_id>/<year>/<month>/
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| employee_id | string | 员工ID |
| year | integer | 年份 |
| month | integer | 月份 |

**响应**: HTML 页面

**说明**: 显示工资计算明细

---

## 8. Holidays API

### 8.1 节假日列表

```http
GET /holidays/
```

**响应**: HTML 页面

**说明**: 显示年度节假日日历

---

### 8.2 节假日导入

```http
GET /holidays/import/
POST /holidays/import/
```

**GET 响应**: HTML 页面（导入表单）

**POST 参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| notice_text | string | 国务院通知文本 |
| year | integer | 年度 |

**POST 响应**: HTML 页面（解析结果预览）

---

### 8.3 删除节假日

```http
POST /holidays/delete/<date>
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| date | string | 日期 (YYYY-MM-DD) |

**响应**: 重定向到节假日列表

---

### 8.4 删除年度数据

```http
POST /holidays/delete-year/<year>
```

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| year | integer | 年度 |

**响应**: 重定向到节假日列表

---

## 9. 错误响应

### 9.1 404 Not Found

```html
<!DOCTYPE html>
<html>
<head><title>Not Found</title></head>
<body>
  <h1>Not Found</h1>
  <p>The requested URL was not found on the server.</p>
</body>
</html>
```

### 9.2 500 Internal Server Error

```html
<!DOCTYPE html>
<html>
<head><title>Internal Server Error</title></head>
<body>
  <h1>Internal Server Error</h1>
  <p>The server encountered an internal error...</p>
</body>
</html>
```

---

## 10. 静态资源

### 10.1 CSS 文件

```http
GET /static/css/<filename>
```

**文件列表**:
- `base.css` - 基础样式
- `tokens.css` - 设计令牌
- `components.css` - 组件样式
- `interactions.css` - 交互动画
- `responsive.css` - 响应式布局

---

### 10.2 JavaScript 文件

```http
GET /static/js/<filename>
```

**文件列表**:
- `components.js` - 组件交互
- `interactions.js` - 交互逻辑

---

## 11. 相关文档

- [20-record-import-feature.md](./20-record-import-feature.md) - 导入功能详细设计
- [12-holiday-management.md](./12-holiday-management.md) - 节假日管理功能
- [28-cli-reference.md](./28-cli-reference.md) - CLI 命令参考
