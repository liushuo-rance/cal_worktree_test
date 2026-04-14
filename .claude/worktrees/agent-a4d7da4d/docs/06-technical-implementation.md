# 加班记录分析系统 - 技术实现方案文档

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 文档名称 | 技术实现方案文档 |
| 版本 | 1.0 |
| 创建日期 | 2026-04-04 |
| 状态 | 初稿 |

---

## 2. 技术栈选型

### 2.1 核心技术栈

| 层次 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 编程语言 | Python | 3.9+ | 主开发语言 |
| 数据库 | SQLite | 3.35+ | 嵌入式关系型数据库 |
| ORM | SQLAlchemy | 2.0+ | SQL工具包和ORM |
| 数据库迁移 | Alembic | 1.12+ | SQLAlchemy的数据库迁移工具 |
| CLI框架 | Click | 8.1+ | Python命令行接口创建工具 |
| 配置管理 | Pydantic Settings | 2.0+ | 配置验证和管理 |
| 日志 | structlog | 23.0+ | 结构化日志 |
| 测试 | pytest | 7.4+ | 测试框架 |
| 类型检查 | mypy | 1.5+ | 静态类型检查 |
| 代码格式化 | black | 23.0+ | 代码格式化 |
| 代码检查 | ruff | 0.1+ | 快速Python linter |

### 2.2 技术选型理由

1. **Python 3.9+**: 成熟的生态，丰富的库支持，适合数据处理任务
2. **SQLite**: 零配置、单文件、事务支持，满足当前需求
3. **SQLAlchemy 2.0**: 强大的ORM，支持类型提示，现代化API
4. **Click**: 简洁的CLI创建方式，自动生成帮助文档
5. **Pydantic**: 强大的数据验证，与类型提示完美集成

---

## 3. 项目目录结构

```
ot_calculation/
├── pyproject.toml              # 项目配置和依赖
├── README.md                   # 项目说明
├── .gitignore                  # Git忽略文件
├── .env.example                # 环境变量示例
├── alembic.ini                 # 数据库迁移配置
├── Makefile                    # 常用命令快捷方式
│
├── src/                        # 源代码目录
│   └── ot_calculation/        # 主包
│       ├── __init__.py
│       ├── __main__.py        # 入口点
│       │
│       ├── core/              # 核心模块
│       │   ├── __init__.py
│       │   ├── models.py      # 数据模型（Pydantic/SQLAlchemy）
│       │   ├── constants.py   # 常量定义
│       │   ├── enums.py       # 枚举类型
│       │   └── exceptions.py  # 自定义异常
│       │
│       ├── config/            # 配置模块
│       │   ├── __init__.py
│       │   ├── settings.py    # 应用配置
│       │   └── rules.yaml     # 解析规则配置
│       │
│       ├── parsers/           # 解析器模块
│       │   ├── __init__.py
│       │   ├── base.py        # 解析器基类
│       │   ├── pipeline.py    # 解析管道
│       │   ├── date_parser.py # 日期解析器
│       │   ├── type_parser.py # 类型识别器
│       │   ├── hours_parser.py# 时长解析器
│       │   └── validator.py   # 验证器
│       │
│       ├── services/          # 服务层
│       │   ├── __init__.py
│       │   ├── import_service.py
│       │   ├── query_service.py
│       │   ├── statistics_service.py
│       │   └── validation_service.py
│       │
│       ├── repositories/      # 数据访问层
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── database.py    # 数据库连接
│       │   ├── employee_repository.py
│       │   ├── record_repository.py
│       │   └── import_repository.py
│       │
│       ├── interfaces/        # 接口层
│       │   ├── __init__.py
│       │   ├── cli.py         # 命令行接口
│       │   └── commands/      # CLI命令
│       │       ├── __init__.py
│       │       ├── import_cmd.py
│       │       ├── query_cmd.py
│       │       └── stats_cmd.py
│       │
│       └── utils/             # 工具模块
│           ├── __init__.py
│           ├── logger.py      # 日志配置
│           ├── file_utils.py  # 文件工具
│           └── helpers.py     # 辅助函数
│
├── tests/                     # 测试目录
│   ├── __init__.py
│   ├── conftest.py           # pytest配置和fixtures
│   ├── unit/                 # 单元测试
│   │   ├── __init__.py
│   │   ├── test_parsers/
│   │   ├── test_services/
│   │   └── test_repositories/
│   ├── integration/          # 集成测试
│   │   ├── __init__.py
│   │   └── test_import_flow.py
│   └── fixtures/             # 测试数据
│       ├── sample_records.md
│       └── sample_data.sql
│
├── docs/                     # 文档目录
│   ├── 01-prd.md
│   ├── 02-system-architecture.md
│   ├── 03-data-parsing-strategy.md
│   ├── 04-database-design.md
│   ├── 05-core-process-design.md
│   ├── 06-technical-implementation.md
│   ├── 07-testing-strategy.md
│   └── 08-deployment.md
│
├── migrations/               # 数据库迁移
│   ├── versions/
│   └── env.py
│
└── scripts/                  # 工具脚本
    ├── init_db.py
    ├── backup_db.py
    └── generate_report.py
```

