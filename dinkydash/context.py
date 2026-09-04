"""Deterministic context: ages, birthdays, countdowns, chore rotation.

Nothing here calls the network or the model. Everything is a pure function of
the config plus the date you pass in, which is why the board can recompute it
at render time even when the day's generated text is stale.
"""

import calendar as _calendar
from datetime import date, datetime


def anniversary(year, month, day):
    """Return the given month/day as it falls in `year`.

    February 29 exists only in leap years; in other years the anniversary is
    observed on February 28, so a leap-day birthday still counts down to a
    real date instead of raising ValueError. Any other invalid month/day is a
    config error and is left to raise.
    """
    if (month, day) == (2, 29) and not _calendar.isleap(year):
        return date(year, 2, 28)
    return date(year, month, day)


def compute_age(dob, today):
    """Return age on `today` given a date-of-birth."""
    age = today.year - dob.year
    # Compare against the observed anniversary rather than the raw month/day,
    # so someone born on February 29 ages up on February 28 in common years —
    # the same day compute_birthday_info counts down to.
    if today < anniversary(today.year, dob.month, dob.day):
        age -= 1
    return age


def parse_dob(value):
    """Parse a YYYY-MM-DD date of birth from config."""
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def compute_birthday_info(person, today):
    """Return birthday countdown info for one person."""
    dob = parse_dob(person["date_of_birth"])
    current_age = compute_age(dob, today)

    birthday_this_year = anniversary(today.year, dob.month, dob.day)
    if birthday_this_year < today:
        next_birthday = anniversary(today.year + 1, dob.month, dob.day)
        turning = current_age + 1
    elif birthday_this_year == today:
        next_birthday = birthday_this_year
        turning = current_age
    else:
        next_birthday = birthday_this_year
        turning = current_age + 1

    return {
        "name": person["name"],
        "current_age": current_age,
        "turning": turning,
        "days_until_birthday": (next_birthday - today).days,
        "birthday_date": next_birthday.strftime("%-d %B"),
    }


def compute_special_date_info(special_date, today):
    """Return countdown info for one recurring special date (MM/DD)."""
    month, day = [int(part) for part in str(special_date["date"]).split("/")]
    target = anniversary(today.year, month, day)
    if target < today:
        # Recompute from month/day rather than bumping the year: a Feb 28 that
        # was rolled back from Feb 29 must become Feb 29 again in a leap year.
        target = anniversary(today.year + 1, month, day)
    return {
        "title": special_date["title"],
        "emoji": special_date.get("emoji", ""),
        "days_until": (target - today).days,
        "date_display": target.strftime("%-d %B"),
    }


def compute_chore_assignments(recurring, today):
    """Whose turn each recurring job is on `today`.

    Rotation is by day-of-year modulo the number of people, so it keeps in step
    whether or not the board was switched on yesterday.
    """
    day_of_year = today.timetuple().tm_yday
    assignments = []
    for chore in recurring or []:
        choices = chore.get("choices") or []
        if not choices:
            continue
        assignments.append({
            "emoji": chore.get("emoji", ""),
            "title": chore["title"],
            "assigned_to": choices[day_of_year % len(choices)],
        })
    return assignments


def upcoming_for(chore, today, days=7):
    """Who is up for `chore` on each of the next `days` days."""
    choices = chore.get("choices") or []
    if not choices:
        return []
    out = []
    for offset in range(days):
        d = date.fromordinal(today.toordinal() + offset)
        out.append({
            "date": d,
            "assigned_to": choices[d.timetuple().tm_yday % len(choices)],
        })
    return out


def build_countdowns(people, special_dates, today, limit=None):
    """Birthdays and special dates merged into one list, soonest first."""
    countdowns = []
    for person in people or []:
        info = compute_birthday_info(person, today)
        countdowns.append({
            "emoji": "🎂",
            "title": f"{info['name']}'s birthday",
            "days": info["days_until_birthday"],
        })
    for special_date in special_dates or []:
        info = compute_special_date_info(special_date, today)
        countdowns.append({
            "emoji": info["emoji"] or "📅",
            "title": info["title"],
            "days": info["days_until"],
        })
    countdowns.sort(key=lambda c: c["days"])
    return countdowns[:limit] if limit else countdowns
