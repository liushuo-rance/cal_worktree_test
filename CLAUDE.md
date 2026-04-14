# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**加班记录分析系统 (Overtime Calculation System)** - A Python-based system for parsing Markdown overtime records, calculating salaries according to Chinese Labor Law, and managing compensatory time off.

**Key Features:**
- Parse Markdown overtime records using AI (Volces/火山方舟 API) with SSE streaming
- Retain local parsers (date/hours/type) as fallback when AI is unavailable
- Calculate overtime pay at 1.5x/2x/3x rates per Labor Law
- Track compensatory time off (调休) with FIFO expiration
- Manage national holidays and adjusted workdays
- Web interface for record import, review, search, import sessions, and comp-off approval

## Architecture

### High-Level Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Application Layer                                          │
│  ├── Web Interface (Flask) - src/web/                      │
│  │   ├── routes/ - Blueprints for dashboard, employees,    │
│  │   │             records, holidays, reports, review, api │
│  │   ├── templates/ - Jinja2 HTML templates                │
│  │   ├── static/ - CSS, JS assets                         │
│  │   └── utils.py - DB connection helper                  │
│  └── CLI - src/cli/commands.py                             │
├─────────────────────────────────────────────────────────────┤
│  Service Layer - src/services/                             │
│  ├── ai_parser_service.py - AI parsing (火山方舟 API)      │
│  ├── overtime_service.py - Overtime statistics             │
│  ├── salary_service.py - Salary calculation (1.5x/2x/3x)   │
│  ├── comp_off_service.py - Comp time management (FIFO)     │
│  ├── holiday_service.py - National holidays management     │
│  ├── parse_result_processor.py - Confidence scoring        │
│  ├── review_service.py - Line-by-line approval workflow    │
│  ├── report_service.py - Report generation                 │
│  ├── storage_service.py - Database operations              │
│  ├── import_service.py - CSV/Excel file import & normalize │
│  └── export_service.py - CSV/Excel/PDF export              │
├─────────────────────────────────────────────────────────────┤
│  Parser Layer - src/parsers/                               │
│  ├── date_parser.py - Date extraction (7+ formats)         │
│  ├── type_parser.py - Record classification                │
│  ├── hours_parser.py - Duration extraction                 │
│  └── holiday_notification_parser.py - Gov notice parsing   │
├─────────────────────────────────────────────────────────────┤
│  Data Layer                                                │
│  ├── src/db/schema.py - SQLite schema (8 tables + views)   │
│  └── data/overtime.db - SQLite database file               │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema (8 Tables + Views)

**Core Tables:**
- `employees` - Employee master data
- `overtime_records` - Overtime entries (type: weekday_morning/lunch/evening/weekend/holiday)
- `leave_records` - Leave entries (type: personal/sick/annual/other)
- `comp_off_balances` - Compensatory time earned (only from weekend overtime). Uses `total_minutes` / `remaining_minutes` (migrated from old hour columns).
- `comp_off_usage_records` - Comp time usage with `balance_id`, `used_minutes`, `status` (`pending`/`approved`/`rejected`), and `source_import_id`
- `holiday_config` - Annual holiday calendar and adjusted workdays (调休上班日)
- `import_sessions` / `import_records` - Import session tracking (`import_sessions` includes `employee_id`)
- `review_queue` - Review/approval queue for parsed import records

**Views:**
- `v_employee_overtime_summary` - Monthly aggregated overtime by employee/type
- `v_employee_comp_off_balance` - Active comp_off remaining minutes per employee

**Migrations:**
- `init_database()` automatically runs `_migrate_import_sessions()`, `_migrate_comp_off_balances()`, and `_migrate_comp_off_usage_records()` to upgrade legacy schema data.

**Constraints:**
- All time values stored as positive integers (hours, minutes)
- Weekday overtime (1.5x) cannot be converted to comp time
- Only weekend overtime (2x) generates comp time balance

### AI Parsing Architecture

