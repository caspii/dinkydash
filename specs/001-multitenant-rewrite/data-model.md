# Data Model: Multi-Tenant DinkyDash

**Feature**: 001-multitenant-rewrite
**Date**: 2025-12-04
**Purpose**: Complete database schema design for multi-tenant DinkyDash web application

---

## Overview

The DinkyDash data model implements a multi-tenant architecture where each family (tenant) has complete data isolation. The schema supports:

- **Tenant-based isolation**: Each family is a tenant with its own users, dashboards, tasks, and countdowns
- **Database portability**: Single schema works on both SQLite (Raspberry Pi) and PostgreSQL (cloud)
- **Scalability**: Indexes and foreign keys optimize queries for 50+ concurrent families
- **Referential integrity**: Foreign keys with appropriate cascade delete policies
- **Audit trail**: Creation timestamps on all records for debugging and analytics

The database follows a normalized relational design with 5 core entities:
1. **Family** (tenant container)
2. **User** (authentication)
3. **Dashboard** (organization/layout)
4. **Task** (recurring rotation)
5. **Countdown** (event tracking)

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Family (Tenant)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ id (PK)                                              │   │
│  │ name                                                 │   │
│  │ created_at                                           │   │
│  └──────────────────────────────────────────────────────┘   │
│         ↓ (1:many)              ↓ (1:many)                  │
├─────────────────────┬──────────────────────┤                │
│                     │                      │                │
│  ┌────────────────┐ │  ┌──────────────────┐│                │
│  │     User       │─┤  │    Dashboard     ││                │
│  │                │ │  │                  ││                │
│  │ id (PK)        │ │  │ id (PK)          ││                │
│  │ email (UK)     │ │  │ name             ││                │
│  │ password_hash  │ │  │ layout_size      ││                │
│  │ tenant_id (FK) │ │  │ is_default       ││                │
│  │ created_at     │ │  │ created_at       ││                │
│  └────────────────┘ │  │ tenant_id (FK)   ││                │
│                     │  └──────────────────┘│                │
│                     │         ↓ (1:many)   │                │
│                     └─────┬──────────┬─────┤                │
│                           │          │      │                │
│                     ┌──────┴──┐  ┌──┴───────┴─────┐         │
│                     │          │  │                │         │
│                  ┌──────────┐  │  │  ┌─────────────────┐    │
│                  │  Task    │  │  │  │   Countdown     │    │
│                  │          │  │  │  │                 │    │
│                  │ id (PK)  │  │  │  │ id (PK)         │    │
│                  │ name     │  │  │  │ name            │    │
│                  │ rotation │  │  │  │ date_month      │    │
│                  │ icon_*   │  │  │  │ date_day        │    │
│                  │ created  │  │  │  │ icon_*          │    │
│                  │ dashboard└──┘  │  │ created_at      │    │
│                  │ (FK)           │  │ dashboard_id    │    │
│                  └────────────────┘  │   (FK)          │    │
│                                      │ created_at      │    │
│                                      └─────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Legend:
  PK = Primary Key
  FK = Foreign Key
  UK = Unique Key
  1:many = One-to-Many relationship
```

---

## Detailed Table Schemas

### 1. Family Table (Tenant Container)

```sql
CREATE TABLE family (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT family_name_not_empty CHECK (name != ''),
    CONSTRAINT family_name_max_length CHECK (length(name) <= 255)
);

-- Indexes
CREATE INDEX idx_family_created_at ON family(created_at);
```

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, NOT NULL, auto-increment | Unique family/tenant identifier |
| `name` | VARCHAR(255) | NOT NULL, NOT EMPTY | Family name (e.g., "Smith Family") |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Account creation timestamp |

**Relationships**:
- **One-to-Many**: Family → Users (1 family has many users)
- **One-to-Many**: Family → Dashboards (1 family has many dashboards)

**Constraints**:
- Primary key on `id` (auto-incremented)
- Not-null constraint on `name` and `created_at`
- Check constraint: family name cannot be empty string
- Check constraint: family name maximum 255 characters

**Indexes**:
- Primary key index on `id` (automatic)
- Index on `created_at` (for querying recent registrations)

---

### 2. User Table (Authentication)

```sql
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    tenant_id INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    CONSTRAINT user_family_fk FOREIGN KEY (tenant_id)
        REFERENCES family(id) ON DELETE CASCADE,

    -- Unique Constraint
    CONSTRAINT user_email_unique UNIQUE (email),

    -- Check Constraints
    CONSTRAINT user_email_format CHECK (email LIKE '%@%.%'),
    CONSTRAINT user_email_not_empty CHECK (email != ''),
    CONSTRAINT user_password_not_empty CHECK (password_hash != '')
);

