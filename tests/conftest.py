"""
Pytest configuration and fixtures for DinkyDash tests.
"""
import pytest
from dinkydash import create_app
from dinkydash.models import db, Family, User, Dashboard, Task, Countdown
from dinkydash.utils.auth import hash_password
import json


@pytest.fixture
def app():
    """Create and configure a test Flask application."""
    from dinkydash.config import TestConfig

    app = create_app(TestConfig)

    # Create database tables
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def family(app):
    """Create a test family."""
    with app.app_context():
        family = Family(name="Test Family")
        db.session.add(family)
        db.session.commit()
        # Refresh to load all attributes
        db.session.refresh(family)
        family_id = family.id
        family_name = family.name

    # Create a detached object to return
    family_obj = Family(name=family_name)
    family_obj.id = family_id
    return family_obj


@pytest.fixture
def user(app, family):
    """Create a test user."""
    with app.app_context():
        user = User(
            email="test@example.com",
            password_hash=hash_password("testpassword123"),
            tenant_id=family.id
        )
        db.session.add(user)
        db.session.commit()
        # Store user data before session closes
        user_id = user.id
        user_email = user.email
        user_password_hash = user.password_hash
        user_tenant_id = user.tenant_id

    # Create a detached object to return
    user_obj = User(
        email=user_email,
        password_hash=user_password_hash,
        tenant_id=user_tenant_id
    )
    user_obj.id = user_id
    return user_obj


@pytest.fixture
def auth_client(client, user):
    """Create an authenticated test client."""
    # Login the user
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
    return client


@pytest.fixture
def dashboard(app, family):
    """Create a test dashboard."""
    with app.app_context():
        dashboard = Dashboard(
            tenant_id=family.id,
            name="Test Dashboard",
            layout_size="medium",
            is_default=True
        )
        db.session.add(dashboard)
        db.session.commit()
        # Store data before session closes
        dashboard_id = dashboard.id
        dashboard_tenant_id = dashboard.tenant_id
        dashboard_name = dashboard.name
        dashboard_layout_size = dashboard.layout_size
        dashboard_is_default = dashboard.is_default

    # Create a detached object to return
    dashboard_obj = Dashboard(
        tenant_id=dashboard_tenant_id,
        name=dashboard_name,
        layout_size=dashboard_layout_size,
        is_default=dashboard_is_default
    )
    dashboard_obj.id = dashboard_id
    return dashboard_obj


@pytest.fixture
def task(app, dashboard, family):
    """Create a test task."""
    with app.app_context():
        task = Task(
            dashboard_id=dashboard.id,
            tenant_id=family.id,
            name="Dishes",
            rotation_json=json.dumps(["Alice", "Bob", "Charlie"]),
            icon_type="emoji",
            icon_value="🍽"
        )
        db.session.add(task)
        db.session.commit()
        # Store data before session closes
        task_id = task.id
        task_dashboard_id = task.dashboard_id
        task_tenant_id = task.tenant_id
        task_name = task.name
        task_rotation_json = task.rotation_json
        task_icon_type = task.icon_type
        task_icon_value = task.icon_value

    # Create a detached object to return
    task_obj = Task(
        dashboard_id=task_dashboard_id,
        tenant_id=task_tenant_id,
        name=task_name,
        rotation_json=task_rotation_json,
        icon_type=task_icon_type,
        icon_value=task_icon_value
    )
    task_obj.id = task_id
    return task_obj


@pytest.fixture
def countdown(app, dashboard, family):
    """Create a test countdown."""
    with app.app_context():
        countdown = Countdown(
            dashboard_id=dashboard.id,
            tenant_id=family.id,
            name="Alice's Birthday",
            date_month=6,
            date_day=15,
            icon_type="emoji",
            icon_value="🎂"
        )
        db.session.add(countdown)
        db.session.commit()
        # Store data before session closes
        countdown_id = countdown.id
        countdown_dashboard_id = countdown.dashboard_id
        countdown_tenant_id = countdown.tenant_id
        countdown_name = countdown.name
        countdown_date_month = countdown.date_month
        countdown_date_day = countdown.date_day
        countdown_icon_type = countdown.icon_type
        countdown_icon_value = countdown.icon_value

    # Create a detached object to return
    countdown_obj = Countdown(
        dashboard_id=countdown_dashboard_id,
        tenant_id=countdown_tenant_id,
        name=countdown_name,
        date_month=countdown_date_month,
        date_day=countdown_date_day,
        icon_type=countdown_icon_type,
        icon_value=countdown_icon_value
    )
    countdown_obj.id = countdown_id
    return countdown_obj
