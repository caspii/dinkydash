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
- the strategy document — positioning, pricing, SEO. Not in the repo by policy: it is a Linear
  document on the Dinky Dash team. See [Strategy and marketing live in
  Linear](#strategy-and-marketing-live-in-linear).
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

`.gitignore` covers `.env`, `config.yaml`, `dashboard_data.json`, `content_history.json` and
`generate.log`. That is the safety net, not the plan: read `git status` before staging and never
`git add -f` one of them. A secret in history survives
in every clone and fork after the commit that removes it, so the fix is rotation, not a revert.

- **An iCal "secret address" is a password in a URL.** Whoever holds it reads that family's whole
  calendar, indefinitely, and there is no way to see who has. It never goes in a commit, a test
  fixture, an issue, a log line, a screenshot, or a prompt to any model. Example URLs in the docs
  and in `config.example.yaml` are visibly fake (`private-xxxx`); keep new ones that way, because
  `.gitleaks.toml` has a rule for the real shape and CI fails on it.
- **Real family data.** Names, dates of birth and children's faces are the entire content of this
  app. Screenshots for the README or the marketing site come from `python sample_board.py`, which
  invents people. Tests invent people too.
- **Secrets come from the environment**, never a literal in code or config. `.env` also lives on the
  Pi, and `deploy_to_pi.sh` deliberately excludes it — rotating a key means editing it on the Pi in
  place, and in the main checkout, rather than pushing one over the other.
- **A new dependency is a supply-chain decision** in an app holding other families' calendars.
  Prefer the standard library; justify anything else in the PR.

### Strategy and marketing live in Linear

**Commercial intent is not repo content.** Positioning, pricing reasoning, SEO and keyword research,
competitor analysis, funnel thinking and launch plans live as Linear documents on the **Dinky Dash
(`DIN`)** team. This holds for features and documentation too: *what* something does and *how* it is
built is written here; *why it earns money* is written there. A feature note that argues for a
conversion rate is in the wrong place, whatever file it is in.

The line to hold:

- **Here** — architecture, the two modes, code, tests, what a self-hoster needs to run it, and the
  marketing site's own source in `website/`. Shipped public artefacts, and the engineering behind
  them.
- **In Linear** — prices and the argument for them, keyword volumes and competitor tables, revenue
  targets, cost-per-family models, and anything framing this repo as top of a funnel.

The shop window is the exception, and only the window. The README may state the hosted price and
link the waitlist, and `website/` is a marketing site by definition. What must not appear is the
*reasoning* behind either — the number is public, the case for the number is not.

New strategy docs are written to a temporary file and pushed straight to Linear, never through the
working tree where a stray `git add` can catch them:

```bash
linear document create --team DIN --title "..." --content-file /tmp/note.md
```

Relative links like `[PLAN.md](PLAN.md)` break once a document is in Linear. Rewrite them to full
`https://github.com/caspii/dinkydash/blob/main/...` URLs before uploading.

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

### The safety net, and what it does not cover

Phase 0 of PLAN.md is mostly this. Three of the four pieces are now in place.

`.github/workflows/test.yml` runs on every push and pull request, as two independent jobs so a
secret and a broken test are separate red X's: **pytest** on Python 3.11, and **gitleaks** over the
full history — `fetch-depth: 0`, because gitleaks scans commits rather than the working tree.
GitHub's own secret scanning and push protection are switched on for the repo as a second layer.
**Do not rely on that layer yet.** Minutes after enabling it, a correctly shaped fake
`sk-ant-api03-` key and a correctly shaped fake AWS key pair were both pushed to a scratch branch
without being blocked, and neither raised an alert — so the settings report enabled while nothing
observably enforces. GitHub rescans a repo from scratch when the feature is turned on, so this may
simply be the backfill; it is worth re-testing on a scratch branch before treating a rejected push
as the safety net. **gitleaks is the layer that was actually observed to work**: it failed the build
on that same fake key, and `--redact` kept the value out of the CI log.

The gitleaks job runs the MIT-licensed binary directly, pinned, rather than the upstream
`gitleaks-action` — that action is a bundled JavaScript blob under a commercial licence, and this is
one fewer thing holding a token in our CI. Rules live in `.gitleaks.toml`, which extends the default
set with the one shape the defaults do not know: **an iCal secret address**. Google
(`private-` + 32 hex) and iCloud (`/published/2/` + a long token) both have a rule; the visibly fake
examples in the docs (`private-xxxx`, `private-8f3c1a`) are too short to match, so keep new ones
that way. The single allowlist entry is the Ahrefs Web Analytics site key, which is served in the
`<head>` of every page on dinkydash.co and so trips `generic-api-key` 4,000+ times across `docs/`.
**Allowlisting is for values that are public by design.** A real secret that reached a commit is
fixed by rotating it.

Two things the net does not catch, both worth knowing before trusting it:

- **The defaults have no rule for a calendar URL**, which is why we wrote our own. Anything else
  shaped like a password in a URL needs the same treatment.
- **`config.yaml` is in the history**, nine commits from before it was gitignored. It holds two
  children's first names; it holds no credential, no calendar URL and no key, so there is nothing to
  rotate — but it is public and permanent, and rewriting a published history is not a fix worth the
  breakage. It is the reason the rules above exist.

**`.env` should hold `ANTHROPIC_API_KEY` and nothing else.** `FLASK_ENV`, `SECRET_KEY`,
`DATABASE_URL`, `UPLOAD_FOLDER` and `MAX_CONTENT_LENGTH` are leftovers from an abandoned plan and
none of them is read by any code — a grep over the repo returns only `web/__init__.py`, and that
reads `DINKYDASH_SECRET_KEY`, a different name. **They are all still there**, as of 7 September 2026:
in the main checkout, on the Pi, and in every new worktree. `.env` is not in git, so stripping it in
a worktree dies with that worktree, and the next workspace is seeded from the main checkout again —
which is why an earlier note here claiming they had been stripped did not stay true. Every copy has
to be edited where it lives, including the Pi's, whose `.env` `deploy_to_pi.sh` does not overwrite.
Do not put `SECRET_KEY` back: nothing calls `from_prefixed_env`, so Flask never sees it, and the
session key comes from `DINKYDASH_SECRET_KEY` or the hardcoded fallback whatever `.env` says.

**The Anthropic key was rotated on 7 September 2026** (DIN-20), after living on a Pi and having
been rsynced. The old key now reads 401 from the API; the new one is in `.env` in the main checkout
and on the Pi, written in place. CI could not have done it, and a future rotation is the same manual
job: revoke in the Anthropic console, then edit each copy where it lives. `deploy_to_pi.sh` excludes
`.env`, so pushing one copy over the other is not an option and is not meant to be.

**`requirements.txt` and `requirements-dev.txt` are pinned with `==`** to the versions CI passes on,
so a clean venv gets what was tested. Bump deliberately, and check the release notes: `anthropic`
must stay at 1.x or later, because `claude_client.py` calls `output_config` structured outputs.

**`requirements.txt` is runtime only** — it is what `deploy_to_pi.sh` installs on the Pi. The site
generator's dependencies (`jinja2`, `markdown`, `pyyaml`) and the favicon script's (`Pillow`) live
in `requirements-dev.txt`, because `website/` never runs on the board. A new import in `website/`
goes there, not in `requirements.txt`.

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
├── history.py         what the recent notes say, and how they trim (pure)
├── schedule.py        due(config, payload, now) -> what a tick owes (pure)
├── store.py           the six storage operations; FileStore is the only one yet
└── runner.py          the two halves of the day, reading and writing through a store

web/
├── __init__.py        create_app()
├── routes/board.py    the board and the preview harness
├── routes/settings.py the settings UI (one table drives every list section)
└── templates/         board.html, preview.html, settings/*.html
```

### The storage seam

Six operations, on one object, and nothing above them knows what is behind it:

```python
load_config()                save_config(config)
load_payload(config)         save_payload(config, payload)
recent_notes(config, days)   record_note(config, entry, keep)
```

`FileStore(config_path)` is the only implementation today — `config.yaml` and two JSON files in one
directory. `PostgresStore` is the cloud one, where the payload is composed from two rows and comes
back as the same dict (PLAN.md decision 10). The runner, the board route and the settings routes all
take a store; `create_app(store=None)` builds one and every route reads `app.config["STORE"]`.

Three rules keep it a seam rather than a name:

- **`store.py` and `config.py` are the only files under `dinkydash/` that open a file.** `grep -rn
  "open(" dinkydash web` is the check, and it should stay that short. A new file read anywhere else
  is a caller that cloud mode will have to fork.
- **`data_file` and `content_history_file` are storage-layer keys.** They stay in `DEFAULTS` and in
  `config.example.yaml` for compatibility, and only `FileStore` reads them. They mean nothing hosted.
- **The store is passed, never constructed, below the entry points.** `generate.py`, `app.py` and
  `sample_board.py` build one; everything else is handed it. That is what makes a second
  implementation a constructor argument rather than an edit.

### What the payload holds, and what it does not

The payload stores only what cannot be recomputed: the model's `headline` and `note`, plus the
fetched calendar window (14 days, not just today). Chores, countdowns and ages are pure functions of
config + date, so `board.build_view` recomputes them on every render.

That split is deliberate and load-bearing: when a morning's generation fails, the times, turns and
countdowns on the wall are still **today's** — only the written line is old, and the board says so.
Yesterday's fetch reached 14 days ahead, so today's agenda is still in it. The stale headline is
replaced by a computed one (`"3 things on today, starting at 08:20."`) because a day-old AI headline
can be actively wrong.

That same 14-day window is where **tomorrow's** agenda comes from, so it survives a failed run too.

The payload carries two stamps, **both in UTC**: `generated_at` (when the brief was written) and
`calendars_fetched_at` (when the feeds were last fetched, and what `schedule.due` reads). UTC
because the server is routinely not on the family's clock — a Pi is often left on UTC, and hosted
the server is nowhere near them. They are rendered in the family's timezone at the point of display,
which on the settings home is `_clock(stamp, tzinfo)`. It used to slice the characters out of the
ISO string, which showed the server's hour (PLAN.md bug 9).

### Two cadences, one tick

The fetch and the model call ran together only because history put them there, and it meant an
appointment added at 09:00 was not on the wall until the next morning. They now run on their own
clocks, chosen by the family (PLAN.md decision 11, single-mode half):

```
[cron */5m] -> generate.py --tick -> schedule.due(config, payload, now)
                                       refresh? -> runner.refresh_calendars()
                                                     fetch every enabled feed, merge, sort
                                                     write events + calendars_fetched_at
                                       brief?   -> runner.write_brief()
                                                     build the prompt, call Claude
                                                     write headline + note, append to history
                                       neither  -> exit 0, silently