-- Indexes
CREATE INDEX idx_user_email ON user(email);
CREATE INDEX idx_user_tenant_id ON user(tenant_id);
```

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, NOT NULL, auto-increment | Unique user identifier |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE | Email address (login credential) |
| `password_hash` | VARCHAR(255) | NOT NULL | Bcrypt/Argon2 hash (never store plain text) |
| `tenant_id` | INTEGER | NOT NULL, FK | References Family.id for tenant isolation |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Account creation timestamp |

**Relationships**:
- **Many-to-One**: User → Family (many users belong to one family)

**Constraints**:
- Primary key on `id` (auto-incremented)
- Unique constraint on `email` (prevents duplicate accounts, enforces via check on global level)
- Foreign key on `tenant_id` with ON DELETE CASCADE (delete family → delete users)
- Check constraint: email must follow format 'x@y.z' (basic validation, strict validation in application)
- Check constraints: email and password_hash cannot be empty strings
- Not-null constraint on all columns

**Indexes**:
- Primary key index on `id` (automatic)
- Unique index on `email` (for fast login lookups)
- Index on `tenant_id` (for querying users by family)

**Security Notes**:
- Passwords hashed with bcrypt (cost factor 12) or Argon2 before storage
- Email validated for format on registration (application-level)
- Session tokens never stored in user table (handled by Flask-Login session)

---

### 3. Dashboard Table (Organization/Layout)

```sql
CREATE TABLE dashboard (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    layout_size VARCHAR(50) NOT NULL DEFAULT 'medium',
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    CONSTRAINT dashboard_family_fk FOREIGN KEY (tenant_id)
        REFERENCES family(id) ON DELETE CASCADE,

    -- Check Constraints
    CONSTRAINT dashboard_name_not_empty CHECK (name != ''),
    CONSTRAINT dashboard_name_max_length CHECK (length(name) <= 255),
    CONSTRAINT dashboard_layout_size_valid CHECK (
        layout_size IN ('small', 'medium', 'large')
    ),
    CONSTRAINT dashboard_is_default_boolean CHECK (
        is_default IN (0, 1)
    )
);

-- Indexes
CREATE INDEX idx_dashboard_tenant_id ON dashboard(tenant_id);
CREATE INDEX idx_dashboard_tenant_is_default ON dashboard(tenant_id, is_default);
CREATE INDEX idx_dashboard_created_at ON dashboard(created_at);
```

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, NOT NULL, auto-increment | Unique dashboard identifier |
| `tenant_id` | INTEGER | NOT NULL, FK | References Family.id for tenant isolation |
| `name` | VARCHAR(255) | NOT NULL | User-defined dashboard name (e.g., "Kitchen Dashboard") |
| `layout_size` | VARCHAR(50) | NOT NULL, DEFAULT 'medium' | Preset size: 'small', 'medium', or 'large' |
| `is_default` | BOOLEAN | NOT NULL, DEFAULT FALSE | Marks first dashboard created during registration |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Dashboard creation timestamp |

**Relationships**:
- **Many-to-One**: Dashboard → Family (many dashboards belong to one family)
- **One-to-Many**: Dashboard → Tasks (1 dashboard has many tasks)
- **One-to-Many**: Dashboard → Countdowns (1 dashboard has many countdowns)

**Constraints**:
- Primary key on `id` (auto-incremented)
- Foreign key on `tenant_id` with ON DELETE CASCADE (delete family → delete dashboards)
- Not-null constraint on all columns except `created_at` (has default)
- Check constraint: name cannot be empty
- Check constraint: name maximum 255 characters
- Check constraint: layout_size must be one of 'small', 'medium', 'large'
- Check constraint: is_default is boolean (0 or 1 in SQLite)

**Indexes**:
- Primary key index on `id` (automatic)
- Index on `tenant_id` (for querying dashboards for a family)
- Composite index on `(tenant_id, is_default)` (for finding default dashboard quickly)
- Index on `created_at` (for audit/analytics)

**Business Rules**:
- Each family must have at least one dashboard
- Exactly one dashboard per family has `is_default = TRUE` (enforced at application level)
- Default dashboard is created automatically during family registration with name "Family Dashboard"
- Dashboard names need not be unique within a family (multiple can have same name)
- Deleting a dashboard orphans its tasks/countdowns (must be reassigned or deleted separately)

---

### 4. Task Table (Recurring Rotation)

```sql
CREATE TABLE task (
    id INTEGER PRIMARY KEY,
    dashboard_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    rotation_json TEXT NOT NULL,
    icon_type VARCHAR(50) NOT NULL,
    icon_value TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    CONSTRAINT task_dashboard_fk FOREIGN KEY (dashboard_id)
        REFERENCES dashboard(id) ON DELETE SET NULL,

    -- Check Constraints
    CONSTRAINT task_name_not_empty CHECK (name != ''),
    CONSTRAINT task_name_max_length CHECK (length(name) <= 255),
    CONSTRAINT task_icon_type_valid CHECK (
        icon_type IN ('emoji', 'image', 'none')
    ),
    CONSTRAINT task_rotation_not_empty CHECK (rotation_json != '[]')
);

