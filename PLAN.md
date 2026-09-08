# DinkyDash Hosted MVP — Plan

*Last updated: September 8, 2026. Supersedes `HOSTING_ANALYSIS.md` (deleted — it predated both the AI generation feature and the July 2026 calendar-display repositioning, and its recommended stack and data model no longer matched the product).*

*September 8, last: **the multi-tenancy is real** (DIN-39). `web/family.py` builds one `PostgresStore` per request from the family on the session, over a pool built once per process; `create_app` holds no store at all in cloud mode, and the environment variable that used to name "the" family is deleted from the code, the app spec and the docs. Nothing a caller can send — path segment, query parameter, form field or header — reaches a query as a family selector, which is a stronger property than checking an id against the session. The ids that do appear in URLs are item ids inside one family's config document, and another family's is not in the list: `tests/test_tenancy.py` walks every section and every write route and asserts a 404, never a 403. **Phase 1's "done when" is met.** `login_link.py` prints a sign-in link without waiting on email, because the preview and the support inbox both need one.*

*September 8, later still: **magic-link auth is built** (DIN-38). `dinkydash/accounts.py` is the token lifecycle — 32 bytes from `secrets`, only the SHA-256 stored, fifteen minutes, spent by one `UPDATE ... WHERE used_at IS NULL RETURNING`; `web/routes/auth.py` is `/login`, `/login/link` and `/logout`; `web/session.py` is the cookie and a CSRF token on every form that writes, in both modes. `/settings` in cloud mode is behind a session. What was deliberately still missing at that point was the **scoping**, which DIN-39 above then did. The token rides in the query string rather than the path because the app runs `gunicorn --access-logfile -` and a login link in a log is a login in a log — see the access log format in `.do/app.yaml`, which is now a security control.*

