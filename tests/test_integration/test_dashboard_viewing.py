"""
Integration tests for dashboard viewing with sample data.
"""
import pytest
import json
from datetime import date
from freezegun import freeze_time
from dinkydash import create_app
from dinkydash.models import db, Family, User, Dashboard, Task, Countdown
from dinkydash.utils.auth import hash_password


@pytest.fixture
def app_with_data():
    """Create app with sample family data for testing."""
    from dinkydash.config import TestConfig
    app = create_app(TestConfig)
    
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Create sample family
        family = Family(name="Test Family")
        db.session.add(family)
        db.session.flush()
        
        # Create user
        user = User(
            email="test@example.com",
            password_hash=hash_password("password123"),
            tenant_id=family.id
        )
        db.session.add(user)
        db.session.flush()
        
        # Create dashboard
        dashboard = Dashboard(
            tenant_id=family.id,
            name="Family Dashboard",
            layout_size="medium",
            is_default=True
        )
        db.session.add(dashboard)
        db.session.flush()
        
        # Create tasks with rotations
        tasks_data = [
            ("Dishes", ["Alice", "Bob", "Charlie"], "🍽"),
            ("Take out trash", ["Bob", "Charlie", "Alice"], "🗑"),
            ("Feed the dog", ["Charlie", "Alice", "Bob"], "🐕"),
        ]
        
        for name, rotation, emoji in tasks_data:
            task = Task(
                dashboard_id=dashboard.id,
                name=name,
                rotation_json=json.dumps(rotation),
                icon_type="emoji",
                icon_value=emoji
            )
            db.session.add(task)
        
        # Create countdowns
        countdowns_data = [
            ("Alice's Birthday", 6, 15, "🎂"),
            ("Christmas", 12, 25, "🎄"),
            ("Summer Vacation", 7, 1, "🏖"),
        ]
        
        for name, month, day, emoji in countdowns_data:
            countdown = Countdown(
                dashboard_id=dashboard.id,
                name=name,
                date_month=month,
                date_day=day,
                icon_type="emoji",
                icon_value=emoji
            )
            db.session.add(countdown)
        
        db.session.commit()
        
        yield app
        
        db.session.remove()
        db.drop_all()


@pytest.fixture
def auth_client(app_with_data):
    """Create authenticated test client."""
    client = app_with_data.test_client()
    
    # Login
    client.post('/login', data={
        'email': 'test@example.com',
        'password': 'password123'
    })
    
    return client


