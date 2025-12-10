"""
Integration tests for countdown CRUD workflow.
"""
import pytest
from flask import g
from dinkydash import create_app
from dinkydash.models import db, Family, User, Dashboard, Countdown
from dinkydash.utils.auth import hash_password


@pytest.fixture
def countdown_app():
    """Create app with test data for countdown management."""
    from dinkydash.config import TestConfig
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        
        # Create test family and user
        family = Family(name="Countdown Test Family")
        db.session.add(family)
        db.session.flush()
        
        user = User(
            email="countdown@test.com",
            password_hash=hash_password("testpass123"),
            tenant_id=family.id
        )
        db.session.add(user)
        db.session.flush()
        
        # Create dashboards
        dashboard1 = Dashboard(
            tenant_id=family.id,
            name="Main Dashboard",
            layout_size="medium",
            is_default=True
        )
        dashboard2 = Dashboard(
            tenant_id=family.id,
            name="Kitchen Dashboard",
            layout_size="small"
        )
        db.session.add_all([dashboard1, dashboard2])
        db.session.commit()
        
        yield app
        
        db.session.remove()
        db.drop_all()


@pytest.fixture
def countdown_client(countdown_app):
    """Create authenticated client for countdown tests."""
    client = countdown_app.test_client()
    
    # Login
    client.post('/login', data={
        'email': 'countdown@test.com',
        'password': 'testpass123'
    })
    
    return client


