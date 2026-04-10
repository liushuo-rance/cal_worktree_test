# 加班记录分析系统 - 核心流程设计文档

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档名称 | 核心流程设计文档 |
| 版本 | 1.0 |
| 创建日期 | 2026-04-04 |
| 状态 | 初稿 |

---

## 2. 流程概述

本文档描述系统的核心业务流程，包括：
- 批量导入流程
- 单文件解析流程
- 解析决策流程

---


> **重要更新**：本文档描述的流程图中包含的关键词匹配、正则表达式解析等逻辑为原始设计。
>
> **实际实现已改为AI大模型解析**：系统完全依赖火山方舟API进行智能文本解析，不再使用本地关键词/正则规则。
> 实际代码实现请参见 `docs/03-data-parsing-strategy.md` 和 `src/services/ai_parser_service.py`

## 3. 批量导入时序图

### 3.1 批量导入完整流程

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as CLI Interface
    participant IS as ImportService
    participant FP as FileProcessor
    participant PP as ParserPipeline
    participant RR as RecordRepository
    participant FR as FileImportRepository
    participant DB as SQLite Database

    User->>CLI: import --dir /data/overtime_records
    CLI->>IS: import_directory(path)
    
    IS->>FP: scan_directory(path)
    FP-->>IS: file_list[]
    
    loop For each file
        IS->>FR: create_import_record(filename, path)
        FR->>DB: INSERT import_sessions
        DB-->>FR: import_id
        FR-->>IS: import_record
        
        IS->>FP: process_file(file_path)
        
        FP->>FP: read_file_content()
        FP->>FP: split_lines()
        FP->>FR: update_total_lines(import_id, count)
        FR->>DB: UPDATE import_sessions
        
        loop For each line
            FP->>PP: parse_line(line_text)
            
            PP->>PP: extract_date()
            PP->>PP: classify_type()
            PP->>PP: extract_hours()
            PP->>PP: build_record()
            PP->>PP: validate_record()
            
            alt Parse Success
                PP-->>FP: ParsedRecord
                FP->>RR: save(record)
                RR->>DB: INSERT overtime_records
                DB-->>RR: record_id
                RR-->>FP: saved_record
                FP->>FR: increment_success(import_id)
            else Parse Warning
                PP-->>FP: ParsedRecord(with warnings)
                FP->>RR: save(record)
                RR->>DB: INSERT overtime_records
                FP->>FR: log_warning(import_id, line, warning)
            else Parse Error
                PP-->>FP: ParseError
                FP->>FR: log_error(import_id, line, error)
                FR->>DB: INSERT import_records
                FP->>FR: increment_error(import_id)
            end
        end
        
        FP-->>IS: processing_result
        IS->>FR: update_status(import_id, status)
        FR->>DB: UPDATE import_sessions
    end
    
    IS->>IS: generate_summary_report()
    IS-->>CLI: ImportReport
    CLI-->>User: Display results
```

### 3.2 批量导入简化时序图

```mermaid
sequenceDiagram
    participant User
    participant System
    participant DB

    User->>System: 提交批量导入请求
    activate System
    
    System->>System: 扫描目录获取文件列表
    System->>DB: 创建导入任务记录
    
    loop 每个文件
        System->>System: 读取文件内容
        
        loop 每行记录
            System->>System: 解析日期
            System->>System: 识别类型
            System->>System: 提取时长
            System->>System: 验证数据
            
            alt 解析成功
                System->>DB: 保存记录
            else 解析失败
                System->>DB: 记录错误日志
            end
        end
        
        System->>DB: 更新文件导入状态
    end
    
    System->>System: 生成导入报告
    System->>DB: 更新任务状态
    deactivate System
    
    System-->>User: 返回导入结果