-- Indexes
CREATE INDEX idx_task_dashboard_id ON task(dashboard_id);
CREATE INDEX idx_task_created_at ON task(created_at);
```

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, NOT NULL, auto-increment | Unique task identifier |
| `dashboard_id` | INTEGER | NOT NULL, FK | References Dashboard.id |
| `name` | VARCHAR(255) | NOT NULL | Task name (e.g., "Wash Dishes") |
| `rotation_json` | TEXT | NOT NULL | JSON array of people in rotation (e.g., `["Alice", "Bob", "Charlie"]`) |
| `icon_type` | VARCHAR(50) | NOT NULL | One of 'emoji', 'image', or 'none' |
| `icon_value` | TEXT | NULLABLE | Emoji text (if type='emoji') or file path (if type='image') |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Task creation timestamp |

**Relationships**:
- **Many-to-One**: Task → Dashboard (many tasks belong to one dashboard)

**Constraints**:
- Primary key on `id` (auto-incremented)
- Foreign key on `dashboard_id` with ON DELETE SET NULL (orphan if dashboard deleted)
- Not-null constraint on all except `icon_value` and `created_at`
- Check constraint: name cannot be empty
- Check constraint: name maximum 255 characters
- Check constraint: icon_type must be 'emoji', 'image', or 'none'
- Check constraint: rotation_json cannot be empty array (must have at least 1 person)

**Indexes**:
- Primary key index on `id` (automatic)
- Index on `dashboard_id` (for querying tasks per dashboard)
- Index on `created_at` (for audit/analytics)

**Tenant Isolation**:
- Indirectly tenant-isolated through Dashboard.tenant_id
- All task queries must filter through Dashboard

**Data Format**:
- `rotation_json`: Valid JSON array of strings
  - Example: `["Alice", "Bob", "Charlie"]`
  - Minimum length: 1 element
  - Maximum elements: 365 (one per day of year, practical limit)
  - No duplicate checking (duplicates allowed but unusual)

- `icon_value` format by type:
  - If `icon_type = 'emoji'`: Unicode emoji or text (e.g., "🍽" or "Dishes")
  - If `icon_type = 'image'`: File path relative to uploads directory (e.g., `uploads/123/task_456.jpg`)
  - If `icon_type = 'none'`: NULL or empty string

**Business Rules**:
- Rotation is circular: person at index 0 on day 0, person at index 1 on day 1, etc.
- Current assignee calculated by: `rotation[day_of_year % rotation_length]`
- Only one icon type allowed (emoji OR image, not both)
- Task can be deleted independently of dashboard (orphaning not typically needed since ON DELETE SET NULL handles dashboard deletion)

---

### 5. Countdown Table (Event Tracking)

```sql
CREATE TABLE countdown (
    id INTEGER PRIMARY KEY,
    dashboard_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    date_month INTEGER NOT NULL,
    date_day INTEGER NOT NULL,
    icon_type VARCHAR(50) NOT NULL,
    icon_value TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    CONSTRAINT countdown_dashboard_fk FOREIGN KEY (dashboard_id)
        REFERENCES dashboard(id) ON DELETE SET NULL,

    -- Check Constraints
    CONSTRAINT countdown_name_not_empty CHECK (name != ''),
    CONSTRAINT countdown_name_max_length CHECK (length(name) <= 255),
    CONSTRAINT countdown_month_valid CHECK (
        date_month >= 1 AND date_month <= 12
    ),
    CONSTRAINT countdown_day_valid CHECK (
        date_day >= 1 AND date_day <= 31
    ),
    CONSTRAINT countdown_icon_type_valid CHECK (
        icon_type IN ('emoji', 'image', 'none')
    )
);

