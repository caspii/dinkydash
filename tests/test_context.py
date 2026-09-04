"""Ages, birthdays, countdowns and chore rotation.

Every test injects the date. Nothing here is allowed to depend on when it runs —
that was the bug class this suite exists to catch.
"""

from datetime import date

import pytest

from dinkydash.context import (anniversary, build_countdowns, compute_age,
                               compute_birthday_info, compute_chore_assignments,
                               compute_special_date_info, upcoming_for)


class TestAnniversary:
    def test_ordinary_date(self):
        assert anniversary(2026, 3, 15) == date(2026, 3, 15)

    def test_leap_day_in_a_leap_year_stays_put(self):
        assert anniversary(2028, 2, 29) == date(2028, 2, 29)

    def test_leap_day_is_observed_on_the_28th_otherwise(self):
        assert anniversary(2026, 2, 29) == date(2026, 2, 28)


class TestAge:
    def test_before_the_birthday(self):
        assert compute_age(date(2017, 3, 15), date(2026, 3, 14)) == 8

    def test_on_the_birthday(self):
        assert compute_age(date(2017, 3, 15), date(2026, 3, 15)) == 9

    def test_after_the_birthday(self):
        assert compute_age(date(2017, 3, 15), date(2026, 3, 16)) == 9

    def test_leap_day_child_ages_up_on_the_28th(self):
        # Born 29 Feb 2016; in 2026 the anniversary is observed on the 28th.
        assert compute_age(date(2016, 2, 29), date(2026, 2, 27)) == 9
        assert compute_age(date(2016, 2, 29), date(2026, 2, 28)) == 10


class TestBirthdayInfo:
    person = {"name": "Mia", "date_of_birth": "2017-03-15"}

    def test_counts_down_within_the_year(self):
        info = compute_birthday_info(self.person, date(2026, 3, 3))
        assert info["days_until_birthday"] == 12
        assert info["current_age"] == 8
        assert info["turning"] == 9

    def test_rolls_into_next_year_once_past(self):
        info = compute_birthday_info(self.person, date(2026, 3, 16))
        assert info["days_until_birthday"] == 364
        assert info["turning"] == 10

    def test_on_the_day_itself(self):
        info = compute_birthday_info(self.person, date(2026, 3, 15))
        assert info["days_until_birthday"] == 0
        assert info["turning"] == 9

    def test_accepts_a_real_date_object(self):
        # ruamel parses unquoted YAML dates into date objects.
        info = compute_birthday_info(
            {"name": "Theo", "date_of_birth": date(2019, 6, 20)}, date(2026, 6, 19)
        )
        assert info["days_until_birthday"] == 1


class TestSpecialDates:
    def test_counts_down_to_this_year(self):
        info = compute_special_date_info(
            {"title": "Christmas", "date": "12/25"}, date(2026, 9, 3)
        )
        assert info["days_until"] == 113

    def test_rolls_over_after_the_date_passes(self):
        info = compute_special_date_info(
            {"title": "Christmas", "date": "12/25"}, date(2026, 12, 26)
        )
        assert info["days_until"] == 364

    def test_leap_day_returns_to_the_29th_in_a_leap_year(self):
        # From 2027 the next 29 Feb is a real one, not the rolled-back 28th.
        info = compute_special_date_info(
            {"title": "Leap party", "date": "02/29"}, date(2027, 6, 1)
        )
        assert info["days_until"] == (date(2028, 2, 29) - date(2027, 6, 1)).days


class TestChoreRotation:
    chore = {"title": "Set the table", "emoji": "🍽", "choices": ["Mia", "Theo", "Ines"]}

    def test_rotates_by_day_of_year(self):
        first = compute_chore_assignments([self.chore], date(2026, 1, 1))
        second = compute_chore_assignments([self.chore], date(2026, 1, 2))
        assert first[0]["assigned_to"] != second[0]["assigned_to"]

    def test_is_stable_for_a_given_day(self):
        twice = [compute_chore_assignments([self.chore], date(2026, 9, 3))[0] for _ in range(2)]
        assert twice[0] == twice[1]

    def test_cycles_through_everyone(self):
        names = {
            compute_chore_assignments([self.chore], date(2026, 9, 3 + offset))[0]["assigned_to"]
            for offset in range(3)
        }
        assert names == {"Mia", "Theo", "Ines"}

    def test_skips_a_job_with_nobody_assigned(self):
        assert compute_chore_assignments([{"title": "Bins", "choices": []}], date(2026, 9, 3)) == []

    def test_handles_no_jobs_at_all(self):
        assert compute_chore_assignments(None, date(2026, 9, 3)) == []

    def test_upcoming_preview_matches_what_each_day_computes(self):
        preview = upcoming_for(self.chore, date(2026, 9, 3), days=7)
        assert len(preview) == 7
        for entry in preview:
            live = compute_chore_assignments([self.chore], entry["date"])[0]
            assert entry["assigned_to"] == live["assigned_to"]


class TestCountdowns:
    def test_merges_and_sorts_soonest_first(self):
        countdowns = build_countdowns(
            [{"name": "Mia", "date_of_birth": "2017-03-15"}],
            [{"title": "Christmas", "emoji": "🎄", "date": "12/25"}],
            date(2026, 9, 3),
        )
        assert [c["days"] for c in countdowns] == sorted(c["days"] for c in countdowns)
        assert countdowns[0]["title"] == "Christmas"  # 113 days vs 193

    def test_limit_takes_the_soonest(self):
        countdowns = build_countdowns(
            [{"name": "Mia", "date_of_birth": "2017-03-15"},
             {"name": "Theo", "date_of_birth": "2019-06-20"}],
            [{"title": "Christmas", "emoji": "🎄", "date": "12/25"}],
            date(2026, 9, 3), limit=2,
        )
        assert len(countdowns) == 2
        assert countdowns[0]["days"] <= countdowns[1]["days"]

    def test_empty_config_is_fine(self):
        assert build_countdowns(None, None, date(2026, 9, 3)) == []


@pytest.mark.parametrize("day", [date(2026, 1, 1), date(2026, 2, 28), date(2026, 12, 31)])
def test_rotation_never_indexes_out_of_range(day):
    chore = {"title": "Bins", "choices": ["A", "B"]}
    assert compute_chore_assignments([chore], day)[0]["assigned_to"] in {"A", "B"}