```

---

## 4. 单文件解析时序图

### 4.1 单文件解析完整流程

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as CLI
    participant IS as ImportService
    participant TE as TextExtractor
    participant LP as LineParser
    participant DN as DateNormalizer
    participant TC as TypeClassifier
    participant HC as HoursCalculator
    participant RV as RecordValidator
    participant RR as RecordRepository
    participant PR as ParseLogRepository
    participant DB as Database

    User->>CLI: import --file overtime.md
    CLI->>IS: import_file(file_path)
    
    IS->>TE: extract(file_path)
    TE->>TE: detect_encoding()
    TE->>TE: read_content()
    TE-->>IS: raw_text
    
    IS->>LP: parse_lines(raw_text)
    LP->>LP: split_by_newline()
    LP->>LP: filter_empty_lines()
    LP->>LP: normalize_whitespace()
    LP-->>IS: lines[]
    
    IS->>IS: create_import_record()
    IS->>DB: INSERT import_sessions
    DB-->>IS: import_id
    
    loop For each line
        IS->>DN: normalize_date(line)
        DN->>DN: match_date_patterns()
        DN->>DN: parse_date_components()
        DN->>DN: validate_date_range()
        DN-->>IS: date_result
        
        IS->>TC: classify_type(line)
        TC->>TC: keyword_matching()
        TC->>TC: pattern_matching()
        TC->>TC: calculate_confidence()
        TC-->>IS: type_result
        
        IS->>HC: calculate_hours(line, type)
        
        alt type == OVERTIME
            HC->>HC: parse_overtime_hours()
        else type == LEAVE
            HC->>HC: parse_leave_hours()
        else type == COMP_OFF
            HC->>HC: parse_comp_off_hours()
        else
            HC->>HC: try_generic_parsing()
        end
        
        HC-->>IS: hours_value
        
        IS->>RV: validate(date, type, hours)
        RV->>RV: check_required_fields()
        RV->>RV: check_date_validity()
        RV->>RV: check_hours_reasonable()
        RV-->>IS: validation_result
        
        alt Validation Passed
            IS->>IS: build_record()
            IS->>RR: save(record)
            RR->>DB: INSERT overtime_records
            DB-->>RR: record_id
            RR-->>IS: saved_record
            IS->>IS: increment_success()
        else Validation Failed
            IS->>PR: log_parse_error()
            PR->>DB: INSERT import_records
            IS->>IS: increment_error()
        end
    end
    
    IS->>DB: UPDATE import_sessions (final status)
    IS->>IS: generate_report()
    IS-->>CLI: ImportResult
    CLI-->>User: Display summary
```

### 4.2 解析器管道内部时序图

```mermaid
sequenceDiagram
    participant Pipeline
    participant Preprocessor
    participant DateParser
    participant TypeParser
    participant HoursParser
    participant Validator
    participant RecordBuilder

    Pipeline->>Preprocessor: process(raw_text)
    Preprocessor->>Preprocessor: clean_whitespace()
    Preprocessor->>Preprocessor: normalize_encoding()
    Preprocessor-->>Pipeline: cleaned_text

    Pipeline->>DateParser: parse(cleaned_text)
    DateParser->>DateParser: match_date_pattern()
    DateParser->>DateParser: extract_date_parts()
    DateParser->>DateParser: validate_date()
    DateParser-->>Pipeline: date_info, remaining_text

    Pipeline->>TypeParser: classify(remaining_text)
    TypeParser->>TypeParser: scan_keywords()
    TypeParser->>TypeParser: apply_rules()
    TypeParser->>TypeParser: score_matches()
    TypeParser-->>Pipeline: record_type, confidence

    Pipeline->>HoursParser: extract(remaining_text, type)
    HoursParser->>HoursParser: select_strategy(type)
    HoursParser->>HoursParser: apply_extraction()
    HoursParser->>HoursParser: calculate_value()
    HoursParser-->>Pipeline: hours_value

    Pipeline->>Validator: validate_all()
    Validator->>Validator: check_completeness()
    Validator->>Validator: check_consistency()
    Validator->>Validator: check_constraints()
    Validator-->>Pipeline: validation_result

    alt Validation Passed
        Pipeline->>RecordBuilder: build()
        RecordBuilder->>RecordBuilder: assemble_fields()
        RecordBuilder->>RecordBuilder: set_metadata()
        RecordBuilder-->>Pipeline: ot_record
    else Validation Failed
        RecordBuilder-->>Pipeline: validation_errors
    end
```

---

## 5. 解析决策活动图

### 5.1 主解析决策流程

```mermaid
flowchart TD
    Start([开始解析]) --> A[接收原始文本行]
    
    A --> B[预处理文本]
    B --> C{文本是否为空?}
    C -->|是| D[标记为跳过]
    C -->|否| E[提取日期部分]
    
    D --> Z[记录解析日志]
    
    E --> F{日期提取成功?}
    F -->|否| G[标记日期错误]
    F -->|是| H[解析日期范围]
    
    G --> Z
    
    H --> I{日期范围有效?}
    I -->|否| J[标记范围错误]
    I -->|是| K[提取内容文本]
    
    J --> Z
    
    K --> L[识别记录类型]
    L --> M{类型识别成功?}
    M -->|否| N[尝试通用解析]
    M -->|是| O[根据类型选择解析器]
    
    N --> P{通用解析成功?}
    P -->|否| Q[标记类型错误]
    P -->|是| R[解析时长]
    
    Q --> Z
    
    O --> R
    
    R --> S{时长解析成功?}
    S -->|否| T[标记时长错误]
    S -->|是| U[构建记录对象]
    
    T --> Z
    
    U --> V[验证记录完整性]
    V --> W{验证通过?}
    W -->|否| X[标记验证错误]
    W -->|是| Y[保存到数据库]
    
    X --> Z
    Y --> AA[更新统计信息]
    Z --> AA
    
    AA --> End([结束])
```

### 5.2 类型识别决策流程

