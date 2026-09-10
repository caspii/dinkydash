# DinkyDash Hosted MVP — Plan

*Updated 9 September 2026: main through PR #94, plus signup-link and calendar-date fixes (DIN-63/62).*

This is the engineering plan for the hosted app and its shared self-hosted codebase.
Positioning, pricing reasoning and launch strategy live in Linear on the DIN team.
[CLAUDE.md](CLAUDE.md) holds development rules; [doc/operations.md](doc/operations.md)
holds dated deployment records. The issue links below track remaining work.

## Current state and next work

The multi-tenant core is built: email signup/login, family-scoped settings, calendar
management, a tokenised screen, and a worker that owes the first brief on its next tick.
PR #85 delivered [DIN-45](https://linear.app/keepthescore/issue/DIN-45); PR #86 consolidated token issuance and URL construction,
serialized the per-address token limit, and fixed hosted HTTPS screen links.
PRs #87 and #89 added the calendar-provider and device guides ([DIN-14](https://linear.app/keepthescore/issue/DIN-14), [DIN-13](https://linear.app/keepthescore/issue/DIN-13)).
PR #91 implemented privacy-safe calendar publication ([DIN-46](https://linear.app/keepthescore/issue/DIN-46))
and removed generated text and malformed screen credentials from service logs ([DIN-47](https://linear.app/keepthescore/issue/DIN-47)).
PR #93 preserves explicit preview database overrides ([DIN-48](https://linear.app/keepthescore/issue/DIN-48))
and connects calendar fetches only to validated public addresses ([DIN-61](https://linear.app/keepthescore/issue/DIN-61)).
PR #94 preserves charged global usage after account deletion ([DIN-49](https://linear.app/keepthescore/issue/DIN-49))
and enforces the platform's model and token ceiling for hosted generation ([DIN-51](https://linear.app/keepthescore/issue/DIN-51)).
It also exports retained daily generations ([DIN-50](https://linear.app/keepthescore/issue/DIN-50)) and enforces trial expiry,
manual-action restrictions and the 30-day lapsed display period ([DIN-52](https://linear.app/keepthescore/issue/DIN-52)).
Public hosted calls to action now lead to signup/login ([DIN-63](https://linear.app/keepthescore/issue/DIN-63)),
and calendar-link descriptions require the family's date from their caller ([DIN-62](https://linear.app/keepthescore/issue/DIN-62)).

Todo is reserved for the hosted MVP: signup and trial use, payment/cancellation,
privacy and spending controls, basic monitoring/recovery, and real-device validation.
Optional features, promotion and additional operational tooling are Backlog.
Hosted readiness is still open. The remaining sequence is:

1. Complete Stripe conversion, subscription changes and cancellation before accepting payment ([DIN-53](https://linear.app/keepthescore/issue/DIN-53)).
2. Add liveness alerts and recovery checks ([DIN-54](https://linear.app/keepthescore/issue/DIN-54),
   [DIN-56](https://linear.app/keepthescore/issue/DIN-56)), and finish the trust work in Phase 5.
3. Verify real screens and run the small private beta ([DIN-58](https://linear.app/keepthescore/issue/DIN-58)), collecting feedback through the existing support email. Use observed setup
   problems to decide whether the existing settings flow needs a wizard.

A checked box below means that capability exists; linked follow-up defects remain
open until their own completion criteria pass. Deployment alone is not beta readiness.

## The goal

A parent can sign up, configure a family and calendar, and get a usable kitchen screen
within five minutes under normal operation. The same engine and board must continue to
work for a self-hoster without Postgres, email or billing services.

## Decisions (settled)

| # | Decision | Engineering consequence |
|---|---|---|
| 1 | Python, Flask and Postgres; plain SQL | Reuse the Python/Jinja engine and keep migrations in `migrations/`. |
| 2 | One public monorepo, two modes | Share the engine, settings and renderer; test both storage backends. |
| 3 | Multiple iCal feeds, no calendar OAuth | Paste provider URLs; each feed can have its own `shared_with` filter. |
| 4 | Screen access through a bearer URL | Current tokens are 12 random characters from an unambiguous alphabet; parents can rotate them. |
| 5 | Render the real board shown on the site | Agenda, chore turns, countdowns, headline and one written line. Person cards are not a parity requirement. Emoji avatars; no photo uploads. |
| 6 | A 14-day hosted trial, no card on signup | Store trial state in the app. Expiry enforcement is still [DIN-52](https://linear.app/keepthescore/issue/DIN-52). |
| 7 | Stripe for paid subscriptions | Create a Stripe customer at conversion. Checkout, portal and webhook handling remain [DIN-53](https://linear.app/keepthescore/issue/DIN-53). |
| 8 | Published privacy policy and terms based on the existing company documents | Disclosures must match implemented storage, deletion and outbound calls. Outstanding work is in Phase 5. |
| 9 | Community-supported self-hosting; MIT licence | Keep the from-source/Pi workflow operational with the user's own API key. |
| 10 | The config dict is the storage contract | Comment-preserving YAML in single mode; the same shape in Postgres `jsonb` in cloud mode. |
| 11 | Calendar cadence and brief time are family settings | Both modes use the same pure scheduling calculation. |
| 12 | DigitalOcean App Platform and Managed Postgres in Frankfurt, with Cloudflare | One web service, one worker and a pre-deploy migration job; no Dockerfile or separate staging app currently. |
| 13 | SendGrid for transactional email | `dinkydash/mail.py` sends login/signup mail; single mode does not need email credentials. |

## Architecture

### One app, two modes

| | Single | Cloud |
|---|---|---|
| Config and runtime storage | YAML and local JSON | Postgres, scoped to the family |
| Settings access | Local network, no authentication | Magic-link session |
| Board | `/` | `/s/<token>` |
| Scheduler | `generate.py --tick` from cron | `worker/`, one pass every five minutes |
| Model configuration | User's model, token limit and API key | Platform key, model and output-token ceiling ([DIN-51](https://linear.app/keepthescore/issue/DIN-51)) |
| Billing | None | Planned; [DIN-52](https://linear.app/keepthescore/issue/DIN-52) and [DIN-53](https://linear.app/keepthescore/issue/DIN-53) |

`create_app(store=None, *, pool=None)` accepts a store only in single mode and a
shared pool only in cloud mode. `web/family.py` constructs a request's cloud store from
the session's family; the screen route resolves its bearer token separately. A family
selector supplied in a form, query or header cannot override this scope.

### Where the config lives

`config.with_defaults` handles the same config shape in both modes. People, pets,
chores, special dates and calendars have stable item IDs, so deleting one item does
not retarget another open edit form. Phone edits preserve YAML comments in single mode.

Storage-path keys remain compatible with existing self-hosted configs; cloud storage
does not use those paths. New family settings belong in the config dict, while platform
lifecycle, token and usage data belong in database columns.

### The storage seam

Built in [DIN-19](https://linear.app/keepthescore/issue/DIN-19) and [DIN-31](https://linear.app/keepthescore/issue/DIN-31). `FileStore` and `PostgresStore` provide seven operations:

```
load_config / save_config
load_payload / save_agenda / save_brief
recent_notes / record_note
```

The runner, settings and renderer use that interface. A cloud payload combines the
latest brief in `generations` with the current calendar window in `agendas`. Agenda
and brief writes own separate fields. Config saves clear affected calendars and
coordinate with refresh publication using a short storage lock. A refresh made with
obsolete calendar settings is rejected before that tick can call the model ([DIN-46](https://linear.app/keepthescore/issue/DIN-46)).

### Sign-up

Built in [DIN-38](https://linear.app/keepthescore/issue/DIN-38), [DIN-39](https://linear.app/keepthescore/issue/DIN-39) and [DIN-41](https://linear.app/keepthescore/issue/DIN-41). `/login` accepts both new and returning addresses
and gives the same outward answer. Clicking the emailed link verifies the address;
only then is a new family, user and invented starting config created in one transaction.
A request for a link creates only a pending token and sends email.

`login_tokens` contains either a `user_id` or a signup `email`, enforced by a constraint.
Only the token hash is stored; links expire after 15 minutes and are consumed once.
The worker sweeps expired tokens. PR #86 shares issuance between the two cases and
serializes each subject's limit with a transaction-scoped advisory lock before checking it.

Cloud settings require a session. Cookies are Secure in cloud mode, HttpOnly and
SameSite=Lax. Every writing form carries a CSRF token in both modes. New families get
fictional starter entries and no calendar URL, plus links to replace the defaults.

### The first board

Built in [DIN-45](https://linear.app/keepthescore/issue/DIN-45) / PR #85. `schedule.brief_due` owes a brief whenever
`generated_for_date` is absent, including when a calendar-only payload exists.
The existing cloud worker attempts it on its next five-minute pass; a self-hoster's
cron does the same. Signup itself does not call the model or enqueue another job.

Failed first briefs remain due, subject to the hosted call cap. Later briefs follow
`brief_time` in the family's timezone. **Write it now** in settings becomes
**Rewrite now** after a successful first brief.

### The screen

Built in [DIN-42](https://linear.app/keepthescore/issue/DIN-42). `/s/<token>` grants access to the board and its manifest, never to
settings. Rotation immediately invalidates the old URL for subsequent requests.
Tokens are currently 12 random characters; [DIN-40](https://linear.app/keepthescore/issue/DIN-40)'s old 32-character requirement
has been reconciled with this implemented TV-entry decision.

Responses use `no-store`, `noindex` and `Referrer-Policy: no-referrer`. Fonts are
self-hosted, and the board makes no third-party asset requests. QR codes are encoded
locally with lazily imported `segno`. `web/urls.py` builds hosted links from an HTTPS
app origin; single mode retains its local HTTP URLs.

The app rate-limits invalid-token attempts. Additional Cloudflare edge hardening is Backlog ([DIN-40](https://linear.app/keepthescore/issue/DIN-40));
this document does not claim an edge rule is deployed. Access-log redaction covers
invalid, mistyped and encoded screen-token variants ([DIN-47](https://linear.app/keepthescore/issue/DIN-47)). Offline behaviour is deferred
under [DIN-60](https://linear.app/keepthescore/issue/DIN-60); weakening shared-cache headers is not the implementation plan.

### The spend breaker

Built in [DIN-43](https://linear.app/keepthescore/issue/DIN-43). Hosted worker ticks and manual rewrites share a budget charged before
the model call. `model_spend` records calls and reported tokens per family per UTC day.
The per-family cap uses an atomic upsert; the global cap is approximate under concurrent
calls and scales with the number of non-lapsed families. `global_model_spend` holds a
daily call total with no family identifiers; a database trigger adds every charged
attempt, including writes from older instances during deployment. Account deletion
removes the family's usage rows without refunding this total ([DIN-49](https://linear.app/keepthescore/issue/DIN-49)). Zero caps refuse generation.
Single mode uses the self-hoster's own key without this hosted budget.

The same budget applies the platform's `claude-haiku-4-5` model and 1,024-token output
ceiling before generation, ignoring legacy or crafted family overrides ([DIN-51](https://linear.app/keepthescore/issue/DIN-51)).
Budget refusal preserves the previous brief; calendar refreshes are not charged to
the model budget. Call counts and an output ceiling are not a currency-denominated cap.

### Three clocks, one setting

| Clock | Current behaviour |
|---|---|
| Screen reload | Every five minutes or the configured refresh interval, whichever is shorter; waiting screens retry every minute. |
| Calendar refresh | Due after `refresh_minutes`, default 60 minutes; chosen in settings. Provider-side caching can delay source changes. |
| Daily brief | First brief immediately due; subsequent briefs after `brief_time`, default 06:00, on the family's local day. Manual rewrites are separate attempts. |

`runner.refresh_calendars` and `runner.write_brief` are separate operations.
`schedule.due(config, payload, now)` receives an aware timestamp and decides what is owed.
`generate.py --tick` drives the same calculation in both modes. A plain `generate.py`
run still performs a refresh and brief for compatibility with older self-hosted cron jobs.

### Scheduling (cloud mode)

The worker reads family IDs with current access, visits them sequentially, and passes each
config and payload through the scheduling calculation. It does not currently select
due families through timezone expression indexes or fan calendar fetches into a thread pool.
One family's failure does not stop the pass; shutdown finishes the family in hand.

`generations` has one stored row per family/local date. Rewriting that row is storage
uniqueness, not a guarantee that concurrent callers cannot make two paid model calls.
Every hosted attempt must continue to pass through the budget.

Keep-last-good and retries on subsequent ticks exist. Persistent failure tracking,
backoff and parent notification are Backlog ([DIN-55](https://linear.app/keepthescore/issue/DIN-55)); the MVP worker heartbeat remains [DIN-54](https://linear.app/keepthescore/issue/DIN-54).
Trial access ends at `trial_ends_at`, using the database's timezone-aware clock ([DIN-52](https://linear.app/keepthescore/issue/DIN-52)).
The worker persists expired trials as lapsed; selection, manual feed checks, calendar refreshes
and model calls also enforce the deadline independently of that sweep. Legacy trials with no
deadline get one 14 days after account creation. Active paid accounts ignore their old trial dates.

For 30 days after access ends, the screen renders the last successful brief using its saved date,
so dates, chore rotations and countdowns stop advancing. Explicit settings edits and calendar
privacy invalidation still apply; no extra copy of family content is stored. At 30 days, or if no
successful brief exists, only the ended-access message is rendered. Settings, export and deletion
remain available. Reactivation clears the lapse timestamp and the screen resumes on reload.
This display cutoff does not delete stored content; retention sweeps remain DIN-57.

### The engine boundary

```
generate(config, today, events, recent_notes) -> payload dict
```

The caller supplies the date, fetched events and recent notes. Generation returns data;
the caller owns storage. The model call is isolated in `claude_client.py`, feed access
in `calendars.py`. Keep business calculations independent of clocks and files.
`describe_feed` requires the caller's date; settings supplies the family's date, with timezone-boundary checks in both modes ([DIN-62](https://linear.app/keepthescore/issue/DIN-62)).

### Repository layout

| Path | Current responsibility |
|---|---|
| `dinkydash/context.py`, `board.py`, `history.py`, `schedule.py` | Date/board calculations, recent-copy selection and scheduling |
| `dinkydash/calendars.py`, `prompt.py`, `claude_client.py`, `generate.py` | Feed handling and model generation |
| `dinkydash/config.py`, `store.py`, `pgstore.py` | Config migration and the two storage implementations |
| `dinkydash/accounts.py`, `mail.py`, `budget.py`, `db.py` | Account lifecycle, email, hosted call caps, pools and migrations |
| `dinkydash/runner.py`, `generate.py`, `worker/` | Shared operations, CLI/cron entry point and hosted loop |
| `web/` | App factory, session/family scope, URLs, routes, settings and shared renderer |
| `website/` | Marketing Flask app rendering Markdown through Jinja on request |
| `wsgi.py` | Dispatch to the marketing or app Flask instance by hostname |
| `migrations/`, `migrate.py` | Ordered plain-SQL migrations |
| `.do/app.yaml`, `.python-version`, `requirements-cloud.txt` | Hosted components, Python build and dependencies |
| `tests/`, `.github/workflows/test.yml` | Both-mode validation and CI |

Billing is future work, and admin functionality so far is the growth page at `/admin`
([DIN-37](https://linear.app/keepthescore/issue/DIN-37)); there is no planned ORM/model layer
or duplicate self-hosted config loader.

### URL map

| Route | Single | Cloud |
|---|---|---|
| `/` | Board | Settings when signed in, otherwise login |
| `/login`, `/login/link?t=…`, `/logout` | No sign-in needed | Request/consume a link and end a session |
| `/settings/…` | Local settings | Settings scoped to the session's family |
| `/s/<token>` | Not used | Bearer-token board |
| `/preview` | Three sizes of the local board | Authenticated preview of the tokenised board |
| `/admin` | Not used | Signups and activations by week, for addresses in `DINKYDASH_ADMIN_EMAILS` only |
| `/healthz` | Process health | Process health, not worker/database health |

Stripe routes are not implemented; their contract belongs to [DIN-53](https://linear.app/keepthescore/issue/DIN-53).

### Data model sketch

The SQL files in [migrations/](migrations/) are authoritative. The current tables are:

| Table | Stored data / current use |
|---|---|
| `families` | Config, screen token, account status, trial deadline, lapse and activation timestamps |
| `users` | Family membership and login address |
| `login_tokens` | Hashed single-use token, expiry, and either user or signup email |
| `agendas` | One overwritten calendar window and fetch status per family |
| `generations` | Per-day brief plus generation metadata and reported token usage |
| `content_history` | Recent generated copy, trimmed to the configured history length (at least 30) |
| `model_spend` | Daily per-family calls and reported tokens |
| `global_model_spend` | Daily call totals without family identifiers; survives deletion |
| `growth_by_day` | Daily signups and activations without family identifiers, kept by a trigger; survives deletion |
| `calendar_health` | Schema exists; recurring-failure tracking is not yet wired up |
| `schema_migrations` | Applied migration versions |

Model-written text can contain calendar details and currently remains in older
`generations.brief` rows until account deletion. Exports include all retained generations and the
separate recent rewrite history ([DIN-50](https://linear.app/keepthescore/issue/DIN-50)); retention sweeps remain
[DIN-57](https://linear.app/keepthescore/issue/DIN-57). A config change normally uses
`with_defaults`; platform schema changes use migrations.

### Hosting and deployment

The deployed shape is one `dinkydash-site` App Platform app in Frankfurt: `site`
serves the marketing and app hostnames through `wsgi.py`, `worker` runs the tick loop,
and a `PRE_DEPLOY` job runs migrations. Managed Postgres is in Frankfurt too.
Database location is not a claim that all outbound data stays in the EU; Anthropic
and SendGrid receive the data described in the published processor list.

Cloudflare DNS is in use, marketing pages run on App Platform, and GitHub Pages has
been retired. Edge rate limits are still an open task, not an assumed part of that move.
The spec is [`.do/app.yaml`](.do/app.yaml); secrets stay in encrypted platform environment
variables. The Python buildpack installs `requirements-cloud.txt`. No Dockerfile is needed.

Changes on main deploy through App Platform with a pre-deploy migration job and
`/healthz` readiness checks. GitHub CI checks pytest and gitleaks; the tests run with
Postgres 17 and without a configured database. The current branch rules and deployment
history are recorded in [doc/operations.md](doc/operations.md).

There is no separate staging app. Tests and restores must use an explicit isolated
database. The preview loads `.env` as defaults and preserves exported values, including
an explicit scratch `DATABASE_URL`; missing/empty database configuration fails before
Flask starts without printing the connection string ([DIN-48](https://linear.app/keepthescore/issue/DIN-48)).

#### Connection pooling

Use DigitalOcean's transaction-mode pool plus a small `psycopg_pool` in each process.
`DATABASE_URL` selects the pooled endpoint; `DATABASE_URL_DIRECT` is for migration
and backup operations that need the direct connection. Always return connections with
`with pool.connection() as conn:`. Pool limits still require capacity planning; pooling
does not make database exhaustion impossible.

`prepare_threshold=None` is set consistently in development, CI and cloud mode so
psycopg does not depend on a server-prepared statement surviving a backend switch.
PR #86 uses `pg_advisory_xact_lock` for token issuance: the lock belongs to the current
transaction. It does not introduce a session-scoped lock or require session pooling.

Managed backups are documented in operations; the independent restore drill remains
[DIN-56](https://linear.app/keepthescore/issue/DIN-56). Worker liveness alerts remain MVP work ([DIN-54](https://linear.app/keepthescore/issue/DIN-54));
Sentry instrumentation is Backlog ([DIN-35](https://linear.app/keepthescore/issue/DIN-35)).
Cloud startup validates the session key and database configuration; model/email failures
have their own runtime handling. Stripe credentials are not required before billing exists.

## Phases

The original phase numbers remain for existing references. Work is now ordered by the
readiness sequence above; the multi-tenant core does not need rebuilding.

### Phase 0 — Foundations

- [x] Shared engine, stable item IDs, timezone/event-ordering fixes and tests (#28, #29).
- [x] Both-mode CI, gitleaks, pinned requirements, environment example and key rotation ([DIN-16](https://linear.app/keepthescore/issue/DIN-16), [DIN-20](https://linear.app/keepthescore/issue/DIN-20)).
- [x] Separate refresh/brief clocks and settings; storage seam ([DIN-17](https://linear.app/keepthescore/issue/DIN-17), [DIN-18](https://linear.app/keepthescore/issue/DIN-18), [DIN-19](https://linear.app/keepthescore/issue/DIN-19)).
- [x] Postgres migrations and store contract tests ([DIN-31](https://linear.app/keepthescore/issue/DIN-31)).
- [x] Sanitised feed errors, no-referrer headers, self-hosted fonts and health endpoint ([DIN-32](https://linear.app/keepthescore/issue/DIN-32)).
- [x] Cloudflare DNS, dynamic marketing site, hosted web/worker deployment ([DIN-26](https://linear.app/keepthescore/issue/DIN-26), [DIN-27](https://linear.app/keepthescore/issue/DIN-27), [DIN-29](https://linear.app/keepthescore/issue/DIN-29)).

**Completion:** the shared engine and both stores are deployed and tested. Subsequent
privacy and readiness defects are tracked explicitly below.

### Phase 1 — Multi-tenant core

- [x] Schema, signup/login, session hygiene and family scoping ([DIN-31](https://linear.app/keepthescore/issue/DIN-31), [DIN-38](https://linear.app/keepthescore/issue/DIN-38), [DIN-39](https://linear.app/keepthescore/issue/DIN-39), [DIN-41](https://linear.app/keepthescore/issue/DIN-41)).
- [x] Multi-calendar add/label/enable/remove, per-feed sharing filters and live link checks.
- [x] Feed scheme, address, redirect and response-size checks ([DIN-33](https://linear.app/keepthescore/issue/DIN-33)).
- [x] Pin calendar connections to validated public IPs, preserving HTTPS hostname verification, redirect checks and size limits ([DIN-61](https://linear.app/keepthescore/issue/DIN-61)).
- [x] Editable family lists, timezone, family name, refresh cadence and seeded setup guidance.
- [x] Inline Google, iCloud and Outlook help in getting-started ([DIN-2](https://linear.app/keepthescore/issue/DIN-2)).
- [x] Standalone provider pages and screenshots ([DIN-14](https://linear.app/keepthescore/issue/DIN-14)).
- [x] Hide/reject self-hosting controls in cloud settings (PR #92).
- [x] Enforce platform model and token limits at every hosted generation entry point ([DIN-51](https://linear.app/keepthescore/issue/DIN-51)).
- [ ] Assess the need for a guided wizard from observed setup friction ([DIN-58](https://linear.app/keepthescore/issue/DIN-58)).

**Core completion met by [DIN-39](https://linear.app/keepthescore/issue/DIN-39):** two families can be configured independently, and
another family's item ID returns 404. Onboarding validation remains open.

### Phase 2 — Generation pipeline

- [x] Shared operations, five-minute worker, first-board scheduling and manual actions ([DIN-17](https://linear.app/keepthescore/issue/DIN-17), [DIN-28](https://linear.app/keepthescore/issue/DIN-28), [DIN-45](https://linear.app/keepthescore/issue/DIN-45)).
- [x] Separate agenda/brief persistence, one daily generation row, and reported token usage.
- [x] Per-family and approximate global call caps, including manual rewrites ([DIN-43](https://linear.app/keepthescore/issue/DIN-43)).
- [x] Keep-last-good rendering and retry on subsequent ticks.
- [x] Reject refresh publication after a calendar privacy/config change ([DIN-46](https://linear.app/keepthescore/issue/DIN-46)).
- [x] Preserve global spending across account deletion ([DIN-49](https://linear.app/keepthescore/issue/DIN-49)).
- [ ] Failure tracking, backoff and parent notification ([DIN-55](https://linear.app/keepthescore/issue/DIN-55); Backlog).
- [x] Remove the remaining implicit date fallback in feed description ([DIN-62](https://linear.app/keepthescore/issue/DIN-62)).

**Done when:** families in different timezones get correct boards and calendar updates;
failed providers preserve useful last-good output; retries and paid calls obey their bounds.

### Phase 3 — The screen

- [x] Token route, rotation, QR display, privacy headers and app miss-rate limit ([DIN-42](https://linear.app/keepthescore/issue/DIN-42)).
- [x] Hosted HTTPS links and shared URL policy (#86).
- [x] Real-board parity with the homepage and staleness indicator. No new person-card feature is required.
- [ ] Additional Cloudflare edge hardening ([DIN-40](https://linear.app/keepthescore/issue/DIN-40); Backlog).
- [ ] Render the already-configured person colours ([DIN-8](https://linear.app/keepthescore/issue/DIN-8); feature backlog).
- [ ] Verify TV, older iPad/tablet and Pi kiosk behaviour ([DIN-58](https://linear.app/keepthescore/issue/DIN-58)).
- [ ] Define offline behaviour while preserving credential/cache controls ([DIN-60](https://linear.app/keepthescore/issue/DIN-60); deferred).

**Done when:** the shared board works on the actual target devices, including the
agreed failure behaviour. Device-specific guides are published ([DIN-13](https://linear.app/keepthescore/issue/DIN-13));
the real-device checks remain [DIN-58](https://linear.app/keepthescore/issue/DIN-58).

### Phase 4 — Money

- [x] Store the trial deadline when a verified signup creates a family ([DIN-41](https://linear.app/keepthescore/issue/DIN-41)).
- [x] Enforce expiry, restrict manual actions, and render the agreed lapsed state ([DIN-52](https://linear.app/keepthescore/issue/DIN-52)).
- [ ] Checkout, Customer Portal, verified/idempotent webhooks, pricing and lifecycle notifications ([DIN-53](https://linear.app/keepthescore/issue/DIN-53)).
- [ ] Apply the agreed price/tax configuration and update processor disclosures when enabling Stripe ([DIN-53](https://linear.app/keepthescore/issue/DIN-53)).

**Done when:** signup → trial → paid → cancel passes in Stripe test mode. Trial
expiry is implemented; checkout, payment and cancellation still need that verification.

### Phase 5 — Legal & trust

- [x] Published privacy policy, terms, processor list and relevant disclosures beside calendar setup ([DIN-44](https://linear.app/keepthescore/issue/DIN-44)).
- [x] Account export/download and hard-delete actions, scoped to the signed-in family ([DIN-44](https://linear.app/keepthescore/issue/DIN-44)).
- [x] Include every retained historical generation in the export ([DIN-50](https://linear.app/keepthescore/issue/DIN-50)).
- [x] Keep generated family text and bearer credentials out of service logs ([DIN-47](https://linear.app/keepthescore/issue/DIN-47)).
- [ ] Verify DigitalOcean/Cloudflare agreement status and record private evidence ([DIN-59](https://linear.app/keepthescore/issue/DIN-59)).
- [ ] Implement and then disclose old-brief and lapsed-family retention sweeps ([DIN-57](https://linear.app/keepthescore/issue/DIN-57)).

**Done when:** disclosures match actual collection, retention, export and deletion,
and the recorded privacy findings are resolved. The presence of the two account buttons
alone does not close the phase.

### Phase 6 — Ops

- [x] Transactional email wired into signup/login ([DIN-36](https://linear.app/keepthescore/issue/DIN-36), [DIN-38](https://linear.app/keepthescore/issue/DIN-38)).
- [ ] Sentry for web, worker and applicable frontend errors, with sensitive-data filtering ([DIN-35](https://linear.app/keepthescore/issue/DIN-35); Backlog).
- [ ] Worker heartbeat and external health alerts, verified by a controlled failure ([DIN-54](https://linear.app/keepthescore/issue/DIN-54)).
- [ ] Repeatable restore into an isolated database, with a successful drill recorded ([DIN-56](https://linear.app/keepthescore/issue/DIN-56)).
- [x] Preserve explicit preview database overrides ([DIN-48](https://linear.app/keepthescore/issue/DIN-48)).
- [ ] Admin dashboard ([DIN-37](https://linear.app/keepthescore/issue/DIN-37)): signups and activations by week exist at `/admin`, behind `DINKYDASH_ADMIN_EMAILS` (migration 006, `dinkydash/growth.py`). Spend, trial status and calendar health, per the issue's triage, remain Backlog.

**Done when:** an operator can detect stopped/failed work, inspect useful metadata and
recover the application. A healthy `/healthz` response alone is insufficient.

### Phase 7 — Launch

- [x] Self-hosted getting-started/provider instructions and the Pi/from-source path exist.
- [x] Search Console and Ahrefs connection is marked Done in [DIN-3](https://linear.app/keepthescore/issue/DIN-3); ongoing account status is tracked there.
- [ ] Real-device checks, current self-hosted smoke test and the small private beta ([DIN-58](https://linear.app/keepthescore/issue/DIN-58)).
- [x] Replace hosted waitlist/form links with the actual signup/login page ([DIN-63](https://linear.app/keepthescore/issue/DIN-63)).
- [ ] Refresh launch dependencies, rewrite obsolete drafts, tag a release and execute the approved public launch ([DIN-25](https://linear.app/keepthescore/issue/DIN-25); Backlog).
- [x] Calendar-provider and device guides ([DIN-14](https://linear.app/keepthescore/issue/DIN-14), [DIN-13](https://linear.app/keepthescore/issue/DIN-13)).
- [ ] Embedded feedback widget/backend ([DIN-34](https://linear.app/keepthescore/issue/DIN-34); Backlog). MVP feedback uses the existing support email.

Beta invitations and public launch follow the readiness gates above. Launch copy,
waitlist communications and rollout decisions belong in Linear. [DIN-21](https://linear.app/keepthescore/issue/DIN-21) is Canceled;
[DIN-25](https://linear.app/keepthescore/issue/DIN-25) must record whether its remaining cleanup was completed or consciously waived,
rather than treating cancellation as evidence of remediation.

## Explicitly out of scope for MVP

Photo uploads, calendar OAuth, native/mobile apps, multiple dashboard layouts per
family, shared parent editing, a theme/template gallery, drag-and-drop layout editing,
i18n, and extra scheduled daily briefs. Light/dark themes and basic appearance settings
already exist and are not exclusions. Manual rewrites also already exist.

Weather ([DIN-24](https://linear.app/keepthescore/issue/DIN-24)) and photo/screensaver mode ([DIN-11](https://linear.app/keepthescore/issue/DIN-11)) remain deferred scope decisions.
Their issues must agree with the plan before either is promoted into the MVP.

Additional edge rules, Sentry instrumentation, the rest of the admin dashboard (spend,
trial status, calendar health), persisted retry backoff/parent notifications, a feedback
widget and public launch promotion are also Backlog. Existing redacted logs, bounded retries and support email
cover those needs for the MVP alongside the remaining liveness and recovery work.

## Open questions

| Decision / verification | Tracking |
|---|---|
| Implement the proposed 90-day brief-content and lapsed-family deletion periods before promising them | [DIN-57](https://linear.app/keepthescore/issue/DIN-57) |
| Account-specific Stripe price/tax setup before the first charge | [DIN-53](https://linear.app/keepthescore/issue/DIN-53) |
| Whether observed setup failures justify a multi-step wizard | [DIN-58](https://linear.app/keepthescore/issue/DIN-58) |
| Whether offline screen support merits local caching and how revocation behaves | [DIN-60](https://linear.app/keepthescore/issue/DIN-60) |

The host, storage backend, email provider, current screen-token shape and renderer
parity are settled. Batch generation remains deferred until a measured need justifies
a second processing path.
