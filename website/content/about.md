---
title: About DinkyDash
seo_title: "About DinkyDash — An Open-Source Family Calendar"
template: page.html
description: DinkyDash is an open-source family calendar for a screen you already own. We can host it for you, or you can run it yourself for free.
---

DinkyDash is a **family calendar for a screen you already own**. Open it on a TV, an old tablet or a Raspberry Pi, and your family gets one screen with today's calendar, whose turn each chore is, and countdowns to the big days. A short headline at the top is written fresh each day.

It was built by [Caspar](https://casparwre.de), an indie developer in Berlin, for his own kids. It's been open source since 2021, because a family calendar shouldn't cost a dedicated screen and a subscription.

## What the dashboard shows

- **Today's agenda.** What's happening today, in time order, merged from every calendar you add.
- **Whose turn it is.** Each chore passes to the next person every day, so nobody has to keep track.
- **Countdowns.** Days until birthdays, holidays and the dates everyone keeps asking about.
- **A headline.** One line about the day, written by AI. It's the only part an AI writes.

## How it runs

Once a day, at a time you pick, Claude reads the day ahead and writes the headline. Your calendars are fetched every hour on their own schedule. Whose turn it is and the countdowns are worked out from the date each time the page loads, so they're right even if nobody has touched anything for months.

## The principles

- **Bring your own screen.** Anything with a browser works. There's no hardware to buy from us, now or later.
- **Nothing to feed.** There's nothing to tick and nobody to chase. It looks after itself.
- **Yours to keep.** The code is MIT-licensed and public, so the dashboard can't be taken away from you.

## Two ways to have it

**We host it.** Free for 14 days, and we don't ask for a card. After that it's $39 a year or $6 a month. We store your settings so we can build your dashboard each day, and the day's agenda goes to Anthropic so Claude can write the headline. [The privacy policy](/privacy/) names every company involved. [Start free](https://app.dinkydash.co/login).

**You host it.** Free, on your own machine, with your own Anthropic key, which costs about $0.13 a month. Your family's details stay with you. The one thing that leaves is the day's agenda, which goes to Anthropic under your key. Setting it up takes an afternoon and some comfort with a terminal.

## Where to start

- [Self-hosting guide](/getting-started/): from nothing to a dashboard on your wall
- [The ~$150 DIY build](/diy-skylight-calendar/): the Raspberry Pi and touchscreen route
- [How it compares to Skylight, Hearth and the rest](/skylight-calendar-alternatives/)
- [The code, on GitHub](https://github.com/caspii/dinkydash)
