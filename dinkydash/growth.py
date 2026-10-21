"""Signups, activations and the newest accounts, for whoever runs the service.
Cloud only.

    history(pool)                -> every day with a signup or an activation
    families_now(pool)           -> how many families exist right now
    paying(pool)                 -> active paid subscriptions, and the plan split
    roster(pool, most)           -> the newest families: address, bookkeeping, screen sizes
    screen_sizes(pool)           -> each reported size, how many screens, when last seen
    by_week(rows, weeks, today)  -> the last `weeks` weeks, gaps filled (pure)
    totals(rows)                 -> all-time signups and activations (pure)
    spend_by_day(pool, days)     -> the last `days` days' charged calls, newest first
    trial_health(pool, within)   -> trialling, lapsing within `within` days, and lapsed
    calendar_health(pool)        -> feeds by their last fetch result

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
the address on each account, the platform's own bookkeeping about it
(when it was created, when it activated, its status and deadlines, when it
last signed in), and the sizes its screens have reported. **Never the config.**
Names, dates of birth and calendars are the family's content, and no operator
page needs them. `screen_sizes` is a count per size and a time, with no family
id in the result. No family id leaves this module in either direction, because
nothing on the page links to one family — so a bug in the page can show an
operator an address, which the operator can already see in the mailbox that
sent it, and a screen size, and nothing else.

`spend_by_day`, `trial_health` and `calendar_health` (DIN-71) hold the same
line: each is one or more `count(*)` or a daily total from a table with no
family id in it (`global_model_spend`, `families.status`, `calendar_health`'s
own `last_fetch_status`), and none of the three takes a family id or returns
one. A family on trial, lapsing soon, or with a feed that has been failing is
a count the operator's page adds to, never a row it can click through to.

Like `accounts.py`, this imports no driver: it is handed a pool and asks it for
connections.
"""

from collections import namedtuple
from datetime import timedelta
from decimal import Decimal

# One week on the chart. `start` is the Monday, as a date.
Week = namedtuple("Week", "start signups activations")
Totals = namedtuple("Totals", "signups activations")
Paying = namedtuple("Paying", "total monthly yearly unrecorded")

# One reported size on the roster. `pixel_ratio` is a Decimal.
Size = namedtuple("Size", "width height pixel_ratio")

# One size across every family: how many screens reported it, and when one last did.
Viewport = namedtuple("Viewport", "width height pixel_ratio count last_seen_at")

# One account on the roster: the address, the bookkeeping, and the sizes its
# screens have reported. Nothing of the config. `screens` defaults to none so a
# caller building an account for the words on the page can leave it off.
Account = namedtuple("Account", "email created_at activated_at status trial_ends_at "
                                "lapsed_at last_login_at screens",
                     defaults=((),))

# How many the roster shows. A page listing every address there has ever been
# is a leak amplifier as well as a slow page; the newest are the ones an
# operator is looking for, and the counts above the list are about everyone.
MOST_IN_ROSTER = 100

# One day's charged calls, summed over every family. No family id.
SpendDay = namedtuple("SpendDay", "day calls")

# How many families are trialling, how many of those lapse soon, and how many
# have already lapsed. Counts, never which family is in which bucket.
TrialHealth = namedtuple("TrialHealth", "trialing lapsing_soon lapsed")

# Feeds by their last fetch result. `longest_run` is the worst current run of
# consecutive failures, or `None` until something has actually counted past
# the column's default of zero.
CalendarHealth = namedtuple("CalendarHealth", "ok failed paused unchecked longest_run")

# "Lapsing soon" on the operator's page: a trial due, or already overdue and
# not yet swept, within this many days.
LAPSING_SOON_DAYS = 7


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


