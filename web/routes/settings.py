"""The settings UI.

Every list section — people, pets, chores, dates, calendars — is the same
shape: a list, an edit form, a delete. So they share one pair of routes driven
by the SECTIONS table below rather than five near-identical copies.

Writes go straight back to config.yaml through ruamel's round-trip mode, so the
comments in the file survive being edited from a phone.
"""

import logging
from datetime import datetime, time, timezone

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, url_for)

from dinkydash import config as config_module
from dinkydash import schedule
from dinkydash.calendars import FeedError, addresses, describe_feed, feed_label
from dinkydash.claude_client import GenerationError
from dinkydash.context import compute_birthday_info, upcoming_for
from dinkydash.runner import forget_calendar, refresh_calendars
from dinkydash.runner import run as run_generation
from web import manifest as manifest_module
from web.family import current_store
from web.session import guard

log = logging.getLogger(__name__)

bp = Blueprint("settings", __name__)


@bp.before_request
def _needs_a_session():
    """Cloud mode: everything under /settings is behind a magic link.

    `guard()` reads the mode off `current_app` rather than being registered
    conditionally, because this blueprint object is shared by every app built
    in a process — attaching a cloud-mode hook to it would follow the next
    single-mode app that imported it.
    """
    return guard()


# Each field is (name, label, kind, required, help). `kind` decides both the
# input rendered and how the posted value is parsed back.
SECTIONS = {
    "people": {
        "key": "people",
        "title": "People",
        "singular": "person",
        "add_label": "Add a person",
        "blurb": "Birthdays here become countdowns, and names here are who chores rotate between.",
        "fields": [
            ("name", "Name", "text", True, ""),
            ("date_of_birth", "Date of birth", "date", True, "Used for ages and the birthday countdown."),
            ("avatar_emoji", "Emoji", "emoji", False, ""),
            ("avatar_color", "Colour", "color", False, ""),
            ("interests", "Interests", "textarea", False,
             "Feeds the daily line — try “dinosaurs, drawing, swimming”."),
        ],
    },
    "pets": {
        "key": "pets",
        "title": "Pets",
        "singular": "pet",
        "add_label": "Add a pet",
        "blurb": "With a pet on file, some days the board's note is about them.",
        "fields": [
            ("name", "Name", "text", True, ""),
            ("type", "Kind of animal", "text", False, "Dog, cat, rabbit…"),
            ("avatar_emoji", "Emoji", "emoji", False, ""),
        ],
    },
    "recurring": {
        "key": "recurring",
        "title": "Chores",
        "singular": "job",
        "add_label": "Add a job",
        "blurb": "Jobs hand over at midnight and keep to the order you set. Nobody ticks anything off.",
        "fields": [
            ("title", "Job", "text", True, ""),
            ("emoji", "Emoji", "emoji", False, ""),
            ("choices", "Whose turn, in order", "people", True,
             "Rotates one person per day, by day of the year."),
        ],
    },
    "special_dates": {
        "key": "special_dates",
        "title": "Special dates",
        "singular": "date",
        "add_label": "Add a date",
        "blurb": "These come back every year, so there is no year to fill in. Birthdays are counted down already.",
        "fields": [
            ("title", "What is it", "text", True, ""),
            ("emoji", "Emoji", "emoji", False, ""),
            ("date", "Date", "monthday", True, "Day and month — it repeats every year."),
        ],
    },
    "calendars": {
        "key": "calendars",
        "title": "Calendars",
        "singular": "calendar",
        "add_label": "Add a calendar",
        "blurb": "Every calendar you switch on is merged into one agenda. Titles and times are "
                 "sent to Claude each morning; an event kept off the board by a guest list is not.",
        "fields": [
            ("label", "Call it", "text", True, ""),
            ("url", "iCal link", "url", True,
             "Google → Settings and sharing → Integrate calendar → Secret address in iCal format. "
             "iCloud → share the calendar → Public Calendar → Copy Link (a webcal:// link is "
             "fine, it is converted for you). Outlook → Settings → Calendar → Shared calendars → "
             "Publish a calendar, then the ICS link. Links must be https."),
            ("shared_with", "Only show events shared with", "emails", False,
             "Email addresses, with commas between them. Only events with one of these people "
             "on the guest list, or organised by them, go on the board — the rest of this "
             "calendar stays private. Use the address on the invitation. Leave it empty to "
             "show everything."),
            ("enabled", "Show on the board", "checkbox", False, ""),
        ],
    },
}

