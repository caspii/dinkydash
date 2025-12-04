# Jinja2 Template Specifications

**Feature**: 001-multitenant-rewrite
**Date**: 2025-12-04
**Purpose**: Define Jinja2 template structure, HTMX integration, layout patterns, and rendering logic

## Template Organization

Templates are organized by feature area in `dinkydash/templates/`:

```text
templates/
├── base.html                   # Base template with HTMX, CSRF, meta refresh
├── auth/
│   ├── register.html           # Registration form
│   └── login.html              # Login form
├── dashboard/
│   ├── list.html               # Dashboard switcher (list of dashboards)
│   └── view.html               # Dashboard display with tasks/countdowns
├── admin/
│   ├── dashboards.html         # Dashboard management list
│   ├── dashboard_form.html     # Dashboard create/edit form
│   ├── tasks.html              # Task management list
│   ├── task_form.html          # Task create/edit form
│   ├── countdowns.html         # Countdown management list
│   └── countdown_form.html     # Countdown create/edit form
└── errors/
    ├── 403.html                # Forbidden error
    ├── 404.html                # Not found error
    └── 500.html                # Internal server error
```

## Base Template (`templates/base.html`)

**Purpose**: Shared layout for all pages with HTMX, CSRF, and progressive enhancement

**Template**:

```jinja2
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token() }}">

    <title>{% block title %}DinkyDash{% endblock %}</title>

    <!-- CSS -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">

    <!-- HTMX for progressive enhancement -->
    <script src="https://unpkg.com/htmx.org@1.9.10" integrity="sha384-D1Kt99CQMDuVetoL1lrYwg5t+9QdHe7NLX/SoJYkXDFfX37iInKRy5xLSi8nO7UC" crossorigin="anonymous"></script>

    <!-- Configure HTMX to include CSRF token -->
    <script>
        document.body.addEventListener('htmx:configRequest', (event) => {
            event.detail.headers['X-CSRFToken'] = document.querySelector('meta[name="csrf-token"]').content;
        });
    </script>

    <!-- Fallback meta refresh for no-JS (only on dashboard pages) -->
    {% if not request.headers.get('HX-Request') and request.endpoint == 'dashboard.view_dashboard' %}
    <meta http-equiv="refresh" content="60">
    {% endif %}

    {% block extra_head %}{% endblock %}
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar">
        <div class="container">
            <a href="{{ url_for('dashboard.dashboard_list') }}" class="logo">DinkyDash</a>

            {% if current_user.is_authenticated %}
            <ul class="nav-links">
                <li><a href="{{ url_for('dashboard.dashboard_list') }}">Dashboards</a></li>
                <li><a href="{{ url_for('admin.list_tasks') }}">Tasks</a></li>
                <li><a href="{{ url_for('admin.list_countdowns') }}">Countdowns</a></li>
                <li><a href="{{ url_for('admin.list_dashboards') }}">Manage</a></li>
                <li><a href="{{ url_for('auth.logout') }}">Logout</a></li>
            </ul>
            <span class="family-name">{{ current_user.family.name }}</span>
            {% else %}
            <ul class="nav-links">
                <li><a href="{{ url_for('auth.login') }}">Login</a></li>
                <li><a href="{{ url_for('auth.register') }}">Register</a></li>
            </ul>
            {% endif %}
        </div>
    </nav>

    <!-- Flash messages -->
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
        <div class="container">
            {% for category, message in messages %}
            <div class="alert alert-{{ category }}">
                {{ message }}
                <button type="button" class="alert-close">&times;</button>
            </div>
            {% endfor %}
        </div>
        {% endif %}
    {% endwith %}

    <!-- Main content -->
    <main class="container">
        {% block content %}{% endblock %}
    </main>

    <!-- Footer -->
    <footer class="footer">
        <div class="container">
            <p>&copy; 2025 DinkyDash. Built for families.</p>
        </div>
    </footer>

    <!-- JavaScript for alert dismissal -->
    <script>
        document.querySelectorAll('.alert-close').forEach(button => {
            button.addEventListener('click', () => {
                button.parentElement.remove();
            });
        });
    </script>

    {% block extra_scripts %}{% endblock %}
</body>
</html>
```

**Key Features**:
- **CSRF Token**: Embedded in meta tag for HTMX
- **HTMX**: Loaded from CDN with integrity hash
- **Meta Refresh Fallback**: Only on dashboard view when JS disabled
- **Navigation**: Shows family name, links to key sections
- **Flash Messages**: Auto-dismissible alerts
- **Progressive Enhancement**: Works without JavaScript

