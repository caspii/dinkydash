# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

DinkyDash is a family dashboard for a screen on the wall. A daily cron job calls the Claude API to
write a headline and one line of copy; the Flask app renders that alongside today's agenda, whose
turn each chore is, and the countdowns — all recomputed from `config.yaml` at render time.

Three components:

1. **The engine** (`dinkydash/`) — pure functions plus the model call. No config file is read here,
   no clock consulted, nothing written to disk.
2. **The web app** (`web/`) — the board at `/`, a settings UI at `/settings` that writes `config.yaml`.
3. **Static site generator** (`website/`) — the marketing site, built to `docs/` for GitHub Pages.

The project is being rebuilt as a hosted multi-tenant SaaS in this same public repo, with
self-hosting as a second mode of one codebase. Before making structural changes, read:

- [PLAN.md](PLAN.md) — hosted MVP architecture, phases, settled decisions, open questions
- [STRATEGY.md](STRATEGY.md) — positioning, pricing, SEO
- [design/](design/) — mockups for the settings UI and the board, with the reasoning

## Architecture

### The engine boundary

```python
generate(config, today, events, recent_notes) -> payload dict
```

`today` is injected, events are fetched by the caller, and the payload comes back as data. This is
what lets one code path serve a Pi cron job and, later, a multi-tenant scheduler — and it is what
makes the logic testable. Do not reintroduce `date.today()`, `SCRIPT_DIR`, file reads, or `sys.exit`
inside `dinkydash/`.

```
dinkydash/
├── context.py         ages, birthdays, countdowns, chore rotation (pure)
├── calendars.py       iCal fetch, parse, recurrence expansion, merge feeds
├── prompt.py          system + user prompt, note kinds, response schema
├── claude_client.py   the API call, with structured outputs
├── generate.py        orchestrator: config + date + events -> payload
├── board.py           payload + config -> what the template renders
├── config.py          config.yaml load/save (ruamel round-trip)
├── history.py         rolling record of recent notes, to avoid repeats
└── runner.py          the one place that does I/O around the engine

web/
├── __init__.py        create_app()
├── routes/board.py    the board and the preview harness
├── routes/settings.py the settings UI (one table drives every list section)
└── templates/         board.html, preview.html, settings/*.html
```

### What the payload holds, and what it does not

The payload stores only what cannot be recomputed: the model's `headline` and `note`, plus the
fetched calendar window (14 days, not just today). Chores, countdowns and ages are pure functions of
config + date, so `board.build_view` recomputes them on every render.

That split is deliberate and load-bearing: when a morning's generation fails, the times, turns and
countdowns on the wall are still **today's** — only the written line is old, and the board says so.
Yesterday's fetch reached 14 days ahead, so today's agenda is still in it. The stale headline is
replaced by a computed one (`"3 things on today, starting at 08:20."`) because a day-old AI headline
can be actively wrong.

### The daily cycle

```
[cron @ 6am] -> generate.py -> dinkydash.runner.run()
                                 fetch every enabled iCal feed, merge, sort
                                 build the prompt, call Claude
                                 write dashboard_data.json atomically
                                 append to content_history.json

[browser]    -> app.py       -> board.build_view(config, payload, today)
                                 renders web/templates/board.html
```

### Config

`config.yaml` is the single source of truth, and the settings UI writes it back. Loads and saves go
through ruamel round-trip mode with `indent(mapping=2, sequence=4, offset=2)`, so comments, key
order and indentation all survive an edit made from a phone. There is a test asserting a save
changes exactly the lines it means to.

`config.example.yaml` documents every key. Two are migrated on load: a single `calendar_url` becomes
the first entry in `calendars`, and `calendar_filter_emails` is dropped with a warning.

## Development Commands

