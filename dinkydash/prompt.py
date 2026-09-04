"""Prompt construction.

The board shows one written line a day plus a headline, so that is all we ask
for. Which *kind* of line — a fact, a challenge, or something about the pet —
is chosen here in Python rather than left to the model, so the rotation is even
and the history can tell whether today repeats last Tuesday.
"""

import random

# Rotated each day to push the model off its default "safe" answers (the
# clowder-of-cats fact, the build-it-in-Minecraft challenge) and give the line a
# fresh anchor even before any history exists.
FUN_FACT_THEMES = [
    "animals", "outer space", "the ocean", "dinosaurs", "the human body",
    "weather and seasons", "insects and bugs", "plants and trees",
    "food and cooking", "faraway countries", "inventions and machines",
    "music and instruments", "sports and games", "rivers and mountains",
    "the moon and stars", "reptiles and amphibians", "birds",
    "colours and light", "vehicles and travel", "castles and history",
    "robots and technology", "volcanoes and earthquakes", "rainforests",
    "deserts", "snow and ice", "how everyday things work",
]

CHALLENGE_CATEGORIES = [
    "being creative or making art",
    "a small act of kindness",
    "moving and being active",
    "exploring outdoors or in nature",
    "learning something new or being curious",
    "using imagination and pretend play",
    "helping out around the house",
    "music, singing, or dancing",
    "building or inventing something (not on a screen)",
    "a silly or funny dare",
    "teamwork with the whole family",
    "storytelling or writing",
]

PET_ANGLES = [
    "what they are probably up to right now",
    "an opinion they seem to hold",
    "a spot in the house they have claimed",
    "something they are suspicious of",
    "a small triumph of theirs",
]

NOTE_KINDS = ("fact", "challenge", "pet")

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {
            "type": "string",
            "description": "A warm greeting tied to today, at most 10 words.",
        },
        "note": {
            "type": "string",
            "description": "The single line for the board's note box, at most 25 words.",
        },
    },
    "required": ["headline", "note"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
You write the daily text for DinkyDash, a family board that hangs on a kitchen \
wall. Young children read it, so keep the language simple and warm. It is a \
glanceable display, not an article: every word has to earn its place.

Write British English. Do not use emoji — the board adds its own. Do not \
mention that you are an AI, and do not greet the reader by describing the \
weather, which you cannot see.

The headline names something real about today, drawn from the day's events, \
birthdays or countdowns. If the day is genuinely empty, say so plainly rather \
than inventing excitement.

The note must be clearly different from every recent note listed in the \
prompt — a different topic, not a rewording. Reach past the obvious answer.\
"""


def choose_note_kind(config, rng=None):
    """Pick which kind of line today's note is. Pets only if there are pets."""
    rng = rng or random
    kinds = [k for k in NOTE_KINDS if k != "pet" or config.get("pets")]
    return rng.choice(kinds)


def note_instruction(kind, config, rng=None):
    """The one-line brief for today's note, with a rotating anchor."""
    rng = rng or random
    if kind == "challenge":
        return (
            f"Write a challenge for the family to do today, about "
            f"{rng.choice(CHALLENGE_CATEGORIES)}. One sentence, doable in a day, "
            f"no screens, no shopping."
        )
    if kind == "pet":
        pets = config.get("pets") or []
        names = ", ".join(p.get("name", "") for p in pets if p.get("name"))
        types = ", ".join(p.get("type", "pet") for p in pets)
        return (
            f"Write one affectionate, funny line about the family pet "
            f"({names or 'the pet'}, a {types or 'pet'}) — "
            f"{rng.choice(PET_ANGLES)}. Invent it; you cannot see the pet."
        )
    return (
        f"Write a surprising fact a child would repeat at school, about "
        f"{rng.choice(FUN_FACT_THEMES)}. One or two short sentences."
    )


def _format_event(event):
    when = "All day" if event["all_day"] else event["time"]
    where = f" ({event['location']})" if event.get("location") else ""
    return f"- {when}: {event['title']}{where}"


def build_user_prompt(config, today, events_today, events_soon, chores,
                      countdowns, recent_notes, note_kind, rng=None):
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

    lines.append("")
    if events_today:
        lines.append("On today's calendar:")
        lines.extend(_format_event(e) for e in events_today)
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

    if recent_notes:
        lines.append("")
        lines.append("Recent notes — today's must not resemble any of these:")
        lines.extend(f"- {n}" for n in recent_notes if n)

    lines.append("")
    lines.append(note_instruction(note_kind, config, rng=rng))
    return "\n".join(lines)
