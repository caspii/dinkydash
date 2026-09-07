# Running DinkyDash day to day

What the board does on its own, what the two buttons in the settings UI do, and what to
check when something looks wrong.

Setting it up for the first time? Use the
[getting started guide](https://dinkydash.co/getting-started/).

## What happens each day

Cron runs `generate.py --tick` every five minutes, and the tick does only what is owed.

**Every hour**, it re-fetches every enabled calendar and merges them into one time-ordered agenda
for the next 14 days. This costs nothing but a few HTTP requests, and it is what puts an
appointment added at 09:00 for 15:00 onto the board the same afternoon. Make that 15 minutes or
once a day under **Settings → How often it updates**. Fetching faster than the provider updates
buys nothing: Google's secret `.ics` link is cached at their end and can lag by hours.

**Once a day at 06:00**, on your own clock, it asks Claude for a headline and one line of copy —
the only part that costs money. The same page changes the hour. A brief that fails is simply
owed again five minutes later, so a network blip at dawn no longer means a day-old line.

Both write atomically to `dashboard_data.json`, and a refresh never touches the written line.

The browser does the rest of the work on every render: ages, countdowns, whose turn it is, and
today's slice of the agenda are all recomputed from `config.yaml` and the current date. Only the
headline and the written line come from the model.

That split is why a failed run is not a disaster. Yesterday's fetch already reached 14 days ahead,
so today's times are still there and still right.

## The three states the board can be in

| What you see | What it means | What to do |
|---|---|---|
| The board, no banner | Today's run succeeded | Nothing |
| An amber banner across the top | Today's brief failed or hasn't happened yet. Times, turns and countdowns are still today's; only the written line is older, and it is labelled | Nothing — the next tick retries. Check `generate.log` if it stays. Press **Rewrite now** in settings to force it |
| "Writing … first board" | Nothing has ever been generated | Press **Rewrite now**, or run `python generate.py` |

The board never blanks itself. A failed run leaves the previous one up rather than clearing the
screen, on the grounds that a stale kitchen board beats an empty one.

## Changing things

Everything is editable from a phone at `/settings` — people, pets, chores and their rotation order,
special dates, calendars, and whether the board is light or dark. It writes `config.yaml`, keeping
your comments and formatting, so editing the file by hand and editing through the UI are
interchangeable.

Config changes show up on the next page load. They do **not** re-run generation: the headline and
note are from this morning.

Two buttons on the settings home force the point:

- **Refresh calendars** re-fetches the feeds and nothing else. Free, and usually what you want
  after adding something to a calendar you don't want to wait for.
- **Rewrite now** does that *and* asks Claude for a new headline and line. One API call per press.

**How often it updates** sets both cadences — how often the calendars are fetched, and what time
the daily line is written, on your own clock. They are the `refresh_minutes` and `brief_time` keys,
so editing them by hand still works; the page is just the version you can reach from a phone. The
board's own reload follows: it redraws every five minutes, or every `refresh_minutes` if you set
something shorter than that.

## Keeping settings on your phone

Save `/settings` to your phone's home screen and it opens like an app, with the DinkyDash icon and
name rather than a bare URL. On an iPhone: **Share** → **Add to Home Screen**. On Android: the **⋮**
menu → **Add to home screen**. The settings page offers this itself the first time, until you say no.

The board does the same at `/` — worth doing if a tablet is your panel, because a saved board opens
full screen with no browser around it.

## Adding a calendar

Settings → Calendars → Add a calendar. Paste an iCal link and press **Check this link** — it will
tell you how many events it found and what the next one is, rather than silently accepting a URL
that returns nothing.

Where the link lives, per provider:

| Provider | Where to find the iCal link |
|---|---|
| **Google Calendar** | Settings and sharing → **Integrate calendar** → **Secret address in iCal format** |
| **Apple iCloud** | iCloud Calendar → share the calendar → **Public Calendar** → Copy Link. A `webcal://` link is fine — it is converted for you |
| **Outlook / Microsoft 365** | Settings → Calendar → **Shared calendars** → **Publish a calendar**, permission **Can view all details**, then copy the **ICS** link |

Nothing here signs you in to an account. DinkyDash fetches the link on a schedule and can only read.
The [getting started guide](https://dinkydash.co/getting-started/#find-your-calendar-link) has the
full steps and the gotchas.

Add one feed per person. A feed that stops answering is reported on the settings home page and is
skipped rather than emptying the board.

## Costs

One board a day on `claude-haiku-4-5` is roughly **$0.13 a month** — about 2,500 tokens in and 350
out. `claude-sonnet-5` is around three times that and writes better. Change it under
Settings → Family & system. **Rewrite now** costs the same as a scheduled run, so don't sit on it.

## When something looks wrong

**The board is a day behind.** Look at `generate.log`. The commonest causes are an expired API key
or no network. With the `--tick` cron line a single failure fixes itself five minutes later, so a
banner that is still there an hour on is a real fault. Fix it and press **Rewrite now**.

**An event I just added is not on the board.** Give it up to `refresh_minutes` (an hour by
default), plus your provider's own lag — Google's secret `.ics` link is cached at their end and can
take hours to show a change. Press **Rewrite now** if you cannot wait.

**One calendar is broken and its events are still showing.** That is deliberate. A feed that stops
answering keeps whatever it last gave us, because an event that vanishes is one nobody notices,
while a stale one is at least on the right day. Your other calendars carry on updating normally.
Fix or delete the feed under Settings → Calendars, where it is flagged.

**Times are off by an hour, or "today" rolls over at the wrong moment.** The timezone under
Settings → Family & system is what the engine works from, not the machine's clock. Set it even on a
Pi whose clock is already local.

**A calendar shows nothing.** Check it under Settings → Calendars — a failed feed says so. Apple
regenerates iCloud links when a calendar stops being shared, so a link that worked last month may
need replacing.

**The same fact twice in a fortnight.** `content_history.json` is what stops that; if you deleted
it, the model has nothing to avoid. It refills itself over the next few days.

**Emoji show as boxes.** `sudo apt install fonts-noto-color-emoji && fc-cache -fv`

---

Trouble getting a Raspberry Pi to *boot* into the board — Chromium starting before Flask,
a keyring dialog, a blanking screen, blocked Wi-Fi — is covered under
[Troubleshooting](https://dinkydash.co/getting-started/#troubleshooting) in the getting
started guide.
