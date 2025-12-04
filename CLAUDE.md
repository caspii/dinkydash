# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**⚠️ Architecture Rewrite in Progress**: This project is undergoing a complete rewrite from single-family config-based Pi dashboard to multi-tenant web application. See `/specs/001-multitenant-rewrite/` for implementation plan.

---

## Overview

DinkyDash is a multi-tenant family dashboard web application that displays:
- **Recurring tasks** that rotate daily among family members (e.g., whose turn to do dishes)
- **Countdowns** to important dates (birthdays, holidays, etc.)
- **Multiple dashboards** per family for room-based organization (Kitchen, Kids Room, etc.)
- **Customizable layouts** (small/medium/large) for different screen sizes

**Deployment targets**:
- **Raspberry Pi** (local/kiosk mode) - SQLite database
- **Cloud servers** (multi-family hosting) - PostgreSQL database

**Key principle**: Database-first design with row-level tenant isolation for security.

---

## Project Structure

### Application Code

```text
dinkydash/                      # Main application package
├── __init__.py                 # Flask app factory (create_app)
├── models/                     # SQLAlchemy ORM models
│   ├── family.py               # Family/Tenant model
│   ├── user.py                 # User model with Flask-Login
│   ├── dashboard.py            # Dashboard model
│   ├── task.py                 # Recurring task model
│   └── countdown.py            # Countdown event model
├── routes/                     # Flask blueprints
│   ├── auth.py                 # Registration, login, logout
│   ├── dashboard.py            # Dashboard viewing + HTMX polling
│   └── admin.py                # Task/countdown/dashboard CRUD
├── forms/                      # WTForms definitions
│   ├── auth.py                 # Registration, login forms
│   ├── task.py                 # Task create/edit form
│   ├── countdown.py            # Countdown create/edit form
│   └── dashboard.py            # Dashboard create/edit form
├── templates/                  # Jinja2 templates (server-side rendering)
│   ├── base.html               # Base template with HTMX
│   ├── auth/                   # Registration, login templates
│   ├── dashboard/              # Dashboard view, list
│   └── admin/                  # Admin management templates
├── static/                     # Static assets
│   ├── css/style.css
│   └── uploads/                # Tenant-isolated image storage
│       └── {tenant_id}/
└── utils/                      # Utility modules
    ├── rotation.py             # Day-of-year rotation logic
    ├── countdown.py            # Countdown calculation logic
    └── tenant.py               # Tenant context utilities

migrations/                     # Alembic database migrations
tests/                          # pytest test suite
app.py                          # Application entry point
config.py                       # Configuration classes
requirements.txt                # Python dependencies
.env                            # Environment variables (not in git)
```

### Specification Documents

```text
specs/001-multitenant-rewrite/
├── spec.md                     # Feature specification (WHAT to build)
├── plan.md                     # Implementation plan (HOW to build)
├── research.md                 # Technology decisions and patterns
├── data-model.md               # Database schema details
├── quickstart.md               # Setup and deployment guide
└── contracts/                  # API/UI specifications
    ├── routes.md               # Flask route specifications
    ├── forms.md                # WTForms specifications
    └── templates.md            # Jinja2 template specifications
```

---

## Development Commands

### Initial Setup

```bash
# Clone repository
git clone https://github.com/yourusername/dinkydash.git
cd dinkydash

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For testing

# Create environment file
cp .env.example .env
# Edit .env and set SECRET_KEY, DATABASE_URL

# Initialize database
flask db init        # First time only
flask db migrate -m "Initial schema"
flask db upgrade
```

### Running Locally

```bash
# Activate virtual environment
source venv/bin/activate

# Run development server
flask run
# or
python app.py

# Access at http://localhost:5000
```

### Database Migrations

```bash
# Generate migration after model changes
flask db migrate -m "Description of changes"

# Review migration file in migrations/versions/

# Apply migration
flask db upgrade

# Rollback migration
flask db downgrade
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=dinkydash --cov-report=html

# Run specific test file
pytest tests/test_routes/test_auth.py

# Run specific test
pytest tests/test_routes/test_auth.py::test_registration_success
```

---

## Architecture

### Flask Application Factory Pattern

**Entry point** (`app.py`):
```python
from dinkydash import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
```

**App factory** (`dinkydash/__init__.py`):
```python
def create_app(config_class=None):
    app = Flask(__name__)

    # Load configuration
    if config_class is None:
        env = os.environ.get('FLASK_ENV', 'production')
        config_map = {
            'development': DevelopmentConfig,
            'production': ProductionConfig,
            'testing': TestConfig
        }
        config_class = config_map.get(env, ProductionConfig)

    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Register blueprints
    from dinkydash.routes import auth, dashboard, admin
    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(admin.bp)

    # Register error handlers
    app.register_error_handler(403, forbidden_error)
    app.register_error_handler(404, not_found_error)
    app.register_error_handler(500, internal_error)

    return app
```

