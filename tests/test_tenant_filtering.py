"""
Test tenant filtering functionality.
"""
import pytest
from flask import g
from dinkydash.models import db, Family, User, Dashboard, Task, Countdown
import json


class TestTenantFiltering:
    """Test automatic tenant filtering."""
    
    def test_tenant_filter_basic(self, app):
        """Test that queries are automatically filtered by tenant."""
        with app.app_context():
            # Create two families
            family1 = Family(name="Family 1")
            family2 = Family(name="Family 2")
            db.session.add_all([family1, family2])
            db.session.commit()
            
            # Create dashboards for each family
            dashboard1 = Dashboard(tenant_id=family1.id, name="Dashboard 1", layout_size="medium")
            dashboard2 = Dashboard(tenant_id=family2.id, name="Dashboard 2", layout_size="medium")
            db.session.add_all([dashboard1, dashboard2])
            db.session.commit()
            
            # Set tenant context to family1
            g.current_tenant_id = family1.id
            
            # Query should only return family1's dashboard
            dashboards = Dashboard.query.all()
            assert len(dashboards) == 1
            assert dashboards[0].name == "Dashboard 1"
            
            # Change tenant context to family2
            g.current_tenant_id = family2.id
            
            # Query should only return family2's dashboard
            dashboards = Dashboard.query.all()
            assert len(dashboards) == 1
            assert dashboards[0].name == "Dashboard 2"
    
    def test_no_tenant_context(self, app):
        """Test that queries work without tenant context (admin access)."""
        with app.app_context():
            # Create two families
            family1 = Family(name="Family 1")
            family2 = Family(name="Family 2")
            db.session.add_all([family1, family2])
            db.session.commit()
            
            # Create dashboards for each family
            dashboard1 = Dashboard(tenant_id=family1.id, name="Dashboard 1", layout_size="medium")
            dashboard2 = Dashboard(tenant_id=family2.id, name="Dashboard 2", layout_size="medium")
            db.session.add_all([dashboard1, dashboard2])
            db.session.commit()
            
            # Without tenant context, should return all dashboards
            dashboards = Dashboard.query.all()
            assert len(dashboards) == 2
            assert {d.name for d in dashboards} == {"Dashboard 1", "Dashboard 2"}
    
    def test_automatic_tenant_id_on_insert(self, app):
        """Test that tenant_id is automatically set on new records."""
        with app.app_context():
            # Create a family
            family = Family(name="Test Family")
            db.session.add(family)
            db.session.commit()
            
            # Set tenant context
            g.current_tenant_id = family.id
            
            # Create dashboard without explicitly setting tenant_id
            dashboard = Dashboard(name="Auto Tenant Dashboard", layout_size="large")
            db.session.add(dashboard)
            db.session.commit()
            
            # Verify tenant_id was set automatically
            assert dashboard.tenant_id == family.id
            
            # Create a task without explicitly setting tenant_id
            task = Task(
                dashboard_id=dashboard.id,
                name="Test Task",
                rotation_json=json.dumps(["Alice", "Bob"]),
                icon_type="emoji",
                icon_value="🔄"
            )
            db.session.add(task)
            db.session.commit()
            
            # Verify tenant_id was set automatically
            assert task.tenant_id == family.id
    
    def test_cross_tenant_protection(self, app):
        """Test that one tenant cannot access another tenant's data."""
        with app.app_context():
            # Create two families
            family1 = Family(name="Family 1")
            family2 = Family(name="Family 2")
            db.session.add_all([family1, family2])
            db.session.commit()
            
            # Create dashboard for family2
            dashboard2 = Dashboard(tenant_id=family2.id, name="Private Dashboard", layout_size="medium")
            db.session.add(dashboard2)
            db.session.commit()
            
            # Set tenant context to family1
            g.current_tenant_id = family1.id
            
            # Try to query family2's dashboard by ID
            result = Dashboard.query.filter_by(id=dashboard2.id).first()
            assert result is None  # Should not find it due to tenant filter
            
            # Verify the dashboard still exists when queried with correct tenant
            g.current_tenant_id = family2.id
            result = Dashboard.query.filter_by(id=dashboard2.id).first()
            assert result is not None
            assert result.name == "Private Dashboard"