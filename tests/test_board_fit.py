"""A short panel drops rows instead of clipping them.

Body is `height: 100vh; overflow: hidden`, so a day that does not fit at the
readable floor would otherwise be cut off with no sign that anything was
missing. The script in `board.html` hides locations, then tomorrow, and only
then the tail of today — and a `+N more` line counts those, so a row is never
left half on screen.

The three larger sizes are a light day that already fits. They must not gain
`.tight` or lose tomorrow: the floor and the label minimum only apply once
the root would otherwise be unreadably small.
"""

import os
import re
import threading
from pathlib import Path

import pytest
from flask import render_template
from werkzeug.serving import make_server

from dinkydash.store import FileStore
from web import create_app

REPO = Path(__file__).resolve().parents[1]
BOARD = REPO / "web" / "templates" / "board.html"

LONG = "Parish hall, 120 High Street, Northbridge"
# Long enough to wrap under a 25px title in the Pi's agenda column, so today
# alone is taller than 480px once tomorrow has gone.
WRAPPED = "School run the long way round past the park, the library and the baker"


def event(time_, title, location):
    return {"title": title, "time": time_, "all_day": False, "location": location}


def view(events, tomorrow, headline, clock="24h", theme="light", countdowns=None):
    return {
        "family_name": "The Wilsons",
        "theme": theme,
        "clock": clock,
        "date_display": "Wednesday, 14 October",
        "headline": headline,
        "events": [event(*row) for row in events],
        "tomorrow": [event(*row) for row in tomorrow],
        "chores": [
            {"emoji": "🍽", "title": "Set the table", "assigned_to": "Mia"},
            {"emoji": "🦴", "title": "Feed Biscuit", "assigned_to": "Theo"},
        ],
        "countdowns": countdowns or [
            {"days": 12, "emoji": "🎄", "title": "Christmas"},
            {"days": 2, "emoji": "🎂", "title": "Mia's birthday"},
            {"days": 40, "emoji": "☀️", "title": "Summer holidays"},
        ],
        "state": "ready",
        "overdue": False,
        "stale": False,
        "reload_seconds": 300,
        "today": "2026-10-14",
        "timezone": "Europe/Berlin",
    }


BUSY_TODAY = [
    ("08:05", "School run", LONG),
    ("09:20", "Swimming lesson", "Stadtbad, Pool lane 3, Northbridge"),
    ("10:45", "Dentist checkup", "Oak House surgery, 14 Station Road"),
    ("12:10", "Lunch at Oma's", "Gartenstrasse 8, upstairs flat"),
    ("13:30", "Library books due", "Town library, children's floor"),
    ("15:00", "Football training", "Sportplatz, Meadow Lane, Northbridge"),
    ("16:40", "Piano lesson", "Mrs Adler, 9 Chapel Lane"),
    ("18:15", "Family supper", "Home, the big table"),
]
BUSY_TOMORROW = [
    ("08:30", "Term starts", "School gate, West entrance, Northbridge"),
    ("11:00", "Vaccination", "Clinic, 40 Market Street, second floor"),
    ("14:15", "Playdate", "The Rec, Pavilion Road, Northbridge"),
    ("17:00", "Parents' evening", "School hall, 2 School Lane, Northbridge"),
]
BUSY = view(BUSY_TODAY, BUSY_TOMORROW, "Eight things today, and tomorrow is full too.")
PACKED = view(
    [(f"{8 + i:02d}:00", f"Thing {i}: {WRAPPED}", LONG) for i in range(8)],
    [(f"{9 + i:02d}:00", f"Tomorrow {i}: {WRAPPED}", LONG) for i in range(4)],
    "A packed day from breakfast until supper.",
)
LIGHT = view(
    [("09:30", "Swimming lesson", "Stadtbad")],
    [("14:15", "Dentist", None)],
    "Swimming, then a quiet afternoon.",
)
# Long enough that the narrow side column wraps them; a wider column holds
# each on one line. The words are not what the assertions check.
LONG_COUNTS = [
    {"days": 64, "emoji": "🎂", "title": "Jack's birthday"},
    {"days": 12, "emoji": "🎄", "title": "Christmas"},
    {"days": 40, "emoji": "☀️", "title": "Summer holidays"},
]
EMPTY = view(
    [],
    [("8:00 am", "Swimming lesson", "Stadtbad"), ("12:00 pm", "Lunch with Grandma", None)],
    "Nothing booked in all day.",
    clock="12h",
    countdowns=LONG_COUNTS,
)
TWELVE = view(
    [("12:00 pm", "Swimming lesson", "Stadtbad"), ("8:00 am", "School run", None)],
    [
        ("12:00 pm", "Lunch with Grandma", None),
        ("3:45 pm", "Piano lesson", None),
    ],
    "Swimming, then a quiet afternoon.",
    clock="12h",
    countdowns=LONG_COUNTS,
)

