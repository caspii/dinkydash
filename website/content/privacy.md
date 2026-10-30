---
title: Privacy policy
seo_title: "Privacy Policy — DinkyDash"
template: page.html
description: What DinkyDash stores, who it is sent to, how long it is kept, and how to get it back or delete it.
---

*Last updated: 22 October 2026.*

DinkyDash puts a family's day on a screen. That means the things it holds are a
household's names, dates of birth and movements — which is about as personal as
data gets, and children's data at that. This page says exactly what happens to
it.

**If you run DinkyDash yourself**, most of this does not apply to us at all.
Your config, your calendar links and your dashboard stay on your machine, and the
only thing that leaves it is the day's agenda, sent to Anthropic so Claude can
write the headline — with your own API key, under your own agreement with
them. We hold nothing. This page describes the **hosted** version at
`app.dinkydash.co`.

## What we collect

Nothing is bought, sold, or gathered from anywhere else. Everything below is
something you typed, something the software produced, or the size and browser
of a screen showing your dashboard.

| What | Where it comes from | Why |
|---|---|---|
| **Your email address** | You type it to sign in | It is the whole of the account. There is no password |
| **Your family's details** | You type them: names, dates of birth, emoji, chores, special dates | They are what the dashboard shows |
| **Your calendar links** | You paste them | To fetch the events the dashboard shows |
| **Your calendar events** | Fetched from those links | The agenda on the dashboard |
| **The headline** | Written by Claude once a day | The line at the top of the dashboard |
| **Sign-in links** | Generated when you ask for one | Hashed, never stored as a working link |
| **Counts of model calls** | Recorded when the dashboard is written | So one account cannot run up an unbounded bill |
| **Counts of sign-ups and first calendar connections** | Recorded when a family is created, and the first time it saves a calendar link | So we can see whether the product is being used, without looking at anyone's account |
| <span id="screen-size-row">**Your screen's size and browser**</span> | Sent by the dashboard when it refreshes | Used only to tune the layout |
| **Anything you send us** | You write it in the feedback form, or email us | So we can answer it and fix what you told us about. It is not stored in the app — it arrives as an email |
| **Subscription records** | Stripe, after you choose to pay | Customer/subscription identifiers, payment status, monthly or yearly billing, renewal and cancellation dates; no card details |

The size is the browser window the dashboard fits itself to, not the panel's
own resolution. We record it, and the browser, only to tune the layout.

## Lawful basis

- Screen size and browser: our legitimate interest in making the dashboard fit the screens it actually runs on (Art. 6(1)(f) GDPR).

**We use a small number of cookies for tracking, described below.** The
hosted app sets a session cookie that keeps you signed in. The sign-in
pages on `app.dinkydash.co` load Fathom Analytics, so we can see which sites
and campaigns bring people to a new dashboard. Fathom is cookieless. It does
not see your name, your email address, your family's details or your calendar,
and it is not loaded on the dashboard, the settings pages or the screen. The
marketing site at `dinkydash.co` uses Fathom on every page, also without a
cookie, and Ahrefs Web Analytics, which is also cookieless. Ahrefs is sent
the page's address without anything after the # in the link, and it does
not set a cookie or receive your name, your email address or the names on a
chart. Fathom sees any campaign parameters on the link that brought you
here; Ahrefs no longer does.
<!-- Source: https://business.safety.google/privacy/ -->
We also use Google Ads tags on the marketing site, the sign-in pages and the
page shown after you subscribe, to measure sign-ups and subscriptions, and we
store the campaign details — such as a utm or gclid value — that first
brought you here on your account.

## Where it goes

The services below receive only what they need for their part of the app.

**Anthropic sees your family's day.** Once a day the day's agenda — the
event titles and times, your family's names and interests — is sent to
Anthropic so Claude can write the headline. That is the feature. Nothing else
about you is sent, and it is not used to train
models.