---

## 4. 核心类设计

### 4.1 数据模型类

```python
# src/ot_calculation/core/models.py

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Float, Text, Date, DateTime, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy基类"""
    pass


class Employee(Base):
    """员工模型"""
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关系
    records: Mapped[list["OTRecord"]] = relationship(back_populates="employee")
    balances: Mapped[list["EmployeeBalance"]] = relationship(back_populates="employee")

    def __repr__(self) -> str:
        return f"<Employee({self.employee_code}: {self.name})>"


class OTRecord(Base):
    """加班记录模型"""
    __tablename__ = "ot_records"

    # 时间存储（正数，支持小时和分钟）
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    description: Mapped[Optional[str]] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关系
    employee: Mapped["Employee"] = relationship(back_populates="overtime_records")
    file_import: Mapped[Optional["FileImport"]] = relationship(back_populates="overtime_records")

    def __repr__(self) -> str:
        return f"<OvertimeRecord({self.date_start}, {self.overtime_type}, {self.duration_hours}h{self.duration_minutes}m)>"


class LeaveRecord(Base):
    """请假记录模型"""
    __tablename__ = "leave_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    file_import_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("file_imports.id"), nullable=True
    )
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    leave_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 时间存储（正数，支持小时和分钟）
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    description: Mapped[Optional[str]] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关系
    employee: Mapped["Employee"] = relationship(back_populates="leave_records")
    file_import: Mapped[Optional["FileImport"]] = relationship(back_populates="leave_records")

    def __repr__(self) -> str:
        return f"<LeaveRecord({self.date_start}, {self.leave_type}, {self.duration_hours}h{self.duration_minutes}m)>"


class FileImport(Base):
    """文件导入记录模型"""
    __tablename__ = "file_imports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    total_lines: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="pending")

    # 关系
    records: Mapped[list["OTRecord"]] = relationship(back_populates="file_import")
    parse_logs: Mapped[list["ParseLog"]] = relationship(back_populates="file_import")

    def __repr__(self) -> str:
        return f"<FileImport({self.filename}, {self.status})>"


class ParseLog(Base):
    """解析日志模型"""
    __tablename__ = "parse_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_import_id: Mapped[int] = mapped_column(
        ForeignKey("file_imports.id"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 关系
    file_import: Mapped["FileImport"] = relationship(back_populates="parse_logs")

    def __repr__(self) -> str:
        return f"<ParseLog(line {self.line_number}: {self.parse_status})>"
```

### 4.2 解析器基类

```python
# src/ot_calculation/parsers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ParseResult:
    """解析结果数据类"""
    success: bool
    data: Optional[Any] = None
    error_message: Optional[str] = None
    confidence: float = 0.0
    raw_text: Optional[str] = None


class BaseParser(ABC):
    """解析器基类"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._error_message: Optional[str] = None

    @abstractmethod
    def parse(self, text: str) -> ParseResult:
        """解析文本，返回解析结果"""
        pass

    def validate(self, result: ParseResult) -> bool:
        """验证解析结果"""
        return result.success and result.data is not None

    def get_error(self) -> Optional[str]:
        """获取错误信息"""
        return self._error_message

    def _set_error(self, message: str) -> None:
        """设置错误信息"""
        self._error_message = message
```

### 4.3 解析管道类

```python
# src/ot_calculation/parsers/pipeline.py

from typing import List, Optional
from dataclasses import dataclass
from datetime import date

from .base import BaseParser, ParseResult
from .date_parser import DateParser
from .type_parser import TypeParser
from .hours_parser import HoursParser
from ..core.models import OTRecord
from ..core.enums import RecordType


@dataclass
class ParsedRecord:
    """解析后的记录数据类"""
    date_start: date
    date_end: date
    record_type: RecordType
    hours: Optional[float]
    description: Optional[str]
    raw_text: str
    confidence: float = 0.0


class ParserPipeline:
    """解析管道，协调多个解析器"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.date_parser = DateParser(config.get("date", {}))
        self.type_parser = TypeParser(config.get("type", {}))
        self.hours_parser = HoursParser(config.get("hours", {}))
        self._errors: List[str] = []

    def parse_line(self, line: str) -> ParseResult:
        """解析单行文本"""
        self._errors.clear()

        # 步骤1: 提取日期
        date_result = self.date_parser.parse(line)
        if not date_result.success:
            self._errors.append(f"日期解析失败: {date_result.error_message}")
            return ParseResult(
                success=False,
                error_message="; ".join(self._errors),
                raw_text=line
            )

        # 步骤2: 识别类型
        type_result = self.type_parser.parse(date_result.remaining_text)
        if not type_result.success:
            self._errors.append(f"类型识别失败: {type_result.error_message}")
            # 尝试通用解析
            type_result.data = RecordType.UNKNOWN

        # 步骤3: 提取时长
        hours_result = self.hours_parser.parse(
            date_result.remaining_text,
            type_result.data
        )

        # 构建解析结果
        parsed_record = ParsedRecord(
            date_start=date_result.data["start"],
            date_end=date_result.data["end"],
            record_type=type_result.data,
            hours=hours_result.data if hours_result.success else None,
            description=self._extract_description(date_result.remaining_text),
            raw_text=line,
            confidence=min(date_result.confidence, type_result.confidence)
        )

        return ParseResult(
            success=True,
            data=parsed_record,
            confidence=parsed_record.confidence,
            raw_text=line
        )

    def _extract_description(self, text: str) -> str:
        """提取描述信息"""
        # 移除已解析的部分，保留描述
        return text.strip()

    def get_errors(self) -> List[str]:
        """获取错误列表"""
        return self._errors.copy()
```

