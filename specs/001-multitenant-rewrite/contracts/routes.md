# Flask Route Specifications

**Feature**: 001-multitenant-rewrite
**Date**: 2025-12-04
**Purpose**: Define Flask route endpoints, HTTP methods, authentication requirements, and response patterns

## Route Organization

Routes are organized into three Flask blueprints:

1. **auth.bp** - User authentication and registration
2. **dashboard.bp** - Dashboard viewing and polling
3. **admin.bp** - Dashboard, task, and countdown management

## Authentication Blueprint (`routes/auth.py`)

### POST /register

**Purpose**: Register new family account with first user

**Authentication**: None (public endpoint)

**Form**: `RegistrationForm` (from `forms/auth.py`)

**Request**:
- Method: POST
- Content-Type: application/x-www-form-urlencoded
- CSRF Token: Required (via Flask-WTF)

**Form Fields**:
```python
family_name: StringField       # validators=[DataRequired(), Length(max=100)]
email: EmailField              # validators=[DataRequired(), Email()]
password: PasswordField        # validators=[DataRequired(), Length(min=8)]
confirm_password: PasswordField # validators=[DataRequired(), EqualTo('password')]
```

**Success Response** (302 Redirect):
- Creates Family record with `family_name`
- Creates User record with `email`, hashed `password`, linked to family via `tenant_id`
- Creates default Dashboard named "Family Dashboard" with `is_default=True`
- Logs in user (session created)
- Redirects to: `/` (dashboard list)
- Flash message: "Welcome to DinkyDash! Your account has been created."

**Error Response** (200 OK):
- Re-renders `auth/register.html` with form errors
- Validation errors displayed per field
- Possible errors:
  - Email already registered (check uniqueness)
  - Password too short (<8 chars)
  - Passwords don't match
  - Invalid email format

**Related Requirements**: FR-001, FR-002, FR-003, FR-011 (auto-created dashboard)

---

### GET /register

**Purpose**: Display registration form

**Authentication**: None (public endpoint)

**Response** (200 OK):
- Renders `auth/register.html` with empty `RegistrationForm`
- CSRF token embedded in form

---

### POST /login

**Purpose**: Authenticate user and create session

**Authentication**: None (public endpoint)

**Form**: `LoginForm` (from `forms/auth.py`)

**Request**:
- Method: POST
- Content-Type: application/x-www-form-urlencoded
- CSRF Token: Required

**Form Fields**:
```python
email: EmailField           # validators=[DataRequired(), Email()]
password: PasswordField     # validators=[DataRequired()]
remember_me: BooleanField   # optional, default=False
```

**Success Response** (302 Redirect):
- Validates email/password against hashed password in database
- Creates session with `user_id`
- Sets `g.current_tenant_id` for tenant isolation
- If `remember_me=True`: Sets secure cookie (30-day expiry)
- Redirects to: `/` (dashboard list)
- Flash message: "Welcome back!"