-- Indexes
CREATE INDEX idx_countdown_dashboard_id ON countdown(dashboard_id);
CREATE INDEX idx_countdown_date ON countdown(date_month, date_day);
CREATE INDEX idx_countdown_created_at ON countdown(created_at);
```

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, NOT NULL, auto-increment | Unique countdown identifier |
| `dashboard_id` | INTEGER | NOT NULL, FK | References Dashboard.id |
| `name` | VARCHAR(255) | NOT NULL | Event name (e.g., "Mom's Birthday") |
| `date_month` | INTEGER | NOT NULL | Month (1-12) |
| `date_day` | INTEGER | NOT NULL | Day (1-31) |
| `icon_type` | VARCHAR(50) | NOT NULL | One of 'emoji', 'image', or 'none' |
| `icon_value` | TEXT | NULLABLE | Emoji text (if type='emoji') or file path (if type='image') |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Countdown creation timestamp |

**Relationships**:
- **Many-to-One**: Countdown → Dashboard (many countdowns belong to one dashboard)

**Constraints**:
- Primary key on `id` (auto-incremented)
- Foreign key on `dashboard_id` with ON DELETE SET NULL (orphan if dashboard deleted)
- Not-null constraint on all except `icon_value` and `created_at`
- Check constraint: name cannot be empty
- Check constraint: name maximum 255 characters
- Check constraint: date_month between 1-12 (valid months)
- Check constraint: date_day between 1-31 (valid day range, note: doesn't validate Feb 29 or invalid dates like Apr 31)
- Check constraint: icon_type must be 'emoji', 'image', or 'none'

**Indexes**:
- Primary key index on `id` (automatic)
- Index on `dashboard_id` (for querying countdowns per dashboard)
- Composite index on `(date_month, date_day)` (for finding countdowns near today's date)
- Index on `created_at` (for audit/analytics)

**Tenant Isolation**:
- Indirectly tenant-isolated through Dashboard.tenant_id
- All countdown queries must filter through Dashboard

**Data Format**:
- `date_month`: 1-12 (Jan-Dec)
- `date_day`: 1-31 (valid day numbers, note: application must validate actual valid dates)
- `icon_value`: Same format as Task

**Business Rules**:
- No year stored (countdowns are annual events)
- Days remaining calculated: If date has passed this year, calculate days to next year's occurrence
- Countdown automatically rolls over to next year after event passes
- Invalid dates (e.g., Feb 30) prevented by application validation on creation/edit
- Only one icon type allowed (emoji OR image, not both)

---

## Field Specifications

### Common Fields Across Tables

**Timestamps** (`created_at`):
- Type: TIMESTAMP
- Format: ISO 8601 with timezone (if supported) or UTC
- Default: CURRENT_TIMESTAMP
- Usage: Record creation time for audit trail and analytics
- Not updated on subsequent modifications (created_at remains constant)

**Text Fields** (name, email, emoji):
- Type: VARCHAR or TEXT
- Encoding: UTF-8 (supports emojis and international characters)
- Validation: Application-level length checks before database insert
- Escaping: Automatic via ORM parameterized queries (SQLAlchemy)

**File Paths** (icon_value for images):
- Stored as relative path from uploads root
- Format: `uploads/{tenant_id}/{entity_type}_{entity_id}.{ext}`
- Examples:
  - `uploads/123/task_456.jpg`
  - `uploads/123/countdown_789.png`
- Validation: Application validates file exists and is accessible to tenant
- Cleanup: Orphaned files deleted when task/countdown deleted

**JSON Data** (rotation_json):
- Type: TEXT field containing JSON
- Format: Valid JSON array of strings
- Example: `["Alice", "Bob", "Charlie"]`
- Parsing: Application deserializes to Python list on load
- Serialization: Application serializes from Python list on save
- Validation: Application validates JSON validity and array length

### Nullable vs NOT NULL

| Field | Nullable | Reason |
|-------|----------|--------|
| Family.name | NO | Required for family identity |
| User.email | NO | Required for authentication |
| User.password_hash | NO | Required for authentication |
| User.tenant_id | NO | Required for tenant isolation |
| Dashboard.name | NO | Required for user navigation |
| Dashboard.layout_size | NO | Has sensible default ('medium') |
| Dashboard.is_default | NO | Has default value (FALSE) |
| Task.name | NO | Required for display |
| Task.rotation_json | NO | Required (must have rotation) |
| Task.icon_type | NO | Has default ('none') |
| Task.icon_value | YES | Icon is optional |
| Countdown.name | NO | Required for display |
| Countdown.date_month | NO | Required for calculation |
| Countdown.date_day | NO | Required for calculation |
| Countdown.icon_type | NO | Has default ('none') |
| Countdown.icon_value | YES | Icon is optional |

### Unique Constraints

| Table | Constraint | Type | Reason |
|-------|-----------|------|--------|
| User | email | UNIQUE | Prevents duplicate accounts across entire system |
| Dashboard | (tenant_id, name) | NOT UNIQUE | Allows duplicate dashboard names within family (by design) |
| Task | None | - | Multiple tasks can have same name on different dashboards |
| Countdown | None | - | Multiple countdowns can have same name on different dashboards |

---

## Foreign Keys with Cascading Rules

### Cascading Strategies

**ON DELETE CASCADE**: Automatically delete child records when parent deleted
- `family` ← `user` (delete family → delete all users)
- `family` ← `dashboard` (delete family → delete all dashboards)

**ON DELETE SET NULL**: Orphan child records when parent deleted
- `dashboard` ← `task` (delete dashboard → tasks become dashboard_id=NULL)
- `dashboard` ← `countdown` (delete dashboard → countdowns become dashboard_id=NULL)

### Rationale

- **CASCADE on Family**: Family deletion is permanent and destructive; safe to cascade
- **CASCADE on Dashboard creation via Family**: Dashboard is created with family; cascading ensures data consistency
- **SET NULL on Dashboard for Tasks/Countdowns**: Tasks/Countdowns are reassignable; orphaning allows reassignment to another dashboard
- **Manual cleanup**: Application responsible for handling orphaned tasks/countdowns (UI prompts for reassignment)

---

## Validation Rules

### Email Validation

**Format**: Must follow standard email pattern
- Pattern: `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
- Application-level validation (not just database check)
- Prevents typos and ensures deliverability for password reset
- Library: Python `email-validator` or `WTForms.validators.Email`

