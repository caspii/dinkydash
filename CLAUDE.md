# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

DinkyDash is a family dashboard on a Raspberry Pi. A daily cron job calls the Claude API to generate personalized content based on a Google Calendar and family info. The Flask app renders the pre-generated JSON.

The project has two main components:
1. **Dashboard App** (root directory) - `generate.py` (daily content generation) + `app.py` (Flask server)
2. **Static Site Generator** (website/ directory) - Generates marketing/documentation site to GitHub Pages

**This file describes the code as it currently is: single-family, file-based, Pi-targeted.** The project is being rebuilt as a hosted multi-tenant SaaS in the same public monorepo, with self-hosting as a second mode of one codebase. Before making structural changes, read:

- [PLAN.md](PLAN.md) — hosted MVP architecture, phases, settled decisions, open questions
- [STRATEGY.md](STRATEGY.md) — positioning, pricing, SEO

## Known issues

Latent on a single Pi, actively harmful once multi-tenant. Don't be surprised by them, and don't work around them — they're scheduled to be fixed in Phase 0:

- `generate.py:119` sorts calendar events by **formatted string** (`"Friday, August 15 at 03:30 PM"`), so ordering is alphabetical by weekday name, not chronological.
- `date.today()` / `datetime.now()` use **server local time** throughout. There is no per-family timezone.
- `calendar_filter_emails` requires every listed email to appear as an `ATTENDEE`. Most personal Google Calendar events have no `ATTENDEE` property, so this silently returns zero events.
- There are no tests.
- `.env` carries unused `DATABASE_URL`, `SECRET_KEY`, `UPLOAD_FOLDER`, `MAX_CONTENT_LENGTH` keys left over from an abandoned plan.
- `config.yaml` pins `claude-sonnet-4-5-20250929`. Note that newer models run adaptive thinking by default, which competes with `max_tokens: 2048` and can truncate the JSON response.

## Development Commands

### Dashboard App

**Setup** (requires Python 3.11+)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Generate dashboard content** (requires `ANTHROPIC_API_KEY` in `.env`):
```bash
python generate.py
```

**Run dev server**
```bash
flask run --host=0.0.0.0
```

**Deploy to Raspberry Pi**
```bash
./deploy_to_pi.sh
```

### Static Site Generator (Marketing Site)

**Build static site**
```bash
cd website
python build.py
```

## Architecture

### Two-Script Model

```
[cron @ 6am] -> generate.py -> fetches Google Calendar
                             -> builds prompt with family context
                             -> calls Claude API
                             -> saves dashboard_data.json

[browser]    -> app.py       -> reads dashboard_data.json
                             -> renders templates/index.html
```

### `generate.py` - Daily Content Generator

Four stages:
1. **Load config** - reads `config.yaml`, computes ages, birthday countdowns, chore rotations, special date countdowns
2. **Fetch calendar** - GET iCal URL, parse with `icalendar` + `recurring-ical-events`, filter by attendee emails
3. **Build prompt** - system prompt constrains output to kid-friendly JSON; user prompt provides all context
4. **Call Claude API** - validate JSON response, save atomically to `dashboard_data.json`

Key functions:
- `fetch_calendar_events(url, days_ahead, filter_emails)` - fetches and filters iCal events
- `compute_birthday_info(person)` - calculates age, next birthday, days remaining
- `compute_chore_assignments(recurring, people)` - daily rotation via `tm_yday % len(choices)`
- `build_user_prompt(...)` - assembles all context into the Claude prompt
- `call_claude(system_prompt, user_prompt, config)` - calls the Anthropic API

### `app.py` - Flask Server

Minimal: reads `dashboard_data.json`, passes to template. Graceful fallback if no JSON exists.

Routes:
- `/` - Main dashboard
- `/preview` - 800x480 iframe preview matching Pi display size (useful for development)

Environment variable `DINKYDASH_DATA_FILE` overrides the default data file path.

### `config.yaml` - Configuration

- `calendar_url` - Google Calendar iCal URL
- `calendar_filter_emails` - only include events where these emails are attendees
- `people[]` - name, date_of_birth (YYYY-MM-DD), sex, image, email, interests
- `pets[]` - name, type, image
- `recurring[]` - emoji, title, choices (person names, rotated daily)
- `special_dates[]` - emoji, title, date (MM/DD)
- `claude_model`, `max_tokens` - API settings

### `templates/index.html` - Dashboard Template

Bootstrap 5 (Quartz Bootswatch) + Inter font. Sections: header with headline, person cards, chore badges, countdown items, fun fact / daily challenge / pet corner, calendar events. Optimized for 800x480 Pi display. Auto-refreshes every 300s.

### Static Site Generator (`website/build.py`)

Reads Markdown from `website/content/`, extracts YAML front matter, converts to HTML, renders via Jinja2 templates, outputs to `docs/` for GitHub Pages.

Each page gets a `canonical_url` (derived from its output path and `SITE_URL`) used for both `<link rel="canonical">` and `og:url` in `templates/base.html`. The build also writes `docs/sitemap.xml` and `docs/robots.txt`; sitemap `lastmod` comes from the last git commit touching the page's Markdown or its template, so **a page's `lastmod` only updates once its change is committed**.

## Raspberry Pi Deployment

`deploy_to_pi.sh` rsyncs files (including `.env` with API key), restarts the `dinkydash.service` systemd service, and installs pip dependencies.

Daily generation runs via cron at 6am:
```
0 6 * * * cd /home/pi/dinkydash && source venv/bin/activate && python generate.py >> generate.log 2>&1
```