```mermaid
flowchart TD
    Start([开始类型识别]) --> A[输入: 内容文本]
    
    A --> B[扫描加班关键词]
    B --> C{匹配加班模式?}
    C -->|是| D[计算加班置信度]
    C -->|否| E[扫描请假关键词]
    
    D --> D1{置信度>阈值?}
    D1 -->|是| D2[返回: OVERTIME]
    D1 -->|否| E
    
    E --> F{匹配请假模式?}
    F -->|是| G[计算请假置信度]
    F -->|否| H[扫描调休关键词]
    
    G --> G1{置信度>阈值?}
    G1 -->|是| G2[返回: LEAVE]
    G1 -->|否| H
    
    H --> I{匹配调休模式?}
    I -->|是| J[计算调休置信度]
    I -->|否| K[扫描调整关键词]
    
    J --> J1{置信度>阈值?}
    J1 -->|是| J2[返回: COMP_OFF]
    J1 -->|否| K
    
    K --> L{匹配调整模式?}
    L -->|是| M[计算调整置信度]
    L -->|否| N[尝试模式匹配]
    
    M --> M1{置信度>阈值?}
    M1 -->|是| M2[返回: ADJUSTMENT]
    M1 -->|否| N
    
    N --> O[应用备用规则]
    O --> P{匹配成功?}
    P -->|是| Q[返回对应类型]
    P -->|否| R[返回: UNKNOWN]
    
    D2 --> End([结束])
    G2 --> End
    J2 --> End
    M2 --> End
    Q --> End
    R --> End
```

### 5.3 时长解析决策流程

```mermaid
flowchart TD
    Start([开始时长解析]) --> A[输入: 文本, 类型]
    
    A --> B{类型?}
    
    B -->|OVERTIME| C[解析加班时长]
    B -->|LEAVE| D[解析请假时长]
    B -->|COMP_OFF| E[解析调休时长]
    B -->|ADJUSTMENT| F[解析调整时长]
    B -->|UNKNOWN| G[尝试通用解析]
    
    C --> C1[匹配"晚上X小时"]
    C1 --> C2{匹配成功?}
    C2 -->|是| C3[提取数字]
    C2 -->|否| C4[匹配"早X到晚Y"]
    
    C4 --> C5{匹配成功?}
    C5 -->|是| C6[计算时间差]
    C5 -->|否| C7[匹配"X小时"]
    
    C7 --> C8{匹配成功?}
    C8 -->|是| C3
    C8 -->|否| C9[标记解析失败]
    
    D --> D1[匹配"半天"]
    D1 --> D2{匹配成功?}
    D2 -->|是| D3[设置4小时]
    D2 -->|否| D4[匹配"一天/全天"]
    
    D4 --> D5{匹配成功?}
    D5 -->|是| D6[设置8小时]
    D5 -->|否| D7[匹配"X天"]
    
    D7 --> D8{匹配成功?}
    D8 -->|是| D9[计算X*8]
    D8 -->|否| D10[标记解析失败]
    
    E --> E1[同请假解析逻辑]
    E1 --> E2[应用调休系数]
    
    F --> F1[匹配"加/减X小时"]
    F1 --> F2{匹配成功?}
    F2 -->|是| F3[提取数字和符号]
    F2 -->|否| F4[标记解析失败]
    
    G --> G1[扫描所有数字]
    G1 --> G2{找到数字?}
    G2 -->|是| G3[提取第一个数字]
    G2 -->|否| G4[标记解析失败]
    
    C3 --> H[应用符号]
    C6 --> H
    D3 --> H
    D6 --> H
    D9 --> H
    E2 --> H
    F3 --> H
    G3 --> H
    
    H --> I{需要取反?}
    I -->|是| J[乘以-1]
    I -->|否| K[保持正值]
    
    J --> L[验证范围]
    K --> L
    
    L --> M{在有效范围内?}
    M -->|是| N[返回时长值]
    M -->|否| O[标记无效时长]
    
    C9 --> P[返回错误]
    D10 --> P
    F4 --> P
    G4 --> P
    O --> P
    
    N --> End([结束])
    P --> End
```

---

## 6. 错误处理流程

### 6.1 错误处理活动图

```mermaid
flowchart TD
    Start([发生错误]) --> A[捕获异常]
    
    A --> B{错误类型?}
    
    B -->|日期错误| C[记录日期解析错误]
    B -->|类型错误| D[记录类型识别错误]
    B -->|时长错误| E[记录时长解析错误]
    B -->|验证错误| F[记录验证错误]
    B -->|系统错误| G[记录系统错误]
    
    C --> H[保存原始文本]
    D --> H
    E --> H
    F --> H
    G --> H
    
    H --> I[记录行号]
    I --> J[记录错误信息]
    J --> K[写入import_records表]
    
    K --> L{错误级别?}
    
    L -->|CRITICAL| M[跳过当前行]
    L -->|HIGH| N[尝试备用解析]
    L -->|MEDIUM| O[使用默认值]
    L -->|LOW| P[记录警告继续]
    
    N --> Q{备用成功?}
    Q -->|是| P
    Q -->|否| M
    
    M --> R[更新错误计数]
    O --> R
    P --> S[更新警告计数]
    
    R --> T[继续处理下一行]
    S --> T
    
    T --> End([结束])
```