**Uniqueness**: Global uniqueness across all families
- User cannot register with email already in use
- Prevents multiple accounts and enables login uniqueness

**Case Sensitivity**: Email lowercased on storage
- Normalize to lowercase on registration and login
- Prevents duplicate accounts from case variations

### Password Validation

**Minimum Length**: 8 characters (as per FR-004)
- Enforced during registration and password change
- Clear error message if too short

**Strength**: No additional complexity requirements in MVP
- Rationale: 8-character minimum sufficient for family usage
- Future enhancement: Add complexity checks (uppercase, numbers, symbols)

**Hashing**: Bcrypt with cost factor 12 or Argon2
- Library: Werkzeug.security or `argon2-cffi`
- Never stored as plain text
- Hash verified on login via constant-time comparison

### Task Validation

**Name**:
- Required (not empty)
- Maximum 255 characters
- Any Unicode text allowed (names in any language)

**Rotation**:
- At least 1 person (array length >= 1)
- Maximum 365 people (one per day of year, practical limit)
- Each person is non-empty string
- Duplicates allowed (unusual but valid)
- Order preserved (first in array = day 0)

**Icon Type**:
- Must be 'emoji', 'image', or 'none'
- Mutually exclusive: cannot have both emoji and image

**Icon Value** (if type='emoji'):
- Non-empty Unicode string
- May contain emojis: "🍽", "🚮", "🐾"
- May contain text: "Dishes", "Trash", "Pet Care"
- No length limit (reasonable assumption: <1000 chars)

**Icon Value** (if type='image'):
- Valid file path to uploaded image
- File must exist in uploads directory
- File must be accessible by user
- Allowed formats: JPG, PNG, GIF
- File size: < 5 MB

### Countdown Validation

**Name**:
- Required (not empty)
- Maximum 255 characters
- Any Unicode text allowed

**Date**:
- Month: 1-12 (Jan-Dec)
- Day: 1-31 (basic range check)
- Application validates actual valid dates (e.g., rejects Feb 30)
- Application validates date not in distant past (prevents user error)

**Icon Type**: Same as Task

**Icon Value**: Same as Task

### File Upload Validation

**File Type**:
- Allowed: JPG, PNG, GIF (checked by MIME type and file extension)
- Rejected: EXE, PDF, ZIP, or any other type
- Validation library: Pillow (to verify image headers)

**File Size**:
- Maximum: 5 MB (5 * 1024 * 1024 bytes)
- Checked before processing
- Error message: "File too large. Maximum 5 MB allowed."

**File Name**:
- Sanitized to prevent directory traversal
- Stored as: `{type}_{id}.{ext}` (e.g., task_456.jpg)
- Original filename discarded

**Virus/Malware**:
- File header validated (prevents .exe renamed as .jpg)
- Pillow library verifies image headers
- No additional antivirus scanning in MVP

---

## Indexes for Performance

### Index Strategy

Indexes are created for:
1. **Primary Keys**: Automatic (unique index)
2. **Foreign Keys**: Required for join performance
3. **Search Columns**: Where WHERE clauses filter
4. **Sorting**: Columns used in ORDER BY
5. **Composite Indexes**: For common multi-column queries

### Index Specifications

| Table | Index Name | Columns | Type | Purpose |
|-------|-----------|---------|------|---------|
| family | PK | id | UNIQUE | Primary key |
| family | idx_family_created_at | created_at | BTREE | Recent registrations query |
| user | PK | id | UNIQUE | Primary key |
| user | idx_user_email | email | UNIQUE | Fast login lookup |
| user | idx_user_tenant_id | tenant_id | BTREE | Query users by family |
| dashboard | PK | id | UNIQUE | Primary key |
| dashboard | idx_dashboard_tenant_id | tenant_id | BTREE | Query dashboards by family |
| dashboard | idx_dashboard_tenant_default | (tenant_id, is_default) | BTREE | Find default dashboard quickly |
| dashboard | idx_dashboard_created_at | created_at | BTREE | Audit/analytics |
| task | PK | id | UNIQUE | Primary key |
| task | idx_task_dashboard_id | dashboard_id | BTREE | Query tasks per dashboard |
| task | idx_task_created_at | created_at | BTREE | Audit/analytics |
| countdown | PK | id | UNIQUE | Primary key |
| countdown | idx_countdown_dashboard_id | dashboard_id | BTREE | Query countdowns per dashboard |
| countdown | idx_countdown_date | (date_month, date_day) | BTREE | Find countdowns by date |
| countdown | idx_countdown_created_at | created_at | BTREE | Audit/analytics |

