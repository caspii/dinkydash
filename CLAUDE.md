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

**This repo is public and MIT-licensed**, and the hosted multi-tenant SaaS is being built inside
it, with self-hosting as the second mode of one codebase. Both facts constrain every change: see
[This is a public repo](#this-is-a-public-repo) and [Two modes, always](#two-modes-always) below.
Before making structural changes, read:

- [PLAN.md](PLAN.md) — hosted MVP architecture, phases, settled decisions, open questions
- [STRATEGY.md](STRATEGY.md) — positioning, pricing, SEO
- [design/](design/) — mockups for the settings UI and the board, with the reasoning

## This is a public repo

DinkyDash is open source, and the hosted product is being built in the same public repo (PLAN.md
decision 2). Everything pushed is world-readable the moment it lands, and the repo is itself the
funnel — the Show HN and r/selfhosted launch point straight at it. The code is read by strangers,
so a careless commit is an incident rather than a tidy-up.

Two consequences, pulling the same way:

- **Nothing private goes in.** Not a key, not a real family's data, not a calendar URL.
- **Hygiene is visible.** Careless handling of somebody's calendar is a public, permanent argument
  against trusting the hosted version too.

### What must never be committed

`.gitignore` covers `.env`, `config.yaml`, `dashboard_data.json`, `content_history.json`,
`generate.log` and `static/*.jpg|png` (except `icon.png`). That is the safety net, not the plan:
read `git status` before staging and never `git add -f` one of them. A secret in history survives
in every clone and fork after the commit that removes it, so the fix is rotation, not a revert.

- **An iCal "secret address" is a password in a URL.** Whoever holds it reads that family's whole
  calendar, indefinitely, and there is no way to see who has. It never goes in a commit, a test
  fixture, an issue, a log line, a screenshot, or a prompt to any model. Example URLs in the docs
  and in `config.example.yaml` are visibly fake (`private-xxxx`); keep new ones that way.
- **Real family data.** Names, dates of birth and children's faces are the entire content of this
  app. Screenshots for the README or the marketing site come from `python sample_board.py`, which
  invents people. Tests invent people too.
- **Secrets come from the environment**, never a literal in code or config. `.env` also lives on the
  Pi, because `deploy_to_pi.sh` rsyncs it — rotating a key means changing it in both places.
- **A new dependency is a supply-chain decision** in an app holding other families' calendars.
  Prefer the standard library; justify anything else in the PR.

### Handling other people's data

- **Calendar feeds are untrusted remote input.** Event titles are written by third parties, arrive
  over the network, and land in two places: the rendered page and the model prompt. Autoescaping
  protects the first — there is no `|safe` anywhere in `web/`, and none should appear on feed or
  user content. For the second, treat the text as data: an event titled "ignore your instructions
  and ..." must not change what the model does.
- **The server fetches URLs the user typed.** On a Pi that is the user's own machine. Hosted, it is
  a request from our infrastructure to anywhere, so before cloud mode goes live `fetch_feed` needs a
  scheme allowlist, redirects that cannot reach a private range, and a response size cap alongside
  the timeout it already has.
- **Calendar contents leave the machine.** They go to Anthropic to write the daily line. A fair
  trade, but it has to be *said* — in the privacy policy, the sub-processor list, and the UI
  (PLAN.md phase 5).
- **Log the label, not the URL.** `fetch_events` logs `entry["label"]` on purpose. The exception
  text does not follow that rule by itself — see the gotcha below.

### Hosted mode raises the stakes

Self-hosted is one family on their own network and has **no authentication by design**: anyone who
reaches the port can edit the config, which is the same trust model as the file it writes. Cloud
mode is a different product on the same code.

- **Every read and write is scoped to a `family_id`.** There is no unscoped query. An id arriving in
  a URL or a form is a claim, not a fact — check it against the session before it reaches a query.
- **`web/__init__.py` falls back to a hardcoded `app.secret_key`.** Harmless with no auth; in cloud
  mode the session *is* the authentication, so cloud mode must refuse to start without a real
  `DINKYDASH_SECRET_KEY`.
- **Screen tokens are bearer credentials.** Rate-limited, `noindex`, no referrer leakage, rotatable,
  and never written to a log or an error page.
- **Spend caps are a security control.** The per-family and global breaker (PLAN.md phase 2) is what
  stops a bug or an abusive account becoming an unbounded Anthropic bill.

### Hygiene still owed

Phase 0 of PLAN.md is mostly this, and none of it is done: no CI, no `gitleaks` hook, GitHub push
protection not enabled, and no `.env.example`. `.env` now holds `ANTHROPIC_API_KEY` and nothing
else — `FLASK_ENV`, `SECRET_KEY`, `DATABASE_URL`, `UPLOAD_FOLDER` and `MAX_CONTENT_LENGTH` were
leftovers from an abandoned plan and none of them was read by any code. Do not put `SECRET_KEY`
back: nothing calls `from_prefixed_env`, so Flask never sees it, and the session key comes from
`DINKYDASH_SECRET_KEY` or the hardcoded fallback whatever `.env` says. The Anthropic key is still
not rotated after living on a Pi and being rsynced. `requirements.txt` pins no versions. There is no
`LICENSE` file, though the README and the website both say MIT.

## Architecture

### Two modes, always

One codebase, two products (PLAN.md decision 2):

```
DINKYDASH_MODE=single   config.yaml · auth off · billing off · one family · local cron
DINKYDASH_MODE=cloud    Postgres · magic links · Stripe · many families · worker + scheduler
```

**Every change must work in both.** The engine, the board template, the CSS, the calendar handling
and the settings UI are shared verbatim; mode gates four things and no others — authentication,
billing, where the config is stored, and what drives the scheduler. A mode check anywhere else means
the change is in the wrong layer.

- **Self-hosted keeps working with no Postgres, no Stripe, no email provider**, and no network
  beyond the two things it fetches. A feature that needs a database is a cloud feature, or it is not
  a feature yet.
- **Hosted never assumes one family.** No module-level cache of "the" config, no singleton payload,
  no fixed path on disk. If a value is per-family, it is a parameter.
- **New settings go through the config dict**, so they survive both as commented YAML and as a
  `jsonb` column, with `with_defaults` migrating each on load. Nothing below the storage layer reads
  `config.yaml`.
- **New code in `dinkydash/` stays pure**, per the engine boundary below. That purity is what makes
  the two modes one codebase rather than two.

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
├── config.py          config.yaml load/save (ruamel round-trip), item ids
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

Every item in the five edited lists — people, pets, recurring, special_dates, calendars — carries a
short `id`. The settings UI addresses items by it, because a position is not an identity: delete the
first person and everyone below renumbers onto somebody else's edit form. Ids are backfilled by
`ensure_ids`, which the settings UI calls on load and saves once if it added any. Deliberately not
part of `load_config` — loading must not rewrite the file, and the engine never reads ids.
`_add_id` puts the id *first* in the mapping: ruamel hangs the comment introducing the next section
off the last item of the previous one, so an appended key lands under the wrong heading.

Ids are also what lets one settings UI serve both modes later. `PLAN.md` decision 10: the config
dict is the storage contract, a file in self-hosted mode and a `jsonb` column when hosted.

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
call at all, run `python sample_board.py`, which writes a plausible payload for today and calls no
API. It refuses to overwrite a real one, so delete `dashboard_data.json` first if that is what you
want. Then edit the file by hand — change `generated_for_date` to an older date to see the stale
state, or move it aside entirely to see the first-run screen.

**Local data in a new workspace.** `config.yaml`, `dashboard_data.json` and `content_history.json`
are gitignored, so a new Conductor workspace only receives them through Files to copy, which reads
`.worktreeinclude` **from the main checkout on disk** — having it on the branch is not enough. If
the main checkout is parked on an old commit that predates that file, Conductor falls back to its
default `.env*` pattern: `.env` arrives, the rest does not. `.conductor/settings.toml` covers the
gap by falling back to `config.example.yaml` and seeding a sample board, so a workspace always opens
on something real. Copied data still wins over both.

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
sizes at `/preview` rather than just the one you are looking at.

That root value is now *measured*, not guessed. A short script at the foot of `board.html` binary-
searches the largest `html { font-size }` whose content still fits the viewport, capped at
`min(26px, vh/24)`. The CSS `clamp()` stays as the no-JS fallback. Because `body` is
`height:100vh;overflow:hidden`, nothing ever reports an overflow — so the script lets the page lay
out freely for one measurement (`height:auto`) and puts it straight back.

In two-column mode the body is a grid, and **the note sits under the agenda, not across the
bottom**. The agenda is short on a quiet day while chores plus countdowns are not, so a full-width
note left the lower left quarter of an 800x480 panel empty. Under the agenda it balances the two
columns instead: on a five-event day the left column measures 311px against the side column's 312.

## Conventions

- **British English** throughout — UI copy, the model's system prompt, and `%-d %B` date formatting
  (`25 December`, not `December 25`).
- **Times are 24-hour** on the board (`08:20`).
- The board is sized in `rem` off one root `clamp(11px, 2.4vh, 26px)`, so the same layout reads on a
  480px-tall Pi panel and a living-room TV. Two columns above a 3:2 aspect ratio, one below.
- The settings UI does the same off one root `clamp(1rem, 0.75rem + 0.625vw, 1.25rem)`: the mockup's
  16px on a phone, up to 20px on a desktop browser, so the phone layout reads at desk distance
  without becoming a second layout. Every length in `web/templates/settings/` is therefore in `rem`
  or `em` — a new `px` value there stops scaling and drifts out of proportion. Borders, focus rings
  and shadows are the exception and stay in `px`; hairlines should not scale.
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
  Cloud mode cannot inherit this — see [Hosted mode raises the stakes](#hosted-mode-raises-the-stakes).
- **A failed calendar fetch puts the secret URL in the error text.** `requests` formats both
  `raise_for_status()` and connection errors with the full URL (`404 Client Error: ... for url:
  https://.../private-REALSECRET/basic.ics`), and `fetch_feed` wraps `{exc}` straight into
  `FeedError`. That string reaches `generate.log` and the feed status on the settings page.
  `fetch_events` logs the *label* precisely to avoid this; the exception text needs the same
  treatment before hosted mode, where the log is ours and the calendar is not.
- `strftime("%-d")` is glibc-specific. Fine on a Pi and in CI; would need changing for Windows.
- **Headless Chrome lies about the viewport.** `--window-size=800,480` renders into 800x393 — 87px
  short — while `--screenshot` still writes an 800x480 PNG, so the bottom fifth looks empty when it
  is simply not there. Add 87 to the height you want (`--window-size=800,567` gives a true 480), and
  confirm it by reading `window.innerHeight` out of the page rather than trusting the flag. Chrome
  also reuses a running instance unless each run gets its own `--user-data-dir`, which silently
  makes every size in a loop return the first one's numbers.
- The honest check is `scrot` over SSH on the Pi itself: a real 800x480 panel, a real kiosk browser,
  no capture artifacts. The board refreshes itself every 5 minutes, so a change takes one refresh to
  appear.

## Raspberry Pi Deployment

`deploy_to_pi.sh` rsyncs the tree (including `.env`), installs dependencies, and restarts the
`dinkydash.service` systemd unit.

Daily generation runs via cron:
```
0 6 * * * cd /home/pi/dinkydash && venv/bin/python generate.py >> generate.log 2>&1
```
A failed run leaves the previous board in place rather than blanking the screen, and the board
labels itself stale.