---

## 7. 数据流状态转换

### 7.1 记录状态转换图

```mermaid
stateDiagram-v2
    [*] --> Raw: 读取文件
    
    Raw --> Preprocessing: 预处理
    Preprocessing --> DateExtracted: 提取日期
    Preprocessing --> Invalid: 格式错误
    
    DateExtracted --> TypeClassified: 识别类型
    DateExtracted --> Invalid: 日期无效
    
    TypeClassified --> HoursExtracted: 提取时长
    TypeClassified --> UnknownType: 类型未知
    
    UnknownType --> HoursExtracted: 通用解析
    UnknownType --> Invalid: 解析失败
    
    HoursExtracted --> Validated: 验证数据
    HoursExtracted --> Invalid: 时长无效
    
    Validated --> Saved: 保存成功
    Validated --> Invalid: 验证失败
    
    Saved --> [*]: 完成
    Invalid --> Logged: 记录错误
    Logged --> [*]: 完成
```

---

## 8. 并发处理流程

### 8.1 批量处理并发流程

```mermaid
flowchart TD
    Start([开始批量导入]) --> A[扫描目录获取文件列表]
    
    A --> B[创建线程池]
    B --> C[提交文件处理任务]
    
    C --> D{任务队列}
    D -->|任务1| E[Worker 1]
    D -->|任务2| F[Worker 2]
    D -->|任务N| G[Worker N]
    
    E --> H[解析文件]
    F --> H
    G --> H
    
    H --> I{解析结果}
    I -->|成功| J[批量插入数据库]
    I -->|失败| K[记录错误]
    
    J --> L[更新进度]
    K --> L
    
    L --> M{所有任务完成?}
    M -->|否| D
    M -->|是| N[合并结果]
    
    N --> O[生成汇总报告]
    O --> P[更新导入状态]
    P --> End([结束])
```

---

## 9. 查询流程

### 9.1 数据查询时序图

```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI
    participant QS as QueryService
    participant RR as RecordRepository
    participant ER as EmployeeRepository
    participant DB as Database

    User->>CLI: query --employee E001 --month 2025-09
    CLI->>QS: query(criteria)
    
    QS->>QS: parse_criteria()
    QS->>QS: build_query()
    
    alt By Employee
        QS->>ER: find_by_code(employee_code)
        ER->>DB: SELECT * FROM employees
        DB-->>ER: employee
        ER-->>QS: employee_id
        QS->>RR: find_by_employee(employee_id)
    else By Date Range
        QS->>RR: find_by_date_range(start, end)
    else By Type
        QS->>RR: find_by_type(type)
    else Complex Query
        QS->>RR: find_by_criteria(criteria)
    end
    
    RR->>DB: SELECT * FROM overtime_records
    DB-->>RR: records[]
    RR-->>QS: records[]
    
    QS->>QS: transform_results()
    QS->>QS: calculate_summary()
    QS->>QS: format_output()
    
    QS-->>CLI: QueryResult
    CLI-->>User: Display results
```

---

## 10. 统计报告流程

### 10.1 月度统计生成流程

```mermaid
flowchart TD
    Start([生成月度统计]) --> A[接收统计请求]
    
    A --> B[解析参数]
    B --> C[验证参数]
    
    C --> D{参数有效?}
    D -->|否| E[返回错误]
    D -->|是| F[查询数据库]
    
    F --> G[获取月度记录]
    G --> H[按部门分组]
    H --> I[按类型汇总]
    
    I --> J[计算统计指标]
    J --> K[总记录数]
    J --> L[总加班时长]
    J --> M[总请假时长]
    J --> N[人均加班]
    
    K --> O[组装报告数据]
    L --> O
    M --> O
    N --> O
    
    O --> P[生成图表数据]
    P --> Q[格式化输出]
    
    Q --> R{输出格式?}
    R -->|JSON| S[JSON格式]
    R -->|CSV| T[CSV格式]
    R -->|Table| U[表格格式]
    
    S --> V[返回结果]
    T --> V
    U --> V
    E --> End([结束])
    V --> End
```

---

## 11. 流程优化建议

### 11.1 性能优化点

| 流程阶段 | 优化策略 | 预期效果 |
|----------|----------|----------|
| 文件读取 | 使用内存映射 | 减少IO开销 |
| 批量插入 | 事务批量提交 | 提升10x写入速度 |
| 并发解析 | 多线程处理 | 提升CPU利用率 |
| 数据库查询 | 添加复合索引 | 减少查询时间 |

### 11.2 可靠性优化点

| 流程阶段 | 优化策略 | 预期效果 |
|----------|----------|----------|
| 错误处理 | 分级处理策略 | 提高容错性 |
| 数据验证 | 多重验证机制 | 提高数据质量 |
| 日志记录 | 详细操作日志 | 便于问题排查 |
| 状态管理 | 事务状态追踪 | 支持断点续传 |

---

## 12. 逐行审批流程

