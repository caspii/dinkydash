"""
Tests for dashboard routes and endpoints.
"""
import pytest
from flask import g
from dinkydash.models import db, Dashboard, Task, Countdown
import json


class TestDashboardRoutes:
    """Test cases for dashboard routes."""

    def test_dashboard_list_route(self, auth_client, family, dashboard):
        """Test GET /dashboards - list all dashboards for family."""
        with auth_client.application.app_context():
            g.current_tenant_id = family.id

            response = auth_client.get('/dashboards')
            assert response.status_code == 200
            assert b'Test Dashboard' in response.data

    def test_dashboard_view_route_default(self, auth_client, family, dashboard):
        """Test GET /dashboard - view default dashboard."""
        with auth_client.application.app_context():
            g.current_tenant_id = family.id

            response = auth_client.get('/dashboard')
            assert response.status_code == 200

    def test_dashboard_view_route_by_id(self, auth_client, family, dashboard):
        """Test GET /dashboard/<id> - view specific dashboard."""
        with auth_client.application.app_context():
            g.current_tenant_id = family.id

            response = auth_client.get(f'/dashboard/{dashboard.id}')
            assert response.status_code == 200

    def test_dashboard_view_nonexistent(self, auth_client, family):
        """Test viewing non-existent dashboard returns 404."""
        with auth_client.application.app_context():
            g.current_tenant_id = family.id

            response = auth_client.get('/dashboard/99999')
            assert response.status_code == 404

    def test_dashboard_htmx_partial_refresh(self, auth_client, family, dashboard, task):
        """Test HTMX partial refresh endpoint."""
        with auth_client.application.app_context():
            g.current_tenant_id = family.id

            # Simulate HTMX request with header
            headers = {'HX-Request': 'true'}
            response = auth_client.get(f'/dashboard/{dashboard.id}', headers=headers)

            assert response.status_code == 200
            # Should return partial HTML (tasks/countdowns only, not full page)

    def test_unauthenticated_access_redirects(self, client):
        """Test that unauthenticated access redirects to login."""
        # Test dashboard view
        response = client.get('/dashboard')
        assert response.status_code == 302
        assert '/login' in response.location

        # Test dashboard list
        response = client.get('/dashboards')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_tenant_isolation_in_routes(self, app, auth_client):
        """Test that routes properly enforce tenant isolation."""
        with app.app_context():
            # Create another family and dashboard
            from dinkydash.models import Family, Dashboard
            family1 = Family(name="Family 1")
            family2 = Family(name="Family 2")
            db.session.add_all([family1, family2])
            db.session.commit()

            dash1 = Dashboard(
                tenant_id=family1.id,
                name="Dashboard 1",
                layout_size="medium",
                is_default=True
            )
            dash2 = Dashboard(
                tenant_id=family2.id,
                name="Dashboard 2",
                layout_size="medium",
                is_default=True
            )
            db.session.add_all([dash1, dash2])
            db.session.commit()

            # Set tenant to family1
            g.current_tenant_id = family1.id

            # Should be able to access family1's dashboard
            response = auth_client.get(f'/dashboard/{dash1.id}')
            assert response.status_code == 200

            # Should NOT be able to access family2's dashboard
            response = auth_client.get(f'/dashboard/{dash2.id}')
            assert response.status_code == 404  # Filtered by tenant isolation


class TestIntegration:
    """Integration tests for complete user workflows."""

    def test_full_dashboard_viewing_workflow(self, app, client):
        """Test complete workflow: register -> login -> view dashboard."""
        with app.app_context():
            # Create family and user manually
            from dinkydash.models import Family, User, Dashboard, Task, Countdown
            from dinkydash.utils.auth import hash_password

            family = Family(name="Integration Test Family")
            db.session.add(family)
            db.session.commit()

            user = User(
                email="integration@example.com",
                password_hash=hash_password("testpass123"),
                tenant_id=family.id
            )
            db.session.add(user)
            db.session.commit()

            # Create dashboard with tasks and countdowns
            dashboard = Dashboard(
                tenant_id=family.id,
                name="Family Dashboard",
                layout_size="medium",
                is_default=True
            )
            db.session.add(dashboard)
            db.session.commit()

            task = Task(
                dashboard_id=dashboard.id,
                name="Dishes",
                rotation_json=json.dumps(["Alice", "Bob"]),
                icon_type="emoji",
                icon_value="🍽"
            )
            countdown = Countdown(
                dashboard_id=dashboard.id,
                name="Christmas",
                date_month=12,
                date_day=25,
                icon_type="emoji",
                icon_value="🎄"
            )
            db.session.add_all([task, countdown])
            db.session.commit()

            # Login (simulate)
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user.id)

            # Set tenant context
            g.current_tenant_id = family.id

            # View dashboard
            response = client.get('/dashboard')
            assert response.status_code == 200

            # Verify content
            assert b'Family Dashboard' in response.data
            assert b'Dishes' in response.data
            assert b'Christmas' in response.data

            # Verify rotation shows one of the people
            assert b'Alice' in response.data or b'Bob' in response.data

            # Verify countdown shows days
            assert (b'Today!' in response.data or
                    b'Tomorrow' in response.data or
                    b'day' in response.data)

    def test_multi_dashboard_workflow(self, app, auth_client):
        """Test workflow with multiple dashboards."""
        with app.app_context():
            from dinkydash.models import Family, Dashboard

            family = Family(name="Multi-Dashboard Family")
            db.session.add(family)
            db.session.commit()

            # Create multiple dashboards
            dash1 = Dashboard(
                tenant_id=family.id,
                name="Living Room",
                layout_size="large",
                is_default=True
            )
            dash2 = Dashboard(
                tenant_id=family.id,
                name="Kitchen",
                layout_size="medium",
                is_default=False
            )
            db.session.add_all([dash1, dash2])
            db.session.commit()

            g.current_tenant_id = family.id

            # View dashboard list
            response = auth_client.get('/dashboards')
            assert response.status_code == 200
            assert b'Living Room' in response.data
            assert b'Kitchen' in response.data

            # View each dashboard
            response = auth_client.get(f'/dashboard/{dash1.id}')
            assert response.status_code == 200
            assert b'Living Room' in response.data

            response = auth_client.get(f'/dashboard/{dash2.id}')
            assert response.status_code == 200
            assert b'Kitchen' in response.data

    def test_empty_family_workflow(self, app, auth_client):
        """Test workflow for family with no dashboards."""
        with app.app_context():
            from dinkydash.models import Family

            family = Family(name="Empty Family")
            db.session.add(family)
            db.session.commit()

            g.current_tenant_id = family.id

            # Try to view default dashboard (should handle gracefully)
            response = auth_client.get('/dashboard')
            # Should either redirect to create or show empty state
            assert response.status_code in [200, 302]

            # View dashboard list (should show empty state)
            response = auth_client.get('/dashboards')
            assert response.status_code == 200