### Database Models (SQLAlchemy 2.0)

**Key entities**:
- `Family`: Tenant root (tenant_id references this)
- `User`: Authenticated users, belongs to Family
- `Dashboard`: Multiple dashboards per family (auto-created "Family Dashboard" on registration)
- `Task`: Recurring tasks with rotation, belongs to Dashboard
- `Countdown`: Countdown events with date, belongs to Dashboard

**Tenant isolation pattern**:
```python
from sqlalchemy import event
from flask import g

class TenantModel(db.Model):
    __abstract__ = True
    tenant_id = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)

# Automatic tenant filtering on all queries
@event.listens_for(db.session, 'before_compile', retval=True)
def apply_tenant_filter(query):
    if hasattr(g, 'current_tenant_id'):
        for entity in query.column_descriptions:
            if hasattr(entity['type'], 'tenant_id'):
                query = query.filter(entity['type'].tenant_id == g.current_tenant_id)
    return query
```

**Important**: All queries automatically filtered by tenant_id. To bypass (e.g., admin operations), explicitly use `db.session.query(Model).filter(...)` without tenant_id filter.

### Core Business Logic

**Rotation calculation** (`utils/rotation.py`):
```python
import time

def get_current_person(rotation_list):
    """Calculate current person in rotation based on day of year"""
    day_of_year = time.localtime().tm_yday
    index = day_of_year % len(rotation_list)
    return rotation_list[index]
```

**Countdown calculation** (`utils/countdown.py`):
```python
from datetime import date

def calculate_days_remaining(month, day):
    """Calculate days until next occurrence of date"""
    today = date.today()
    target = date(today.year, month, day)

    # If date already passed this year, target next year
    if target < today:
        target = date(today.year + 1, month, day)

    return (target - today).days
```

### HTMX Progressive Enhancement

**Dashboard auto-refresh** (30-second polling):
```html
<!-- templates/dashboard/view.html -->
<div id="dashboard-content"
     hx-get="{{ url_for('dashboard.dashboard_content', dashboard_id=dashboard.id) }}"
     hx-trigger="every 30s"
     hx-swap="outerHTML">
    <!-- Dashboard content (tasks, countdowns) -->
</div>

<!-- Fallback: Meta refresh for no-JS (60 seconds) -->
<meta http-equiv="refresh" content="60">
```

**Polling endpoint** (`routes/dashboard.py`):
```python
@dashboard_bp.route('/dashboard/<int:dashboard_id>/content')
@login_required
def dashboard_content(dashboard_id):
    # Validate tenant ownership
    dashboard = Dashboard.query.filter_by(
        id=dashboard_id,
        tenant_id=g.current_tenant_id
    ).first_or_404()

    # Eager load relationships (avoid N+1 queries)
    tasks = Task.query.options(joinedload(Task.dashboard)).filter_by(dashboard_id=dashboard_id).all()
    countdowns = Countdown.query.options(joinedload(Countdown.dashboard)).filter_by(dashboard_id=dashboard_id).all()

    # Calculate current state
    for task in tasks:
        task.current_person = get_current_person(json.loads(task.rotation_json))

    for countdown in countdowns:
        countdown.days_remaining = calculate_days_remaining(countdown.date_month, countdown.date_day)

    # Return partial HTML (no base template)
    return render_template('dashboard/view.html',
                           dashboard=dashboard,
                           tasks=tasks,
                           countdowns=countdowns,
                           partial=True)
```

### Authentication (Flask-Login)

**User loader** (`models/user.py`):
```python
@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    if user:
        g.current_tenant_id = user.tenant_id  # Set tenant context
    return user
```

**Password hashing** (Werkzeug):
```python
from werkzeug.security import generate_password_hash, check_password_hash

# On registration
user.password_hash = generate_password_hash(form.password.data)

# On login
if check_password_hash(user.password_hash, form.password.data):
    login_user(user, remember=form.remember_me.data)
```

### Image Upload Handling

**Direct upload pattern** (forms handle file upload):
```python
# forms/task.py
from flask_wtf.file import FileField, FileAllowed, FileSize

class TaskForm(FlaskForm):
    icon_type = RadioField('Icon Type', choices=[('emoji', 'Emoji'), ('image', 'Image')])
    emoji = StringField('Emoji', validators=[Optional()])
    image = FileField('Image', validators=[
        Optional(),
        FileAllowed(['jpg', 'png', 'gif']),
        FileSize(max_size=5*1024*1024)  # 5MB
    ])
```