**Related Requirements**: FR-010a (meta refresh), FR-020, FR-021

---

## Authentication Templates

### Registration Form (`templates/auth/register.html`)

**Purpose**: Display registration form for new family

**Template**:

```jinja2
{% extends "base.html" %}

{% block title %}Register - DinkyDash{% endblock %}

{% block content %}
<div class="auth-container">
    <h1>Register Your Family</h1>
    <p class="subtitle">Create a DinkyDash account to get started.</p>

    <form method="POST" action="{{ url_for('auth.register') }}" class="auth-form">
        {{ form.hidden_tag() }}

        <div class="form-group">
            {{ form.family_name.label }}
            {{ form.family_name(class="form-control") }}
            {% if form.family_name.errors %}
                <ul class="errors">
                {% for error in form.family_name.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-group">
            {{ form.email.label }}
            {{ form.email(class="form-control") }}
            {% if form.email.errors %}
                <ul class="errors">
                {% for error in form.email.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-group">
            {{ form.password.label }}
            {{ form.password(class="form-control") }}
            {% if form.password.errors %}
                <ul class="errors">
                {% for error in form.password.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-group">
            {{ form.confirm_password.label }}
            {{ form.confirm_password(class="form-control") }}
            {% if form.confirm_password.errors %}
                <ul class="errors">
                {% for error in form.confirm_password.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <button type="submit" class="btn btn-primary">Register</button>
    </form>

    <p class="auth-footer">
        Already have an account? <a href="{{ url_for('auth.login') }}">Login here</a>
    </p>
</div>
{% endblock %}
```

**Related Requirements**: FR-001, FR-002, FR-003

---

### Login Form (`templates/auth/login.html`)

**Purpose**: Display login form for existing users

**Template**:

```jinja2
{% extends "base.html" %}

{% block title %}Login - DinkyDash{% endblock %}

{% block content %}
<div class="auth-container">
    <h1>Welcome Back</h1>
    <p class="subtitle">Login to access your family dashboard.</p>

    <form method="POST" action="{{ url_for('auth.login') }}" class="auth-form">
        {{ form.hidden_tag() }}

        <div class="form-group">
            {{ form.email.label }}
            {{ form.email(class="form-control") }}
            {% if form.email.errors %}
                <ul class="errors">
                {% for error in form.email.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-group">
            {{ form.password.label }}
            {{ form.password(class="form-control") }}
            {% if form.password.errors %}
                <ul class="errors">
                {% for error in form.password.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-group form-check">
            {{ form.remember_me(class="form-check-input") }}
            {{ form.remember_me.label(class="form-check-label") }}
            <small class="form-text">{{ form.remember_me.description }}</small>
        </div>

        <button type="submit" class="btn btn-primary">Login</button>
    </form>

    <p class="auth-footer">
        Don't have an account? <a href="{{ url_for('auth.register') }}">Register here</a>
    </p>
</div>
{% endblock %}
```

**Related Requirements**: FR-004, FR-005

---

## Dashboard Templates

### Dashboard List (`templates/dashboard/list.html`)

**Purpose**: List all dashboards for family (dashboard switcher)

**Template**:

```jinja2
{% extends "base.html" %}

{% block title %}Your Dashboards - DinkyDash{% endblock %}

{% block content %}
<div class="dashboard-list-container">
    <div class="header">
        <h1>Your Dashboards</h1>
        <a href="{{ url_for('admin.create_dashboard') }}" class="btn btn-primary">Create New Dashboard</a>
    </div>

    {% if dashboards %}
    <div class="dashboard-grid">
        {% for dashboard in dashboards %}
        <div class="dashboard-card {% if dashboard.is_default %}default{% endif %}">
            <h2>{{ dashboard.name }}</h2>
            {% if dashboard.is_default %}
            <span class="badge badge-default">Default</span>
            {% endif %}

            <div class="dashboard-stats">
                <span>{{ dashboard.task_count }} tasks</span>
                <span>{{ dashboard.countdown_count }} countdowns</span>
            </div>

            <a href="{{ url_for('dashboard.view_dashboard', dashboard_id=dashboard.id) }}" class="btn btn-secondary">View Dashboard</a>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="empty-state">
        <p>You don't have any dashboards yet.</p>
        <a href="{{ url_for('admin.create_dashboard') }}" class="btn btn-primary">Create Your First Dashboard</a>
    </div>
    {% endif %}
</div>
{% endblock %}
```

