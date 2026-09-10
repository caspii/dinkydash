"""The operator's page: signups and activations by week. Cloud mode only.

    GET /admin             the last twelve weeks
    GET /admin/            the same; a typed URL often ends in a slash
    GET /admin?weeks=52    further back, up to a year

Registered only in cloud mode, like `auth` and `screen` — a self-hoster is one
family, and there is nothing to count.

**Two checks, and the second answers 404.** `guard()` sends a signed-out
visitor to `/login`, like every other page a person signs into. Then the
address on the signed-in account is compared with `DINKYDASH_ADMIN_EMAILS`
(`web.family.is_admin`), and anybody not on that list gets the same answer as
a URL that does not exist. A 403 would say the page is there, which is nothing
a stranger needs to know, and 404-on-a-mismatch is the rule every other
authorisation miss in this app follows. An empty or missing list means nobody,
which is the safe way for a new deployment to be wrong.

**No family is read here.** The page is built from `dinkydash/growth.py`,
which reads a table with no family identifiers in it plus one `count(*)`, and
from `dinkydash/heartbeat.py`, which reads the worker's last pass — a time and
three counts, the same row `/healthz/worker` serves to the monitor, said in a
sentence here so the operator can see it without curl. Nothing in this file
takes an id from the request, the session or the URL, so there is no id to
check and nothing for a bug here to leak.

The chart is inline SVG drawn from numbers worked out below, with no script
and no third-party request — the settings shell's own rules. Its two colours
are the shell's accent and purple tokens, checked as a pair on the card's
white: adjacent CVD ΔE 24.7, both above 3:1 against the surface.
"""

import math
from datetime import datetime, timezone

from flask import (Blueprint, abort, current_app, make_response, render_template,
                   request)

from dinkydash import growth, heartbeat
from web.family import is_admin
from web.routes.status import stale_after
from web.session import guard

bp = Blueprint("admin", __name__)

DEFAULT_WEEKS = 12
MOST_WEEKS = 52
SPANS = (12, 26, 52)

# The chart, in SVG user units. The page scales the drawing to the shell's
# width, so these are proportions rather than pixels. Room on the left for the
# axis figures, on top for the direct labels, and below for the week labels.
WIDTH, HEIGHT = 420, 190
LEFT, RIGHT, TOP, BOTTOM = 28, 8, 20, 28
PLOT_W = WIDTH - LEFT - RIGHT
PLOT_H = HEIGHT - TOP - BOTTOM

# A column is thin: at most this thick, and a 2-unit gap of surface between
# the two in a week separates them without a stroke. Data-ends are rounded,
# the baseline end square.
THICKEST = 20
GAP = 2
RADIUS = 4

# Axis steps that read as clean numbers, chosen so there are at most five
# gridlines above the baseline.
STEPS = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000)
MOST_GRIDLINES = 5
MOST_WEEK_LABELS = 6


@bp.before_request
def _admins_only():
    bounce = guard()
    if bounce is not None:
        return bounce
    if not is_admin():
        abort(404)
    return None


# `strict_slashes=False`, so `/admin/` is the page and not a 404. Flask only
# adds the slash-tolerant redirect to rules that *end* in one, and the first
# person to open this typed the slash — a 404 that arrives before the admin
# check runs looks exactly like not being on the list.
@bp.route("/admin", strict_slashes=False)
def growth_page():
    weeks = span(request.args.get("weeks"))
    pool = current_app.config["POOL"]
    rows = growth.history(pool)
    # UTC, because the counter is in UTC days and there is no family clock.
    today = datetime.now(timezone.utc).date()
    weekly = growth.by_week(rows, weeks, today)
    total = growth.totals(rows)
    families = growth.families_now(pool)
    pulse = heartbeat.verdict(heartbeat.last(pool), datetime.now(timezone.utc),
                              stale_after())
    response = make_response(render_template(
        "admin/growth.html",
        weekly=weekly, latest=weekly[-1], span=weeks, spans=SPANS,
        totals=total, families_now=families,
        # Every signup since the counter began is either a family that still
        # exists or one that was deleted. Clamped, in case a family predates
        # the counter in a way the backfill could not see.
        deleted=max(0, total.signups - families),
        chart=chart(weekly),
        pulse=pulse, pulse_word=PULSE_WORDS[pulse["status"]],
        pulse_text=pulse_text(pulse),
    ))
    # Counts, not anybody's data — but it is the business's own page, and a
    # shared cache has no business holding it.
    response.headers["Cache-Control"] = "no-store"
    return response