def screen_sizes(pool):
    """Every reported size, with how many screens use it and when one last did.

    One row in `screen_sizes` is one family at one size, so the count is how
    many families have reported that size. A family with two screens of the
    same size has one row and counts once. No family id leaves with the numbers.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT width, height, pixel_ratio, count(*)::int, max(last_seen_at)
               FROM screen_sizes
               GROUP BY width, height, pixel_ratio
               ORDER BY count(*) DESC, max(last_seen_at) DESC,
                        width, height, pixel_ratio""",
        )
        return [Viewport(*row) for row in cur.fetchall()]


def roster(pool, most=MOST_IN_ROSTER):
    """The newest `most` families, newest first, with the address on each.

    A LEFT JOIN, because a family made by hand has no parent row yet and should
    still be on the list rather than silently missing from it. One parent per
    family at MVP; a second would be a second line, which is the right answer.

    Screen sizes ride along, most recently seen first. The join stays inside
    the query so no family id has to come out to attach them afterwards.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT u.email, f.created_at, f.activated_at, f.status,
                      f.trial_ends_at, f.lapsed_at, u.last_login_at,
                      COALESCE((
                          SELECT string_agg(
                                     s.width::text || 'x' || s.height::text || '@' ||
                                     trim(trailing '.' FROM
                                          trim(trailing '0' FROM s.pixel_ratio::text)),
                                     ',' ORDER BY s.last_seen_at DESC,
                                              s.width, s.height, s.pixel_ratio)
                          FROM screen_sizes AS s
                          WHERE s.family_id = f.id
                      ), '')
               FROM families AS f
               LEFT JOIN users AS u ON u.family_id = f.id
               ORDER BY f.created_at DESC, u.id
               LIMIT %s""",
            (max(1, int(most)),),
        )
        return [Account(*row[:-1], _sizes(row[-1])) for row in cur.fetchall()]


def _sizes(text):
    """The roster's packed sizes as `Size`s, most recently seen first."""
    if not text:
        return ()
    sizes = []
    for piece in text.split(","):
        width, _, rest = piece.partition("x")
        height, _, ratio = rest.partition("@")
        sizes.append(Size(int(width), int(height), Decimal(ratio)))
    return tuple(sizes)


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


def spend_by_day(pool, days=14):
    """The last `days` days with a charged call, newest first.

    Reads `global_model_spend`: one row per UTC day, summed over every family
    by the trigger that writes it, with no family id in the table at all.
    `model_spend` itself — one row per family per day — is never read here.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT day, calls FROM global_model_spend
               ORDER BY day DESC LIMIT %s""",
            (max(1, int(days)),),
        )
        return [SpendDay(*row) for row in cur.fetchall()]


def trial_health(pool, within_days=LAPSING_SOON_DAYS):
    """How many families are trialling, how many lapse within `within_days`,
    and how many have already lapsed.

    An aggregate of `families.status` and `trial_ends_at`: three counts, and
    no way to tell from them which family is in which.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT
                   count(*) FILTER (WHERE status = 'trialing'),
                   count(*) FILTER (WHERE status = 'trialing' AND trial_ends_at
                                     <= now() + %s * interval '1 day'),
                   count(*) FILTER (WHERE status = 'lapsed')
               FROM families""",
            (within_days,),
        )
        return TrialHealth(*cur.fetchone())


def calendar_health(pool):
    """Feeds counted by their last fetch result.

    `consecutive_failures` defaults to zero, which reads exactly like "nothing
    has ever failed" until something actually increments it — so `longest_run`
    stays `None` until a row's count is above zero, and the page then shows the
    last result per feed as aggregate counts only. Nothing here reads
    `family_id` or `calendar_id`.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT
                   count(*) FILTER (WHERE last_fetch_status = 'ok'),
                   count(*) FILTER (WHERE last_fetch_status = 'failed'),
                   count(*) FILTER (WHERE last_fetch_status = 'paused'),
                   count(*) FILTER (WHERE last_fetch_status IS NULL),
                   max(consecutive_failures) FILTER (WHERE consecutive_failures > 0)
               FROM calendar_health""",
        )
        ok, failed, paused, unchecked, worst = cur.fetchone()
        return CalendarHealth(ok, failed, paused, unchecked, worst)
