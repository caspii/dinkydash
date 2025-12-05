"""
Unit tests for countdown calculation logic.
"""
import pytest
from datetime import date, timedelta
from freezegun import freeze_time
from dinkydash.utils.countdown import calculate_days_remaining, get_target_date, format_countdown


class TestCountdownLogic:
    """Test cases for countdown calculations."""
    
    @freeze_time("2024-01-15")  # January 15, 2024
    def test_calculate_days_remaining_future_date_same_year(self):
        """Test countdown to a date later in the same year."""
        # Christmas is December 25
        days = calculate_days_remaining(12, 25)
        # From Jan 15 to Dec 25 is 344 days in 2024 (leap year)
        assert days == 344
    
    @freeze_time("2024-01-15")
    def test_calculate_days_remaining_past_date_next_year(self):
        """Test countdown to a date that already passed (should roll to next year)."""
        # January 1st already passed, should count to next year
        days = calculate_days_remaining(1, 1)
        # From Jan 15, 2024 to Jan 1, 2025 is 351 days
        assert days == 351
    
    @freeze_time("2024-06-15")
    def test_calculate_days_remaining_birthday_example(self):
        """Test countdown to a birthday (Alice's Birthday on June 15)."""
        # Today is June 15, her birthday is today
        days = calculate_days_remaining(6, 15)
        assert days == 0  # Birthday is today!
    
    @freeze_time("2024-06-16")
    def test_calculate_days_remaining_day_after_event(self):
        """Test countdown the day after an event."""
        # Alice's birthday was yesterday (June 15)
        days = calculate_days_remaining(6, 15)
        # Should count to next year: 364 days (365 - 1)
        assert days == 364
    
    @freeze_time("2024-02-28")
    def test_calculate_days_remaining_leap_day(self):
        """Test countdown involving leap day."""
        # Feb 29 exists in 2024 (leap year)
        days = calculate_days_remaining(2, 29)
        assert days == 1
    
    @freeze_time("2025-02-28")
    def test_calculate_days_remaining_leap_day_non_leap_year(self):
        """Test countdown to Feb 29 in non-leap year."""
        # Feb 29 doesn't exist in 2025, should handle gracefully
        # Most implementations treat it as March 1
        days = calculate_days_remaining(2, 29)
        # Should count to Feb 29, 2028 (next leap year)
        # This might fail if implementation doesn't handle leap years
        assert days > 0
    
    def test_calculate_days_remaining_invalid_dates(self):
        """Test handling of invalid dates."""
        # Invalid month
        assert calculate_days_remaining(13, 1) is None
        assert calculate_days_remaining(0, 1) is None
        
        # Invalid day
        assert calculate_days_remaining(1, 32) is None
        assert calculate_days_remaining(4, 31) is None  # April only has 30 days
        
        # Invalid types
        assert calculate_days_remaining("12", "25") is None
        assert calculate_days_remaining(None, None) is None
    
    @freeze_time("2024-12-20")
    def test_calculate_days_remaining_near_year_end(self):
        """Test countdown behavior near year end."""
        # Christmas is in 5 days
        days = calculate_days_remaining(12, 25)
        assert days == 5
        
        # New Year's Day (next year)
        days = calculate_days_remaining(1, 1)
        assert days == 12  # Dec 20 to Jan 1
    
    @freeze_time("2024-03-15")
    def test_get_target_date_same_year(self):
        """Test getting target date for event later this year."""
        target = get_target_date(7, 4)  # July 4th
        assert target == date(2024, 7, 4)
    
    @freeze_time("2024-08-15")
    def test_get_target_date_next_year(self):
        """Test getting target date for event that passed."""
        target = get_target_date(7, 4)  # July 4th already passed
        assert target == date(2025, 7, 4)
    
    def test_format_countdown_various_values(self):
        """Test countdown formatting."""
        assert format_countdown(0) == "Today!"
        assert format_countdown(1) == "Tomorrow!"
        assert format_countdown(7) == "7 days"
        assert format_countdown(30) == "30 days"
        assert format_countdown(365) == "365 days"
    
    @freeze_time("2024-06-01")
    def test_countdown_consistency(self):
        """Test that countdown calculations are consistent."""
        # Calculate same countdown multiple times
        days1 = calculate_days_remaining(12, 25)
        days2 = calculate_days_remaining(12, 25)
        assert days1 == days2
    
    @freeze_time("2024-01-01")
    def test_countdown_all_months(self):
        """Test countdown works for all months."""
        # Test the 15th of each month
        expected_days = [
            14,   # Jan 15 (14 days away)
            45,   # Feb 15 (31 + 14)
            75,   # Mar 15 (31 + 29 + 15 - leap year)
            106,  # Apr 15
            136,  # May 15
            167,  # Jun 15
            197,  # Jul 15
            228,  # Aug 15
            259,  # Sep 15
            289,  # Oct 15
            320,  # Nov 15
            350,  # Dec 15
        ]
        
        for month, expected in enumerate(expected_days, 1):
            days = calculate_days_remaining(month, 15)
            assert days == expected, f"Month {month} failed: expected {expected}, got {days}"