### 4.4 服务层类

```python
# src/ot_calculation/services/import_service.py

from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..parsers.pipeline import ParserPipeline
from ..repositories.record_repository import RecordRepository
from ..repositories.import_repository import ImportRepository
from ..core.models import FileImport, OTRecord
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ImportResult:
    """导入结果"""
    file_import_id: int
    total_lines: int
    success_count: int
    error_count: int
    errors: List[str]


class ImportService:
    """导入服务"""

    def __init__(
        self,
        db_session: Session,
        parser_pipeline: Optional[ParserPipeline] = None
    ):
        self.db = db_session
        self.parser = parser_pipeline or ParserPipeline()
        self.record_repo = RecordRepository(db_session)
        self.import_repo = ImportRepository(db_session)

    def import_file(self, file_path: Path, employee_id: int) -> ImportResult:
        """导入单个文件"""
        logger.info(f"开始导入文件: {file_path}")

        # 创建导入记录
        file_import = self.import_repo.create(
            filename=file_path.name,
            file_path=str(file_path),
            status="processing"
        )

        errors = []
        success_count = 0

        try:
            # 读取文件
            lines = self._read_file(file_path)
            self.import_repo.update_total_lines(file_import.id, len(lines))

            # 逐行解析
            for line_num, line in enumerate(lines, 1):
                try:
                    result = self._process_line(line, employee_id, file_import.id)
                    if result:
                        success_count += 1
                    else:
                        errors.append(f"行 {line_num}: 解析失败")
                except Exception as e:
                    errors.append(f"行 {line_num}: {str(e)}")
                    logger.error(f"处理行 {line_num} 时出错: {e}")

            # 更新状态
            status = "completed" if not errors else "partial"
            self.import_repo.update_status(
                file_import.id,
                status=status,
                success_count=success_count,
                error_count=len(errors)
            )

            logger.info(f"文件导入完成: {file_path}, 成功: {success_count}, 错误: {len(errors)}")

            return ImportResult(
                file_import_id=file_import.id,
                total_lines=len(lines),
                success_count=success_count,
                error_count=len(errors),
                errors=errors
            )

        except Exception as e:
            self.import_repo.update_status(file_import.id, status="failed")
            logger.error(f"导入文件失败: {file_path}, 错误: {e}")
            raise

    def _read_file(self, file_path: Path) -> List[str]:
        """读取文件内容"""
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    def _process_line(
        self,
        line: str,
        employee_id: int,
        file_import_id: int
    ) -> bool:
        """处理单行记录"""
        result = self.parser.parse_line(line)

        if not result.success:
            return False

        parsed = result.data

        # 创建记录
        record = OTRecord(
            employee_id=employee_id,
            file_import_id=file_import_id,
            date_start=parsed.date_start,
            date_end=parsed.date_end,
            record_type=parsed.record_type.value,
            hours=parsed.hours,
            description=parsed.description,
            raw_text=parsed.raw_text
        )

        self.record_repo.save(record)
        return True

    def import_directory(
        self,
        dir_path: Path,
        employee_id: int,
        pattern: str = "*.md"
    ) -> List[ImportResult]:
        """批量导入目录"""
        results = []
        for file_path in dir_path.glob(pattern):
            result = self.import_file(file_path, employee_id)
            results.append(result)
        return results
```

### 4.5 仓库层类

```python
# src/ot_calculation/repositories/base.py

from typing import Generic, TypeVar, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..core.models import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """仓库基类"""

    def __init__(self, db_session: Session, model_class: type[ModelType]):
        self.db = db_session
        self.model_class = model_class

    def get_by_id(self, id: int) -> Optional[ModelType]:
        """根据ID获取"""
        return self.db.get(self.model_class, id)

    def get_all(self) -> List[ModelType]:
        """获取所有"""
        stmt = select(self.model_class)
        return list(self.db.execute(stmt).scalars().all())

    def save(self, obj: ModelType) -> ModelType:
        """保存对象"""
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def save_many(self, objs: List[ModelType]) -> List[ModelType]:
        """批量保存"""
        self.db.add_all(objs)
        self.db.commit()
        return objs

    def delete(self, obj: ModelType) -> None:
        """删除对象"""
        self.db.delete(obj)
        self.db.commit()


# src/ot_calculation/repositories/record_repository.py

from datetime import date
from typing import List, Optional
from sqlalchemy import select, and_

from .base import BaseRepository
from ..core.models import OTRecord


class RecordRepository(BaseRepository[OTRecord]):
    """加班记录仓库"""

    def __init__(self, db_session):
        super().__init__(db_session, OTRecord)

    def find_by_employee(
        self,
        employee_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[OTRecord]:
        """根据员工查询记录"""
        stmt = select(OTRecord).where(OTRecord.employee_id == employee_id)

        if start_date:
            stmt = stmt.where(OTRecord.date_start >= start_date)
        if end_date:
            stmt = stmt.where(OTRecord.date_start <= end_date)

        stmt = stmt.order_by(OTRecord.date_start)
        return list(self.db.execute(stmt).scalars().all())

    def find_by_date_range(
        self,
        start_date: date,
        end_date: date,
        employee_id: Optional[int] = None
    ) -> List[OTRecord]:
        """根据日期范围查询"""
        stmt = select(OTRecord).where(
            and_(
                OTRecord.date_start >= start_date,
                OTRecord.date_end <= end_date
            )
        )

        if employee_id:
            stmt = stmt.where(OTRecord.employee_id == employee_id)

        stmt = stmt.order_by(OTRecord.date_start)
        return list(self.db.execute(stmt).scalars().all())

    def find_by_type(self, record_type: str) -> List[OTRecord]:
        """根据类型查询"""
        stmt = select(OTRecord).where(OTRecord.record_type == record_type)
        return list(self.db.execute(stmt).scalars().all())
```

