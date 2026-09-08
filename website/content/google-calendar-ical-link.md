---
title: "How to Get Your Google Calendar iCal Link (the Secret Address)"
seo_title: "Google Calendar iCal Link: Find the Secret Address"
template: page.html
description: Where to find the private iCal URL for a Google Calendar, in four steps on a computer — plus what the link is, why it has to stay private, and how to reset it if it leaks.
faq:
  - q: "Where is the iCal link in Google Calendar?"
    a: "Open Google Calendar in a browser on a computer, go to Settings, pick the calendar under 'Settings for my calendars', open 'Integrate calendar', and copy the address under 'Secret address in iCal format'. The phone apps do not show it."
  - q: "Is the Google Calendar secret address safe to share?"
    a: "No. Anyone who has it can read that whole calendar, for as long as the address exists, and there is no way to see who has used it. Treat it like a password. If it leaks, press Reset next to it in Google Calendar — that issues a new address and kills the old one."
  - q: "What is the difference between the public address and the secret address?"
    a: "The public address only works if you have also made the calendar public, which lists it for anyone. The secret address works on a private calendar, because the long random string in the URL is what stands in for signing in. For a wall display you want the secret address."
  - q: "Why can I not see 'Secret address in iCal format'?"
    a: "On a work, school or organisation account an administrator can switch secret addresses off for everyone. If the section is missing, that is usually why. A personal Google account is the simplest way round it."
  - q: "Does the iCal link update automatically?"
    a: "Yes. It is a live feed, not a one-off export — whatever you change in Google Calendar shows up the next time something fetches the address. It is read-only, so nothing that reads it can change your calendar."
---

Google Calendar's iCal link is called the **secret address**, and it lives under
**Settings → your calendar → Integrate calendar**. You can only get it in a browser
on a computer; the phone apps do not show it.

Here are the four steps, then what the link is and why it needs looking after.

## Get the link

1. Open [Google Calendar](https://calendar.google.com/) in a browser on a computer.
2. Open **Settings** — the gear in the top right corner, then **Settings** in the menu.
3. In the left sidebar, under **Settings for my calendars**, choose the calendar you want.
   (You can also get here by hovering over the calendar in the main sidebar and picking
   **Settings and sharing** from its ⋮ menu.)
4. Scroll down to **Integrate calendar** and copy the address under
   **Secret address in iCal format**.

That is the whole job. The address looks like this:

```url
https://calendar.google.com/calendar/ical/you%40gmail.com/private-xxxx/basic.ics
```

The real one has a long random string where `private-xxxx` is. Everything after
`private-` is the part that matters.

## What the link actually is

It is a **live, read-only feed** of that one calendar. Anything that can read it sees your
events update as you change them, and nothing that reads it can write back. That is why a wall
display, a dashboard or another calendar app asks for this rather than for your password:
you are handing over a view, not an account.

It is also why the address is long and random. **The random part is the login.** There is no
sign-in step, so whoever holds the URL is treated as you, indefinitely, and Google has no way
to tell you who has used it. Treat the address exactly like a password:

- Do not put it in a shared document, a screenshot, a public issue or a group chat.
- If it does get out, open the same **Integrate calendar** screen and press **Reset** next to
  the secret address. Google issues a new one and the old one stops working immediately —
  which also means anything you had pointed at the old address needs the new one.

## One calendar per link

The secret address covers **one** calendar, not your whole account. If your family's events
are spread across a personal calendar, a school calendar and a partner's calendar, you need
one address from each. Most tools that read them, DinkyDash included, merge several feeds
into a single agenda.

Repeat the four steps for each calendar in the **Settings for my calendars** list.

## If the section is not there

Two things hide it:

- **A work, school or organisation account.** An administrator can switch external sharing
  off for everyone, and when they have, the **Secret address in iCal format** row simply is
  not on the page. There is no way round it from your side. A personal Google account is the
  usual answer — make a family calendar there and invite your work account to the events that
  matter.
- **A calendar somebody else owns.** A calendar shared *with* you has no secret address of
  yours to hand out. Ask the owner for theirs, or use their public address if the calendar is
  a public one.

## Put it on a screen

A calendar link on its own does nothing. The point of getting it is to show the calendar
somewhere the family will actually look — a tablet in the hall, an old TV, a small screen on
the kitchen wall.

[DinkyDash](/) is free, open-source software that does exactly that: paste the link and it
shows today's events on a wall screen, alongside a rotating chore chart, birthday countdowns
and a daily line written each morning. There is no Google sign-in — the link is the whole
connection, and it can only read.

To add it:

1. Open **Settings → Calendars → Add a calendar**.
2. Give it a name and paste the address into **iCal link**.
3. Press **Check this link**. It says how many events it found and what the next one is, so
   you know it works before you save.

![Adding a calendar in DinkyDash's settings: a name, the iCal link, and a Check this link button](/images/settings-add-calendar.webp)

If your own calendar also holds work meetings you would rather not put on the kitchen wall,
fill in **Only show events shared with** and give the other parent's email address. Only the
events they are invited to reach the screen. The [getting started
guide](/getting-started/#personal-calendar) has the detail.

## Two things people get wrong

**An `http://` version of the address.** Some older guides suggest editing the URL by hand.
Do not — the address is a password, and plain `http` puts it on the network in the clear.
DinkyDash refuses `http` links for that reason. Copy what Google gives you.

**Confusing it with the public address.** The same **Integrate calendar** screen also lists a
public address and an embed code. Those only work on a calendar you have made public, which
means anybody can find it. The secret address is the one that works on a private calendar,
and it is the one you want.

## Other calendars

- [Apple iCloud Calendar](/icloud-calendar-link/) — turn on Public Calendar and copy the link
- [Outlook and Microsoft 365](/outlook-calendar-ics-link/) — publish the calendar, then take
  the ICS link
- [Cozi](/cozi-calendar-display/) — Settings → Shared Cozi Calendars

Any of them, or several at once, merge into one agenda. The [full setup
guide](/getting-started/) takes it from here — running the board on your computer first, then
moving it onto a screen that stays on the wall.
