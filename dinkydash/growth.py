"""Signups, activations and the newest accounts, for whoever runs the service.
Cloud only.

    history(pool)                -> every day with a signup or an activation
    families_now(pool)           -> how many families exist right now
    paying(pool)                 -> active paid subscriptions, and the plan split
    roster(pool, most)           -> the newest families: address and bookkeeping
    by_week(rows, weeks, today)  -> the last `weeks` weeks, gaps filled (pure)
    totals(rows)                 -> all-time signups and activations (pure)

A **signup** is a family created — the click on the emailed link, never the
address being submitted (DIN-41). An **activation** is the first time that
family's settings carry a calendar link, which `config.starter_config` calls
the parent's first real act. Both are counted per UTC day by a trigger on
`families` (migration 006) into `growth_by_day`, a table with a date and two
counts in it and nothing else.

**This is the fourth deliberately unscoped read in the product**, after
`worker.family_ids`, `accounts.py` and `screens.py`. The counts are the
narrowest read there is — `growth_by_day` carries no family identifier,
`families_now` is a bare `count(*)`, and `paying` counts rows by lifecycle
status, Stripe subscription status and plan interval. No address and no
config in that count. The roster is wider, and deliberately only so wide:
the address on each account and the platform's own bookkeeping about it
(when it was created, when it activated, its status and deadlines, when it
last signed in). **Never the config.** Names, dates of birth and calendars
are the family's content, and no operator page needs them. No family id
leaves this module in either direction, because nothing on the page links
to one family — so a bug in the page can show an operator an address, which
the operator can already see in the mailbox that sent it, and nothing else.

Like `accounts.py`, this imports no driver: it is handed a pool and asks it for
connections.
"""

from collections import namedtuple
from datetime import timedelta

# One week on the chart. `start` is the Monday, as a date.
Week = namedtuple("Week", "start signups activations")
Totals = namedtuple("Totals", "signups activations")
Paying = namedtuple("Paying", "total monthly yearly unrecorded")

# One account on the roster: the address and the bookkeeping, nothing of the config.
Account = namedtuple("Account", "email created_at activated_at status trial_ends_at "
                                "lapsed_at last_login_at")

# How many the roster shows. A page listing every address there has ever been
# is a leak amplifier as well as a slow page; the newest are the ones an
# operator is looking for, and the counts above the list are about everyone.
MOST_IN_ROSTER = 100


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


def paying(pool):
    """How many families have an active, paid subscription, and the plan split.

    A paying family has lifecycle `status` `active` and Stripe
    `subscription_status` `active`. Anything else is left out: `trialing`
    (including a Stripe trial, stored as lifecycle `active` with subscription
    status `trialing`), `past_due`, `canceled` and `lapsed`. A subscription
    set to cancel at period end stays `active` until that deadline, so it
    still counts.

    `monthly` and `yearly` are that same set whose stored plan interval is
    `month` ($6) or `year` ($39). A paying family with no interval yet is in
    `total` and in `unrecorded`. The interval is copied when billing writes
    the snapshot; this read does not ask Stripe.

    An aggregate of those columns: no address, no config and no family id.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT
                   count(*) FILTER (WHERE status = 'active'
                                     AND subscription_status = 'active'),
                   count(*) FILTER (WHERE status = 'active'
                                     AND subscription_status = 'active'
                                     AND subscription_interval = 'month'),
                   count(*) FILTER (WHERE status = 'active'
                                     AND subscription_status = 'active'
                                     AND subscription_interval = 'year')
               FROM families""",
        )
        total, monthly, yearly = cur.fetchone()
    return Paying(total, monthly, yearly, total - monthly - yearly)


def roster(pool, most=MOST_IN_ROSTER):
    """The newest `most` families, newest first, with the address on each.

    A LEFT JOIN, because a family made by hand has no parent row yet and should
    still be on the list rather than silently missing from it. One parent per
    family at MVP; a second would be a second line, which is the right answer.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT u.email, f.created_at, f.activated_at, f.status,
                      f.trial_ends_at, f.lapsed_at, u.last_login_at
               FROM families AS f
               LEFT JOIN users AS u ON u.family_id = f.id
               ORDER BY f.created_at DESC, u.id
               LIMIT %s""",
            (max(1, int(most)),),
        )
        return [Account(*row) for row in cur.fetchall()]


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