*September 8, later: **one service, not two.** The board joins the marketing site in the existing `dinkydash-site` app rather than getting its own, because that is how `qrpage.co` and `abc-league` already run in this account — one container, one gunicorn, everything in it. Staging is dropped until there is a paying family to protect. The `worker` is the one genuine addition, because the tick has no lock and two web instances would tick twice. See [Hosting and deployment](#hosting-and-deployment).*

*September 8, later: **sign-up exists** (DIN-41). An address posted to `/login` gets a link, and
clicking it creates the family, the parent and a starting config in one transaction. The design
question that had to be settled first was *when* the family is created, and the answer is **on the
click, not on the submit** — see [Sign-up](#sign-up) below. `login_tokens.user_id` is nullable and
the row carries an `email` instead (`migrations/002_signup_tokens.sql`). Nothing is created by
asking, so an unverified sign-up costs one token row and one email.*

*September 8: the transactional email provider is settled — decision 13, **SendGrid**, on the account KeepTheScore already sends from. The open question is closed. `dinkydash.co` is an authenticated sending domain on that account (DKIM and a monitor-only DMARC record are live in Cloudflare), and this repo has its own send-only API key. What is not built is the sending itself — that arrives with magic links in Phase 1.*

*September 7, later still: the Postgres layer is built (DIN-31) — `migrations/001_initial_schema.sql`, `migrate.py`, `dinkydash/db.py`, `dinkydash/pgstore.py`, and a contract suite that runs the same assertions over both stores in CI. Connection pooling is settled above. What is deliberately still missing is the multi-tenancy: cloud mode serves one family, named by an environment variable, because auth and scoping are Phase 1.*

*September 7, later: the storage seam is built (DIN-19). `dinkydash/store.py` holds the six operations, `FileStore` is the one implementation, and the runner and both blueprints take a store rather than a path. The seam section below describes what exists; `PostgresStore` is now a constructor argument away.*

*September 7 changes: the host is settled — decision 12, DigitalOcean App Platform in Frankfurt with DigitalOcean Managed Postgres and Cloudflare in front. The "Which host?" open question is closed, the hosting section is rewritten around it, and DNS gets its own Phase 0 line.*

*September 7, and this reverses a decision made the same day: **there is no Dockerfile and no Compose file.** App Platform does not need one — its Python buildpack builds from `.python-version` and `requirements.txt` and runs whatever `run_command` a component declares, which is how qrpage.co already deploys to the same platform, pre-deploy migration job and all. Docker was machinery with nothing here to earn it, so it is gone. Self-hosting is the from-source path it always was: a virtualenv and a cron line.*

*September 6 changes: decision 11 (the refresh cadence is a setting), a storage seam for the payload and history, a hosting and deployment recommendation, and the Batch API deferred.*

This document covers **how the hosted version gets built and launched**. Its companion — positioning, pricing anchors, and SEO — is kept outside this repo, as a Linear document on the Dinky Dash team.

---

## The goal

Turn DinkyDash from a single-family Raspberry Pi app into a hosted product a non-technical parent can sign up for and have running on a kitchen screen in under five minutes — without giving up the open-source repo that feeds the funnel.

**Target:** $39/year (or $6/month), 14-day trial, no card up front. Full structure and reasoning live in the strategy document.

---

## Decisions (settled)

| # | Decision | Rationale |
|---|---|---|
| 1 | **Python + Flask + Postgres**, single boring host. Not Next.js/Supabase. | The engine, prompt, and template are already Python/Jinja. A TypeScript rewrite discards the differentiated part for no user-visible gain. |
| 2 | **Single public monorepo.** Hosted app and self-host are one codebase in two modes. | Simpler than any split-repo arrangement: no packaging, no version pinning, no drift. Self-hosting becomes "the same app with one family in it." |
| 3 | **No Google OAuth.** iCal URL paste only, with **multiple calendars per family**. | OAuth needs a Google verification review measured in weeks. Multiple feeds (one per parent) also replaces the broken attendee filter properly. |
| 4 | **Screen access via unguessable URL.** No pairing code. | Simplicity. Constrains token length — see Architecture below. |
| 5 | **Dashboard renders to landing-page parity.** Person cards + real time-ordered agenda. Emoji/color avatars, no photo uploads. | It's what waitlist signups were shown. Emoji avatars delete storage, moderation, EXIF-stripping, and image resizing from the MVP. |
| 6 | **14-day trial, no card up front.** Then $39/yr, or $6/mo for the month-to-month case. One plan, unlimited people, chores, calendars and screens. No permanent free tier. | Annual is the shape of the purchase and pays one Stripe fee instead of twelve; $39 is half of Skylight Plus. Every free family costs real Anthropic money daily, forever. |
| 7 | **Stripe direct.** | Reuse of existing KeepTheScore setup. See open questions re: EU VAT. |
| 8 | **Fork KeepTheScore's privacy policy and ToS** as the starting point. | Faster than drafting; same jurisdiction and entity. |
| 9 | **Self-hosting stays, community-supported only.** | See below. |
| 10 | **The config dict is the storage contract.** `config.yaml` in single mode, a `jsonb` column in cloud mode. Not SQLite on the Pi. | The engine already takes a plain dict, so both modes can produce the same one. Self-hosters expect a file they can edit and copy, and a Pi should not have to run migrations to gain a field. One shape means one settings UI. |
| 11 | **The refresh cadence is a setting in the UI.** How often the calendars are re-fetched, and when the daily brief is written, are chosen by the family — not hard-coded in a cron line. | A calendar product whose board only learns about a new appointment the next morning is a support ticket waiting to happen. See [Three clocks, one setting](#three-clocks-one-setting). |
| 12 | **DigitalOcean App Platform (Frankfurt) + DigitalOcean Managed Postgres, with Cloudflare in front.** Not Hetzner and a box, which is what this plan recommended until 7 September. | Quickest route to a deployed app: no SSH, no firewall, no container machinery, and the worker is a second component off the same checkout. A managed database deletes the backup, upgrade and failover work a box would have added. About $25 a month against roughly €5 for the box — the difference buys the ops. See [Hosting and deployment](#hosting-and-deployment). |
| 13 | **SendGrid for transactional email**, on the same account KeepTheScore sends from. Not Postmark, and not the Customer.io connector. | Shared sender reputation from day one, which is the whole game for magic links — a link that lands in spam is a login that fails. It is one account, one bill and one set of suppression lists across six domains. Customer.io stays what it is: a marketing tool, right for the waitlist sequence, heavy for a login link. |

### On self-hosting (decision 9)

The repo is the credibility wedge and the backlink engine — the Show HN / r/selfhosted launch is still untried, and it's the fastest available path from DR 11 to the DR 30 the wedge keywords need. "Free and open source" is also the only line on the competitor comparison tables that Mango Display and DAKboard cannot copy.

What gets cut is the **support commitment**, not the code:

> Self-hosting is community-supported. Clone the repo, make a virtualenv, bring your own Anthropic API key, issues welcome but unanswered.

This costs roughly zero hours. Realistically almost no parent completes the current self-host path anyway — it needs a terminal and an API key — so this loses a support queue, not customers.

**Revisit in six months.** If the HN launch produces real referring domains, it paid for itself. If it produces nothing, close the repo then, with data rather than a guess.

### Licensing

Currently MIT, and the website says "MIT-licensed and free forever" in two places.

**Staying MIT for now.** At this scale the realistic cloning risk is low and MIT is the friendlier launch story. If cloning becomes a concern, AGPL is the standard move here (Plausible, Cal.com both chose it) — self-host freely, but run it as a service and you must publish modifications. Relicensing is straightforward while there are no outside contributors, but it would require updating the marketing copy in the same pass.

---

## Architecture

### One app, two modes

```
DINKYDASH_MODE=single   config.yaml · auth off · billing off · one family · cron ticks
DINKYDASH_MODE=cloud    Postgres · magic links · Stripe · many families · worker ticks
```

The generation engine, dashboard template, CSS, and calendar handling are shared verbatim. Mode only gates auth, billing, storage backend, and how the scheduler is driven.

### Where the config lives

`dinkydash.config.load_config` returns a plain dict, and everything above the
engine takes that dict. The file is one way to write it down; a database row is
another. Neither the engine, the board, nor the settings UI is told which.

So single mode keeps `config.yaml` — an editable, diffable, copy-to-back-it-up
file is most of why anyone self-hosts, and ruamel round-trip mode means an edit
made from a phone leaves the comments alone. Cloud mode stores the same dict in
a `jsonb` column. `with_defaults` and its migrations then run once for both.

The one thing this needs is that list items have identities rather than
positions. Every person, pet, chore, date and calendar carries a short `id`,
backfilled the first time the settings UI opens a file without them. That is
what lets one set of settings routes address a row in Postgres and an entry in
a YAML list without knowing the difference — and it fixes a real single-mode
bug on the way, where deleting anyone shifted everybody below onto somebody
else's edit form.

### The storage seam

*Built in DIN-19.* Decision 10 covers the config. The runtime writes two more
things — the payload and the note history — and those used to be file calls
scattered across `web/__init__.py` (`load_payload`), `runner.py`
(`write_payload`) and `history.py` (`load_history`, `record`). Cloud mode needs
the same operations against Postgres, so they were named before Phase 1 rather
than discovered during it:

```
load_config   / save_config
load_payload  / save_agenda + save_brief
recent_notes  / record_note
```

One object with those six methods, in `dinkydash/store.py`. `FileStore` is what
exists now, gathered up; `PostgresStore` is the cloud one. The runner, the board
route and the settings routes take a store and never learn which — `create_app`
accepts one, and every route reads `app.config["STORE"]`. In single mode the
payload is `dashboard_data.json`. In cloud mode it is composed from two rows —
the brief in `generations`, the fetched calendar window in `agendas` — and
comes back as the same dict.

`data_file` and `content_history_file` are storage-layer keys that had been
living in the family's config dict. They mean nothing in cloud mode. The store
owns them; they stay in `config.yaml` for compatibility and nothing else reads
them.

`store.py` and `config.py` are now the only files under `dinkydash/` that open
a file. That is the invariant to keep: a read anywhere else is a caller cloud
mode would have to fork.

### Sign-up

*Built in DIN-41.* One form does both jobs. A new address and a returning one post the same field to
`/login`, get the same page back, and are told apart behind that answer — two routes or two buttons
would publish which addresses already have an account, which is the one thing that page exists to
hide. What differs is only what lands in the mailbox, and whoever opens that mailbox already knows.

**The family is created when the link is clicked.** This was the open question and it is worth
writing down, because the simpler design is the other one. A `families` row starts the 14-day trial,
and the worker calls Anthropic daily for every family that is not lapsed — so a POST that created
one would let a script turn free sign-ups into a real and rising bill with no card behind it and
nothing to charge back. Creating on the click instead means an unverified sign-up costs **one
`login_tokens` row and one email**: no trial, no API call, and no second cleanup job, because the
sweep that already deletes expired tokens is the cleanup. It also makes "signing in through the link
*is* email verification" true of sign-up as well — otherwise a family exists for an address nobody
has proved they can read.

That is a rate limit's worth of protection and not a cap. The cap is the **global spend breaker**,
which is Phase 2 and still to come. A CAPTCHA is deliberately last: it puts a third-party script on
the page where a parent types their email, and friction on the one conversion step that matters, so
it waits until abuse actually appears.

**The cost was a schema change, and it bought one table rather than two.** `login_tokens.user_id` is
now nullable, with an `email` column beside it and a CHECK that exactly one of the two is set. A
separate `signup_tokens` table would have needed its own single-use `UPDATE`, its own expiry, its own
sweep and its own rate limit — and single use is the property everything else rests on, so a second
copy of that statement is a second thing to keep right. Both kinds of token prove the same thing;
only what happens next differs, and that branch lives in one place in `accounts.consume_link`.

**A new family is seeded rather than empty.** `config.starter_config()` is the same invented
household `config.example.yaml` documents — two children, a dog, two chores, two countdowns, every
one of them there to be replaced. An empty board looks broken rather than empty. **No calendar URL,
not even an example**: an iCal address is a password in a URL, and one that worked would put somebody
else's appointments on a stranger's wall. The settings home says so while the board is still
untouched, which is `settings.looks_untouched` — no calendar and the default family name, a signal
that is equally true of a freshly cloned Pi, so it needs no mode check.

**Still open, and not this issue's:** the gap between the click and the first board. The worker's
next tick refreshes the calendars within five minutes, but the brief waits for `brief_time` on the
family's clock, so a 03:00 sign-up looks at a waiting screen until 06:00. PLAN.md's "**Generate now**
on signup" line under [Scheduling](#scheduling-cloud-mode) is what closes it, and it is a Phase 2
worker item — a web request must not call Anthropic.

### Three clocks, one setting

The board changes on three cadences, and until decision 11 only one of them was
anybody's choice:

| Clock | What it does | Today | Cost |
|---|---|---|---|
| The screen reload | Re-renders from what is stored: rolls the date over at midnight, picks up a config edit, shows a new brief | Every 5 minutes, hard-coded in `board.html` (every minute before the first run) | Nothing |
| The calendar refresh | Re-fetches every enabled feed, so a change made in Google Calendar reaches the wall | Once a day, inside the 6am run | A few HTTP requests |
| The daily brief | Asks Claude for the headline and the note | Once a day, at 6am | One API call |

The gap is the middle row. A dentist appointment added at 09:00 for 15:00 is
not on the board until tomorrow, because today's agenda is a slice of a window
fetched once at dawn. For a product whose category is "family calendar", that
is the complaint every competitor solved first.

**The requirement.** Two new keys in the config dict, so they exist in both
modes and migrate through `with_defaults` like everything else:

- `refresh_minutes` — how often the calendars are re-fetched. Offered in the UI
  as every 15 minutes, every 30 minutes, every hour, every 6 hours, once a day.
  **Default: every hour.**
- `brief_time` — when the daily brief is written, in the family's own
  timezone. **Default: `06:00`.**

One row under **This screen** on the settings home, reading "Calendars every
hour · brief at 06:00", with a page behind it holding the two controls.

What it deliberately is not:

- The brief stays **once a day**. Every extra call is real money in cloud mode,
  and "Rewrite now" already covers the manual case. A second daily brief is a
  lever for later, not a setting now.
- The screen reload is derived, not chosen: 5 minutes, or the refresh interval
  if that is shorter. A parent wants "how soon does a change show up", not a
  browser knob.
- Fetching more often than the provider updates buys nothing. Google's secret
  `.ics` feed is itself cached and can lag by hours; the help text says so, so
  "every 15 minutes" is not read as a promise.

**How each mode drives it.** `runner.run` splits into two operations —
`refresh_calendars` (fetch, merge, write the events into the stored payload,
stamp `calendars_fetched_at`) and `write_brief` (the Claude call, the history
record). A pure `due(config, payload, now)` in `dinkydash/` decides which of
the two is owed. Then:

```
single   */5 * * * *  generate.py --tick     # cron ticks often; the config decides
cloud    worker loop, every 5 minutes        # the same tick, over every family that is due
```

That is the "what drives the scheduler" gate from decision 2 doing exactly its
job, and nothing else differs between the modes. The old `0 6 * * *
generate.py` keeps working — a plain run is a refresh plus a brief — so nobody's
Pi breaks on upgrade; it just never sees a same-day change.

Two things fall out for free. A brief that fails at 06:00 is retried on the next
tick instead of leaving the board stale all day, which is the retry logic the
cloud pipeline needed anyway. And "Rewrite now" gains a cheaper sibling,
"Refresh calendars", which is what most people pressing it actually want.

### Repository layout

Built (as of #45):

```
dinkydash/                  # the engine — pure, no clock, no file reads
├── context.py              # ages, birthdays, countdowns, chore rotation
├── calendars.py            # iCal fetch, parse, recurrence expansion, merge feeds
├── prompt.py               # system + user prompt, note kinds, response schema
├── claude_client.py        # the API call, with structured outputs
├── generate.py             # orchestrator: config + date + events -> payload
├── board.py                # payload + config -> what the template renders
├── config.py               # the config dict: load, save, defaults, migrations, ids
├── history.py              # what the recent notes say, and how they trim (pure)
├── schedule.py             # due(config, payload, now) -> what a tick owes (pure)
├── store.py                # the six storage operations; FileStore, single mode
├── pgstore.py              # PostgresStore, cloud mode
├── db.py                   # the pool and the migration runner (cloud only)
└── runner.py               # the two halves of the day, over a store

migrations/                 # plain SQL, applied in order by migrate.py

web/
├── __init__.py             # create_app()
├── manifest.py             # the two home-screen manifests
├── routes/board.py         # the board and the preview harness
├── routes/settings.py      # the settings UI (one table drives every list section)
└── templates/              # board.html, preview.html, settings/*.html

tests/
website/                    # marketing site generator (unchanged)
```

Still to come:

```
dinkydash/store.py          # the storage seam: FileStore now, PostgresStore in cloud
dinkydash/schedule.py       # due(config, payload, now) — pure
web/models.py               # cloud mode only — families, users, generations
web/routes/                 # auth, billing, admin, the tokenised screen
worker/                     # the tick loop (cloud mode)
migrations/                 # plain SQL, applied in order
.python-version             # what App Platform's Python buildpack pins to
.do/app.yaml                # the App Platform spec: components, build command,
                            #   health check, pre-deploy migration job.
                            #   No secrets in it.
selfhost/                   # Pi and from-source docs
```

No `selfhost/` config loader: single and cloud mode both go through
`dinkydash/config.py`, which is the point of decision 10.

### The engine boundary

The single most important refactor. Done in #28; `dinkydash.generate` is now:

```python
def generate(config: dict, today: date, events: list, recent_notes: list = ()) -> dict
```

Events are fetched by the caller rather than by the engine, which is what keeps `calendars.py` the
only module that touches the network.

No `SCRIPT_DIR`, no `config.yaml` read, no JSON write, no `sys.exit`, no `date.today()` — the caller injects the date. This is what lets one code path serve a Pi and a multi-tenant scheduler, and it's what makes the engine testable.

### Screen URLs

Dropping the pairing code makes token length a UX constraint — a 32-character token cannot be typed on a TV remote.

- `app.dinkydash.co/s/<10–12 chars>` from an unambiguous alphabet (no `0`/`O`/`1`/`l`) — ~50 bits
- Rate-limit the route; enumeration is the only attack and it's slow
- Rotatable from the settings page, invalidating the old URL
- `noindex`, `Referrer-Policy: no-referrer`, and **no third-party requests from the page** — the
  font is self-hosted and every response carries `Referrer-Policy: no-referrer`, both done in
  Phase 0 (DIN-32), which is what closes the `Referer` path for the token.
- Display as a QR code as well, for tablets and phones

### URL map

The board template is shared; only the route that reaches it differs.

```
                        single                  cloud
/                       the board               → /settings if signed in, else /login
/login                  —                       ask for a link; `?t=` is the landing
/login/link?t=<token>   —                       spend the token, start the session
/logout                 —                       throw the session away
/settings/…             as today                as today, scoped to the session's family
/s/<token>              —                       the board
/preview                three sizes of /        under /settings, framing /s/<token>
/healthz                ok                      ok
/webhooks/stripe        —                       Stripe events
```

### Scheduling (cloud mode)

- Each family's timezone, `refresh_minutes` and `brief_time` live in its config; the worker
  selects on `config->>'timezone'` and friends through expression indexes.
- The worker ticks every **5 minutes**. Each tick refreshes calendars for every family whose
  `agendas.fetched_at` is older than its interval, and writes the brief for every family whose
  local clock has passed `brief_time` and has no generation for today.
- Synchronous Claude calls; a small thread pool for the fetches. At 1,000 families on the hourly
  default that is 17 fetches a minute and 1,000 API calls a day, spread across the timezones.
- ~~Fan out via the Batch API~~ — deferred; see the cost model and open questions.
- **"Generate now"** on signup — a new family sees their dashboard in seconds, not tomorrow
- Idempotency: unique on `(family_id, generated_for_date)`
- On failure: keep last-good payload, mark stale, retry on later ticks with backoff, email the
  parent after N consecutive failures
- **The worker pings a dead-man's switch every tick.** A worker that quietly stops is the one
  failure that hits every family at once, and nothing else in this plan would notice.

### Cost model

Roughly 2,500 input / 350 output tokens per family per day:

| Model | Per family/month | With Batch API (−50%) |
|---|---|---|
| Haiku 4.5 | ~$0.13 | ~$0.07 |
| Sonnet 5 | ~$0.39 | ~$0.19 |
| Opus 5 | ~$0.64 | ~$0.32 |

How that relates to the price is the strategy document's business. What matters here: on Haiku —
the default — the Batch discount is a few cents a family a month, bought with a second pipeline
(submit, poll, match results, fall back to a synchronous call by 06:00). **Not in the MVP.** It
earns its complexity if the model moves to Sonnet.

Three notes:

- **`claude_model` and `max_tokens` are per-family keys** in the config dict, editable today under
  Settings → Family & system. In cloud mode the worker ignores them and uses the platform's model,
  or a family picks Opus on the flat plan. That is a billing gate, so it is allowed; the field
  hides in cloud mode.
- **Sonnet 5 runs adaptive thinking by default**, which eats into `max_tokens` and can truncate
  the JSON. Set `thinking` explicitly before moving off Haiku.
- ~~Switch to structured outputs~~ — done in #28; there is no JSON-repair loop to delete.

### Data model sketch

Config is one document, not five tables. Nothing in the product ever asks which
families have a child born in March, so a table each for people, pets, chores,
dates and calendars buys five sets of CRUD code and no answers. Real columns are
for what the *platform* queries or writes; the parent's own settings stay in the
dict the engine already takes.

```
families         id, plan, status, trial_ends_at, stripe_customer_id,
                 screen_token, screen_token_rotated_at,
                 config (jsonb)     -- the same dict config.yaml holds
users            id, family_id, email, last_login_at
login_tokens     id, user_id, token_hash, expires_at, used_at
agendas          family_id (pk), events (jsonb), fetched_at, statuses (jsonb)
                                    -- the fetched window; overwritten every refresh
calendar_health  id, family_id, calendar_id, last_fetch_at, last_fetch_status,
                 consecutive_failures    -- calendar_id is the id inside config
generations      id, family_id, generated_for_date, generated_at, status,
                 brief (jsonb), input_tokens, output_tokens, cost_cents,
                 model, error       -- unique (family_id, generated_for_date)
content_history  id, family_id, date, headline, note, note_kind
```

Four notes:

- **The scheduler selects on `config->>'timezone'`.** An expression index on
  that path is as fast as a column and leaves no second copy to drift.
- **`calendar_health` is keyed on the calendar's config id**, which exists
  precisely because list items now carry stable ids. Fetch state is something
  the platform writes, so it does not belong in the parent's config.
- **Calendar contents never accumulate.** `agendas` holds one row per family
  and is overwritten on every refresh, and `generations.brief` holds only the
  model's words. So the retention question in Phase 5 has a short answer: the
  most calendar data ever stored about a family is one fourteen-day window.
- **A config change needs no migration.** `with_defaults` already migrates old
  shapes on load, and it runs in both modes.

What this gives up: no database constraints on config contents, and no SQL
across them without a jsonb query. Both are analytics conveniences, not product
needs, and jsonb answers them when they arise.

### Hosting and deployment

*Settled 7 September 2026 — decision 12.*

What has to run: the Flask app, one worker process, Postgres, TLS, and the
5-minute tick. Traffic is small — a screen reloading every 5 minutes is 288
requests a day, so 1,000 families is about 3 requests a second. The data is EU
consumers' calendars held by a German entity, so EU residency is a line worth
being able to write in the privacy policy.

**DigitalOcean App Platform in Frankfurt (FRA), with DigitalOcean Managed
Postgres, and Cloudflare in front.**

```
dinkydash-site app (exists)                 Managed Postgres cluster (FRA1)
├── site      service   gunicorn, HTTP      └── dinkydash
│              dinkydash.co     -> website.site
│              app.dinkydash.co -> web.create_app()
├── worker    worker    the 5-minute tick   Cloudflare — DNS, edge TLS, rate limits
└── migrate   pre-deploy job
     all three from the same checkout, no image
```

**One service, not two, and it is the one already running.** `dinkydash-site`
serves `dinkydash.co` today on a $5 instance. The board becomes a second
hostname on that same container, dispatched on the `Host` header, rather than a
second app. Two reasons, and neither is architectural taste:

- **It is the house pattern.** `qrpage.co` is one App Platform app, one `web`
  service, one container, marketing pages and application together, with a
  `PRE_DEPLOY` migration job. `abc-league` is one service answering on two
  domains. Both work. A shape that is running in this account beats a shape
  argued from first principles.
- **The saving is real and the cost is not.** A second service is $5/month; a
  second *app* for staging is another $10. What separation would buy — a
  marketing container holding no secrets, and a board crash that cannot take
  the ranked pages down — is worth having, but not worth $180 a year before
  there is a single paying family. Revisit when there is revenue to protect.

**`site`, not `web`.** Renaming an App Platform component destroys and recreates
it, and the name is not worth an outage on the pages that rank. The component
serving both hostnames keeps the name it has.

**`wsgi.py` is the seam**, and it exists: it reads the `Host` header and hands the
request to one app or the other. Unknown hostnames get the *site*, never the board —
App Platform's health check arrives on an `.ondigitalocean.app` name that is in no
spec, so it has to answer, and the site is the half that holds no family's data.
`app.py` is untouched; a Pi never loads any of this.

**The subdomain stays, and it is what makes merging easy.** `app.dinkydash.co`
costs nothing: App Platform attaches many domains to one app, which is what
`abc-league` already does. Keeping it means both Flask apps go on owning `/` —
`website/site.py` says plainly why they are separate apps — so nothing in
either URL map has to move. It also keeps the Cloudflare cache rule simple:
cache the marketing host, never cache the board host. Sharing one hostname
would make that a per-path allowlist, and a mistake there serves one family's
board to another.

**No Dockerfile, and no Compose file.** App Platform's Python buildpack reads
`.python-version` and `requirements.txt` and runs whatever `run_command` each
component declares, so `site`, `worker` and the migration job are one checkout
with three commands. That is decision 2's "one artefact" argument holding in
the only form that ever mattered — one codebase — without a container runtime
in the middle of it.

qrpage.co already deploys to this platform exactly this way, `PRE_DEPLOY`
migration job and all, so this is a shape known to work in this account rather
than one read off a documentation page.

**One wrinkle the buildpack creates.** It installs `requirements.txt`, which is
deliberately the *smaller* list — no Postgres driver and no production WSGI
server, because `deploy_to_pi.sh` installs that same file onto a Pi that needs
neither. So the app spec carries a build command:

```yaml
build_command: pip install -r requirements-cloud.txt
```

`requirements-cloud.txt` pulls in `requirements.txt` and adds `psycopg`,
`psycopg-pool` and `gunicorn`.

**Self-hosting is untouched by any of this.** It is what it always was: clone,
virtualenv, `pip install -r requirements.txt`, and a cron line calling
`generate.py --tick`. `deploy_to_pi.sh` does exactly that, and nothing about
the hosted build reaches it.

**Region and residency.** App and database both in Frankfurt, so the calendar
data never leaves the EU and sits in the same country as the entity holding it.
Amsterdam (AMS3) is the equivalent fallback if any component turns out to be
missing in FRA1 — check the availability matrix when provisioning; the choice
between the two is not load-bearing.

One thing the switch away from Hetzner costs: **DigitalOcean is a US company**
with EU data centres, where Hetzner is a German entity. That means signing
DigitalOcean's DPA with standard contractual clauses and naming them plainly in
the sub-processor list. Paperwork, not a blocker, but it belongs in Phase 5
rather than being discovered there.

**The database.** The cheapest single-node cluster — 1 GiB RAM, 10 GiB disk,
$15.15/month — carries the first few thousand families. Four things it changes
in the app:

- `sslmode=require`, against DigitalOcean's CA certificate. `DATABASE_URL`
  carries it; nothing else in the app needs to know.
- **Connection limits are small** on the cheap node — **22**, and that is the
  whole cluster (25 per GiB of RAM, less 3 reserved for maintenance). Gunicorn
  workers plus the tick worker would exhaust it by accident, and the failure is
  a 500 on the board, not a slow page. **Settled: both, with a division of
  labour** — see [Connection pooling](#connection-pooling) below.
- Daily backups and 7-day point-in-time recovery are on by default and are
  theirs. **The restore drill is still ours** — see Phase 6.
- **One database, `dinkydash`, and no staging** until there is a paying family to protect.
  Staging was two more components and a second branch to keep green, for a product with no
  customers. `dinkydash_staging` is a line to add to this file the day losing production
  costs money, not before.

#### Connection pooling

*Settled 7 September 2026, after reading how KeepTheScore does it.*

**DigitalOcean's own connection pool (their hosted PgBouncer) in transaction
mode makes exhaustion impossible; a small `psycopg_pool` in each process makes
the common case fast.** One decides safety, the other decides speed, and
getting the second one wrong then costs latency rather than an outage.

```python
pool = ConnectionPool(
    os.environ["DATABASE_URL"],      # DigitalOcean's pool, transaction mode
    min_size=1, max_size=3,
    configure=lambda conn: setattr(conn, "prepare_threshold", None),
)
```

**Why not the app-side pool alone.** Web and worker is two processes, not the four
the staging plan would have made — but 22 connections is still the whole cluster, and
the migration job and a `psql` window both want one. The arithmetic is tight enough
that a third gunicorn worker tips it over. PgBouncer
turns "connection refused" into "wait a moment", and that change of failure mode
is the whole reason it is there.

**Why not the DigitalOcean pool alone.** KeepTheScore is the natural experiment:
same host, same managed Postgres, pool on the DigitalOcean side, no client-side
pool, and `db.close()` on every request — so every request pays a fresh TCP and
TLS handshake to the pool endpoint. It has never broken, and nobody has ever
measured what it costs. Filed as LBD-685. We get the client-side half for free
by writing it once, before `PostgresStore` exists.

**Transaction mode, not session mode.** DigitalOcean recommends session mode for
applications that use prepared statements, advisory locks or listen/notify. We
use none of them — the daily idempotency is a unique constraint on
`(family_id, generated_for_date)`, not a lock. Session mode holds a backend
connection for a client's whole session, so it barely multiplexes and the
arithmetic above comes straight back.

**`prepare_threshold=None`, everywhere, including local development and CI.**
psycopg 3 prepares a statement server-side once it repeats, and under
transaction-mode pooling the next execution can land on a different backend
connection: `prepared statement "..." does not exist`, intermittently, under
load, after everything looked fine in testing. This is the one line that differs from
KeepTheScore, which is on psycopg2 and never auto-prepares — their clean record
does not transfer. Setting it unconditionally means one behaviour rather than
two. The cost is nil at this query volume.

**Two connection strings.** `DATABASE_URL` (pooled) for `web` and `worker`;
`DATABASE_URL_DIRECT` (the cluster, port 25060) for the pre-deploy migration job
and for `pg_dump`. DigitalOcean documents that `pg_dump` errors against a
transaction-mode pool, and `CREATE INDEX CONCURRENTLY` cannot run inside a
transaction block. Both are named in `.do/app.yaml`. KeepTheScore has exactly
this shape already, arrived at by accident and written down as a naming quirk.

**Always `with pool.connection() as conn:`.** The connection returns to the pool
on the error path too. Skipping that is how KEEPTHESCORE-28A happened next door:
a view raised, the connection was never released, and the next request on that
thread got a dead one.

**Deploy.** Push to `main`; App Platform's Python buildpack builds the checkout
and rolls the components out with a health check on `/healthz`. Migrations run as a
**pre-deploy job** in the app spec, so the schema is always ahead of the code
that needs it and a failed migration fails the deploy instead of half-updating
a live app. GitHub Actions keeps running the test suite — App Platform deploys,
it does not gate. There is no staging app; see the database section. The Pi keeps
`deploy_to_pi.sh`; a self-hoster is not a tenant.

**Nothing here needs the dashboard.** The one thing `doctl` cannot do is create an app
with a GitHub source, because an API token carries no GitHub OAuth session. `dinkydash-site` already has one, so adding the board's hostname, the `worker` and
the migration job is `doctl apps update` against a spec in this repo.

**The app spec lives in the repo** as `.do/app.yaml`, so the components,
instance sizes, health checks and the pre-deploy job are reviewed like code.
**No secrets in it.** App Platform's encrypted environment variables are set
with `doctl` or in the dashboard, and the spec references them by name.

**Cloudflare** gives DNS, TLS at the edge, a rate-limiting rule on `/s/*` and
`/login` with no dependency in the app, and — once DIN-27 moves the marketing
pages onto the app — a cache in front of pages that currently cost nothing to
serve. `dinkydash.co` is on DNSimple today with the apex pointing at GitHub
Pages, so this is a nameserver move and an afternoon of re-entering records,
not a toggle.

> **The cert gotcha.** App Platform issues its own Let's Encrypt certificate
> for a custom domain and validates it through the CNAME. A proxied
> (orange-cloud) Cloudflare record breaks that validation. Add the domain in
> App Platform with the record **unproxied**, wait for the certificate, then
> turn the proxy on and set Cloudflare's SSL mode to **Full (strict)**.

**Not Cloudflare Workers**, though the tooling is to hand. It would be a
rewrite of a Flask app that leans on ruamel, icalendar and a long-running
worker. Decision 1 already answered that.

**What it costs.** Two $5 instances (1 vCPU, 512 MiB each — the app is
I/O-light) plus the $15.15 database is **about $25/month** for production.
Staging adds two more $5 components and shares the cluster, so call it $35 all
in. Verified against DigitalOcean's pricing pages on 7 September 2026.

**What was considered and dropped.** One Hetzner box in Falkenstein — cheaper
(about €5 a month) and a German entity. It loses on time: a box means SSH
hardening, a firewall, Caddy, a process manager, credentials in CI and a deploy
key, before anything of the product exists. Render in Frankfurt is the same
shape as the choice made and was close to a coin toss. Neither is hard to
leave: the app is a Python checkout with a `run_command`, so moving is an
afternoon, not a migration.

**Inside the app:**

- `psycopg` (v3) and plain SQL. Six tables and one jsonb document do not need
  an ORM; a forty-line runner applies `migrations/*.sql` in order and records
  each in a `schema_migrations` table. One new dependency rather than three —
  plus `psycopg_pool` if the app-side pool is the answer to the connection
  limit above.
- Gunicorn with a handful of workers. The app is I/O-light and the worker is a
  separate process, so there is nothing to tune — but see the connection limit.
- `/healthz` for the uptime check and as App Platform's readiness gate.
- Sentry is already connected; the worker component gets the same DSN.
- Secrets are App Platform encrypted environment variables —
  `DINKYDASH_SECRET_KEY`, `DATABASE_URL`, `ANTHROPIC_API_KEY`, the Stripe keys,
  the email key. Cloud mode refuses to start if any is missing.

---

## Bugs to fix before multi-tenancy

These are latent on a single Pi and actively harmful hosted.

**Fixed in #28:**

1. ~~**`generate.py:119` sorts events by formatted string.**~~ `events.sort(key=lambda e: e["date"])` sorted `"Friday, August 15 at 03:30 PM"` alphabetically by weekday name, so today's 8:30am school run could land after next Tuesday. Now sorted on `(date, all_day, start)` in `calendars.py`.
2. ~~**`date.today()` / `datetime.now()` use server local time.**~~ On a UTC host a family in Auckland got the wrong day. The engine now takes an injected date, from `config_module.today_for(config)`.
3. ~~**`calendar_filter_emails` requires all listed emails as `ATTENDEE`s.**~~ Most personal Google Calendar events have no `ATTENDEE` property at all, so it silently returned zero events. Dropped on load, with a warning; multiple calendars replaces it. Since brought back the right way round as a per-calendar `shared_with` list: any one address is enough, `ORGANIZER` counts as well as `ATTENDEE`, **Check this link** says when it matches nobody, and a legacy `calendar_filter_emails` now migrates onto the migrated feed instead of being dropped.
4. ~~**No tests.**~~ 157 of them, in under a second.

**Also fixed, found while settling decision 10:**

5. ~~**The settings UI addressed list items by position.**~~ `items[int(item_id)]`, so removing anyone renumbered everybody below and an open edit form silently pointed at the wrong person. Items now carry stable ids.

**Still open:**

6. **Stale `.env` keys.** `DATABASE_URL`, `SECRET_KEY`, `UPLOAD_FOLDER`, `MAX_CONTENT_LENGTH` are leftovers from an abandoned plan. No code reads any of them, so removing them changes nothing — but `.env` is not in git, so each copy has to be edited where it lives: the main checkout, and the Pi, whose `.env` `deploy_to_pi.sh` no longer overwrites. There is still no `.env.example`.
7. **No CI.** The suite runs in under a second and nothing runs it on push.
8. ~~**A failed fetch puts the secret URL in the error text.**~~ Fixed in DIN-32. `calendars._why` reduces a `requests` failure to a category and a status code, leaving out the host as well as the path, and the parse error is scrubbed too — a parser quotes the line it choked on, which is an appointment. Tested.
9. **`generated_at` is the server's clock.** `generate.py` stamps `datetime.now().astimezone()` and the settings home prints `stamp[11:16]` as "written 06:02". On a UTC host that is the wrong time for every family. Stamp in UTC; render in the family's timezone.
10. **`describe_feed` falls back to `date.today()`.** Never reached — the settings route passes the date — but it is the one clock left inside `dinkydash/`.
11. **No CSRF protection on any form.** Harmless with no accounts; the moment a session exists, a page elsewhere can submit "Rewrite now" or a delete on the parent's behalf. Every POST needs a token in cloud mode.

---

## Small jobs, big return

Each of these is under an hour, needs no database, and ships to the Pi as well as the cloud. Do them before anything in Phase 1.

1. **CI.** A GitHub Actions workflow that runs `pytest` on push and pull request; a `gitleaks` step beside it; push protection switched on in the repo settings. About twenty lines and one toggle.
2. **`.env.example`** — one line: `ANTHROPIC_API_KEY=`.
3. **Pin `requirements.txt`.** An unpinned dependency in an app holding other families' calendars is the supply-chain decision CLAUDE.md warns about, made by omission.
4. **Rotate the Anthropic key.** Five minutes, no code, overdue. Edit it on the Pi in place — `deploy_to_pi.sh` no longer copies `.env`.
5. ~~**Self-host Nunito.**~~ Done in DIN-32 — one variable font per subset in `web/static/fonts/`, and its own copy in `website/static/`. Removes a third-party request from every screen, a GDPR sub-processor (a Munich court ruled against dynamically loaded Google Fonts in 2022), the `Referer` path for screen tokens, and it makes a Pi's board render the same when the internet is down.
6. ~~**Scrub the URL out of `FeedError`**~~ (bug 8). Done in DIN-32.
7. ~~**`Referrer-Policy: no-referrer`**~~. Done in DIN-32, on every response rather than two templates, so it covers redirects and errors too.
8. ~~**`/healthz`.**~~ Done in DIN-32. Returns `ok` and the git SHA from the environment, and deliberately reads no config and no database.
9. **`generated_at` in UTC**, rendered in the family's timezone (bug 9).
10. ~~**A `Dockerfile`.**~~ Dropped on 7 September, having been built and then removed. App Platform's Python buildpack needs none, and Docker was machinery with nothing here to earn it. `.python-version` and a `build_command` in the app spec are what replaced it *(DIN-30, cancelled)*.

---

## Phases

Critical path is 0 → 1 → 2 → 3. Phases 4–6 can run alongside 3. Nothing ships without 5.

### Phase 0 — Foundations

- [x] Restructure into the monorepo layout above *(#28)*
- [x] Refactor the engine to `generate(config, today, events, recent_notes) -> dict` *(#28)*
- [x] Fix the five issues listed above; add tests around date/timezone, calendar parsing, chore rotation *(#28, #29)*
- [x] Update the Claude model; switch to structured outputs *(#28 — `claude-haiku-4-5` takes no `thinking` parameter, so leaving it unset is the explicit choice)*
- [x] The small jobs above: CI, `gitleaks`, push protection, `.env.example`, pinned requirements, key rotation *(DIN-16)*; self-hosted font, URL scrub, referrer policy, `/healthz` *(DIN-32)*.
- [x] **Decision 11, single-mode half:** `refresh_minutes` and `brief_time` in `DEFAULTS`; `runner.run` split into `refresh_calendars` and `write_brief`; a pure `due()`; `generate.py --tick`; the settings page under *This screen*; the board's reload derived from the interval; README cron line updated. Ships to the Pi at once and needs no database. *(DIN-17 for the engine and cron, DIN-18 for the page)*
- [x] Name the storage seam: `FileStore` gathering the six operations that exist today, and the settings routes, runner and board taking a store *(DIN-19)*
- [x] Postgres + plain-SQL migrations; CI running the suite against a Postgres service container *(DIN-31)*
- [x] Move DNS to Cloudflare and add the app records *(DIN-29)*. The apex now points at App Platform, not GitHub Pages — DIN-27 moved the marketing pages onto the app. The SendGrid records are in the same zone and validated: `em4199`, `s1._domainkey`, `s2._domainkey` and a `_dmarc` TXT at `p=none`. All four are **DNS-only** — a proxied CNAME answers as Cloudflare and domain authentication never passes.
- [x] Add the board to the existing `dinkydash-site` app and stand up Managed Postgres in Frankfurt; `app.dinkydash.co` live over TLS *(DIN-26)*. One service serving both hostnames, plus a `worker` and a `PRE_DEPLOY` migration job. No staging app — see the database section. Done on 8 September 2026: the board answers on `app.dinkydash.co`, the cluster is online in `fra1`, and the worker has been ticking every five minutes since 10:58 UTC. **Phase 0 is closed.**

**Done when:** the engine runs from a dict with an injected date, tests pass in CI on Postgres, a same-day calendar change reaches a Pi within its chosen interval, and `app.dinkydash.co` serves a hardcoded family over TLS.

### Phase 1 — Multi-tenant core

Some of this is already built for one family, in `web/routes/settings.py` (#28–#31): the five edited
lists with stable ids, add/label/enable/remove for iCal feeds with live validation on paste, and
timezone, family name and location under `/system`. The boxes below stay unticked because what is
missing is the multi-tenant half — a schema, auth, and scoping every read and write to a `family_id`.

- [x] Schema + migrations per the sketch above; `PostgresStore` behind the seam *(DIN-31)*
- [x] Magic-link auth: token hashed at rest, single use, 15-minute expiry, request endpoint rate-limited per address and per caller. Signing in through the link *is* email verification — there is no second step. *(DIN-38)*
- [x] Session hygiene: `Secure` (cloud only — a Pi serves plain HTTP), `HttpOnly`, `SameSite=Lax`; a CSRF token on every form, in **both** modes and with no switch to turn it off; cloud mode refuses to start without `DINKYDASH_SECRET_KEY` *(DIN-38)*
- [x] `fetch_feed` hardening before any stranger's URL is fetched: `https` only, redirects that cannot land on a private range, a response size cap beside the timeout *(DIN-33)*. The settings page's "Check this link" goes through the same function, so it is covered too. DNS rebinding is documented as still open.
- [x] **Sign-up: an address creates a family, a parent and a starting config — on the click, not on the submit** *(DIN-41)*. The same form as sign-in, and the same answer. `screen_token` and `trial_ends_at` are set at creation; see [Sign-up](#sign-up) for why the schema changed.
- [ ] Family setup wizard: people + DOBs, emoji/color avatars, pets, chores, special dates. **Half of this exists**: the five lists are editable at `/settings/…` and a new family arrives seeded, with a first-run card on the settings home saying the household is invented and pointing at the calendar and the timezone (DIN-41). What is missing is a guided multi-step path rather than a settings page.
- [ ] Multi-calendar management: add/label/enable/remove iCal feeds, with live validation on paste
- [ ] Per-provider help content — Google, iCloud, Outlook each expose iCal URLs differently
- [ ] Settings: timezone, family name, refresh cadence, screen URL display + rotation, account deletion. `claude_model` hidden in cloud mode.
- [x] Every read and write scoped to the family on the session; the hardcoded family id deleted *(DIN-39)*
- [ ] The URL map above: `/` redirects, `/login`, `/s/<token>`. **`/login` is done** (DIN-38, DIN-41). The other two are one change and not two: in cloud mode `/` is the board today, so it cannot start redirecting to `/settings/` until `/s/<token>` is where the board lives — and that route is Phase 3's first box. Doing half of it would leave the board unreachable.

**Done when:** two different families can be configured independently through the UI, and a request carrying the wrong family's id in a URL gets a 404, never a row. **Met by DIN-39**, and asserted in `tests/test_tenancy.py`.

### Phase 2 — Generation pipeline

- [ ] Worker process: the 5-minute tick over every family that is due, per the scheduling section
- [ ] Calendar refresh and daily brief as separate operations, each recorded (`agendas`, `generations`)
- [ ] "Generate now" and "Refresh calendars" for onboarding and manual use
- [ ] Per-family daily idempotency on the brief
- [ ] Per-family and **global** spend caps with a hard breaker
- [ ] Keep-last-good on failure; retry with backoff on later ticks; consecutive-failure tracking; parent notification after N
- [ ] Per-generation token/cost recording
- [ ] Dead-man's switch pinged from the tick, alerting if it stops

**Done when:** families in three timezones each get a correct dashboard at their own brief time, a calendar change reaches each screen within its interval, and killing the Anthropic key degrades gracefully instead of blanking screens.

### Phase 3 — The screen

- [ ] Public tokenized dashboard route, rate-limited at the edge, `noindex`, no referrer, no third-party requests
- [ ] Token rotation; QR code display
- [ ] Renderer to landing-page parity: person cards with ages, time-ordered agenda for today
- [ ] Staleness indicator when the brief isn't from today *(built for single mode in #28; confirm it reads the same from `PostgresStore`)*
- [ ] Offline tolerance and sensible cache headers
- [ ] Verify on the target surfaces: TV browser, old iPad, Pi kiosk

**Done when:** the live dashboard matches what the homepage mockup promises, on a real TV.

### Phase 4 — Money

- [ ] The trial lives in the app (`families.trial_ends_at`); Stripe enters only when the family chooses to pay. No Stripe customer for a family that never converts, and none of the "trial without a payment method" edge cases.
- [ ] Stripe Checkout at conversion + Customer Portal; webhooks verified by signature and idempotent on the event id
- [ ] Stripe Tax on from the first charge, with tax-inclusive prices *(see open questions)*
- [ ] Lapse behaviour *(see open questions; recommendation is freeze)*
- [ ] Dunning: trial ending, payment failed, subscription canceled
- [ ] Pricing page on the marketing site

**Done when:** a full signup → trial → paid → cancel cycle works end to end against Stripe test mode.

### Phase 5 — Legal & trust

- [ ] Privacy policy and ToS, forked from KeepTheScore
- [ ] Sub-processor list — Anthropic, DigitalOcean, Stripe, **SendGrid** (decision 13), Cloudflare. **Not Google Fonts**: self-hosted since DIN-32, and nothing on the board, the settings UI or the marketing site requests anything from them.
- [ ] **DigitalOcean's DPA signed, with standard contractual clauses.** They are a US company; the app and database sit in Frankfurt. Say both — where the data lives, and who the company is. Cloudflare needs the same treatment.
- [ ] Plain statement that calendar contents are sent to Anthropic for generation
- [ ] Say what SendGrid receives, which is **the email address and the login link, never the calendar**. The two disclosures are different in kind and should not be merged into one sentence: Anthropic sees a family's appointments, SendGrid sees only who is logging in.
- [ ] Data export and hard delete — the delete cascades through users, tokens, agendas, generations, history and calendar health; the Stripe customer record stays, as accounting requires
- [ ] Retention, with numbers: `agendas` is one overwritten row; `content_history` keeps 30 entries of the model's words; `generations` keeps token counts indefinitely and drops the `brief` column after 90 days; a lapsed family is deleted 90 days after lapse
- [ ] Cookie/analytics review

**Done when:** you could take money from an EU customer without wincing.

### Phase 6 — Ops

- [ ] Sentry (already connected) in both processes; uptime check on `/healthz`
- [ ] Generation-success dashboard; alerts on failure rate, calendar-fetch failures, spend breaker, Stripe webhook failures, and the dead-man's switch
- [ ] **The restore drill.** DigitalOcean takes daily backups and keeps 7 days of point-in-time recovery, so the *dump* is no longer a job. Restoring into a scratch database on a schedule still is, and an untested backup is a hope. Script it; run it monthly.
- [x] SendGrid wired up in the app *(decision 13)*. `dinkydash/mail.py` is the send (DIN-36) and `web/routes/auth.py` is its first caller (DIN-38), so this landed in Phase 1 as planned rather than here.
- [ ] Support inbox and a basic admin view (find family, inspect last generation, re-run)

**Done when:** you'd be comfortable going away for a weekend.

### Phase 7 — Launch

- [ ] Community-supported self-host docs around the from-source path and `deploy_to_pi.sh`; smoke-test single mode before release
- [ ] Private beta: ~10 waitlist families, two weeks
- [ ] Waitlist email sequence
- [ ] Swap Typeform links for real signup across homepage, FAQ, and all six satellite pages
- [ ] Show HN + r/selfhosted launch with the open-source story
- [ ] **Connect Google Search Console to the Ahrefs project** — currently only modelled estimates exist, and a paid funnel is about to be attached to traffic that can't be measured

---

## Explicitly out of scope for MVP

Photo uploads · Google/Apple OAuth · native or mobile apps · multiple dashboards per family · shared edit access between parents · themes and customization · weather and other widgets · template gallery · drag-and-drop layout editing · public/shareable dashboards · i18n · more than one brief a day.

---

## Open questions

*Which host? — closed on 7 September 2026. Decision 12: DigitalOcean App
Platform in Frankfurt, DigitalOcean Managed Postgres, Cloudflare in front.*

| Question | Blocks | Recommendation |
|---|---|---|
| EU VAT handling with Stripe direct? | Phase 4 | Stripe Tax from the first charge, using KeepTheScore's registration. Consumer prices in the EU are displayed VAT-inclusive, so Checkout is configured with tax-inclusive prices; what that does to the margin is the strategy document's line to update. |
| Lapse behaviour — blank, freeze on last-good, or degrade to a no-AI calendar? | Phase 4 | Freeze. The screen keeps its last board with a quiet "subscription ended" line; fetches and briefs stop. After 30 days the board is that line alone; after 90 the family is deleted, as the privacy policy will say. A blank kitchen screen is a bad churn experience, and a no-AI tier is a product decision for the strategy document, not a lapse state. |
| Batch API? | Phase 2 | Not in the MVP. Revisit when the model moves to Sonnet, or when the strategy document's cost line says the discount is worth a second pipeline. |
| How many Typeform waitlist signups? | Phase 7 sizing | Determines whether the private beta is viable and whether there's consent to email them |
