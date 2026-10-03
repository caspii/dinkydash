"""Prompt construction.

The dashboard shows one headline a day, so that is all we ask for.
"""

from .clock import DEFAULT_CLOCK, clock_of, format_time

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {
            "type": "string",
            "description": "A warm greeting tied to today, at most 10 words.",
        },
    },
    "required": ["headline"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
You write the daily headline for DinkyDash, a family dashboard that hangs on a \
kitchen wall. Young children read it, so keep the language simple and warm. It \
is a glanceable display, not an article: every word has to earn its place.

Write British English. Do not use emoji — the dashboard adds its own. Do not \
mention that you are an AI, and do not greet the reader by describing the \
weather, which you cannot see.

The headline names something real about today, drawn from the day's events, \
birthdays or countdowns. A pet or an interest may colour it when it belongs to \
the day. If the day is genuinely empty, say so plainly rather than inventing \
excitement. Reply with the headline only.\
"""


def _format_event(event, clock=DEFAULT_CLOCK):
    # On the family's clock, because the model quotes these times back into the
    # headline — a 12-hour family reading "swimming at 15:45" in the prose has
    # the same complaint one line down from the agenda.
    when = "All day" if event["all_day"] else format_time(
        event.get("start") or event.get("time"), clock)
    where = f" ({event['location']})" if event.get("location") else ""
    return f"- {when}: {event['title']}{where}"


def build_user_prompt(config, today, events_today, events_soon, chores,
                      countdowns):
    """Assemble everything the model needs into one prompt."""
    lines = [
        f"Today is {today.strftime('%A, %-d %B %Y')}.",
        f"The family is called {config.get('family_name') or 'the family'}.",
    ]
    if config.get("location"):
        lines.append(f"They live in {config['location']}.")

    people = config.get("people") or []
    if people:
        lines.append("")
        lines.append("Who is in the family:")
        from .context import compute_birthday_info
        for person in people:
            info = compute_birthday_info(person, today)
            bits = [f"{info['name']}, {info['current_age']}"]
            if person.get("interests"):
                bits.append(f"into {person['interests']}")
            lines.append(f"- {'; '.join(bits)}")

    pets = config.get("pets") or []
    if pets:
        named = []
        for pet in pets:
            name = pet.get("name") or ""
            kind = pet.get("type") or ""
            if name and kind:
                named.append(f"{name}, a {kind}")
            elif name or kind:
                named.append(name or kind)
        if named:
            lines.append("")
            lines.append("Pets: " + "; ".join(named) + ".")

    lines.append("")
    if events_today:
        lines.append("On today's calendar:")
        lines.extend(_format_event(e, clock_of(config)) for e in events_today)
    else:
        lines.append("Nothing at all on today's calendar.")

    if events_soon:
        lines.append("")
        lines.append("Coming up in the next few days:")
        lines.extend(
            f"- {e['date']}: {e['title']}" for e in events_soon[:6]
        )

    if chores:
        lines.append("")
        lines.append("Whose turn it is today:")
        lines.extend(f"- {c['title']}: {c['assigned_to']}" for c in chores)

    if countdowns:
        lines.append("")
        lines.append("Countdowns:")
        for c in countdowns[:5]:
            when = "today" if c["days"] == 0 else f"in {c['days']} days"
            lines.append(f"- {c['title']} {when}")

    lines.append("")
    lines.append("Write today's headline. Nothing else.")
    return "\n".join(lines)
