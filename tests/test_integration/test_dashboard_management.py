"""
Integration tests for dashboard CRUD workflow.
"""
import pytest
from flask import g
from dinkydash import create_app
from dinkydash.models import db, Family, User, Dashboard, Task, Countdown
from dinkydash.utils.auth import hash_password


@pytest.fixture
def dashboard_mgmt_app():
    """Create app with test data for dashboard management."""
    from dinkydash.config import TestConfig
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        
        # Create test family and user
        family = Family(name="Dashboard Mgmt Test Family")
        db.session.add(family)
        db.session.flush()
        
        user = User(
            email="dashboardmgmt@test.com",
            password_hash=hash_password("testpass123"),
            tenant_id=family.id
        )
        db.session.add(user)
        db.session.flush()
        
        # Create default dashboard (simulating registration)
        dashboard = Dashboard(
            tenant_id=family.id,
            name="Family Dashboard",
            layout_size="medium",
            is_default=True
        )
        db.session.add(dashboard)
        db.session.commit()
        
        yield app
        
        db.session.remove()
        db.drop_all()


@pytest.fixture
def dashboard_mgmt_client(dashboard_mgmt_app):
    """Create authenticated client for dashboard management tests."""
    client = dashboard_mgmt_app.test_client()
    
    # Login
    client.post('/login', data={
        'email': 'dashboardmgmt@test.com',
        'password': 'testpass123'
    })
    
    return client