**Auto-Redirect Logic** (in route, not template):
```python
if len(dashboards) == 1:
    return redirect(url_for('dashboard.view_dashboard', dashboard_id=dashboards[0].id))
```

**Related Requirements**: FR-011, FR-012

---

### Dashboard View (`templates/dashboard/view.html`)

**Purpose**: Display dashboard with tasks and countdowns, HTMX polling

**Template**:

```jinja2
{% extends "base.html" %}

{% block title %}{{ dashboard.name }} - DinkyDash{% endblock %}

{% block content %}
<div class="dashboard-view-container layout-{{ dashboard.layout_size }}">
    <div class="dashboard-header">
        <h1>{{ dashboard.name }}</h1>
        <a href="{{ url_for('admin.edit_dashboard', dashboard_id=dashboard.id) }}" class="btn btn-secondary">Edit Layout</a>
    </div>

    <!-- HTMX polling container -->
    <div id="dashboard-content"
         hx-get="{{ url_for('dashboard.dashboard_content', dashboard_id=dashboard.id) }}"
         hx-trigger="every 30s"
         hx-swap="outerHTML">

        <!-- Tasks Section -->
        {% if tasks %}
        <section class="tasks-section">
            <h2>Today's Tasks</h2>
            <div class="task-grid">
                {% for task in tasks %}
                <div class="task-card">
                    <div class="task-icon">
                        {% if task.icon_type == 'emoji' %}
                            <span class="emoji">{{ task.icon_value }}</span>
                        {% elif task.icon_type == 'image' %}
                            <img src="{{ task.icon_value }}" alt="{{ task.name }} icon">
                        {% endif %}
                    </div>
                    <div class="task-info">
                        <h3>{{ task.name }}</h3>
                        <p class="current-person">{{ task.current_person }}</p>
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>
        {% endif %}

        <!-- Countdowns Section -->
        {% if countdowns %}
        <section class="countdowns-section">
            <h2>Upcoming Events</h2>
            <div class="countdown-grid">
                {% for countdown in countdowns %}
                <div class="countdown-card">
                    <div class="countdown-icon">
                        {% if countdown.icon_type == 'emoji' %}
                            <span class="emoji">{{ countdown.icon_value }}</span>
                        {% elif countdown.icon_type == 'image' %}
                            <img src="{{ countdown.icon_value }}" alt="{{ countdown.name }} icon">
                        {% endif %}
                    </div>
                    <div class="countdown-info">
                        <h3>{{ countdown.name }}</h3>
                        <p class="countdown-date">{{ countdown.date_display }}</p>
                        <p class="countdown-days">
                            {% if countdown.days_remaining == 0 %}
                                Today!
                            {% elif countdown.days_remaining == 1 %}
                                Tomorrow
                            {% else %}
                                {{ countdown.days_remaining }} days
                            {% endif %}
                        </p>
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>
        {% endif %}

        <!-- Empty State -->
        {% if not tasks and not countdowns %}
        <div class="empty-state">
            <p>This dashboard is empty. Add some tasks or countdowns to get started!</p>
            <a href="{{ url_for('admin.create_task') }}" class="btn btn-primary">Add Task</a>
            <a href="{{ url_for('admin.create_countdown') }}" class="btn btn-primary">Add Countdown</a>
        </div>
        {% endif %}

    </div> <!-- End HTMX polling container -->
</div>
{% endblock %}
```

**CSS Classes for Layout Sizes**:
```css
/* CSS adjusts card sizes based on layout-{size} class */
.dashboard-view-container.layout-small .task-card,
.dashboard-view-container.layout-small .countdown-card {
    font-size: 0.875rem;
    padding: 0.75rem;
}

.dashboard-view-container.layout-medium .task-card,
.dashboard-view-container.layout-medium .countdown-card {
    font-size: 1rem;
    padding: 1rem;
}

.dashboard-view-container.layout-large .task-card,
.dashboard-view-container.layout-large .countdown-card {
    font-size: 1.5rem;
    padding: 1.5rem;
}
```

**HTMX Polling Behavior**:
- Polls `/dashboard/<id>/content` every 30 seconds
- Swaps entire `#dashboard-content` div with response (outerHTML)
- Automatically retries on network failure
- Stops polling when user navigates away

**Fallback Meta Refresh** (in base.html):
- Reloads entire page every 60 seconds if JavaScript disabled

**Related Requirements**: FR-007, FR-008, FR-009, FR-010, FR-010a, FR-033 (layout size)

---

## Admin Templates

### Dashboard Management List (`templates/admin/dashboards.html`)

