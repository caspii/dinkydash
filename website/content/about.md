---
title: About DinkyDash
template: page.html
description: DinkyDash is an open-source, AI-powered family dashboard that runs on a Raspberry Pi.
---

DinkyDash is an open-source daily dashboard for families. Every morning, it calls the Claude AI to generate a completely fresh, personalized dashboard based on your family's calendar, chores, and context — then displays it on a small screen at home.

## Why an AI dashboard?

Most family dashboards show static information that someone has to update manually. DinkyDash takes a different approach: you describe your family once, and AI does the rest.

Every morning at 6am, DinkyDash automatically:

- Fetches your Google Calendar events
- Figures out whose turn it is for each chore
- Calculates countdowns to birthdays, holidays, and special dates
- Sends all of this to Claude, which writes a personalized dashboard

The result is a dashboard that feels alive. It knows it's someone's birthday week. It writes different fun facts and daily challenges every day. It adapts to what's actually happening in your family's life.

## What the dashboard shows

- **A daily headline** — a cheerful, AI-written greeting for your family
- **Person cards** — each family member with their photo and key info
- **Chore rotation** — who does what today, automatically rotated
- **Countdowns** — days until birthdays, holidays, vacations, and special events
- **Calendar events** — what's happening today, pulled from Google Calendar
- **Fun facts and challenges** — something new to read every morning
- **Pet corner** — because pets are family too

## How it's built

DinkyDash is a simple two-script system:

1. **generate.py** runs on a cron job each morning. It fetches your calendar, builds a rich prompt, calls the Claude API, and saves the result as a JSON file.
2. **app.py** is a tiny Flask server that reads the JSON and renders it as a dashboard in the browser.

The whole thing runs on a Raspberry Pi with a small display. No cloud accounts, no subscriptions, no app to install.

## The stack

- Python 3 with Flask
- Anthropic Claude API for daily content generation
- Google Calendar (iCal) for event data
- YAML for all configuration
- Designed for Raspberry Pi with a small display (800x480)

## Open source

DinkyDash is MIT-licensed and available on [GitHub](https://github.com/caspii/dinkydash). It was created by [Caspar](https://casparwre.de).