[browser]   -> app.py             -> board.build_view(config, payload, today)
                                       renders web/templates/board.html
```

`refresh_minutes` (default 60) and `brief_time` (default `"06:00"`, on the family's clock) are
ordinary config keys, so they migrate through `with_defaults` and will survive as a `jsonb` column.
`runner.run` is still both halves in order, which is what a plain `python generate.py` and the
settings page's **Rewrite now** do — the old `0 6 * * *` line keeps working, it just never sees a
same-day change. **Refresh calendars**, beside it, is `refresh_calendars` alone: no key needed, no
money spent, and the thing most people pressing the other button actually wanted.

Both keys are edited at `/settings/refresh` rather than in YAML. The select offers five intervals
and nothing else, but it also offers **whatever the file already says** — a hand-edited
`refresh_minutes: 45` has to survive somebody opening the page and pressing Save, or the UI quietly
overrules the file. `brief_time` is written back through `config.quoted()`: bare `06:00` is a string
to ruamel and a sexagesimal integer to a YAML 1.1 parser, and this file is meant to be hand-editable
with either.

**The board's own reload is derived, not stored** (`board.reload_seconds`). Five minutes is the
ceiling; only a `refresh_minutes` shorter than that lowers it, because reloading faster than the
calendars are fetched just redraws the same thing. A parent picks "how soon does a change show up",
not a browser knob — so there is no separate setting for it and the template reads
`view.reload_seconds` rather than deciding.

Three rules hold this together:

- **`due()` is pure and takes `now` as an aware datetime.** No clock, no I/O. That is what lets the
  same function drive a Pi's cron tick and, later, a worker loop walking every family. A brief is
  due when `generated_for_date` is not today *in the family's timezone* and the local clock has
  passed `brief_time`; a refresh is due when `calendars_fetched_at` is missing or older than
  `refresh_minutes`.
- **A refresh must not touch `headline`, `note` or `generated_for_date`.** `runner.REFRESH_KEYS`
  names the three keys it owns. A fresh agenda under yesterday's brief is exactly the amber-banner
  state `board.build_view` already handles, and the whole point of the split.
- **A failure is not handled, it is simply due again.** Nothing is written, so the next tick asks
  the same question and gets the same answer. That is the retry, and it is why there is no backoff
  or attempt counter anywhere.

Two consequences worth knowing.

**A feed that does not answer keeps its own last-known events**, because a missing event is
invisible while a stale one is still on the right day. The keeping is per feed, not per fetch: the
feeds that answered are always fresh, or one dead URL would freeze the whole board for as long as
nobody fixed it. `runner._with_last_known` does the merge, keyed on the `calendar` label each event
carries, and only inside the current window — so a permanently broken feed empties out over a
fortnight instead of growing a tail of appointments that already happened. A *paused* feed keeps
nothing: switching a calendar off means switching it off. The failure is recorded in
`calendar_statuses` and shown on the settings page, and the stamp is written either way, so a broken
feed is retried on the configured cadence rather than every tick.

**A tick takes an exclusive `flock` on `.tick.lock` and skips itself if another holds it**
(`generate.only_one_tick`). A tick can outlive its five-minute slot — several feeds timing out, then
a slow model call — and the next one would find the brief still unwritten, pay for it a second time,
write a second history entry, and race the first over the payload. The overlapping tick exits 0
instead: whatever is owed is still owed five minutes later. It is deliberately only around the tick.
**Rewrite now** is a person asking for something, and should do it.

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
pip install -r requirements-dev.txt   # pytest + the website build; not deployed to the Pi
cp config.example.yaml config.yaml
```

