"""
Unit tests for rotation calculation logic.
"""
import pytest
import json
from datetime import date, datetime
from dinkydash.utils.rotation import get_current_person, get_person_for_date


class TestRotationLogic:
    """Test cases for task rotation calculations."""
    
    def test_get_current_person_basic(self):
        """Test basic rotation with current date."""
        rotation = json.dumps(["Alice", "Bob", "Charlie"])
        current = get_current_person(rotation)
        
        # Should return one of the people in rotation
        assert current in ["Alice", "Bob", "Charlie"]
    
    def test_get_current_person_single_person(self):
        """Test rotation with single person."""
        rotation = json.dumps(["Alice"])
        assert get_current_person(rotation) == "Alice"
    
    def test_get_current_person_empty_rotation(self):
        """Test handling of empty rotation."""
        rotation = json.dumps([])
        assert get_current_person(rotation) is None
    
    def test_get_current_person_invalid_json(self):
        """Test handling of invalid JSON."""
        assert get_current_person("invalid json") is None
        assert get_current_person(None) is None
        assert get_current_person("") is None
    
    def test_get_person_for_date_specific_dates(self):
        """Test rotation on specific dates."""
        rotation = json.dumps(["Alice", "Bob", "Charlie"])
        
        # Test specific date (2024-01-01 is day 1 of year)
        person_day1 = get_person_for_date(rotation, date(2024, 1, 1))
        assert person_day1 == "Bob"  # Day 1 % 3 = 1, so index 1
        
        # Test day 2
        person_day2 = get_person_for_date(rotation, date(2024, 1, 2))
        assert person_day2 == "Charlie"  # Day 2 % 3 = 2, so index 2
        
        # Test day 3
        person_day3 = get_person_for_date(rotation, date(2024, 1, 3))
        assert person_day3 == "Alice"  # Day 3 % 3 = 0, so index 0
        
        # Test day 4 (wraps around)
        person_day4 = get_person_for_date(rotation, date(2024, 1, 4))
        assert person_day4 == "Bob"  # Day 4 % 3 = 1, so index 1
    
    def test_rotation_consistency_across_year(self):
        """Test that rotation is consistent within same position in year."""
        rotation = json.dumps(["Alice", "Bob"])
        
        # These are the same day of year in different years
        person_2023 = get_person_for_date(rotation, date(2023, 3, 1))
        person_2024 = get_person_for_date(rotation, date(2024, 3, 1))
        
        # March 1st is day 60 in non-leap year, day 61 in leap year
        # So they might be different
        assert person_2023 in ["Alice", "Bob"]
        assert person_2024 in ["Alice", "Bob"]
    
    def test_rotation_with_many_people(self):
        """Test rotation with many people."""
        people = [f"Person{i}" for i in range(10)]
        rotation = json.dumps(people)
        
        # Check that all people get assigned eventually
        assigned = set()
        for day in range(1, 11):
            person = get_person_for_date(rotation, date(2024, 1, day))
            assigned.add(person)
        
        # All 10 people should have been assigned
        assert len(assigned) == 10
    
    def test_rotation_predictability(self):
        """Test that rotation is predictable and deterministic."""
        rotation = json.dumps(["Alice", "Bob", "Charlie"])
        
        # Same date should always return same person
        date1 = date(2024, 6, 15)
        person1 = get_person_for_date(rotation, date1)
        person2 = get_person_for_date(rotation, date1)
        assert person1 == person2
    
    def test_get_current_person_uses_today(self):
        """Test that get_current_person uses today's date."""
        rotation = json.dumps(["Alice", "Bob", "Charlie"])
        
        # Get current person
        current = get_current_person(rotation)
        
        # Get person for today using get_person_for_date
        today_person = get_person_for_date(rotation, date.today())
        
        # They should match
        assert current == today_person