# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

DinkyDash is a family dashboard for a screen on the wall. A daily cron job calls the Claude API to
write a headline; the Flask app renders that alongside today's agenda, whose
turn each chore is, and the countdowns — all recomputed from `config.yaml` at render time.

Three components:

1. **The engine** (`dinkydash/`) — pure functions plus the model call. No config file is read here,
   no clock consulted, nothing written to disk.
2. **The web app** (`web/`) — the dashboard at `/`, a settings UI at `/settings` that writes `config.yaml`.
3. **The marketing site** (`website/`) — dinkydash.co, a second Flask app rendering Markdown
   through Jinja on request. No build step and no committed HTML.

**This repo is public and MIT-licensed**, and the hosted multi-tenant SaaS is being built inside
it, with self-hosting as the second mode of one codebase. Both facts constrain every change: see
[This is a public repo](#this-is-a-public-repo) and [Two modes, always](#two-modes-always) below.
Before making structural changes, read:

- the hosted MVP plan — settled decisions, phases and what is still open. A Linear document on the
  Dinky Dash team ([DinkyDash Hosted MVP — Plan](https://linear.app/keepthescore/document/dinkydash-hosted-mvp-plan-3ddbb8cf36a5)),
  because it tracks Linear issues; the engineering rules it rested on are in this file and the
  ones it points to.
- the strategy document — positioning, pricing, SEO. Not in the repo by policy: it is a Linear
  document on the Dinky Dash team. See [Strategy and marketing live in
  Linear](#strategy-and-marketing-live-in-linear).
- [design/](design/) — mockups for the settings UI and the dashboard, with the reasoning

### The other instruction files

This file is loaded on every task, so it holds only what applies to every change. The detail
that matters in one place lives beside that place, and arrives when you open a file there:

| File | Read it when |
|---|---|
| [`dinkydash/CLAUDE.md`](dinkydash/CLAUDE.md) | Touching the engine, the storage seam, the payload, the tick, or `migrations/` |
| [`web/CLAUDE.md`](web/CLAUDE.md) | Changing the dashboard's layout, the settings UI, or measuring either |
| [`website/CLAUDE.md`](website/CLAUDE.md) | Working on the marketing site or the image generators |
| [`doc/voice.md`](doc/voice.md) | Writing or changing anything a customer reads — the site, the settings UI, email, the README |
| [`doc/operations.md`](doc/operations.md) | You need the state of the running system — secrets, the Pi, what has been rotated. A log, not guidance, and deliberately not loaded |

## This is a public repo

DinkyDash is open source, and the hosted product is being built in the same public repo.
Everything pushed is world-readable the moment it lands, and the repo is itself the
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
- **Secrets come from the environment**, never a literal in code or config. `.env` is not in git and
  there is a copy wherever the app runs, so rotating a key means editing each copy where it
  lives — on a Pi in place, and in the main checkout — rather than pushing one over the other.
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
  targets, cost-per-family models, the hosted MVP plan with its phase tracking, and anything
  framing this repo as top of a funnel.

The shop window is the exception, and only the window. The README may state the hosted price and
link the waitlist, and `website/` is a marketing site by definition. What must not appear is the
*reasoning* behind either — the number is public, the case for the number is not.

New strategy docs are written to a temporary file and pushed straight to Linear, never through the
working tree where a stray `git add` can catch them:

```bash
linear document create --team DIN --title "..." --content-file /tmp/note.md
```

Relative links like `[CLAUDE.md](CLAUDE.md)` break once a document is in Linear. Rewrite them to full
`https://github.com/caspii/dinkydash/blob/main/...` URLs before uploading.

### Handling other people's data

- **Calendar feeds are untrusted remote input.** Event titles land in the rendered page and in the
  model prompt. Autoescaping covers the page: the single `|safe` in `web/` is on the QR code
  `segno` draws from our own screen URL, and none goes on feed or user content. In the prompt the
  text is data: an event titled "ignore your instructions and ..." must not change what the model does.
- **`fetch_feed` fetches URLs a stranger typed, from our infrastructure.** `calendars.py` allows
  https only (`webcal://` is normalised, plain `http` refused); refuses private, loopback,
  link-local, reserved and multicast addresses; follows redirects by hand and re-checks each hop;
  connects to the address it checked, keeping the hostname for TLS and `Host`; ignores environment
  proxies; and caps the body at 10 MB. `FeedRefused` subclasses `FeedError`, so one bad URL is a
  failed feed, not a failed tick. Tests: `test_feed_safety.py`, `test_feed_transport.py`.
- **Calendar contents go to Anthropic** for the headline, and the privacy page, the sub-processor
  list, `/settings/account` and the blurb beside the calendar field say so. **Those pages are
  claims about this code**: change what the app stores, sends, or sends it to, and change the
  policy in the same commit.
- **Log the label, never the URL** (`fetch_events` logs `entry["label"]`; see the `FeedError`
  gotcha below). **Ticks log metadata, never generated family text.** Access-log redaction covers
  malformed and encoded screen URLs too (`tests/test_private_logs.py`).

### Hosted mode raises the stakes

Self-hosted is one family on their own network and has **no authentication by design**. Cloud mode
is a different product on the same code. The rules, each enforced in the named file and its test:

- **Every read and write is scoped to a `family_id` from the session** (`web/family.py`), one
  `PostgresStore` per request over one pool per process. Nothing a caller sends names a family.
  When a route does take a family id, check it in `family.py`, and **a mismatch is a 404, never a
  403** — "forbidden" confirms the row exists.
- **`/admin` is gated by `DINKYDASH_ADMIN_EMAILS`; a miss is a 404 and an unset list is nobody.**
  It shows aggregates (`growth_by_day`, paying count) and a roster of addresses and bookkeeping
  columns — never a config, a name, a calendar or a family id (`tests/test_admin.py`).
- **Cloud mode refuses to start without `DINKYDASH_SECRET_KEY`**; the session is the authentication.
- **Magic links** (`dinkydash/accounts.py`): 32 random bytes, only the SHA-256 stored, fifteen
  minutes, spent by one `UPDATE ... WHERE used_at IS NULL RETURNING`. **`GET /login/link` only
  renders a button; its `POST` spends the link**, because mail scanners follow links but do not
  submit forms. Do not auto-submit that page.
- **`/login` answers identically whether or not the address has an account**, including when
  rate-limited, refused by the bot check, or when the send fails — it is also the sign-up form, so
  there is no second route to give the game away. The family is created when the link is spent,
  not when the form is posted, so a stranger's POST costs an email and not a trial.
- **Tokens stay out of logs.** Login tokens ride in `?t=`; screen tokens are in `/s/<token>`.
  The gunicorn access format uses `%(U)s`, and `auth.NoTokens` scrubs both from both request
  loggers (`tests/test_auth.py`, `tests/test_screen.py`).
- **Screen tokens never expire**, so `/s/<token>` is `noindex`, `no-store`, makes no third-party
  request, never echoes the token, and is rotatable. A wrong token is a 404. Only misses are
  rate-limited.
- **Rate limits are ours** (`web/ratelimit.py`, per IP, in process; per address in Postgres), so a
  refusal is a log line: the caller's IP, the domain of the address asked about, never the address.
- **Turnstile** (`web/turnstile.py`) is on only when both keys are set. A refusal is answered
  before the address is looked up; an unreachable Cloudflare lets the request through.
- **CSRF on every writing form, in both modes** (`web/session.py`); a test walks the templates.
- **Fathom** (`web/fathom.py`) loads only with `FATHOM_SITE_ID`, only on the public sign-in pages
  and the one new-account page, and sends the path without the query string.
- **Spend caps** (`dinkydash/budget.py`) count calls, not money, per family and globally, charged
  on the attempt. A refusal is an `OverBudget`, a `GenerationError`, so the existing keep-last-good
  path handles it. **Anything new that calls Anthropic takes a budget**, the way it takes a store.
- **Sentry** (`dinkydash/sentry.py`, cloud only) receives the exception, our frames, the log
  template and the request method. `scrub` strips URLs, headers, bodies, locals, breadcrumbs and
  log arguments. **Keep data in a `log.error`'s arguments, never its template** (`tests/test_sentry.py`).
- **Anything new that sends data to a third party is named on the privacy page and
  `/settings/account`** in the same commit.

### The safety net, and what it does not cover

`.github/workflows/test.yml` runs two jobs on every push and pull request: **pytest** (Python 3.11,
with and without Postgres) and **gitleaks** over the full history (`fetch-depth: 0`), using the
pinned MIT binary rather than the upstream action. `.gitleaks.toml` adds rules for iCal secret
addresses (Google `private-` + 32 hex, iCloud `/published/2/`). Its one allowlist entry is the
public Ahrefs site key. **Allowlist only values that are public by design**; a real secret that
reached a commit is fixed by rotating it. GitHub secret scanning is on as a second layer.

Deploys: App Platform probes `/healthz` on the marketing app, which reads nothing. `create_app`
calls `db.ready` and refuses to start if the database does not answer in ten seconds, so a wrong
`DATABASE_URL` fails the deploy and fires the `DEPLOYMENT_FAILED` alert in `.do/app.yaml`. The
worker sends a Sentry cron check-in after each completed pass, and a Sentry uptime monitor fetches
`app.dinkydash.co/login`. `tests/test_deploy_spec.py` pins the probe, the alert and the DSN shape.

Not covered: anything password-shaped in a URL other than the two calendar shapes needs its own
gitleaks rule. `config.yaml` is in early history with two children's first names and no
credential; that is public and permanent, and the reason the rules above exist.

**Requirements are pinned with `==`** to what CI passes. Bump deliberately; `anthropic` must stay
at 1.x or later for `output_config`. **`requirements.txt` is runtime only** — what a Pi installs.
`website/` and tooling dependencies go in `requirements-dev.txt`.

## Architecture

### Two modes, always

One codebase, two products:

```
DINKYDASH_MODE=single   config.yaml · auth off · billing off · one family · local cron
DINKYDASH_MODE=cloud    Postgres · magic links · Stripe · many families · worker + scheduler
```

**Every change must work in both.** The engine, the dashboard template, the CSS, the calendar handling
and the settings UI are shared verbatim; mode gates four things and no others — authentication,
billing, where the config is stored, and what drives the scheduler. A mode check anywhere else means
the change is in the wrong layer.

**Where the dashboard is served is part of the authentication gate**, not a fifth thing. Single mode
puts it at `/`: one family, no session, the URL somebody types into a Pi's kiosk browser. Cloud mode
cannot, because a wall panel has no way to sign in — so there the dashboard is at `/s/<token>` and `/`
is the front door of the signed-in area. `board.render_board` is what the two routes share, so it is
one dashboard reached two ways rather than two that drift, and `tests/test_cloud_mode.py` asserts the
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
├── clock.py           the only place a displayed time is formatted, in either shape
├── history.py         what the recent notes say, and how they trim (pure)
├── schedule.py        due(config, payload, now) -> what a tick owes (pure)
├── store.py           the seven storage operations; FileStore, the single-mode one
├── pgstore.py         PostgresStore, the cloud one. Imports psycopg; single mode never does
├── db.py              the connection pool and the migration runner (cloud only)
├── mail.py            one transactional email, over SendGrid (cloud only)
├── accounts.py        users, the links that sign them in, and sign-up (cloud only)
├── screens.py         the token that puts a dashboard on a wall (cloud only)
├── budget.py          what a family may spend on the model, and what everybody may
│                     (`accounts.delete_family` is the hard delete)
├── billing.py         hosted subscriptions: Stripe owns payments, Postgres owns access (cloud only)
├── lifecycle.py       trial and access boundaries, on the database's aware clock (cloud only)
├── growth.py          signups and activations per day, with no family in the row (cloud only)
├── sentry.py          error reports and the worker's check-in, and what neither may carry (cloud only)
└── runner.py          the two halves of the day, reading and writing through a store

web/
├── __init__.py        create_app(): the pool, the mode gates, the blueprints
├── family.py          which family a request is for, and its store
├── session.py         what the cookie carries: who is signed in, and CSRF
├── setup.py           the set-up checklist: what a new family still has to do, from the config
├── assets.py          static URLs with the file's content version, and the year they are cached for
├── ratelimit.py       a per-key counter, in this process (the per-IP half)
├── turnstile.py       the bot check in front of /login; off unless both keys are set
├── urls.py            app origins and dashboard paths, shared with the login-link CLI
├── emoji.py           what a free-text emoji field is allowed to hold
├── manifest.py        the two installable pages: a wall panel and a phone
├── feedback.py        what somebody can tell us: one form, one email, nothing kept
├── routes/board.py    the dashboard and the preview harness
├── routes/settings.py the settings UI (one table drives every list section)
├── routes/auth.py     /login, /login/link, /logout — cloud mode only
├── routes/screen.py   /s/<token> — the dashboard with no session, cloud mode only
├── routes/admin.py    /admin — signups and activations by week, for DINKYDASH_ADMIN_EMAILS only
├── routes/billing.py  signed-in payment actions, and the separately signed Stripe webhook
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
other half — the store contract against a real database, and the cloud-mode dashboard — point it at a
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
venv/bin/python migrate.py --status   # what is outstanding
venv/bin/python migrate.py            # apply it
```
**It does not read `.env`.** That file holds the live cluster under production's own key
`DATABASE_URL_DIRECT`, and a schema tool that loaded it would treat "apply my change" as "apply it
to the running service" — silently, because an up-to-date schema reports the same either way. So
with nothing named it migrates `db.DEV_DATABASE_URL`, this machine's development database and the
one `dev.py` serves — put through `db.on_this_machine` first, because a URL with no host is
redirected by `PGHOST` and a local-looking default is not a local one. `DATABASE_URL_DIRECT` is
used when the *environment* sets it, which on App
Platform's pre-deploy job is the only thing set and on a laptop takes an export; `--database-url`
overrides both, and an empty value there is refused rather than fallen back from.

**Generate a dashboard** (needs `ANTHROPIC_API_KEY` in `.env`)
```bash
python generate.py                  # today: fetch the calendars and write the brief
python generate.py --tick           # only what is due now — what cron runs
python generate.py --date 2026-12-24  # any date, for testing
```
`--tick` and `--date` are mutually exclusive: a tick works from the real clock. `--config` now also
decides where `dashboard_data.json` and `content_history.json` live, so a scratch config keeps its
generated files beside it.

**Run the hosted dashboard and marketing site together**
```bash
venv/bin/python dev.py              # also Conductor's default dev run action
```
Requires a development `DATABASE_URL` **on this machine** — loopback or a Unix socket; a remote
database is refused before anything connects, because a workspace's `.env` can carry one — and a
`DINKYDASH_SECRET_KEY`. Outstanding migrations are applied on start, because that database is
disposable. See [doc/development.md](doc/development.md) for setup,
port overrides, sign-in and Conductor configuration pickup. Both processes stop
together; the launcher always selects cloud mode and refuses invalid setup.

**Run the self-hosted app**
```bash
python app.py                       # or: flask run --host=0.0.0.0
```
Dashboard at `/`, settings at `/settings`, all three screen sizes at once at `/preview`.

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
rotation, staleness, and the config round-trip — the things that break silently. They run
in under a second, so there is no excuse for skipping them.

**Testing without spending money.** `generate.py --date 2026-12-24` generates for any date, which is
how to check a countdown or a quiet day. It still costs one API call. To exercise the dashboard with no
call at all, run `python sample_board.py`, which writes a plausible payload for today and calls no
API. It refuses to overwrite a real one, so delete `dashboard_data.json` first if that is what you
want. Then edit the file by hand — change `generated_for_date` to an older date to see the stale
state, or move it aside entirely to see the dashboard before its first brief.

**Local data in a new workspace.** `config.yaml`, `dashboard_data.json` and `content_history.json`
are gitignored, so a new Conductor workspace only receives them through Files to copy, which reads
`.worktreeinclude` **from the main checkout on disk** — having it on the branch is not enough. If
the main checkout is parked on an old commit that predates that file, Conductor falls back to its
default `.env*` pattern: `.env` arrives, the rest does not. `.conductor/settings.toml` covers the
gap by falling back to `config.example.yaml` and seeding a sample dashboard, so a workspace always opens
on something real. Copied data still wins over both.

**Changing the payload shape.** Ask first whether the value can be recomputed from config + date.
If it can, it belongs in `board.build_view`, not the payload — that is what keeps the stale state
honest. The payload is for things only the generator can know. Then ask which half owns it: a key a
refresh writes goes in `runner.REFRESH_KEYS` so `write_brief` carries it forward, and a key the
brief writes must be one a refresh never touches.

**Changing the dashboard, or the settings UI.** Read [`web/CLAUDE.md`](web/CLAUDE.md) first. The
dashboard is sized off one measured root value and every length is relative, so a change that looks
right at one size is not evidence about the other two — and `--window-size` cannot be trusted
to tell you.

## Conventions

- **Copy follows [doc/voice.md](doc/voice.md), and the register of this file is not it.**
  Everything here is engineering documentation: dense, formal, written without contractions.
  Customer-facing writing is the opposite, and matching the surrounding page is no defence when
  that page has the same fault. Two rules carry most of it — read it aloud and use contractions,
  and **trace every claim about what the product does to the code that does it** before writing
  it down. A sentence about a feature that does not exist reads exactly like one about a feature
  that does.

- **Product wording follows [doc/terminology.md](doc/terminology.md).** Call the complete display
  a **dashboard** and the device showing it a **screen**. Keep the glossary in step with UI,
  email and website copy.

- **Comments and docstrings state the rule and its reason, never the incident.** Say what a check
  protects against, in general terms — not the date it went wrong, who pressed what, the Sentry
  issue it opened, or what production did that day. That history goes in
  [doc/operations.md](doc/operations.md), the log, or in Linear: the repo is public, and a war story
  in code is operational detail published for ever.
- **Nor the previous version.** A comment is read by somebody who has never seen the code any other
  way, so "this used to be X", "no longer does Y", "as it always has", "reversed in DIN-30" and
  "renamed because" all describe something that, to them, does not exist — and they have to read it
  before finding out it does not matter. Write the rule that holds now: not *"`DATABASE_URL` no
  longer belongs in `.env`"* but *"`.env` needs no `DATABASE_URL`; the launcher defaults to a local
  one"*. **The test is whether the sentence still makes sense to somebody who arrived today.** This
  covers docstrings, config headers, `.env.example`, `.do/app.yaml`, test docstrings and commit-sized
  "why I changed this" notes — everything except `doc/operations.md`, which is the log and is dated
  on purpose, and the Linear issue, which is where a decision's history belongs.
- **British English** throughout — UI copy, the model's system prompt, and `%-d %B` date formatting
  (`25 December`, not `December 25`).
- **Times are 24-hour by default** (`08:20`), and a family can choose 12-hour (`8:20 am`) instead.
  Every displayed time goes through `dinkydash/clock.py`, which is also the *only* place the two
  shapes are written — a `%H:%M` anywhere else is a time that will not follow the setting. Stored
  times keep one shape in both modes; the reader's shape is applied at the point of display, so a
  change shows on the next redraw rather than on the next calendar fetch.
- The dashboard is sized in `rem` off one root. The stylesheet fallback is `clamp(12px, 3.2vh, 40px)`;
  the script in `board.html` raises that until the content fills the viewport and lowers it when a
  busy day would overflow, capped at `min(120px, innerHeight / 9)`. Two columns from a 5:4 aspect
  ratio and 640px wide; portrait and narrower screens stack.
- The settings UI does the same off one root `clamp(1rem, 0.75rem + 0.625vw, 1.25rem)`: the mockup's
  16px on a phone, up to 20px on a desktop browser, so the phone layout reads at desk distance
  without becoming a second layout. Every length in `web/templates/settings/` is therefore in `rem`
  or `em` — a new `px` value there stops scaling and drifts out of proportion. Borders, focus rings
  and shadows are the exception and stay in `px`; hairlines should not scale.
- Light and dark are the same rules with a different set of CSS custom properties. Never hard-code a
  colour in a dashboard rule; add a token.
- Icons are inline SVG, never emoji. Emoji in *content* (avatars, chore markers) are the brand.

## Known issues and gotchas

- **`claude-haiku-4-5` takes no `thinking` parameter.** Omitting it means no thinking, which is what
  we want. If you move to Sonnet 5 or an Opus model, adaptive thinking is on by default and will
  compete with `max_tokens` — set it explicitly or raise the budget.
- **Structured outputs** (`output_config.format`) guarantee the response matches the schema, so
  there is no JSON-repair retry loop. Do not add one back.
- Self-hosted mode has **no authentication**. Anyone who can reach the port can edit the config.
  That is the same trust model as the file it writes, but keep the port off the public internet;
  the README says so in a callout under **Quickstart**. Cloud mode cannot inherit this — see [Hosted mode raises the stakes](#hosted-mode-raises-the-stakes).
- **A `FeedError` message must never carry the URL, and `calendars._why` is what keeps it out.**
  `requests` formats both `raise_for_status()` and connection errors with the full URL (`404 Client
  Error: ... for url: https://.../private-REALSECRET/basic.ics`), and that message reaches
  `generate.log` and the feed status on the settings page. `_why` reduces it to a category and a status code, and the host is left out too: it is not
  possible to tell `calendar.google.com` from `calendar.the-smiths.example` in code. The parse error
  is scrubbed for the same reason — a parser quotes the line it choked on, which is an appointment.
  `tests/test_secrets_and_headers.py` fails if any of that regresses.
- `strftime("%-d")` is glibc-specific. Fine on a Pi and in CI; would need changing for Windows.
- **Measuring the dashboard in headless Chrome is full of traps** — a viewport that is not the size
  the flag asked for, a reused instance returning the previous run's numbers, and a `--screenshot`
  that writes its file and then hangs forever. All of them, and what to do instead, are in
  [`web/CLAUDE.md`](web/CLAUDE.md).