**Setup** (Python 3.11+)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pytest; not deployed to the Pi
cp config.example.yaml config.yaml
```

**Run the tests** — do this before every commit
```bash
venv/bin/python -m pytest tests/ -q
```

**Generate a board** (needs `ANTHROPIC_API_KEY` in `.env`)
```bash
python generate.py                  # today
python generate.py --date 2026-12-24  # any date, for testing
```

**Run the app**
```bash
python app.py                       # or: flask run --host=0.0.0.0
```
Board at `/`, settings at `/settings`, all three screen sizes at once at `/preview`.

**Build the marketing site**
```bash
cd website && python build.py
```

## Working on it

**What the tests cover**, and why they exist: leap years, timezone conversion, event ordering,
rotation, staleness, and the config round-trip — the things that used to break silently. They run
in under a second, so there is no excuse for skipping them.

**Testing without spending money.** `generate.py --date 2026-12-24` generates for any date, which is
how to check a countdown or a quiet day. It still costs one API call. To exercise the board with no
call at all, edit `dashboard_data.json` by hand — change `generated_for_date` to an older date to
see the stale state, or move it aside entirely to see the first-run screen.

**Adding a field to a settings section.** Add a tuple to the section's `fields` list in
`web/routes/settings.py` — `(name, label, kind, required, help)`. The list template and the edit
form both render from it, and `parse_field` reads it back. `kind` is one of `text`, `url`, `date`,
`monthday`, `textarea`, `checkbox`, `emoji`, `color`, `people`. A new `kind` needs a branch in
`parse_field` and a branch in `web/templates/settings/edit.html`; nothing else.

**Adding a whole settings section.** Add an entry to `SECTIONS` and a row to
`web/templates/settings/home.html`. The list, edit, delete and reorder routes are generic and need
no changes.

**Changing the payload shape.** Ask first whether the value can be recomputed from config + date.
If it can, it belongs in `board.build_view`, not the payload — that is what keeps the stale state
honest. The payload is for things only the generator can know.

**Changing the board layout.** Everything is sized in `rem` off one root value, so check all three
sizes at `/preview` rather than just the one you are looking at. Headless screenshots of a
fixed-height board can drop the bottom of the frame; measure `scrollHeight` against the viewport
before believing a clipping bug.

## Conventions

- **British English** throughout — UI copy, the model's system prompt, and `%-d %B` date formatting
  (`25 December`, not `December 25`).
- **Times are 24-hour** on the board (`08:20`).
- The board is sized in `rem` off one root `clamp(11px, 2.4vh, 26px)`, so the same layout reads on a
  480px-tall Pi panel and a living-room TV. Two columns above a 3:2 aspect ratio, one below.
- Light and dark are the same rules with a different set of CSS custom properties. Never hard-code a
  colour in a board rule; add a token.
- Icons are inline SVG, never emoji. Emoji in *content* (avatars, chore markers) are the brand.

## Known issues and gotchas

- **`claude-haiku-4-5` takes no `thinking` parameter.** Omitting it means no thinking, which is what
  we want. If you move to Sonnet 5 or an Opus model, adaptive thinking is on by default and will
  compete with `max_tokens` — set it explicitly or raise the budget.
- **Structured outputs** (`output_config.format`) guarantee the response matches the schema, so
  there is no JSON-repair retry loop. Do not add one back.
- Self-hosted mode has **no authentication**. Anyone who can reach the port can edit the config.
  That is the same trust model as the file it writes, but keep the port off the public internet.
- `strftime("%-d")` is glibc-specific. Fine on a Pi and in CI; would need changing for Windows.
- Headless-Chrome screenshots of the board can drop the bottom ~20% of the frame. It is a capture
  artifact, not a layout bug — measure `scrollHeight` against the viewport before chasing it.

## Raspberry Pi Deployment

`deploy_to_pi.sh` rsyncs the tree (including `.env`), installs dependencies, and restarts the
`dinkydash.service` systemd unit.

Daily generation runs via cron:
```
0 6 * * * cd /home/pi/dinkydash && venv/bin/python generate.py >> generate.log 2>&1
```
A failed run leaves the previous board in place rather than blanking the screen, and the board
labels itself stale.
