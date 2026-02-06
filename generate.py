#!/usr/bin/env python3
"""
DinkyDash Daily Content Generator

Runs once per day via cron. Fetches calendar events, builds a prompt,
calls the Claude API, and saves structured JSON for the Flask app.
"""

import json
import logging
import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv
from icalendar import Calendar
from recurring_ical_events import of as recurring_events_of

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent


def load_config():
    config_path = SCRIPT_DIR / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Calendar fetching
# ---------------------------------------------------------------------------

def _get_attendee_emails(event):
    """Extract all attendee email addresses from an iCal event."""
    attendees = event.get("ATTENDEE")
    if not attendees:
        return set()
    if not isinstance(attendees, list):
        attendees = [attendees]
    emails = set()
    for a in attendees:
        email = str(a).replace("mailto:", "").lower()
        emails.add(email)
    return emails


def fetch_calendar_events(url, days_ahead=14, filter_emails=None):
    """Fetch and parse a public Google Calendar iCal URL.
    Returns a list of event dicts for the next `days_ahead` days.
    If filter_emails is set, only include events where all those
    emails appear as attendees.
    """
    if not url:
        log.warning("No calendar URL configured, skipping calendar fetch")
        return []

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.warning("Failed to fetch calendar: %s", e)
        return []

    try:
        cal = Calendar.from_ical(resp.text)
    except Exception as e:
        log.warning("Failed to parse iCal data: %s", e)
        return []

    required_emails = {e.lower() for e in filter_emails} if filter_emails else set()

    today = date.today()
    end = today + timedelta(days=days_ahead)

    events = []
    skipped = 0
    for event in recurring_events_of(cal).between(today, end):
        # Filter by attendees if configured
        if required_emails:
            attendee_emails = _get_attendee_emails(event)
            if not required_emails.issubset(attendee_emails):
                skipped += 1
                continue

        summary = str(event.get("SUMMARY", "Untitled"))
        dtstart = event.get("DTSTART")
        if dtstart:
            dtstart = dtstart.dt
            if isinstance(dtstart, datetime):
                date_str = dtstart.strftime("%A, %B %d at %I:%M %p")
            else:
                date_str = dtstart.strftime("%A, %B %d")
        else:
            date_str = "Unknown date"

        location = str(event.get("LOCATION", "")) or None
        description = str(event.get("DESCRIPTION", "")) or None

        events.append({
            "summary": summary,
            "date": date_str,
            "location": location,
            "description": description,
        })

    events.sort(key=lambda e: e["date"])
    log.info("Fetched %d calendar events for next %d days (%d filtered out)",
             len(events), days_ahead, skipped)
    return events


# ---------------------------------------------------------------------------
# Context computation
# ---------------------------------------------------------------------------

def compute_age(dob, today=None):
    """Return current age given a date-of-birth."""
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def compute_birthday_info(person, today=None):
    """Return dict with birthday countdown info for a person."""
    today = today or date.today()
    dob = datetime.strptime(person["date_of_birth"], "%Y-%m-%d").date()
    current_age = compute_age(dob, today)

    birthday_this_year = dob.replace(year=today.year)
    if birthday_this_year < today:
        next_birthday = dob.replace(year=today.year + 1)
        turning = current_age + 1
    elif birthday_this_year == today:
        next_birthday = birthday_this_year
        turning = current_age
    else:
        next_birthday = birthday_this_year
        turning = current_age + 1

    days_until = (next_birthday - today).days
    return {
        "name": person["name"],
        "current_age": current_age,
        "turning": turning,
        "days_until_birthday": days_until,
        "birthday_date": next_birthday.strftime("%B %d"),
        "image": person.get("image", ""),
    }


def compute_special_date_info(sd, today=None):
    """Return dict with countdown info for a special date."""
    today = today or date.today()
    month, day = sd["date"].split("/")
    target = date(today.year, int(month), int(day))
    if target < today:
        target = target.replace(year=today.year + 1)
    days_until = (target - today).days
    return {
        "title": sd["title"],
        "emoji": sd.get("emoji", ""),
        "days_until": days_until,
        "date_display": target.strftime("%B %d"),
    }


