"""
Form validation tests for CountdownForm.
"""
import pytest
from dinkydash import create_app
from dinkydash.forms.countdown import CountdownForm


class TestCountdownForm:
    """Test CountdownForm validation."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        from dinkydash.config import TestConfig
        app = create_app(TestConfig)
        return app
    
    def test_valid_countdown_form(self, app):
        """Test form with all valid data."""
        with app.app_context():
            with app.test_request_context():
                form = CountdownForm(
                    name='Christmas',
                    dashboard_id=1,
                    date_month=12,
                    date_day=25,
                    icon_type='emoji',
                    emoji='🎄'
                )
                assert form.validate() is True
    
    def test_countdown_name_required(self, app):
        """Test that name is required."""
        with app.app_context():
            with app.test_request_context():
                form = CountdownForm(
                    name='',
                    dashboard_id=1,
                    date_month=12,
                    date_day=25,
                    icon_type='emoji',
                    emoji='🎄'
                )
                assert form.validate() is False
                assert 'Event name is required' in form.name.errors
    
    def test_countdown_name_length(self, app):
        """Test name length validation."""
        with app.app_context():
            with app.test_request_context():
                # Too long
                form = CountdownForm(
                    name='A' * 101,
                    dashboard_id=1,
                    date_month=12,
                    date_day=25,
                    icon_type='emoji',
                    emoji='🎄'
                )
                assert form.validate() is False
                assert 'Event name must be between 1 and 100 characters' in form.name.errors
    
    def test_countdown_dashboard_required(self, app):
        """Test that dashboard_id is required."""
        with app.app_context():
            with app.test_request_context():
                form = CountdownForm(
                    name='Christmas',
                    dashboard_id=None,
                    date_month=12,
                    date_day=25,
                    icon_type='emoji',
                    emoji='🎄'
                )
                assert form.validate() is False
                assert 'Please select a dashboard' in form.dashboard_id.errors
    
    def test_countdown_date_validation(self, app):
        """Test date validation for invalid dates."""
        with app.app_context():
            with app.test_request_context():
                # February 31st
                form = CountdownForm(
                    name='Invalid Date',
                    dashboard_id=1,
                    date_month=2,
                    date_day=31,
                    icon_type='emoji',
                    emoji='📅'
                )
                assert form.validate() is False
                assert 'February only has' in form.date_day.errors[0]
    
    def test_countdown_date_april_31(self, app):
        """Test date validation for April 31st."""
        with app.app_context():
            with app.test_request_context():
                form = CountdownForm(
                    name='Invalid Date',
                    dashboard_id=1,
                    date_month=4,
                    date_day=31,
                    icon_type='emoji',
                    emoji='📅'
                )
                assert form.validate() is False
                assert 'April only has 30 days' in form.date_day.errors[0]
    
    def test_countdown_date_range_validation(self, app):
        """Test day must be between 1 and 31."""
        with app.app_context():
            with app.test_request_context():
                # Day 0
                form = CountdownForm(
                    name='Invalid Day',
                    dashboard_id=1,
                    date_month=1,
                    date_day=0,
                    icon_type='emoji',
                    emoji='📅'
                )
                assert form.validate() is False
                assert 'Day must be between 1 and 31' in form.date_day.errors
                
                # Day 32
                form = CountdownForm(
                    name='Invalid Day',
                    dashboard_id=1,
                    date_month=1,
                    date_day=32,
                    icon_type='emoji',
                    emoji='📅'
                )
                assert form.validate() is False
                assert 'Day must be between 1 and 31' in form.date_day.errors
    
    def test_countdown_emoji_required_when_emoji_type(self, app):
        """Test that emoji is required when icon_type is emoji."""
        with app.app_context():
            with app.test_request_context():
                form = CountdownForm(
                    name='Christmas',
                    dashboard_id=1,
                    date_month=12,
                    date_day=25,
                    icon_type='emoji',
                    emoji=''  # Missing emoji
                )
                assert form.validate() is False
                assert 'Emoji is required when emoji icon type is selected' in form.emoji.errors
    
    def test_countdown_emoji_not_required_when_image_type(self, app):
        """Test that emoji is not required when icon_type is image."""
        with app.app_context():
            with app.test_request_context():
                form = CountdownForm(
                    name='Christmas',
                    dashboard_id=1,
                    date_month=12,
                    date_day=25,
                    icon_type='image',
                    emoji=''  # Empty emoji is OK for image type
                )
                # Form should validate (image upload is optional on edit)
                assert form.validate() is True
    
    def test_countdown_february_29_leap_year(self, app):
        """Test that Feb 29 is valid (using non-leap year for validation)."""
        with app.app_context():
            with app.test_request_context():
                form = CountdownForm(
                    name='Leap Day',
                    dashboard_id=1,
                    date_month=2,
                    date_day=29,
                    icon_type='emoji',
                    emoji='📅'
                )
                # Should validate - we use 2023 (non-leap) but Feb 29 is still allowed
                # The actual countdown logic will handle the year rollover
                assert form.validate() is True
    
    def test_all_months_valid(self, app):
        """Test that all 12 months are valid choices."""
        with app.app_context():
            with app.test_request_context():
                for month in range(1, 13):
                    form = CountdownForm(
                        name=f'Month {month} Event',
                        dashboard_id=1,
                        date_month=month,
                        date_day=15,  # 15th exists in all months
                        icon_type='emoji',
                        emoji='📅'
                    )
                    assert form.validate() is True, f"Month {month} should be valid"