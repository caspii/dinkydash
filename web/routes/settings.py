"""The settings UI.

Every list section — people, pets, chores, dates, calendars — is the same
shape: a list, an edit form, a delete. So they share one pair of routes driven
by the SECTIONS table below rather than five near-identical copies.

Writes go straight back to config.yaml through ruamel's round-trip mode, so the
comments in the file survive being edited from a phone.
"""

import logging
from datetime import datetime

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, url_for)

from dinkydash import config as config_module
from dinkydash.calendars import FeedError, describe_feed
from dinkydash.claude_client import GenerationError
from dinkydash.context import compute_birthday_info, upcoming_for
from dinkydash.runner import run as run_generation

log = logging.getLogger(__name__)

bp = Blueprint("settings", __name__)


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
        "blurb": "Every calendar you switch on is merged into one agenda. Titles and times are sent to Claude each morning.",
        "fields": [
            ("label", "Call it", "text", True, ""),
            ("url", "iCal link", "url", True,
             "Google Calendar → Settings and sharing → Secret address in iCal format."),
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


def current_config():
    return config_module.load_config(current_app.config["CONFIG_PATH"])


def save(config):
    config_module.save_config(config, current_app.config["CONFIG_PATH"])


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
    return problems


@bp.route("/")
def home():
    from web import load_payload
    config = current_config()
    today = config_module.today_for(config)
    payload = load_payload(config)

    status = {"state": "waiting", "detail": "No board has been generated yet."}
    if payload:
        generated_for = payload.get("generated_for_date")
        if generated_for == today.isoformat():
            status = {"state": "ready", "detail": f"Today's board is up — written {_clock(payload)}."}
        else:
            status = {"state": "stale", "detail": f"Showing the board from {generated_for}."}

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
        broken=broken, sections=SECTIONS,
    )


def _clock(payload):
    stamp = payload.get("generated_at", "")
    return stamp[11:16] if len(stamp) >= 16 else "earlier"


@bp.route("/generate", methods=["POST"])
def generate_now():
    config = current_config()
    try:
        payload = run_generation(config, base=current_app.config["CONFIG_PATH"].parent)
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
        try:
            index = int(item_id)
            item = items[index]
        except (ValueError, IndexError):
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
                    items.append(submitted)
                else:
                    items[index] = submitted
                save(config)
                flash(f"Saved {submitted.get('name') or submitted.get('title') or submitted.get('label') or 'it'}.", "ok")
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
    """Fetch a pasted iCal URL and describe what came back."""
    url = (item.get("url") or "").strip()
    if not url:
        return {"ok": False, "message": "Paste a link first."}
    try:
        found = describe_feed(
            url, config_module.tzinfo_for(config),
            today=config_module.today_for(config),
            days_ahead=int(config.get("calendar_days_ahead") or 14),
        )
    except FeedError as exc:
        return {"ok": False, "message": str(exc)}
    if not found["count"]:
        return {"ok": True, "message":
                f"That link works, but there is nothing on it in the next "
                f"{found['days_ahead']} days."}
    nxt = found["next"]
    when = "all day" if nxt["all_day"] else nxt["time"]
    return {"ok": True, "message":
            f"{found['count']} events over the next {found['days_ahead']} days. "
            f"Next up: {nxt['title']}, {nxt['date']} at {when}."}


@bp.route("/<section_name>/<int:index>/delete", methods=["POST"])
def section_delete(section_name, index):
    section = section_or_404(section_name)
    config = current_config()
    items = config.get(section["key"]) or []
    if not 0 <= index < len(items):
        abort(404)
    removed = items.pop(index)
    save(config)
    flash(f"Removed {removed.get('name') or removed.get('title') or removed.get('label') or 'it'}.", "ok")
    return redirect(url_for("settings.section_list", section_name=section_name))


@bp.route("/<section_name>/<int:index>/move", methods=["POST"])
def section_move(section_name, index):
    """Reorder within a list — chore rotation order is the reason this exists."""
    section = section_or_404(section_name)
    config = current_config()
    items = config.get(section["key"]) or []
    target = index + (-1 if request.form.get("direction") == "up" else 1)
    if 0 <= index < len(items) and 0 <= target < len(items):
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
