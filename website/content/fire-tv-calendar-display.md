---
title: "A Family Calendar on Fire TV (No App to Install)"
seo_title: "Fire TV Calendar Display: Put Your Family Calendar on a TV"
template: page.html
description: There is no good family calendar app for Fire TV, but there is a browser — and a web-based calendar board works in it. Here is the setup, and the honest limit of using a TV stick for this.
faq:
  - q: "Is there a family calendar app for Fire TV?"
    a: "Not a good one. The Fire TV app store is built around streaming, and the calendar apps in it are thin. The better route is Amazon's own Silk Browser, which is free in the same store — any web-based calendar board opens in it with nothing else to install."
  - q: "Does Fire TV have a web browser?"
    a: "Yes. Amazon Silk is a free download from the Fire TV app store and is still the maintained browser for the platform. Search for Silk from the home screen, download it, and it works with the standard remote."
  - q: "Can a Fire Stick show a calendar all day?"
    a: "It can show one for a long stretch, but a Fire TV has a screensaver and a TV has power saving, so it is not a set-and-forget wall panel. For always-on, a cheap tablet or a Raspberry Pi is the right device."
  - q: "How do I type a web address on a Fire TV?"
    a: "Use the Alexa voice button on the remote to dictate it, or the Fire TV phone app, which gives you a real keyboard. Then bookmark the page so you never type it again."
  - q: "Do I need an Amazon subscription for this?"
    a: "No. Silk is a free download, the calendar software is free and open source, and nothing here touches Prime."
---

There is no good family calendar app for Fire TV. There is, however, a **browser** — Amazon's
own Silk, free in the same app store — and a web-based calendar board opens in it with nothing
else to install.

So: **yes, you can put your family's day on the television**, and the only thing you install
is a browser. The honest limit is at the bottom of the page.

## What you need

DinkyDash is a **web page**, not an app. So there are two parts:

1. **Something to serve it.** A Raspberry Pi or an old computer on your Wi-Fi — free, MIT
   licensed, and about an evening's work. Or [start a free 14-day hosted trial](https://app.dinkydash.co/login), no card required.
2. **The Fire TV**, which is the screen. Silk opens that address.

![The DinkyDash board on a wide screen: today's events on the left, whose turn each chore is and the countdowns on the right](/images/family-calendar-tv-board.webp)

On a 16:9 television the board splits into two columns by itself and sizes its own type to the
screen. Nothing needs configuring for a particular set.

## Set it up

**1. Install Silk.** From the Fire TV home screen, go to **Find → Search**, type or say
"Silk", pick **Amazon Silk** and choose **Download**. It is free and it is Amazon's own, so
there is no sideloading and no developer mode.

**2. Type the address, once.** On your own network it looks like `http://192.168.1.50:5000`.
Typing that on an on-screen keyboard with a remote is the worst minute of this whole setup.
Two ways round it:

- **Hold the voice button** on the remote and dictate the address. Silk supports Alexa input.
- **Use the Fire TV phone app**, which turns your phone into a remote with a real keyboard.

**3. Bookmark it.** Silk opens on its bookmarks, so after this the board is two clicks from
the home screen and you never type the address again.

**4. Push the screensaver out.** Settings → **Display & Sounds** → **Screensaver** → set
**Start after** to its longest value. This does not remove the screensaver, only delays it.

## The honest limit

A Fire TV stick is a streaming device plugged into a television, and both halves of that fight
an always-on calendar:

- **The Fire TV screensaver comes back.** You can push it out, not switch it off.
- **The television has its own power saving**, and on an OLED set the panel dims or shifts a
  static image on purpose, because it can burn in.
- **A television is in the living room.** A family calendar earns its keep in the kitchen or
  the hall, where people pass it on the way out of the door.

So the fair summary: **a Fire TV is a good way to put today on the big screen for a few
minutes — over breakfast, or while the football is loading — and the wrong device to leave it
on all day.** If what you want is a panel that never goes off, an
[old tablet](/android-tablet-calendar-display/) or a
[Raspberry Pi](/raspberry-pi-family-calendar/) does that job properly, and costs less than the
television does.

If your TV already has its own browser, you may not need the stick at all — see [smart TV
calendar display](/smart-tv-calendar-display/) for Samsung and LG.

## What ends up on the screen

- **Today's events**, merged from every calendar you add:
  [Google](/google-calendar-ical-link/), [iCloud](/icloud-calendar-link/),
  [Outlook](/outlook-calendar-ics-link/) and [Cozi](/cozi-calendar-display/) each publish a
  link, and each has its own page here with the steps.
- **A chore chart that rotates**, moving on one person a day by itself.
- **Countdowns** to birthdays, Christmas and the school holidays.
- **A daily line written each morning** by Claude, around your family's actual day.

The board reloads itself every five minutes with a plain HTML refresh rather than JavaScript.
That matters on a TV stick, where the browser is the least capable one in the house.

## What it costs

Nothing beyond the Fire TV you already own. Silk is free, DinkyDash is free and MIT licensed
with no subscription for the self-hosted version, and the only running cost is the daily
line — a Claude API call once a day, roughly $0.13 a month, and the board works without it.

## Other screens

- [Smart TV](/smart-tv-calendar-display/) — Samsung and LG have their own browsers
- [iPad](/ipad-calendar-display/) — the best cheap always-on panel
- [Android tablet](/android-tablet-calendar-display/) — the same, cheaper second-hand
- [Raspberry Pi](/raspberry-pi-family-calendar/) — the tidiest permanent panel, about $100
- [Echo Show](/echo-show-calendar-display/) — the one that does not work, and why

## Start here

The [setup guide](/getting-started/) covers the other half: getting DinkyDash running, adding
your calendars, and pointing a screen at it. The code is on
[GitHub](https://github.com/caspii/dinkydash) under an MIT licence.

Rather skip the setup? [Start a free 14-day hosted trial](https://app.dinkydash.co/login), no card required.
