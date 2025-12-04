# Implementation Plan: Multi-Tenant Web Application Rewrite

**Branch**: `001-multitenant-rewrite` | **Date**: 2025-12-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-multitenant-rewrite/spec.md`

## Summary

Complete architectural rewrite of DinkyDash from single-family, config-file-based Raspberry Pi dashboard to multi-tenant web application. Core functionality (recurring task rotations, countdown calculations) remains unchanged but delivered through database-backed, authenticated web interface. System must support both SQLite (Pi deployment) and PostgreSQL (cloud deployment) from same codebase using Flask with server-side rendering, HTMX for progressive enhancement, and Flask-Login for authentication.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Flask 3.0+, SQLAlchemy 2.0+, Flask-Login, Flask-WTF (CSRF), Flask-Migrate (Alembic), Werkzeug, HTMX 1.9+ (CDN), Pillow (image processing)
**Storage**: SQLite 3.x (Pi/local), PostgreSQL 14+ (cloud), file storage for uploaded images
**Testing**: pytest, pytest-flask, coverage
**Target Platform**: Raspberry Pi 4+ (Raspbian/Ubuntu), Linux server (cloud), macOS/Linux (development)
**Project Type**: Web application (server-side rendering)
**Performance Goals**: <3s dashboard page load, support 50+ concurrent families, 30s polling without degradation
**Constraints**: Pi memory <512MB for app process, works without JavaScript (graceful degradation), tenant isolation enforced at query level
**Scale/Scope**: Target 50-100 families initially, 2-10 dashboards per family, 10-20 tasks/countdowns per dashboard

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Database-First Design
- ✅ **PASS**: SQLite and PostgreSQL support via SQLAlchemy ORM
- ✅ **PASS**: Migrations managed by Flask-Migrate (Alembic wrapper)
- ✅ **PASS**: No runtime dependence on config files (config.yaml eliminated)
- **Validation**: All entities (Family, User, Dashboard, Task, Countdown) stored in relational schema

### Principle II: Multi-Tenancy & Authentication
- ✅ **PASS**: Flask-Login provides session management with 30min timeout
- ✅ **PASS**: tenant_id on all data tables, query filters enforced
- ✅ **PASS**: CSRF protection via Flask-WTF on all state-changing forms
- ✅ **PASS**: Password hashing via Werkzeug (bcrypt-based)
- **Validation**: Row-level tenant isolation, session bound to tenant context

### Principle III: Traditional Web Architecture
- ✅ **PASS**: Jinja2 templates for all UI rendering (server-side)
- ✅ **PASS**: HTMX for progressive enhancement (polling), not required for core functionality
- ✅ **PASS**: Meta refresh fallback when JavaScript disabled
- ✅ **PASS**: No SPA framework, no client-side routing
- **Validation**: Application fully functional with JS disabled except polling

### Principle IV: Simplicity Over Features
- ✅ **PASS**: Flask + SQLAlchemy is standard Python web stack
- ✅ **PASS**: HTMX (14KB) is only non-essential dependency for UX enhancement
- ✅ **PASS**: Direct image upload pattern (no complex image library management)
- ⚠️ **REVIEW**: 7 user stories - ensure implementation stays focused on MVP
- **Justification**: Multi-tenancy complexity necessary for core use case (multiple families)

### Principle V: Living Documentation
- ✅ **PASS**: Migration files document schema evolution
- ✅ **PASS**: This plan documents architecture decisions
- ✅ **PASS**: quickstart.md covers both SQLite and PostgreSQL setup
- ✅ **PASS**: CLAUDE.md updated with new architecture (v2.0.0)

### Data & Privacy Compliance
- ✅ **PASS**: tenant_id filter on all queries (SQLAlchemy query events or base model)
- ✅ **PASS**: Werkzeug password hashing (bcrypt)
- ✅ **PASS**: Image uploads validated (type, size) and stored with tenant-scoped paths
- ✅ **PASS**: No third-party analytics

### Deployment & Operations Compliance
- ✅ **PASS**: SQLite mode for Pi (single-file DB)
- ✅ **PASS**: PostgreSQL mode for cloud
- ✅ **PASS**: Environment-based config (same codebase)
- ✅ **PASS**: Migrations apply on startup (Pi) or via command (cloud)
- ✅ **PASS**: Backup strategies documented in quickstart.md (SQLite + PostgreSQL)

### Testing Standards Compliance
- ✅ **PASS**: pytest for test framework
- ⚠️ **TODO**: Verify tenant isolation in integration tests
- ⚠️ **TODO**: Test auth flows (login, logout, session)
- ⚠️ **TODO**: Test migrations on both SQLite and PostgreSQL

### Security Review Compliance
- ✅ **PASS**: SQLAlchemy ORM prevents SQL injection
- ✅ **PASS**: Flask-WTF provides CSRF tokens
- ✅ **PASS**: Werkzeug provides password hashing
- ✅ **PASS**: WTForms for input validation
- ⚠️ **TODO**: Implement secure password reset with time-limited tokens

**GATE STATUS**: ✅ PASS - Phase 1 Design Complete

**Phase 1 Re-Evaluation Notes**:
- All constitutional principles remain satisfied after Phase 1 design
- Design artifacts generated:
  - ✅ research.md (technology decisions and patterns)
  - ✅ data-model.md (comprehensive database schema)
  - ✅ contracts/routes.md (Flask route specifications)
  - ✅ contracts/forms.md (WTForms specifications)
  - ✅ contracts/templates.md (Jinja2 template specifications)
  - ✅ quickstart.md (deployment guide for SQLite and PostgreSQL)
  - ✅ CLAUDE.md (updated with v2.0.0 architecture)
- TODOs remain for Phase 2 (implementation):
  - Implement tenant isolation tests (integration test suite)
  - Implement auth flow tests (login, logout, session management)
  - Test migrations on both SQLite and PostgreSQL
  - Implement secure password reset (post-MVP feature)
- Focus on MVP to honor Simplicity principle maintained

## Project Structure

### Documentation (this feature)

```text
specs/001-multitenant-rewrite/
├── plan.md              # This file
├── research.md          # Phase 0: Technology decisions and patterns
├── data-model.md        # Phase 1: Database schema details
├── quickstart.md        # Phase 1: Setup and deployment guide
└── contracts/           # Phase 1: API/UI specifications
    ├── routes.md        # Flask route specifications
    ├── forms.md         # WTForms specifications
    └── templates.md     # Jinja2 template specifications