EMOJI_SUGGESTIONS = {
    "people": ["🦖", "⚽", "🎨", "☕", "🚀", "🎸", "🐙", "📚"],
    "pets": ["🐕", "🐈", "🐰", "🐠", "🐹", "🐦", "🐢", "🐴"],
    "recurring": ["🍽", "🦴", "🗑", "🧺", "🛏", "🌱", "🧹", "📦"],
    "special_dates": ["🎄", "☀️", "🚂", "🎃", "✈️", "🎆", "🥚", "🍂"],
}

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# How often the calendars are re-fetched. A short list rather than a free
# number: the useful range is bounded at both ends, and Google's own feed is
# cached, so anything under a quarter of an hour would be a promise we cannot
# keep. The engine takes any integer — these are what the page offers.
REFRESH_CHOICES = (15, 30, 60, 360, 1440)


def current_config():
    config = current_store().load_config()
    if config_module.ensure_ids(config):
        # A config written by hand, or before ids existed. Give its items ids
        # once, so the links on this page keep meaning the same thing.
        save(config)
    return config


def save(config):
    current_store().save_config(config)


def section_or_404(name):
    section = SECTIONS.get(name)
    if not section:
        abort(404)
    return section


def parse_field(field, form, existing):
    """Read one posted field back into its config value."""
    name, _label, kind, required, _help = field
    if kind == "checkbox":
        return name in form
    if kind == "people":
        values = [v for v in form.getlist(name) if v]
        return values
    if kind == "emails":
        # One text box, stored as a list: what the engine compares against.
        return addresses(form.get(name, ""))
    if kind == "monthday":
        month = form.get(f"{name}_month", "").strip()
        day = form.get(f"{name}_day", "").strip()
        if not (month and day):
            return existing.get(name, "")
        return f"{int(month):02d}/{int(day):02d}"
    value = form.get(name, "").strip()
    if kind == "date" and value:
        # <input type="date"> already gives YYYY-MM-DD.
        return value
    return value


def validate(section, item):
    """Return a list of human-readable problems with a submitted item."""
    problems = []
    for name, label, kind, required, _help in section["fields"]:
        value = item.get(name)
        if required and not value:
            problems.append(f"{label} is needed.")
        if kind == "date" and value:
            try:
                datetime.strptime(str(value), "%Y-%m-%d")
            except ValueError:
                problems.append(f"{label} should look like 2017-03-15.")
        if kind == "emails":
            for address in value or []:
                if "@" not in address:
                    problems.append(f"“{address}” is not an email address. Use the address "
                                    f"on the invitation, like sam@example.com.")
    return problems


@bp.route("/")
def home():
    config = current_config()
    today = config_module.today_for(config)
    payload = current_store().load_payload(config)

    tzinfo = config_module.tzinfo_for(config)
    status = {"state": "waiting", "detail": "No board has been generated yet."}
    if payload:
        generated_for = payload.get("generated_for_date")
        written = _clock(payload.get("generated_at"), tzinfo)
        if generated_for == today.isoformat():
            status = {"state": "ready",
                      "detail": f"Today's board is up — written {written or 'earlier'}."}
        elif generated_for:
            status = {"state": "stale", "detail": f"Showing the board from {generated_for}."}
        # A refresh with no brief yet leaves a payload holding only the agenda,
        # so an unwritten board stays "waiting" rather than claiming a date.
        fetched = _clock(payload.get("calendars_fetched_at"), tzinfo)
        if fetched:
            status["detail"] += f" Calendars refreshed {fetched}."

    calendars = config.get("calendars") or []
    broken = [c for c in (payload or {}).get("calendar_statuses", []) if c.get("ok") is False]

    counts = {
        "people": len(config.get("people") or []),
        "pets": len(config.get("pets") or []),
        "recurring": len(config.get("recurring") or []),
        "special_dates": len(config.get("special_dates") or []),
        "calendars": len(calendars),
    }
    return render_template(
        "settings/home.html", config=config, status=status, counts=counts,
        broken=broken, sections=SECTIONS, cadence=cadence_summary(config),
    )


