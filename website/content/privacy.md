---
title: Privacy policy
seo_title: "Privacy Policy — DinkyDash"
template: page.html
description: What DinkyDash stores, who it is sent to, how long it is kept, and how to get it back or delete it.
---

*Last updated: 11 September 2026.*

DinkyDash puts a family's day on a screen. That means the things it holds are a
household's names, dates of birth and movements — which is about as personal as
data gets, and children's data at that. This page says exactly what happens to
it.

**If you run DinkyDash yourself**, most of this does not apply to us at all.
Your config, your calendar links and your dashboard stay on your machine, and the
only thing that leaves it is the day's agenda, sent to Anthropic so Claude can
write the daily line — with your own API key, under your own agreement with
them. We hold nothing. This page describes the **hosted** version at
`app.dinkydash.co`.

## What we collect

Nothing is bought, sold, or gathered from anywhere else. Everything below is
either something you typed or something the software produced.

| What | Where it comes from | Why |
|---|---|---|
| **Your email address** | You type it to sign in | It is the whole of the account. There is no password |
| **Your family's details** | You type them: names, dates of birth, emoji, chores, special dates | They are what the dashboard shows |
| **Your calendar links** | You paste them | To fetch the events the dashboard shows |
| **Your calendar events** | Fetched from those links | The agenda on the dashboard |
| **The written line** | Written by Claude each morning | The dashboard's headline and note |
| **Sign-in links** | Generated when you ask for one | Hashed, never stored as a working link |
| **Counts of model calls** | Recorded when the dashboard is written | So one account cannot run up an unbounded bill |
| **Counts of sign-ups and first calendar connections** | Recorded when a family is created, and the first time it saves a calendar link | So we can see whether the product is being used, without looking at anyone's account |

**We do not use cookies for tracking.** The hosted app sets one cookie, and it
is the session that keeps you signed in. There is no analytics on
`app.dinkydash.co`, no advertising, and no third-party script on the dashboard or
the settings pages. The marketing site at `dinkydash.co` uses Ahrefs Web
Analytics, which is cookieless and collects no personal data.

## Where it goes

Three things leave our servers, they are different in kind, and it matters
which is which.

**Anthropic sees your family's day.** Once each morning the day's agenda — the
event titles and times, your family's names and interests — is sent to
Anthropic so Claude can write the headline and the one written line. That is
the feature. Nothing else about you is sent, and it is not used to train
models.

**SendGrid sees who is signing in, and nothing else.** When you ask for a sign-in
link, your email address and the link go to SendGrid to be delivered. SendGrid
never sees a calendar, a name or a date of birth.

**Sentry sees that something broke, and not whose dashboard it was.** When the app
or the background worker hits an error, a report goes to Sentry: which line of
our code failed, the kind of request it was in, and which version was running.
Never the page's address, and never a name, a calendar link, an appointment, an
email address or a written line — those are stripped before the report leaves,
and a test in the code base fails if they are not. The worker also tells Sentry
every few minutes that it is still running, which is how we find out when it is
not, and Sentry checks from outside that the sign-in page answers. Neither
carries anything about you.

If you would rather Anthropic saw nothing, self-host: the dashboard works with no
API key at all, and simply goes without the written line.

### Sub-processors

| Who | What they do | Where |
|---|---|---|
| **Anthropic** | Writes the daily line from the day's agenda | United States |
| **DigitalOcean** | Runs the app and the database | Frankfurt, Germany (US company) |
| **SendGrid** (Twilio) | Delivers sign-in emails | United States |
| **Cloudflare** | DNS, and TLS at the edge | Global (US company) |
| **Sentry** (Functional Software) | Error reports, and the checks that the app and the worker are running | United States |

The app and the database are in **Frankfurt**. DigitalOcean and Cloudflare are
United States companies operating them, and SendGrid and Sentry are in the
United States, so transfers outside the EU are covered by standard contractual
clauses.

