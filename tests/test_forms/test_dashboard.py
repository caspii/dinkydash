"""
Form validation tests for DashboardForm.
"""
import pytest
from dinkydash import create_app
from dinkydash.forms.dashboard import DashboardForm


class TestDashboardForm:
    """Test DashboardForm validation."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        from dinkydash.config import TestConfig
        app = create_app(TestConfig)
        return app
    
    def test_valid_dashboard_form(self, app):
        """Test form with all valid data."""
        with app.app_context():
            with app.test_request_context():
                form = DashboardForm(
                    name='Kitchen Dashboard',
                    layout_size='medium'
                )
                assert form.validate() is True
    
    def test_dashboard_name_required(self, app):
        """Test that name is required."""
        with app.app_context():
            with app.test_request_context():
                form = DashboardForm(
                    name='',
                    layout_size='medium'
                )
                assert form.validate() is False
                assert 'Dashboard name is required' in form.name.errors
    
    def test_dashboard_name_length(self, app):
        """Test name length validation."""
        with app.app_context():
            with app.test_request_context():
                # Too long
                form = DashboardForm(
                    name='A' * 101,
                    layout_size='medium'
                )
                assert form.validate() is False
                assert 'Dashboard name must be between 1 and 100 characters' in form.name.errors
    
    def test_dashboard_layout_size_required(self, app):
        """Test that layout_size is required."""
        with app.app_context():
            with app.test_request_context():
                form = DashboardForm(data={
                    'name': 'Kitchen Dashboard',
                    # layout_size missing
                })
                assert form.validate() is False
                assert form.layout_size.errors  # RadioField shows generic required error
    
    def test_dashboard_layout_size_choices(self, app):
        """Test all valid layout size choices."""
        with app.app_context():
            with app.test_request_context():
                for size in ['small', 'medium', 'large']:
                    form = DashboardForm(
                        name=f'{size.title()} Dashboard',
                        layout_size=size
                    )
                    assert form.validate() is True, f"Layout size '{size}' should be valid"
    
    def test_dashboard_layout_size_invalid_choice(self, app):
        """Test invalid layout size choice."""
        with app.app_context():
            with app.test_request_context():
                form = DashboardForm(data={
                    'name': 'Test Dashboard',
                    'layout_size': 'extra-large'  # Invalid choice
                })
                assert form.validate() is False
                assert form.layout_size.errors
    
    def test_dashboard_layout_size_default(self, app):
        """Test that default layout size is 'medium'."""
        with app.app_context():
            with app.test_request_context():
                form = DashboardForm()
                assert form.layout_size.default == 'medium'
    
    def test_dashboard_form_placeholder(self, app):
        """Test that name field has helpful placeholder."""
        with app.app_context():
            with app.test_request_context():
                form = DashboardForm()
                assert form.name.render_kw['placeholder'] == 'e.g., Kitchen Dashboard'
    
    def test_dashboard_form_css_classes(self, app):
        """Test that form fields have correct CSS classes."""
        with app.app_context():
            with app.test_request_context():
                form = DashboardForm()
                assert form.name.render_kw['class'] == 'form-control'
                assert form.layout_size.render_kw['class'] == 'form-check-input'
    
    def test_dashboard_whitespace_name(self, app):
        """Test that whitespace-only names are invalid."""
        with app.app_context():
            with app.test_request_context():
                form = DashboardForm(
                    name='   ',  # Only whitespace
                    layout_size='medium'
                )
                # WTForms DataRequired should catch this
                assert form.validate() is False
                assert 'Dashboard name is required' in form.name.errors