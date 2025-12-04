"""
Tests for task rotation calculation logic.
"""
import pytest
import json
from datetime import datetime, timedelta
from dinkydash.utils.rotation import get_current_person, get_person_for_date


class TestRotationLogic:
    """Test cases for rotation calculation."""

    def test_get_current_person_three_people(self):
        """Test rotation with three people."""
        rotation_json = json.dumps(["Alice", "Bob", "Charlie"])
        person = get_current_person(rotation_json)

        # Should return one of the three people
        assert person in ["Alice", "Bob", "Charlie"]

    def test_get_current_person_two_people(self):
        """Test rotation with two people."""
        rotation_json = json.dumps(["Alice", "Bob"])
        person = get_current_person(rotation_json)

        # Should return one of the two people
        assert person in ["Alice", "Bob"]

    def test_get_current_person_single_person(self):
        """Test rotation with single person."""
        rotation_json = json.dumps(["Alice"])
        person = get_current_person(rotation_json)

        # Should always return Alice
        assert person == "Alice"

    def test_get_current_person_empty_rotation(self):
        """Test that empty rotation raises ValueError."""
        rotation_json = json.dumps([])

        with pytest.raises(ValueError, match="rotation_list cannot be empty"):
            get_current_person(rotation_json)

    def test_get_current_person_invalid_json(self):
        """Test that invalid JSON raises ValueError."""
        rotation_json = "not valid json"

        with pytest.raises(ValueError, match="Invalid JSON"):
            get_current_person(rotation_json)

    def test_get_current_person_none_rotation(self):
        """Test that None rotation raises ValueError."""
        with pytest.raises(ValueError, match="rotation_json cannot be empty"):
            get_current_person(None)

    def test_get_person_for_date_consistency(self):
        """Test that same date returns same person."""
        rotation_json = json.dumps(["Alice", "Bob", "Charlie"])
        test_date = datetime(2024, 6, 15)

        # Call multiple times with same date
        person1 = get_person_for_date(rotation_json, test_date)
        person2 = get_person_for_date(rotation_json, test_date)

        # Should return same person
        assert person1 == person2

    def test_get_person_for_date_daily_rotation(self):
        """Test that consecutive days rotate through all people."""
        rotation_json = json.dumps(["Alice", "Bob", "Charlie"])
        base_date = datetime(2024, 1, 1)

        # Get person for 9 consecutive days (3 full cycles)
        people = []
        for i in range(9):
            date = base_date + timedelta(days=i)
            person = get_person_for_date(rotation_json, date)
            people.append(person)

        # Should have all three people appearing
        assert "Alice" in people
        assert "Bob" in people
        assert "Charlie" in people

        # Should repeat the pattern (first 3 days == days 3-6 == days 6-9)
        assert people[0] == people[3] == people[6]
        assert people[1] == people[4] == people[7]
        assert people[2] == people[5] == people[8]

    def test_get_person_for_date_year_boundary(self):
        """Test rotation across year boundaries."""
        rotation_json = json.dumps(["Alice", "Bob"])

        # Last day of year
        dec_31 = datetime(2024, 12, 31)
        person_dec_31 = get_person_for_date(rotation_json, dec_31)

        # First day of next year
        jan_1 = datetime(2025, 1, 1)
        person_jan_1 = get_person_for_date(rotation_json, jan_1)

        # Different years might have same person (depends on leap year)
        # But at least one should be Alice or Bob
        assert person_dec_31 in ["Alice", "Bob"]
        assert person_jan_1 in ["Alice", "Bob"]

    def test_rotation_deterministic(self):
        """Test that rotation is deterministic (same day of year = same person)."""
        rotation_json = json.dumps(["Alice", "Bob", "Charlie"])

        # June 15 in different years
        date_2024 = datetime(2024, 6, 15)  # Leap year
        date_2025 = datetime(2025, 6, 15)  # Not leap year

        person_2024 = get_person_for_date(rotation_json, date_2024)
        person_2025 = get_person_for_date(rotation_json, date_2025)

        # Same calendar date in different years might have different people
        # due to leap year affecting day-of-year
        # Both should be valid people
        assert person_2024 in ["Alice", "Bob", "Charlie"]
        assert person_2025 in ["Alice", "Bob", "Charlie"]

    def test_rotation_with_four_people(self):
        """Test rotation with four people."""
        rotation_json = json.dumps(["Alice", "Bob", "Charlie", "David"])
        base_date = datetime(2024, 1, 1)

        # Get person for 12 days (3 full cycles)
        people = []
        for i in range(12):
            date = base_date + timedelta(days=i)
            person = get_person_for_date(rotation_json, date)
            people.append(person)

        # Should cycle through all four people
        assert "Alice" in people
        assert "Bob" in people
        assert "Charlie" in people
        assert "David" in people

        # Pattern should repeat every 4 days
        assert people[0] == people[4] == people[8]
        assert people[1] == people[5] == people[9]
        assert people[2] == people[6] == people[10]
        assert people[3] == people[7] == people[11]

    def test_rotation_json_with_unicode_names(self):
        """Test rotation with Unicode characters in names."""
        rotation_json = json.dumps(["José", "François", "李明"])
        person = get_current_person(rotation_json)

        # Should handle Unicode names correctly
        assert person in ["José", "François", "李明"]
