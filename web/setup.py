"""What a new family still has to do, worked out from the config.

The settings home has two personalities. While a family is being set up it
shows a checklist that leads somewhere; once the first board is written it
shows the day's controls. Which one, and which steps are done, is decided
here from the config and the stored board and nothing else — no stored
"onboarding step", no mode check — so a freshly cloned Pi running the
untouched example file gets the same checklist as a hosted family five
seconds old.

`config.is_set_up` is the engine's half of the same question: it is what
holds the first brief back until the answers are real, and the two must keep
agreeing. That is why every "done" below is read off the same helpers rather
than decided here.
"""

from flask import url_for

from dinkydash import config as config_module


def status(config, payload):
    """The checklist, and whether the page should be showing it.

    `in_progress` while the family is not set up *or* no brief has been
    written yet — the second half because a set-up family waiting for its
    first board still wants the screen link and the button, not a status line
    about a board that does not exist. `ready` is when the screen step may be
    shown: the household is real and the timezone chosen, so a board written
    now would be theirs.
    """
    set_up = config_module.is_set_up(config)
    written = bool((payload or {}).get("generated_for_date"))
    return {
        "in_progress": not (set_up and written),
        "ready": set_up,
        "written": written,
        "steps": [household(config), timezone(config), calendar(config)],
    }


def household(config):
    """Step one: the invented people and pets, until they are gone."""
    invented = config_module.invented_names(config)
    people = config_module.people_names(config)
    pets = [p["name"] for p in config.get("pets") or []
            if isinstance(p, dict) and p.get("name")]
    if invented:
        verb = "is" if len(invented) == 1 else "are"
        detail = (f"{names(invented)} {verb} invented, so the board has something "
                  f"to show. Rename or remove them.")
    elif people or pets:
        detail = names(people + pets)
    else:
        detail = "Nobody yet. Add the people whose birthdays and turns go on the board."
    return {
        "key": "household", "title": "Who lives here", "done": not invented,
        "detail": detail,
        "href": url_for("settings.section_list", section_name="people"),
    }


def timezone(config):
    """Step two: the one setting that changes what the board says."""
    done = config_module.timezone_is_set(config)
    return {
        "key": "timezone", "title": "Time zone", "done": done,
        "detail": config.get("timezone") if done else (
            "Still UTC. It decides when the day rolls over, when the morning's "
            "line is written, and what time an appointment shows."),
        "href": url_for("settings.system"),
    }


def calendar(config):
    """Step three: optional, and said to be — but it is the product."""
    on = [c.get("label") or "Calendar" for c in config.get("calendars") or []
          if isinstance(c, dict) and c.get("enabled")]
    return {
        "key": "calendar", "title": "A calendar", "done": bool(on),
        "detail": names(on) if on else (
            "None yet. The board works without one, but this is what puts "
            "today's plans on it."),
        "href": url_for("settings.section_list", section_name="calendars"),
    }


def names(items):
    """"Mia", "Mia and Theo", "Mia, Theo and Biscuit"."""
    items = [str(item) for item in items]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]