### 12.1 逐行审批时序图

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as CLI Interface
    participant RS as ReviewService
    participant PP as ParserPipeline
    participant CD as ComplianceDetector
    participant RC as RecordClassifier
    participant RR as RecordRepository
    participant DB as SQLite Database

    User->>CLI: import --file xuchen.md --review-mode
    CLI->>RS: start_review(file_path)
    
    RS->>RS: read_file_content()
    RS->>RS: split_into_lines()
    RS->>DB: create_import_session()
    
    loop For each line
        RS->>PP: parse_line(line_text)
        PP->>PP: extract_date()
        PP->>PP: extract_type()  // 识别为加班、请假、调休等大类
        PP->>PP: extract_hours()
        PP->>PP: calculate_confidence()
        PP-->>RS: ParseResult
        
        RS->>CD: detect_compliance(parse_result)
        CD->>CD: check_holiday_table()
        CD->>CD: check_weekday()
        CD->>CD: determine_overtime_type()  // 细分为: weekday_morning/lunch/evening/weekend/holiday
        CD-->>RS: ComplianceInfo
        
        Note over RS,DB: 类型分离存储逻辑
        alt 记录类型为 加班(OVERTIME)
            RS->>RR: determine_storage_target('overtime_records')
            RR-->>RS: target_table = 'overtime_records'
            RS->>RS: calculate_overtime_balance()  // 按加班类型分别累计
        else 记录类型为 调休(COMP_OFF)
            RS->>RR: determine_storage_target('comp_off_balances')
            RR-->>RS: target_table = 'comp_off_balances'
            RS->>RS: deduct_from_comp_off_balance()  // 抵扣调休余额
        else 记录类型为 请假(LEAVE)
            RS->>RR: determine_storage_target('leave_records')
            RR-->>RS: target_table = 'leave_records'
        end
        
        RS->>RC: classify_review_need()
        RC->>RC: score_confidence()
        RC->>RC: check_exceptions()
        RC-->>RS: ReviewClassification
        
        alt 高置信度
            RS->>CLI: display_auto_approved(parse_result)
            CLI-->>User: 显示自动通过信息
            User->>CLI: confirm_or_reject()
            CLI-->>RS: user_decision
        else 中置信度
            RS->>CLI: display_for_review(parse_result, compliance_info)
            CLI-->>User: 显示详细解析结果
            User->>CLI: approve() / revise() / reject()
            CLI-->>RS: user_decision
        else 低置信度
            RS->>CLI: display_manual_required(parse_result)
            CLI-->>User: 显示必须人工处理
            User->>CLI: manual_input()
            CLI-->>RS: manual_record
        end
        
        RS->>RS: apply_user_decision()
        
        alt 用户通过
            RS->>RR: save(record)
            RR->>DB: INSERT overtime_records
            RS->>RS: update_system_calculated_balance()  // 按《劳动法》规则独立计算，不参考文件累计值
        else 用户修订
            RS->>RR: save(revised_record)
            RR->>DB: INSERT overtime_records
            RS->>RS: update_system_calculated_balance()  // 按《劳动法》规则独立计算，不参考文件累计值
        else 用户驳回
            RS->>DB: log_rejection(line, reason)
        end
        
        RS->>CLI: display_next_line_prompt()
    end
    
    RS->>RS: generate_review_report()
    RS-->>CLI: ReviewReport
    CLI-->>User: 显示审批完成报告
```

### 12.2 行解析详情展示界面

```
═══════════════════════════════════════════════════════════════════════════════
                         加班记录逐行审批系统
═══════════════════════════════════════════════════════════════════════════════

📄 文件: employee_ot_record/xuchen.md          行号: 29 / 61
👤 员工: 徐晨

┌─────────────────────────────────────────────────────────────────────────────┐
│ 【原始文本】                                                                 │
│                                                                             │
│   2025.10.25，早7到晚10共15小时，累计48.5小时                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 【系统解析结果】                                                             │
│                                                                             │
│  📅 日期信息                                                                 │
│     • 日期: 2025-10-25                                                      │
│     • 星期: 星期六 (Weekend)                                                │
│     • 是否法定节假日: ❌ 否                                                 │
│     • 是否调休上班日: ❌ 否                                                 │
│                                                                             │
│  📝 记录类型                                                                 │
│     • 原始描述: "早7到晚10共15小时"                                         │
│     • 识别类型: 加班 (Overtime)                                             │
│     • 置信度: 95%                                                           │
│                                                                             │
│  ⏱️  时长计算                                                                │
│     • 工作时段: 07:00 - 22:00                                               │
│     • 总时长: 15小时                                                        │
│     • 系统取值: 15小时 (描述明确指定)                                       │
│                                                                             │
│  ⚖️  合规判定                                                                │
│     • 加班类型: 周末加班 (weekend)                                          │
│     • 工资倍数: 2.0x                                                        │
│     • 可调休: ✅ 是 (15小时全部可调休)                                      │
│     • 调休有效期: 2025-10-25 至 2026-04-25 (6个月)                          │
│                                                                             │
│  🔢 系统独立计算（不参考声明累计）                                          │
│     • 本次记录: +15小时 周末加班                                            │
│     • 系统计算: 15小时可调休（按《劳动法》规则）                            │
│     • 员工声明: "累计48.5小时"（仅供参考，不参与计算）                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 【处理方案选择】                                                             │
│                                                                             │
│   系统推荐: [✓] 通过 - 确认为周末加班，计入可调休余额                       │
│                                                                             │
│   其他选项:                                                                  │
│     [ ] 修订 - 修改解析结果                                                 │
│         └─ 时长: [15    ] 小时                                              │
│         └─ 类型: [周末加班 ▼]                                               │
│         └─ 可调休: [✓]                                                      │
│                                                                             │
│     [ ] 驳回 - 标记为无效记录                                               │
│         └─ 驳回原因: [                      ]                               │
│                                                                             │
│     [ ] 拆分 - 拆分为多条记录                                               │
│         └─ 07:00-18:00 标准工时 (不计加班)                                  │
│         └─ 18:00-22:00 延时加班 (4小时)                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

