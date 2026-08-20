---
title: "Raspberry Pi Family Calendar: Build a Wall Dashboard That Updates Itself"
template: page.html
description: How to turn a Raspberry Pi into a wall-mounted family calendar and dashboard — today's events, rotating chores, birthday countdowns and an AI daily brief, for about $100 in parts and no subscription.
---

A Raspberry Pi, a small touchscreen and some open-source software make a genuinely good family calendar: it hangs on the kitchen wall, shows today's schedule at a glance, updates itself every morning, and costs about **$100 in parts with nothing monthly**.

This page covers the hardware side — which Pi, which screen, what it draws, what it costs. The [full setup guide](/getting-started/) has the copy-paste commands.

![A Raspberry Pi with a small touchscreen showing a family dashboard, sitting on a kitchen shelf](/images/diy-raspberry-pi-calendar.png)

## What ends up on the screen

[DinkyDash](https://github.com/caspii/dinkydash) is a free, open-source, MIT-licensed family dashboard built for exactly this. On the display you get:

- **Today's events**, pulled from Google Calendar or any calendar with an iCal link
- **A chore chart** that rotates between family members automatically each day
- **Countdowns** to birthdays, holidays and vacations
- **A daily brief written by Claude** — a fresh greeting, fun fact and family challenge every morning, written around your actual family

No touch interaction is required. It's a display, not an app — which is the point, and also why a modest Pi is plenty.

## Which Raspberry Pi

| Model | Verdict |
|---|---|
| **Pi 4 (2GB)** | The sweet spot. Runs Chromium in kiosk mode comfortably, cheap, widely available second-hand. This is what we'd pick. |
| **Pi 5** | Works fine and boots faster, but it's more money and more heat for a job that's mostly idle. Overkill here. |
| **Pi Zero 2 W** | Tempting at the price, but Chromium is a heavy browser and the Zero struggles. Workable if you're patient; frustrating if you're not. |
| **Pi 3** | Fine if you already own one. Slow to boot, but it only boots once. |

2GB of RAM is enough. The dashboard is a single static page that refreshes every five minutes — there's no database and no continuous rendering.

## Which display

The software targets **800×480**, which is the resolution of the official Raspberry Pi 7″ Touch Display. That's the path of least resistance.

- **Official 7″ Touch Display** — connects over DSI (one ribbon cable, no HDMI), powered from the Pi itself. Around $60–80.
- **Any HDMI monitor** — works, and a bigger screen reads better from across a room. You'll want to adjust the layout, and you're now managing two power supplies.
- **An old monitor you already own** — free, and honestly the best way to test whether your family will actually look at it before you spend anything.

Touch is optional. The dashboard is read-only by design; you edit events in Google Calendar on your phone, the way you already do.

## Parts list

| Part | Approximate cost |
|---|---|
| Raspberry Pi 4 (2GB) | $45–60 |
| Official 7″ Touch Display | $60–80 |
| MicroSD card (16GB+) | $8–12 |
| USB-C power supply | $8–12 |
| Case or stand | $0–20 |
| **Total** | **~$120–185 new, well under $100 with parts you own or buy used** |

*Prices are approximate and vary by retailer — checked August 2026.*

Second-hand Pis are abundant and this workload will never stress one, so the used market is a genuinely good idea here.

## How it actually works

The architecture is deliberately boring, which is why it keeps running:

1. **A cron job at 6am** runs a generation script. It fetches your calendar, works out ages, birthday countdowns and whose turn it is for each chore, sends all of that to the Claude API, and writes the result to a single JSON file.
2. **A small Flask server** reads that JSON file and renders the page.
3. **Chromium launches fullscreen at boot** in kiosk mode and refreshes every five minutes.

The API call happens **once a day**, not on every page load. That matters for two reasons: the dashboard stays instant because it's only ever serving a static file, and your Anthropic bill is a few cents a month rather than a few dollars.

If the network drops or the API call fails, the previous day's JSON is still on disk and the screen keeps showing it. A stale dashboard beats a blank one.

## Power draw and leaving it on

A Pi 4 with the 7″ display sits **under 10 watts**. Left on around the clock that's roughly 60 kWh a year — call it $10 at typical US rates.

You can cut that roughly in half with two cron lines that switch the display off overnight and back on before breakfast:

```
0 22 * * * /home/pi/screen_control.sh off
0 7 * * * /home/pi/screen_control.sh on
```

The Pi stays up; only the panel sleeps. The [setup guide](/getting-started/) has the script.

## Kiosk mode

The one part people usually get wrong is the boot sequence: Chromium starts before Flask is ready and you get "localhost refused to connect" on the wall every morning. The startup script in the setup guide polls the server for up to 60 seconds before launching the browser, which fixes it.

Two other things worth knowing before you start:

- Install `fonts-noto-color-emoji`, or the dashboard renders as empty boxes.
- On Raspberry Pi OS Bookworm the boot config lives at `/boot/firmware/config.txt`, not `/boot/config.txt` — this trips up a lot of older tutorials.

Both are covered, with fixes, in the [troubleshooting section](/getting-started/).

## Why build one instead of buying

A Skylight Calendar Max is $629, plus $79 a year for the Plus features. A Hearth Display is $699 plus $9 a month. They're nicely made, and if you want something that works out of the box with a support line, they're reasonable purchases.

But a digital family calendar is fundamentally a screen showing a web page. If you're comfortable with a terminal, the Pi version costs about a sixth as much, has no subscription, keeps your family's data on your own device, and does one thing the $629 hardware doesn't: writes you a fresh daily brief every morning.

The full cost comparison is on the [DIY Skylight calendar page](/diy-skylight-calendar/).

## Start building

Everything you need is in the [setup guide](/getting-started/) — install, config, cron, systemd service and kiosk mode, with the commands to copy. Budget an evening for the first build.

The code is on [GitHub](https://github.com/caspii/dinkydash) under an MIT licence. Stars and issues welcome.

Want the dashboard without the Pi? A hosted version is coming — [join the waitlist](https://fffwryhvses.typeform.com/to/yxMMhmFs).