def span(raw):
    """How many weeks to show: the query string, bounded, or the default."""
    try:
        weeks = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_WEEKS
    return min(MOST_WEEKS, max(1, weeks))


# -- the worker's pulse -------------------------------------------------------

# One word for the pill beside the sentence: the three answers `heartbeat.verdict`
# can give, in the operator's language.
PULSE_WORDS = {"ok": "Alive", "stale": "Quiet", "never": "Never run"}


def pulse_text(pulse):
    """The worker's last pass in one sentence, from what `heartbeat.verdict` said."""
    if pulse["status"] == "never":
        return "No pass has finished yet."
    last = pulse["last_pass"]
    families = last["families"]
    return (f"Last pass finished {ago(pulse['age_seconds'])}: "
            f"{families} {'family' if families == 1 else 'families'}, "
            f"{'none failed' if not last['failed'] else str(last['failed']) + ' failed'}, "
            f"{last['took_ms'] / 1000:.1f} s.")


def ago(seconds):
    """`seconds` as a person would say it. Coarse on purpose: the page is not a clock."""
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'' if minutes == 1 else 's'} ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} hour{'' if hours == 1 else 's'} ago"
    return f"{hours // 24} days ago"


# -- the drawing ------------------------------------------------------------

def scale(highest):
    """The axis ceiling and its step: clean numbers, at most five gridlines.

    `highest` is the tallest value on the chart. The ceiling is the next
    multiple of the step at or above it, so the tallest column reaches the top
    gridline only when it happens to land on one.
    """
    highest = max(1, int(highest))
    for step in STEPS:
        if highest <= step * MOST_GRIDLINES:
            break
    return step * math.ceil(highest / step), step


def chart(weekly):
    """Everything the template needs to draw the columns, as plain numbers.

    Worked out here rather than in Jinja because it is arithmetic, and
    arithmetic in a template is arithmetic nobody tests.
    """
    ceiling, step = scale(max(max(w.signups, w.activations) for w in weekly))
    count = len(weekly)
    slot = PLOT_W / count
    thickness = min(THICKEST, max(1.5, (slot - GAP) / 2 * 0.72))
    pair = 2 * thickness + GAP
    label_every = max(1, math.ceil(count / MOST_WEEK_LABELS))

    def y_of(value):
        return TOP + PLOT_H * (1 - value / ceiling)

    columns = []
    for i, week in enumerate(weekly):
        slot_x = LEFT + i * slot
        x = slot_x + (slot - pair) / 2
        bars = []
        for series, value in (("signups", week.signups),
                              ("activations", week.activations)):
            y = y_of(value)
            bars.append({"series": series, "value": value, "x": round(x, 2),
                         "y": round(y, 2),
                         "path": column_path(x, y, thickness, TOP + PLOT_H - y)})
            x += thickness + GAP
        columns.append({
            "week": week,
            "slot_x": round(slot_x, 2), "slot_w": round(slot, 2),
            "bars": bars,
            "last": i == count - 1,
            # Counted from the right, so the latest week is always labelled.
            "label": (week.start.strftime("%-d %b")
                      if (count - 1 - i) % label_every == 0 else ""),
        })

    return {
        "width": WIDTH, "height": HEIGHT,
        "left": LEFT, "right": WIDTH - RIGHT, "top": TOP, "plot_h": PLOT_H,
        "baseline": TOP + PLOT_H, "thickness": round(thickness, 2),
        "gridlines": [{"value": v, "y": round(y_of(v), 2)}
                      for v in range(0, ceiling + 1, step)],
        "columns": columns,
    }


def column_path(x, y, width, height):
    """A column with a rounded top and a square foot, or "" for nothing.

    A zero draws nothing rather than a hairline: the week is still there, in
    its label, its hover text and the table, and an empty week should look
    empty.
    """
    if height <= 0:
        return ""
    r = min(RADIUS, width / 2, height)
    foot = y + height
    return (f"M{x:.2f},{foot:.2f} V{y + r:.2f} Q{x:.2f},{y:.2f} {x + r:.2f},{y:.2f} "
            f"H{x + width - r:.2f} Q{x + width:.2f},{y:.2f} {x + width:.2f},{y + r:.2f} "
            f"V{foot:.2f} Z")