**SendGrid delivers sign-in links, subscription notices and feedback.** Your
email address, sign-in link or trial/payment/cancellation notice goes to
SendGrid for delivery. When you use the feedback form, what you wrote and your
address go the same way. Your calendars, family names and dates of birth are
not included unless you write them in feedback yourself.

**Stripe handles payments when you choose a subscription.** Starting Checkout
creates a Stripe customer with an internal account identifier. You enter your
billing email, name, address and payment details directly on Stripe's pages.
We receive subscription status, whether you pay monthly or yearly, and identifiers, not your card details. Your
calendars and family details are never sent to Stripe. Signing up for the free
trial does not create a Stripe customer.

**Feedback goes to a mailbox, not to a database.** What you write in the form is
emailed to us with your account's address and your family's internal reference
on it, so we can reply and find the dashboard you are asking about. Nothing from
the dashboard goes with it — no names, no calendar links and no appointments —
unless you write them yourself. It arrives in a mailbox held by Google, read by
Caspar and nobody else, and that is where your message stays: there is no
feedback table in the app, so nothing about it appears in your export and there
is nothing in the app to delete. Writing to **hi@keepthescore.com** reaches the
same person, and is what a reply to us comes back to.

**Sentry sees that something broke, and not whose dashboard it was.** When the app
or the background worker hits an error, a report goes to Sentry: which line of
our code failed, the kind of request it was in, and which version was running.
Never the page's address, and never a name, a calendar link, an appointment, an
email address or a written line — those are stripped before the report leaves,
and a test in the code base fails if they are not. The worker also tells Sentry
every few minutes that it is still running, which is how we find out when it is
not, and Sentry checks from outside that the sign-in page answers. Neither
carries anything about you.

**Fathom counts visits to the sign-in pages, and a sign-up.** The pages where
you ask for a link, check your email and press the button load Fathom
Analytics. So does one page you see only once, just after a new account is
created, which then opens your settings. Your browser tells Fathom which of
those pages you opened, which site linked you here, and any campaign
parameters on that link. Fathom also works out your browser, your type of
device and your country. It uses your IP address and browser details to count
you as one visitor for the day, mixing them into a code that changes every
day, and it doesn't keep the address. It sets no cookie. It doesn't see your
name, your email address, your family's details or your calendar, and it isn't
on the dashboard, the settings pages or the screen. A sign-up is counted once,
when the account is created. Signing in again isn't counted as a sign-up. The
marketing site at dinkydash.co uses Fathom on every page.

**Cloudflare checks that a person is asking for the sign-in link.** The sign-in
page carries a Cloudflare Turnstile box, so your browser talks to Cloudflare
when you ask us to email you a link. It is there to stop scripts having us send
sign-in emails to addresses that never asked for one. Turnstile sees your IP
address and what your browser gives it to tell a person from a script; it does
not see the address you typed, and it is on no other page. It sets no
advertising cookie and we do not use it to track you.

If you would rather Anthropic saw nothing, self-host: the dashboard works with no
API key at all, and simply goes without the headline.

### Sub-processors