class TestDashboardManagement:
    """Test dashboard CRUD workflow."""
    
    def test_dashboard_list_single_dashboard(self, dashboard_mgmt_client):
        """Test dashboard management list with single dashboard."""
        response = dashboard_mgmt_client.get('/admin/dashboards')
        
        assert response.status_code == 200
        assert b'Manage Dashboards' in response.data
        assert b'Family Dashboard' in response.data
        assert b'Default' in response.data
        assert b'cannot delete your last dashboard' in response.data
    
    def test_dashboard_create_form_display(self, dashboard_mgmt_client):
        """Test dashboard create form displays correctly."""
        response = dashboard_mgmt_client.get('/admin/dashboards/new')
        
        assert response.status_code == 200
        assert b'Add Dashboard' in response.data
        assert b'Dashboard Name' in response.data
        assert b'Layout Size' in response.data
        assert b'Small - Compact view' in response.data
        assert b'Medium - Default size' in response.data
        assert b'Large - Big view for TVs' in response.data
    
    def test_dashboard_create_success(self, dashboard_mgmt_client, dashboard_mgmt_app):
        """Test creating a new dashboard."""
        response = dashboard_mgmt_client.post('/admin/dashboards/new', data={
            'name': 'Kitchen Dashboard',
            'layout_size': 'small',
            'csrf_token': dashboard_mgmt_client.get('/admin/dashboards/new').data
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Dashboard created successfully!' in response.data
        assert b'Kitchen Dashboard' in response.data
        assert b'Small' in response.data
        
        # Verify it's not default
        with dashboard_mgmt_app.app_context():
            new_dashboard = Dashboard.query.filter_by(name="Kitchen Dashboard").first()
            assert new_dashboard is not None
            assert new_dashboard.is_default is False
    
    def test_dashboard_create_validation(self, dashboard_mgmt_client):
        """Test dashboard creation with validation errors."""
        response = dashboard_mgmt_client.post('/admin/dashboards/new', data={
            'name': '',  # Empty name
            'layout_size': 'medium',
            'csrf_token': dashboard_mgmt_client.get('/admin/dashboards/new').data
        })
        
        assert response.status_code == 200
        assert b'Dashboard name is required' in response.data
    
    def test_dashboard_edit_form_display(self, dashboard_mgmt_client, dashboard_mgmt_app):
        """Test dashboard edit form displays with existing data."""
        with dashboard_mgmt_app.app_context():
            dashboard = Dashboard.query.filter_by(name="Family Dashboard").first()
            dashboard_id = dashboard.id
        
        response = dashboard_mgmt_client.get(f'/admin/dashboards/{dashboard_id}/edit')
        
        assert response.status_code == 200
        assert b'Edit Dashboard' in response.data
        assert b'Family Dashboard' in response.data
        assert b'value="medium" checked' in response.data
        assert b'This is your default dashboard' in response.data
    
    def test_dashboard_edit_update(self, dashboard_mgmt_client, dashboard_mgmt_app):
        """Test updating a dashboard."""
        with dashboard_mgmt_app.app_context():
            dashboard = Dashboard.query.filter_by(name="Family Dashboard").first()
            dashboard_id = dashboard.id
        
        response = dashboard_mgmt_client.post(f'/admin/dashboards/{dashboard_id}/edit', data={
            'name': 'Main Family Dashboard',
            'layout_size': 'large',
            'csrf_token': dashboard_mgmt_client.get(f'/admin/dashboards/{dashboard_id}/edit').data
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Dashboard updated successfully!' in response.data
        assert b'Main Family Dashboard' in response.data
        assert b'Large' in response.data
    
    def test_dashboard_delete_prevention_default(self, dashboard_mgmt_client, dashboard_mgmt_app):
        """Test that default dashboard cannot be deleted."""
        with dashboard_mgmt_app.app_context():
            dashboard = Dashboard.query.filter_by(is_default=True).first()
            dashboard_id = dashboard.id
        
        response = dashboard_mgmt_client.post(
            f'/admin/dashboards/{dashboard_id}/delete',
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert b'Cannot delete the default dashboard' in response.data
    
    def test_dashboard_delete_prevention_last(self, dashboard_mgmt_client, dashboard_mgmt_app):
        """Test that last dashboard cannot be deleted."""
        # Try to delete the only dashboard
        with dashboard_mgmt_app.app_context():
            dashboard = Dashboard.query.first()
            dashboard_id = dashboard.id
        
        response = dashboard_mgmt_client.post(
            f'/admin/dashboards/{dashboard_id}/delete',
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert b'Cannot delete the last dashboard' in response.data or b'Cannot delete the default dashboard' in response.data
    
    def test_dashboard_delete_with_reassignment(self, dashboard_mgmt_client, dashboard_mgmt_app):
        """Test deleting dashboard reassigns tasks and countdowns."""
        with dashboard_mgmt_app.app_context():
            g.current_tenant_id = 1
            
            # Create second dashboard
            dashboard2 = Dashboard(
                tenant_id=1,
                name="Kitchen Dashboard",
                layout_size="small",
                is_default=False
            )
            db.session.add(dashboard2)
            db.session.flush()
            
            # Add task and countdown to second dashboard
            task = Task(
                dashboard_id=dashboard2.id,
                name="Test Task",
                rotation_json='["Person1"]',
                icon_type="emoji",
                icon_value="✅"
            )
            countdown = Countdown(
                dashboard_id=dashboard2.id,
                name="Test Countdown",
                date_month=12,
                date_day=25,
                icon_type="emoji",
                icon_value="📅"
            )
            db.session.add_all([task, countdown])
            db.session.commit()
            
            dashboard2_id = dashboard2.id
            default_dashboard = Dashboard.query.filter_by(is_default=True).first()
            default_id = default_dashboard.id
        
        # Delete the second dashboard
        response = dashboard_mgmt_client.post(
            f'/admin/dashboards/{dashboard2_id}/delete',
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert b'Dashboard deleted' in response.data
        assert b'Tasks and countdowns have been moved' in response.data
        
        # Verify items were reassigned
        with dashboard_mgmt_app.app_context():
            task = Task.query.filter_by(name="Test Task").first()
            countdown = Countdown.query.filter_by(name="Test Countdown").first()
            
            assert task.dashboard_id == default_id
            assert countdown.dashboard_id == default_id
    
    def test_dashboard_default_auto_creation_on_registration(self, dashboard_mgmt_app):
        """Test that registration creates a default dashboard."""
        client = dashboard_mgmt_app.test_client()
        
        # Register new family
        response = client.post('/register', data={
            'family_name': 'New Test Family',
            'email': 'newtest@example.com',
            'password': 'password123',
            'password_confirm': 'password123',
            'csrf_token': client.get('/register').data
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        # Check that default dashboard was created
        with dashboard_mgmt_app.app_context():
            new_family = Family.query.filter_by(name="New Test Family").first()
            assert new_family is not None
            
            dashboards = Dashboard.query.filter_by(tenant_id=new_family.id).all()
            assert len(dashboards) == 1
            assert dashboards[0].name == "New Test Family Dashboard"
            assert dashboards[0].is_default is True
            assert dashboards[0].layout_size == "medium"
    
    def test_dashboard_tenant_isolation(self, dashboard_mgmt_app):
        """Test that users cannot access other tenants' dashboards."""
        with dashboard_mgmt_app.app_context():
            # Create another family's dashboard
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
            db.session.commit()
            other_id = other_dashboard.id
        
        client = dashboard_mgmt_app.test_client()
        client.post('/login', data={
            'email': 'dashboardmgmt@test.com',
            'password': 'testpass123'
        })
        
        # Try to access other tenant's dashboard
        response = client.get(f'/admin/dashboards/{other_id}/edit')
        assert response.status_code == 404
        
        response = client.post(f'/admin/dashboards/{other_id}/delete')
        assert response.status_code == 404