**Run the tests** — do this before every commit
```bash
venv/bin/python -m pytest tests/ -q
```

**Generate a board** (needs `ANTHROPIC_API_KEY` in `.env`)
```bash
python generate.py                  # today: fetch the calendars and write the brief
python generate.py --tick           # only what is due now — what cron runs
python generate.py --date 2026-12-24  # any date, for testing
```
`--tick` and `--date` are mutually exclusive: a tick works from the real clock. `--config` now also
decides where `dashboard_data.json` and `content_history.json` live, so a scratch config keeps its
generated files beside it.

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
honest. The payload is for things only the generator can know. Then ask which half owns it: a key a
refresh writes goes in `runner.REFRESH_KEYS` so `write_brief` carries it forward, and a key the
brief writes must be one a refresh never touches.

**Changing the board layout.** Everything is sized in `rem` off one root value, so check all three
sizes at `/preview` rather than just the one you are looking at.

That root value is now *measured*, not guessed. A short script at the foot of `board.html` binary-
searches the largest `html { font-size }` whose content still fits the viewport, capped at
`min(26px, vh/24)`. The CSS `clamp()` stays as the no-JS fallback. Because `body` is
`height:100vh;overflow:hidden`, nothing ever reports an overflow — so the script lets the page lay
out freely for one measurement (`height:auto`) and puts it straight back.