The primary parsing path uses Volces (火山方舟) API with SSE streaming (`/records/import/stream/`). Local parsers (`date_parser.py`, `hours_parser.py`, `type_parser.py`) are retained as fallback when AI is unavailable. After AI parsing, `records.py` applies holiday-based overtime type auto-correction via `get_date_type()`.

```python
# src/services/ai_parser_service.py
AIParserService.parse_lines(text_lines: List[str]) -> Dict[
    'records': [...],    # Parsed records
    'prompt': str,       # Full prompt sent to AI
    'response': str,     # Raw AI response
    'error': Optional[str]
]
```

**API Configuration (Hardcoded):**
- Base URL: `https://ark.cn-beijing.volces.com/api/v3`
- Model: `ep-20260331092634-wfnm8`
- Batch size: 3 lines per request
- Max lines: 5 lines per import

**AI returns JSON with:**
- `type`: overtime/leave/comp_off/unknown
- `subtype`: weekday_evening/weekend/personal/sick/etc.
- `hours`: float value
- `confidence`: 0.0-1.0 score

### Web Import Flow

The import uses a 3-step session-based flow with SSE streaming:

1. **Upload** (`/records/import/`) - User pastes Markdown text or drags-and-drops a file into the editor
2. **Preview** (`/records/import/preview/`) - AI-parsed records are shown with confidence levels, anomaly warnings, and duplicate detection; user can edit/delete lines and choose skip/overwrite for duplicates
3. **Confirm** (`/records/import/confirm/`) - Selected records saved to DB; low-confidence records are sent to `review_queue`

Progress is delivered via **Server-Sent Events** to `/records/import/stream/`. If AI parsing fails, the system falls back to the local parser (`parse_record_line`). Holiday-based overtime type auto-correction is applied after each batch.

## Common Commands

### Running Tests

```bash
# Run all tests
python3 -m pytest tests/

# Run with coverage
python3 -m pytest tests/ --cov=src --cov-report=term-missing

# Run specific test file
python3 -m pytest tests/test_date_parser.py -v

# Run specific test class
python3 -m pytest tests/test_date_parser.py::TestDateParserSingleDate -v

# Run specific test method
python3 -m pytest tests/test_date_parser.py::TestDateParserSingleDate::test_standard_format -v

# Run visual regression tests
python3 -m pytest tests/visual/ -v

# Update baseline screenshots
python3 -m pytest tests/visual/ --update-snapshots
```

### Running the Web Application

```bash
# Start Flask web server on port 5001
python3 run_web.py

# Access at http://127.0.0.1:5001
```

### CLI Operations

```bash
# Spreadsheet import (CSV/Excel)
python3 -m src.cli.commands import_excel_csv --file <path> --employee-id EMP001 --format csv

# Data export (csv/xlsx/pdf)
python3 -m src.cli.commands export --type overtime --employee-id EMP001 --format csv --output report.csv --year 2026 --month 4

# Report generation
python3 -m src.cli.commands report --employee-id EMP001 --year 2026 --month 4
```

### Database Operations

```bash
# Database location
data/overtime.db

# Initialize schema (done automatically on first run)
# See src/db/schema.py::init_database()
```

### Key File Locations

```
src/
├── parsers/           # Text parsing modules
├── services/          # Business logic
├── web/               # Flask application
│   ├── routes/        # URL handlers
│   ├── templates/     # HTML templates
│   └── static/        # CSS/JS assets
├── db/schema.py       # Database schema
└── utils/             # Utilities (time_utils, lunar_converter)

tests/                 # pytest test files
data/                  # SQLite database
employee_ot_record/    # Sample MD files for testing
docs/                  # Documentation (20+ markdown files)

### New Key Files (Added 2026-04-13)
- `src/web/routes/api.py` — REST API blueprint (`/api/v1/records/import/`)
- `src/services/import_service.py` — CSV/Excel file reading and row normalization
- `src/services/export_service.py` — CSV/Excel/PDF export service
- `tests/test_api_routes.py` — API route tests
- `tests/test_export_service.py` — Export service tests
```

