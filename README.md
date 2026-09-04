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
venv/bin/python -m pytest tests/ -q
```

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

Create `/home/pi/dinkydash/run_app.sh`:

```bash
#!/bin/bash
cd /home/pi/dinkydash
source venv/bin/activate
export FLASK_APP=app.py
flask run --host=0.0.0.0
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
python generate.py
flask run --host=0.0.0.0

# On the Pi
sudo systemctl status dinkydash      # Check service
sudo systemctl restart dinkydash     # Restart
journalctl -u dinkydash -f           # View logs
/home/pi/screen_control.sh on        # Screen on
/home/pi/screen_control.sh off       # Screen off
```

## Key files

| File | Purpose |
|------|---------|
| `generate.py` | Daily content generation (calendar, Claude API, JSON output) |
| `app.py` | Flask server that renders the dashboard |
| `config.yaml` | All configuration (people, calendar, chores, dates) |
| `config.example.yaml` | Template config to copy and customize |
| `templates/index.html` | Dashboard template (Bootstrap 5, optimized for 800x480) |
| `deploy_to_pi.sh` | Deployment script (rsync + service restart) |
| `.env` | API key (not in git) |
| `dashboard_data.json` | Generated daily content (not in git) |
| `PLAN.md` | Hosted MVP architecture and build phases |
| `STRATEGY.md` | Positioning, pricing, and SEO strategy |

## Contributing

Pull requests are welcome. Note that the codebase is mid-restructure into a monorepo that serves both the self-hosted and hosted builds — check [PLAN.md](PLAN.md) before starting anything structural, and open an issue first for larger changes.

Known rough edges are listed under "Known issues" in [CLAUDE.md](CLAUDE.md).

## License

MIT