---

## 5. CLI 接口设计

```python
# src/ot_calculation/interfaces/cli.py

import click
from pathlib import Path

from .commands.import_cmd import import_group
from .commands.query_cmd import query_group
from .commands.stats_cmd import stats_group


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """加班记录分析系统 CLI"""
    pass


# 注册命令组
cli.add_command(import_group)
cli.add_command(query_group)
cli.add_command(stats_group)
cli.add_command(review_group)


if __name__ == "__main__":
    cli()
```

```python
# src/ot_calculation/interfaces/commands/import_cmd.py

import click
from pathlib import Path

from ...services.import_service import ImportService
from ...repositories.database import get_session


@click.group(name="import")
def import_group():
    """导入加班记录"""
    pass


@import_group.command()
@click.option("--file", "-f", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--employee", "-e", required=True, help="员工编号")
def file(file: Path, employee: str):
    """导入单个文件"""
    with get_session() as session:
        service = ImportService(session)
        # TODO: 获取员工ID
        result = service.import_file(file, employee_id=1)
        click.echo(f"导入完成: 成功 {result.success_count}, 错误 {result.error_count}")


@import_group.command()
@click.option("--dir", "-d", type=click.Path(exists=True, file_okay=False, path_type=Path), required=True)
@click.option("--employee", "-e", required=True, help="员工编号")
@click.option("--pattern", "-p", default="*.md", help="文件匹配模式")
def directory(dir: Path, employee: str, pattern: str):
    """批量导入目录"""
    with get_session() as session:
        service = ImportService(session)
        results = service.import_directory(dir, employee_id=1, pattern=pattern)
        total_success = sum(r.success_count for r in results)
        total_error = sum(r.error_count for r in results)
        click.echo(f"批量导入完成: 成功 {total_success}, 错误 {total_error}")
```

### 4.6 逐行审批服务类

