# Research: Multi-Tenant Web Application

**Feature**: 001-multitenant-rewrite
**Date**: 2025-12-04
**Purpose**: Document technology decisions, patterns, and best practices for DinkyDash rewrite

## Technology Decisions

### 1. Flask vs FastAPI vs Django

**Decision**: Flask 3.0+

**Rationale**:
- **Simplicity**: Flask is lightweight and doesn't impose structure (aligns with Principle IV: Simplicity)
- **Flexibility**: Easy to add only what's needed (no admin panel, no unnecessary ORM features)
- **Server-side rendering**: Excellent Jinja2 integration for traditional web architecture (Principle III)
- **Ecosystem**: Flask-Login, Flask-WTF, Flask-Migrate are mature, well-documented extensions
- **Performance**: Sufficient for 50+ families with moderate traffic
- **Learning curve**: Accessible to developers with basic Python knowledge

**Alternatives Considered**:
- **FastAPI**: Modern, fast, but optimized for APIs not server-side rendering; would require additional templating setup
- **Django**: Full-featured but heavy; admin panel and many features unnecessary for MVP; would violate Simplicity principle

### 2. SQLAlchemy ORM vs Direct SQL

**Decision**: SQLAlchemy 2.0+ with declarative models

**Rationale**:
- **Database portability**: Single codebase supports SQLite and PostgreSQL (Principle I: Database-First)
- **SQL injection prevention**: Parameterized queries built-in (Security requirement)
- **Migration support**: Alembic (via Flask-Migrate) handles schema evolution
- **Tenant isolation**: Can implement query filters at ORM level for automatic tenant_id filtering
- **Type safety**: Modern SQLAlchemy 2.0 with type hints improves maintainability

**Alternatives Considered**:
- **Direct SQL**: More performant but loses portability, requires manual query sanitization, error-prone for tenant isolation
- **Django ORM**: Tied to Django framework

**Implementation Pattern**:
```python
# Base model with automatic tenant filtering
class TenantMixin:
    tenant_id = Column(Integer, ForeignKey('families.id'), nullable=False)

    @classmethod
    def query_for_tenant(cls, tenant_id):
        return db.session.query(cls).filter_by(tenant_id=tenant_id)
```

### 3. Authentication: Flask-Login vs Flask-Security vs Custom

**Decision**: Flask-Login with Werkzeug password hashing

**Rationale**:
- **Simplicity**: Flask-Login handles session management only; perfect for MVP
- **Security**: Werkzeug provides bcrypt-based hashing (Principle II: Multi-Tenancy & Authentication)
- **Flexibility**: Easy to add password reset later without framework constraints
- **Standard**: Industry-standard pattern, well-documented

**Alternatives Considered**:
- **Flask-Security**: Too many features (roles, permissions) not needed for MVP
- **Custom auth**: Reinventing wheel, higher security risk

**Implementation Details**:
- Session timeout: 30 minutes (configurable)
- CSRF protection via Flask-WTF
- Remember me: Optional checkbox (secure cookie with 30-day expiry)

### 4. HTMX vs Alpine.js vs Vanilla JS

**Decision**: HTMX 1.9+ (CDN)

**Rationale**:
- **Progressive enhancement**: Works via HTML attributes, degrades gracefully (Principle III)
- **Minimal footprint**: 14KB, no build step required
- **Server-side focus**: Fetches HTML from server, no client-side state management
- **Simplicity**: Declarative syntax, no JavaScript knowledge required for basic usage

**Alternatives Considered**:
- **Alpine.js**: More client-side logic, not needed for simple polling
- **Vanilla JS**: More code to maintain, HTMX is more declarative

**Usage Pattern**:
```html
<!-- Dashboard auto-refresh every 30s -->
<div hx-get="/dashboard/{{ dashboard.id }}/content"
     hx-trigger="every 30s"
     hx-swap="outerHTML">
  <!-- Dashboard content -->
</div>

<!-- Fallback for no-JS -->
<meta http-equiv="refresh" content="60">
```

### 5. Image Storage: Filesystem vs S3 vs Database BLOBs

**Decision**: Filesystem with tenant-scoped directories

**Rationale**:
- **Simplicity**: No external service required for Pi deployment (Principle IV)
- **Performance**: Faster than database BLOBs, web server can serve directly
- **Scalability**: Can migrate to S3 later without code changes (URL abstraction)
- **Cost**: Free on Pi, cheap on cloud (local filesystem)

**Alternatives Considered**:
- **S3/Object storage**: Adds complexity, cost; overkill for MVP with <5MB images
- **Database BLOBs**: Poor performance, bloats database backups

**Storage Pattern**:
```
static/uploads/
├── {tenant_id}/
│   ├── task_{task_id}.jpg
│   └── countdown_{countdown_id}.png
```