# CSS pixels, and the device pixel ratio a real panel reported. The ratio does
# not change the layout; it is part of the size being held steady.
LIGHT_SIZES = (
    ("1024x744", 1024, 744, 2),
    ("768x1004", 768, 1004, 2),
    ("1500x1000", 1500, 1000, 1.6),
)

MEASURE = """
() => {
  const roomH = window.innerHeight;
  const roomW = window.innerWidth;
  const over = [];
  const nodes = document.body.querySelectorAll("*");
  for (let i = 0; i < nodes.length; i++) {
    const el = nodes[i];
    const style = getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") continue;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) continue;
    if (rect.bottom > roomH + 1 || rect.top < -1 || rect.right > roomW + 1) {
      over.push({
        cls: String(el.className).slice(0, 60),
        top: Math.round(rect.top),
        bottom: Math.round(rect.bottom)
      });
    }
  }
  const today = document.querySelectorAll(".agenda > .events > .event");
  let hidden = 0;
  let firstHidden = false;
  for (let i = 0; i < today.length; i++) {
    const gone = getComputedStyle(today[i]).display === "none";
    if (gone) hidden += 1;
    if (i === 0) firstHidden = gone;
  }
  const tomorrow = document.querySelector(".tomorrow");
  const label = document.querySelector(".label");
  const more = document.querySelector(".agenda > .events > .more");
  const root = parseFloat(getComputedStyle(document.documentElement).fontSize);
  const empty = document.querySelector(".empty");
  let emptySlack = null;
  let tomorrowGap = null;
  if (empty) {
    const kids = empty.children;
    const first = kids[0].getBoundingClientRect();
    const last = kids[kids.length - 1].getBoundingClientRect();
    const style = getComputedStyle(empty);
    const expected = (last.bottom - first.top)
      + parseFloat(style.paddingTop) + parseFloat(style.paddingBottom)
      + (parseFloat(getComputedStyle(kids[0]).marginTop) || 0)
      + (parseFloat(getComputedStyle(kids[kids.length - 1]).marginBottom) || 0);
    emptySlack = empty.getBoundingClientRect().height - expected;
    if (tomorrow) tomorrowGap = tomorrow.getBoundingClientRect().top - empty.getBoundingClientRect().bottom;
  }
  const agendaBox = document.querySelector(".agenda");
  const sideBox = document.querySelector(".side");
  const body = document.querySelector(".body");
  const grid = body ? getComputedStyle(body).gridTemplateColumns : "none";
  let sideShare = null;
  if (agendaBox && sideBox) {
    const a = agendaBox.getBoundingClientRect().width;
    const s = sideBox.getBoundingClientRect().width;
    if (a + s > 0) sideShare = s / (a + s);
  }
  const countdownLines = [];
  const counts = document.querySelectorAll(".countdown span:last-child");
  for (let i = 0; i < counts.length; i++) {
    const lh = parseFloat(getComputedStyle(counts[i]).lineHeight);
    if (lh) countdownLines.push(counts[i].getBoundingClientRect().height / lh);
  }
  let timeColumnRem = 0;
  let tomorrowColumnRem = 0;
  let timeOverflow = 0;
  let meridiemSmaller = false;
  const times = document.querySelectorAll(".event-time");
  for (let i = 0; i < times.length; i++) {
    const el = times[i];
    if (el.getBoundingClientRect().width === 0) continue;
    const copy = el.cloneNode(true);
    copy.style.width = "max-content";
    copy.style.position = "absolute";
    el.parentElement.appendChild(copy);
    const natural = copy.getBoundingClientRect().width;
    copy.parentElement.removeChild(copy);
    const box = el.getBoundingClientRect();
    const rem = box.width / root;
    const inTomorrow = !!(el.closest && el.closest(".tomorrow"));
    if (inTomorrow) {
      if (rem > tomorrowColumnRem) tomorrowColumnRem = rem;
    } else if (rem > timeColumnRem) {
      timeColumnRem = rem;
    }
    if (natural - box.width > timeOverflow) timeOverflow = natural - box.width;
    const suffix = el.querySelector(".meridiem");
    if (suffix) {
      meridiemSmaller = parseFloat(getComputedStyle(suffix).fontSize)
        < parseFloat(getComputedStyle(el).fontSize) - 0.5;
    }
  }
  return {
    width: roomW,
    height: roomH,
    fontSize: root,
    labelSize: label ? parseFloat(getComputedStyle(label).fontSize) : 0,
    today: today.length,
    hidden: hidden,
    firstHidden: firstHidden,
    tomorrowShown: !!(tomorrow && getComputedStyle(tomorrow).display !== "none"),
    boardClass: (document.querySelector(".board") || {}).className || "",
    bodyClass: body ? body.className : "",
    more: more ? more.textContent : "",
    moreHidden: more ? more.hidden : true,
    over: over,
    emptySlack: emptySlack,
    tomorrowGap: tomorrowGap,
    twoColumn: grid !== "none",
    sideShare: sideShare,
    countdownLines: countdownLines,
    timeColumnRem: timeColumnRem,
    tomorrowColumnRem: tomorrowColumnRem,
    timeOverflow: timeOverflow,
    meridiemSmaller: meridiemSmaller
  };
}
"""