It re-fits on `document.fonts.ready` as well as on resize, and that is not optional. Nunito arrives
after the first paint and sets taller lines than the system fallback, so a size measured before it
lands can overflow once it swaps in — measured at 557px of content in a 480px panel. The board only
looks right because it re-measures when the font arrives.

**The agenda's row budget.** `MAX_EVENTS = 5` is the budget for the whole agenda, not today's cap.
Today fills it first; tomorrow tops up whatever is left, capped again at `MAX_TOMORROW = 3` so it
stays a footnote even on an empty day. A five-event day therefore renders exactly as it did before
tomorrow existed. This is what "if there is space" means in code — a fixed row count, decided by a
pure function, rather than a layout measurement.

What those rows cost depends on which column is taller, so measure against a real config rather
than `config.example.yaml`. In two-column mode the side column (chores plus countdowns) usually
sets the page height, and the agenda grows into slack it was already wasting. On a config with
three chores and four birthdays the 800x480 root moves 14.23px -> 14.10px on a three-event day —
under 1% — and 14.23px -> 13.32px on a quiet one. The two-chore example config has a shorter side
column, so there the agenda *is* the constraint and the same change costs 8% and 13%. The stacked
single-column layout (an iPad in portrait) has no side column to hide behind and always pays the
full price, around 13-18%. Everything fits at all three sizes in every case. Raising either
constant spends more type size, so measure at `/preview` before you do.