### Query Performance Examples

**Find all tasks on a dashboard**:
- Query: `SELECT * FROM task WHERE dashboard_id = 5`
- Index used: `idx_task_dashboard_id`
- Expected: <10ms for typical dashboard

**Find default dashboard for family**:
- Query: `SELECT * FROM dashboard WHERE tenant_id = 3 AND is_default = TRUE`
- Index used: `idx_dashboard_tenant_default`
- Expected: <5ms

**Login with email**:
- Query: `SELECT * FROM user WHERE email = 'alice@example.com'`
- Index used: `idx_user_email`
- Expected: <5ms

**Find countdowns near today**:
- Query: `SELECT * FROM countdown WHERE date_month = 12 AND date_day = 25`
- Index used: `idx_countdown_date`
- Expected: <10ms

---

## Tenant Isolation Implementation

### Multi-Tenancy Model

**Type**: Account-based multi-tenancy
- Each family is a separate account (tenant)
- Users belong to exactly one family (tenant)
- Data is logically separated by tenant_id

### Isolation Strategy

**Database Level**:
- All tenant-specific tables have `tenant_id` column
- Foreign keys link directly to Family table
- Queries automatically filtered by tenant_id (via SQLAlchemy event listener)

**Application Level**:
- User context sets `g.current_tenant_id` from authenticated user
- All queries transparently filter by tenant
- Middleware rejects cross-tenant access attempts

**Example - Tenant Isolation via ORM**:

```python
# models/__init__.py
from sqlalchemy import event
from flask import g

# Automatic tenant filtering
@event.listens_for(db.session, 'before_compile', retval=True)
def apply_tenant_filter(query):
    if hasattr(g, 'current_tenant_id'):
        for entity in query.column_descriptions:
            mapper = entity.get('type')
            if mapper and hasattr(mapper, 'tenant_id'):
                query = query.filter(mapper.tenant_id == g.current_tenant_id)
    return query

# Set tenant context when user logs in
@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    if user:
        g.current_tenant_id = user.tenant_id
    return user
```

### Testing Tenant Isolation

**Test Case 1**: Family A cannot access Family B's tasks
```python
def test_cross_tenant_isolation():
    # Create two families
    family_a = Family(name="Family A")
    family_b = Family(name="Family B")

    # Create users for each
    user_a = User(email="alice@a.com", tenant_id=family_a.id)
    user_b = User(email="bob@b.com", tenant_id=family_b.id)

    # Create dashboard and task for Family A
    dashboard_a = Dashboard(tenant_id=family_a.id, name="Kitchen")
    task_a = Task(dashboard_id=dashboard_a.id, name="Dishes")

    # Create task for Family B
    dashboard_b = Dashboard(tenant_id=family_b.id, name="Kitchen")
    task_b = Task(dashboard_id=dashboard_b.id, name="Laundry")

    # Login as Family A user
    login_user(user_a)

    # Query should only return task_a
    tasks = Task.query.all()
    assert len(tasks) == 1
    assert tasks[0].id == task_a.id

    # task_b should not be accessible
```

**Test Case 2**: URL manipulation cannot access other family's dashboard
```python
def test_cross_tenant_url_access():
    # Login as Family A
    login_user(user_a)

    # Attempt to access Family B's dashboard by ID
    response = client.get(f'/dashboard/{dashboard_b.id}')

    # Should get 403 or empty result
    assert response.status_code == 403 or b'not found' in response.data
```

---

## Migration Strategy

### Initial Schema Creation

**Step 1: Define Models**
```python
# models.py - SQLAlchemy models matching schema above
class Family(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('family.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

# ... other models
```

**Step 2: Generate Initial Migration**
```bash
flask db init migrations/
flask db migrate -m "Create initial schema"
```

**Step 3: Review Migration**
- Inspect `migrations/versions/xxx_create_initial_schema.py`
- Verify all tables, columns, constraints, indexes are present
- Check ON DELETE behavior is correct

**Step 4: Apply to Development Database**
```bash
flask db upgrade
# Verify with: sqlite3 dinkydash.db ".schema"
```

### Schema Evolution

**Adding a Column**:
```bash
# 1. Update model
class Task(db.Model):
    # ... existing columns
    priority = db.Column(db.Integer, default=0)  # NEW

# 2. Create migration
flask db migrate -m "Add priority column to task"

# 3. Review and apply
flask db upgrade
```