| Who | What they do | Where |
|---|---|---|
| **Anthropic** | Writes the headline from the day's agenda | United States |
| **DigitalOcean** | Runs the app and the database | Frankfurt, Germany (US company) |
| **SendGrid** (Twilio) | Delivers sign-in emails, subscription notices and feedback | United States |
| **Google** | The mailbox our support and feedback email arrives in, and the Google Ads tags on the marketing site and sign-in pages | United States |
| **Cloudflare** | DNS; website and app delivery through DigitalOcean's App Platform; the bot check on the sign-in page | Global (US company) |
| **Fathom Analytics** (Conva Ventures) | Cookieless visit counts on the marketing site and the sign-in pages, and the sign-up event | Canadian company. EU and UK visitors are processed in Germany and Finland, other visitors in the United States, and the counts are stored in the United States |
| **Ahrefs** | Cookieless visit counts on the marketing site | See [Ahrefs' privacy policy](https://ahrefs.com/legal/privacy-policy) for its entities and international processing |
| **Sentry** (Functional Software) | Error reports, and the checks that the app and the worker are running | United States |
| **Stripe** | Processes subscriptions and payments when you choose to pay | See [Stripe's privacy policy](https://stripe.com/privacy) for its entities and international processing |

<!-- Source: https://ahrefs.com/legal/privacy-policy, checked 2026-10-22 -->

The app and the database run on DigitalOcean in **Frankfurt**. Cloudflare
provides our DNS and, as one of
[DigitalOcean's sub-processors](https://www.digitalocean.com/trust/subprocessors),
delivers website and app traffic through its global network. Hosting in
Frankfurt does not mean all processing stays in Germany: requests pass through
that network, and Anthropic, SendGrid, Google and Sentry process data in the
United States, and so does Fathom for visitors outside the EU, as listed above.

DigitalOcean and Cloudflare are United States companies. Their published
[data processing agreement](https://www.digitalocean.com/legal/data-processing-agreement)
and [data processing addendum](https://www.cloudflare.com/cloudflare-customer-dpa/)
set out safeguards for international transfers, including the EU–US Data
Privacy Framework and standard contractual clauses where applicable.

Fathom is run by a Canadian company, Conva Ventures, and Canada is covered by
an EU adequacy decision. Under its
[data processing agreement](https://usefathom.com/legal/dpa), the IP address of
a visitor in the EU is hashed on servers in the EU before anything reaches its
US infrastructure, and it keeps no personal data for longer than 24 hours.

**Google Fonts is not on that list, and that is deliberate.** The typeface is
served from our own servers, not Google's, so no page of DinkyDash — not the
dashboard, not the settings, not this site — asks Google for a font or tells
them you were here just to render one. The mailbox above and the Google Ads
tags described earlier are the only other times this service is involved.

## How long it is kept

We would rather hold less, so most of this expires on its own.

- **Your calendar events**: one rolling fourteen-day window per family,
  overwritten every time the calendars are refreshed. Nothing accumulates — the
  most we ever hold about your calendar is that one window.
- **The headline**: kept while your account exists. A recent history keeps at
  least the last 30 entries and drops older ones as new ones arrive, and that
  history is in your export. An older entry can still hold a short note the
  dashboard no longer shows. Rewriting a day replaces that day's saved headline;
  an earlier version may remain in the recent history until it is trimmed.
- **Sign-in links**: deleted once expired, which is fifteen minutes. A link that
  has been used is deleted on the same schedule.
- **Anything you send us**: kept in our mailbox as long as any other
  correspondence, because that is what it is. Ask us to delete it and we will.
- **Your account, your family's details and the record of dashboards written**: kept
  while the account exists, and deleted when you delete it.
- **Daily totals of model calls across the service**: kept without an account
  identifier, including after account deletion, so deleting an account does not
  reset the service's spending limit. These totals contain only a date and count.
- **Daily counts of sign-ups and of families that first connected a calendar**:
  kept without an account identifier, including after account deletion. Like the
  model-call totals, these hold a date and a count and nothing else.
- **Your screen's size and browser**: kept while the account exists, and
  deleted with it. Used only to tune the layout.
- **Our subscription records, processed payment-event identifiers and notification
  delivery records**: kept while the account exists and deleted with it. We do
  not store webhook bodies or copies of your billing address or card details.
  Stripe keeps its own payment records under its [privacy policy](https://stripe.com/privacy),
  including records it needs to meet legal obligations.

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
  all retained daily headlines, recent rewrite history, and each recorded
  screen size and browser as one JSON file.
- **Delete** removes your family, your account, your calendar links, the stored
  agenda, every written line, every sign-in link, and the record of your
  screen's size and browser. It cannot be undone and we
  cannot restore it for you.
  If you have started billing, deletion first cancels your subscriptions and
  deletes the Stripe customer. If Stripe cannot confirm this, we keep the account
  and ask you to retry, so billing is not left running without an account.

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
