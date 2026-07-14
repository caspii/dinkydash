---
title: About DinkyDash
template: page.html
description: DinkyDash is a free, open-source digital family calendar that runs on screens you already own — with an AI-written daily brief for your family.
---

DinkyDash is a free, open-source **digital family calendar for screens you already own**. Point a TV, an old tablet, or a Raspberry Pi at it and your family gets one glanceable screen with today's calendar, a self-rotating chore chart, countdowns to the big days — and a daily brief written fresh every morning by AI.

It was built by [Caspar](https://casparwre.de), an indie developer in Berlin, for his own kids — and open-sourced because a family calendar shouldn't cost $629 plus a subscription.

## Why an AI-written dashboard?

Most family calendar displays show static information that someone has to curate. DinkyDash takes a different approach: you describe your family once, and AI does the rest.

Every morning at 6am, DinkyDash automatically:

- Fetches your Google Calendar events (any iCal link works)
- Figures out whose turn it is for each chore
- Calculates countdowns to birthdays, holidays, and special dates
- Sends all of this to Claude, which writes a personalized dashboard

The result is a screen that feels alive. It knows it's someone's birthday week. It writes a different fun fact and family challenge every day, tuned to your kids' interests. Kids check it voluntarily — which is the entire battle.

## What the dashboard shows

- **A daily headline** — a cheerful, AI-written greeting for your family
- **Person cards** — each family member with their photo and key info
- **Chore rotation** — who does what today, rotated automatically and fairly
- **Countdowns** — days until birthdays, holidays, vacations, and special events
- **Calendar events** — what's happening today, pulled from your shared calendar
- **Fun facts and challenges** — something new to read every morning
- **Pet corner** — because pets are family too

## The principles

- **Bring your own screen.** Anything with a browser works — no proprietary hardware, ever.
- **No subscription.** MIT-licensed, free forever. You bring your own AI API key; a day's dashboard costs a few cents.
- **Private by design.** Your family's details live in one config file on your own device — not in our cloud, because there isn't one.
- **Boring, reliable tech.** Python, a cron job, and a web page: `generate.py` builds the day's dashboard as JSON each morning, and a tiny Flask app renders it. It's fixable with a search engine and an afternoon.

## Where to start

- [Getting started guide](/getting-started/) — from zero to a dashboard on your wall
- [The ~$100 DIY build](/diy-skylight-calendar/) — the Raspberry Pi + touchscreen route
- [How it compares to Skylight, Hearth & co.](/skylight-calendar-alternatives/)
- [The code, on GitHub](https://github.com/caspii/dinkydash)

Want DinkyDash without the setup? A hosted version is in the works — [join the waitlist](https://fffwryhvses.typeform.com/to/yxMMhmFs).
