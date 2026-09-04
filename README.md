# DinkyDash

The digital family calendar for screens you already own — a TV, an old tablet, or a Raspberry Pi.

Website: [dinkydash.co](https://dinkydash.co)

Every morning, DinkyDash merges your calendars into one agenda, works out whose turn each chore is, counts down to the next birthday, and asks Claude for a headline and one line of copy. Then it puts the lot on a screen at home — light or dark, sized to read from across the kitchen.

## Two ways to run it

**Self-hosted (this repo).** Free, MIT-licensed, runs on your own hardware with your own Anthropic API key. Setup takes an afternoon and some comfort with a terminal.

> Self-hosting is **community-supported**. Issues and pull requests are welcome, but there is no support commitment — if you need it to just work, use the hosted version.

**Hosted (in development).** Zero setup, $5/month or $39/year. [Join the waitlist.](https://fffwryhvses.typeform.com/to/yxMMhmFs) Built from this same repo — see [PLAN.md](PLAN.md).

## What the board shows

- Today's agenda, in time order, merged from as many iCal feeds as you like
- Whose turn each chore is — rotated daily, nothing to tick off
- Countdowns to birthdays, holidays and special dates
- An AI-written headline, and one line that is some days a fact, some days a
  challenge, some days about the dog
- Light or dark, chosen in the settings UI

Configure all of it from your phone at `/settings`, or by editing `config.yaml` directly — they are
the same file, and the UI keeps your comments.

## How it works

```
[cron @ 6am] → generate.py → merges every enabled iCal feed, in time order
                           → builds the prompt, calls Claude
                           → saves dashboard_data.json

[browser]    → app.py      → recomputes chores, countdowns and today's agenda
                           → renders the board
```

Only the headline and the written line come from the model. Ages, countdowns, chore turns and the
agenda are recomputed on every render, so if a morning's run fails the times and turns on the wall
are still today's — the board just labels the written line as older.

---

## Getting started

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/settings/keys)
- One or more iCal URLs (Google Calendar → Settings and sharing → Secret address in iCal format)

### 1. Clone and install

```bash
git clone https://github.com/caspii/dinkydash.git
cd dinkydash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Create your config

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your family's details — or start the app and use `/settings`:

```yaml
family_name: "The Wilsons"
timezone: "Europe/Berlin"     # decides when "today" rolls over
location: "Berlin, Germany"   # optional, flavours the daily line
theme: light                  # or dark

calendars:                    # as many as you like; merged into one agenda
  - label: "Sam's Google"
    url: "https://calendar.google.com/calendar/ical/…/basic.ics"
    enabled: true

people:
  - name: "Mia"
    date_of_birth: "2017-03-15"
    avatar_emoji: "🦖"
    avatar_color: purple
    interests: "dinosaurs, drawing, swimming"

pets:
  - name: "Biscuit"
    type: "dog"
    avatar_emoji: "🐕"

recurring:                    # rotated one person per day, in this order
  - title: "Set the table"
    emoji: "🍽"
    choices: ["Mia", "Theo"]

special_dates:                # repeat every year, so no year to set
  - title: "Christmas"
    emoji: "🎄"
    date: "12/25"

claude_model: "claude-haiku-4-5"
max_tokens: 1024
```

### 3. Add your API key

Create a `.env` file:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Generate and run

```bash
python generate.py        # write today's board
python app.py             # start the server
```

- http://localhost:5000 — the board
- http://localhost:5000/settings — configure it from a phone
- http://localhost:5000/preview — Pi, TV and tablet sizes side by side

Before the first generation the board shows a waiting screen; press **Rewrite now** in the settings
UI to fill it in.

### Running the tests

```bash
pip install -r requirements-dev.txt   # adds pytest; not needed on the Pi
python -m pytest tests/ -q
```

122 tests, well under a second. They cover leap years, timezone conversion, event ordering, chore
rotation, the stale-board logic, and the config round-trip.

---

## Running it day to day

### What happens each morning

At 6am cron runs `generate.py`. It fetches every enabled calendar, merges them into one
time-ordered agenda for the next 14 days, works out whose turn each chore is, and asks Claude for a
headline and one line of copy. The result is written atomically to `dashboard_data.json`.

The browser does the rest of the work on every render: ages, countdowns, whose turn it is, and
today's slice of the agenda are all recomputed from `config.yaml` and the current date. Only the
headline and the written line come from the model.

That split is why a failed run is not a disaster. Yesterday's fetch already reached 14 days ahead,
so today's times are still there and still right.

### The three states the board can be in

| What you see | What it means | What to do |
|---|---|---|
| The board, no banner | Today's run succeeded | Nothing |
| An amber banner across the top | Today's run failed or hasn't happened yet. Times, turns and countdowns are still today's; only the written line is older, and it is labelled | Check `generate.log`. Press **Rewrite now** in settings to retry |
| "Writing … first board" | Nothing has ever been generated | Press **Rewrite now**, or run `python generate.py` |

The board never blanks itself. A failed run leaves the previous one up rather than clearing the
screen, on the grounds that a stale kitchen board beats an empty one.

### Changing things

Everything is editable from a phone at `/settings` — people, pets, chores and their rotation order,
special dates, calendars, and whether the board is light or dark. It writes `config.yaml`, keeping
your comments and formatting, so editing the file by hand and editing through the UI are
interchangeable.

Config changes show up on the next page load. They do **not** re-run generation: the headline and
note are from this morning. Press **Rewrite now** if you want fresh copy immediately — each press is
one API call.

### Adding a calendar

Settings → Calendars → Add a calendar. In Google Calendar: **Settings and sharing** → the calendar
in the left sidebar → **Secret address in iCal format**. Paste it and press **Check this link** —
it will tell you how many events it found and what the next one is, rather than silently accepting
a URL that returns nothing.

Add one feed per person. A feed that stops answering is reported on the settings home page and is
skipped rather than emptying the board.

### Costs

One board a day on `claude-haiku-4-5` is roughly **$0.13 a month** — about 2,500 tokens in and 350
out. `claude-sonnet-5` is around three times that and writes better. Change it under
Settings → Family & system. **Rewrite now** costs the same as a scheduled run, so don't sit on it.

### When something looks wrong

**The board is a day behind.** Look at `generate.log`. The commonest causes are an expired API key,
no network at 6am, or a calendar that now 404s. Fix and press **Rewrite now**.

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

## Upgrading from an earlier version

Nothing to do to your config — it is migrated on load. But be aware:

- **New dependency.** `pip install -r requirements.txt` — `ruamel.yaml` is needed for the settings
  UI to write the config without destroying your comments.
- **`calendar_url` becomes `calendars`.** A single URL is migrated into a one-entry list. The
  settings UI will write the new shape back the first time you save.
- **`calendar_filter_emails` is gone.** It required every listed address to appear as an `ATTENDEE`
  on an event, which most personal calendar entries do not have — so it silently returned zero
  events. Add one feed per person instead. It is ignored with a warning in the log.
- **Photos are no longer used.** The board shows an agenda rather than person cards, so the `image:`
  fields and the JPEGs in `static/` do nothing. `avatar_emoji` and `avatar_color` replace them, and
  are used in the settings UI. Old keys are harmless if left in place.
- **Dates read as `25 December`,** not `December 25`.
- **The model default is now `claude-haiku-4-5`.** If your config pins
  `claude-sonnet-4-5-20250929`, it will keep using it — that model is dated, and newer models run
  adaptive thinking by default, which competes with `max_tokens` and can truncate the response.
  Either move to `claude-haiku-4-5` or `claude-sonnet-5`.

---

## Configuration reference

| Field | Description |
|-------|-------------|
| `family_name` | Shown in the corner of the board |
| `timezone` | IANA name. Decides when "today" rolls over and how event times are shown — set it even on a Pi whose clock is already local |
| `location` | Your city/country. Optional, gives the daily line some local flavour |
| `theme` | `light` or `dark` |
| `calendars[]` | iCal feeds: `label`, `url`, `enabled`. Merged into one agenda |
| `people[]` | `name`, `date_of_birth` (YYYY-MM-DD), `avatar_emoji`, `avatar_color`, `interests` |
| `pets[]` | `name`, `type`, `avatar_emoji` |
| `recurring[]` | Rotating chores: `title`, `emoji`, `choices` (names, one per day by day-of-year) |
| `special_dates[]` | Countdowns: `title`, `emoji`, `date` (MM/DD, repeats yearly) |
| `claude_model` | `claude-haiku-4-5` (~$0.13/month) or `claude-sonnet-5` for better prose |
| `max_tokens` | Max response length |
| `calendar_days_ahead` | How far ahead to fetch (default 14) |
| `history_days` | Days of past notes sent back so the model doesn't repeat itself |
| `data_file` | Path for the generated JSON |
| `content_history_file` | Path for the rolling note history |

Upgrading from an older config? A single `calendar_url` is migrated into `calendars` automatically,
and `calendar_filter_emails` is dropped — it required every listed address to appear as an
`ATTENDEE`, which most personal calendar events do not have, so it silently matched nothing. Use one
feed per person instead.

---

## Raspberry Pi deployment

This section covers setting up DinkyDash on a Raspberry Pi with a small display so it runs as a permanent family dashboard.

### What you need

- Raspberry Pi 4 (2GB+ RAM)
- MicroSD card (16GB+)
- DSI touchscreen display or HDMI monitor (800x480 recommended)
- Power supply
- Wi-Fi connection

### Step 1: Set up the Pi

Install Raspberry Pi OS (Debian Bookworm) using the [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Enable SSH and configure Wi-Fi during setup.

After first boot:

```bash
ssh pi@raspberrypi
sudo apt update && sudo apt upgrade -y
sudo apt install fonts-noto-color-emoji unclutter -y
```

The emoji font package is required for the dashboard to render emoji correctly.

### Step 2: Install DinkyDash

```bash
ssh pi@raspberrypi
mkdir -p /home/pi/dinkydash
```

From your local machine, copy the files:

```bash
rsync -az --exclude='venv' --exclude='.git' --exclude='__pycache__' \
  ./ pi@raspberrypi:/home/pi/dinkydash/
```

Or use the deploy script:

```bash
./deploy_to_pi.sh
```

Then on the Pi:

```bash
cd /home/pi/dinkydash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create the `.env` file on the Pi:

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." > /home/pi/dinkydash/.env
```

Test it:

```bash
python generate.py
flask run --host=0.0.0.0
```

### Step 3: Create the systemd service

Create `/etc/systemd/system/dinkydash.service`:

```ini
[Unit]
Description=DinkyDash Family Dashboard
After=network.target

[Service]
ExecStart=/home/pi/dinkydash/run_app.sh
User=pi
WorkingDirectory=/home/pi/dinkydash
Restart=always

[Install]
WantedBy=multi-user.target
```

`run_app.sh` ships with the repo and is what the unit runs:

```bash
#!/bin/bash
cd /home/pi/dinkydash
exec venv/bin/python app.py
```

Enable and start:

```bash
chmod +x /home/pi/dinkydash/run_app.sh
sudo systemctl daemon-reload
sudo systemctl enable dinkydash.service
sudo systemctl start dinkydash.service
```

### Step 4: Set up daily generation

```bash
crontab -e
```

Add this line to write a fresh board every morning at 6am. If a run fails, the previous board
stays up and labels itself — the screen never goes blank:

```cron
0 6 * * * cd /home/pi/dinkydash && source venv/bin/activate && python generate.py >> generate.log 2>&1
```

### Step 5: Set up kiosk mode

This makes Chromium launch fullscreen on boot, showing the dashboard.

Create `/home/pi/run.sh`:

```bash
#!/bin/sh
# Wait for Flask to be ready (max 60 seconds)
echo 'Waiting for DinkyDash...'
i=0
while [ $i -lt 60 ]; do
    if curl -s -o /dev/null -w '' http://localhost:5000/ 2>/dev/null; then
        echo 'Ready!'
        break
    fi
    i=$((i + 1))
    sleep 1
done

/usr/bin/chromium-browser \
  --kiosk \
  --password-store=basic \
  --disable-infobars \
  --enable-features=OverlayScrollbar \
  --disable-restore-session-state \
  --noerrdialogs \
  http://localhost:5000/
```

```bash
chmod +x /home/pi/run.sh
```

Edit `/home/pi/.config/lxsession/LXDE-pi/autostart`:

```
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@unclutter
@xset s off
@xset -dpms
@xset s noblank
@/home/pi/run.sh
```

This disables the screensaver, hides the mouse cursor, and launches the dashboard in kiosk mode.

### Step 6: Display rotation (optional)

If your display is mounted upside down, add to `/boot/firmware/config.txt`:

```ini
[all]
lcd_rotate=2
display_rotate=2
```

Note: On Bookworm, the boot config is at `/boot/firmware/config.txt`, not `/boot/config.txt`.

### Step 7: Screen power schedule (optional)

Save power by turning the display off at night.

Create `/home/pi/screen_control.sh`:

```bash
#!/bin/bash
if [ "$1" = "off" ]; then
    vcgencmd display_power 0
elif [ "$1" = "on" ]; then
    vcgencmd display_power 1
fi
```

```bash
chmod +x /home/pi/screen_control.sh
```

Add to crontab:

```cron
0 22 * * * /home/pi/screen_control.sh off
0 7 * * * /home/pi/screen_control.sh on
```

---

## Troubleshooting

Problems with the *board itself* — a stale banner, a calendar that stopped working, wrong times —
are covered under [When something looks wrong](#when-something-looks-wrong). This section is about
getting the Pi to boot into it.

**"localhost refused to connect" on boot** — Race condition where Chromium starts before Flask is ready. The `run.sh` script above handles this by waiting up to 60 seconds.

**GNOME Keyring password dialog** — Chromium tries to use GNOME keyring on auto-login. The `--password-store=basic` flag prevents this.

**Emoji not displaying** — Install the emoji font: `sudo apt install fonts-noto-color-emoji && fc-cache -fv`

**Wayland switch dialog on boot** — Bookworm may prompt to switch from X11 to Wayland. Fix with: `sudo raspi-config nonint do_wayland W1`

**Wi-Fi blocked** — Fresh Bookworm installs may have Wi-Fi soft-blocked: `sudo raspi-config nonint do_wifi_country DE && sudo rfkill unblock wifi`

---

## Quick reference

```bash
# Local development
source venv/bin/activate
python -m pytest tests/ -q           # run the tests
python generate.py                   # write today's board (costs a few cents)
python generate.py --date 2026-12-24 # any date, for checking a countdown
python app.py                        # board at /, settings at /settings

# On the Pi
sudo systemctl status dinkydash      # is it running
sudo systemctl restart dinkydash     # restart after a code change
journalctl -u dinkydash -f           # app logs
tail -f /home/pi/dinkydash/generate.log   # last night's generation
/home/pi/screen_control.sh on        # screen on
/home/pi/screen_control.sh off       # screen off
```

## Key files

| Path | Purpose |
|------|---------|
| `dinkydash/` | The engine. Pure functions plus the model call — no clock, no file reads |
| `dinkydash/context.py` | Ages, birthdays, countdowns, chore rotation |
| `dinkydash/calendars.py` | iCal fetch, parse, recurrence, merging feeds |
| `dinkydash/board.py` | Turns config + payload into what the board renders |
| `dinkydash/runner.py` | The daily cycle: fetch, generate, write. Used by cron and the UI |
| `web/` | Flask app — board, settings UI, templates |
| `web/templates/board.html` | The board itself, light and dark, all screen sizes |
| `generate.py` | Command-line skin over `runner.run` — this is what cron calls |
| `app.py` | Flask entry point |
| `config.yaml` | All configuration. The settings UI writes this same file |
| `config.example.yaml` | Template config, documenting every key |
| `tests/` | 122 tests. Run them before committing |
| `design/` | Mockups for the board and settings UI, with the reasoning |
| `deploy_to_pi.sh` | Deployment (rsync + service restart) |
| `.env` | `ANTHROPIC_API_KEY` (not in git) |
| `dashboard_data.json` | The generated payload (not in git) |
| `content_history.json` | Recent notes, so the model doesn't repeat itself (not in git) |
| `PLAN.md` | Hosted MVP architecture and build phases |
| `STRATEGY.md` | Positioning, pricing, and SEO |

## Contributing

Pull requests are welcome. Note that the codebase is mid-restructure into a monorepo that serves both the self-hosted and hosted builds — check [PLAN.md](PLAN.md) before starting anything structural, and open an issue first for larger changes.

Known rough edges are listed under "Known issues" in [CLAUDE.md](CLAUDE.md).

## License

MIT