**Image storage** (tenant-scoped directories):
```python
# routes/admin.py
import os
import uuid
from PIL import Image

def save_task_image(form_image, tenant_id, task_id):
    # Validate with Pillow
    img = Image.open(form_image)
    img.verify()

    # Generate unique filename
    ext = os.path.splitext(form_image.filename)[1]
    filename = f'task_{task_id}_{uuid.uuid4().hex}{ext}'

    # Save to tenant directory
    upload_dir = os.path.join('static', 'uploads', str(tenant_id))
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, filename)
    form_image.seek(0)  # Reset after verify
    form_image.save(filepath)

    return f'/static/uploads/{tenant_id}/{filename}'
```

---

## Configuration

### Environment Variables (.env)

```bash
FLASK_ENV=development              # development, production, testing
SECRET_KEY=<generate-with-openssl> # 32-byte hex string
DATABASE_URL=sqlite:///dinkydash-dev.db  # or postgresql://...
UPLOAD_FOLDER=static/uploads
MAX_CONTENT_LENGTH=5242880         # 5MB in bytes
```

### Configuration Classes (config.py)

- `Config`: Base configuration
- `DevelopmentConfig`: Debug mode, SQLite in-memory
- `ProductionConfig`: Production settings, PostgreSQL
- `TestConfig`: Testing mode, SQLite :memory:

Load via `FLASK_ENV` environment variable.

---

## Deployment

### Raspberry Pi (SQLite)

See `/specs/001-multitenant-rewrite/quickstart.md` for full guide.

**Quick steps**:
1. Install Python 3.11+, Nginx, systemd
2. Clone repo, install dependencies
3. Configure `.env` with SQLite
4. Run migrations: `flask db upgrade`
5. Create systemd service
6. Configure Nginx reverse proxy
7. Access at `http://<pi-ip>`

**Kiosk mode** (auto-launch browser): Configure Chromium autostart in `~/.config/lxsession/LXDE-pi/autostart`.

### Cloud (PostgreSQL)

**Hosting options**: DigitalOcean, AWS EC2, Heroku, Fly.io

**Quick steps**:
1. Provision PostgreSQL database (managed service recommended)
2. Provision Linux server
3. Clone repo, install dependencies
4. Configure `.env` with PostgreSQL connection string
5. Run migrations: `flask db upgrade`
6. Configure Gunicorn + systemd service
7. Configure Nginx reverse proxy + SSL (Certbot)
8. Access at `https://yourdomain.com`

---

## Testing

### Test Structure

- `tests/test_models/`: Unit tests for SQLAlchemy models
- `tests/test_routes/`: Route tests (HTTP requests/responses)
- `tests/test_utils/`: Utility function tests (rotation, countdown logic)
- `tests/test_integration/`: Full workflow tests (tenant isolation, auth flows)

### Key Test Patterns

**Tenant isolation tests**:
```python
def test_dashboard_tenant_isolation(test_app, family_a, family_b):
    # Create dashboards for two families
    dashboard_a = Dashboard(tenant_id=family_a.id, name="Dashboard A")
    dashboard_b = Dashboard(tenant_id=family_b.id, name="Dashboard B")
    db.session.add_all([dashboard_a, dashboard_b])
    db.session.commit()

    # Login as Family A user
    with test_app.test_client() as client:
        client.post('/login', data={'email': 'familya@example.com', 'password': 'password'})

        # Attempt to access Family B's dashboard
        response = client.get(f'/dashboard/{dashboard_b.id}')
        assert response.status_code == 404  # Tenant filter prevents access
```

**Form validation tests**:
```python
def test_task_form_emoji_required_when_icon_type_emoji():
    form = TaskForm(
        name='Test Task',
        dashboard_id=1,
        rotation=['Alice'],
        icon_type='emoji',
        emoji=''  # Missing emoji
    )
    assert form.validate() is False
    assert 'Emoji is required' in form.emoji.errors
```

---

## Security Considerations

### Tenant Isolation

**Critical**: All queries MUST filter by `tenant_id` to prevent cross-family data leaks.

- Use SQLAlchemy event listener for automatic filtering (see `models/__init__.py`)
- Manually validate tenant ownership in routes when bypassing automatic filter
- Test tenant isolation thoroughly in integration tests

### CSRF Protection

- All POST/PUT/DELETE routes protected via Flask-WTF
- CSRF token embedded in forms: `{{ form.hidden_tag() }}`
- HTMX includes CSRF token via meta tag + JavaScript

### File Upload Security

- Validate file type with WTForms `FileAllowed` validator
- Validate file integrity with Pillow `Image.open().verify()`
- Never trust user-supplied filename (use UUID)
- Store in tenant-scoped directories for isolation

### Password Security

- Werkzeug bcrypt hashing (via `generate_password_hash`)
- Minimum 8 characters enforced in forms
- Session timeout: 30 minutes (configurable)

