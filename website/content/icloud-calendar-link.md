---
title: "How to Get Your iCloud Calendar Link (Apple Calendar)"
seo_title: "iCloud Calendar URL: Get the Link to Your Apple Calendar"
template: page.html
description: Where to find the sharing URL for an Apple iCloud calendar, step by step on iCloud.com — what "Public Calendar" really means, why the link starts with webcal, and what to do when an old link stops working.
faq:
  - q: "How do I get the URL of my iCloud calendar?"
    a: "Sign in at icloud.com/calendar, hover over the calendar in the sidebar and open the information icon next to its name, switch on 'Public Calendar', then press Copy. That copies the calendar's sharing URL to your clipboard."
  - q: "Does 'Public Calendar' mean anyone can find my calendar?"
    a: "Not find, but read. Apple does not list it anywhere and it is not searchable, so nobody stumbles across it. But the link contains a long random string that works instead of a password, so anyone you give it to can read the whole calendar until you switch sharing off."
  - q: "Why does my iCloud calendar link start with webcal:// instead of https://?"
    a: "webcal:// is an old scheme that tells a computer to hand the link to a calendar app rather than a browser. It is the same address underneath. Most tools swap webcal:// for https:// automatically, DinkyDash included, so you can normally paste it exactly as Apple gives it to you."
  - q: "My iCloud calendar link stopped working. Why?"
    a: "Switching Public Calendar off and on again issues a different link, and the old one stops working for good. So does the calendar being deleted and recreated. If a link that used to work now returns nothing, go back to iCloud.com, copy the current link and paste the new one in."
  - q: "Can I get an iCloud calendar link on an iPhone?"
    a: "Yes — the Calendar app on a Mac, iPhone or iPad has the same Public Calendar switch and offers the link once it is on. Doing it in a browser at icloud.com/calendar is easier if the link then has to be pasted on a computer."
---

An iCloud calendar's sharing URL is behind the **information icon** next to the calendar's
name. Switch on **Public Calendar**, press **Copy**, and the address is on your clipboard.

Here are the steps, then the three things about this link that surprise people.

## Get the link

1. Open [iCloud Calendar](https://www.icloud.com/calendar/) in a browser and sign in with
   your Apple Account.
2. Hover over the calendar in the left sidebar, then click the **information icon** (ⓘ) next
   to its name. On a tablet, tap the icon instead.
3. Switch on **Public Calendar**.
4. Press **Copy**.

The Calendar app on a Mac, iPhone or iPad has the same **Public Calendar** switch beside each
calendar, and offers the link once it is on. The browser is easier if the link then has to go
into something on a computer.

The address looks like this:

```url
webcal://p00-caldav.icloud.com/published/2/xxxxxxxxxxxx
```

The real one has a long random string where the `xxxx` are, and the number after `p` varies
by which Apple server holds your calendar. Both are normal.

## "Public" does not mean listed

This is the part worth understanding before you paste the link anywhere.

Apple does not publish your calendar to a directory, and it is not searchable. Nobody finds
it by accident. But there is **no sign-in on the other end** — the long random string in the
URL is what stands in for a password. Anyone holding the link reads that whole calendar, for
as long as sharing stays on, and Apple gives you no way to see who has.

So: private enough to put on your own wall screen, not private enough to post in a group chat
or leave in a screenshot.

To take it back, switch **Public Calendar** off. Everything pointed at that link stops
working, and Apple emails anyone you shared it with to say so.

## Why the link starts with `webcal://`

`webcal://` is an old scheme whose only job is to tell your computer "hand this to a calendar
app, not a browser". Underneath it is an ordinary web address. Swap `webcal` for `https` and
it fetches the same file.

Most tools do that swap for you, so **paste it exactly as Apple gives it to you** and let the
other end sort it out. DinkyDash converts `webcal://` to `https://` on the way in and leaves
the rest of the address alone. What it will not accept is a plain `http://` link: the address
is a password, and `http` would put it on the network in the clear.

## When an old link stops working

An iCloud sharing link is not permanent, and this catches people out months later.

**Switching Public Calendar off and on again issues a different link.** The old one is dead —
not paused, dead. Same if the calendar is deleted and recreated, or recreated on a different
Apple Account.

So a wall display that has shown your calendar happily since spring can go blank one morning
because somebody turned sharing off and on while tidying up. The fix is always the same: go
back to iCloud.com, copy the link that is there now, and paste the new one in.

## One calendar per link

The link covers **one** calendar. A household with a personal calendar, a school calendar and
a partner's calendar needs three, one from each. Tools that read them normally merge several
into a single agenda — DinkyDash does, in time order, so the screen shows one day rather than
three lists.

Repeat the steps for each calendar in the sidebar.

## Put it on a screen

The reason to fetch the link is to get the calendar somewhere the whole family sees it,
without anybody having to unlock a phone.

[DinkyDash](/) is free, open-source software for exactly that: paste the link and today's
events appear on a wall screen, next to a chore chart that rotates by itself, countdowns to
birthdays and holidays, and a short daily line written each morning. There is no Apple sign-in
anywhere in it — the link is the entire connection, and it can only read.

To add it:

1. Open **Settings → Calendars → Add a calendar**.
2. Give it a name and paste the address into **iCal link**. A `webcal://` link is fine.
3. Press **Check this link**. It reports how many events it found and what the next one is,
   so you know before you save.

![Adding a calendar in DinkyDash's settings: a name, the iCal link, and a Check this link button](/images/settings-add-calendar.webp)

If the calendar you are pasting also holds work meetings, fill in **Only show events shared
with** and give the other parent's email address. Only events they are invited to reach the
screen; the rest never leave iCloud. The [getting started
guide](/getting-started/#personal-calendar) covers that properly.

## Other calendars

- [Google Calendar](/google-calendar-ical-link/) — Settings → Integrate calendar → Secret
  address in iCal format
- [Outlook and Microsoft 365](/outlook-calendar-ics-link/) — publish the calendar, then take
  the ICS link
- [Cozi](/cozi-calendar-display/) — Settings → Shared Cozi Calendars

Mix providers freely; they all end up as one agenda. The [full setup
guide](/getting-started/) is the next step — it starts the board on your own computer, then
moves it onto a screen that lives on the wall.