操作: [P]通过 [E]编辑 [R]驳回 [S]拆分 [B]返回上条 [N]下一条 [Q]保存退出
选择: _

═══════════════════════════════════════════════════════════════════════════════
进度: ████████████████████░░░░░░░░░░░░░░░░░░░░  29/61 (47.5%)
═══════════════════════════════════════════════════════════════════════════════
```

### 12.3 工作日延时加班审批界面（区分时段）

```
═══════════════════════════════════════════════════════════════════════════════
                         加班记录逐行审批系统
═══════════════════════════════════════════════════════════════════════════════

📄 文件: employee_ot_record/xuchen.md          行号: 27 / 61
👤 员工: 徐晨

┌─────────────────────────────────────────────────────────────────────────────┐
│ 【原始文本】                                                                 │
│                                                                             │
│   2025.10.24，早晨1.5小时，晚上5.5小时，累计33.5小时                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 【系统解析结果】                                                             │
│                                                                             │
│  📅 日期信息                                                                 │
│     • 日期: 2025-10-24                                                      │
│     • 星期: 星期五 (Weekday)                                                │
│     • 工作时间: 08:30-12:00, 13:00-17:30                                    │
│                                                                             │
│  📝 记录类型                                                                 │
│     • 识别类型: 加班 (Overtime)                                             │
│     • 置信度: 92%                                                           │
│                                                                             │
│  ⏱️  时段分解（根据公司工作时间）                                           │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐     │
│     │ 时段1: 早晨加班                                                  │     │
│     │   • 描述: "早晨1.5小时"                                          │     │
│     │   • 时段: 07:00 - 08:30 (1.5小时)                                │     │
│     │   • 类型: weekday_morning                                        │     │
│     │   • 工资倍数: 1.5x                                               │     │
│     │   • 可调休: ❌ 否                                                │     │
│     ├─────────────────────────────────────────────────────────────────┤     │
│     │ 时段2: 晚间加班                                                  │     │
│     │   • 描述: "晚上5.5小时"                                          │     │
│     │   • 时段: 17:30 - 23:00 (5.5小时)                                │     │
│     │   • 类型: weekday_evening                                        │     │
│     │   • 工资倍数: 1.5x                                               │     │
│     │   • 可调休: ❌ 否                                                │     │
│     └─────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│     合计加班时长: 1.5 + 5.5 = 7.0小时                                       │
│                                                                             │
│  💾 存储目标                                                                 │
│     • 加班记录表 (overtime_records): 存储2条记录                                   │
│       - 记录1: weekday_morning, 1.5小时                                     │
│       - 记录2: weekday_evening, 5.5小时                                     │
│     • 调休余额表 (comp_off_balances): 无变化（工作日加班不产生调休）        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 【处理方案选择】                                                             │
│                                                                             │
│   系统推荐: [✓] 通过 - 确认为工作日延时加班                                  │
│                                                                             │
│   其他选项:                                                                  │
│     [ ] 修订 - 修改解析结果                                                 │
│         └─ 早晨时长: [1.5   ] 小时                                          │
│         └─ 晚间时长: [5.5   ] 小时                                          │
│         └─ 时段类型: [工作日延时 ▼]                                         │
│                                                                             │
│     [ ] 驳回 - 标记为无效记录                                               │
│         └─ 驳回原因: [                      ]                               │
│                                                                             │
│     [ ] 合并为一条记录                                                      │
│         └─ 总时长: 7.0小时，类型: weekday_mixed                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

操作: [P]通过 [E]编辑 [R]驳回 [M]合并 [B]返回上条 [N]下一条 [Q]保存退出
选择: _

═══════════════════════════════════════════════════════════════════════════════
进度: ████████████████████░░░░░░░░░░░░░░░░░░░░  27/61 (44.3%)
═══════════════════════════════════════════════════════════════════════════════
```

### 12.4 调休记录审批界面（抵扣逻辑）

```
═══════════════════════════════════════════════════════════════════════════════
                         加班记录逐行审批系统
