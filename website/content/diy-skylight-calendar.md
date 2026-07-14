---
title: "DIY Skylight Calendar: Build a Digital Family Calendar for About $100"
template: page.html
description: How to build your own Skylight-style digital family calendar with a Raspberry Pi or an old tablet — free, open-source software, no subscription, about $100 in hardware (or $0 if you have a spare screen).
---

A Skylight Calendar Max costs $629, plus $79 a year if you want the Plus features. The thing is, a digital family calendar is fundamentally *a screen showing a web page* — and that's something you can build yourself for about $100 with a Raspberry Pi, or for **$0** with a tablet you already own.

Here's exactly how, using [DinkyDash](https://github.com/caspii/dinkydash), our free and open-source family calendar software.

![A Raspberry Pi with a small touchscreen showing a family dashboard, sitting on a kitchen shelf](/images/diy-raspberry-pi-calendar.png)

## What you get

Your DIY calendar shows everything on one glanceable screen, refreshed automatically:

- **Today's events** from Google Calendar (or any calendar with an iCal link)
- **A chore chart** that rotates between kids automatically every day
- **Countdowns** to birthdays, holidays, and vacations
- **A daily brief written by AI** — a fresh greeting, fun fact, and family challenge every single morning, personalized to your family

That last one is something even the $629 hardware doesn't do.

## The hardware: three routes

| Route | What you need | Cost |
|---|---|---|
| **Old tablet** | The iPad or Android tablet in your drawer + a stand or wall mount | ~$0 |
| **Raspberry Pi build** | Pi 4 or 5, 7″ touchscreen, SD card, power supply | ~$100–130 |
| **Spare monitor or TV** | Any screen with a browser, or one connected to any computer | ~$0 |

The Raspberry Pi route is the classic: it draws a couple of watts, mounts cleanly on a wall or shelf, and boots straight into the dashboard in kiosk mode. The old-tablet route is the fastest way to find out whether your family will actually use a wall calendar.

## The build, in five steps

The [full getting-started guide](/getting-started/) has copy-paste commands for every step. The short version:

1. **Install DinkyDash** — clone the repo, install Python dependencies (about 10 minutes).
2. **Describe your family** — one config file with names, birthdays, chores, special dates, and your Google Calendar's iCal link.
3. **Add an Anthropic API key** — this powers the daily AI brief. A day's dashboard costs a few cents.
4. **Set the 6am schedule** — one cron line generates a fresh dashboard every morning before anyone wakes up.
5. **Point your screen at it** — on a Pi, Chromium launches fullscreen at boot; on a tablet or TV, just open the dashboard URL in the browser.

## DIY vs Skylight, honestly

**What you give up:** the slick touch interface for editing events on the screen itself (you edit in Google Calendar instead), the polished companion app, and someone to email when things break.

**What you gain:**

| | Skylight Calendar Max | DIY with DinkyDash |
|---|---|---|
| Hardware | $629 | $0–130 |
| Subscription | $79/yr for Plus features | None |
| Three-year cost | ~$866 | ~$0–130 |
| Your data | Their cloud | Your device |
| AI daily brief | No | Yes |
| Fixable/customizable | No | It's your code |

*Prices checked July 2026.*

## Start here

If you can copy commands into a terminal, you can have this on your kitchen wall by Sunday: **[the complete setup guide](/getting-started/)**. Rather skip the setup entirely? A hosted version is coming — [join the waitlist](/#waitlist).

Not sure DIY is for you? See [all the Skylight alternatives](/skylight-calendar-alternatives/), including no-setup options.
