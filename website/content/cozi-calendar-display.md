---
title: "Cozi Calendar Display: Put Your Cozi Calendar on a Wall Screen"
seo_title: "Cozi Calendar Display: Put Cozi on a Wall Screen"
template: page.html
description: Cozi has no wall display of its own, but it does hand out a shareable calendar URL. Here is how to find it and put your family's Cozi calendar on a screen in the kitchen — free, on a screen you already own.
faq:
  - q: "Does Cozi have a wall display?"
    a: "No. Cozi is a phone and web app — there is no Cozi hardware and no TV or tablet display mode. What Cozi does give you is a shareable calendar URL, which any display that reads iCal feeds can subscribe to."
  - q: "How do I get my Cozi calendar URL?"
    a: "Sign in to Cozi on a computer, open Settings, and under the calendar section open 'Shared Cozi Calendars'. Switch the family member you want from Unshared to Shared, then use 'View or send Cozi URL' and copy it."
  - q: "Do I need Cozi Gold to share my calendar?"
    a: "No. The shared calendar URL is part of the free Cozi account. Cozi Gold removes the adverts and adds features like the month view and birthday tracking, but the outbound calendar feed is not one of them."
  - q: "Can I edit events from the wall screen?"
    a: "No, and that is deliberate. The Cozi URL is a read-only feed, so a display can show your events but never change them. You keep editing in Cozi on your phone, exactly as you do now, and the screen follows."
  - q: "How quickly does the display pick up a change made in Cozi?"
    a: "Cozi puts a change into the outbound feed straight away. After that it depends on how often the display refetches — DinkyDash checks every hour by default, and you can set that shorter or longer."
---

Cozi has no wall display of its own — it is a phone app, and there is no Cozi screen to buy.
But Cozi does hand out a **shareable calendar URL**, and any display that reads calendar feeds
can subscribe to it. So you can put the family's Cozi calendar on a screen in the kitchen
today, on a screen you already own.

Two parts: get the URL out of Cozi, then point something at it.

## Part 1 — get your Cozi calendar URL

Do this on a computer; the flow is easier to reach than in the app.

1. Sign in to [Cozi](https://my.cozi.com/) in a browser.
2. Open **Settings** from the menu on the left of your account page.
3. In the calendar section, open **Shared Cozi Calendars**. A window lists everybody in the
   family.
4. Switch the calendar you want from **Unshared** to **Shared**.
5. Press **View or send Cozi URL**, then **Copy Cozi URL**.

What you get is a long `https://` address on a `cozi.com` server, ending in `.ics`. The long
random string in the middle of it is the part that matters — that is the bit standing in for
a password.

**You do not need Cozi Gold for this.** The shared calendar URL is part of the free account.
Gold removes the adverts and adds the month view and birthday tracking; it does not gate the
outbound feed.

**Each family member is a separate feed.** If you want two children's calendars on the screen,
share each of them and copy both URLs. Most displays merge several feeds into one agenda, so
two links do not mean two lists.

**Treat the URL like a password.** There is no sign-in at the other end — the random string in
the address is what stands in for one — so anyone holding the link can read that calendar
until you set it back to Unshared. Keep it out of screenshots, shared documents and group
chats.

## Part 2 — put it on a screen

[DinkyDash](/) is free, open-source software that turns a screen you already own into a family
dashboard: today's events, a chore chart that rotates between people by itself, countdowns to
birthdays and holidays, and a short line written fresh every morning by AI. It runs in a
browser, so an old tablet, a spare monitor, a TV or a Raspberry Pi will all do.

Which screen? An [old iPad](/ipad-calendar-display/) or an [Android
tablet](/android-tablet-calendar-display/) is the cheapest good panel, a [Raspberry
Pi](/raspberry-pi-family-calendar/) the tidiest, and a [smart TV](/smart-tv-calendar-display/)
or [Fire TV](/fire-tv-calendar-display/) will show it on the big screen. There is one device it
does not work on, and [the Echo Show page](/echo-show-calendar-display/) says why.

![The DinkyDash board on a kitchen wall, showing today's events, chores and countdowns](/images/family-calendar-kitchen-wall.webp)

Point it at Cozi:

1. Open **Settings → Calendars → Add a calendar**.
2. Give it a name — "Cozi" or the child's name — and paste the URL into **Calendar link (iCal / ICS)**.
3. Press **Test calendar link**. It reports how many events it found and what the next one is,
   so you know it works before you save.
4. Repeat for each family member's feed you shared.

![Adding a calendar in DinkyDash's settings: a name, the iCal link, and a Check this link button](/images/settings-add-calendar.webp)

Everything stays where it is. You keep adding events in Cozi on your phone, because the feed
is read-only and a display cannot write back to it. The screen just shows what Cozi already
knows.

## What the screen adds that Cozi does not

Cozi is good at capture — you type an appointment into your phone on the way out of school
pickup. It is less good at the other half, which is everybody in the house knowing what is
happening without asking a parent to unlock a phone.

A wall screen fills that half, and once it is up it does a few things Cozi has no place to
show:

- **A chore chart that rotates.** List who is in the rota and it moves on one person a day,
  by itself. Nobody has to update a chart, and the screen — not a parent — is the one saying
  whose turn it is.
- **Countdowns.** Birthdays, Christmas, the school holidays. This is the feature children
  actually use, and it retires the "how many days until…" question.
- **A daily line.** A greeting and one line of copy, written each morning around the family's
  real day.

More on that combination on the [digital calendar and chore chart
page](/digital-calendar-and-chore-chart/).

## What it costs

Nothing, if you have a spare screen. DinkyDash is MIT-licensed and free to run yourself.

- **A tablet or monitor you already own** — $0. The cheapest way to find out whether the
  family will look at it.
- **A Raspberry Pi and a small touchscreen** — about $100 in parts, and the tidiest wall
  panel. The [Raspberry Pi build guide](/raspberry-pi-family-calendar/) has the parts list.

There is no subscription for the self-hosted version. The one running cost is the AI daily
line, which is a Claude API call once a day — roughly $0.13 a month — and the board works
without it.

Compare that with a dedicated display: a Skylight Calendar is $299.99 to $599.99 plus an
optional $79 a year, and a Hearth is $699 plus $9 a month. Both are nicely made. Neither
reads your Cozi calendar any better than a browser does. The full comparison is on the [best
digital family calendar page](/best-digital-family-calendar/).

## If Cozi is not the only calendar in the house

Most families end up with more than one. Work is often in Outlook, the school sends an iCal
subscription, and one parent lives in Google Calendar. All of them publish a link, and they
all merge into a single agenda on the screen:

- [Google Calendar](/google-calendar-ical-link/) — Settings → Integrate calendar → Secret
  address in iCal format
- [Apple iCloud Calendar](/icloud-calendar-link/) — turn on Public Calendar and copy the link
- [Outlook and Microsoft 365](/outlook-calendar-ics-link/) — publish the calendar, then take
  the ICS link

## Start here

The [setup guide](/getting-started/) walks the whole thing: run the board on your own computer
first, see your own family on it, then move it onto the screen that stays on the wall. Budget
an evening for the Raspberry Pi version; a spare tablet takes about ten minutes.

The code is on [GitHub](https://github.com/caspii/dinkydash) under an MIT licence.
