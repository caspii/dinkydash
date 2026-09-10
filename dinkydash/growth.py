"""Signups and activations over time, for whoever runs the service. Cloud only.

    history(pool)                -> every day with a signup or an activation
    families_now(pool)           -> how many families exist right now
    by_week(rows, weeks, today)  -> the last `weeks` weeks, gaps filled (pure)
    totals(rows)                 -> all-time signups and activations (pure)

A **signup** is a family created — the click on the emailed link, never the
address being submitted (DIN-41). An **activation** is the first time that
family's settings carry a calendar link, which `config.starter_config` calls
the parent's first real act. Both are counted per UTC day by a trigger on
`families` (migration 006) into `growth_by_day`, a table with a date and two
counts in it and nothing else.

**This is the fourth deliberately unscoped read in the product**, after
`worker.family_ids`, `accounts.py` and `screens.py`, and it is the narrowest
of them: the table it reads carries no family identifiers, so there is nothing
here that *could* be scoped. `families_now` is a bare `count(*)`. No row about
any one family is read, and no id passes through this module in either
direction — which is the property an operator's page in a public repo should
have, so that a bug in it cannot leak a family.

Like `accounts.py`, this imports no driver: it is handed a pool and asks it for
connections.
"""

from collections import namedtuple
from datetime import timedelta

# One week on the chart. `start` is the Monday, as a date.
Week = namedtuple("Week", "start signups activations")
Totals = namedtuple("Totals", "signups activations")


def history(pool):
    """Every day on which somebody signed up or activated, oldest first.

    One row per day with something in it — a year of a small product is a few
    hundred rows — so the roll-up below can be a pure function over the lot.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT day, signups, activations FROM growth_by_day ORDER BY day")
        return cur.fetchall()


def families_now(pool):
    """How many families exist at this moment. A count, and only a count."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM families")
        return cur.fetchone()[0]


def week_of(day):
    """The Monday of the week that day is in."""
    return day - timedelta(days=day.weekday())


def by_week(rows, weeks, today):
    """The last `weeks` weeks up to and including today's, oldest first.

    Every week in the span is present, so a quiet fortnight reads as two empty
    columns rather than a gap the eye closes over. `today` is passed in rather
    than read from a clock, like everything else in this package.
    """
    weeks = max(1, int(weeks))
    first = week_of(today) - timedelta(weeks=weeks - 1)
    counts = {first + timedelta(weeks=i): [0, 0] for i in range(weeks)}
    for day, signups, activations in rows:
        bucket = counts.get(week_of(day))
        if bucket is not None:
            bucket[0] += signups
            bucket[1] += activations
    return [Week(start, *pair) for start, pair in sorted(counts.items())]


def totals(rows):
    """All-time signups and activations, whatever span the chart shows."""
    return Totals(sum(row[1] for row in rows), sum(row[2] for row in rows))
