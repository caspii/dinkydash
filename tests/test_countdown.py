"""
Tests for countdown calculation logic.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch
from dinkydash.utils.countdown import (
    calculate_days_remaining,
    get_target_date,
    format_countdown
)


class TestCountdownLogic:
    """Test cases for countdown calculation."""

    def test_calculate_days_remaining_future_date(self):
        """Test countdown for a date in the future this year."""
        today = date.today()
        future_date = today + timedelta(days=30)

        days = calculate_days_remaining(future_date.month, future_date.day)
        assert days == 30

    def test_calculate_days_remaining_today(self):
        """Test countdown for today's date."""
        today = date.today()

        days = calculate_days_remaining(today.month, today.day)
        assert days == 0

    def test_calculate_days_remaining_past_date_this_year(self):
        """Test countdown for a date that passed this year (should show next year)."""
        today = date.today()
        past_date = today - timedelta(days=30)

        days = calculate_days_remaining(past_date.month, past_date.day)

        # Should be approximately 335 days (365 - 30)
        assert 330 <= days <= 340

    @patch('dinkydash.utils.countdown.date')
    def test_calculate_days_remaining_year_boundary(self, mock_date):
        """Test countdown calculation near year boundary."""
        # Mock today as December 31
        mock_date.today.return_value = date(2024, 12, 31)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        # Event on January 1
        days = calculate_days_remaining(1, 1)
        assert days == 1  # Tomorrow

    @patch('dinkydash.utils.countdown.date')
    def test_calculate_days_remaining_leap_year(self, mock_date):
        """Test countdown calculation in leap year."""
        # Mock today as January 1, 2024 (leap year)
        mock_date.today.return_value = date(2024, 1, 1)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        # Event on March 1 (after Feb 29)
        days = calculate_days_remaining(3, 1)
        assert days == 60  # 31 days in Jan + 29 days in Feb

    def test_calculate_days_remaining_invalid_month(self):
        """Test that invalid month raises ValueError."""
        with pytest.raises(ValueError, match="Invalid month"):
            calculate_days_remaining(13, 15)

        with pytest.raises(ValueError, match="Invalid month"):
            calculate_days_remaining(0, 15)

    def test_calculate_days_remaining_invalid_day(self):
        """Test that invalid day raises ValueError."""
        with pytest.raises(ValueError, match="Invalid day"):
            calculate_days_remaining(6, 32)

        with pytest.raises(ValueError, match="Invalid day"):
            calculate_days_remaining(6, 0)

    def test_calculate_days_remaining_invalid_date(self):
        """Test that invalid date combination raises ValueError."""
        # February 30 doesn't exist
        with pytest.raises(ValueError, match="Invalid date"):
            calculate_days_remaining(2, 30)

    def test_get_target_date_future(self):
        """Test getting target date for future event."""
        today = date.today()
        # Use a date that's always in the future this year (unless today is Dec 31)
        # Pick a date 30 days from now, but ensure it doesn't cross year boundary
        if today.month <= 10:  # Jan-Oct, safe to add 30 days
            future_date = today + timedelta(days=30)
            expected_year = today.year
        else:  # Nov-Dec, use a fixed future date in current year
            future_date = date(today.year, 11, 15)
            if future_date < today:
                # If Nov 15 has passed, expect next year
                future_date = date(today.year + 1, 1, 15)
                expected_year = today.year + 1
            else:
                expected_year = today.year

        target = get_target_date(future_date.month, future_date.day)

        assert target.month == future_date.month
        assert target.day == future_date.day
        assert target.year == expected_year

    def test_get_target_date_past(self):
        """Test getting target date for past event (should be next year)."""
        today = date.today()
        past_date = today - timedelta(days=50)

        target = get_target_date(past_date.month, past_date.day)

        assert target.month == past_date.month
        assert target.day == past_date.day
        assert target.year == today.year + 1

    def test_get_target_date_today(self):
        """Test getting target date for today."""
        today = date.today()

        target = get_target_date(today.month, today.day)

        assert target == today

    @patch('dinkydash.utils.countdown.date')
    def test_get_target_date_dec_31_to_jan_1(self, mock_date):
        """Test target date calculation from Dec 31 to Jan 1."""
        # Mock today as December 31
        mock_date.today.return_value = date(2024, 12, 31)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        target = get_target_date(1, 1)

        assert target.month == 1
        assert target.day == 1
        assert target.year == 2025

    def test_format_countdown_today(self):
        """Test formatting countdown for today."""
        formatted = format_countdown(0)
        assert formatted == "Today!"

    def test_format_countdown_tomorrow(self):
        """Test formatting countdown for tomorrow."""
        formatted = format_countdown(1)
        assert formatted == "Tomorrow"

    def test_format_countdown_multiple_days(self):
        """Test formatting countdown for multiple days."""
        formatted = format_countdown(5)
        assert formatted == "5 days"

        formatted = format_countdown(100)
        assert formatted == "100 days"

    def test_format_countdown_large_number(self):
        """Test formatting countdown for large number of days."""
        formatted = format_countdown(365)
        assert formatted == "365 days"

    @patch('dinkydash.utils.countdown.date')
    def test_birthday_countdown(self, mock_date):
        """Test real-world birthday countdown scenario."""
        # Mock today as January 15
        mock_date.today.return_value = date(2024, 1, 15)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        # Birthday on June 15
        days = calculate_days_remaining(6, 15)

        # Jan has 16 days left + Feb 29 + Mar 31 + Apr 30 + May 31 + Jun 15
        # = 16 + 29 + 31 + 30 + 31 + 15 = 152
        assert days == 152

    @patch('dinkydash.utils.countdown.date')
    def test_christmas_countdown(self, mock_date):
        """Test countdown to Christmas."""
        # Mock today as January 1
        mock_date.today.return_value = date(2024, 1, 1)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        # Christmas on December 25
        days = calculate_days_remaining(12, 25)

        # Should be 359 days (2024 is leap year, 366 - 7)
        assert days == 359

    @patch('dinkydash.utils.countdown.date')
    def test_new_years_countdown(self, mock_date):
        """Test countdown to New Year's Day from late December."""
        # Mock today as December 30
        mock_date.today.return_value = date(2024, 12, 30)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        # New Year's Day on January 1
        days = calculate_days_remaining(1, 1)

        assert days == 2  # Dec 31 and Jan 1