═══════════════════════════════════════════════════════════════════════════════

📄 文件: employee_ot_record/xuchen.md          行号: 47 / 61
👤 员工: 徐晨

┌─────────────────────────────────────────────────────────────────────────────┐
│ 【原始文本】                                                                 │
│                                                                             │
│   2025.12.29-31，调休三天，累计24.5小时                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 【系统解析结果】                                                             │
│                                                                             │
│  📅 日期信息                                                                 │
│     • 日期范围: 2025-12-29 至 2025-12-31 (3天)                              │
│     • 日期类型: 周一、周二、周三（工作日）                                   │
│                                                                             │
│  📝 记录类型                                                                 │
│     • 识别类型: 调休 (Compensatory Leave)                                   │
│     • 时长: -24小时 (3天 × 8小时)                                           │
│                                                                             │
│  💰 抵扣逻辑（FIFO - 先进先出）                                             │
│                                                                             │
│     当前可用调休余额: 48.5小时                                              │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐     │
│     │ 抵扣明细:                                                        │     │
│     │   1. 从 2025-10-25 获得的调休抵扣 15.0小时 → 剩余 0.0小时       │     │
│     │   2. 从 2025-10-26 获得的调休抵扣 9.0小时  → 剩余 6.0小时       │     │
│     │                                                                  │     │
│     │ 抵扣后余额: 48.5 - 24 = 24.5小时                                │     │
│     └─────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  💾 存储目标                                                                 │
│     • 调休余额表 (comp_off_balances):                                       │
│       - 更新记录1: remaining_hours = 0, status = 'used'                     │
│       - 更新记录2: remaining_hours = 6, status = 'active'                   │
│     • 调休使用记录表 (comp_off_usage): 插入2条抵扣记录                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 【处理方案选择】                                                             │
│                                                                             │
│   系统推荐: [✓] 通过 - 确认为调休，按FIFO抵扣周末加班余额                   │
│                                                                             │
│   其他选项:                                                                  │
│     [ ] 部分调休 - 只批准部分天数                                           │
│         └─ 批准天数: [3     ] 天                                            │
│                                                                             │
│     [ ] 转请假 - 工作日调休转为请假（从年假/事假扣除）                      │
│         └─ 请假类型: [年假 ▼]                                               │
│                                                                             │
│     [ ] 驳回 - 调休余额不足或其他原因                                       │
│         └─ 驳回原因: [                      ]                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

操作: [P]通过 [E]编辑 [R]驳回 [C]转换类型 [B]返回上条 [N]下一条 [Q]保存退出
选择: _

═══════════════════════════════════════════════════════════════════════════════
进度: ████████████████████████████████████████░░░  47/61 (77.0%)
═══════════════════════════════════════════════════════════════════════════════
```

### 12.5 复杂案例审批界面

```
═══════════════════════════════════════════════════════════════════════════════
                         加班记录逐行审批系统
═══════════════════════════════════════════════════════════════════════════════

📄 文件: employee_ot_record/lijunjie.md        行号: 3 / 59
👤 员工: 李俊杰

┌─────────────────────────────────────────────────────────────────────────────┐
│ 【原始文本】                                                                 │
│                                                                             │
│   9.10，晚上加班                                                              │
│   抵消了                                                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 【系统解析结果】                                                             │
│                                                                             │
│  📅 日期信息                                                                 │
│     • 日期: 2025-09-10 (继承上一条年份)                                     │
│     • 星期: 星期三 (Weekday)                                                │
│     • ⚠️  注意: 工作日18:00后的加班                                         │
│                                                                             │
│  📝 记录类型                                                                 │
│     • 识别类型: ⚠️  模糊 - 可能为加班或调休抵消                             │
│     • 置信度: 40% (低置信度)                                                │
│                                                                             │
│  ⏱️  时长计算                                                                │
│     • 第1行: "晚上加班" - 未指定时长                                        │
│     • 第2行: "抵消了" - 需要关联前文                                        │
│     • 上下文: 上一条为"9.10，上午请假" (请假半天 = 4小时)                   │
│                                                                             │
│  ⚠️  系统推断 (需人工确认)                                                   │
│                                                                             │
│     方案A: 当天请假和加班相互抵消                                           │
│     ├─ 上午请假 4小时 (扣减)                                                │
│     ├─ 晚上加班 4小时 (增加)                                                │
│     └─ 净变化: 0小时                                                        │
│                                                                             │
│     方案B: 晚上加班用于抵消之前的调休                                         │
│     ├─ 晚上加班 X小时 (需指定)                                              │
│     ├─ 用于抵扣之前的调休或请假                                             │
│     └─ 净变化: +X小时加班，-X小时调休余额                                    │
│                                                                             │
│     方案C: 仅作为状态记录，无实际加班时长                                     │
│     ├─ 标记为"抵消记录"                                                     │
│     ├─ 不计算时长                                                           │
│     └─ 可能需要关联其他记录                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 【请选择处理方案】                                                           │
│                                                                             │
│   [1] 方案A - 当天请假加班相互抵消                                          │
│       └─ 请假4小时，加班4小时，净变化0                                       │
│                                                                             │
│   [2] 方案B - 加班用于抵消之前调休                                          │
│       └─ 加班时长: [    ] 小时                                              │
│       └─ 抵扣哪条记录: [从列表选择 ▼]                                       │
│                                                                             │
│   [3] 方案C - 仅作为状态记录                                                │
│       └─ 记录类型: [状态记录/备注 ▼]                                        │
│                                                                             │
│   [4] 自定义处理                                                            │
│       └─ 日期: [2025-09-10]                                                 │
│       └─ 时长: [    ] 小时                                                  │
│       └─ 类型: [请选择 ▼]                                                   │
│       └─ 说明: [                      ]                                     │
│                                                                             │
│   [R] 驳回 - 记录格式不清晰，需要员工重新提交                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