## Development Guidelines

### Code Organization

- **Parsers** (`src/parsers/`): Pure functions, no side effects, return typed structures
- **Services** (`src/services/`): Business logic, database operations through repositories
- **Web Routes** (`src/web/routes/`): Flask blueprints, form handling, template rendering
- **API Routes** (`src/web/routes/api.py`): REST API endpoints for programmatic access
- **Tests** (`tests/`): Mirror src structure, use pytest fixtures from `tests/fixtures/`

### Import Paths in Web Routes

Some web route files use `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))` to enable relative imports from `src/` (e.g., `from services.report_service import ...`). When adding new routes, follow the existing pattern in the file you are editing.

### Key Business Rules

1. **Overtime Types & Rates:**
   - Weekday (工作日延时): 1.5x pay, NO comp time
   - Weekend (周末): 2.0x pay OR comp time
   - Holiday (法定节假日): 3.0x pay, NO comp time

2. **Comp Time (调休) Rules:**
   - Only earned from weekend overtime
   - FIFO deduction when used
   - 6-month expiration

3. **Work Schedule:**
   - Morning: 08:30-12:00 (3.5h)
   - Lunch break: 12:00-13:00
   - Afternoon: 13:00-17:30 (4.5h)
   - Standard day: 8 hours

### Testing

- Tests use `src.` prefix for imports (e.g., `from src.parsers.date_parser import parse_date`)
- Fixtures in `tests/fixtures/e2e_test_data.py`
- Coverage reports generated in `htmlcov/`

### Visual Regression Testing

Visual tests use Playwright for browser automation:

```bash
# Run all visual tests
python3 -m pytest tests/visual/ -v

# Run with headed browser (visible)
python3 -m pytest tests/visual/ --headed

# Update baseline screenshots
python3 -m pytest tests/visual/ --update-snapshots
```

**Visual Test Structure:**
- `tests/visual/test_critical_pages.py` - Page-level tests (dashboard, employees, import, etc.)
- `tests/visual/test_components.py` - Component-level tests (buttons, forms, tables)
- `tests/visual/screenshots/` - Generated screenshots
- `tests/visual/conftest.py` - Fixtures for page, mobile_page, tablet_page

**Test Fixtures:**
- `page` - Desktop viewport (1440x900)
- `mobile_page` - Mobile viewport (375x667)
- `tablet_page` - Tablet viewport (768x1024)

## Documentation

Comprehensive docs in `docs/`:
- `01-prd.md` - Product requirements
- `02-system-architecture.md` - System architecture
- `03-data-parsing-strategy.md` - AI parsing strategy (v2.0)
- `04-database-design.md` - Database design (note: table names may differ from actual code)
- `06-technical-implementation.md` - Technical details
- `09-compliance-rules.md` - Labor law compliance
- `20-record-import-feature.md` - Import feature design
- `24-env-config.md` - Environment variables configuration
- `25-api-reference.md` - Web API endpoints reference
- `26-contributing.md` - Development environment setup guide
- `27-runbook.md` - Operations manual
- `28-cli-reference.md` - CLI commands reference

## Active Requirements Record

The following requirements have been confirmed and are pending implementation:

### Employee Overtime Ranking (Web)
- **Status**: Implemented
- **Scope**: Ranking page under `/reports/ranking/` showing monthly/yearly overtime hours per employee, sorted by total hours
- **Decision**: Implemented in web interface (2026-04-10)

### CLI Single-File Import
- **Status**: Implemented
- **Scope**: `src/cli/commands.py` provides `import_excel_csv` for CSV/Excel file import and `export` for CSV/Excel/PDF export. Directory batch import remains out of scope.
- **Decision**: Implemented via `import_excel_csv` and `export` CLI commands (2026-04-13)