---

## Performance Optimization

### Database Query Optimization

- Use `joinedload()` for eager loading (avoid N+1 queries)
- Add indexes on frequently queried columns (see `data-model.md`)
- Query optimization example:
  ```python
  Dashboard.query.options(
      joinedload(Dashboard.tasks),
      joinedload(Dashboard.countdowns)
  ).filter_by(id=dashboard_id).first()
  ```

### HTMX Polling Optimization

- Polling endpoint returns partial HTML only (no base template)
- Target response time: <500ms for good UX
- Use eager loading in polling endpoint

---

## Common Development Tasks

### Adding a New Model

1. Create model in `dinkydash/models/`
2. Import model in `dinkydash/models/__init__.py`
3. Generate migration: `flask db migrate -m "Add ModelName"`
4. Review migration file
5. Apply migration: `flask db upgrade`
6. Write tests in `tests/test_models/`

### Adding a New Route

1. Add route to appropriate blueprint (`routes/auth.py`, `routes/dashboard.py`, `routes/admin.py`)
2. Create form if needed (`forms/`)
3. Create template (`templates/`)
4. Add route specification to `/specs/001-multitenant-rewrite/contracts/routes.md`
5. Write route tests in `tests/test_routes/`

### Modifying the Database Schema

1. Update model in `dinkydash/models/`
2. Generate migration: `flask db migrate -m "Description"`
3. **Review migration carefully** (check for data loss)
4. Test on SQLite: `DATABASE_URL=sqlite:///test.db flask db upgrade`
5. Test on PostgreSQL (if available)
6. Backup production database before applying
7. Apply in production: `flask db upgrade`

---

## Troubleshooting

### Common Issues

**Database locked (SQLite)**:
- Stop all application processes
- Check for stale connections: `lsof dinkydash.db`

**Image uploads fail**:
- Check file permissions on `static/uploads/`
- Verify `MAX_CONTENT_LENGTH` in config
- Check Nginx `client_max_body_size` (cloud deployments)

**HTMX polling not working**:
- Check browser console for JavaScript errors
- Verify HTMX loaded: View page source, check `<script src="https://unpkg.com/htmx.org@1.9.10"></script>`
- Test polling endpoint: `curl -H "HX-Request: true" http://localhost:5000/dashboard/1/content`

**Tenant isolation not working**:
- Verify `g.current_tenant_id` set in `load_user()` function
- Check SQLAlchemy event listener registered (`models/__init__.py`)
- Write integration test to catch tenant leaks

---

## Project Governance

### Constitution

See `.specify/memory/constitution.md` for project principles:
1. **Database-First Design**: All data in relational database (SQLite or PostgreSQL)
2. **Multi-Tenancy & Authentication**: Row-level tenant isolation, secure sessions
3. **Traditional Web Architecture**: Server-side rendering with progressive enhancement
4. **Simplicity Over Features**: MVP focus, avoid complexity
5. **Living Documentation**: Schema documented in migrations, setup in quickstart.md

### Specification Workflow

See `SPECKIT.md` for workflow reference:
1. `/speckit.constitution` - Define project principles
2. `/speckit.specify` - Create feature specification (WHAT to build)
3. `/speckit.plan` - Generate implementation plan (HOW to build)
4. `/speckit.tasks` - Generate task list from plan
5. `/speckit.implement` - Execute tasks

---

## Additional Resources

- **Full Implementation Plan**: `/specs/001-multitenant-rewrite/plan.md`
- **Feature Specification**: `/specs/001-multitenant-rewrite/spec.md`
- **Deployment Guide**: `/specs/001-multitenant-rewrite/quickstart.md`
- **Database Schema**: `/specs/001-multitenant-rewrite/data-model.md`
- **Route Specifications**: `/specs/001-multitenant-rewrite/contracts/routes.md`
- **Form Specifications**: `/specs/001-multitenant-rewrite/contracts/forms.md`
- **Template Specifications**: `/specs/001-multitenant-rewrite/contracts/templates.md`

---

## Version History

- **v2.0.0** (In Progress): Multi-tenant web application rewrite
  - Flask + SQLAlchemy + PostgreSQL/SQLite
  - Multiple families with authentication
  - Multiple dashboards per family
  - HTMX progressive enhancement
  - Tenant-isolated image uploads

- **v1.x** (Legacy): Single-family config-based Pi dashboard
  - config.yaml-driven
  - No database, no authentication
  - Single dashboard per Pi
  - Static site generator for marketing site

---

**Note**: This project is undergoing active rewrite. Refer to `/specs/001-multitenant-rewrite/` for current state. Legacy v1.x code remains in repository for reference but will be replaced in v2.0.0 release.
