---
title: "How to Publish an Outlook Calendar and Get the ICS Link"
seo_title: "Publish an Outlook Calendar: Get the ICS Link"
template: page.html
description: How to publish a calendar in Outlook on the web and copy its ICS link — which permission level to pick, why the HTML link is the wrong one, and what to do when your work account has publishing switched off.
faq:
  - q: "How do I get an ICS link from Outlook?"
    a: "Open Outlook on the web, go to Settings, then Calendar, then Shared calendars. Under 'Publish a calendar', pick the calendar, set the permission to 'Can view all details', and press Publish. Two links appear — copy the ICS one."
  - q: "What is the difference between the ICS link and the HTML link?"
    a: "The HTML link opens a read-only web view of your calendar in a browser. The ICS link is a machine-readable feed that other calendar apps and displays subscribe to. For anything that has to show your events, you want the ICS link."
  - q: "Which permission level should I choose when publishing?"
    a: "'Can view all details'. The lesser options publish only free/busy blocks, so the feed arrives with no event titles — and titles are the whole point of a calendar on a wall."
  - q: "Why is 'Publish a calendar' missing or greyed out in my Outlook?"
    a: "On a work or school Microsoft 365 account, an administrator controls whether calendar publishing is allowed, and it is off by default in many organisations. If the section is missing or does nothing, that is why. A personal Outlook.com account has it switched on."
  - q: "How often does a published Outlook calendar update?"
    a: "It is a live feed, so the file always reflects your calendar at the moment it is fetched. How quickly a change reaches a display depends on how often that display refetches — DinkyDash checks every hour by default."
---

Outlook calls this **publishing**. In Outlook on the web, go to **Settings → Calendar →
Shared calendars**, publish the calendar under **Publish a calendar**, and copy the **ICS**
link — not the HTML one.

Here are the steps, then the two choices on that screen that decide whether it works.

## Get the link

1. Open [Outlook on the web](https://outlook.live.com/calendar/) and switch to the calendar.
2. Open **Settings** (the gear in the top right), then **Calendar**, then
   **Shared calendars**.
3. Under **Publish a calendar**, choose the calendar you want to publish.
4. Set the permission to **Can view all details**.
5. Press **Publish**.
6. Two links appear. Copy the **ICS** one.

The address looks like this:

```url
https://outlook.office365.com/owa/calendar/xxxxxxxx@example.com/xxxxxxxx/calendar.ics
```

A personal Outlook.com account produces a slightly different host; a Microsoft 365 work
account produces the shape above. Either is fine.

## The two choices that matter

**Permission: "Can view all details".** The other options publish only *when* you are busy,
with no titles and no locations. That is useful for scheduling with colleagues and useless on
a kitchen wall — a screen that says "Busy, 15:00" tells nobody anything. Pick the full-detail
option or the display will look broken when it is working exactly as configured.

**ICS, not HTML.** Outlook gives you both:

| Link | What it is for |
|---|---|
| **HTML** | Opens a read-only view of your calendar in a browser, for a human to look at |
| **ICS** | A machine-readable feed, for another calendar app or a display to subscribe to |

Anything that has to *show your events somewhere else* needs the ICS link. Paste the HTML one
into a dashboard and it will fail to parse, because it is a web page rather than a calendar.

## Publishing is a password in a URL

Once published, the ICS link works for whoever holds it. There is no sign-in at the other end
— the long random string in the address is what stands in for one. Anyone with the URL reads
your calendar at full detail, for as long as it stays published, and Microsoft does not tell
you who has.

So treat it the way you would treat a password: keep it out of shared documents, screenshots,
public issues and group chats. To take it back, return to **Shared calendars** and stop
publishing. The link dies immediately, and republishing gives you a different one — so
anything pointed at the old address needs updating.

## When "Publish a calendar" is not there

On a **work or school Microsoft 365 account**, calendar publishing is an administrator
setting, and plenty of organisations leave it off. When it is off, the section is missing or
does nothing at all, and there is no way round it from your side.

Two things that do work:

- **Use a personal Outlook.com account** for the family calendar, and invite your work account
  to the events that matter.
- **Ask the administrator.** It is a per-organisation policy in the Exchange admin centre, and
  in a small business the answer is sometimes just yes.

## One calendar per link

Publishing covers **one** calendar. A household running a personal calendar, a school calendar
and a partner's calendar publishes each one and gets three links. Most displays merge several
feeds into a single agenda — DinkyDash sorts them into one day in time order rather than
showing three separate lists.

## Put it on a screen

The reason to publish is usually to get the calendar somewhere everyone can see it without
opening a laptop.

Which screen? An [old iPad](/ipad-calendar-display/) or an [Android
tablet](/android-tablet-calendar-display/) is the cheapest good panel, a [Raspberry
Pi](/raspberry-pi-family-calendar/) the tidiest, and a [smart TV](/smart-tv-calendar-display/)
or [Fire TV](/fire-tv-calendar-display/) will show it on the big screen. There is one device it
does not work on, and [the Echo Show page](/echo-show-calendar-display/) says why.

[DinkyDash](/) is free, open-source software for that: paste the ICS link and today's events
appear on a wall screen, beside a chore chart that rotates by itself, countdowns to birthdays
and holidays, and a short line written fresh each morning. There is no Microsoft sign-in in
it — the published link is the whole connection, and it can only read.

To add it:

1. Open **Settings → Calendars → Add a calendar**.
2. Give it a name and paste the ICS address into **Calendar link (iCal / ICS)**.
3. Press **Test calendar link**. It says how many events came back and what the next one is,
   before you save.

![Adding a calendar in DinkyDash's settings: a name, the iCal link, and a Test calendar link button](/images/settings-add-calendar.webp)

If the calendar also holds work meetings you would rather keep off the kitchen wall, fill in
**Only show events shared with** and give the other parent's email address — only events they
are invited to reach the screen. The [getting started
guide](/getting-started/#personal-calendar) has the detail.

## Other calendars

- [Google Calendar](/google-calendar-ical-link/) — Settings → Integrate calendar → Secret
  address in iCal format
- [Apple iCloud Calendar](/icloud-calendar-link/) — turn on Public Calendar and copy the link
- [Cozi](/cozi-calendar-display/) — Settings → Shared Cozi Calendars

They mix freely and end up as one agenda. The [full setup guide](/getting-started/) is the
next step — it runs the dashboard on your own computer first, then moves it onto a screen that
stays on the wall.
