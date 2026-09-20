---
title: DinkyDash for Offices and Shared Spaces
template: page.html
description: Using DinkyDash as a daily information screen for an office, classroom or co-working space — what it does, and what it won't do.
---

DinkyDash was built for families. It works in an office kitchen, a classroom or a co-working lobby too — but it helps to know what you're actually getting, because it's a family product wearing a different hat.

## What's on the screen

Today's shared calendar in time order, whose turn it is for the rotating jobs, countdowns to the dates that matter, and two lines written fresh each day by Claude: a headline and one note.

The note is one of two things — a fact, or a line about the pet if you've named one. That's the lot. There's no icebreaker generator and no conversation-starter feature.

## What it's actually good at

Static office screens get ignored. Someone puts up a shared calendar and a motivational quote, and by week two nobody's looking. The headline and the fact change every day, which is enough to make people glance — and while they're glancing they see the rota and the calendar.

The rota is the part that earns its place. Who's buying the coffee, who's cleaning the fridge, who's running stand-up: it moves to the next person when the date changes, with nothing to tick and nobody to chase. That's the failure mode it fixes. A shared spreadsheet needs somebody to maintain it, and that person gives up in about three weeks.

## Mapping it onto a team

The settings are built around a household, so you translate:

| The setting | What it becomes |
|---|---|
| **People** | Team members, students, members |
| **Chores** | Rotating jobs — facilitator, kitchen, stand-up |
| **Special dates** | Deadlines, launches, term dates |
| **Calendars** | Your team's shared calendar, via its iCal link |

## The honest limits

- **It thinks it's writing for a household.** Claude is told the name, who's in it and where they are. There's no tone setting, no audience setting and no custom prompt — none of those are settings. Self-host and you can edit the prompt in the source, but that's a code change, not configuration.
- **The note is a fact or the pet.** Nothing else, and nothing age-aware.
- **Everyone sees the same screen.** There's no per-person view and no sign-in on the display.

If you can live with those, it's a good shared-space screen. If you need per-team content or a tone dial, it isn't the tool and we'd rather say so.

## Getting started

**Hosted** — paste your team's calendar link and open the dashboard on whatever screen is nearest. Free for 14 days, and we don't ask for a card. [Start a trial](https://app.dinkydash.co/login).

**Self-hosted** — MIT-licensed and free for ever. It runs on anything that can serve a web page: an old laptop, a spare PC, a Raspberry Pi. [The setup guide](/getting-started/) has the commands, and you'll want your own Anthropic key, which costs well under a dollar a month.
