---
title: "Put a Family Calendar on Your Smart TV (Samsung, LG and the rest)"
seo_title: "Smart TV Calendar Display: Samsung, LG and Android TV"
template: page.html
description: Samsung and LG TVs have a web browser, so they can show a family calendar with no app to install. Here is how — and the honest limit, which is that a TV is built to stop showing a still image.
faq:
  - q: "Can I display a calendar on my smart TV?"
    a: "Yes, if the TV has a web browser — Samsung's Tizen sets and LG's webOS sets both do. Open the browser, type the address of a calendar page, and it fills the screen. There is no app to install."
  - q: "Is there a calendar app for Samsung or LG TVs?"
    a: "Not a good one. Both app stores are built around streaming, and the calendar apps that exist are thin. The browser is the better route, because any web-based family calendar works in it and nothing needs installing."
  - q: "Will my TV keep showing the calendar?"
    a: "Not indefinitely. Most sets switch to a screensaver after about 30 minutes without input, and OLED sets do it whether you like it or not because a still image risks burning in. A TV is fine for glancing at the day; it is the wrong device for an always-on panel."
  - q: "How do I type a web address with a TV remote?"
    a: "Slowly. Do it once, bookmark the page, and never type it again. A Bluetooth keyboard paired to the TV, or the TV maker's phone app with its on-screen keyboard, makes the one time much less painful."
  - q: "What should I use instead for an always-on calendar?"
    a: "A cheap tablet or a Raspberry Pi. Both are designed to sit there showing one thing, both cost far less than a television, and both go in the kitchen, where a family calendar is actually useful."
---

**Yes, if your TV has a web browser — and Samsung's Tizen sets and LG's webOS sets both do.**
Open the browser, type the address, and the dashboard fills the screen. No app, no account, no
casting.

But be told the limit up front: **a television is built to stop showing a still picture.**
That makes it a fine screen to glance at and a poor always-on panel. The honest version of
both halves is below.

## What you need

DinkyDash is a **web page**, not an app you install. So there are two parts:

1. **Something to serve it.** A Raspberry Pi or an old computer on your Wi-Fi — free, MIT
   licensed, and about an evening's work. Or [start a free 14-day hosted trial](https://app.dinkydash.co/login), no card required.
2. **The TV**, which is the screen. It opens that address in the browser it already has.

![The DinkyDash dashboard on a wide screen: today's events on the left, whose turn each chore is and the countdowns on the right](/images/family-calendar-tv-board.webp)

On a 16:9 screen the dashboard splits into two columns by itself, and sizes its own type to the
display. Nothing needs configuring for a particular television.

## Set it up

**1. Find the browser.** On **Samsung**, it is **Internet**, in the apps row on the home bar.
On **LG**, it is **Web Browser**, in the launcher. On an **Android TV or Google TV** box there
is usually no browser preinstalled — install Chrome, or use a [Fire TV
stick](/fire-tv-calendar-display/) instead.

**2. Type the address, once.** On your own network it looks like `http://192.168.1.50:5000`.
Typing that with a remote is the worst part of this whole page. Two ways to make it survivable:

- Pair a **Bluetooth keyboard** to the TV for the one minute it takes.
- Use the **TV maker's phone app** — SmartThings for Samsung, the LG ThinQ remote — which
  gives you a phone keyboard instead of an on-screen grid.

**3. Bookmark it.** Then you never type it again. Both browsers open on their bookmarks, so
the dashboard is two clicks from the home screen for good.

## The honest limit

**Most TVs switch to a screensaver after about 30 minutes without a button press.** That is
not a bug you can configure away on every set:

- **Samsung** and **LG LCD sets** usually let you turn the screensaver off, or lengthen it,
  under the general or power settings. Look for **Screen saver**, **Auto power off** or
  **Energy saving**.
- **OLED sets do it deliberately**, and on many of them the option is missing entirely. An
  OLED panel can retain a static image permanently, so the manufacturer moves or dims the
  picture on purpose. That is the panel protecting itself, and you should let it.

There is a second, plainer problem: a television is in the living room. A family calendar earns
its keep in the kitchen or the hall, where people pass it on the way out of the door.

So the fair summary is: **a smart TV is a good way to put the day on the big screen for a
minute, and the wrong device to leave it on all day.** If what you want is an always-on panel,
an [old tablet](/android-tablet-calendar-display/) or a
[Raspberry Pi](/raspberry-pi-family-calendar/) does that job properly and costs a fraction of
a television.

## What ends up on the screen

- **Today's events**, merged from every calendar you add:
  [Google](/google-calendar-ical-link/), [iCloud](/icloud-calendar-link/),
  [Outlook](/outlook-calendar-ics-link/) and [Cozi](/cozi-calendar-display/) each publish a
  link, and each has its own page here with the steps.
- **A chore chart that rotates**, moving on one person a day by itself.
- **Countdowns** to birthdays, Christmas and the school holidays.
- **A daily line written each morning** by Claude, around your family's actual day.

The dashboard reloads itself every five minutes with a plain HTML refresh rather than JavaScript,
which matters here more than anywhere: TV browsers are the oldest browsers in the house, and
this one keeps working in them.

## What it costs

Nothing beyond the television you already own. DinkyDash is free and MIT licensed with no
subscription for the self-hosted version, and the only running cost is the daily line — a
Claude API call once a day, roughly $0.13 a month, and the dashboard works without it.

## Other screens

- [Fire TV](/fire-tv-calendar-display/) — if your TV has no browser, a Fire Stick gives it one
- [iPad](/ipad-calendar-display/) — the best cheap always-on panel
- [Android tablet](/android-tablet-calendar-display/) — the same, cheaper second-hand
- [Raspberry Pi](/raspberry-pi-family-calendar/) — the tidiest permanent panel, about $100
- [Echo Show](/echo-show-calendar-display/) — the one that does not work, and why

## Start here

The [setup guide](/getting-started/) covers the other half: getting DinkyDash running, adding
your calendars, and pointing a screen at it. The code is on
[GitHub](https://github.com/caspii/dinkydash) under an MIT licence.

Rather skip the setup? [Start a free 14-day hosted trial](https://app.dinkydash.co/login), no card required.