**Purpose**: List all dashboards for management (edit/delete)

**Template**:

```jinja2
{% extends "base.html" %}

{% block title %}Manage Dashboards - DinkyDash{% endblock %}

{% block content %}
<div class="admin-container">
    <div class="header">
        <h1>Manage Dashboards</h1>
        <a href="{{ url_for('admin.create_dashboard') }}" class="btn btn-primary">Create New Dashboard</a>
    </div>

    {% if dashboards %}
    <table class="admin-table">
        <thead>
            <tr>
                <th>Name</th>
                <th>Layout Size</th>
                <th>Tasks</th>
                <th>Countdowns</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for dashboard in dashboards %}
            <tr>
                <td>
                    {{ dashboard.name }}
                    {% if dashboard.is_default %}
                    <span class="badge badge-default">Default</span>
                    {% endif %}
                </td>
                <td>{{ dashboard.layout_size|capitalize }}</td>
                <td>{{ dashboard.task_count }}</td>
                <td>{{ dashboard.countdown_count }}</td>
                <td class="actions">
                    <a href="{{ url_for('dashboard.view_dashboard', dashboard_id=dashboard.id) }}" class="btn btn-sm btn-secondary">View</a>
                    <a href="{{ url_for('admin.edit_dashboard', dashboard_id=dashboard.id) }}" class="btn btn-sm btn-secondary">Edit</a>
                    {% if not dashboard.is_default or dashboards|length > 1 %}
                    <form method="POST" action="{{ url_for('admin.delete_dashboard', dashboard_id=dashboard.id) }}" style="display:inline;" onsubmit="return confirm('Delete {{ dashboard.name }}? Items will be moved to default dashboard.');">
                        {{ csrf_token() }}
                        <button type="submit" class="btn btn-sm btn-danger">Delete</button>
                    </form>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty-state">
        <p>No dashboards found.</p>
    </div>
    {% endif %}
</div>
{% endblock %}
```

**Related Requirements**: FR-012, FR-015

---

### Dashboard Form (`templates/admin/dashboard_form.html`)

**Purpose**: Create or edit dashboard

**Template**:

```jinja2
{% extends "base.html" %}

{% block title %}{% if dashboard %}Edit{% else %}Create{% endif %} Dashboard - DinkyDash{% endblock %}

{% block content %}
<div class="admin-container">
    <h1>{% if dashboard %}Edit{% else %}Create{% endif %} Dashboard</h1>

    <form method="POST" class="admin-form">
        {{ form.hidden_tag() }}

        <div class="form-group">
            {{ form.name.label }}
            {{ form.name(class="form-control") }}
            {% if form.name.errors %}
                <ul class="errors">
                {% for error in form.name.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-group">
            {{ form.layout_size.label }}
            <p class="form-help">{{ form.layout_size.description }}</p>
            {% for subfield in form.layout_size %}
                <div class="form-radio">
                    {{ subfield }}
                    {{ subfield.label }}
                </div>
            {% endfor %}
            {% if form.layout_size.errors %}
                <ul class="errors">
                {% for error in form.layout_size.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-actions">
            <button type="submit" class="btn btn-primary">{% if dashboard %}Save Changes{% else %}Create Dashboard{% endif %}</button>
            <a href="{{ url_for('admin.list_dashboards') }}" class="btn btn-secondary">Cancel</a>
        </div>
    </form>
</div>
{% endblock %}
```

**Related Requirements**: FR-013, FR-014, FR-029, FR-030, FR-031

---

### Task Management List (`templates/admin/tasks.html`)

**Purpose**: List all tasks for management (edit/delete)

**Template**:

```jinja2
{% extends "base.html" %}

{% block title %}Manage Tasks - DinkyDash{% endblock %}

{% block content %}
<div class="admin-container">
    <div class="header">
        <h1>Manage Tasks</h1>
        <a href="{{ url_for('admin.create_task') }}" class="btn btn-primary">Create New Task</a>
    </div>

    {% if tasks %}
    <table class="admin-table">
        <thead>
            <tr>
                <th>Icon</th>
                <th>Name</th>
                <th>Dashboard</th>
                <th>Current Person</th>
                <th>Rotation Size</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for task in tasks %}
            <tr>
                <td class="icon-cell">
                    {% if task.icon_type == 'emoji' %}
                        <span class="emoji-preview">{{ task.icon_value }}</span>
                    {% elif task.icon_type == 'image' %}
                        <img src="{{ task.icon_value }}" alt="Icon" class="icon-preview">
                    {% endif %}
                </td>
                <td>{{ task.name }}</td>
                <td>{{ task.dashboard.name }}</td>
                <td>{{ task.current_person }}</td>
                <td>{{ task.rotation|length }} people</td>
                <td class="actions">
                    <a href="{{ url_for('admin.edit_task', task_id=task.id) }}" class="btn btn-sm btn-secondary">Edit</a>
                    <form method="POST" action="{{ url_for('admin.delete_task', task_id=task.id) }}" style="display:inline;" onsubmit="return confirm('Delete {{ task.name }}?');">
                        {{ csrf_token() }}
                        <button type="submit" class="btn btn-sm btn-danger">Delete</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty-state">
        <p>No tasks found. Create your first task to get started!</p>
        <a href="{{ url_for('admin.create_task') }}" class="btn btn-primary">Create Task</a>
    </div>
    {% endif %}
</div>
{% endblock %}
```

