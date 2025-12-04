# WTForms Specifications

**Feature**: 001-multitenant-rewrite
**Date**: 2025-12-04
**Purpose**: Define Flask-WTF form classes, field types, validators, and custom validation logic

## Form Organization

Forms are organized by feature area in `dinkydash/forms/`:

- `auth.py` - Registration and login forms
- `dashboard.py` - Dashboard create/edit form
- `task.py` - Task create/edit form
- `countdown.py` - Countdown create/edit form

## Authentication Forms (`forms/auth.py`)

### RegistrationForm

**Purpose**: New family registration with first user account

**Inherits**: `FlaskForm`

**Fields**:

```python
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from dinkydash.models import User

class RegistrationForm(FlaskForm):
    family_name = StringField(
        'Family Name',
        validators=[
            DataRequired(message='Family name is required'),
            Length(max=100, message='Family name must be 100 characters or fewer')
        ],
        render_kw={'placeholder': 'The Smith Family', 'autofocus': True}
    )

    email = EmailField(
        'Email Address',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Invalid email address')
        ],
        render_kw={'placeholder': 'family@example.com'}
    )

    password = PasswordField(
        'Password',
        validators=[
            DataRequired(message='Password is required'),
            Length(min=8, message='Password must be at least 8 characters long')
        ],
        render_kw={'placeholder': 'Enter password'}
    )

    confirm_password = PasswordField(
        'Confirm Password',
        validators=[
            DataRequired(message='Please confirm your password'),
            EqualTo('password', message='Passwords must match')
        ],
        render_kw={'placeholder': 'Re-enter password'}
    )

    def validate_email(self, field):
        """Custom validator: Ensure email is not already registered"""
        existing_user = User.query.filter_by(email=field.data.lower()).first()
        if existing_user:
            raise ValidationError('This email is already registered. Please log in instead.')
```

**Validation Order**:
1. Built-in validators (DataRequired, Email, Length, EqualTo)
2. Custom `validate_email()` method (checks uniqueness)

**Processing Notes**:
- Email should be normalized to lowercase before storing: `email.lower()`
- Password should be hashed using Werkzeug: `generate_password_hash(password)`

**Related Requirements**: FR-001, FR-002, FR-003

---

### LoginForm

**Purpose**: User authentication

**Inherits**: `FlaskForm`

**Fields**:

```python
class LoginForm(FlaskForm):
    email = EmailField(
        'Email Address',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Invalid email address')
        ],
        render_kw={'placeholder': 'family@example.com', 'autofocus': True}
    )

    password = PasswordField(
        'Password',
        validators=[
            DataRequired(message='Password is required')
        ],
        render_kw={'placeholder': 'Enter password'}
    )

    remember_me = BooleanField(
        'Remember Me',
        default=False,
        description='Keep me logged in for 30 days'
    )
```

**Validation Notes**:
- No custom validation needed (authentication happens in route, not form)
- Email normalized to lowercase for lookup: `email.lower()`

**Related Requirements**: FR-004, FR-005

---

## Dashboard Forms (`forms/dashboard.py`)

### DashboardForm

**Purpose**: Create or edit dashboard

**Inherits**: `FlaskForm`

**Fields**:

```python
from wtforms import RadioField

class DashboardForm(FlaskForm):
    name = StringField(
        'Dashboard Name',
        validators=[
            DataRequired(message='Dashboard name is required'),
            Length(max=100, message='Dashboard name must be 100 characters or fewer')
        ],
        render_kw={'placeholder': 'Kitchen Dashboard', 'autofocus': True}
    )

    layout_size = RadioField(
        'Element Size',
        choices=[
            ('small', 'Small (for phones and small screens)'),
            ('medium', 'Medium (default)'),
            ('large', 'Large (for TVs and large displays)')
        ],
        default='medium',
        validators=[DataRequired()],
        description='Adjust element size to fit your display'
    )
```

**Validation Notes**:
- No custom validation needed
- `layout_size` constrained to enum values by `choices` parameter

**Processing Notes**:
- Store `layout_size` directly in Dashboard.layout_size column (ENUM or VARCHAR)

**Related Requirements**: FR-013, FR-014, FR-029, FR-030, FR-031

---

## Task Forms (`forms/task.py`)

### TaskForm

**Purpose**: Create or edit recurring task with rotation and icon

**Inherits**: `FlaskForm`

**Fields**:

```python
from flask_wtf.file import FileField, FileAllowed, FileSize
from wtforms import FieldList, RadioField, SelectField, HiddenField
from wtforms.validators import Optional, ValidationError

class TaskForm(FlaskForm):
    name = StringField(
        'Task Name',
        validators=[
            DataRequired(message='Task name is required'),
            Length(max=100, message='Task name must be 100 characters or fewer')
        ],
        render_kw={'placeholder': 'Dishes', 'autofocus': True}
    )

    dashboard_id = SelectField(
        'Dashboard',
        coerce=int,
        validators=[DataRequired(message='Please select a dashboard')],
        description='Which dashboard should display this task?'
    )
    # Choices populated dynamically in route:
    # form.dashboard_id.choices = [(d.id, d.name) for d in current_user.family.dashboards]

    rotation = FieldList(
        StringField(
            'Person',
            validators=[
                DataRequired(message='Name is required'),
                Length(max=100, message='Name must be 100 characters or fewer')
            ],
            render_kw={'placeholder': 'Enter name'}
        ),
        min_entries=1,
        max_entries=365,  # Reasonable limit (one person per day of year)
        label='Rotation'
    )
    # JavaScript on template allows adding/removing entries dynamically

    icon_type = RadioField(
        'Icon Type',
        choices=[
            ('emoji', 'Use Emoji'),
            ('image', 'Upload Image')
        ],
        default='emoji',
        validators=[DataRequired()]
    )

    emoji = StringField(
        'Emoji',
        validators=[
            Optional(),
            Length(max=10, message='Emoji must be 10 characters or fewer')
        ],
        render_kw={'placeholder': '🍽', 'maxlength': '10'},
        description='Enter a single emoji character'
    )

    image = FileField(
        'Image',
        validators=[
            Optional(),
            FileAllowed(['jpg', 'jpeg', 'png', 'gif'], message='Images only (JPG, PNG, GIF)'),
            FileSize(max_size=5 * 1024 * 1024, message='Image must be smaller than 5MB')
        ],
        description='Upload JPG, PNG, or GIF (max 5MB)'
    )

    def validate(self, extra_validators=None):
        """Custom validation: Ensure icon_type matches provided icon data"""
        if not super().validate(extra_validators):
            return False

        if self.icon_type.data == 'emoji':
            if not self.emoji.data or self.emoji.data.strip() == '':
                self.emoji.errors.append('Emoji is required when icon type is Emoji')
                return False

        elif self.icon_type.data == 'image':
            # On edit, image might already exist (not required to re-upload)
            # Check if this is a new task or edit by looking for task_id
            # (task_id would be passed as hidden field or route parameter)
            if not self.image.data and not hasattr(self, 'existing_image'):
                self.image.errors.append('Image is required when icon type is Image')
                return False

        return True

    def validate_dashboard_id(self, field):
        """Custom validator: Ensure dashboard belongs to current tenant"""
        from flask import g
        from dinkydash.models import Dashboard

        dashboard = Dashboard.query.filter_by(
            id=field.data,
            tenant_id=g.current_tenant_id
        ).first()

        if not dashboard:
            raise ValidationError('Invalid dashboard selected')
```

**Validation Order**:
1. Per-field validators (DataRequired, Length, FileAllowed, FileSize)
2. Custom `validate()` method (icon_type XOR validation)
3. Custom `validate_dashboard_id()` method (tenant ownership check)

**Processing Notes**:
- Rotation list stored as JSON array: `json.dumps([person for person in form.rotation.data])`
- Image upload handling (if `icon_type='image'`):
  ```python
  import os
  import uuid
  from werkzeug.utils import secure_filename
  from PIL import Image

  def save_task_image(form_image, tenant_id, task_id):
      """Save uploaded image and return file path"""
      # Validate image with Pillow (prevents malicious files)
      try:
          img = Image.open(form_image)
          img.verify()
      except Exception:
          raise ValidationError('Invalid image file')

      # Generate unique filename
      ext = os.path.splitext(secure_filename(form_image.filename))[1]
      filename = f'task_{task_id}_{uuid.uuid4().hex}{ext}'

      # Create tenant directory if not exists
      upload_dir = os.path.join('static', 'uploads', str(tenant_id))
      os.makedirs(upload_dir, exist_ok=True)

      # Save file
      filepath = os.path.join(upload_dir, filename)
      form_image.seek(0)  # Reset file pointer after verify
      form_image.save(filepath)

      # Return relative path for database
      return f'/static/uploads/{tenant_id}/{filename}'
  ```