class TestDashboardViewing:
    """Test dashboard viewing functionality with sample data."""
    
    @freeze_time("2024-06-15")  # Alice's birthday
    def test_dashboard_displays_tasks_with_current_rotation(self, auth_client):
        """Test that dashboard shows tasks with today's assigned person."""
        response = auth_client.get('/dashboard/1')
        assert response.status_code == 200
        
        # Check task rotation display
        assert b'Dishes' in response.data
        assert b'Take out trash' in response.data
        assert b'Feed the dog' in response.data
        
        # Check that emojis are displayed
        assert '🍽'.encode('utf-8') in response.data
        assert '🗑'.encode('utf-8') in response.data
        assert '🐕'.encode('utf-8') in response.data
        
        # Should show current person for each task
        # On June 15 (day 166 of 2024), rotations would be:
        # Dishes: rotation[166 % 3 = 1] = "Bob"
        # Trash: rotation[166 % 3 = 1] = "Charlie"  
        # Dog: rotation[166 % 3 = 1] = "Alice"
        assert b'Bob' in response.data
        assert b'Charlie' in response.data
        assert b'Alice' in response.data
    
    @freeze_time("2024-06-15")
    def test_dashboard_displays_countdowns_with_days_remaining(self, auth_client):
        """Test that dashboard shows countdowns with correct days remaining."""
        response = auth_client.get('/dashboard/1')
        assert response.status_code == 200
        
        # Check countdown display
        assert b"Alice's Birthday" in response.data
        assert b'Christmas' in response.data
        assert b'Summer Vacation' in response.data
        
        # Check countdown emojis
        assert '🎂'.encode('utf-8') in response.data
        assert '🎄'.encode('utf-8') in response.data
        assert '🏖'.encode('utf-8') in response.data
        
        # On June 15, 2024:
        # - Alice's Birthday is today (0 days)
        # - Christmas is Dec 25 (193 days)
        # - Summer Vacation is July 1 (16 days)
        assert b'Today!' in response.data  # Alice's birthday
        assert b'193 days' in response.data  # Christmas
        assert b'16 days' in response.data  # Summer Vacation
    
    def test_dashboard_requires_authentication(self, app_with_data):
        """Test that dashboard viewing requires login."""
        client = app_with_data.test_client()
        response = client.get('/dashboard/1')
        
        # Should redirect to login
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_dashboard_list_shows_all_dashboards(self, auth_client):
        """Test that dashboard list shows all family dashboards."""
        response = auth_client.get('/')
        
        # Should redirect to dashboard since only one exists
        assert response.status_code == 302
        assert '/dashboard/1' in response.location
    
    def test_dashboard_respects_layout_size(self, auth_client):
        """Test that dashboard applies correct layout size class."""
        response = auth_client.get('/dashboard/1')
        assert response.status_code == 200
        
        # Should have medium layout class
        assert b'layout-medium' in response.data
    
    def test_dashboard_shows_empty_state(self, app_with_data):
        """Test dashboard with no tasks or countdowns."""
        with app_with_data.app_context():
            # Create empty dashboard
            dashboard = Dashboard(
                tenant_id=1,
                name="Empty Dashboard",
                layout_size="small"
            )
            db.session.add(dashboard)
            db.session.commit()
            dashboard_id = dashboard.id
        
        client = app_with_data.test_client()
        client.post('/login', data={
            'email': 'test@example.com',
            'password': 'password123'
        })
        
        response = client.get(f'/dashboard/{dashboard_id}')
        assert response.status_code == 200
        
        # Should show empty state messages
        assert b'No tasks' in response.data or b'Add your first task' in response.data
        assert b'No countdowns' in response.data or b'Add your first countdown' in response.data
    
    def test_dashboard_htmx_content_endpoint(self, auth_client):
        """Test HTMX polling endpoint returns partial content."""
        # Regular request
        response = auth_client.get('/dashboard/1/content')
        assert response.status_code == 200
        
        # Should return partial HTML (no base template)
        assert b'<!DOCTYPE html>' not in response.data
        assert b'<html' not in response.data
        
        # Should still have dashboard content
        assert b'Dishes' in response.data
        assert b'Christmas' in response.data
    
    def test_dashboard_auto_refresh_meta_tag(self, auth_client):
        """Test dashboard includes meta refresh for non-JS fallback."""
        response = auth_client.get('/dashboard/1')
        assert response.status_code == 200
        
        # Should have meta refresh tag
        assert b'<meta http-equiv="refresh"' in response.data
        assert b'content="60"' in response.data  # 60 second refresh
    
    def test_dashboard_htmx_polling_attributes(self, auth_client):
        """Test dashboard includes HTMX polling attributes."""
        response = auth_client.get('/dashboard/1')
        assert response.status_code == 200
        
        # Should have HTMX polling setup
        assert b'hx-get=' in response.data
        assert b'hx-trigger="every 30s"' in response.data
        assert b'hx-swap=' in response.data
    
    def test_dashboard_sorting_order(self, auth_client):
        """Test tasks and countdowns are displayed in correct order."""
        response = auth_client.get('/dashboard/1')
        assert response.status_code == 200
        
        content = response.data.decode('utf-8')
        
        # Tasks should appear in order they were added
        dishes_pos = content.find('Dishes')
        trash_pos = content.find('Take out trash')
        dog_pos = content.find('Feed the dog')
        
        assert dishes_pos < trash_pos < dog_pos
        
        # Countdowns should be sorted by days remaining
        # Alice's Birthday (0) < Summer Vacation (16) < Christmas (193)
        alice_pos = content.find("Alice's Birthday")
        summer_pos = content.find('Summer Vacation')
        christmas_pos = content.find('Christmas')
        
        assert alice_pos < summer_pos < christmas_pos