操作提示: 此记录存在歧义，请选择最符合实际情况的处理方案。

═══════════════════════════════════════════════════════════════════════════════
进度: █████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  3/59 (5.1%)
═══════════════════════════════════════════════════════════════════════════════
```

### 12.6 审批状态流转图

```mermaid
flowchart TD
    Start([读取行文本]) --> Parse[系统解析]
    
    Parse --> A{置信度评估}
    
    A -->|≥90% 高置信度| B[标记: AUTO_APPROVE]
    A -->|70-89% 中置信度| C[标记: REVIEW_SUGGESTED]
    A -->|<70% 低置信度| D[标记: MANUAL_REQUIRED]
    
    B --> E{用户决策}
    C --> E
    D --> E
    
    E -->|通过| F[应用系统解析]
    E -->|修订| G[应用用户修订]
    E -->|驳回| H[标记为无效]
    E -->|跳过| I[暂存待处理]
    
    F --> J[系统独立计算合规结果]
    G --> J
    
    J --> K{校验通过?}
    K -->|是| L[保存记录]
    K -->|否| M[警告并询问]
    
    M --> N{用户确认}
    N -->|强制保存| L
    N -->|返回修改| G
    
    H --> O[记录驳回原因]
    I --> P[加入待处理队列]
    
    L --> Q[更新系统计算余额]
    O --> R[跳过本条]
    P --> S[继续下一行]
    
    Q --> T{是否最后一行?}
    R --> T
    S --> T
    
    T -->|否| Start
    T -->|是| U[生成审批报告]
    
    U --> End([完成])
```

### 12.7 批量审批与逐行审批对比

| 特性 | 批量导入模式 | 逐行审批模式 |
|------|--------------|--------------|
| 适用场景 | 格式规范、高置信度记录 | 格式松散、需要人工确认 |
| 处理速度 | 快 (>100条/秒) | 慢 (人工决定) |
| 准确率 | 依赖自动解析 | 人工保证 |
| 置信度阈值 | ≥90%自动通过 | 所有记录都展示 |
| 纠错能力 | 事后修正 | 实时修正 |
| 合规审查 | 事后检查 | 实时判定 |
| 用户体验 | 等待结果 | 交互式确认 |

### 12.8 审批报告示例

```
═══════════════════════════════════════════════════════════════════════════════
                         审批完成报告
═══════════════════════════════════════════════════════════════════════════════

文件: employee_ot_record/xuchen.md
员工: 徐晨
审批时间: 2026-04-04 14:32:18

┌─────────────────────────────────────────────────────────────────────────────┐
│ 统计摘要                                                                     │
│                                                                             │
│   总记录数:        37                                                       │
│   ├─ 自动通过:     12 (32.4%)                                               │
│   ├─ 人工通过:     20 (54.1%)                                               │
│   ├─ 人工修订:      3 (8.1%)                                                │
│   └─ 驳回:          2 (5.4%)                                                │
│                                                                             │
│ 加班统计:                                                                   │
│   ├─ 工作日延时:   15.5小时 (1.5倍工资，不可调休)                           │
│   ├─ 周末加班:     30.0小时 (可调休30.0小时)                                │
│   └─ 法定假日:      0.0小时                                                 │
│                                                                             │
│ 调休抵扣:                                                                   │
│   ├─ 调休使用:     40.0小时                                                 │
│   └─ 调休余额:      0.0小时 (全部用完)                                      │
│                                                                             │
│ 驳回记录:                                                                   │
│   ├─ 行3: "海军中学晚上半天" - 集体活动，不计入加班                         │
│   └─ 行23: "午餐会1小时" - 公司福利活动，不计入加班                         │
│                                                                             │
│ 修订记录:                                                                   │
│   ├─ 行57: 2025.2.24 → 2026.2.24 (年份修正)                                 │
│   ├─ 行27: 请假 → 调休 (类型修正)                                           │
│   └─ 行31: 时长 15 → 7 (按标准工时计算)                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
                              [导出报告] [完成]
═══════════════════════════════════════════════════════════════════════════════
```