**Google Fonts is not on this list, and that is deliberate.** The typeface is
served from our own servers, so no page of DinkyDash — not the dashboard, not the
settings, not this site — asks Google for anything or tells them you were here.

Payment processing will be added to this list when payment exists. It does not
yet.

## How long it is kept

We would rather hold less, so most of this expires on its own.

- **Your calendar events**: one rolling fourteen-day window per family,
  overwritten every time the calendars are refreshed. Nothing accumulates — the
  most we ever hold about your calendar is that one window.
- **The written lines**: daily briefs are kept while your account exists. A
  separate recent history helps the model avoid repetition; it keeps at least
  the last 30 entries and drops older ones as new ones arrive. Rewriting a day
  replaces that day's saved brief, while an earlier version may remain in the
  recent history until it is trimmed.
- **Sign-in links**: deleted once expired, which is fifteen minutes. A link that
  has been used is deleted on the same schedule.
- **Your account, your family's details and the record of dashboards written**: kept
  while the account exists, and deleted when you delete it.
- **Daily totals of model calls across the service**: kept without an account
  identifier, including after account deletion, so deleting an account does not
  reset the service's spending limit. These totals contain only a date and count.
- **Daily counts of sign-ups and of families that first connected a calendar**:
  kept without an account identifier, including after account deletion. Like the
  model-call totals, these hold a date and a count and nothing else.

After your trial or subscription ends, the screen shows the last saved dashboard
with an ended-access message for 30 days, then only the message. This changes
what the screen shows; it does not delete your stored account data. You can
still sign in to export or delete it.

**Backups.** DigitalOcean takes daily backups of the database and keeps seven
days of point-in-time recovery. Deleted data can therefore persist in a backup
for up to seven days before it ages out.

## Getting it back, and getting rid of it

Both are buttons, not requests, and both are on your settings page.

- **Export** gives you your family's details, calendar links, stored agenda,
  all retained daily briefs and recent rewrite history as one JSON file.
- **Delete** removes your family, your account, your calendar links, the stored
  agenda, every written line and every sign-in link. It cannot be undone and we
  cannot restore it for you.

You also have the right to correct what we hold — which the settings page does
directly — to object to processing, and to ask for your data in a portable form,
which is what the export is.

## Children

DinkyDash is for parents to use, and holds children's names and dates of birth
because that is what a family calendar is. **Accounts are for adults.** A child
does not sign up, and nothing on the dashboard asks a child for anything.

## Security

Sign-in links are hashed before they are stored, work once, and expire in
fifteen minutes. The dashboard's own screen URL is unguessable and can be changed at
any time from the settings page, which stops the old one working. Everything
travels over HTTPS. Every form that changes anything carries a token that stops
another site submitting it on your behalf.

**We will tell you** if a breach affects your data, and the Berlin supervisory
authority within 72 hours, as the GDPR requires.

## Automated decisions

Claude writes a sentence about your day. That is the whole of the automation,
and nothing is decided about you by it — no profiling, no scoring, and no
decision with any legal or similar effect.

## Complaints

If we have got something wrong, tell us first — but you have the right to go
straight to a supervisory authority. Ours is the **Berliner Beauftragte für
Datenschutz und Informationsfreiheit**, and you may also complain to the
authority where you live.

## Changes

If this policy changes in a way that affects what happens to your data, we will
email the address on your account before it takes effect. The date at the top
is when it last changed.

## Who we are

**Caspar von Wrede**
Argentinische Allee 2
14163 Berlin
Germany

Data protection enquiries: **hi@keepthescore.com**, with "privacy" in the
subject. That is the same person — DinkyDash and Keep The Score are both run by
Caspar, and `dinkydash.co` sends email but does not yet receive it, so writing
to an address there would reach nobody. We answer within one month, and will say
so if a request needs longer.

**Our domains** are `dinkydash.co` and `app.dinkydash.co`. Anything else is not
us.