def _clock(stamp, tzinfo):
    """An ISO timestamp as the time on the family's own clock, or None.

    Stamps are written in UTC. The server is often not in the family's timezone
    — a Pi is frequently left on UTC, and hosted the server is nowhere near
    them — so reading the characters out of the string showed the wrong time.
    """
    if not stamp:
        return None
    try:
        moment = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(tzinfo).strftime("%H:%M")


@bp.route("/manifest.webmanifest")
def manifest():
    """The name and icon a phone gives this page on its home screen.

    Read straight from the store rather than through `current_config`: fetching
    a manifest must not be able to write config.yaml.
    """
    config = current_store().load_config()
    family = config.get("family_name")
    return manifest_module.response(
        id=url_for("settings.home"),
        name="DinkyDash settings",
        # What fits under the icon. Not "Settings" — that is already an app.
        short_name="DinkyDash",
        description=f"Change what {family} sees on the board." if family
                    else "Change what the board shows.",
        start_url=url_for("settings.home"),
        background_color="#fffaf5",
        theme_color="#fffaf5",
    )


@bp.route("/generate", methods=["POST"])
def generate_now():
    config = current_config()
    try:
        payload = run_generation(config, current_store())
    except GenerationError as exc:
        flash(str(exc), "error")
    except Exception as exc:  # a broken feed or an unreadable file shouldn't 500 the UI
        log.exception("Generation failed")
        flash(f"Generation failed: {exc}", "error")
    else:
        flash(f"Board rewritten — “{payload['headline']}”", "ok")
    return redirect(url_for("settings.home"))


@bp.route("/<section_name>")
def section_list(section_name):
    section = section_or_404(section_name)
    config = current_config()
    items = config.get(section["key"]) or []
    today = config_module.today_for(config)

    extras = {}
    if section_name == "people":
        extras["birthdays"] = [compute_birthday_info(p, today) for p in items]
    if section_name == "recurring":
        extras["turns"] = [upcoming_for(c, today, days=1) for c in items]

    return render_template(
        "settings/list.html", section=section, section_name=section_name,
        items=items, extras=extras, config=config,
    )


@bp.route("/<section_name>/<item_id>", methods=["GET", "POST"])
def section_edit(section_name, item_id):
    section = section_or_404(section_name)
    config = current_config()
    items = config.setdefault(section["key"], [])

    is_new = item_id == "new"
    if is_new:
        item = {"enabled": True} if section_name == "calendars" else {}
        index = None
    else:
        index, item = config_module.find_item(items, item_id)
        if item is None:
            abort(404)

    problems, checked = [], None

    if request.method == "POST":
        submitted = dict(item)
        for field in section["fields"]:
            submitted[field[0]] = parse_field(field, request.form, item)

        if request.form.get("action") == "check":
            checked = check_feed(submitted, config)
            item = submitted
        else:
            problems = validate(section, submitted)
            if not problems:
                if is_new:
                    submitted["id"] = config_module.new_id(
                        i.get("id") for i in items if isinstance(i, dict)
                    )
                    items.append(submitted)
                else:
                    submitted["id"] = item_id
                    items[index] = submitted
                save(config)
                if section_name == "calendars":
                    # What this calendar last said was fetched under the old
                    # entry — before a guest list, say — so it goes, and the
                    # next tick fetches afresh. Under the old name as well as
                    # the new, in case this was a rename.
                    stale = {feed_label(submitted)} | ({feed_label(item)} if not is_new else set())
                    forget_calendar(config, current_store(), stale)
                    flash(f"Saved {feed_label(submitted)}. The board picks up the change at "
                          f"the next refresh — press Refresh calendars if you don't want to wait.",
                          "ok")
                else:
                    flash(f"Saved {submitted.get('name') or submitted.get('title') or 'it'}.", "ok")
                return redirect(url_for("settings.section_list", section_name=section_name))
            item = submitted

    return render_template(
        "settings/edit.html", section=section, section_name=section_name,
        item=item, item_id=item_id, is_new=is_new, problems=problems,
        checked=checked, config=config, months=MONTHS,
        emoji=EMOJI_SUGGESTIONS.get(section_name, []),
        colors=config_module.AVATAR_COLORS, people=config_module.people_names(config),
    )


