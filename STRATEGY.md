# DinkyDash Strategy

*Last updated: August 10, 2026. Positioning based on Ahrefs keyword/competitor research (July 2026) — see data summary below. Hosted-version build plan lives in [PLAN.md](PLAN.md).*

## The decision

DinkyDash is repositioned from "AI-powered family dashboard" to:

> **The digital family calendar for screens you already own.**
> A free, open-source alternative to Skylight and Hearth — turn any TV, tablet, or Raspberry Pi into a shared family calendar with a chore chart, countdowns, and an AI-written daily brief.

Two directions were considered and rejected:

- **Chores dashboard for families** — total "chore app" search demand is ~3K/mo (US) and the monetizable end (chores + allowance) is owned by funded fintechs (Greenlight: DR 73, 270K organic visits/mo; BusyKid). Chores stay in the product as a *feature* — Skylight itself markets "calendar + chore chart" as one purchase.
- **AI-first positioning** — "family dashboard" gets 60 searches/mo, "ai family assistant" 60/mo. No category language exists yet. AI stays as the differentiator and launch story, not the category.

## Why the calendar-display category

- The category is huge and brand-led: **"skylight calendar" = 338K US searches/mo** (KD 28). "digital calendar" 32K. Families pay $299–$699 for hardware plus $79–$108/yr subscriptions.
- The buyer-intent long tail is nearly uncontested:
  - "skylight calendar alternatives" — 2,500/mo, KD 1
  - "skylight calendar dupe" — 600/mo, KD 0
  - "hearth vs skylight" (both orders) — ~800/mo, KD 0
  - "does skylight calendar require a subscription" — 1,200/mo, KD 0
  - "diy skylight calendar" — 350/mo, KD 0
  - "best digital family calendar" / "best family calendar display" — 800/mo combined, KD 4
- **Proof it works at small scale: Mango Display** (software-only, DR 28) earns ~6.3K organic visits/mo, ranks #3 for "skylight calendar alternatives", and is cited in Google AI Overviews with the exact "no hardware required" angle.
- **Proof of the community route: DAKboard** — nearly all of its 16.8K visits/mo is its own brand name (11K searches/mo), built through the Raspberry Pi/DIY community. DinkyDash's open-source repo plays this role.

## Product model: one public monorepo, hosted SaaS as the business

1. **Open-source repo (now)** — the credibility wedge and top of funnel. Free, MIT, self-hosted, bring your own Anthropic API key. Feeds HN/Reddit launches, GitHub stars, and referring domains (dinkydash.co is DR 11 with 84 ref domains; needs ~DR 30 for the wedge terms).
2. **Hosted version (next)** — the business. Signup, family config form, paste one or more iCal URLs, per-family screen URL, central 6am generation in the family's own timezone, Stripe. Category-anchored pricing: **$5/mo or $39/yr**, 14-day trial, no card up front (vs Skylight Plus $79/yr, Hearth $9/mo). AI cost per family is $0.19–0.39/month. Collect emails via a waitlist link until it exists.

**Both ship from a single public monorepo.** The hosted app and the self-host build are one codebase in two modes, so self-hosting is "the same app with one family in it" rather than a second product to maintain. Billing and auth code being public is an accepted trade — the moat is the SEO position and the brand, not the source.

Self-hosting is **community-supported only**: Docker Compose in the repo, issues welcome but unanswered. This preserves the funnel and the one differentiator Mango Display and DAKboard cannot copy, at near-zero ongoing cost. Revisit in six months — if the HN launch produces real referring domains it paid for itself; if not, close the repo with data rather than a guess.

Explicitly skipped: monetizing self-hosting (license keys/paid repo) — keeps the audience filter, no recurring value capture. Also skipped for MVP: Google Calendar OAuth (verification review takes weeks; iCal paste ships now), photo uploads (emoji avatars instead), and a permanent free tier (every free family costs real AI money daily).

## Pricing anchors (verified July 2026)

| Product | Hardware | Subscription |
|---|---|---|
| Skylight Calendar 2 (15") | $299 | Plus $79/yr (optional) |
| Skylight Calendar Max (27") | $629 | Plus $79/yr (optional) |
| Hearth Display (27") | $699 ($599 promo) | $9/mo after first month |
| DAKboard (BYO screen) | — | Free tier; $5–8/mo |
| Mango Display (BYO screen) | — | Free tier; Pro $5.99/mo |
| **DinkyDash (BYO screen)** | — | **Free, open source (hosted tier $5/mo or $39/yr, 14-day trial)** |

## SEO plan

**Site:** dinkydash.co (static, GitHub Pages). Homepage repositioned around "digital family calendar for screens you already own."

**Satellite pages (shipped July 2026), targeting KD ≤ 5 buyer intent:**

| Page | Target keyword(s) | US vol/mo |
|---|---|---|
| /skylight-calendar-alternatives/ | skylight calendar alternatives, dupe | 3,100 |
| /skylight-calendar-subscription/ | does skylight require a subscription, subscription cost | 2,000 |
| /hearth-vs-skylight/ | hearth vs skylight, skylight vs hearth | 800 |
| /best-digital-family-calendar/ | best digital family calendar, best family calendar display | 800 |
| /diy-skylight-calendar/ | diy skylight calendar | 350 |
| /digital-calendar-and-chore-chart/ | digital calendar and chore chart | 250–1,100 |

**Later (free-tool playbook, à la KeepTheScore):** birthday countdown tool (4.1K/mo, KD 3), interactive/printable chore chart (13K/mo, KD 6), morning routine chart (350/mo).

**Channels beyond SEO:** Show HN / r/selfhosted / r/raspberry_pi launch (brand + backlinks), parenting subreddits where "cheaper Skylight" threads already rank, YouTube reviewers who compare calendar displays.

## Risks

- Head terms ("digital family calendar") are shopping-walled SERPs — win long tail + AI Overview citations instead.
- Comparison pages state competitor prices — re-verify quarterly ("prices checked July 2026" notes in copy).
- DR 11 → 30 required before even KD-1 terms rank reliably; launch-driven backlinks are the fastest path.
- Hosted version stores family data (kids' names, DOBs, calendar contents) and sends calendar text to Anthropic — GDPR care needed at build time. Phase 5 of [PLAN.md](PLAN.md).
- Traffic is currently only modelled: Google Search Console is not connected to the Ahrefs project, so there are no impression, click, or position numbers. Attaching a paid funnel to unmeasurable traffic is the bigger risk than any single keyword call.

## Next steps

1. ~~Reposition homepage + publish 6 satellite pages~~ (July 2026)
2. ~~Add waitlist capture for the hosted version~~ (Typeform, July 2026)
3. Connect Google Search Console to the Ahrefs project — highest-value measurement fix, blocks nothing, costs an hour
4. Build the hosted MVP — see [PLAN.md](PLAN.md) for phases and open questions
5. Launch: Show HN + r/selfhosted with the open-source story, timed with the hosted launch
6. Free tools: birthday countdown page, chore chart generator