**Template Notes**:
- Use JavaScript to show/hide emoji vs image fields based on `icon_type` radio selection
- Use JavaScript to dynamically add/remove rotation entries (via "Add Person" and "Remove" buttons)

**Related Requirements**: FR-018, FR-019, FR-020, FR-022a, FR-022b, FR-022c

---

## Countdown Forms (`forms/countdown.py`)

### CountdownForm

**Purpose**: Create or edit countdown event with date and icon

**Inherits**: `FlaskForm`

**Fields**:

```python
from wtforms import IntegerField
from wtforms.validators import NumberRange

class CountdownForm(FlaskForm):
    name = StringField(
        'Event Name',
        validators=[
            DataRequired(message='Event name is required'),
            Length(max=100, message='Event name must be 100 characters or fewer')
        ],
        render_kw={'placeholder': "Alice's Birthday", 'autofocus': True}
    )

    dashboard_id = SelectField(
        'Dashboard',
        coerce=int,
        validators=[DataRequired(message='Please select a dashboard')],
        description='Which dashboard should display this countdown?'
    )
    # Choices populated dynamically in route

    date_month = SelectField(
        'Month',
        coerce=int,
        choices=[
            (1, 'January'), (2, 'February'), (3, 'March'),
            (4, 'April'), (5, 'May'), (6, 'June'),
            (7, 'July'), (8, 'August'), (9, 'September'),
            (10, 'October'), (11, 'November'), (12, 'December')
        ],
        validators=[DataRequired(message='Month is required')]
    )

    date_day = IntegerField(
        'Day',
        validators=[
            DataRequired(message='Day is required'),
            NumberRange(min=1, max=31, message='Day must be between 1 and 31')
        ],
        render_kw={'placeholder': '21', 'min': '1', 'max': '31'}
    )

    icon_type = RadioField(
        'Icon Type',
        choices=[
            ('emoji', 'Use Emoji'),
            ('image', 'Upload Image')
        ],
        default='emoji',
        validators=[DataRequired()]
    )

    emoji = StringField(
        'Emoji',
        validators=[
            Optional(),
            Length(max=10, message='Emoji must be 10 characters or fewer')
        ],
        render_kw={'placeholder': '🎂', 'maxlength': '10'},
        description='Enter a single emoji character'
    )

    image = FileField(
        'Image',
        validators=[
            Optional(),
            FileAllowed(['jpg', 'jpeg', 'png', 'gif'], message='Images only (JPG, PNG, GIF)'),
            FileSize(max_size=5 * 1024 * 1024, message='Image must be smaller than 5MB')
        ],
        description='Upload JPG, PNG, or GIF (max 5MB)'
    )

    def validate(self, extra_validators=None):
        """Custom validation: Icon XOR and valid date"""
        if not super().validate(extra_validators):
            return False

        # Icon type validation (same as TaskForm)
        if self.icon_type.data == 'emoji':
            if not self.emoji.data or self.emoji.data.strip() == '':
                self.emoji.errors.append('Emoji is required when icon type is Emoji')
                return False
        elif self.icon_type.data == 'image':
            if not self.image.data and not hasattr(self, 'existing_image'):
                self.image.errors.append('Image is required when icon type is Image')
                return False

        # Date validation: Check if date is valid (e.g., not Feb 31)
        import calendar
        month = self.date_month.data
        day = self.date_day.data

        if month and day:
            # Get max days in month (use non-leap year for Feb)
            max_days = calendar.monthrange(2023, month)[1]
            if day > max_days:
                self.date_day.errors.append(
                    f'{calendar.month_name[month]} only has {max_days} days'
                )
                return False

        return True

    def validate_dashboard_id(self, field):
        """Custom validator: Ensure dashboard belongs to current tenant"""
        from flask import g
        from dinkydash.models import Dashboard

        dashboard = Dashboard.query.filter_by(
            id=field.data,
            tenant_id=g.current_tenant_id
        ).first()

        if not dashboard:
            raise ValidationError('Invalid dashboard selected')
```

**Validation Order**:
1. Per-field validators (DataRequired, NumberRange, FileAllowed, FileSize)
2. Custom `validate()` method (icon XOR validation + date validity check)
3. Custom `validate_dashboard_id()` method (tenant ownership check)

