"""Date arithmetic tests for the countdown logic.

Run with:  python3 -m unittest discover tests   (pytest collects them too)

Stdlib unittest rather than pytest so this adds no dependency to the Pi
deploy. The functions moved from generate.py into dinkydash.context during the
Phase 0 extraction; the cases are unchanged.
"""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dinkydash.context import (  # noqa: E402
    anniversary,
    compute_age,
    compute_birthday_info,
    compute_special_date_info,
)


def person(name="Test", dob="2015-03-15"):
    return {"name": name, "date_of_birth": dob}


class TestAnniversary(unittest.TestCase):
    def test_ordinary_date_passes_through(self):
        self.assertEqual(anniversary(2027, 3, 15), date(2027, 3, 15))

    def test_feb_29_kept_in_leap_year(self):
        self.assertEqual(anniversary(2028, 2, 29), date(2028, 2, 29))

    def test_feb_29_observed_on_feb_28_in_common_year(self):
        self.assertEqual(anniversary(2027, 2, 29), date(2027, 2, 28))

    def test_genuinely_invalid_date_still_raises(self):
        # A config typo should surface, not be silently coerced.
        with self.assertRaises(ValueError):
            anniversary(2027, 2, 30)
        with self.assertRaises(ValueError):
            anniversary(2027, 13, 1)


class TestComputeAge(unittest.TestCase):
    def test_before_birthday_this_year(self):
        self.assertEqual(compute_age(date(2015, 3, 15), date(2026, 1, 1)), 10)

    def test_on_birthday(self):
        self.assertEqual(compute_age(date(2015, 3, 15), date(2026, 3, 15)), 11)

    def test_after_birthday_this_year(self):
        self.assertEqual(compute_age(date(2015, 3, 15), date(2026, 8, 20)), 11)

    def test_born_today(self):
        self.assertEqual(compute_age(date(2026, 8, 20), date(2026, 8, 20)), 0)

    def test_leap_day_child_ages_up_on_feb_28_in_common_year(self):
        dob = date(2016, 2, 29)
        self.assertEqual(compute_age(dob, date(2027, 2, 27)), 10)
        # Observed birthday: must match the day compute_birthday_info counts to.
        self.assertEqual(compute_age(dob, date(2027, 2, 28)), 11)
        self.assertEqual(compute_age(dob, date(2027, 3, 1)), 11)

    def test_leap_day_child_ages_up_on_feb_29_in_leap_year(self):
        dob = date(2016, 2, 29)
        self.assertEqual(compute_age(dob, date(2028, 2, 28)), 11)
        self.assertEqual(compute_age(dob, date(2028, 2, 29)), 12)


class TestComputeBirthdayInfo(unittest.TestCase):
    def test_upcoming_birthday_this_year(self):
        info = compute_birthday_info(person(dob="2015-03-15"), date(2026, 3, 10))
        self.assertEqual(info["days_until_birthday"], 5)
        self.assertEqual(info["turning"], 11)
        self.assertEqual(info["current_age"], 10)
        self.assertEqual(info["birthday_date"], "15 March")

    def test_birthday_today(self):
        info = compute_birthday_info(person(dob="2015-03-15"), date(2026, 3, 15))
        self.assertEqual(info["days_until_birthday"], 0)
        self.assertEqual(info["turning"], 11)
        self.assertEqual(info["current_age"], 11)

    def test_birthday_passed_rolls_to_next_year(self):
        info = compute_birthday_info(person(dob="2015-03-15"), date(2026, 3, 16))
        self.assertEqual(info["days_until_birthday"], 364)
        self.assertEqual(info["turning"], 12)

    def test_leap_day_birthday_in_common_year_does_not_raise(self):
        # This raised ValueError before the fix, crashing the daily generation
        # for any family with a leap-day birthday.
        info = compute_birthday_info(person(dob="2016-02-29"), date(2027, 1, 1))
        self.assertEqual(info["days_until_birthday"], 58)  # 31 Jan + 27 Feb
        self.assertEqual(info["birthday_date"], "28 February")
        self.assertEqual(info["turning"], 11)

    def test_leap_day_birthday_observed_day_is_consistent(self):
        info = compute_birthday_info(person(dob="2016-02-29"), date(2027, 2, 28))
        self.assertEqual(info["days_until_birthday"], 0)
        # current_age and turning must agree on the observed birthday.
        self.assertEqual(info["current_age"], 11)
        self.assertEqual(info["turning"], 11)

    def test_leap_day_birthday_rolls_into_a_leap_year(self):
        info = compute_birthday_info(person(dob="2016-02-29"), date(2027, 3, 1))
        self.assertEqual(info["birthday_date"], "29 February")
        self.assertEqual(info["days_until_birthday"], 365)


class TestComputeSpecialDateInfo(unittest.TestCase):
    def test_upcoming_date(self):
        info = compute_special_date_info(
            {"title": "Christmas", "emoji": "🎄", "date": "12/25"}, date(2026, 12, 20)
        )
        self.assertEqual(info["days_until"], 5)
        self.assertEqual(info["date_display"], "25 December")

    def test_date_today(self):
        info = compute_special_date_info(
            {"title": "Christmas", "date": "12/25"}, date(2026, 12, 25)
        )
        self.assertEqual(info["days_until"], 0)

    def test_passed_date_rolls_to_next_year(self):
        info = compute_special_date_info(
            {"title": "Christmas", "date": "12/25"}, date(2026, 12, 26)
        )
        self.assertEqual(info["days_until"], 364)

    def test_feb_29_special_date_in_common_year_does_not_raise(self):
        info = compute_special_date_info(
            {"title": "Leap Day", "date": "02/29"}, date(2027, 2, 1)
        )
        self.assertEqual(info["days_until"], 27)
        self.assertEqual(info["date_display"], "28 February")

    def test_feb_29_rolls_forward_to_a_real_feb_29(self):
        # Bumping the year on the rolled-back Feb 28 would wrongly yield
        # Feb 28 2028; it must recompute to Feb 29.
        info = compute_special_date_info(
            {"title": "Leap Day", "date": "02/29"}, date(2027, 3, 1)
        )
        self.assertEqual(info["date_display"], "29 February")


if __name__ == "__main__":
    unittest.main()