def _launch(playwright):
    errors = []
    for kwargs in ({}, {"channel": "chrome"}):
        try:
            return playwright.chromium.launch(**kwargs)
        except Exception as exc:
            errors.append(f"{kwargs or 'bundled'}: {exc}")
    message = "Chromium is not available (" + "; ".join(errors) + "). " \
        "Install it with: python -m playwright install chromium"
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(message)


@pytest.fixture(scope="module")
def browser():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    manager = sync_playwright().start()
    launched = _launch(manager)
    yield launched
    launched.close()
    manager.stop()


@pytest.fixture(scope="module")
def origin(tmp_path_factory):
    folder = tmp_path_factory.mktemp("board-fit")
    config = folder / "config.yaml"
    config.write_text('family_name: "The Wilsons"\ntimezone: "Europe/Berlin"\ntheme: light\n')
    app = create_app(FileStore(config))
    pages = {"busy": BUSY, "packed": PACKED, "light": LIGHT, "empty": EMPTY, "twelve": TWELVE}

    @app.route("/fixture/<name>")
    def fixture(name):
        return render_template(
            "board.html", view=pages[name], manifest_url="/manifest.webmanifest")

    server = make_server("127.0.0.1", 0, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def settle(page, url):
    page.goto(url, wait_until="networkidle")
    page.evaluate("() => document.fonts.ready")
    page.evaluate(
        "() => new Promise(function (resolve) {"
        " requestAnimationFrame(function () { requestAnimationFrame(resolve); });"
        "})"
    )
    return page.evaluate(MEASURE)


def open_at(browser, origin, name, width, height, scale):
    context = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=scale,
    )
    page = context.new_page()
    try:
        return settle(page, f"{origin}/fixture/{name}")
    finally:
        context.close()


class TestTheSource:
    """The shedding rules are in the page a panel actually loads."""

    def test_labels_have_a_floor_and_rows_are_shed_in_order(self):
        css = BOARD.read_text()
        assert "font-size: max(0.82rem, 12px);" in css
        assert ".tight .event-where { display: none; }" in css
        assert ".drop-tomorrow .tomorrow { display: none; }" in css
        assert "@media (max-height: 520px)" in css
        assert ".tomorrow .event-where { display: none; }" in css
        script = css.split("<script>", 1)[1]
        # Locations go before tomorrow, and tomorrow before any of today.
        assert script.index('classList.add("tight")') < script.index('classList.add("drop-tomorrow")')
        assert script.index('classList.add("drop-tomorrow")') < script.index("trimToday(room);")
        assert "var FLOOR = 13;" in script