def compute_chore_assignments(recurring, people, today=None):
    """Compute today's chore rotation using day-of-year modulo."""
    today = today or date.today()
    day_of_year = today.timetuple().tm_yday
    people_by_name = {p["name"]: p for p in people}

    assignments = []
    for chore in recurring:
        choices = chore["choices"]
        idx = day_of_year % len(choices)
        assigned_name = choices[idx]
        person = people_by_name.get(assigned_name, {})
        assignments.append({
            "emoji": chore.get("emoji", ""),
            "title": chore["title"],
            "assigned_to": assigned_name,
            "image": person.get("image", ""),
        })
    return assignments


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are DinkyDash, a friendly family dashboard AI. You create fun, warm, \
age-appropriate daily content for a family. The family has young children \
so all content should be suitable for kids, using simple language they can \
understand.

You MUST respond with valid JSON only. No markdown, no code fences, no \
explanation. Use this exact structure:

{
  "headline": "A fun, short daily greeting (max 10 words)",
  "fun_fact": "An interesting, kid-friendly fact of the day (2-3 sentences)",
  "daily_challenge": "A fun family challenge or question for today",
  "people": [
    {
      "name": "PersonName",
      "message": "A personalized, encouraging message (1-2 sentences)",
      "fun_tidbit": "A fun fact or joke related to their interests"
    }
  ],
  "events": [
    {
      "title": "Event name",
      "date": "Human-readable date",
      "commentary": "A witty or fun remark about this event (1 sentence)"
    }
  ],
  "chore_commentary": "A brief, encouraging comment about today's chore assignments",
  "pet_corner": "A fun dog fact or silly comment about the family dog"
}