**Security**:
- Validate file type (JPG, PNG, GIF) via Pillow
- Validate file size (<5MB)
- Sanitize filenames to prevent directory traversal
- Serve with tenant check before file access

### 6. Database Migrations: Alembic Direct vs Flask-Migrate

**Decision**: Flask-Migrate (Alembic wrapper)

**Rationale**:
- **Flask integration**: Commands work with Flask CLI (`flask db upgrade`)
- **Simplicity**: Abstraction over Alembic reduces boilerplate
- **Auto-generation**: Can detect model changes and generate migrations
- **Standard**: De facto standard for Flask + SQLAlchemy projects

**Migration Strategy**:
- Auto-generate initial schema from models
- Manual review of all migrations before commit
- Test both upgrade and downgrade paths
- Test on SQLite and PostgreSQL before deployment

### 7. Forms: Flask-WTF vs Custom Forms

**Decision**: Flask-WTF with WTForms

**Rationale**:
- **CSRF protection**: Built-in token generation and validation
- **Validation**: Declarative validators (Email, Length, DataRequired, etc.)
- **File uploads**: FileField with validation support
- **Error handling**: Automatic error message rendering in templates

**Form Pattern**:
```python
class TaskForm(FlaskForm):
    name = StringField('Task Name', validators=[DataRequired(), Length(max=100)])
    rotation = FieldList(StringField('Person'), min_entries=1)
    icon_type = RadioField('Icon Type', choices=[('emoji', 'Emoji'), ('image', 'Image')])
    emoji = StringField('Emoji')
    image = FileField('Image', validators=[FileAllowed(['jpg', 'png', 'gif'])])
    dashboard_id = SelectField('Dashboard', coerce=int)
```

### 8. Testing Strategy

**Decision**: pytest with pytest-flask

**Testing Layers**:

1. **Unit Tests**: Models, utilities (rotation logic, countdown calculations)
   - Fast, isolated, no database required for utilities
   - Use in-memory SQLite for model tests

2. **Route Tests**: HTTP requests/responses, form submissions
   - Test authenticated and unauthenticated states
   - Verify CSRF protection
   - Test tenant isolation (cannot access other family data)

3. **Integration Tests**: Full workflows (register → create task → view dashboard)
   - Test on both SQLite and PostgreSQL
   - Verify migrations work correctly
   - Test image upload and serving

**Coverage Goals**:
- Models: 90%+
- Routes: 85%+
- Utils: 95%+
- Overall: 85%+

### 9. Configuration Management

**Decision**: Environment variables with config classes

**Configuration Levels**:
```python
# config.py
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///dinkydash.db'
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dinkydash-dev.db'

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
```

