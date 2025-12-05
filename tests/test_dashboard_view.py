"""
Tests for dashboard viewing functionality.
"""
import pytest
from flask import g
from dinkydash.models import db, Dashboard, Task, Countdown
import json


class TestDashboardView:
    """Test cases for viewing dashboards."""

    def test_view_default_dashboard_not_logged_in(self, client):
        """Test that unauthenticated users are redirected to login."""
        response = client.get('/dashboard')
        assert response.status_code == 302  # Redirect to login
        assert '/login' in response.location

    def test_view_default_dashboard_logged_in(self, auth_client, family, dashboard, task, countdown):
        """Test viewing the default dashboard when logged in."""
        # The tenant context is set by the user loader when the request is made
        response = auth_client.get('/dashboard')
        assert response.status_code == 200

        # Check that dashboard content is present
        assert b'Test Dashboard' in response.data
        assert b'Dishes' in response.data
        # HTML escapes the apostrophe
        assert b"Alice&#39;s Birthday" in response.data

    def test_view_specific_dashboard(self, auth_client, family, dashboard):
        """Test viewing a specific dashboard by ID."""
        with auth_client.application.app_context():
            g.current_tenant_id = family.id

            response = auth_client.get(f'/dashboard/{dashboard.id}')
            assert response.status_code == 200
            assert b'Test Dashboard' in response.data

    def test_view_dashboard_wrong_tenant(self, auth_client, app):
        """Test that users cannot view dashboards from other tenants."""
        with app.app_context():
            # Create another family and dashboard
            from dinkydash.models import Family, Dashboard
            other_family = Family(name="Other Family")
            db.session.add(other_family)
            db.session.commit()

            other_dashboard = Dashboard(
                tenant_id=other_family.id,
                name="Other Dashboard",
                layout_size="medium",
                is_default=True
            )
            db.session.add(other_dashboard)
            db.session.commit()

            # Try to access other tenant's dashboard
            response = auth_client.get(f'/dashboard/{other_dashboard.id}')
            assert response.status_code == 404  # Should not be found due to tenant filtering

    def test_view_dashboard_with_no_items(self, auth_client, family, dashboard):
        """Test viewing an empty dashboard with no tasks or countdowns."""
        with auth_client.application.app_context():
            g.current_tenant_id = family.id

            response = auth_client.get(f'/dashboard/{dashboard.id}')
            assert response.status_code == 200
            # Should show empty state message
            assert b'Test Dashboard' in response.data

    def test_dashboard_shows_current_rotation(self, auth_client, family, dashboard, task):
        """Test that dashboard shows the current person in rotation."""
        with auth_client.application.app_context():
            g.current_tenant_id = family.id

            response = auth_client.get('/dashboard')
            assert response.status_code == 200

            # Should show one of the rotation members (Alice, Bob, or Charlie)
            assert (b'Alice' in response.data or
                    b'Bob' in response.data or
                    b'Charlie' in response.data)

    def test_dashboard_shows_days_remaining(self, auth_client, family, dashboard, countdown):
        """Test that dashboard shows days remaining for countdowns."""
        with auth_client.application.app_context():
            g.current_tenant_id = family.id

            response = auth_client.get('/dashboard')
            assert response.status_code == 200

            # Should show countdown information (HTML escaped)
            assert b"Alice&#39;s Birthday" in response.data
            # Should show some indication of days (could be "Today!", "Tomorrow", or "X days")
            assert (b'Today!' in response.data or
                    b'Tomorrow' in response.data or
                    b'day' in response.data)

    def test_dashboard_layout_size_classes(self, auth_client, app, family):
        """Test that dashboard applies correct layout size CSS classes."""
        with app.app_context():
            # Create dashboards with different sizes
            small_dash = Dashboard(
                tenant_id=family.id,
                name="Small Dashboard",
                layout_size="small",
                is_default=False
            )
            large_dash = Dashboard(
                tenant_id=family.id,
                name="Large Dashboard",
                layout_size="large",
                is_default=False
            )
            db.session.add_all([small_dash, large_dash])
            db.session.commit()

            # Test small layout
            g.current_tenant_id = family.id
            response = auth_client.get(f'/dashboard/{small_dash.id}')
            assert b'layout-small' in response.data

            # Test large layout
            response = auth_client.get(f'/dashboard/{large_dash.id}')
            assert b'layout-large' in response.data

    def test_dashboard_no_default_dashboard(self, auth_client, app, family):
        """Test behavior when family has no default dashboard."""
        with app.app_context():
            # Delete all dashboards
            Dashboard.query.filter_by(tenant_id=family.id).delete()
            db.session.commit()

            g.current_tenant_id = family.id
            response = auth_client.get('/dashboard')

            # Should redirect to dashboard list or show create message
            assert response.status_code in [302, 200]