```python
# src/ot_calculation/services/review_service.py

from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from enum import Enum
from datetime import date, datetime

from ..parsers.pipeline import ParserPipeline, ParsedRecord
from ..core.models import OTRecord, FileImport
from ..core.enums import RecordType, OvertimeType
from ..utils.date_utils import get_weekday_name, is_holiday, is_adjusted_workday


class ReviewAction(Enum):
    """审批动作"""
    APPROVE = "approve"
    REVISE = "revise"
    REJECT = "reject"
    SKIP = "skip"


class ConfidenceLevel(Enum):
    """置信度级别"""
    HIGH = "high"      # >= 90%
    MEDIUM = "medium"  # 70-89%
    LOW = "low"        # < 70%


@dataclass
class ComplianceInfo:
    """合规信息"""
    weekday_name: str
    is_holiday: bool
    is_adjusted_workday: bool
    overtime_type: OvertimeType
    multiplier: float
    can_comp_off: bool
    comp_eligible_hours: float


@dataclass
class LineReviewResult:
    """单行审批结果"""
    line_number: int
    raw_text: str
    parsed_record: Optional[ParsedRecord]
    compliance_info: Optional[ComplianceInfo]
    confidence: float
    confidence_level: ConfidenceLevel
    # ⚠️ 以下余额字段仅用于参考展示，不参与系统计算
    # 系统按《劳动法》规则独立计算，不依赖文件中的"累计"声明
    running_balance_before: float  # 系统计算的上条余额（仅参考）
    running_balance_after: float   # 系统计算的当前余额（仅参考）
    stated_balance: Optional[float]  # 文件中声明的累计值（仅提取展示，不用于计算）
    balance_match: bool  # 是否匹配（仅参考，不影响保存）
    user_action: Optional[ReviewAction] = None
    revised_record: Optional[ParsedRecord] = None
    reject_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class ReviewSession:
    """审批会话"""
    file_path: Path
    employee_id: int
    employee_name: str
    total_lines: int
    current_line: int = 0
    results: List[LineReviewResult] = field(default_factory=list)
    # ⚠️ 以下字段仅用于审批会话期间的临时计算展示，不保存到数据库
    # 系统按《劳动法》规则独立计算合规余额，不依赖文件中的"累计"声明
    running_balance: float = 0.0  # 临时计算余额（仅参考，不用于系统计算）


class ReviewService:
    """逐行审批服务"""

    def __init__(self, db_session, parser_pipeline: Optional[ParserPipeline] = None):
        self.db = db_session
        self.parser = parser_pipeline or ParserPipeline()
        self._session: Optional[ReviewSession] = None

    def start_review(self, file_path: Path, employee_id: int, employee_name: str) -> ReviewSession:
        """开始审批会话"""
        lines = self._read_file(file_path)

        self._session = ReviewSession(
            file_path=file_path,
            employee_id=employee_id,
            employee_name=employee_name,
            total_lines=len(lines)
        )

        # 解析所有行，但不保存
        for line_num, line in enumerate(lines, 1):
            result = self._parse_line(line_num, line)
            self._session.results.append(result)

        return self._session

    def _read_file(self, file_path: Path) -> List[str]:
        """读取文件内容"""
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    def _parse_line(self, line_number: int, line: str) -> LineReviewResult:
        """解析单行"""
        parse_result = self.parser.parse_line(line)

        if not parse_result.success:
            return LineReviewResult(
                line_number=line_number,
                raw_text=line,
                parsed_record=None,
                compliance_info=None,
                confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
                running_balance_before=self._session.running_balance if self._session else 0,
                running_balance_after=self._session.running_balance if self._session else 0,
                stated_balance=None,
                balance_match=False,
                warnings=["解析失败"]
            )

        parsed = parse_result.data

        # 获取合规信息
        compliance = self._get_compliance_info(parsed.date_start, parsed.hours, parsed.record_type)

        # 计算置信度级别
        confidence = parse_result.confidence
        if confidence >= 0.9:
            level = ConfidenceLevel.HIGH
        elif confidence >= 0.7:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        # 提取声明的累计值（⚠️ 仅用于参考展示，不参与系统计算）
        stated_balance = self._extract_stated_balance(line)

        # 计算变化
        hours = parsed.hours or 0
        # ⚠️ 以下余额计算仅用于审批界面展示，系统按《劳动法》规则独立计算
        balance_before = self._session.running_balance if self._session else 0
        balance_after = balance_before + hours

        # ⚠️ 累计值"校验"仅作为参考提示，不影响保存逻辑
        # 因员工记录未区分加班类型（工作日/周末/法定假日），其累计方式不符合合规要求
        balance_match = True
        if stated_balance is not None:
            balance_match = abs(balance_after - stated_balance) < 0.5

        # 更新运行累计值（⚠️ 仅用于审批会话临时展示，不保存到数据库）
        if self._session:
            self._session.running_balance = balance_after

        return LineReviewResult(
            line_number=line_number,
            raw_text=line,
            parsed_record=parsed,
            compliance_info=compliance,
            confidence=confidence,
            confidence_level=level,
            running_balance_before=balance_before,
            running_balance_after=balance_after,
            stated_balance=stated_balance,
            balance_match=balance_match,
            warnings=self._generate_warnings(parsed, compliance, balance_match)
        )

    def _get_compliance_info(
        self,
        record_date: date,
        hours: Optional[float],
        record_type: RecordType
    ) -> ComplianceInfo:
        """获取合规信息"""
        weekday_name = get_weekday_name(record_date)
        holiday = is_holiday(record_date)
        adjusted = is_adjusted_workday(record_date)

        # 判定加班类型
        if holiday:
            ot_type = OvertimeType.HOLIDAY
            multiplier = 3.0
            can_comp = False
            comp_hours = 0.0
        elif record_date.weekday() >= 5 and not adjusted:
            ot_type = OvertimeType.WEEKEND
            multiplier = 2.0
            can_comp = True
            comp_hours = hours or 0
        else:
            ot_type = OvertimeType.WEEKDAY
            multiplier = 1.5
            can_comp = False
            comp_hours = 0.0

        return ComplianceInfo(
            weekday_name=weekday_name,
            is_holiday=holiday,
            is_adjusted_workday=adjusted,
            overtime_type=ot_type,
            multiplier=multiplier,
            can_comp_off=can_comp,
            comp_eligible_hours=comp_hours
        )

    def _extract_stated_balance(self, line: str) -> Optional[float]:
        """从行文本中提取声明的累计值

        ⚠️ 重要说明：此方法提取的累计值仅用于参考展示，不参与系统计算。
        因为员工记录未区分加班类型（工作日延时/周末/法定假日），其累加方式
        不符合《劳动法》合规要求。系统会独立按合规规则计算余额。
        """
        import re
        match = re.search(r'累计\s*([+-]?\d+\.?\d*)\s*小时?', line)
        if match:
            return float(match.group(1))
        return None

    def _generate_warnings(
        self,
        parsed: ParsedRecord,
        compliance: ComplianceInfo,
        balance_match: bool
    ) -> List[str]:
        """生成警告信息"""
        warnings = []

        if parsed.hours and parsed.hours > 12:
            warnings.append("加班时长超过12小时，请注意劳动法规定")

        if compliance.is_holiday:
            warnings.append("法定节假日加班，不可调休，需支付3倍工资")

        # ⚠️ 注意：balance_match 仅作为参考提示，不影响保存逻辑
        # 因为员工记录中的"累计"值未区分加班类型，不符合合规要求
        if not balance_match:
            warnings.append("声明的累计值与系统计算不一致（仅参考，不影响保存）")

        if compliance.overtime_type == OvertimeType.WEEKDAY:
            warnings.append("工作日延时加班不可调休，需支付1.5倍工资")

        return warnings

    def apply_user_action(
        self,
        line_number: int,
        action: ReviewAction,
        revised_record: Optional[ParsedRecord] = None,
        reject_reason: Optional[str] = None
    ) -> LineReviewResult:
        """应用用户决策"""
        if not self._session:
            raise ValueError("No active review session")

        result = self._session.results[line_number - 1]
        result.user_action = action

        if action == ReviewAction.REVISE and revised_record:
            result.revised_record = revised_record
            # ⚠️ 重新计算仅用于审批界面展示的临时余额，不影响系统合规计算
            old_hours = result.parsed_record.hours or 0
            new_hours = revised_record.hours or 0
            delta = new_hours - old_hours
            result.running_balance_after += delta

        elif action == ReviewAction.REJECT:
            result.reject_reason = reject_reason
            # ⚠️ 恢复仅用于展示的临时余额
            result.running_balance_after = result.running_balance_before

        return result

    def save_approved_records(self, import_id: int) -> int:
        """保存所有审批通过的记录"""
        if not self._session:
            raise ValueError("No active review session")

        saved_count = 0
        for result in self._session.results:
            if result.user_action == ReviewAction.REJECT:
                continue

            record_to_save = result.revised_record or result.parsed_record
            if not record_to_save:
                continue

            compliance = result.compliance_info

            ot_record = OTRecord(
                employee_id=self._session.employee_id,
                file_import_id=import_id,
                date_start=record_to_save.date_start,
                date_end=record_to_save.date_end,
                record_type=record_to_save.record_type.value,
                overtime_type=compliance.overtime_type.value if compliance else None,
                hours=record_to_save.hours,
                comp_eligible_hours=compliance.comp_eligible_hours if compliance else 0,
                description=record_to_save.description,
                raw_text=result.raw_text
            )

            self.db.add(ot_record)
            saved_count += 1

        self.db.commit()
        return saved_count

    def get_current_line(self) -> Optional[LineReviewResult]:
        """获取当前行"""
        if not self._session or self._session.current_line >= self._session.total_lines:
            return None
        return self._session.results[self._session.current_line]

    def next_line(self) -> Optional[LineReviewResult]:
        """前进到下一行"""
        if not self._session:
            return None

        self._session.current_line += 1
        return self.get_current_line()

    def previous_line(self) -> Optional[LineReviewResult]:
        """返回上一行"""
        if not self._session or self._session.current_line <= 0:
            return None

        self._session.current_line -= 1
        return self.get_current_line()

    def get_summary_report(self) -> Dict:
        """生成审批汇总报告"""
        if not self._session:
            return {}

        results = self._session.results

        return {
            "file": str(self._session.file_path),
            "employee": self._session.employee_name,
            "total_lines": self._session.total_lines,
            "auto_approved": len([r for r in results if r.confidence_level == ConfidenceLevel.HIGH]),
            "reviewed": len([r for r in results if r.user_action]),
            "approved": len([r for r in results if r.user_action == ReviewAction.APPROVE]),
            "revised": len([r for r in results if r.user_action == ReviewAction.REVISE]),
            "rejected": len([r for r in results if r.user_action == ReviewAction.REJECT]),
            "total_overtime_hours": sum(
                (r.revised_record or r.parsed_record).hours or 0
                for r in results
                if r.user_action != ReviewAction.REJECT and r.parsed_record
            )
        }
```

