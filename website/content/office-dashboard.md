---
title: DinkyDash for Offices and Shared Spaces
template: page.html
description: Use DinkyDash as an AI-powered information display for offices, co-working spaces, and shared areas.
---

DinkyDash was built for families, but the same concept works beautifully in offices, co-working spaces, classrooms, and any shared area where people need quick, glanceable information.

The idea is simple: a small screen that displays AI-generated, always-fresh content tailored to the people in that space.

## Why AI-generated dashboards work for offices

Static office dashboards get ignored. Someone puts up a screen with a Google Calendar and a motivational quote, and after a week nobody looks at it.

DinkyDash is different because the content changes completely every day. The AI writes new headlines, new facts, new challenges. People actually stop and read it because there's always something they haven't seen before.

## Four ways to use DinkyDash in shared spaces

**1. Team dashboard in the office kitchen**

Configure DinkyDash with your team members, shared calendar, and rotating responsibilities (who's buying coffee, who's cleaning the fridge, who's running standup). Every morning, the AI generates a fresh team dashboard with today's meetings, a fun icebreaker, and something to talk about at lunch.

**2. Classroom daily board**

Teachers can set up DinkyDash with student names, class events, and rotating classroom jobs. The AI writes a daily greeting, shows countdowns to field trips and holidays, rotates who's line leader or board eraser, and includes an age-appropriate fun fact.

**3. Co-working space welcome screen**

A DinkyDash in a co-working lobby can show community events, rotating "member spotlight" features, shared resource schedules, and daily conversation starters. It makes the space feel more personal without requiring someone to update content manually.

**4. Family business or workshop**

Small businesses with a shared break room can use DinkyDash to show the day's schedule, whose turn it is for various tasks, and inject a bit of fun into the workday with daily facts and challenges.

## Adapting DinkyDash for your space

DinkyDash is configured through a simple YAML file. To adapt it for an office or shared space:

- **People** become team members, students, or community members
- **Chores** become rotating responsibilities (meeting facilitator, kitchen cleanup, etc.)
- **Special dates** become deadlines, launches, team events
- **Calendar** connects to your team's shared Google Calendar
- **The AI prompt** can be customized to match the tone of your space — professional, playful, or somewhere in between

The AI adapts its writing style based on the context you give it. A classroom dashboard will sound different from an office dashboard because the prompt tells Claude about the setting and audience.

## Getting started

DinkyDash is free, open source, and runs on any Raspberry Pi with a screen. The setup takes an afternoon, and once it's running, it generates a new dashboard every morning on its own.

Check out the [GitHub repository](https://github.com/caspii/dinkydash) for setup instructions and configuration examples.
