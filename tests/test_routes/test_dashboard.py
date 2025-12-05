"""
Route tests for dashboard view and HTMX polling endpoints.
"""
import pytest
from flask import g
from dinkydash import create_app
from dinkydash.models import db, Family, User, Dashboard
from dinkydash.utils.auth import hash_password


@pytest.fixture
def dashboard_app():
    """Create app with dashboard test data."""
    from dinkydash.config import TestConfig
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        
        # Create test family and user
        family = Family(name="Dashboard Test Family")
        db.session.add(family)
        db.session.flush()
        
        user = User(
            email="dashboard@test.com",
            password_hash=hash_password("testpass123"),
            tenant_id=family.id
        )
        db.session.add(user)
        db.session.flush()
        
        # Create multiple dashboards
        dashboard1 = Dashboard(
            tenant_id=family.id,
            name="Main Dashboard",
            layout_size="large",
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
def dashboard_client(dashboard_app):
    """Create authenticated client for dashboard tests."""
    client = dashboard_app.test_client()
    
    # Login
    client.post('/login', data={
        'email': 'dashboard@test.com',
        'password': 'testpass123'
    })
    
    return client


class TestDashboardRoutes:
    """Test dashboard route endpoints."""
    
    def test_dashboard_view_requires_login(self, dashboard_app):
        """Test that dashboard view requires authentication."""
        client = dashboard_app.test_client()
        response = client.get('/dashboard/1')
        
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_dashboard_view_success(self, dashboard_client):
        """Test successful dashboard view."""
        response = dashboard_client.get('/dashboard/1')
        
        assert response.status_code == 200
        assert b'Main Dashboard' in response.data
        assert b'layout-large' in response.data
    
    def test_dashboard_view_nonexistent(self, dashboard_client):
        """Test viewing non-existent dashboard returns 404."""
        response = dashboard_client.get('/dashboard/999')
        
        assert response.status_code == 404
    
    def test_dashboard_view_wrong_tenant(self, dashboard_app):
        """Test that users cannot view other tenants' dashboards."""
        with dashboard_app.app_context():
            # Create another family's dashboard
            other_family = Family(name="Other Family")
            db.session.add(other_family)
            db.session.flush()
            
            other_dashboard = Dashboard(
                tenant_id=other_family.id,
                name="Other Dashboard",
                layout_size="medium"
            )
            db.session.add(other_dashboard)
            db.session.commit()
            other_id = other_dashboard.id
        
        client = dashboard_app.test_client()
        client.post('/login', data={
            'email': 'dashboard@test.com',
            'password': 'testpass123'
        })
        
        response = client.get(f'/dashboard/{other_id}')
        assert response.status_code == 404  # Tenant filter prevents access
    
    def test_dashboard_list_single_dashboard_redirect(self, dashboard_app):
        """Test that dashboard list redirects when only one dashboard exists."""
        with dashboard_app.app_context():
            # Delete second dashboard
            Dashboard.query.filter_by(name="Kitchen Dashboard").delete()
            db.session.commit()
        
        client = dashboard_app.test_client()
        client.post('/login', data={
            'email': 'dashboard@test.com',
            'password': 'testpass123'
        })
        
        response = client.get('/dashboards')
        assert response.status_code == 302
        # Should redirect to the specific dashboard
        with dashboard_app.app_context():
            dashboard = Dashboard.query.filter_by(name="Main Dashboard").first()
            assert f'/dashboard/{dashboard.id}' in response.location
    
    def test_dashboard_list_multiple_dashboards(self, dashboard_client):
        """Test dashboard list when multiple dashboards exist."""
        response = dashboard_client.get('/dashboards')
        
        assert response.status_code == 200
        assert b'My Dashboards' in response.data
        assert b'Main Dashboard' in response.data
        assert b'Kitchen Dashboard' in response.data
    
    def test_dashboard_content_endpoint(self, dashboard_client):
        """Test HTMX content endpoint returns partial HTML."""
        response = dashboard_client.get('/dashboard/1/content')
        
        assert response.status_code == 200
        # Should not have full HTML structure
        assert b'<!DOCTYPE html>' not in response.data
        assert b'<html' not in response.data
        assert b'</html>' not in response.data
        
        # Should have dashboard content
        assert b'dashboard-content' in response.data or b'tasks' in response.data
    
    def test_dashboard_content_with_htmx_header(self, dashboard_client):
        """Test content endpoint with HX-Request header."""
        response = dashboard_client.get(
            '/dashboard/1/content',
            headers={'HX-Request': 'true'}
        )
        
        assert response.status_code == 200
        # Response should be partial HTML for HTMX
        assert b'<!DOCTYPE html>' not in response.data
    
    def test_dashboard_content_requires_login(self, dashboard_app):
        """Test that content endpoint requires authentication."""
        client = dashboard_app.test_client()
        response = client.get('/dashboard/1/content')
        
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_dashboard_content_wrong_tenant(self, dashboard_app):
        """Test content endpoint respects tenant isolation."""
        with dashboard_app.app_context():
            # Create another tenant's dashboard
            other_family = Family(name="Other Family")
            db.session.add(other_family)
            db.session.flush()
            
            other_dashboard = Dashboard(
                tenant_id=other_family.id,
                name="Other Dashboard",
                layout_size="medium"
            )
            db.session.add(other_dashboard)
            db.session.commit()
            other_id = other_dashboard.id
        
        client = dashboard_app.test_client()
        client.post('/login', data={
            'email': 'dashboard@test.com',
            'password': 'testpass123'
        })
        
        response = client.get(f'/dashboard/{other_id}/content')
        assert response.status_code == 404
    
    def test_dashboard_includes_navigation(self, dashboard_client):
        """Test dashboard view includes navigation elements."""
        response = dashboard_client.get('/dashboard/1')
        
        assert response.status_code == 200
        # Should have navigation links
        assert b'href="/logout"' in response.data or b'Logout' in response.data
        assert b'href="/"' in response.data or b'Dashboards' in response.data
    
    def test_dashboard_includes_htmx_script(self, dashboard_client):
        """Test dashboard includes HTMX library."""
        response = dashboard_client.get('/dashboard/1')
        
        assert response.status_code == 200
        # Should include HTMX script
        assert b'htmx.org' in response.data or b'htmx.min.js' in response.data
    
    def test_dashboard_protected_requires_login(self, dashboard_app):
        """Test that all dashboard routes require authentication (T048)."""
        client = dashboard_app.test_client()
        
        # Test various dashboard routes without authentication
        protected_routes = [
            '/dashboard/1',
            '/dashboard/1/content',
            '/dashboards',  # Dashboard list
        ]
        
        for route in protected_routes:
            response = client.get(route)
            assert response.status_code == 302, f"Route {route} should redirect to login"
            assert '/login' in response.location, f"Route {route} should redirect to login page"