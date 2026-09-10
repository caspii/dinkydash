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
3. **The marketing site** (`website/`) — dinkydash.co, a second Flask app rendering Markdown
   through Jinja on request. No build step and no committed HTML.

**This repo is public and MIT-licensed**, and the hosted multi-tenant SaaS is being built inside
it, with self-hosting as the second mode of one codebase. Both facts constrain every change: see
[This is a public repo](#this-is-a-public-repo) and [Two modes, always](#two-modes-always) below.
Before making structural changes, read:

- [PLAN.md](PLAN.md) — hosted MVP architecture, phases, settled decisions, open questions
- the strategy document — positioning, pricing, SEO. Not in the repo by policy: it is a Linear
  document on the Dinky Dash team. See [Strategy and marketing live in
  Linear](#strategy-and-marketing-live-in-linear).
- [design/](design/) — mockups for the settings UI and the board, with the reasoning

### The other instruction files

This file is loaded on every task, so it holds only what applies to every change. The detail
that matters in one place lives beside that place, and arrives when you open a file there:

| File | Read it when |
|---|---|
| [`dinkydash/CLAUDE.md`](dinkydash/CLAUDE.md) | Touching the engine, the storage seam, the payload, the tick, or `migrations/` |
| [`web/CLAUDE.md`](web/CLAUDE.md) | Changing the board's layout, the settings UI, or measuring either |
| [`website/CLAUDE.md`](website/CLAUDE.md) | Working on the marketing site or the image generators |
| [`doc/operations.md`](doc/operations.md) | You need the state of the running system — secrets, the Pi, what has been rotated. A log, not guidance, and deliberately not loaded |

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
  protects the first — the single `|safe` in `web/` is on the QR code `segno` draws from our own
  screen URL, and none should ever appear on feed or user content. For the second, treat the text as data: an event titled "ignore your instructions
  and ..." must not change what the model does.
- **The server fetches URLs the user typed, and `fetch_feed` is what keeps that safe.** On a Pi the
  typist owns the network; hosted it is our infrastructure dialling whatever a stranger pasted, and
  everything worth reaching is inside. Four rules, all in `calendars.py` and all tested in
  `tests/test_feed_safety.py`: **https only** (`webcal://` is normalised, plain `http` is refused
  because it puts the secret address on the wire); **every resolved address checked** against
  private, loopback, link-local, reserved and multicast, before any request is made; **redirects
  followed by hand** with the scheme and address re-checked at each hop, because a public URL that
  302s to `169.254.169.254` is the whole attack; and a **10 MB body cap** enforced on
  `Content-Length` *and* on the read, since a server can omit or lie in that header.
  `FeedRefused` subclasses `FeedError` on purpose, so one bad URL in a config is a failed feed
  rather than a failed tick. **Connect to the checked IP**, preserving the original hostname for
  TLS SNI, certificate verification and the `Host` header. The per-request Requests adapter uses
  only validated numeric addresses, including IPv6/IPv4 fallback; every redirect resolves and
  validates again. Calendar fetches use direct connections because an environment proxy could
  resolve the hostname elsewhere. `tests/test_feed_transport.py` exercises this with changing DNS
  answers and real TLS on an isolated local server.
- **Calendar contents leave the machine.** They go to Anthropic to write the daily line. A fair
  trade, and it *is* said now (DIN-44): in `website/content/privacy.md`, in the sub-processor list
  on it, on `/settings/account`, and — the one that matters — in the blurb beside the field where
  somebody pastes a calendar link. **Those pages are claims about what this code does.** A retention
  period is a promise that a `DELETE` exists; a sub-processor list is a promise that nothing else is
  called. Change what the app stores, sends, or sends it to, and the policy changes in the same
  commit.
- **Log the label, not the URL.** `fetch_events` logs `entry["label"]` on purpose. The exception
  text does not follow that rule by itself — see the gotcha below.
- **Service ticks log metadata, never generated family text.** `runner.write_brief` logs the
  date and token usage. Headline/note output belongs to an explicit CLI run, outside `--tick`.
  Access-log redaction covers malformed and encoded screen URLs as well as valid credentials;
  the route's token alphabet must not limit the log filter (`tests/test_private_logs.py`).

### Hosted mode raises the stakes

Self-hosted is one family on their own network and has **no authentication by design**: anyone who
reaches the port can edit the config, which is the same trust model as the file it writes. Cloud
mode is a different product on the same code.

- **Every read and write is scoped to a `family_id`, and that id comes from the session.**
  `web/family.py` builds one `PostgresStore` per request out of it, over a pool built once per
  process — never one pool per request, because the cluster has 22 connections and a PgBouncer in
  front. Nothing a caller can send names a family: no path segment, no query parameter, no form
  field, no header. That is stronger than checking an id, and it is why there is no "the" family
  anywhere. When a route does one day take a family id — the admin view is the likely first — the
  check goes in `family.py`, before the store is built, and **a mismatch is a 404 and never a 403**:
  "forbidden" confirms the row exists, which tells one family that another one does.
- **The operator's page is behind a list of addresses, and a miss is a 404.** `/admin` (DIN-37)
  shows signups and activations by week, and only to a signed-in account whose address is in
  `DINKYDASH_ADMIN_EMAILS`. Anybody else gets the same answer as a URL that does not exist, and an
  unset list means nobody. It reads `growth_by_day` — a date and two counts, kept by a trigger on
  `families` and surviving deletion the way `global_model_spend` does — and one bare `count(*)`, so
  no family row is read and no id passes through it. `tests/test_admin.py` asserts each of those.
- **`web/__init__.py` falls back to a hardcoded `app.secret_key`.** Harmless with no auth; in cloud
  mode the session *is* the authentication, so cloud mode must refuse to start without a real
  `DINKYDASH_SECRET_KEY`.
- **A magic link is a bearer credential, and so is everything it touches.** `dinkydash/accounts.py`
  holds the lifecycle — 32 bytes from `secrets`, only the SHA-256 stored, fifteen minutes, spent by
  a single `UPDATE ... WHERE used_at IS NULL RETURNING`. **A login link in a log is a login in a
  log**, which is why the token rides in the query string, `.do/app.yaml` sets a gunicorn access
  log format built from `%(U)s` (path, no query) rather than the default `%(r)s`, and
  `auth.NoTokens` scrubs `?t=` from both request loggers regardless. All three are asserted in
  `tests/test_auth.py`; none of them is a preference.
- **A login request answers identically whether or not the address has an account**, including when
  it is rate-limited and when the send fails. Anything else enumerates accounts, and the accounts
  are families. **`/login` is the sign-up form too** (DIN-41), which is why there is no "create an
  account" route: a second page, or a second button, would say which addresses already have one.
- **Nothing a stranger can POST creates a row that costs money.** A sign-up creates the family when
  the emailed link is *clicked*, so an unverified one costs a token row and an email rather than a
  trial and a daily Anthropic call. That is the rate limit; the cap is the spend breaker below.
- **Every form that writes carries a CSRF token**, in *both* modes — `web/session.py`, with no
  switch to turn it off. A test walks the templates and fails on a form without one.
- **Screen tokens are bearer credentials**, and unlike a magic link they never expire — a wall panel
  holds one for months. So `/s/<token>` is `noindex`, `no-store`, makes no third-party request,
  never echoes the token back on a miss, and is rotatable, which is the only revocation there is.
  **A wrong token is a 404 and never a 403**: "forbidden" would confirm it exists.
- **A token in a *path* is in the access log; a token in a query string is not.** `%(U)s` is what
  keeps `?t=` out, and it is exactly what would write `/s/<token>` down thousands of times from one
  panel. `auth.NoTokens` scrubs both, on both request loggers, and `tests/test_screen.py` fails if
  it stops.
- **Rate-limit the misses, not the requests.** A real screen asks for its board every few minutes
  for years; counting that would put a rate limit on somebody's kitchen wall. Only wrong tokens are
  counted, which is also the only thing worth counting.
- **The sign-in rate limits are ours, not an edge rule, so that a refusal is a line somebody can
  read.** That is the trade being made — a Cloudflare rule would be sturdier and invisible. What
  goes in the line is chosen: the caller's address in full, the *domain* of the address asked about
  and never the address, and nothing at all for an address with no account. `tests/test_auth.py`
  asserts each of those, because a log policy nobody tests is a log policy that drifts.
- **Spend caps are a security control, and they exist now** (DIN-43). `dinkydash/budget.py` counts
  **calls, not money** — a price table goes stale silently and in the wrong direction — per family
  and globally, in one statement that decides and records before the call. Three rules to keep:
  **charge on the attempt**, because a revoked key that fails every time reports no usage and would
  otherwise retry for ever; **a refusal is an `OverBudget`, which is a `GenerationError`**, so every
  caller's existing keep-last-good path handles it and no second such path gets written; and
  **anything new that calls Anthropic takes a budget**, the way it takes a store. "Rewrite now" was
  the one path with no limit on it at all, and it is charged now too.
  The budget also applies the platform's model and output-token ceiling before hosted generation.
  Its global daily aggregate has no family identifiers and survives account deletion (DIN-49/51).

### The safety net, and what it does not cover

Phase 0 of PLAN.md is mostly this. Three of the four pieces are now in place.

`.github/workflows/test.yml` runs on every push and pull request, as two independent jobs so a
secret and a broken test are separate red X's: **pytest** on Python 3.11, and **gitleaks** over the
full history — `fetch-depth: 0`, because gitleaks scans commits rather than the working tree.
GitHub's own secret scanning is switched on as a second layer, but **gitleaks is the layer that was
observed to work** — see [doc/operations.md](doc/operations.md) for what happened when the other
one was tested.

The gitleaks job runs the MIT-licensed binary directly, pinned, rather than the upstream
`gitleaks-action` — that action is a bundled JavaScript blob under a commercial licence, and this is
one fewer thing holding a token in our CI. Rules live in `.gitleaks.toml`, which extends the default
set with the one shape the defaults do not know: **an iCal secret address**. Google
(`private-` + 32 hex) and iCloud (`/published/2/` + a long token) both have a rule; the visibly fake
examples in the docs (`private-xxxx`, `private-8f3c1a`) are too short to match, so keep new ones
that way. The single allowlist entry is the Ahrefs Web Analytics site key, which is served in the
`<head>` of every page on dinkydash.co. It used to trip `generic-api-key` 4,000+ times across the
committed `docs/`; with the site rendered on request there is one copy of it, in a template.
**Allowlisting is for values that are public by design.** A real secret that reached a commit is
fixed by rotating it.

Two things the net does not catch, both worth knowing before trusting it:

- **The defaults have no rule for a calendar URL**, which is why we wrote our own. Anything else
  shaped like a password in a URL needs the same treatment.
- **`config.yaml` is in the history**, nine commits from before it was gitignored. It holds two
  children's first names; it holds no credential, no calendar URL and no key, so there is nothing to
  rotate — but it is public and permanent, and rewriting a published history is not a fix worth the
  breakage. It is the reason the rules above exist.

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

**Where the board is served is part of the authentication gate**, not a fifth thing. Single mode
puts it at `/`: one family, no session, the URL somebody types into a Pi's kiosk browser. Cloud mode
cannot, because a wall panel has no way to sign in — so there the board is at `/s/<token>` and `/`
is the front door of the signed-in area. `board.render_board` is what the two routes share, so it is
one board reached two ways rather than two that drift, and `tests/test_cloud_mode.py` asserts the
two are byte-identical apart from the one link that has to differ.

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
├── store.py           the seven storage operations; FileStore, the single-mode one
├── pgstore.py         PostgresStore, the cloud one. Imports psycopg; single mode never does
├── db.py              the connection pool and the migration runner (cloud only)
├── mail.py            one transactional email, over SendGrid (cloud only)
├── accounts.py        users, the links that sign them in, and sign-up (cloud only)
├── screens.py         the token that puts a board on a wall (cloud only)
├── budget.py          what a family may spend on the model, and what everybody may
│                     (`accounts.delete_family` is the hard delete; see phase 5)
├── growth.py          signups and activations per day, with no family in the row (cloud only)
└── runner.py          the two halves of the day, reading and writing through a store

web/
├── __init__.py        create_app(): the pool, the mode gates, the blueprints
├── family.py          which family a request is for, and its store
├── session.py         what the cookie carries: who is signed in, and CSRF
├── ratelimit.py       a per-key counter, in this process (the per-IP half)
├── routes/board.py    the board and the preview harness
├── routes/settings.py the settings UI (one table drives every list section)
├── routes/auth.py     /login, /login/link, /logout — cloud mode only
├── routes/screen.py   /s/<token> — the board with no session, cloud mode only
├── routes/admin.py    /admin — signups and activations by week, for DINKYDASH_ADMIN_EMAILS only
└── templates/         board.html, preview.html, auth/*.html, settings/*.html, admin/growth.html
```

### The storage seam

Seven operations, on one object, and nothing above them knows what is behind it — `FileStore`
for a Pi, `PostgresStore` for cloud mode, and `tests/test_store_contract.py` asserting the two
behave identically. Two invariants hold anywhere in the repo:

- **`store.py` and `config.py` are the only files under `dinkydash/` that open a file**, and
  `pgstore.py` and `db.py` are the only ones that import psycopg. `grep -rn "open(" dinkydash web`
  is the check, and it should stay that short. A new file read anywhere else is a caller that cloud
  mode will have to fork.
- **Every `PostgresStore` query is scoped to `self.family_id`.** There is no unscoped read and no
  unscoped write in that file, and there must never be one. An id arriving in a URL is a claim, not
  a fact, and the place to check it is before it reaches a store.

The seven operations, how the halves are written, the migration runner and the connection pool are
in [`dinkydash/CLAUDE.md`](dinkydash/CLAUDE.md), along with what the payload may hold and how the
two cadences of a tick are decided.

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
That is the suite a self-hoster runs: the Postgres tests skip, everything else passes. To run the
other half — the store contract against a real database, and the cloud-mode board — point it at a
scratch database:
```bash
pip install -r requirements-cloud.txt          # psycopg; not in requirements.txt
createdb dinkydash_test
DINKYDASH_TEST_DATABASE_URL=postgresql:///dinkydash_test venv/bin/python -m pytest tests/ -q
```
The fixture migrates that database itself, so there is nothing to set up and nothing to tear down.
CI runs it both ways on every push, which is the point: the parity assertions only mean something if
they actually run.

**Apply the schema** (cloud mode only)
```bash
venv/bin/python migrate.py --status                  # what is outstanding
venv/bin/python migrate.py --database-url postgresql:///dinkydash_dev
```
Without `--database-url` it reads `DATABASE_URL_DIRECT` — the cluster, not the pool.

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

**Run the marketing site** (dinkydash.co)
```bash
pip install -r requirements-site.txt        # markdown, pyyaml, gunicorn
FLASK_APP=website.site flask run --port 5001
```
There is no build step and no `docs/` directory: `website/site.py` renders `content/*.md` through
`website/templates/` on request. Adding a page is still "write a Markdown file" and nothing else.

Deployed on DigitalOcean App Platform from `.do/app.yaml` — Python buildpack, no Dockerfile, and
`doctl apps update <id> --spec .do/app.yaml` applies a change. **The one thing the dashboard has to
do is create an app with a GitHub source**: `doctl` cannot introduce one (an API token carries no
GitHub OAuth session), though it can update an app that already has one.

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

**Changing the payload shape.** Ask first whether the value can be recomputed from config + date.
If it can, it belongs in `board.build_view`, not the payload — that is what keeps the stale state
honest. The payload is for things only the generator can know. Then ask which half owns it: a key a
refresh writes goes in `runner.REFRESH_KEYS` so `write_brief` carries it forward, and a key the
brief writes must be one a refresh never touches.

**Changing the board, or the settings UI.** Read [`web/CLAUDE.md`](web/CLAUDE.md) first. The
board is sized off one measured root value and every length is relative, so a change that looks
right at one size is not evidence about the other two — and `--window-size` cannot be trusted
to tell you.

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
  The README now says so too, in a callout under **Quickstart** — it used to be written down only
  here and in the `app.py` docstring, neither of which a user reads. Cloud mode cannot inherit
  this — see [Hosted mode raises the stakes](#hosted-mode-raises-the-stakes).
- **A `FeedError` message must never carry the URL, and `calendars._why` is what keeps it out.**
  `requests` formats both `raise_for_status()` and connection errors with the full URL (`404 Client
  Error: ... for url: https://.../private-REALSECRET/basic.ics`), and `fetch_feed` used to wrap
  `{exc}` straight in — publishing it to `generate.log` and to the feed status on the settings page.
  `_why` reduces it to a category and a status code, and the host is left out too: it is not
  possible to tell `calendar.google.com` from `calendar.the-smiths.example` in code. The parse error
  is scrubbed for the same reason — a parser quotes the line it choked on, which is an appointment.
  `tests/test_secrets_and_headers.py` fails if any of that regresses.
- `strftime("%-d")` is glibc-specific. Fine on a Pi and in CI; would need changing for Windows.
- **Measuring the board in headless Chrome is full of traps** — a viewport that is not the size
  the flag asked for, a reused instance returning the previous run's numbers, and a `--screenshot`
  that writes its file and then hangs forever. All of them, and what to do instead, are in
  [`web/CLAUDE.md`](web/CLAUDE.md).