### 4.7 逐行审批CLI命令

```python
# src/ot_calculation/interfaces/commands/review_cmd.py

import click
from pathlib import Path
from typing import Optional

from ...services.review_service import (
    ReviewService, ReviewAction, ConfidenceLevel, LineReviewResult
)
from ...repositories.database import get_session
from ...utils.display import format_compliance_info, format_balance_check


@click.group(name="review")
def review_group():
    """逐行审批加班记录"""
    pass


@review_group.command()
@click.option("--file", "-f", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--employee", "-e", required=True, help="员工姓名/编号")
def interactive(file: Path, employee: str):
    """交互式逐行审批"""
    with get_session() as session:
        service = ReviewService(session)
        review_session = service.start_review(file, employee_id=1, employee_name=employee)

        click.echo(f"\n{'='*80}")
        click.echo(f"  加班记录逐行审批 - {employee}")
        click.echo(f"  文件: {file.name}")
        click.echo(f"{'='*80}\n")

        while True:
            result = service.get_current_line()
            if not result:
                break

            # 显示行详情
            _display_line_detail(result, review_session.total_lines)

            # 根据置信度决定交互方式
            if result.confidence_level == ConfidenceLevel.HIGH and not result.warnings:
                action = _handle_auto_approve(service, result)
            else:
                action = _handle_interactive_review(service, result)

            if action == "quit":
                break

        # 生成报告
        report = service.get_summary_report()
        _display_summary_report(report)


def _display_line_detail(result: LineReviewResult, total_lines: int):
    """显示行详情"""
    click.echo(f"\n{'─'*80}")
    click.echo(f"  行号: {result.line_number}/{total_lines}  │  置信度: {result.confidence*100:.0f}%")
    click.echo(f"{'─'*80}")

    # 原始文本
    click.echo(f"\n  📄 原始文本:")
    click.echo(f"     {result.raw_text}")

    if not result.parsed_record:
        click.echo(f"\n  ❌ 解析失败")
        return

    parsed = result.parsed_record
    compliance = result.compliance_info

    # 日期信息
    click.echo(f"\n  📅 日期信息:")
    click.echo(f"     日期: {parsed.date_start}")
    if compliance:
        click.echo(f"     星期: {compliance.weekday_name}")
        if compliance.is_holiday:
            click.echo(f"     ⚠️  法定节假日")
        if compliance.is_adjusted_workday:
            click.echo(f"     调休上班日")

    # 记录类型和时长
    click.echo(f"\n  📝 记录:")
    click.echo(f"     类型: {parsed.record_type.value}")
    click.echo(f"     时长: {parsed.hours} 小时")
    if parsed.description:
        click.echo(f"     描述: {parsed.description}")

    # 合规信息
    if compliance:
        click.echo(f"\n  ⚖️  合规判定:")
        click.echo(f"     加班类型: {compliance.overtime_type.value}")
        click.echo(f"     工资倍数: {compliance.multiplier}x")
        click.echo(f"     可调休: {'✓ 是' if compliance.can_comp_off else '✗ 否'}")
        if compliance.can_comp_off:
            click.echo(f"     可调休时长: {compliance.comp_eligible_hours} 小时")

    # ⚠️ 累计值展示（仅参考，不参与系统计算）
    click.echo(f"\n  🔢 累计值（仅供参考）:")
    click.echo(f"     会话累计(之前): {result.running_balance_before} 小时")
    click.echo(f"     本次变化: +{parsed.hours} 小时")
    click.echo(f"     会话累计(之后): {result.running_balance_after} 小时")
    if result.stated_balance is not None:
        click.echo(f"     声明累计: {result.stated_balance} 小时")
        status = "✓ 匹配" if result.balance_match else "✗ 不匹配"
        click.echo(f"     校验结果: {status}")

    # 警告
    if result.warnings:
        click.echo(f"\n  ⚠️  警告:")
        for warning in result.warnings:
            click.echo(f"     • {warning}")


def _handle_auto_approve(service: ReviewService, result: LineReviewResult) -> str:
    """处理自动通过"""
    click.echo(f"\n  ✓ 高置信度，系统自动通过")

    # 询问用户是否确认
    choice = click.prompt(
        "  操作: [Enter]确认通过 [e]编辑 [r]驳回 [b]返回上条 [q]保存退出",
        default="",
        show_default=False
    )

    if choice.lower() == "q":
        return "quit"
    elif choice.lower() == "b":
        service.previous_line()
        return "back"
    elif choice.lower() == "r":
        reason = click.prompt("  驳回原因")
        service.apply_user_action(result.line_number, ReviewAction.REJECT, reject_reason=reason)
        service.next_line()
        return "reject"
    elif choice.lower() == "e":
        return _handle_edit(service, result)
    else:
        service.apply_user_action(result.line_number, ReviewAction.APPROVE)
        service.next_line()
        return "approve"


def _handle_interactive_review(service: ReviewService, result: LineReviewResult) -> str:
    """处理交互式审批"""
    click.echo(f"\n  ⚠️  需要人工确认")

    choice = click.prompt(
        "  操作: [p]通过 [e]编辑 [r]驳回 [s]跳过 [b]返回上条 [q]保存退出",
        type=click.Choice(["p", "e", "r", "s", "b", "q"], case_sensitive=False),
        default="p"
    )

    if choice.lower() == "q":
        return "quit"
    elif choice.lower() == "b":
        service.previous_line()
        return "back"
    elif choice.lower() == "s":
        service.next_line()
        return "skip"
    elif choice.lower() == "r":
        reason = click.prompt("  驳回原因")
        service.apply_user_action(result.line_number, ReviewAction.REJECT, reject_reason=reason)
        service.next_line()
        return "reject"
    elif choice.lower() == "e":
        return _handle_edit(service, result)
    else:
        service.apply_user_action(result.line_number, ReviewAction.APPROVE)
        service.next_line()
        return "approve"


def _handle_edit(service: ReviewService, result: LineReviewResult) -> str:
    """处理编辑"""
    click.echo(f"\n  ✏️  编辑模式")

    parsed = result.parsed_record
    if not parsed:
        click.echo("  解析失败，无法编辑")
        return "skip"

    # 询问修改项
    new_hours = click.prompt(f"  时长 [{parsed.hours}]", default=parsed.hours, type=float)
    new_type = click.prompt(
        f"  类型 [{parsed.record_type.value}]",
        default=parsed.record_type.value,
        type=click.Choice(["overtime", "leave", "comp_off", "adjustment"])
    )

    # 创建修订记录
    from ...parsers.pipeline import ParsedRecord
    from ...core.enums import RecordType

    revised = ParsedRecord(
        date_start=parsed.date_start,
        date_end=parsed.date_end,
        record_type=RecordType(new_type),
        hours=new_hours,
        description=parsed.description,
        raw_text=parsed.raw_text
    )

    service.apply_user_action(result.line_number, ReviewAction.REVISE, revised_record=revised)
    service.next_line()
    return "revise"


def _display_summary_report(report: dict):
    """显示汇总报告"""
    click.echo(f"\n{'='*80}")
    click.echo(f"  审批完成报告")
    click.echo(f"{'='*80}")
    click.echo(f"\n  文件: {report.get('file')}")
    click.echo(f"  员工: {report.get('employee')}")
    click.echo(f"\n  统计:")
    click.echo(f"     总记录数: {report.get('total_lines')}")
    click.echo(f"     自动通过: {report.get('auto_approved')}")
    click.echo(f"     人工审批: {report.get('reviewed')}")
    click.echo(f"     - 通过: {report.get('approved')}")
    click.echo(f"     - 修订: {report.get('revised')}")
    click.echo(f"     - 驳回: {report.get('rejected')}")
    click.echo(f"\n  加班总时长: {report.get('total_overtime_hours', 0)} 小时")
    click.echo(f"{'='*80}\n")
```

