---
title: "Turn an Old iPad Into a Family Calendar Display"
seo_title: "iPad Calendar Display: Use an Old iPad as a Wall Calendar"
template: page.html
description: An old iPad makes the best cheap family calendar display there is — always on, always charged, wall-mounted. Here is how to set one up with free, open-source software and no App Store account.
faq:
  - q: "Can I use an old iPad as a family calendar display?"
    a: "Yes, and it is the best cheap option there is. Any iPad that still runs Safari can show a wall calendar full screen. You need three settings: Auto-Lock set to Never, Guided Access to stop anyone leaving the page, and the charger left plugged in."
  - q: "How do I stop my iPad screen turning off?"
    a: "Settings, then Display & Brightness, then Auto-Lock, then Never. Auto-Lock offers Never only while the iPad is charging on some models, which is fine for a wall panel because it will be plugged in permanently anyway."
  - q: "How do I lock an iPad to one page?"
    a: "Guided Access. Turn it on under Settings, Accessibility, Guided Access, set a passcode, then triple-click the top or home button while the page is open. The iPad stays on that page until you triple-click and enter the passcode."
  - q: "Do I need an app from the App Store?"
    a: "No. DinkyDash is a web page, so it opens in Safari. Add it to the home screen and it runs full screen with no address bar, which is as close to an app as it needs to get."
  - q: "Will leaving an iPad plugged in all the time damage the battery?"
    a: "It ages the battery faster than normal use, yes. For a wall panel that hardly matters — the iPad is permanently on mains power, so a tired battery only shortens how long it survives a power cut. An old iPad doing this job is already past the point where its battery mattered."
---

**Yes — an old iPad is the best cheap family calendar display there is.** It has a good
screen, it charges over one cable, it already sits flat against a wall, and iOS has both
settings you need built in: a screen that never sleeps, and a lock that keeps everyone on one
page.

Here is the whole setup, with free and open-source software.

## What you need

DinkyDash is a **web page**, not an app you install. So there are two parts:

1. **Something to serve it.** A Raspberry Pi or an old computer on your Wi-Fi — free, MIT
   licensed, and about an evening's work. Or [start a free 14-day hosted trial](https://app.dinkydash.co/login), no card required.
2. **The iPad**, which is the screen. It opens that address in Safari.

Nothing goes through the App Store, and there is no Apple ID to sign in to.

![The DinkyDash board on a tablet in portrait, stacked into one column: today's events, whose turn each chore is, countdowns and the daily note](/images/family-calendar-tablet-board.webp)

Portrait or landscape both work. The board is a single column on a tall screen and two columns
on a wide one — it decides from the shape of the display, so an iPad standing upright looks
like the picture above and one lying on its side splits into two.

## Set it up

**1. Open the board in Safari.** Type the address DinkyDash is serving on. On your own
network that looks like `http://192.168.1.50:5000` — the address of the machine running it.

**2. Add it to the home screen.** Share button, then **Add to Home Screen**. This is the step
that matters: launched from the home screen the board runs **full screen**, with no address
bar and no Safari furniture, and it gets the DinkyDash icon and your family's name under it.

**3. Stop the screen sleeping.** Settings → **Display & Brightness** → **Auto-Lock** →
**Never**. On some iPads Never only appears while the iPad is charging, which is fine — a wall
panel is plugged in permanently.

**4. Lock it to the page.** Settings → **Accessibility** → **Guided Access**, switch it on and
set a passcode. Then open the board and triple-click the top button. The iPad now stays on the
board until somebody triple-clicks and types the passcode — which is what stops a five-year-old
ending up in Settings.

**5. Leave it plugged in.** A right-angled cable and an adhesive wall mount are the usual
answer. Turn the brightness down to about a third; it is a glanceable panel, not a film.

## Two things worth knowing

**The battery will age.** Permanently charging is harder on a battery than normal use. For a
wall panel it barely matters — the iPad is on mains power, so a tired battery only shortens
how long it survives a power cut. An iPad old enough to be doing this job is past the point
where its battery mattered.

**Very old iPads lose some spacing.** The board leans on one modern CSS feature — flexbox
`gap`, which arrived in Safari 14 — for the space between blocks. On anything older the board
still renders and still updates itself; the blocks just sit closer together than they should.
Nothing is hidden and nothing breaks.

## What ends up on the screen

- **Today's events**, merged from every calendar you add:
  [Google](/google-calendar-ical-link/), [iCloud](/icloud-calendar-link/),
  [Outlook](/outlook-calendar-ics-link/) and [Cozi](/cozi-calendar-display/) each publish a
  link, and each has its own page here with the steps.
- **A chore chart that rotates**, moving on one person a day by itself.
- **Countdowns** to birthdays, Christmas and the school holidays.
- **A daily line written each morning** by Claude, around your family's actual day.

The board reloads itself every five minutes using a plain HTML refresh, so it stays current
even in a browser with JavaScript switched off. There is nothing to tap and nothing to
maintain — you keep editing events in your normal calendar app, and the wall follows.

## What it costs

**Nothing, if the iPad is already in a drawer.** DinkyDash is free and MIT licensed with no
subscription for the self-hosted version. The one running cost is the daily line, which is a
Claude API call once a day — roughly $0.13 a month — and the board works without it.

For comparison, a Skylight Calendar is $299.99 to $599.99 plus an optional $79 a year. The
[best digital family calendar page](/best-digital-family-calendar/) has the full comparison.

## Other screens

- [Android tablet](/android-tablet-calendar-display/) — the same idea, and old ones are cheaper
- [Raspberry Pi](/raspberry-pi-family-calendar/) — the tidiest permanent panel, about $100
- [Smart TV](/smart-tv-calendar-display/) — works, but the screensaver fights you
- [Fire TV](/fire-tv-calendar-display/) — for the living-room television
- [Echo Show](/echo-show-calendar-display/) — the one that does not work, and why

## Start here

The [setup guide](/getting-started/) covers the other half: getting DinkyDash running, adding
your calendars, and pointing the iPad at it. The code is on
[GitHub](https://github.com/caspii/dinkydash) under an MIT licence.

Rather skip the setup? [Start a free 14-day hosted trial](https://app.dinkydash.co/login), no card required.
