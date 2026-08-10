# DinkyDash Hosted MVP — Plan

*Last updated: August 10, 2026. Supersedes `HOSTING_ANALYSIS.md` (deleted — it predated both the AI generation feature and the July 2026 calendar-display repositioning, and its recommended stack and data model no longer matched the product).*

Companion to [STRATEGY.md](STRATEGY.md), which covers positioning, pricing anchors, and SEO. This document covers **how the hosted version gets built and launched**.

---

## The goal

Turn DinkyDash from a single-family Raspberry Pi app into a hosted product a non-technical parent can sign up for and have running on a kitchen screen in under five minutes — without giving up the open-source repo that feeds the funnel.

**Target:** ~$5/month or $39/year, 14-day trial, no card up front.

---

## Decisions (settled)

| # | Decision | Rationale |
|---|---|---|
| 1 | **Python + Flask + Postgres**, single boring host. Not Next.js/Supabase. | The engine, prompt, and template are already Python/Jinja. A TypeScript rewrite discards the differentiated part for no user-visible gain. |
| 2 | **Single public monorepo.** Hosted app and self-host are one codebase in two modes. | Simpler than any split-repo arrangement: no packaging, no version pinning, no drift. Self-hosting becomes "the same app with one family in it." |
| 3 | **No Google OAuth.** iCal URL paste only, with **multiple calendars per family**. | OAuth needs a Google verification review measured in weeks. Multiple feeds (one per parent) also replaces the broken attendee filter properly. |
| 4 | **Screen access via unguessable URL.** No pairing code. | Simplicity. Constrains token length — see Architecture below. |
| 5 | **Dashboard renders to landing-page parity.** Person cards + real time-ordered agenda. Emoji/color avatars, no photo uploads. | It's what waitlist signups were shown. Emoji avatars delete storage, moderation, EXIF-stripping, and image resizing from the MVP. |
| 6 | **14-day trial, no card up front.** Then $5/mo or $39/yr. No permanent free tier. | Every free family costs real Anthropic money daily, forever. |
| 7 | **Stripe direct.** | Reuse of existing KeepTheScore setup. See open questions re: EU VAT. |
| 8 | **Fork KeepTheScore's privacy policy and ToS** as the starting point. | Faster than drafting; same jurisdiction and entity. |
| 9 | **Self-hosting stays, community-supported only.** | See below. |

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
DINKYDASH_MODE=single   SQLite · auth off · billing off · one family · local cron
DINKYDASH_MODE=cloud    Postgres · magic links · Stripe · many families · worker + scheduler
```

The generation engine, dashboard template, CSS, and calendar handling are shared verbatim. Mode only gates auth, billing, storage backend, and how the scheduler is driven.

### Repository layout

```
dinkydash/
├── dinkydash/              # the engine — pure, no I/O side effects
│   ├── context.py          # ages, birthdays, countdowns, chore rotation
│   ├── calendar.py         # iCal fetch, parse, recurring expansion, merge feeds
│   ├── prompt.py           # system + user prompt construction
│   ├── claude.py           # API call, structured output, retry
│   └── generate.py         # orchestrator: config dict + date → payload dict
├── web/                    # Flask app (both modes)
│   ├── routes/             # dashboard, auth, config UI, billing, admin
│   ├── models.py
│   ├── templates/
│   └── static/
├── worker/                 # scheduler + generation runner (cloud mode)
├── selfhost/               # docker-compose, config.yaml loader, Pi docs
├── migrations/
├── tests/
└── website/                # marketing site generator (unchanged)
```

### The engine boundary

The single most important refactor. `dinkydash.generate` becomes:

```python
def generate(config: dict, today: date, recent_content: list) -> dict
```

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

At $5/mo, AI is 4–8% of revenue on Sonnet. Three notes:

- Config still pins `claude-sonnet-4-5-20250929` — update it
- **Sonnet 5 runs adaptive thinking by default**, which eats into `max_tokens: 2048` and can truncate the JSON. Set `thinking` explicitly.
- Switch to structured outputs (`output_config.format`) and the three-attempt JSON-parse retry loop can be deleted

### Data model sketch

```
families         id, name, timezone, location, plan, status, trial_ends_at,
                 stripe_customer_id, screen_token, screen_token_rotated_at
users            id, family_id, email, email_verified_at, last_login_at
login_tokens     id, user_id, token_hash, expires_at, used_at
people           id, family_id, name, date_of_birth, avatar_emoji, avatar_color,
                 interests, position
pets             id, family_id, name, type, avatar_emoji
chores           id, family_id, title, emoji, choices (jsonb), position
special_dates    id, family_id, title, emoji, month, day
calendars        id, family_id, label, ical_url, enabled, last_fetch_at,
                 last_fetch_status, consecutive_failures
generations      id, family_id, generated_for_date, generated_at, status,
                 payload (jsonb), input_tokens, output_tokens, cost_cents,
                 model, error       -- unique (family_id, generated_for_date)
content_history  id, family_id, date, fun_fact, daily_challenge, pet_corner, headline
```

---

## Bugs to fix before multi-tenancy

These are latent on a single Pi and actively harmful hosted:

1. **`generate.py:119` sorts events by formatted string.** `events.sort(key=lambda e: e["date"])` sorts `"Friday, August 15 at 03:30 PM"` alphabetically by weekday name. Today's 8:30am school run can land after next Tuesday. Sort on the underlying datetime.
2. **`date.today()` / `datetime.now()` use server local time.** On a UTC host a family in Auckland gets the wrong day. The engine must take an injected, timezone-aware date.
3. **`calendar_filter_emails` requires all listed emails as `ATTENDEE`s.** Most personal Google Calendar events have no `ATTENDEE` property at all, so this silently returns zero events. Remove it — multiple calendars replaces it.
4. **No tests.** A nightly unattended job that costs money needs at least date/timezone, calendar parsing, and chore rotation covered.
5. **Stale `.env` keys.** `DATABASE_URL`, `SECRET_KEY`, `UPLOAD_FOLDER`, `MAX_CONTENT_LENGTH` are leftovers from an abandoned plan.

---

## Phases

Critical path is 0 → 1 → 2 → 3. Phases 4–6 can run alongside 3. Nothing ships without 5.

### Phase 0 — Foundations

- [ ] Restructure into the monorepo layout above
- [ ] Refactor the engine to `generate(config, today, recent_content) -> dict`
- [ ] Fix the five issues listed above; add tests around date/timezone, calendar parsing, chore rotation
- [ ] Update the Claude model; set `thinking` explicitly; switch to structured outputs
- [ ] Postgres + migrations; CI running the test suite
- [ ] Staging deploy on `app.dinkydash.co` (apex stays on GitHub Pages)
- [ ] Enable GitHub push protection; add `gitleaks` pre-commit hook; ship `.env.example`
- [ ] Rotate the Anthropic API key (it has lived on a Pi and been rsynced)

**Done when:** the engine runs from a dict with an injected date, tests pass in CI, and staging serves a hardcoded family.

### Phase 1 — Multi-tenant core

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