**Related Requirements**: FR-017

---

### Task Form (`templates/admin/task_form.html`)

**Purpose**: Create or edit task with rotation and icon

**Template**:

```jinja2
{% extends "base.html" %}

{% block title %}{% if task %}Edit{% else %}Create{% endif %} Task - DinkyDash{% endblock %}

{% block content %}
<div class="admin-container">
    <h1>{% if task %}Edit{% else %}Create{% endif %} Task</h1>

    <form method="POST" enctype="multipart/form-data" class="admin-form">
        {{ form.hidden_tag() }}

        <div class="form-group">
            {{ form.name.label }}
            {{ form.name(class="form-control") }}
            {% if form.name.errors %}
                <ul class="errors">
                {% for error in form.name.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-group">
            {{ form.dashboard_id.label }}
            {{ form.dashboard_id(class="form-control") }}
            <p class="form-help">{{ form.dashboard_id.description }}</p>
            {% if form.dashboard_id.errors %}
                <ul class="errors">
                {% for error in form.dashboard_id.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-group">
            {{ form.rotation.label }}
            <div id="rotation-container">
                {% for person_field in form.rotation %}
                <div class="rotation-entry">
                    {{ person_field(class="form-control", placeholder="Enter name") }}
                    {% if loop.index > 1 %}
                        <button type="button" class="btn btn-sm btn-danger remove-person">Remove</button>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            <button type="button" id="add-person" class="btn btn-sm btn-secondary">Add Person</button>
            {% if form.rotation.errors %}
                <ul class="errors">
                {% for error in form.rotation.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-group">
            {{ form.icon_type.label }}
            {% for subfield in form.icon_type %}
                <div class="form-radio">
                    {{ subfield }}
                    {{ subfield.label }}
                </div>
            {% endfor %}
        </div>

        <div class="form-group" id="emoji-field" style="display:none;">
            {{ form.emoji.label }}
            {{ form.emoji(class="form-control") }}
            <p class="form-help">{{ form.emoji.description }}</p>
            {% if form.emoji.errors %}
                <ul class="errors">
                {% for error in form.emoji.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-group" id="image-field" style="display:none;">
            {{ form.image.label }}
            {{ form.image(class="form-control") }}
            <p class="form-help">{{ form.image.description }}</p>
            {% if task and task.icon_type == 'image' %}
                <p class="current-image">
                    Current image: <img src="{{ task.icon_value }}" alt="Current icon" class="icon-preview">
                </p>
            {% endif %}
            {% if form.image.errors %}
                <ul class="errors">
                {% for error in form.image.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-actions">
            <button type="submit" class="btn btn-primary">{% if task %}Save Changes{% else %}Create Task{% endif %}</button>
            <a href="{{ url_for('admin.list_tasks') }}" class="btn btn-secondary">Cancel</a>
        </div>
    </form>
</div>
{% endblock %}

{% block extra_scripts %}
<script>
    // Show/hide icon fields based on icon_type selection
    const iconTypeRadios = document.querySelectorAll('input[name="icon_type"]');
    const emojiField = document.getElementById('emoji-field');
    const imageField = document.getElementById('image-field');

    function updateIconFields() {
        const selectedType = document.querySelector('input[name="icon_type"]:checked').value;
        if (selectedType === 'emoji') {
            emojiField.style.display = 'block';
            imageField.style.display = 'none';
        } else {
            emojiField.style.display = 'none';
            imageField.style.display = 'block';
        }
    }

    iconTypeRadios.forEach(radio => {
        radio.addEventListener('change', updateIconFields);
    });

    // Initialize on page load
    updateIconFields();

    // Dynamic rotation entries
    let rotationIndex = {{ form.rotation|length }};

    document.getElementById('add-person').addEventListener('click', function() {
        const container = document.getElementById('rotation-container');
        const newEntry = document.createElement('div');
        newEntry.className = 'rotation-entry';
        newEntry.innerHTML = `
            <input type="text" name="rotation-${rotationIndex}" class="form-control" placeholder="Enter name">
            <button type="button" class="btn btn-sm btn-danger remove-person">Remove</button>
        `;
        container.appendChild(newEntry);
        rotationIndex++;
    });

    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-person')) {
            e.target.closest('.rotation-entry').remove();
        }
    });
</script>
{% endblock %}
```