class TestABusyPanel:
    """800×480, the Pi. Tomorrow leaves before any of today's events do."""

    def test_eight_events_fit_without_clipping_and_tomorrow_goes_first(self, browser, origin):
        data = open_at(browser, origin, "busy", 800, 480, 1)
        assert data["width"] == 800 and data["height"] == 480
        assert data["over"] == []
        assert data["today"] == 8
        assert data["tomorrowShown"] is False
        assert data["hidden"] == 0
        assert data["firstHidden"] is False
        assert "tight" in data["boardClass"]
        assert "drop-tomorrow" in data["boardClass"]
        assert data["fontSize"] >= 13
        assert data["labelSize"] >= 12
        assert data["moreHidden"] is True

    def test_today_that_still_overflows_counts_the_hidden_rows(self, browser, origin):
        data = open_at(browser, origin, "packed", 800, 480, 1)
        assert data["over"] == []
        assert data["today"] == 8
        assert data["tomorrowShown"] is False
        assert data["hidden"] > 0
        assert data["firstHidden"] is False
        assert data["hidden"] < data["today"]
        assert data["moreHidden"] is False
        assert int(re.search(r"\d+", data["more"]).group()) == data["hidden"]
        assert "drop-tomorrow" in data["boardClass"]
        assert data["labelSize"] >= 12


class TestALightDayIsUnchanged:
    """Larger panels on a quiet day already fit, so nothing is shed."""

    @pytest.mark.parametrize("label,width,height,scale", LIGHT_SIZES)
    def test_the_day_stays_whole(self, browser, origin, label, width, height, scale):
        data = open_at(browser, origin, "light", width, height, scale)
        assert data["width"] == width and data["height"] == height, label
        assert data["over"] == [], label
        assert data["tomorrowShown"] is True, label
        assert data["hidden"] == 0, label
        assert data["boardClass"] == "board", label
        assert data["moreHidden"] is True, label
        # Above the floor, and above the point where the 12px label minimum
        # would take over from 0.82rem, so the type is the size the search found.
        assert data["fontSize"] > 16, label
        assert data["labelSize"] == pytest.approx(data["fontSize"] * 0.82, abs=0.2)
        assert "day-empty" not in data["bodyClass"], label
        if data["twoColumn"]:
            # Agenda keeps the wider share when today has events.
            assert data["sideShare"] == pytest.approx(1 / 2.55, abs=0.02), label


class TestAnEmptyDay:
    """A quiet today is the height of its words, and the side column is wider."""

    @pytest.mark.parametrize("label,width,height,scale", LIGHT_SIZES)
    def test_the_empty_box_hugs_its_words_and_countdowns_stay_one_line(
        self, browser, origin, label, width, height, scale
    ):
        data = open_at(browser, origin, "empty", width, height, scale)
        assert data["width"] == width and data["height"] == height, label
        assert data["over"] == [], label
        assert data["tomorrowShown"] is True, label
        assert data["boardClass"] == "board", label
        assert "day-empty" in data["bodyClass"], label
        # The box is the words, the padding and the gap. A flex-grow would
        # add a tall blank and push tomorrow down by that much.
        assert data["emptySlack"] == pytest.approx(0, abs=4), label
        assert 0 <= data["tomorrowGap"] < data["fontSize"] * 1.3, label
        assert data["countdownLines"], label
        assert max(data["countdownLines"]) < 1.4, label
        if data["twoColumn"]:
            assert data["sideShare"] > 0.52, label


class TestTheTwelveHourColumn:
    """The suffix is smaller, so the column comes in under a full-size one."""

    def test_the_column_fits_the_widest_time_and_is_narrower(self, browser, origin):
        data = open_at(browser, origin, "twelve", 1024, 744, 2)
        assert data["over"] == []
        # Under the full-size suffix column, and the widest time still fits.
        assert data["timeColumnRem"] < 7.4
        assert data["timeOverflow"] <= 1
        assert data["tomorrowColumnRem"] < data["timeColumnRem"] - 0.5
        assert data["meridiemSmaller"] is True