**Environment Variables**:
- `FLASK_ENV`: development, production, testing
- `SECRET_KEY`: Random 32-byte hex string
- `DATABASE_URL`: Connection string (sqlite:// or postgresql://)
- `UPLOAD_FOLDER`: Path to image uploads directory

### 10. Tenant Isolation Pattern

**Decision**: SQLAlchemy event listeners for automatic filtering

**Pattern**:
```python
# models/__init__.py
from sqlalchemy import event
from flask import g

class TenantModel(db.Model):
    __abstract__ = True
    tenant_id = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)

# Automatic tenant filtering on all queries
@event.listens_for(db.session, 'before_compile', retval=True)
def apply_tenant_filter(query):
    if hasattr(g, 'current_tenant_id'):
        # Apply filter to all TenantModel subclasses
        for entity in query.column_descriptions:
            if hasattr(entity['type'], 'tenant_id'):
                query = query.filter(entity['type'].tenant_id == g.current_tenant_id)
    return query

# Set tenant context from logged-in user
@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    if user:
        g.current_tenant_id = user.tenant_id
    return user
```

**Benefits**:
- Automatic protection against tenant data leaks
- No need to manually add tenant_id filters to every query
- Centralized enforcement point

**Caveat**:
- Must explicitly bypass for admin operations (if needed later)
- Must test thoroughly to ensure no edge cases

## Best Practices

### Flask Application Factory Pattern

Use factory pattern for testability and configuration flexibility:

```python
# dinkydash/__init__.py
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from dinkydash.routes import auth, dashboard, admin
    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(admin.bp)

    return app
```

### Jinja2 Template Inheritance

Base template with HTMX for all pages:

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}DinkyDash{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    {% if not request.headers.get('HX-Request') %}
    <!-- Fallback meta refresh for no-JS -->
    <meta http-equiv="refresh" content="60">
    {% endif %}
</head>
<body>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
            <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    {% block content %}{% endblock %}
</body>
</html>
```

### Blueprint Organization

Separate concerns by feature:

- **auth.bp** (`/register`, `/login`, `/logout`)
- **dashboard.bp** (`/`, `/dashboard/<id>`, `/dashboard/<id>/content`)
- **admin.bp** (`/admin/tasks`, `/admin/countdowns`, `/admin/dashboards`)

### Error Handling

Custom error pages with tenant context preserved:

```python
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500
```

## Security Considerations

### Password Reset Flow

**Pattern** (to be implemented post-MVP):
1. User requests reset → generates time-limited token (30min expiry)
2. Token stored in database with user_id and expiry
3. Email sent with reset link containing token
4. User clicks link → validates token not expired
5. User sets new password → token invalidated

**Libraries**:
- `itsdangerous` for URL-safe token generation
- Flask-Mail for email sending (optional for Pi deployment)

### CSRF Protection Strategy

- All POST/PUT/DELETE forms include CSRF token
- Flask-WTF auto-generates and validates tokens
- HTMX inherits CSRF from page context

### Input Validation

- WTForms validators for all user input
- Pillow for image file validation (prevents malicious files)
- SQLAlchemy ORM prevents SQL injection
- HTML escaping via Jinja2 (auto-enabled)

## Performance Optimization

### Database Indexing

Critical indexes for query performance:

```sql
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_tasks_dashboard_id ON tasks(dashboard_id);
CREATE INDEX idx_countdowns_dashboard_id ON countdowns(dashboard_id);
CREATE INDEX idx_dashboards_tenant_id ON dashboards(tenant_id);
```

### Query Optimization

- Use `joinedload` for eager loading relationships (avoid N+1 queries)
- Example: `Dashboard.query.options(joinedload(Dashboard.tasks), joinedload(Dashboard.countdowns)).filter_by(id=dashboard_id).first()`

### Caching Strategy (Future Enhancement)

Not implemented in MVP (Principle IV: Simplicity) but documented for future:
- Flask-Caching for dashboard content (30s TTL)
- Invalidate on task/countdown updates
- Per-tenant cache keys

## Deployment Considerations

### Raspberry Pi Deployment

**Requirements**:
- Python 3.11+ (from apt or pyenv)
- SQLite 3.x (included in OS)
- Nginx (reverse proxy)
- Gunicorn (WSGI server)
- systemd service for auto-start

**Resource Limits**:
- Gunicorn workers: 2 (Pi has 4GB RAM, keep <512MB per app)
- Database: SQLite sufficient for 50 families
- Uploads: Monitor disk space (automatic cleanup of orphaned images)

### Cloud Deployment (Optional)

**Platforms**: DigitalOcean, Heroku, Fly.io, Railway
**Requirements**:
- PostgreSQL database (managed service recommended)
- Environment variables for configuration
- File storage: Local filesystem or S3 (future)
- Horizontal scaling: Load balancer + multiple app instances

### Migration from v1.x

**Strategy**:
1. Export data from config.yaml to CSV/JSON
2. Create migration script: `scripts/migrate_v1_to_v2.py`
3. Import data:
   - Create default family account
   - Create default dashboard
   - Import recurring tasks
   - Import countdowns
4. Preserve image files (copy from old structure to tenant-scoped structure)

## Open Questions Resolved

1. **Q**: Should we use Flask-Security for auth?
   **A**: No, Flask-Login is sufficient. Flask-Security adds unnecessary complexity (roles, permissions) not needed for MVP.

2. **Q**: How to handle database migrations on Pi?
   **A**: Apply migrations on app startup in production mode. If migration fails, app won't start (fail-fast).

3. **Q**: Should images be stored in database?
   **A**: No, filesystem is simpler and more performant. Can migrate to S3 later if needed.

4. **Q**: How to enforce tenant isolation?
   **A**: SQLAlchemy event listeners automatically filter queries by tenant_id. Centralized, harder to bypass accidentally.

5. **Q**: Should we build an image library feature?
   **A**: No, direct upload per item for MVP. Image library adds complexity (management UI, gallery, selection) that violates Simplicity principle.

6. **Q**: How to handle concurrent edits?
   **A**: Last-write-wins for MVP. Optimistic locking (version column) can be added later if needed.

7. **Q**: Should dashboard support real-time updates (WebSockets)?
   **A**: No, 30-second HTMX polling is sufficient for family dashboard use case. WebSockets add significant complexity.

8. **Q**: How to test tenant isolation?
   **A**: Integration tests that:
   - Create two families with distinct data
   - Authenticate as Family A
   - Attempt to access Family B's data via URL manipulation
   - Assert 403 Forbidden or data not returned

## References

- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/)
- [Flask-Login Documentation](https://flask-login.readthedocs.io/)
- [HTMX Documentation](https://htmx.org/docs/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [12 Factor App](https://12factor.net/) (for deployment best practices)