In two-column mode the body is a grid, and **the note sits under the agenda, not across the
bottom**. The agenda is short on a quiet day while chores plus countdowns are not, so a full-width
note left the lower left quarter of an 800x480 panel empty. Under the agenda it balances the two
columns instead: on a five-event day the left column measures 311px against the side column's 312.

**Saving a page to a home screen.** `/` and `/settings/` each serve their own web app manifest
(`web/manifest.py` holds what they share), so a saved link gets the mark and a name instead of a
URL — the board full screen for a tablet used as the panel, the settings UI standalone on a phone.
They must keep **different `id`s**: share one and the phone treats them as a single app, so saving
the board would replace the settings icon. iOS reads none of the manifest; its icon and label come
from the `apple-touch-icon` link and `apple-mobile-web-app-title` in the page head, which is why
both are set on both pages. The PNGs in `web/static/` are drawn by `website/generate_favicon.py`,
which renders the same mark as the favicon at every size the site and the app need — the outputs
are committed, so Pillow stays out of `requirements.txt` (it is declared in `requirements-dev.txt`).
**Editing `favicon.svg` means re-running that script**, or the `.ico` and the PNGs keep serving the
old mark: `website/static/favicon.ico` sat two weeks behind its own SVG that way. The settings page offers this once and
remembers a "Not now" in `localStorage`; it hides itself when already running from a home screen.
Note that Chrome's own install prompt needs https, so on a home network it never fires and the
written steps are what people see.

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
  The README now says so too, in a callout under **Getting started** and a pointer from the Pi
  section — it used to be written down only here and in the `app.py` docstring, neither of which a
  user reads. Cloud mode cannot inherit this — see
  [Hosted mode raises the stakes](#hosted-mode-raises-the-stakes).
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
- **Do not trust `--window-size` for layout work at all.** Even with the +87 correction it has been
  seen to ignore the flag and report a 756x469 viewport, which silently puts the board on the wrong
  side of the `3/2` media query. Size the page with an **iframe of exactly the target dimensions**
  instead, the way `/preview` already does, and read the numbers out of `iframe.contentWindow`. That
  is deterministic; the flag is not.
- **The board's `<meta http-equiv="refresh">` stops headless Chrome ever exiting.** `--screenshot`
  and `--dump-dom` both hang until the timeout, though they do write their output first. Strip the
  tag when rendering a copy for measurement, and wrap the call in `timeout` regardless.
- The honest check is `scrot` over SSH on the Pi itself: a real 800x480 panel, a real kiosk browser,
  no capture artifacts. The board reloads itself every 5 minutes on a default config, so a change
  takes one reload to appear — check `refresh_minutes` before concluding it did not work.

## Raspberry Pi Deployment

`deploy_to_pi.sh` rsyncs the code to the Pi — protecting the Pi's own `config.yaml`, generated data
and `.env`, and with `--delete` clearing anything dropped from the repo — creates the virtualenv if
it is missing, installs dependencies, and restarts the `dinkydash.service` systemd unit when it is
installed. Host, user and target directory are overridable with the `PI_HOST`, `PI_USER` and
`PI_DIR` environment variables; `--dry-run` shows what a deploy would change without touching the Pi.

Generation runs via cron:
```
*/5 * * * * cd /home/pi/dinkydash && venv/bin/python generate.py --tick >> generate.log 2>&1
```
Each tick does only what `config.yaml` says is owed, and logs nothing when that is nothing — "not
due" is at DEBUG precisely because it is the answer to roughly 260 of the day's 288 ticks. A tick
that overruns its slot makes the next one skip rather than double up, so the interval is a floor and
never a guarantee. The old
`0 6 * * * generate.py` line still works and does both halves at once; use one or the other, not
both. A failed run leaves the previous board in place rather than blanking the screen, the board
labels itself stale, and the next tick tries again.