---

## 6. 配置管理

```python
# src/ot_calculation/config/settings.py

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    # 数据库配置
    database_url: str = "sqlite:///./ot_calculation.db"
    database_echo: bool = False

    # 日志配置
    log_level: str = "INFO"
    log_format: str = "json"

    # 解析配置
    config_dir: Path = Path(__file__).parent
    rules_file: Path = config_dir / "rules.yaml"

    # 导入配置
    batch_size: int = 100
    max_workers: int = 4

    @property
    def database_path(self) -> Path:
        """获取数据库路径"""
        if self.database_url.startswith("sqlite:///"):
            return Path(self.database_url.replace("sqlite:///", ""))
        return Path("./ot_calculation.db")


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
```

---

## 7. 日志配置

```python
# src/ot_calculation/utils/logger.py

import logging
import sys
from functools import lru_cache

import structlog

from ..config.settings import get_settings


def configure_logging():
    """配置日志"""
    settings = get_settings()

    # 配置标准库日志
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    # 配置 structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.log_format == "json"
            else structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


@lru_cache()
def get_logger(name: str):
    """获取日志记录器"""
    return structlog.get_logger(name)
```

---

## 8. 依赖管理

```toml
# pyproject.toml

[project]
name = "ot-calculation"
version = "1.0.0"
description = "加班记录分析系统"
readme = "README.md"
requires-python = ">=3.9"
dependencies = [
    "sqlalchemy>=2.0.0",
    "alembic>=1.12.0",
    "click>=8.1.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "structlog>=23.0.0",
    "pyyaml>=6.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.21.0",
    "mypy>=1.5.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "factory-boy>=3.3.0",
]

[project.scripts]
otcalc = "ot_calculation.interfaces.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.black]
line-length = 88
target-version = ["py39"]

[tool.ruff]
line-length = 88
select = ["E", "F", "I", "N", "W"]

[tool.mypy]
python_version = "3.9"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --cov=src --cov-report=term-missing"
```