**Removing a Column**:
```bash
# 1. Update model (remove column definition)
# 2. Create migration
flask db migrate -m "Remove priority column from task"

# 3. Review migration (verify DROP COLUMN)
# 4. Apply
flask db upgrade
```

**Renaming a Column**:
```bash
# 1. Create migration manually
# (Alembic can auto-detect if you add both old and new in model, but manual is safer)
flask db migrate --manual -m "Rename task.priority to task.importance"

# 2. In migration file, use op.alter_column():
# op.alter_column('task', 'priority', new_column_name='importance')

# 3. Update model after migration succeeds
```

### Testing Migrations

**SQLite Testing**:
```bash
# Start with clean database
rm dinkydash-test.db

# Apply migrations
SQLALCHEMY_DATABASE_URI='sqlite:///dinkydash-test.db' flask db upgrade

# Run tests with test data
pytest tests/

# Verify no data loss
sqlite3 dinkydash-test.db "SELECT COUNT(*) FROM task"
```

**PostgreSQL Testing**:
```bash
# Start with clean database
dropdb dinkydash_test
createdb dinkydash_test

# Apply migrations
DATABASE_URL='postgresql://user:pass@localhost/dinkydash_test' flask db upgrade

# Run tests
pytest tests/ -m postgresql

# Verify
psql dinkydash_test -c "SELECT COUNT(*) FROM task"
```

### Migration Checklist

Before committing a migration:
- [ ] Reviewed generated migration file for accuracy
- [ ] Tested upgrade path on SQLite
- [ ] Tested upgrade path on PostgreSQL
- [ ] Tested downgrade path (if appropriate)
- [ ] No data loss in test scenarios
- [ ] Backups created before production deployment
- [ ] Deployment plan documented

### Handling Migration Failures

**If migration fails during deployment**:
1. Stop application immediately
2. Revert migration: `flask db downgrade` (only if safe)
3. Check database logs for specific error
4. Fix migration and retry, or rollback to previous version
5. Never ignore migration errors (data integrity at risk)

---

## Constraints Summary

### Check Constraints

| Table | Constraint | Condition | Reason |
|-------|-----------|-----------|--------|
| Family | family_name_not_empty | name != '' | Prevent empty names |
| Family | family_name_max_length | length(name) <= 255 | Prevent storage issues |
| User | user_email_not_empty | email != '' | Prevent empty emails |
| User | user_email_format | email LIKE '%@%.%' | Basic email validation |
| User | user_password_not_empty | password_hash != '' | Prevent empty hashes |
| Dashboard | dashboard_name_not_empty | name != '' | Prevent empty names |
| Dashboard | dashboard_name_max_length | length(name) <= 255 | Prevent storage issues |
| Dashboard | dashboard_layout_valid | layout_size IN ('small', 'medium', 'large') | Only valid sizes |
| Dashboard | dashboard_is_default_bool | is_default IN (0, 1) | Boolean enforcement |
| Task | task_name_not_empty | name != '' | Prevent empty names |
| Task | task_name_max_length | length(name) <= 255 | Prevent storage issues |
| Task | task_icon_type_valid | icon_type IN ('emoji', 'image', 'none') | Valid icon types |
| Task | task_rotation_not_empty | rotation_json != '[]' | Must have at least 1 person |
| Countdown | countdown_name_not_empty | name != '' | Prevent empty names |
| Countdown | countdown_name_max_length | length(name) <= 255 | Prevent storage issues |
| Countdown | countdown_month_valid | date_month BETWEEN 1 AND 12 | Valid month range |
| Countdown | countdown_day_valid | date_day BETWEEN 1 AND 31 | Valid day range |
| Countdown | countdown_icon_type_valid | icon_type IN ('emoji', 'image', 'none') | Valid icon types |

### Foreign Key Constraints

| Child Table | Parent Table | Columns | ON DELETE |
|-----------|-------------|---------|-----------|
| User | Family | tenant_id → id | CASCADE |
| Dashboard | Family | tenant_id → id | CASCADE |
| Task | Dashboard | dashboard_id → id | SET NULL |
| Countdown | Dashboard | dashboard_id → id | SET NULL |

### Unique Constraints

| Table | Columns | Type | Reason |
|-------|---------|------|--------|
| User | email | Unique Index | Prevent duplicate logins |

---

## Implementation Notes

### SQLite-Specific Considerations

**Autoincrement**:
- SQLite automatically implements INTEGER PRIMARY KEY as AUTOINCREMENT
- Syntax: `id INTEGER PRIMARY KEY` (no explicit AUTOINCREMENT needed)

**Boolean Storage**:
- SQLite has no native BOOLEAN type
- Stored as INTEGER (0 = FALSE, 1 = TRUE)
- ORM automatically converts to Python bool

