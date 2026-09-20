---
title: The AI-Powered Family Dashboard
template: page.html
description: How DinkyDash uses AI to write a daily family dashboard with calendars, chores and countdowns — and which parts aren't AI at all.
---

If you've ever had a child ask "how many days until Christmas?" for the 47th time, DinkyDash was built for you.

It's a dashboard for a small screen somewhere your family walks past — the kitchen, the hallway, the top of the stairs. Once a day it rewrites itself. The rest of the time it just sits there, being right.

## What the AI actually writes

Worth being precise about, because most of the dashboard isn't AI at all.

Claude writes **two things**: a headline, and one line underneath it. That's the daily message, and it's written around your family's real day. Everything else works itself out from the date:

- **The countdowns** recalculate every time the page loads, so they can't drift.
- **The chore rota** moves to the next person when the date changes. Nothing to tick.
- **The agenda** comes straight from your calendars, merged into one list in time order.

That split is the whole trick. If the daily message fails to write one day, the times, turns and countdowns are still today's — and the dashboard says the line is old rather than pretending otherwise.

## A Tuesday in November

Your family walks past the screen. It shows:

- A headline: "Happy Tuesday! Only 3 more days until the weekend."
- Chore badges: Lily's turn for the dishes, Sam's turn to feed the dog
- [Countdowns](/birthday-countdown/): 28 days until Christmas, 5 days until Dad's birthday
- Today's calendar in time order, merged from both parents' feeds — school pickup at 15:00, swimming at 17:00, dinner at grandma's at 19:00
- A fact about space that Sam will probably repeat all day
- A line about the dog: "Buddy has claimed the warm patch by the radiator again"

The headline and those last two lines are Claude's. The rest is arithmetic.

## Why nobody has to feed it

Every other family calendar needs somebody to keep it current. Someone ticks the chores off, someone updates the ages, someone remembers to change the rota. That person gives up around week three, and then the wall is lying.

DinkyDash has nothing to tick. The rota advances on the date whether anyone's looking or not, and a birthday countdown that says 28 days is doing the sum fresh, not reading a number somebody typed in November.

## Two ways to run it

**We host it.** Paste a calendar link, open your dashboard on any screen with a browser, and leave it there. Free for 14 days, and we don't ask for a card. [Start a trial](https://app.dinkydash.co/login).

**You host it.** It's MIT-licensed and free for ever. You'll need something to serve it — an old laptop, a spare PC, a [Raspberry Pi](/raspberry-pi-family-calendar/) — and your own Anthropic key, which runs well under a dollar a month. [The setup guide](/getting-started/) has the commands.

Same code either way. The only difference is who keeps it running.

## It's private, both ways

There's no camera and no microphone, because it's a web page.

Run it yourself and your family's details stay on your machine. The one thing that leaves is the day's agenda, which goes to Anthropic under your own key so Claude can write the line. Let us host it and we store your settings so we can build the dashboard each day, and that same agenda goes to Anthropic under ours.

Nothing is sold, there are no adverts, and [the privacy policy](/privacy/) names every company involved. It's a short list.