**Related Requirements**: FR-018, FR-019, FR-020, FR-022a, FR-022b

---

### Countdown Management List (`templates/admin/countdowns.html`)

**Purpose**: List all countdowns for management (edit/delete)

**Template**:

```jinja2
{% extends "base.html" %}

{% block title %}Manage Countdowns - DinkyDash{% endblock %}

{% block content %}
<div class="admin-container">
    <div class="header">
        <h1>Manage Countdowns</h1>
        <a href="{{ url_for('admin.create_countdown') }}" class="btn btn-primary">Create New Countdown</a>
    </div>

    {% if countdowns %}
    <table class="admin-table">
        <thead>
            <tr>
                <th>Icon</th>
                <th>Name</th>
                <th>Dashboard</th>
                <th>Date</th>
                <th>Days Remaining</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for countdown in countdowns %}
            <tr>
                <td class="icon-cell">
                    {% if countdown.icon_type == 'emoji' %}
                        <span class="emoji-preview">{{ countdown.icon_value }}</span>
                    {% elif countdown.icon_type == 'image' %}
                        <img src="{{ countdown.icon_value }}" alt="Icon" class="icon-preview">
                    {% endif %}
                </td>
                <td>{{ countdown.name }}</td>
                <td>{{ countdown.dashboard.name }}</td>
                <td>{{ countdown.date_display }}</td>
                <td>
                    {% if countdown.days_remaining == 0 %}
                        Today!
                    {% elif countdown.days_remaining == 1 %}
                        Tomorrow
                    {% else %}
                        {{ countdown.days_remaining }} days
                    {% endif %}
                </td>
                <td class="actions">
                    <a href="{{ url_for('admin.edit_countdown', countdown_id=countdown.id) }}" class="btn btn-sm btn-secondary">Edit</a>
                    <form method="POST" action="{{ url_for('admin.delete_countdown', countdown_id=countdown.id) }}" style="display:inline;" onsubmit="return confirm('Delete {{ countdown.name }}?');">
                        {{ csrf_token() }}
                        <button type="submit" class="btn btn-sm btn-danger">Delete</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty-state">
        <p>No countdowns found. Create your first countdown to get started!</p>
        <a href="{{ url_for('admin.create_countdown') }}" class="btn btn-primary">Create Countdown</a>
    </div>
    {% endif %}
</div>
{% endblock %}
```

**Related Requirements**: FR-023

---

### Countdown Form (`templates/admin/countdown_form.html`)

**Purpose**: Create or edit countdown with date and icon

**Template**:

```jinja2
{% extends "base.html" %}

{% block title %}{% if countdown %}Edit{% else %}Create{% endif %} Countdown - DinkyDash{% endblock %}

{% block content %}
<div class="admin-container">
    <h1>{% if countdown %}Edit{% else %}Create{% endif %} Countdown</h1>

    <form method="POST" enctype="multipart/form-data" class="admin-form">
        {{ form.hidden_tag() }}

        <div class="form-group">
            {{ form.name.label }}
            {{ form.name(class="form-control") }}
            {% if form.name.errors %}
                <ul class="errors">
                {% for error in form.name.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-group">
            {{ form.dashboard_id.label }}
            {{ form.dashboard_id(class="form-control") }}
            <p class="form-help">{{ form.dashboard_id.description }}</p>
            {% if form.dashboard_id.errors %}
                <ul class="errors">
                {% for error in form.dashboard_id.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-row">
            <div class="form-group">
                {{ form.date_month.label }}
                {{ form.date_month(class="form-control") }}
                {% if form.date_month.errors %}
                    <ul class="errors">
                    {% for error in form.date_month.errors %}
                        <li>{{ error }}</li>
                    {% endfor %}
                    </ul>
                {% endif %}
            </div>

            <div class="form-group">
                {{ form.date_day.label }}
                {{ form.date_day(class="form-control") }}
                {% if form.date_day.errors %}
                    <ul class="errors">
                    {% for error in form.date_day.errors %}
                        <li>{{ error }}</li>
                    {% endfor %}
                    </ul>
                {% endif %}
            </div>
        </div>

        <div class="form-group">
            {{ form.icon_type.label }}
            {% for subfield in form.icon_type %}
                <div class="form-radio">
                    {{ subfield }}
                    {{ subfield.label }}
                </div>
            {% endfor %}
        </div>

        <div class="form-group" id="emoji-field" style="display:none;">
            {{ form.emoji.label }}
            {{ form.emoji(class="form-control") }}
            <p class="form-help">{{ form.emoji.description }}</p>
            {% if form.emoji.errors %}
                <ul class="errors">
                {% for error in form.emoji.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-group" id="image-field" style="display:none;">
            {{ form.image.label }}
            {{ form.image(class="form-control") }}
            <p class="form-help">{{ form.image.description }}</p>
            {% if countdown and countdown.icon_type == 'image' %}
                <p class="current-image">
                    Current image: <img src="{{ countdown.icon_value }}" alt="Current icon" class="icon-preview">
                </p>
            {% endif %}
            {% if form.image.errors %}
                <ul class="errors">
                {% for error in form.image.errors %}
                    <li>{{ error }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </div>

        <div class="form-actions">
            <button type="submit" class="btn btn-primary">{% if countdown %}Save Changes{% else %}Create Countdown{% endif %}</button>
            <a href="{{ url_for('admin.list_countdowns') }}" class="btn btn-secondary">Cancel</a>
        </div>
    </form>
</div>
{% endblock %}

{% block extra_scripts %}
<script>
    // Show/hide icon fields based on icon_type selection
    const iconTypeRadios = document.querySelectorAll('input[name="icon_type"]');
    const emojiField = document.getElementById('emoji-field');
    const imageField = document.getElementById('image-field');

    function updateIconFields() {
        const selectedType = document.querySelector('input[name="icon_type"]:checked').value;
        if (selectedType === 'emoji') {
            emojiField.style.display = 'block';
            imageField.style.display = 'none';
        } else {
            emojiField.style.display = 'none';
            imageField.style.display = 'block';
        }
    }

    iconTypeRadios.forEach(radio => {
        radio.addEventListener('change', updateIconFields);
    });

    // Initialize on page load
    updateIconFields();
</script>
{% endblock %}
```

**Related Requirements**: FR-024, FR-025, FR-026, FR-032a, FR-032b

---

## Error Templates

### 403 Forbidden (`templates/errors/403.html`)

```jinja2
{% extends "base.html" %}

{% block title %}Access Denied - DinkyDash{% endblock %}

{% block content %}
<div class="error-container">
    <h1>403</h1>
    <h2>Access Denied</h2>
    <p>You don't have permission to access this resource.</p>
    <a href="{{ url_for('dashboard.dashboard_list') }}" class="btn btn-primary">Go to Dashboards</a>
</div>
{% endblock %}
```

### 404 Not Found (`templates/errors/404.html`)

```jinja2
{% extends "base.html" %}

{% block title %}Page Not Found - DinkyDash{% endblock %}

{% block content %}
<div class="error-container">
    <h1>404</h1>
    <h2>Page Not Found</h2>
    <p>The page you're looking for doesn't exist.</p>
    <a href="{{ url_for('dashboard.dashboard_list') }}" class="btn btn-primary">Go to Dashboards</a>
</div>
{% endblock %}
```

### 500 Internal Server Error (`templates/errors/500.html`)

```jinja2
{% extends "base.html" %}

{% block title %}Server Error - DinkyDash{% endblock %}

{% block content %}
<div class="error-container">
    <h1>500</h1>
    <h2>Something Went Wrong</h2>
    <p>We're sorry, but something went wrong. Please try again later.</p>
    <a href="{{ url_for('dashboard.dashboard_list') }}" class="btn btn-primary">Go to Dashboards</a>
</div>
{% endblock %}
```

---

## CSS Strategy

### Layout Size Classes

CSS uses `.layout-{size}` classes to adjust element sizes dynamically:

```css
/* Base styles */
.task-card, .countdown-card {
    padding: 1rem;
    font-size: 1rem;
    border: 1px solid #ddd;
    border-radius: 8px;
    text-align: center;
}

/* Small layout (phones) */
.layout-small .task-card,
.layout-small .countdown-card {
    padding: 0.75rem;
    font-size: 0.875rem;
}

.layout-small .emoji {
    font-size: 2rem;
}

.layout-small img {
    max-width: 64px;
}

/* Medium layout (default) */
.layout-medium .task-card,
.layout-medium .countdown-card {
    padding: 1rem;
    font-size: 1rem;
}

.layout-medium .emoji {
    font-size: 3rem;
}

.layout-medium img {
    max-width: 128px;
}

/* Large layout (TVs) */
.layout-large .task-card,
.layout-large .countdown-card {
    padding: 1.5rem;
    font-size: 1.5rem;
}

.layout-large .emoji {
    font-size: 5rem;
}

.layout-large img {
    max-width: 256px;
}
```

**Related Requirements**: FR-033

---

## Template Macros (Future Enhancement)

For DRY templates, consider extracting common patterns to macros:

```jinja2
<!-- templates/macros/form_field.html -->
{% macro render_field(field) %}
    <div class="form-group">
        {{ field.label }}
        {{ field(class="form-control") }}
        {% if field.errors %}
            <ul class="errors">
            {% for error in field.errors %}
                <li>{{ error }}</li>
            {% endfor %}
            </ul>
        {% endif %}
    </div>
{% endmacro %}

<!-- Usage in form templates -->
{% from "macros/form_field.html" import render_field %}
{{ render_field(form.name) }}
{{ render_field(form.email) }}
```

Not implemented in MVP (Principle IV: Simplicity), but documented for future refactoring.

---

## Testing Considerations

### Template Rendering Tests

Test that templates render correctly with expected data:

```python
def test_dashboard_view_renders_tasks(test_app, test_dashboard, test_task):
    with test_app.test_client() as client:
        # Login as test user
        client.post('/login', data={'email': 'test@example.com', 'password': 'password123'})

        # Request dashboard view
        response = client.get(f'/dashboard/{test_dashboard.id}')

        assert response.status_code == 200
        assert test_task.name in response.data.decode()
        assert 'hx-get' in response.data.decode()  # Verify HTMX polling
        assert 'hx-trigger="every 30s"' in response.data.decode()

def test_dashboard_view_empty_state(test_app, test_dashboard):
    with test_app.test_client() as client:
        client.post('/login', data={'email': 'test@example.com', 'password': 'password123'})
        response = client.get(f'/dashboard/{test_dashboard.id}')

        assert 'This dashboard is empty' in response.data.decode()
        assert 'Add Task' in response.data.decode()
```

### HTMX Polling Tests

Test that polling endpoint returns partial HTML:

```python
def test_dashboard_content_endpoint(test_app, test_dashboard, test_task):
    with test_app.test_client() as client:
        client.post('/login', data={'email': 'test@example.com', 'password': 'password123'})

        # Request polling endpoint with HX-Request header
        response = client.get(
            f'/dashboard/{test_dashboard.id}/content',
            headers={'HX-Request': 'true'}
        )

        assert response.status_code == 200
        assert test_task.name in response.data.decode()
        assert 'hx-get' in response.data.decode()  # Verify polling continues
        assert '<!DOCTYPE html>' not in response.data.decode()  # Partial HTML only
```

### Form Rendering Tests

Test that forms render with CSRF and validation errors:

```python
def test_registration_form_renders_csrf(test_app):
    with test_app.test_client() as client:
        response = client.get('/register')

        assert response.status_code == 200
        assert 'csrf_token' in response.data.decode()

def test_registration_form_shows_validation_errors(test_app):
    with test_app.test_client() as client:
        response = client.post('/register', data={
            'family_name': '',  # Invalid: required
            'email': 'invalid-email',  # Invalid: format
            'password': 'short',  # Invalid: length
            'confirm_password': 'different'  # Invalid: mismatch
        })

        assert response.status_code == 200
        assert 'Family name is required' in response.data.decode()
        assert 'Invalid email address' in response.data.decode()
        assert 'Password must be at least 8 characters' in response.data.decode()
        assert 'Passwords must match' in response.data.decode()
```

## Accessibility Considerations (Future Enhancement)

Templates should include accessibility improvements:

- **Semantic HTML**: Use `<nav>`, `<main>`, `<section>`, `<article>` tags
- **ARIA labels**: Add `aria-label` to icon-only buttons
- **Keyboard navigation**: Ensure all interactive elements are keyboard-accessible
- **Focus management**: Set focus to first form field with `autofocus`
- **Alt text**: Add descriptive alt text to all images

Not fully implemented in MVP, but basic semantic HTML and alt text are included.

**Related Requirements**: Edge case "Accessibility for non-visual users"
