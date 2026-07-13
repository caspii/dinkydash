# DinkyDash Strategy

*Last updated: July 13, 2026. Based on Ahrefs keyword/competitor research (July 2026) — see data summary below.*

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

## Product model: open core + hosted SaaS

1. **Open-source repo (now)** — the credibility wedge and top of funnel. Free, MIT, self-hosted, bring your own Anthropic API key. Feeds HN/Reddit launches, GitHub stars, and referring domains (dinkydash.co is DR 11 with 84 ref domains; needs ~DR 30 for the wedge terms).
2. **Hosted version (next)** — the business. Signup, family config form, paste an iCal URL, per-family screen URL with pairing code, central 6am generation, Stripe. Category-anchored pricing: **~$4–6/mo or ~$39/yr** (vs Skylight Plus $79/yr, Hearth $9/mo). AI cost per family is pennies/month. Collect emails via a waitlist link until it exists.

Explicitly skipped: monetizing self-hosting (license keys/paid repo) — keeps the audience filter, no recurring value capture.

## Pricing anchors (verified July 2026)

| Product | Hardware | Subscription |
|---|---|---|
| Skylight Calendar 2 (15") | $299 | Plus $79/yr (optional) |
| Skylight Calendar Max (27") | $629 | Plus $79/yr (optional) |
| Hearth Display (27") | $699 ($599 promo) | $9/mo after first month |
| DAKboard (BYO screen) | — | Free tier; $5–8/mo |
| Mango Display (BYO screen) | — | Free tier; Pro $5.99/mo |
| **DinkyDash (BYO screen)** | — | **Free, open source (hosted tier planned ~$4–6/mo)** |

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
- Hosted version stores family data (kids' names, calendars) — GDPR care needed at build time.

## Next steps

1. ~~Reposition homepage + publish 6 satellite pages~~ (this change)
2. Add waitlist capture for the hosted version (currently a mailto link — swap for a form endpoint)
3. Launch: Show HN + r/selfhosted with the open-source story
4. Build hosted MVP (multi-tenant generate + pairing-code screen URLs + Stripe)
5. Free tools: birthday countdown page, chore chart generator