**Date Functions**:
- SQLite uses `CURRENT_TIMESTAMP` for current date/time
- Python datetime objects serialized as ISO 8601 strings
- Application handles timezone normalization (store UTC)

**JSON Support**:
- SQLite 3.38+ has JSON functions (json_array, json_extract, etc.)
- MVP stores rotation_json as TEXT and parses in Python
- Future optimization: Use SQLite JSON functions for filtering

**Full-Text Search**:
- Not required for MVP
- Future enhancement if needed for task/countdown search

### PostgreSQL-Specific Considerations

**Autoincrement**:
- Use SERIAL type for auto-incrementing ID
- Or use BIGSERIAL for future scalability

**Boolean Storage**:
- PostgreSQL has native BOOLEAN type
- SQLAlchemy automatically maps to Python bool

**JSON Support**:
- PostgreSQL has native JSONB type (better for queries)
- ORM can use JSONB for rotation_json with query support
- But TEXT is compatible for MVP

**Indexes**:
- Can use BTREE, HASH, GIN indexes (BTREE default)
- For future: GIN indexes on JSONB rotation_json field

**Connection Pooling**:
- Use psycopg2 with SQLAlchemy connection pooling
- Production: Use PgBouncer for connection management

---

## Backup and Recovery

### Backup Strategy

**SQLite (Raspberry Pi)**:
```bash
# Simple file copy (when app is stopped)
cp /path/to/dinkydash.db /backup/dinkydash-$(date +%Y%m%d).db

# Or with app running (using WAL)
sqlite3 /path/to/dinkydash.db ".backup /backup/dinkydash-backup.db"
```

**PostgreSQL (Cloud)**:
```bash
# Full database backup
pg_dump -U postgres dinkydash > dinkydash-$(date +%Y%m%d).sql

# Or using pg_basebackup for physical backup
pg_basebackup -D /backup/dinkydash_backup -Ft -z
```

**Automated Backups**:
- Cron job for SQLite: Daily at 2 AM (when usage is low)
- RDS snapshots for PostgreSQL: Daily automatic snapshots
- Retention: Keep last 30 days of backups

### Recovery Testing

- Test backup restore quarterly
- Document recovery procedure
- Estimate RTO (Recovery Time Objective): < 1 hour
- Estimate RPO (Recovery Point Objective): < 1 day

---

## Performance Characteristics

### Query Performance Estimates

| Query | Index Used | Expected Time |
|-------|-----------|---|
| Get user by email (login) | idx_user_email | < 5ms |
| Get all dashboards for family | idx_dashboard_tenant_id | < 10ms |
| Get default dashboard | idx_dashboard_tenant_default | < 5ms |
| Get all tasks for dashboard | idx_task_dashboard_id | < 10ms |
| Get all countdowns for dashboard | idx_countdown_dashboard_id | < 10ms |
| List countdowns by date | idx_countdown_date | < 10ms |

**Assumptions**:
- SQLite on Raspberry Pi (limited RAM, spinning disk)
- 50 families with 10 dashboards each = 500 total dashboards
- 5000 total tasks across system
- 7500 total countdowns across system
- Actual times depend on hardware and system load

### Storage Estimates

| Table | Avg Record Size | Estimate for 50 Families |
|-------|---|---|
| Family | 50 bytes | 2.5 KB |
| User | 150 bytes | 7.5 KB |
| Dashboard | 100 bytes | 250 KB |
| Task | 200 bytes | 500 KB |
| Countdown | 200 bytes | 750 KB |
| Uploaded Images | 50-200 KB | 200-500 MB |
| **Total** | - | **~200-500 MB** |

**Note**: Image storage dominates. For 50 families with 100 images each at average 100 KB: ~500 MB

### Scalability Limits

**SQLite (Single-file)**:
- Suitable for: 50-100 families, <1000 tasks, <2000 countdowns
- Bottleneck: File locking (single writer at a time)
- Beyond limit: Migrate to PostgreSQL

**PostgreSQL**:
- Suitable for: 1000+ families, unlimited tasks/countdowns
- Connection pooling: 20-50 connections typical
- Performance monitoring: Install pg_stat_statements

---

## Summary

This data model provides:

1. **Clear Entity Relationships**: Family → Users, Dashboards, Tasks, Countdowns
2. **Tenant Isolation**: All queries automatically filtered by family/tenant
3. **Referential Integrity**: Foreign keys prevent orphaned data
4. **Performance**: Strategic indexes for common queries
5. **Flexibility**: Supports both SQLite (Raspberry Pi) and PostgreSQL (Cloud)
6. **Maintainability**: Clear constraints and validation rules
7. **Security**: Password hashing, CSRF protection, tenant isolation

The schema is normalized (3NF), constraint-driven, and tested on both SQLite and PostgreSQL before deployment.