def check_feed(item, config):
    """Fetch a pasted iCal URL and describe what came back.

    With a guest list on the form, the answer is "3 of the 24" — and a red
    "none of them" when the list matches nobody. That case is the failure the
    old global filter hid: a working link, a full calendar, and a board with
    nothing on it. Red, because that is exactly what saving would give.
    """
    url = (item.get("url") or "").strip()
    if not url:
        return {"ok": False, "message": "Paste a link first."}
    wanted = addresses(item.get("shared_with"))
    try:
        found = describe_feed(
            url, config_module.tzinfo_for(config),
            today=config_module.today_for(config),
            days_ahead=int(config.get("calendar_days_ahead") or 14),
            shared_with=wanted,
        )
    except FeedError as exc:
        return {"ok": False, "message": str(exc)}
    days = found["days_ahead"]
    if not found["total"]:
        return {"ok": True, "message":
                f"That link works, but there is nothing on it in the next {days} days."}
    who = ", ".join(wanted)
    if wanted and not found["count"]:
        return {"ok": False, "message":
                f"That link works and has {found['total']} events in the next {days} days, "
                f"but none of them is shared with {who}. Check the address — it has to be "
                f"the one on the invitation."}
    if wanted:
        count = found["count"]
        lead = (f"{count} of the {found['total']} events over the next {days} days "
                f"{'is' if count == 1 else 'are'} shared with {who}.")
    else:
        lead = f"{found['count']} events over the next {days} days."
    nxt = found["next"]
    tail = ""
    if nxt:
        when = "all day" if nxt["all_day"] else nxt["time"]
        tail = f" Next up: {nxt['title']}, {nxt['date']} at {when}."
    return {"ok": True, "message": lead + tail}


@bp.route("/<section_name>/<item_id>/delete", methods=["POST"])
def section_delete(section_name, item_id):
    section = section_or_404(section_name)
    config = current_config()
    items = config.get(section["key"]) or []
    index, removed = config_module.find_item(items, item_id)
    if removed is None:
        abort(404)
    items.pop(index)
    save(config)
    if section_name == "calendars":
        forget_calendar(config, current_store(), {feed_label(removed)})
    flash(f"Removed {removed.get('name') or removed.get('title') or removed.get('label') or 'it'}.", "ok")
    return redirect(url_for("settings.section_list", section_name=section_name))


@bp.route("/<section_name>/<item_id>/move", methods=["POST"])
def section_move(section_name, item_id):
    """Reorder within a list — chore rotation order is the reason this exists."""
    section = section_or_404(section_name)
    config = current_config()
    items = config.get(section["key"]) or []
    index, item = config_module.find_item(items, item_id)
    if item is None:
        abort(404)
    target = index + (-1 if request.form.get("direction") == "up" else 1)
    if 0 <= target < len(items):
        items[index], items[target] = items[target], items[index]
        save(config)
    return redirect(url_for("settings.section_list", section_name=section_name))


@bp.route("/screen", methods=["GET", "POST"])
def screen():
    config = current_config()
    if request.method == "POST":
        theme = request.form.get("theme")
        if theme in config_module.THEMES:
            config["theme"] = theme
            save(config)
            flash(f"Board set to {theme}.", "ok")
        return redirect(url_for("settings.screen"))
    return render_template("settings/screen.html", config=config, themes=config_module.THEMES)


def describe_minutes(minutes):
    """An interval as the page says it — "Every hour", not "60"."""
    if minutes == 1440:
        return "Once a day"
    if minutes >= 60 and minutes % 60 == 0:
        hours = minutes // 60
        return "Every hour" if hours == 1 else f"Every {hours} hours"
    return "Every minute" if minutes == 1 else f"Every {minutes} minutes"


