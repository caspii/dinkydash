---
title: "Turn an Android Tablet Into a Family Calendar Display"
seo_title: "Android Tablet Calendar Display: A Wall Calendar for $0"
template: page.html
description: A cheap or old Android tablet makes a proper wall-mounted family calendar — today's events, rotating chores and countdowns, on free open-source software with no subscription.
faq:
  - q: "Can I use an Android tablet as a wall calendar?"
    a: "Yes. Any Android tablet with a working screen and Chrome can show a family calendar full screen, permanently. You need the screen timeout set as long as it goes, or a kiosk browser app that overrides it, and the charger left plugged in."
  - q: "How do I stop an Android tablet screen turning off?"
    a: "Settings, Display, Screen timeout, and pick the longest option — usually 30 minutes, which is not enough on its own. The proper fix is Developer options, 'Stay awake while charging', or a kiosk browser app that holds the screen on."
  - q: "What is the best kiosk browser for a wall tablet?"
    a: "Fully Kiosk Browser is the one most people end up with. It holds the screen on, hides the Android furniture, locks the tablet to one address and can turn the screen off overnight. There is a free version and a one-off paid unlock."
  - q: "Do I need to install an app?"
    a: "No. DinkyDash is a web page, so Chrome is enough — add it to the home screen and it opens full screen. A kiosk browser is optional, and only worth it if you want the tablet locked down properly."
  - q: "How much does a tablet family calendar cost?"
    a: "Nothing if the tablet is already in a drawer. A used Android tablet good enough for this costs about $50 to $80. The software is free and open source, and the only running cost is the AI daily line at roughly $0.13 a month."
---

**Yes — and it is the cheapest good wall calendar you can build.** An Android tablet already
has a screen, a browser and a charging port, which is the entire hardware requirement. Old
ones are abundant and cost about $50 used, so this is the version of a $600 family display
that costs almost nothing.

## What you need

DinkyDash is a **web page**, not an app you install. So there are two parts:

1. **Something to serve it.** A Raspberry Pi or an old computer on your Wi-Fi — free, MIT
   licensed, and about an evening's work. Or [start a free 14-day hosted trial](https://app.dinkydash.co/login), no card required.
2. **The tablet**, which is the screen. It opens that address in Chrome.

Nothing goes through the Play Store, and there is no Google account to sign in to.

![The DinkyDash dashboard on a tablet in portrait, stacked into one column: today's events, whose turn each chore is, countdowns and the daily note](/images/family-calendar-tablet-board.webp)

The dashboard reads the shape of the screen: one column on a tall display, two on a wide one. So a
tablet standing upright looks like the picture above, and one lying on its side splits the
agenda and the chores into two columns.

## Set it up

**1. Open the dashboard in Chrome.** On your own network the address looks like
`http://192.168.1.50:5000` — the machine running DinkyDash.

**2. Add it to the home screen.** Chrome menu → **Add to Home screen**. Launched from there
the dashboard runs **full screen**, with no address bar, and gets the DinkyDash icon and your
family's name.

**3. Stop the screen sleeping.** Settings → **Display** → **Screen timeout** → the longest
option. That is usually 30 minutes, which is not enough on its own, so also turn on
**Stay awake while charging** in **Developer options**. (Developer options appear after
tapping **Build number** seven times under **About tablet**.)

**4. Leave it plugged in**, brightness down to about a third. A right-angled USB cable and an
adhesive wall mount are the usual answer.

## When you want it locked down properly

The steps above give you a tablet showing a calendar. They do not stop a child swiping out of
it, and Android's own screen timeout will fight you on some devices.

**[Fully Kiosk Browser](https://www.fully-kiosk.com/)** is what most people end up with. It
holds the screen on regardless of Android's timeout, hides the status and navigation bars,
locks the tablet to one address behind a PIN, and can switch the screen off overnight and back
on before breakfast. There is a free version, and a one-off paid unlock for the locking
features. Point it at the same address and you are done.

That is the only extra piece of software in this whole build, and it is optional.

## What ends up on the screen

- **Today's events**, merged from every calendar you add:
  [Google](/google-calendar-ical-link/), [iCloud](/icloud-calendar-link/),
  [Outlook](/outlook-calendar-ics-link/) and [Cozi](/cozi-calendar-display/) each publish a
  link, and each has its own page here with the steps.
- **A chore chart that rotates**, moving on one person a day by itself.
- **Countdowns** to birthdays, Christmas and the school holidays.
- **A daily line written each morning** by Claude, around your family's actual day.

The dashboard reloads itself every five minutes with a plain HTML refresh, so it keeps itself
current even on a browser with JavaScript switched off. Nothing to tap, nothing to maintain —
you keep editing events in your normal calendar app and the wall follows.

## What it costs

| | |
|---|---|
| A tablet already in a drawer | **$0** |
| A used Android tablet | ~$50–80 |
| DinkyDash | Free, MIT licensed, no subscription |
| The AI daily line | ~$0.13/month, and optional |

A Skylight Calendar is $299.99 to $599.99 plus an optional $79 a year for the same wall. The
[best digital family calendar page](/best-digital-family-calendar/) puts them side by side.

**Buying a tablet for this?** Screen size matters more than speed. The dashboard is a static page
that redraws every five minutes, so a slow tablet is fine; a small or dim one is not. Ten
inches or more, and check the screen is bright enough to read across a kitchen.

## Other screens

- [iPad](/ipad-calendar-display/) — the same idea, with Guided Access to lock it properly
- [Raspberry Pi](/raspberry-pi-family-calendar/) — the tidiest permanent panel, about $100
- [Smart TV](/smart-tv-calendar-display/) — works, but the screensaver fights you
- [Fire TV](/fire-tv-calendar-display/) — for the living-room television
- [Echo Show](/echo-show-calendar-display/) — the one that does not work, and why

## Start here

The [setup guide](/getting-started/) covers the other half: getting DinkyDash running, adding
your calendars, and pointing the tablet at it. The code is on
[GitHub](https://github.com/caspii/dinkydash) under an MIT licence.

Rather skip the setup? [Start a free 14-day hosted trial](https://app.dinkydash.co/login), no card required.