```

### Source Code (repository root)

```text
dinkydash/                      # Main application package
├── __init__.py                 # Flask app factory
├── models/                     # SQLAlchemy models
│   ├── __init__.py
│   ├── family.py               # Family/Tenant model
│   ├── user.py                 # User model with auth
│   ├── dashboard.py            # Dashboard model
│   ├── task.py                 # Recurring task model
│   └── countdown.py            # Countdown event model
├── routes/                     # Flask blueprints
│   ├── __init__.py
│   ├── auth.py                 # Registration, login, logout
│   ├── dashboard.py            # Dashboard viewing (polling endpoint)
│   └── admin.py                # Task/countdown/dashboard management
├── forms/                      # WTForms definitions
│   ├── __init__.py
│   ├── auth.py                 # Registration, login forms
│   ├── task.py                 # Task create/edit forms
│   ├── countdown.py            # Countdown create/edit forms
│   └── dashboard.py            # Dashboard create/edit forms
├── templates/                  # Jinja2 templates
│   ├── base.html               # Base template with HTMX
│   ├── auth/
│   │   ├── register.html
│   │   └── login.html
│   ├── dashboard/
│   │   ├── view.html           # Main dashboard display
│   │   └── list.html           # Dashboard switcher
│   └── admin/
│       ├── tasks.html
│       ├── countdowns.html
│       └── dashboards.html
├── static/                     # Static assets
│   ├── css/
│   │   └── style.css
│   └── uploads/                # User-uploaded images (tenant-isolated)
│       └── {tenant_id}/
├── utils/                      # Utility modules
│   ├── __init__.py
│   ├── rotation.py             # Day-of-year rotation logic
│   ├── countdown.py            # Countdown calculation logic
│   └── tenant.py               # Tenant context utilities
├── migrations/                 # Alembic migrations
│   ├── versions/
│   └── alembic.ini
└── config.py                   # Configuration classes

tests/
├── conftest.py                 # pytest fixtures
├── test_models/                # Model tests
│   ├── test_family.py
│   ├── test_user.py
│   ├── test_dashboard.py
│   ├── test_task.py
│   └── test_countdown.py
├── test_routes/                # Route tests
│   ├── test_auth.py
│   ├── test_dashboard.py
│   └── test_admin.py
├── test_utils/                 # Utility tests
│   ├── test_rotation.py
│   └── test_countdown.py
└── test_integration/           # Integration tests
    ├── test_tenant_isolation.py
    ├── test_auth_flow.py
    └── test_dashboard_polling.py

app.py                          # Application entry point
requirements.txt                # Python dependencies
requirements-dev.txt            # Development dependencies
.env.example                    # Environment variable template
.flaskenv                       # Flask CLI config
