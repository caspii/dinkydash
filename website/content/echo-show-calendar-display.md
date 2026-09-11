---
title: "Echo Show as a Family Calendar Display: What Works, and What Doesn't"
seo_title: "Echo Show Calendar Display: The Honest Guide"
template: page.html
description: An Echo Show can show your calendar — through Alexa's own calendar linking. What it cannot do is stay on a web dashboard, because the browser closes itself after about fifteen minutes. Here is the honest version of both.
faq:
  - q: "Can an Echo Show display my family calendar?"
    a: "Yes, through Alexa's own calendar feature. Link a Google, Microsoft or iCloud calendar in the Alexa app under Settings, Calendar, and the Echo Show displays it and answers questions about it. This is the route that works."
  - q: "Can I keep a web dashboard open on an Echo Show?"
    a: "Not reliably. The built-in Silk browser closes itself after roughly ten to fifteen minutes of no input and returns to the home screen, and Amazon provides no setting to turn that off. It is fine for looking something up; it is not an always-on panel."
  - q: "How do I link a calendar to my Echo Show?"
    a: "In the Alexa app, open More, then Settings, then Calendar, and connect a Google, Microsoft or Apple iCloud account. The Echo Show then shows those events on its home screen and in its calendar view."
  - q: "What should I use instead for an always-on family calendar?"
    a: "A cheap tablet. An old iPad or an Android tablet costs far less than an Echo Show, stays on the page you put it on, and hangs on a wall in the same spot. Both are covered on this site."
  - q: "Does the Echo Show 15 change this?"
    a: "Not for the browser. The Echo Show 15's larger screen and widgets make Alexa's own calendar considerably more useful as a wall display, but Silk still closes itself, so a web dashboard on it still will not stay put."
---

Two different questions get asked here, and they have opposite answers.

**"Can an Echo Show show my family calendar?"** Yes — through Alexa's own calendar feature,
which links to Google, Microsoft and iCloud. That works well and is the right route.

**"Can I leave a web dashboard running on an Echo Show?"** No, not reliably. The built-in
browser closes itself after about ten to fifteen minutes without input and drops back to the
home screen, and Amazon gives you no setting to stop it.

We make a web-based family calendar, so the second answer is the inconvenient one for us. It
is still the answer.

## The route that works: link a calendar to Alexa

This has nothing to do with us and it is what most people asking the question actually want.

1. Open the **Alexa app** on your phone.
2. Go to **More → Settings → Calendar**.
3. Connect a **Google**, **Microsoft** or **Apple iCloud** account.

The Echo Show then shows those events on its home screen, answers "what's on today?", and adds
events by voice. On an **Echo Show 15** or **21**, the calendar widget on the larger screen is
genuinely a decent kitchen display.

What it will not do is rotate a chore chart, count down to birthdays, or write you a line each
morning. It shows a calendar, competently.

## The route that does not: a web dashboard in Silk

The Echo Show has Amazon's Silk browser built in, so you can type a URL and a page will load
and fill the screen. For about a quarter of an hour.

**Silk on Echo Show closes itself after roughly ten to fifteen minutes of no input**, returning
to the home screen. This is widely reported by people trying to run exactly this kind of
dashboard, and Amazon's own support position is that the timeout cannot be switched off.
Workarounds circulate — pages that play a silent audio loop to convince the device something
is happening — and they are fragile, undocumented, and can stop working with any firmware
update.

We are not going to tell you to build a kitchen wall panel on that. A wall panel has one job,
which is to be right there when you glance at it.

## What to use instead

A **cheap tablet**, mounted where the Echo Show is now. It costs less, it stays on the page you
put it on, and both major platforms have a built-in way to lock it there:

- **[An old iPad](/ipad-calendar-display/)** — Guided Access locks it to one page behind a
  passcode, and Auto-Lock set to Never keeps the screen on. This is the best version.
- **[An Android tablet](/android-tablet-calendar-display/)** — the same idea, and second-hand
  ones cost about $50–80.
- **[A Raspberry Pi with a small screen](/raspberry-pi-family-calendar/)** — about $100 in
  parts, and the tidiest permanent panel of the three.

Keep the Echo Show for what it is good at: voice, timers, music and a glance at the calendar
Alexa already knows about.

## What you get on the tablet instead

![The DinkyDash dashboard on a tablet in portrait, stacked into one column: today's events, whose turn each chore is, countdowns and the daily note](/images/family-calendar-tablet-board.webp)

[DinkyDash](/) is free, open-source software that turns that tablet into a family dashboard:

- **Today's events**, merged from every calendar you add:
  [Google](/google-calendar-ical-link/), [iCloud](/icloud-calendar-link/),
  [Outlook](/outlook-calendar-ics-link/) and [Cozi](/cozi-calendar-display/) each publish a
  link, and each has its own page here with the steps.
- **A chore chart that rotates**, moving on one person a day by itself.
- **Countdowns** to birthdays, Christmas and the school holidays.
- **A daily note written each morning** by Claude, around your family's actual day.

It is MIT licensed with no subscription for the self-hosted version. The one running cost is
the daily note — a Claude API call once a day, roughly $0.13 a month — and the dashboard works
without it.

## Other screens

- [iPad](/ipad-calendar-display/) — the best cheap always-on panel
- [Android tablet](/android-tablet-calendar-display/) — the same, cheaper second-hand
- [Raspberry Pi](/raspberry-pi-family-calendar/) — the tidiest permanent panel, about $100
- [Smart TV](/smart-tv-calendar-display/) — Samsung and LG have their own browsers
- [Fire TV](/fire-tv-calendar-display/) — for the living-room television

## Start here

The [setup guide](/getting-started/) covers the whole thing: getting DinkyDash running, adding
your calendars, and pointing a screen at it. The code is on
[GitHub](https://github.com/caspii/dinkydash) under an MIT licence.

Rather skip the setup? [Start a free 14-day hosted trial](https://app.dinkydash.co/login), no card required.