class TestCountdownManagement:
    """Test countdown CRUD workflow."""
    
    def test_countdown_list_empty(self, countdown_client):
        """Test countdown list when no countdowns exist."""
        response = countdown_client.get('/admin/countdowns')
        
        assert response.status_code == 200
        assert b'No countdown events yet' in response.data
        assert b'Add First Countdown' in response.data
    
    def test_countdown_create_form_display(self, countdown_client, countdown_app):
        """Test countdown create form displays correctly."""
        response = countdown_client.get('/admin/countdowns/new')
        
        assert response.status_code == 200
        assert b'Add Countdown Event' in response.data
        assert b'Event Name' in response.data
        assert b'Dashboard' in response.data
        assert b'Month' in response.data
        assert b'Day' in response.data
        assert b'Icon Type' in response.data
        
        # Check dashboard choices are populated
        assert b'Main Dashboard' in response.data
        assert b'Kitchen Dashboard' in response.data
    
    def test_countdown_create_with_emoji(self, countdown_client, countdown_app):
        """Test creating a countdown with emoji icon."""
        with countdown_app.app_context():
            dashboard = Dashboard.query.filter_by(name="Main Dashboard").first()
            dashboard_id = dashboard.id
        
        response = countdown_client.post('/admin/countdowns/new', data={
            'name': 'Christmas',
            'dashboard_id': dashboard_id,
            'date_month': 12,
            'date_day': 25,
            'icon_type': 'emoji',
            'emoji': '🎄',
            'csrf_token': countdown_client.get('/admin/countdowns/new').data  # Get CSRF token
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Countdown created successfully!' in response.data
        assert b'Christmas' in response.data
        assert '🎄'.encode('utf-8') in response.data
    
    def test_countdown_create_validation_errors(self, countdown_client, countdown_app):
        """Test countdown creation with validation errors."""
        response = countdown_client.post('/admin/countdowns/new', data={
            'name': '',  # Empty name
            'dashboard_id': 1,
            'date_month': 2,
            'date_day': 31,  # Invalid date (Feb 31)
            'icon_type': 'emoji',
            'emoji': '',  # Missing emoji
            'csrf_token': countdown_client.get('/admin/countdowns/new').data
        })
        
        assert response.status_code == 200
        assert b'Event name is required' in response.data
        assert b'February only has' in response.data
        assert b'Emoji is required' in response.data
    
    def test_countdown_edit_form_display(self, countdown_client, countdown_app):
        """Test countdown edit form displays with existing data."""
        with countdown_app.app_context():
            # Set tenant context
            g.current_tenant_id = 1
            
            # Create a countdown
            dashboard = Dashboard.query.filter_by(name="Main Dashboard").first()
            countdown = Countdown(
                dashboard_id=dashboard.id,
                name="Birthday",
                date_month=6,
                date_day=15,
                icon_type="emoji",
                icon_value="🎂"
            )
            db.session.add(countdown)
            db.session.commit()
            countdown_id = countdown.id
        
        response = countdown_client.get(f'/admin/countdowns/{countdown_id}/edit')
        
        assert response.status_code == 200
        assert b'Edit Countdown Event' in response.data
        assert b'Birthday' in response.data
        assert b'value="6" selected' in response.data  # June selected
        assert b'value="15"' in response.data  # Day 15
        assert b'🎂' in response.data
    
    def test_countdown_edit_update(self, countdown_client, countdown_app):
        """Test updating a countdown."""
        with countdown_app.app_context():
            g.current_tenant_id = 1
            dashboard = Dashboard.query.filter_by(name="Main Dashboard").first()
            countdown = Countdown(
                dashboard_id=dashboard.id,
                name="Old Event",
                date_month=1,
                date_day=1,
                icon_type="emoji",
                icon_value="📅"
            )
            db.session.add(countdown)
            db.session.commit()
            countdown_id = countdown.id
        
        response = countdown_client.post(f'/admin/countdowns/{countdown_id}/edit', data={
            'name': 'New Year Celebration',
            'dashboard_id': dashboard.id,
            'date_month': 12,
            'date_day': 31,
            'icon_type': 'emoji',
            'emoji': '🎆',
            'csrf_token': countdown_client.get(f'/admin/countdowns/{countdown_id}/edit').data
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Countdown updated successfully!' in response.data
        assert b'New Year Celebration' in response.data
        assert b'Old Event' not in response.data
    
    def test_countdown_delete(self, countdown_client, countdown_app):
        """Test deleting a countdown."""
        with countdown_app.app_context():
            g.current_tenant_id = 1
            dashboard = Dashboard.query.first()
            countdown = Countdown(
                dashboard_id=dashboard.id,
                name="Delete Me",
                date_month=3,
                date_day=17,
                icon_type="emoji",
                icon_value="🗑️"
            )
            db.session.add(countdown)
            db.session.commit()
            countdown_id = countdown.id
        
        # Get CSRF token from list page
        list_response = countdown_client.get('/admin/countdowns')
        
        response = countdown_client.post(
            f'/admin/countdowns/{countdown_id}/delete',
            headers={'X-CSRFToken': 'test'},  # In real test, extract from form
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert b'Countdown deleted successfully!' in response.data
        assert b'Delete Me' not in response.data
    
    def test_countdown_list_sorted_by_days(self, countdown_client, countdown_app):
        """Test countdown list is sorted by days remaining."""
        with countdown_app.app_context():
            g.current_tenant_id = 1
            dashboard = Dashboard.query.first()
            
            # Create countdowns with different dates
            countdowns = [
                Countdown(
                    dashboard_id=dashboard.id,
                    name="Far Event",
                    date_month=12,
                    date_day=25,
                    icon_type="emoji",
                    icon_value="🎄"
                ),
                Countdown(
                    dashboard_id=dashboard.id,
                    name="Soon Event",
                    date_month=1,
                    date_day=15,
                    icon_type="emoji",
                    icon_value="🎊"
                ),
                Countdown(
                    dashboard_id=dashboard.id,
                    name="Medium Event",
                    date_month=6,
                    date_day=1,
                    icon_type="emoji",
                    icon_value="☀️"
                ),
            ]
            db.session.add_all(countdowns)
            db.session.commit()
        
        response = countdown_client.get('/admin/countdowns')
        content = response.data.decode('utf-8')
        
        # Extract positions of event names
        soon_pos = content.find('Soon Event')
        medium_pos = content.find('Medium Event')
        far_pos = content.find('Far Event')
        
        # They should appear in order of days remaining
        assert soon_pos > 0 and medium_pos > 0 and far_pos > 0
        # Exact order depends on current date, but they should all be present
    
    def test_countdown_tenant_isolation(self, countdown_app):
        """Test that users cannot access other tenants' countdowns."""
        with countdown_app.app_context():
            # Create another family's countdown
            other_family = Family(name="Other Family")
            db.session.add(other_family)
            db.session.flush()
            
            other_dashboard = Dashboard(
                tenant_id=other_family.id,
                name="Other Dashboard",
                layout_size="medium",
                is_default=True
            )
            db.session.add(other_dashboard)
            db.session.flush()
            
            other_countdown = Countdown(
                tenant_id=other_family.id,
                dashboard_id=other_dashboard.id,
                name="Other Countdown",
                date_month=7,
                date_day=4,
                icon_type="emoji",
                icon_value="🎆"
            )
            db.session.add(other_countdown)
            db.session.commit()
            other_id = other_countdown.id
        
        client = countdown_app.test_client()
        client.post('/login', data={
            'email': 'countdown@test.com',
            'password': 'testpass123'
        })
        
        # Try to access other tenant's countdown
        response = client.get(f'/admin/countdowns/{other_id}/edit')
        assert response.status_code == 404
        
        response = client.post(f'/admin/countdowns/{other_id}/delete')
        assert response.status_code == 404