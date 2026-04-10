# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**加班记录分析系统 (Overtime Calculation System)** - A Python-based system for parsing Markdown overtime records, calculating salaries according to Chinese Labor Law, and managing compensatory time off.

**Key Features:**
- Parse Markdown overtime records using AI (Volces/火山方舟 API)
- Calculate overtime pay at 1.5x/2x/3x rates per Labor Law
- Track compensatory time off (调休) with FIFO expiration
- Manage national holidays and adjusted workdays
- Web interface for record import and review

## Architecture

### High-Level Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Application Layer                                          │
│  ├── Web Interface (Flask) - src/web/                      │
│  │   ├── routes/ - Blueprints for dashboard, employees,    │
│  │   │             records, holidays, reports, review      │
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
│  └── storage_service.py - Database operations              │
├─────────────────────────────────────────────────────────────┤
│  Parser Layer - src/parsers/                               │
│  ├── date_parser.py - Date extraction (7+ formats)         │
│  ├── type_parser.py - Record classification                │
│  ├── hours_parser.py - Duration extraction                 │
│  └── holiday_notification_parser.py - Gov notice parsing   │
├─────────────────────────────────────────────────────────────┤
│  Data Layer                                                │
│  ├── src/db/schema.py - SQLite schema (7 tables)           │
│  └── data/overtime.db - SQLite database file               │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema (7 Tables)

**Core Tables:**
- `employees` - Employee master data
- `overtime_records` - Overtime entries (type: weekday_morning/lunch/evening/weekend/holiday)
- `leave_records` - Leave entries (type: personal/sick/annual/other)
- `comp_off_balances` - Compensatory time earned (only from weekend overtime)
- `comp_off_usage_records` - Comp time usage with FIFO deduction
- `holiday_config` - Annual holiday calendar and adjusted workdays (调休上班日)
- `import_sessions` / `import_records` - Import session tracking

**Constraints:**
- All time values stored as positive integers (hours, minutes)
- Weekday overtime (1.5x) cannot be converted to comp time
- Only weekend overtime (2x) generates comp time balance

### AI Parsing Architecture

The system uses **AI-only parsing** with Volces (火山方舟) API. Local parsers exist in `src/parsers/` but are **not used as fallback** in the web import flow.

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
- Batch size: 1 line per request
- Max lines: 5 lines per import

**AI returns JSON with:**
- `type`: overtime/leave/comp_off/unknown
- `subtype`: weekday_evening/weekend/personal/sick/etc.
- `hours`: float value
- `confidence`: 0.0-1.0 score

### Web Import Flow

The import uses a 3-step session-based flow:

1. **Upload** (`/records/import/`) - User selects employee and uploads Markdown file
2. **Preview** (`/records/import/preview/`) - AI-parsed records shown with confidence levels; user can edit/delete lines
3. **Confirm** (`/records/import/confirm/`) - Selected records saved to DB

Progress is tracked via AJAX polling to `/records/import/progress/`.

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
# The CLI module is at src/cli/commands.py
# Note: import_file is currently a stub and needs to be wired to parsers
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
```

## Development Guidelines

### Code Organization

- **Parsers** (`src/parsers/`): Pure functions, no side effects, return typed structures
- **Services** (`src/services/`): Business logic, database operations through repositories
- **Web Routes** (`src/web/routes/`): Flask blueprints, form handling, template rendering
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
- **Status**: Pending implementation
- **Scope**: Add a ranking page under `/reports/` showing monthly/yearly overtime hours per employee, sorted by total hours
- **Decision**: Implement in web interface only (2026-04-10)

### CLI Single-File Import
- **Status**: Pending implementation
- **Scope**: Wire `src/cli/commands.py::import_file()` to actual parser and database storage
- **Decision**: Support single-file import via CLI; directory batch import remains out of scope (2026-04-10)

### Simplified Comp-Off Approval Workflow
- **Status**: Pending implementation
- **Scope**: Add `pending` / `approved` states to comp-off usage; only deduct balance after approval
- **Decision**: Implement minimal approval flow without multi-role permissions (2026-04-10)

### Dependency Management
- **Status**: Pending implementation
- **Scope**: Add `requirements.txt` listing actual third-party dependencies (Flask, pytest, playwright, requests, openai)
- **Decision**: Create `requirements.txt` (2026-04-10)

### Documentation Table Name Alignment
- **Status**: Pending implementation
- **Scope**: Update PRD and design docs to use actual table names (`holiday_config`, `import_sessions`, `import_records`)
- **Decision**: Synchronize documentation with code (2026-04-10)

## Explicitly Out of Scope

The following features were confirmed as **not implemented** (2026-04-10):
- Data export (Excel, PDF, CSV) — all deferred to future versions
- Department-based query/filtering — marked as obsolete
- AI offline fallback to local parsers — system remains AI-only

## Important Notes

- **AI Parsing is Primary and Exclusive**: The system relies entirely on Volces AI API for web import. Local parsers exist but are not used as fallback.
- **Hardcoded API Key**: The AI service has hardcoded credentials in `src/services/ai_parser_service.py`
- **Session-based Import**: Web import uses Flask sessions to store preview data between steps
- **Requirements File Pending**: A `requirements.txt` will be added; until then, check imports directly when installing dependencies