**Processing Notes**:
- Date stored as two integer columns: `date_month` (1-12), `date_day` (1-31)
- Image upload handling same as TaskForm:
  ```python
  def save_countdown_image(form_image, tenant_id, countdown_id):
      # Same logic as save_task_image but with 'countdown_' prefix
      filename = f'countdown_{countdown_id}_{uuid.uuid4().hex}{ext}'
      # ... rest of logic
  ```

**Template Notes**:
- Use JavaScript to show/hide emoji vs image fields based on `icon_type`
- Optionally use JavaScript to dynamically adjust max day based on selected month

**Related Requirements**: FR-024, FR-025, FR-026, FR-032a, FR-032b

---

## Common Patterns

### CSRF Protection

All forms automatically include CSRF protection via `FlaskForm`:

**Template Usage**:
```jinja2
<form method="POST" action="{{ url_for('auth.register') }}">
    {{ form.hidden_tag() }}  <!-- Renders CSRF token -->

    <!-- Form fields -->
    {{ form.family_name.label }}
    {{ form.family_name() }}
    {% if form.family_name.errors %}
        <ul class="errors">
        {% for error in form.family_name.errors %}
            <li>{{ error }}</li>
        {% endfor %}
        </ul>
    {% endif %}

    <button type="submit">Register</button>
</form>
```

**HTMX Compatibility**:
HTMX automatically includes CSRF token in requests if set in meta tag:

```html
<meta name="csrf-token" content="{{ csrf_token() }}">
<script>
    document.body.addEventListener('htmx:configRequest', (event) => {
        event.detail.headers['X-CSRFToken'] = document.querySelector('meta[name="csrf-token"]').content;
    });
</script>
```

### Dynamic SelectField Choices

Dashboard and task/countdown forms populate `dashboard_id` choices dynamically in route:

```python
@admin_bp.route('/tasks/new', methods=['GET', 'POST'])
@login_required
def create_task():
    form = TaskForm()

    # Populate dashboard choices for current tenant
    form.dashboard_id.choices = [
        (d.id, d.name)
        for d in Dashboard.query.filter_by(tenant_id=g.current_tenant_id).order_by(Dashboard.name).all()
    ]

    if form.validate_on_submit():
        # ... handle form submission
```

### File Upload Handling

Both TaskForm and CountdownForm follow same pattern for image uploads:

1. Validate file type with WTForms validators (`FileAllowed`, `FileSize`)
2. Validate image integrity with Pillow (`Image.open().verify()`)
3. Generate unique filename with UUID
4. Save to tenant-scoped directory: `static/uploads/{tenant_id}/`
5. Store relative path in database: `/static/uploads/{tenant_id}/filename.jpg`

**Security Considerations**:
- Never trust user-supplied filename (use `secure_filename()` or UUID)
- Always validate file content with Pillow (prevents malicious files disguised as images)
- Store files in tenant-scoped directories for isolation
- Check file size before processing (use `FileSize` validator)

### FieldList Dynamic Entries

TaskForm rotation uses `FieldList` for dynamic person list:

**Template Implementation**:
```jinja2
<div id="rotation-container">
    {% for person_field in form.rotation %}
        <div class="rotation-entry">
            {{ person_field.label }}
            {{ person_field() }}
            {% if loop.index > 1 %}
                <button type="button" class="remove-person">Remove</button>
            {% endif %}
        </div>
    {% endfor %}
</div>
<button type="button" id="add-person">Add Person</button>

<script>
    // JavaScript to dynamically add/remove rotation entries
    document.getElementById('add-person').addEventListener('click', function() {
        const container = document.getElementById('rotation-container');
        const index = container.children.length;
        const newEntry = `
            <div class="rotation-entry">
                <label for="rotation-${index}">Person</label>
                <input type="text" name="rotation-${index}" id="rotation-${index}" placeholder="Enter name">
                <button type="button" class="remove-person">Remove</button>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', newEntry);
    });

    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-person')) {
            e.target.closest('.rotation-entry').remove();
        }
    });
