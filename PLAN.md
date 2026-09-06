# DinkyDash Hosted MVP — Plan

*Last updated: September 5, 2026. Supersedes `HOSTING_ANALYSIS.md` (deleted — it predated both the AI generation feature and the July 2026 calendar-display repositioning, and its recommended stack and data model no longer matched the product).*

Companion to [STRATEGY.md](STRATEGY.md), which covers positioning, pricing anchors, and SEO. This document covers **how the hosted version gets built and launched**.

---

## The goal

Turn DinkyDash from a single-family Raspberry Pi app into a hosted product a non-technical parent can sign up for and have running on a kitchen screen in under five minutes — without giving up the open-source repo that feeds the funnel.

**Target:** $39/year (or $6/month), 14-day trial, no card up front. Full structure and reasoning in [STRATEGY.md](STRATEGY.md#pricing-structure-settled-september-2026).

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

### On self-hosting (decision 9)

The repo is the credibility wedge and the backlink engine — the Show HN / r/selfhosted launch is still untried, and it's the fastest available path from DR 11 to the DR 30 the wedge keywords need. "Free and open source" is also the only line on the competitor comparison tables that Mango Display and DAKboard cannot copy.

What gets cut is the **support commitment**, not the code:

> Self-hosting is community-supported. Docker Compose file is in the repo, bring your own Anthropic API key, issues welcome but unanswered.

This costs roughly zero hours. Realistically almost no parent completes the current self-host path anyway — it needs a terminal and an API key — so this loses a support queue, not customers.

**Revisit in six months.** If the HN launch produces real referring domains, it paid for itself. If it produces nothing, close the repo then, with data rather than a guess.

### Licensing

Currently MIT, and the website says "MIT-licensed and free forever" in two places.

**Staying MIT for now.** At this scale the realistic cloning risk is low and MIT is the friendlier launch story. If cloning becomes a concern, AGPL is the standard move here (Plausible, Cal.com both chose it) — self-host freely, but run it as a service and you must publish modifications. Relicensing is straightforward while there are no outside contributors, but it would require updating the marketing copy in the same pass.

---

## Architecture

### One app, two modes

```
DINKYDASH_MODE=single   config.yaml · auth off · billing off · one family · local cron
DINKYDASH_MODE=cloud    Postgres · magic links · Stripe · many families · worker + scheduler
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

### Repository layout

Built (as of #28):

```
dinkydash/                  # the engine — pure, no clock, no file reads
├── context.py              # ages, birthdays, countdowns, chore rotation
├── calendars.py            # iCal fetch, parse, recurrence expansion, merge feeds
├── prompt.py               # system + user prompt, note kinds, response schema
├── claude_client.py        # the API call, with structured outputs
├── generate.py             # orchestrator: config + date + events -> payload
├── board.py                # payload + config -> what the template renders
├── config.py               # the config dict: load, save, defaults, migrations, ids
├── history.py              # rolling record of recent notes, to avoid repeats
└── runner.py               # the one place that does I/O around the engine

web/
├── __init__.py             # create_app()
├── routes/board.py         # the board and the preview harness
├── routes/settings.py      # the settings UI (one table drives every list section)
└── templates/              # board.html, preview.html, settings/*.html

tests/
website/                    # marketing site generator (unchanged)
```

Still to come:

```
web/models.py               # cloud mode only — families, users, generations
web/routes/                 # auth, billing, admin
worker/                     # scheduler + generation runner (cloud mode)
migrations/
selfhost/                   # docker-compose and Pi docs
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
- `noindex`, no referrer leakage
- Display as a QR code as well, for tablets and phones

### Generation scheduling

- Each family stores an IANA timezone
- Hourly worker tick selects families whose local time just passed **04:30**
- Fan out via the **Batch API** (50% cheaper, and this is a textbook batch workload)
- Synchronous fallback if a batch hasn't landed by the family's 06:00 local
- **"Generate now"** on signup — a new family sees their dashboard in seconds, not tomorrow
- Idempotency: unique on `(family_id, generated_for_date)`
- On failure: keep last-good payload, mark stale, email the parent after N consecutive failures

### Cost model

Roughly 2,500 input / 350 output tokens per family per day:

| Model | Per family/month | With Batch API (−50%) |
|---|---|---|
| Haiku 4.5 | ~$0.13 | ~$0.07 |
| Sonnet 5 | ~$0.39 | ~$0.19 |
| Opus 5 | ~$0.64 | ~$0.32 |

At $6/mo, AI is 3–7% of revenue on Sonnet. Three notes:

- ~~Config still pins `claude-sonnet-4-5-20250929`~~ — now `claude-haiku-4-5`
- **Sonnet 5 runs adaptive thinking by default**, which eats into `max_tokens: 2048` and can truncate the JSON. Set `thinking` explicitly.
- Switch to structured outputs (`output_config.format`) and the three-attempt JSON-parse retry loop can be deleted

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
users            id, family_id, email, email_verified_at, last_login_at
login_tokens     id, user_id, token_hash, expires_at, used_at
calendar_health  id, family_id, calendar_id, last_fetch_at, last_fetch_status,
                 consecutive_failures    -- calendar_id is the id inside config
generations      id, family_id, generated_for_date, generated_at, status,
                 payload (jsonb), input_tokens, output_tokens, cost_cents,
                 model, error       -- unique (family_id, generated_for_date)
content_history  id, family_id, date, headline, note, note_kind
```

Three notes:

- **The scheduler selects on `config->>'timezone'`.** An expression index on
  that path is as fast as a column and leaves no second copy to drift.
- **`calendar_health` is keyed on the calendar's config id**, which exists
  precisely because list items now carry stable ids. Fetch state is something
  the platform writes, so it does not belong in the parent's config.
- **A config change needs no migration.** `with_defaults` already migrates old
  shapes on load, and it runs in both modes.

What this gives up: no database constraints on config contents, and no SQL
across them without a jsonb query. Both are analytics conveniences, not product
needs, and jsonb answers them when they arise.

---

## Bugs to fix before multi-tenancy

These are latent on a single Pi and actively harmful hosted.

**Fixed in #28:**

1. ~~**`generate.py:119` sorts events by formatted string.**~~ `events.sort(key=lambda e: e["date"])` sorted `"Friday, August 15 at 03:30 PM"` alphabetically by weekday name, so today's 8:30am school run could land after next Tuesday. Now sorted on `(date, all_day, start)` in `calendars.py`.
2. ~~**`date.today()` / `datetime.now()` use server local time.**~~ On a UTC host a family in Auckland got the wrong day. The engine now takes an injected date, from `config_module.today_for(config)`.
3. ~~**`calendar_filter_emails` requires all listed emails as `ATTENDEE`s.**~~ Most personal Google Calendar events have no `ATTENDEE` property at all, so it silently returned zero events. Dropped on load, with a warning; multiple calendars replaces it.
4. ~~**No tests.**~~ 157 of them, in under a second.

**Also fixed, found while settling decision 10:**

5. ~~**The settings UI addressed list items by position.**~~ `items[int(item_id)]`, so removing anyone renumbered everybody below and an open edit form silently pointed at the wrong person. Items now carry stable ids.

**Still open:**

6. **Stale `.env` keys.** `DATABASE_URL`, `SECRET_KEY`, `UPLOAD_FOLDER`, `MAX_CONTENT_LENGTH` are leftovers from an abandoned plan. No code reads any of them, so removing them changes nothing — but `.env` is not in git, so each copy has to be edited where it lives: the main checkout, and the Pi, which `deploy_to_pi.sh` rsyncs to. There is still no `.env.example`.
7. **No CI.** The suite runs in under a second and nothing runs it on push.

---

## Phases

Critical path is 0 → 1 → 2 → 3. Phases 4–6 can run alongside 3. Nothing ships without 5.

### Phase 0 — Foundations

- [x] Restructure into the monorepo layout above *(#28)*
- [x] Refactor the engine to `generate(config, today, events, recent_notes) -> dict` *(#28)*
- [x] Fix the five issues listed above; add tests around date/timezone, calendar parsing, chore rotation *(#28, #29)*
- [x] Update the Claude model; switch to structured outputs *(#28 — `claude-haiku-4-5` takes no `thinking` parameter, so leaving it unset is the explicit choice)*
- [ ] Postgres + migrations; CI running the test suite
- [ ] Staging deploy on `app.dinkydash.co` (apex stays on GitHub Pages)
- [ ] Enable GitHub push protection; add `gitleaks` pre-commit hook; ship `.env.example`
- [ ] Rotate the Anthropic API key (it has lived on a Pi and been rsynced)

**Done when:** the engine runs from a dict with an injected date, tests pass in CI, and staging serves a hardcoded family.

### Phase 1 — Multi-tenant core

Some of this is already built for one family, in `web/routes/settings.py` (#28–#31): the five edited
lists with stable ids, add/label/enable/remove for iCal feeds with live validation on paste, and
timezone, family name and location under `/system`. The boxes below stay unticked because what is
missing is the multi-tenant half — a schema, auth, and scoping every read and write to a `family_id`.

- [ ] Schema + migrations per the sketch above
- [ ] Magic-link auth, email verification required before first generation
- [ ] Family setup wizard: people + DOBs, emoji/color avatars, pets, chores, special dates
- [ ] Multi-calendar management: add/label/enable/remove iCal feeds, with live validation on paste
- [ ] Per-provider help content — Google, iCloud, Outlook each expose iCal URLs differently
- [ ] Settings: timezone, family name, screen URL display + rotation, account deletion

**Done when:** two different families can be configured independently through the UI.

### Phase 2 — Generation pipeline

- [ ] Worker process + hourly scheduler tick keyed on family local time
- [ ] Batch API fan-out with synchronous fallback
- [ ] "Generate now" for onboarding and manual refresh
- [ ] Per-family daily idempotency
- [ ] Per-family and **global** spend caps with a hard breaker
- [ ] Keep-last-good on failure; consecutive-failure tracking; parent notification after N
- [ ] Per-generation token/cost recording

**Done when:** families in three timezones each get a correct dashboard at their own 6am, and killing the Anthropic key degrades gracefully instead of blanking screens.

### Phase 3 — The screen

- [ ] Public tokenized dashboard route, rate-limited, `noindex`
- [ ] Token rotation; QR code display
- [ ] Renderer to landing-page parity: person cards with ages, time-ordered agenda for today
- [ ] Staleness indicator when the payload isn't from today
- [ ] Offline tolerance and sensible cache headers
- [ ] Verify on the target surfaces: TV browser, old iPad, Pi kiosk

**Done when:** the live dashboard matches what the homepage mockup promises, on a real TV.

### Phase 4 — Money

- [ ] Stripe Checkout + Customer Portal + webhooks
- [ ] Trial state machine; decide and implement lapse behavior *(see open questions)*
- [ ] Dunning: trial ending, payment failed, subscription canceled
- [ ] Pricing page on the marketing site

**Done when:** a full signup → trial → paid → cancel cycle works end to end against Stripe test mode.

### Phase 5 — Legal & trust

- [ ] Privacy policy and ToS, forked from KeepTheScore
- [ ] Sub-processor list — Anthropic, host, Stripe, email provider
- [ ] Plain statement that calendar contents are sent to Anthropic for generation
- [ ] Data export and hard delete
- [ ] Retention policy for calendar data and generation payloads
- [ ] Cookie/analytics review

**Done when:** you could take money from an EU customer without wincing.

### Phase 6 — Ops

- [ ] Sentry (already connected), uptime checks
- [ ] Generation-success dashboard; alerts on failure rate, calendar-fetch failures, spend breaker, Stripe webhook failures
- [ ] Database backups **with a tested restore**
- [ ] Transactional email provider wired up *(see open questions)*
- [ ] Support inbox and a basic admin view (find family, inspect last generation, re-run)

**Done when:** you'd be comfortable going away for a weekend.

### Phase 7 — Launch

- [ ] Docker Compose + community-supported self-host docs; smoke-test single mode before release
- [ ] Private beta: ~10 waitlist families, two weeks
- [ ] Waitlist email sequence
- [ ] Swap Typeform links for real signup across homepage, FAQ, and all six satellite pages
- [ ] Show HN + r/selfhosted launch with the open-source story
- [ ] **Connect Google Search Console to the Ahrefs project** — currently only modelled estimates exist, and a paid funnel is about to be attached to traffic that can't be measured

---

## Explicitly out of scope for MVP

Photo uploads · Google/Apple OAuth · native or mobile apps · multiple dashboards per family · shared edit access between parents · themes and customization · weather and other widgets · template gallery · drag-and-drop layout editing · public/shareable dashboards · i18n.

---

## Open questions

| Question | Blocks | Notes |
|---|---|---|
| How many Typeform waitlist signups? | Phase 7 sizing | Determines whether the private beta is viable and whether there's consent to email them |
| Transactional email provider? | Phase 1 (magic links) | A Customer.io MCP connector is configured but unauthorized — if that's the stack it needs authorizing |
| EU VAT handling with Stripe direct? | Phase 4 | Stripe Tax if already VAT-registered via KeepTheScore; otherwise this needs resolving before charging EU consumers |
| Lapse behavior — blank, freeze on last-good, or degrade to a no-AI calendar? | Phase 4 | Freeze-with-a-nudge is probably kindest; a blank kitchen screen is a bad churn experience |