### Simplified Comp-Off Approval Workflow
- **Status**: Implemented
- **Scope**: `pending` / `approved` / `rejected` states on `comp_off_usage_records`; balance is only deducted after approval
- **Decision**: Minimal approval flow without multi-role permissions (2026-04-10)

### Dependency Management
- **Status**: Implemented
- **Scope**: `requirements.txt` lists Flask, Flask-Session, openai, requests, pytest, pytest-cov, pytest-playwright, playwright
- **Decision**: `requirements.txt` created (2026-04-10)

### FR-011: CSV/Excel Import (Web + Service + CLI)
- **Status**: Implemented
- **Scope**: `import_service.py` supports reading `.csv`/`.xlsx`/`.xls` and normalizing rows. Web import page (`/records/import/`) accepts spreadsheet uploads and applies holiday correction + duplicate detection. CLI provides `import_excel_csv` command.
- **Files**: `src/services/import_service.py`, `src/web/routes/records.py`, `src/web/templates/import.html`, `src/cli/commands.py`
- **Decision**: Implemented (2026-04-13)

### FR-012: CSV/Excel/PDF Export (Service Layer + Web + CLI)
- **Status**: Implemented
- **Scope**: `export_service.py` exposes `export_to_csv()`, `export_to_excel()`, and `export_report_to_pdf()` with Chinese font fallback for reportlab. Web report pages (`/reports/*/export/?format=csv|xlsx|pdf`) and CLI `export` command are wired up.
- **Files**: `src/services/export_service.py`, `src/web/routes/reports.py`, `src/cli/commands.py`, `tests/test_export_service.py`
- **Decision**: Implemented (2026-04-13)

### FR-013: REST API JSON Batch Import
- **Status**: Implemented
- **Scope**: New blueprint `api.py` under `/api/v1` provides `POST /api/v1/records/import/`. Validates input, reuses `normalize_import_rows`, applies holiday correction, and calls `store_batch_records()`.
- **Files**: `src/web/routes/api.py`, `tests/test_api_routes.py`, `src/web/__init__.py`
- **Decision**: Implemented (2026-04-13)

### FR-014: Employee Soft Delete with Employment Status Tracking
- **Status**: Pending implementation
- **Scope**: Add soft-delete for employees. When an employee is deleted, mark the employee as inactive and update all related `overtime_records` to set `employment_status = 'inactive'`. Web UI needs a delete button on the employee list/detail. CLI needs a `delete_employee` command.
- **Design decisions**:
  - `employees` table: add `is_active` INTEGER DEFAULT 1
  - `overtime_records` table: add `employment_status` TEXT DEFAULT 'active' CHECK(employment_status IN ('active', 'inactive'))
  - Deletion is a soft delete (set `is_active = 0`) + cascade update to related overtime records
  - Employee list should still show inactive employees with a visual indicator
- **Files**: `src/db/schema.py`, `src/web/routes/employees.py`, `src/web/templates/employees.html`, `src/web/templates/employee_detail.html`, `src/cli/commands.py`, related tests
- **Decision**: Implement soft delete to preserve historical data integrity (2026-04-13)

### Documentation Table Name Alignment
- **Status**: Pending implementation
- **Scope**: Update PRD and design docs to use actual table names (`holiday_config`, `import_sessions`, `import_records`)
- **Decision**: Synchronize documentation with code (2026-04-10)

## Explicitly Out of Scope

The following features are **not planned**:
- Department-based query/filtering — marked as obsolete

## Important Notes

- **AI Parsing is Primary; Local Parsers are Fallback**: The system prefers Volces AI API for web import, but falls back to local regex-based parsers if AI fails.
- **Hardcoded API Key**: The AI service has hardcoded credentials in `src/services/ai_parser_service.py`
- **Session-based Import**: Web import uses Flask sessions to store preview data between steps
- **Dependencies**: `requirements.txt` is present at the repo root with Flask, Flask-Session, openai, requests, pytest, pytest-cov, pytest-playwright, playwright