The "people" array must contain one entry per family member, in the same \
order as provided. The "events" array should cover the calendar events \
provided. If no calendar events are given, use an empty array for "events".\
"""


def build_user_prompt(config, calendar_events, chore_assignments,
                      birthday_infos, special_date_infos):
    today = date.today()
    now = datetime.now()

    lines = [
        f"Today is {now.strftime('%A, %B %d, %Y')}. "
        f"Day {today.timetuple().tm_yday} of the year.",
        "",
        "FAMILY MEMBERS:",
    ]

    for person in config["people"]:
        bday = next(b for b in birthday_infos if b["name"] == person["name"])
        interests = person.get("interests", "")
        interest_line = f"  Interests: {interests}" if interests else ""
        lines.append(
            f"- {person['name']} ({person['sex']}, age {bday['current_age']}, "
            f"turning {bday['turning']} in {bday['days_until_birthday']} days)"
        )
        if interest_line:
            lines.append(interest_line)

    if config.get("pets"):
        lines.append("")
        lines.append("PETS:")
        for pet in config["pets"]:
            lines.append(f"- {pet['name']} the {pet['type']}")

    lines.append("")
    lines.append("TODAY'S CHORE ASSIGNMENTS:")
    for chore in chore_assignments:
        lines.append(
            f"- {chore['emoji']} {chore['title']}: {chore['assigned_to']}'s turn"
        )

    lines.append("")
    lines.append("UPCOMING BIRTHDAYS:")
    for bday in sorted(birthday_infos, key=lambda b: b["days_until_birthday"]):
        if bday["days_until_birthday"] == 0:
            lines.append(
                f"- {bday['name']} turns {bday['turning']} TODAY!"
            )
        else:
            lines.append(
                f"- {bday['name']} turns {bday['turning']} in "
                f"{bday['days_until_birthday']} days ({bday['birthday_date']})"
            )

    if calendar_events:
        lines.append("")
        lines.append("UPCOMING CALENDAR EVENTS (next 14 days):")
        for ev in calendar_events:
            loc = f" at {ev['location']}" if ev.get("location") else ""
            lines.append(f"- {ev['summary']} on {ev['date']}{loc}")

    if special_date_infos:
        lines.append("")
        lines.append("SPECIAL DATE COUNTDOWNS:")
        for sd in sorted(special_date_infos, key=lambda s: s["days_until"]):
            lines.append(
                f"- {sd['emoji']} {sd['title']}: {sd['days_until']} days away "
                f"({sd['date_display']})"
            )

    lines.append("")
    lines.append(
        "Please generate today's dashboard content. Be warm, funny, and "
        "encouraging. Make personalized messages age-appropriate. Keep the "
        "headline punchy. If any birthday is within 7 days, make it "
        "prominently celebrated."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude API call
# ---------------------------------------------------------------------------

def call_claude(system_prompt, user_prompt, config):
    """Call the Claude API and return the response text."""
    from anthropic import Anthropic

    client = Anthropic()
    model = config.get("claude_model", "claude-sonnet-4-5-20250929")
    max_tokens = config.get("max_tokens", 2048)

    log.info("Calling Claude API (model=%s, max_tokens=%d)", model, max_tokens)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def parse_ai_response(text):
    """Parse Claude's JSON response, stripping markdown fences if present."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate():
    config = load_config()
    today = date.today()
    now = datetime.now()

    # Compute all context
    birthday_infos = [compute_birthday_info(p) for p in config["people"]]
    special_date_infos = [
        compute_special_date_info(sd)
        for sd in config.get("special_dates", [])
    ]
    chore_assignments = compute_chore_assignments(
        config.get("recurring", []), config["people"]
    )
    calendar_events = fetch_calendar_events(
        config.get("calendar_url", ""),
        days_ahead=14,
        filter_emails=config.get("calendar_filter_emails"),
    )

    # Build prompt
    user_prompt = build_user_prompt(
        config, calendar_events, chore_assignments,
        birthday_infos, special_date_infos,
    )
    log.info("Prompt built (%d characters)", len(user_prompt))

    # Call Claude API with retries
    ai_content = None
    last_error = None
    for attempt in range(3):
        try:
            raw_response = call_claude(SYSTEM_PROMPT, user_prompt, config)
            ai_content = parse_ai_response(raw_response)
            break
        except json.JSONDecodeError as e:
            log.warning("Attempt %d: JSON parse error: %s", attempt + 1, e)
            last_error = e
        except Exception as e:
            log.warning("Attempt %d: API error: %s", attempt + 1, e)
            last_error = e

    if ai_content is None:
        log.error("All attempts failed. Last error: %s", last_error)
        log.error("Preserving previous dashboard data.")
        sys.exit(1)

    # Build the full dashboard envelope
    # Sort countdowns: birthdays + special dates together, by days remaining
    all_countdowns = []
    for bday in birthday_infos:
        all_countdowns.append({
            "emoji": "🎂",
            "title": f"{bday['name']}'s Birthday",
            "days": bday["days_until_birthday"],
            "image": bday["image"],
        })
    for sd in special_date_infos:
        all_countdowns.append({
            "emoji": sd["emoji"],
            "title": sd["title"],
            "days": sd["days_until"],
            "image": None,
        })
    all_countdowns.sort(key=lambda c: c["days"])

    # Map person name → image for template lookup
    people_images = {p["name"]: p.get("image", "") for p in config["people"]}

    dashboard_data = {
        "generated_at": now.isoformat(),
        "generated_date": today.isoformat(),
        "today_display": now.strftime("%A, %B %d"),
        "people_images": people_images,
        "chores": chore_assignments,
        "countdowns": all_countdowns,
        "calendar_events": calendar_events,
        "ai_content": ai_content,
    }

    # Write atomically
    data_file = SCRIPT_DIR / config.get("data_file", "dashboard_data.json")
    fd, tmp_path = tempfile.mkstemp(
        dir=str(data_file.parent), suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
        os.rename(tmp_path, str(data_file))
    except Exception:
        os.unlink(tmp_path)
        raise

    log.info("Dashboard data written to %s", data_file)


if __name__ == "__main__":
    generate()