def cadence_choices(current):
    """The offered intervals, plus whatever the file already says if it differs.

    A hand-edited `refresh_minutes: 45` is a real setting, and a select that
    could not show it would silently rewrite it the first time anyone saved.
    """
    minutes = sorted(set(REFRESH_CHOICES) | {current})
    return [(m, describe_minutes(m)) for m in minutes]


def cadence_values(config):
    """The two keys as the form wants them — an int and an "HH:MM" string."""
    return {
        "refresh_minutes": int(schedule.refresh_interval(config).total_seconds() // 60),
        "brief_time": schedule.brief_time(config).strftime("%H:%M"),
    }


def cadence_summary(config):
    """The one line the settings home shows: "Calendars every hour · brief at 06:00"."""
    values = cadence_values(config)
    cadence = describe_minutes(values["refresh_minutes"])
    return (f"Calendars {cadence[:1].lower()}{cadence[1:]} · "
            f"brief at {values['brief_time']}")


@bp.route("/refresh", methods=["GET", "POST"])
def refresh():
    """The two cadences: how often the calendars are fetched, and when the brief is written."""
    config = current_config()
    stored = cadence_values(config)
    choices = cadence_choices(stored["refresh_minutes"])
    allowed = {m for m, _ in choices}
    values, problems = stored, []

    if request.method == "POST":
        # Show back what was submitted, not what is still on disk.
        values = {
            "refresh_minutes": request.form.get("refresh_minutes", "").strip(),
            "brief_time": request.form.get("brief_time", "").strip(),
        }
        minutes, brief = None, None
        try:
            minutes = int(values["refresh_minutes"])
        except ValueError:
            pass
        if minutes not in allowed:
            problems.append("Pick one of the calendar intervals offered.")
        try:
            # <input type="time"> posts "HH:MM", but "HH:MM:SS" with a step set.
            brief = time.fromisoformat(values["brief_time"]).strftime("%H:%M")
        except ValueError:
            problems.append("The time the brief is written should look like 06:00.")

        if not problems:
            config["refresh_minutes"] = minutes
            config["brief_time"] = config_module.quoted(brief)
            save(config)
            flash("Saved.", "ok")
            return redirect(url_for("settings.refresh"))

    return render_template(
        "settings/refresh.html", config=config, values=values,
        problems=problems, choices=choices,
    )


@bp.route("/refresh-now", methods=["POST"])
def refresh_now():
    """Fetch the calendars and nothing else — the free half of "Rewrite now"."""
    config = current_config()
    try:
        payload = refresh_calendars(config, current_store())
    except Exception as exc:  # a broken feed or an unwritable file shouldn't 500 the UI
        log.exception("Calendar refresh failed")
        flash(f"Could not refresh the calendars: {exc}", "error")
        return redirect(url_for("settings.home"))

    count = len(payload.get("events") or [])
    days = int(config.get("calendar_days_ahead") or 14)
    broken = [s for s in payload.get("calendar_statuses") or [] if s.get("ok") is False]
    message = f"Calendars refreshed — {count} event{'' if count == 1 else 's'} over the next {days} days."
    if broken:
        # Named, because "which one" is the first thing anybody asks. The URL
        # stays out of it: it is a password.
        message += (f" {len(broken)} didn't answer: "
                    f"{', '.join(sorted(s['label'] for s in broken))}.")
    flash(message, "error" if broken else "ok")
    return redirect(url_for("settings.home"))


@bp.route("/system", methods=["GET", "POST"])
def system():
    config = current_config()
    if request.method == "POST":
        config["family_name"] = request.form.get("family_name", "").strip()
        config["location"] = request.form.get("location", "").strip()
        timezone = request.form.get("timezone", "").strip()
        if timezone:
            config["timezone"] = timezone
        model = request.form.get("claude_model", "").strip()
        if model:
            config["claude_model"] = model
        save(config)
        flash("Saved.", "ok")
        return redirect(url_for("settings.system"))

    try:
        from zoneinfo import available_timezones
        zones = sorted(available_timezones())
    except Exception:
        zones = [config.get("timezone", "UTC")]
    return render_template("settings/system.html", config=config, zones=zones)