**Error Response** (200 OK):
- Re-renders `auth/login.html` with form errors
- Generic error message: "Invalid email or password" (don't reveal which is wrong)

**Session Timeout**: 30 minutes (configurable via `PERMANENT_SESSION_LIFETIME`)

**Related Requirements**: FR-004, FR-005

---

### GET /login

**Purpose**: Display login form

**Authentication**: None (public endpoint)

**Response** (200 OK):
- Renders `auth/login.html` with empty `LoginForm`
- CSRF token embedded in form

---

### GET /logout

**Purpose**: End user session

**Authentication**: Required (logged-in users only)

**Request**:
- Method: GET (no CSRF needed for logout)

**Response** (302 Redirect):
- Clears session (calls `logout_user()` from Flask-Login)
- Clears `g.current_tenant_id`
- Redirects to: `/login`
- Flash message: "You have been logged out."

**Related Requirements**: FR-006

---

## Dashboard Blueprint (`routes/dashboard.py`)

### GET /

**Purpose**: List all dashboards for logged-in family

**Authentication**: Required (`@login_required` decorator)

**Query Parameters**: None

**Response** (200 OK):
- Queries all Dashboard records where `tenant_id = g.current_tenant_id`
- Orders by `is_default DESC, created_at ASC` (default dashboard first, then chronological)
- Renders `dashboard/list.html` with dashboard list
- Template shows:
  - Dashboard names as clickable links
  - "View" button for each dashboard (links to `/dashboard/<id>`)
  - "Create New Dashboard" button (links to `/admin/dashboards/new`)

**Response Data**:
```python
{
    'dashboards': [
        {
            'id': int,
            'name': str,
            'is_default': bool,
            'task_count': int,        # Count of tasks in this dashboard
            'countdown_count': int    # Count of countdowns in this dashboard
        },
        ...
    ]
}
```

**Edge Cases**:
- If no dashboards exist (shouldn't happen due to auto-created "Family Dashboard"): Show "Create Your First Dashboard" message
- If only one dashboard: Automatically redirect to `/dashboard/<id>` (skip list)

**Related Requirements**: FR-011, FR-012

---

### GET /dashboard/\<int:dashboard_id\>

**Purpose**: Display full dashboard view with tasks and countdowns

**Authentication**: Required (`@login_required` decorator)

**URL Parameters**:
- `dashboard_id`: integer (Dashboard primary key)

**Response** (200 OK):
- Validates dashboard belongs to current tenant: `Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.current_tenant_id).first_or_404()`
- Queries all Tasks for this dashboard with `joinedload(Task)` to avoid N+1
- Queries all Countdowns for this dashboard with `joinedload(Countdown)`
- Calculates current rotation for each task (via `utils.rotation.get_current_person()`)
- Calculates days remaining for each countdown (via `utils.countdown.calculate_days_remaining()`)
- Sorts countdowns by days remaining (soonest first)
- Renders `dashboard/view.html` with dashboard data
- Template includes HTMX polling directive: `hx-get="/dashboard/<id>/content" hx-trigger="every 30s"`
- Template includes meta refresh fallback: `<meta http-equiv="refresh" content="60">`

**Response Data**:
```python
{
    'dashboard': {
        'id': int,
        'name': str,
        'layout_size': str  # 'small', 'medium', 'large'
    },
    'tasks': [
        {
            'id': int,
            'name': str,
            'current_person': str,      # Calculated rotation
            'icon_type': str,           # 'emoji' or 'image'
            'icon_value': str           # Emoji text or image URL
        },
        ...
    ],
    'countdowns': [
        {
            'id': int,
            'name': str,
            'days_remaining': int,      # Calculated countdown
            'date_display': str,        # "March 21"
            'icon_type': str,
            'icon_value': str
        },
        ...
    ]
}
```

**Error Response** (404 Not Found):
- Dashboard does not exist or belongs to different tenant
- Renders `errors/404.html`

**Related Requirements**: FR-007, FR-008, FR-009, FR-010a (fallback refresh), FR-033 (layout size)

---

### GET /dashboard/\<int:dashboard_id\>/content

**Purpose**: HTMX polling endpoint - returns partial HTML for dashboard content

**Authentication**: Required (`@login_required` decorator)

**URL Parameters**:
- `dashboard_id`: integer

**Request Headers**:
- `HX-Request: true` (set by HTMX)

**Response** (200 OK):
- Same data query logic as `/dashboard/<id>` above
- Renders `dashboard/view.html` with `partial=True` context (renders only content section, no base template)
- Returns partial HTML snippet for HTMX to swap into page
- Response is lightweight (no full page structure)

**Response Format** (HTML Fragment):
```html
<div id="dashboard-content" hx-get="/dashboard/<id>/content" hx-trigger="every 30s" hx-swap="outerHTML">
    <!-- Task cards -->
    <!-- Countdown cards -->
</div>
```

**Performance Requirements**:
- Response time: <500ms (fast polling for good UX)
- Uses eager loading (`joinedload`) to avoid N+1 queries

**Error Handling**:
- If dashboard not found or tenant mismatch: Return 403 Forbidden (not 404, to avoid revealing dashboard existence)
- HTMX will retry on network failure (built-in behavior)

**Related Requirements**: FR-010 (30s polling), FR-020, FR-021

---

## Admin Blueprint (`routes/admin.py`)

All admin routes require authentication (`@login_required`) and enforce tenant isolation.

### Dashboard Management

#### GET /admin/dashboards

**Purpose**: List all dashboards for management (edit/delete)

**Authentication**: Required

**Response** (200 OK):
- Queries all Dashboard records where `tenant_id = g.current_tenant_id`
- Renders `admin/dashboards.html` with list
- Shows:
  - Dashboard name
  - Task/countdown counts
  - "Edit" button (links to `/admin/dashboards/<id>/edit`)
  - "Delete" button (links to `/admin/dashboards/<id>/delete`, requires confirmation)
  - "Create New Dashboard" button (links to `/admin/dashboards/new`)

**Related Requirements**: FR-012

---

#### GET /admin/dashboards/new

**Purpose**: Display form to create new dashboard

**Authentication**: Required

**Response** (200 OK):
- Renders `admin/dashboard_form.html` with empty `DashboardForm`
- Form fields:
  ```python
  name: StringField              # validators=[DataRequired(), Length(max=100)]
  layout_size: RadioField        # choices=[('small', 'Small'), ('medium', 'Medium'), ('large', 'Large')], default='medium'
  ```

**Related Requirements**: FR-013

---

#### POST /admin/dashboards/new

**Purpose**: Create new dashboard

**Authentication**: Required

**Form**: `DashboardForm` (from `forms/dashboard.py`)

**Request**:
- CSRF Token: Required

**Success Response** (302 Redirect):
- Creates Dashboard record with `tenant_id = g.current_tenant_id`
- Sets `is_default=False` (only first dashboard is default)
- Redirects to: `/admin/dashboards`
- Flash message: "Dashboard '{name}' created successfully."

**Error Response** (200 OK):
- Re-renders `admin/dashboard_form.html` with form errors
- Validation errors:
  - Name required
  - Name too long (>100 chars)
  - Layout size not in allowed values

**Related Requirements**: FR-013, FR-029, FR-030

---

#### GET /admin/dashboards/\<int:dashboard_id\>/edit

**Purpose**: Display form to edit existing dashboard

**Authentication**: Required

**URL Parameters**:
- `dashboard_id`: integer

**Response** (200 OK):
- Validates dashboard belongs to tenant: `Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.current_tenant_id).first_or_404()`
- Renders `admin/dashboard_form.html` with pre-filled `DashboardForm`
- Form fields populated with current dashboard data

**Error Response** (404 Not Found):
- Dashboard not found or belongs to different tenant

**Related Requirements**: FR-014, FR-031

---

#### POST /admin/dashboards/\<int:dashboard_id\>/edit

**Purpose**: Update existing dashboard

**Authentication**: Required

**Form**: `DashboardForm`

**Request**:
- CSRF Token: Required

**Success Response** (302 Redirect):
- Updates Dashboard record (validates `tenant_id` match)
- Redirects to: `/admin/dashboards`
- Flash message: "Dashboard '{name}' updated successfully."

**Error Response** (200 OK):
- Re-renders `admin/dashboard_form.html` with form errors

**Related Requirements**: FR-014, FR-031

---

#### POST /admin/dashboards/\<int:dashboard_id\>/delete

**Purpose**: Delete dashboard and reassign tasks/countdowns

**Authentication**: Required

**Request**:
- Method: POST (not GET, to prevent accidental deletion via URL)
- CSRF Token: Required
- Confirmation: Client-side confirmation dialog before POST

**Success Response** (302 Redirect):
- Validates dashboard belongs to tenant
- If this is the only dashboard: Return 400 Bad Request with message "Cannot delete last dashboard"
- If dashboard has tasks/countdowns:
  - Move all tasks and countdowns to default dashboard for this family
  - Or: Cascade delete if user confirms "Delete all items" (future enhancement)
- Deletes Dashboard record
- Redirects to: `/admin/dashboards`
- Flash message: "Dashboard '{name}' deleted. Items moved to default dashboard."

**Error Response**:
- 400 Bad Request: Cannot delete last dashboard
- 404 Not Found: Dashboard not found or belongs to different tenant

**Related Requirements**: FR-015, Edge Case: Deleting dashboard with tasks/countdowns

---

### Task Management

#### GET /admin/tasks

**Purpose**: List all tasks for current tenant (across all dashboards)

**Authentication**: Required

**Response** (200 OK):
- Queries all Task records where `dashboard_id IN (SELECT id FROM dashboards WHERE tenant_id = g.current_tenant_id)`
- Uses `joinedload(Task.dashboard)` to show dashboard name
- Renders `admin/tasks.html` with list
- Shows:
  - Task name
  - Dashboard name
  - Current rotation person (calculated)
  - Icon preview (emoji or image thumbnail)
  - "Edit" button (links to `/admin/tasks/<id>/edit`)
  - "Delete" button (links to `/admin/tasks/<id>/delete`)
  - "Create New Task" button (links to `/admin/tasks/new`)

**Related Requirements**: FR-017

---

#### GET /admin/tasks/new

**Purpose**: Display form to create new task

**Authentication**: Required

**Response** (200 OK):
- Renders `admin/task_form.html` with empty `TaskForm`
- Form fields:
  ```python
  name: StringField                   # validators=[DataRequired(), Length(max=100)]
  dashboard_id: SelectField           # choices=[(d.id, d.name) for d in user's dashboards], coerce=int
  rotation: FieldList(StringField)    # min_entries=1, validators=[DataRequired(), Length(max=100)] per entry
  icon_type: RadioField               # choices=[('emoji', 'Emoji'), ('image', 'Upload Image')], default='emoji'
  emoji: StringField                  # validators=[Optional(), Length(max=10)]
  image: FileField                    # validators=[Optional(), FileAllowed(['jpg', 'png', 'gif']), FileSize(max=5*1024*1024)]
  ```
- Dashboard dropdown populated with user's dashboards

**Related Requirements**: FR-018, FR-022a

---

#### POST /admin/tasks/new

**Purpose**: Create new task with rotation and icon

**Authentication**: Required

**Form**: `TaskForm` (from `forms/task.py`)

**Request**:
- CSRF Token: Required
- Content-Type: multipart/form-data (if image uploaded)

**Validation Logic**:
- If `icon_type='emoji'`: Require `emoji` field, ignore `image` field
- If `icon_type='image'`: Require `image` field, ignore `emoji` field
- Validate file type and size via Pillow (prevent malicious uploads)
- Validate dashboard_id belongs to current tenant

**Image Upload Handling**:
- Generate filename: `task_{task_id}_{uuid}.jpg` (or .png/.gif based on uploaded type)
- Save to: `static/uploads/{tenant_id}/task_{task_id}_{uuid}.jpg`
- Create tenant directory if not exists: `os.makedirs(f'static/uploads/{tenant_id}', exist_ok=True)`
- Store in database: `icon_type='image'`, `icon_value='/static/uploads/{tenant_id}/task_{task_id}_{uuid}.jpg'`

**Success Response** (302 Redirect):
- Creates Task record with:
  - `dashboard_id` (validated tenant ownership)
  - `name`
  - `rotation_json`: JSON array of rotation list `["Alice", "Bob", "Charlie"]`
  - `icon_type`: 'emoji' or 'image'
  - `icon_value`: emoji text or file path
- Redirects to: `/admin/tasks`
- Flash message: "Task '{name}' created successfully."

**Error Response** (200 OK):
- Re-renders `admin/task_form.html` with form errors
- Validation errors:
  - Name required
  - Dashboard required and must belong to tenant
  - Rotation must have at least 1 person
  - If icon_type='emoji': Emoji required
  - If icon_type='image': Image required, valid type (JPG/PNG/GIF), size <5MB

**Related Requirements**: FR-018, FR-019, FR-022a, FR-022b, FR-022c (validation)

---

#### GET /admin/tasks/\<int:task_id\>/edit

**Purpose**: Display form to edit existing task

**Authentication**: Required

**URL Parameters**:
- `task_id`: integer

**Response** (200 OK):
- Validates task belongs to tenant (via dashboard relationship):
  ```python
  task = Task.query.join(Dashboard).filter(
      Task.id == task_id,
      Dashboard.tenant_id == g.current_tenant_id
  ).first_or_404()
  ```
- Renders `admin/task_form.html` with pre-filled `TaskForm`
- Rotation list populated from `rotation_json` (parse JSON array)
- Existing icon displayed (emoji or image preview)

**Error Response** (404 Not Found):
- Task not found or belongs to different tenant

**Related Requirements**: FR-020

---

#### POST /admin/tasks/\<int:task_id\>/edit

**Purpose**: Update existing task

**Authentication**: Required

**Form**: `TaskForm`

**Request**:
- CSRF Token: Required
- Content-Type: multipart/form-data (if new image uploaded)

**Image Replacement Handling**:
- If user uploads new image:
  - Delete old image file from filesystem (if `icon_type='image'`)
  - Upload new image with new filename
  - Update `icon_value` in database
- If user switches from image to emoji:
  - Delete old image file from filesystem
  - Update `icon_type='emoji'`, `icon_value=emoji_text`

**Success Response** (302 Redirect):
- Updates Task record (validates tenant ownership via dashboard)
- Redirects to: `/admin/tasks`
- Flash message: "Task '{name}' updated successfully."

**Error Response** (200 OK):
- Re-renders `admin/task_form.html` with form errors

**Related Requirements**: FR-020, FR-022a

---

#### POST /admin/tasks/\<int:task_id\>/delete

**Purpose**: Delete task and associated image

**Authentication**: Required

**Request**:
- Method: POST
- CSRF Token: Required
- Confirmation: Client-side confirmation before POST

**Success Response** (302 Redirect):
- Validates task belongs to tenant (via dashboard)
- If task has `icon_type='image'`: Delete image file from filesystem
- Deletes Task record (CASCADE handled by SQLAlchemy)
- Redirects to: `/admin/tasks`
- Flash message: "Task '{name}' deleted successfully."

**Error Response**:
- 404 Not Found: Task not found or belongs to different tenant

**Related Requirements**: FR-021

---

### Countdown Management

Routes follow same pattern as Task Management, but with countdown-specific fields.

#### GET /admin/countdowns

**Purpose**: List all countdowns for current tenant (across all dashboards)

**Authentication**: Required

**Response** (200 OK):
- Queries all Countdown records via dashboard tenant filter
- Calculates days remaining for each countdown
- Sorts by days remaining (soonest first)
- Renders `admin/countdowns.html` with list
- Shows:
  - Countdown name
  - Dashboard name
  - Date (formatted "March 21")
  - Days remaining
  - Icon preview
  - "Edit" and "Delete" buttons

**Related Requirements**: FR-023

---

#### GET /admin/countdowns/new

**Purpose**: Display form to create new countdown

**Authentication**: Required

**Response** (200 OK):
- Renders `admin/countdown_form.html` with empty `CountdownForm`
- Form fields:
  ```python
  name: StringField                   # validators=[DataRequired(), Length(max=100)]
  dashboard_id: SelectField           # choices from user's dashboards
  date_month: SelectField             # choices=[(1, 'January'), ..., (12, 'December')]
  date_day: IntegerField              # validators=[DataRequired(), NumberRange(min=1, max=31)]
  icon_type: RadioField               # 'emoji' or 'image'
  emoji: StringField
  image: FileField
  ```

**Related Requirements**: FR-024, FR-032a

---

#### POST /admin/countdowns/new

**Purpose**: Create new countdown with icon

**Authentication**: Required

**Form**: `CountdownForm` (from `forms/countdown.py`)

**Validation Logic**:
- Same icon validation as Task (emoji XOR image)
- Validate date is valid (e.g., not February 31)
- Validate dashboard_id belongs to tenant

**Image Upload Handling**:
- Same pattern as Task: `static/uploads/{tenant_id}/countdown_{countdown_id}_{uuid}.jpg`

**Success Response** (302 Redirect):
- Creates Countdown record with `date_month`, `date_day`, `icon_type`, `icon_value`
- Redirects to: `/admin/countdowns`
- Flash message: "Countdown '{name}' created successfully."

**Error Response** (200 OK):
- Re-renders `admin/countdown_form.html` with form errors
- Validation errors:
  - Name required
  - Dashboard required and must belong to tenant
  - Date required and must be valid (e.g., not Feb 31)
  - Icon validation (same as Task)

**Related Requirements**: FR-024, FR-025, FR-032a, FR-032b (validation)

---

#### GET /admin/countdowns/\<int:countdown_id\>/edit

**Purpose**: Display form to edit existing countdown

**Authentication**: Required

**Response** (200 OK):
- Validates countdown belongs to tenant (via dashboard)
- Renders `admin/countdown_form.html` with pre-filled form
- Existing icon displayed

**Related Requirements**: FR-026

---

#### POST /admin/countdowns/\<int:countdown_id\>/edit

**Purpose**: Update existing countdown

**Authentication**: Required

**Form**: `CountdownForm`

**Image Replacement Handling**:
- Same pattern as Task edit (delete old, upload new, or switch to emoji)

**Success Response** (302 Redirect):
- Updates Countdown record (validates tenant ownership)
- Redirects to: `/admin/countdowns`
- Flash message: "Countdown '{name}' updated successfully."

**Related Requirements**: FR-026, FR-032a

---

#### POST /admin/countdowns/\<int:countdown_id\>/delete

**Purpose**: Delete countdown and associated image

**Authentication**: Required

**Request**:
- Method: POST
- CSRF Token: Required

**Success Response** (302 Redirect):
- Validates countdown belongs to tenant
- If `icon_type='image'`: Delete image file
- Deletes Countdown record
- Redirects to: `/admin/countdowns`
- Flash message: "Countdown '{name}' deleted successfully."

**Related Requirements**: FR-027

---

## Error Handlers

### 403 Forbidden

**Trigger**: Tenant isolation violation (accessing another family's data)

**Response** (403 Forbidden):
- Renders `errors/403.html`
- Message: "You don't have permission to access this resource."

### 404 Not Found

**Trigger**: Resource does not exist

**Response** (404 Not Found):
- Renders `errors/404.html`
- Message: "Page not found."

### 500 Internal Server Error

**Trigger**: Unhandled exception

**Response** (500 Internal Server Error):
- Calls `db.session.rollback()` to clean up transaction
- Renders `errors/500.html`
- Message: "Something went wrong. Please try again later."
- Logs exception to application log

## Security Considerations

### CSRF Protection

- All POST/PUT/DELETE routes require CSRF token (via Flask-WTF)
- CSRF token embedded in all forms
- HTMX inherits CSRF token from page context (set via meta tag or header)

### Tenant Isolation

- All queries filtered by `tenant_id` via SQLAlchemy event listener or manual filtering
- Dashboard/Task/Countdown queries validate tenant ownership before update/delete
- Use `filter_by(tenant_id=g.current_tenant_id)` consistently

### File Upload Security

- Validate file type via Pillow (prevents disguised malicious files)
- Validate file size (<5MB)
- Sanitize filenames (use UUID, don't trust user input)
- Store files in tenant-scoped directories
- Serve files through route that validates tenant access (or use web server with tenant check)

### Session Security

- Session timeout: 30 minutes
- Secure cookie flags: `httponly=True`, `secure=True` (in production)
- Remember me: Optional, 30-day expiry

## Performance Optimizations

### Database Query Optimization

- Use `joinedload()` for eager loading relationships (avoid N+1 queries)
- Example: `Dashboard.query.options(joinedload(Dashboard.tasks), joinedload(Dashboard.countdowns)).filter_by(id=dashboard_id).first()`
- Use indexed columns for filtering (see `data-model.md` for index strategy)

### HTMX Polling Optimization

- Polling endpoint returns partial HTML only (no base template)
- Response time target: <500ms for good UX
- Consider caching dashboard content (30s TTL) if performance degrades with many families (future enhancement)

### Static File Serving

- Serve uploaded images via Nginx/Apache in production (not Flask)
- Set appropriate cache headers (e.g., 1 day for uploaded images)

## Testing Considerations

### Route Tests (pytest)

- Test authenticated and unauthenticated access (verify `@login_required` works)
- Test CSRF protection (POST without token should fail)
- Test tenant isolation (Family A cannot access Family B's data)
- Test form validation (invalid inputs return errors)
- Test success/error paths for all CRUD operations

### Integration Tests

- Test full workflows: Register → Create Dashboard → Create Task → View Dashboard
- Test HTMX polling endpoint (verify partial HTML returned)
- Test image upload and retrieval
- Test dashboard deletion with task/countdown reassignment

### Security Tests

- Test SQL injection resistance (SQLAlchemy ORM provides protection)
- Test CSRF token validation
- Test tenant isolation thoroughly (attempt to access other tenant's data via URL manipulation)
- Test file upload validation (attempt to upload non-image, oversized file)