---

## 9. 开发工作流

### 9.1 Makefile 命令

```makefile
# Makefile

.PHONY: install test lint format migrate run clean

install:
	pip install -e ".[dev]"

test:
	pytest

test-cov:
	pytest --cov=src --cov-report=html

lint:
	ruff check src tests
	mypy src

format:
	black src tests
	ruff check --fix src tests

migrate:
	alembic upgrade head

migrate-create:
	alembic revision --autogenerate -m "$(msg)"

run:
	python -m ot_calculation

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage

db-init:
	python scripts/init_db.py

db-backup:
	python scripts/backup_db.py
```

---

## 10. 部署架构

### 10.1 单机部署

```
┌─────────────────────────────────────┐
│           用户机器                   │
│  ┌─────────────────────────────┐   │
│  │    ot-calculation CLI       │   │
│  └─────────────────────────────┘   │
│              │                      │
│  ┌─────────────────────────────┐   │
│  │    SQLite Database          │   │
│  │    (ot_calculation.db)      │   │
│  └─────────────────────────────┘   │
│              │                      │
│  ┌─────────────────────────────┐   │
│  │    Markdown Files           │   │
│  │    (/data/ot_records/)      │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

### 10.2 容器化部署（未来扩展）

```dockerfile
# Dockerfile

FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY pyproject.toml .
RUN pip install -e "."

# 复制代码
COPY src/ ./src/

# 设置环境变量
ENV DATABASE_URL=sqlite:///data/ot_calculation.db
ENV LOG_LEVEL=INFO

# 挂载数据卷
VOLUME ["/data"]

ENTRYPOINT ["otcalc"]
CMD ["--help"]
```