</script>
```

## Error Handling

### Form Validation Errors

WTForms provides per-field error lists accessible in templates:

```jinja2
{% if form.errors %}
    <div class="alert alert-error">
        <p>Please correct the following errors:</p>
        <ul>
        {% for field, errors in form.errors.items() %}
            {% for error in errors %}
                <li>{{ form[field].label.text }}: {{ error }}</li>
            {% endfor %}
        {% endfor %}
        </ul>
    </div>
{% endif %}
```

### Custom Validation Error Messages

All validators include custom error messages for clarity:

```python
DataRequired(message='Family name is required')  # Instead of generic "This field is required"
Length(max=100, message='Family name must be 100 characters or fewer')
Email(message='Invalid email address')
```

### Field-Level vs Form-Level Validation

- **Field-level**: Use built-in validators or custom `validate_<field>()` methods
- **Form-level**: Override `validate()` method for cross-field validation (e.g., icon_type XOR)

## Testing Considerations

### Form Validation Tests (pytest)

Test each form independently:

```python
def test_registration_form_valid_data():
    form = RegistrationForm(
        family_name='Test Family',
        email='test@example.com',
        password='password123',
        confirm_password='password123'
    )
    assert form.validate() is True

def test_registration_form_password_too_short():
    form = RegistrationForm(
        family_name='Test Family',
        email='test@example.com',
        password='short',
        confirm_password='short'
    )
    assert form.validate() is False
    assert 'Password must be at least 8 characters long' in form.password.errors

def test_registration_form_email_already_registered(test_app, test_user):
    with test_app.test_request_context():
        form = RegistrationForm(
            family_name='Test Family',
            email=test_user.email,  # Existing user
            password='password123',
            confirm_password='password123'
        )
        assert form.validate() is False
        assert 'This email is already registered' in form.email.errors
```

### File Upload Tests

Test file validation:

```python
from werkzeug.datastructures import FileStorage
from io import BytesIO

def test_task_form_invalid_file_type():
    # Create a text file disguised as image
    fake_image = FileStorage(
        stream=BytesIO(b"This is not an image"),
        filename="fake.jpg",
        content_type="image/jpeg"
    )

    form = TaskForm(
        name='Test Task',
        dashboard_id=1,
        rotation=['Alice'],
        icon_type='image',
        image=fake_image
    )

    assert form.validate() is False
    # Pillow validation should catch this in route processing

def test_task_form_file_too_large():
    # Create a 6MB file (exceeds 5MB limit)
    large_file = FileStorage(
        stream=BytesIO(b"x" * (6 * 1024 * 1024)),
        filename="large.jpg",
        content_type="image/jpeg"
    )

    form = TaskForm(
        name='Test Task',
        dashboard_id=1,
        rotation=['Alice'],
        icon_type='image',
        image=large_file
    )

    assert form.validate() is False
    assert 'Image must be smaller than 5MB' in form.image.errors
```

### Dynamic SelectField Tests

Test dashboard choices population:

```python
def test_task_form_dashboard_choices(test_app, test_user):
    with test_app.test_request_context():
        g.current_tenant_id = test_user.tenant_id

        form = TaskForm()
        form.dashboard_id.choices = [
            (d.id, d.name)
            for d in Dashboard.query.filter_by(tenant_id=test_user.tenant_id).all()
        ]

        assert len(form.dashboard_id.choices) > 0
        assert all(isinstance(choice[0], int) for choice in form.dashboard_id.choices)
```

## Flask-WTF Configuration

Required Flask configuration for form functionality:

```python
# config.py
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # CSRF tokens don't expire
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max upload size
```

## Custom Validators

### FileSize Validator

Flask-WTF doesn't include a FileSize validator by default, so implement custom:

```python
# dinkydash/forms/validators.py
from wtforms.validators import ValidationError

class FileSize:
    """Validates file size"""
    def __init__(self, max_size, message=None):
        self.max_size = max_size
        if not message:
            message = f'File must be smaller than {max_size} bytes'
        self.message = message

    def __call__(self, form, field):
        if field.data:
            field.data.seek(0, 2)  # Seek to end
            size = field.data.tell()
            field.data.seek(0)  # Reset to beginning

            if size > self.max_size:
                raise ValidationError(self.message)
```

Usage:
```python
from dinkydash.forms.validators import FileSize

image = FileField(
    'Image',
    validators=[
        FileSize(max_size=5 * 1024 * 1024, message='Image must be smaller than 5MB')
    ]
)
```

## Internationalization (Future Enhancement)

Forms are structured to support i18n:

```python
from flask_babel import lazy_gettext as _l

family_name = StringField(
    _l('Family Name'),
    validators=[
        DataRequired(message=_l('Family name is required'))
    ]
)
```

Not implemented in MVP (Principle IV: Simplicity), but documented for future.
