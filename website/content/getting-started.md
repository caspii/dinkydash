---
title: Getting Started with DinkyDash
template: page.html
description: Step-by-step guide to setting up DinkyDash on your Raspberry Pi — from first install to a working family dashboard.
---

This guide walks you through setting up DinkyDash from scratch — first on your computer, then on a Raspberry Pi as a permanent family dashboard.

## What you need

- **Python 3.11+**
- **An Anthropic API key** — [get one here](https://console.anthropic.com/settings/keys)
- **A Google Calendar iCal URL** — In Google Calendar, go to Settings, find your calendar under "Integrate calendar", and copy the public iCal URL
- **A Raspberry Pi 4** (2GB+ RAM) with a small display (800x480 recommended) — for the permanent dashboard

## Step 1: Clone and install

```bash
git clone https://github.com/caspii/dinkydash.git
cd dinkydash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Step 2: Create your config

```bash
cp config.example.yaml config.yaml
```

Open `config.yaml` and fill in your family's details — or skip ahead, start the app, and do the whole thing from your phone at `/settings`. Here's what a typical config looks like:

```yaml
family_name: "The Wilsons"
timezone: "Europe/Berlin"     # decides when "today" rolls over
location: "Berlin, Germany"   # optional, flavours the daily line
theme: light                  # or dark

calendars:                    # as many as you like; merged into one agenda
  - label: "Alice's Google"
    url: "https://calendar.google.com/calendar/ical/your-email/basic.ics"
    enabled: true

people:
  - name: "Alice"
    date_of_birth: "2015-03-15"
    avatar_emoji: "🦖"
    avatar_color: purple
    interests: "drawing, dinosaurs"
  - name: "Bob"
    date_of_birth: "2017-06-20"
    avatar_emoji: "⚽"
    avatar_color: blue
    interests: "lego, football"

pets:
  - name: "Buddy"
    type: "dog"
    avatar_emoji: "🐕"

recurring:                    # rotated one person per day, in this order
  - title: "Set the table"
    emoji: "🍽"
    choices: ["Alice", "Bob"]
  - title: "Feed Buddy"
    emoji: "🦴"
    choices: ["Bob", "Alice"]

special_dates:                # repeat every year, so no year to set
  - title: "Christmas"
    emoji: "🎄"
    date: "12/25"
  - title: "Summer holidays"
    emoji: "☀️"
    date: "07/01"

claude_model: "claude-haiku-4-5"
max_tokens: 1024
```

### Config fields explained

- **family_name** — Shown in the corner of the board.
- **timezone** — IANA name, like `Europe/Berlin`. Decides when "today" rolls over and how event times are shown. Set it even on a Pi whose clock is already local.
- **location** — Your city and country. Optional; gives the daily line some local flavour.
- **theme** — `light` or `dark`.
- **calendars** — One entry per iCal feed, each with a `label`, a `url` and `enabled`. Add one per parent; they are merged into a single agenda.
- **people** — Name, date of birth (YYYY-MM-DD), an `avatar_emoji`, an `avatar_color`, and `interests` that feed the daily line.
- **pets** — Name, type, and an `avatar_emoji`.
- **recurring** — Daily chores that rotate automatically. Each chore lists the people it rotates between, in order.
- **special_dates** — Countdowns to holidays and other yearly events (MM/DD, no year).
- **claude_model** — `claude-haiku-4-5` costs roughly $0.13 a month. `claude-sonnet-5` writes better for about three times that.
- **max_tokens** — Maximum length of the AI response.

The settings UI adds a short `id` to each person, pet, chore, date and calendar the first time you open it. Leave them alone — they are how the UI tells one entry from another.

Upgrading from an older config? A single `calendar_url` becomes the first entry in `calendars` automatically. `calendar_filter_emails` is dropped, because it required every listed address to appear as an `ATTENDEE` and most personal calendar events have none — use one feed per person instead. Photos are gone; the board uses an emoji and a colour.

## Step 3: Add your API key

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Step 4: Generate and run

```bash
python generate.py        # Generate today's dashboard
python app.py             # Start the server
```

Open **http://localhost:5000** to see your dashboard. **http://localhost:5000/settings** is the settings UI — it writes the same `config.yaml`, keeps your comments, and works from a phone. **http://localhost:5000/preview** shows the board at all three screen sizes at once.

---

## Deploying to a Raspberry Pi

Once you've confirmed it works locally, here's how to set it up as a permanent dashboard on a Raspberry Pi.

### What you need

- Raspberry Pi 4 (2GB+ RAM)
- MicroSD card (16GB+)
- DSI touchscreen display or HDMI monitor (800x480 recommended)
- Power supply
- Wi-Fi connection

### Pi setup: Install the OS

Install **Raspberry Pi OS** (Debian Bookworm) using the [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Enable SSH and configure Wi-Fi during the setup process.

After first boot, SSH in and install the required system packages:

```bash
ssh pi@raspberrypi
sudo apt update && sudo apt upgrade -y
sudo apt install fonts-noto-color-emoji unclutter -y
```

The emoji font package is essential — without it, the dashboard won't render emoji.

### Pi setup: Install DinkyDash

From your local machine, copy the project files to the Pi:

```bash
rsync -az --exclude='venv' --exclude='.git' --exclude='__pycache__' \
  ./ pi@raspberrypi:/home/pi/dinkydash/
```

Or use the included deploy script:

```bash
./deploy_to_pi.sh
```

Then on the Pi, set up the virtual environment:

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

Test that everything works:

```bash
python generate.py
flask run --host=0.0.0.0
```

### Pi setup: Create the systemd service

This makes DinkyDash start automatically on boot.

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

Enable and start it:

```bash
chmod +x /home/pi/dinkydash/run_app.sh
sudo systemctl daemon-reload
sudo systemctl enable dinkydash.service
sudo systemctl start dinkydash.service
```

### Pi setup: Daily generation cron job

This generates a fresh dashboard every morning at 6am:

```bash
crontab -e
```

Add this line:

```
0 6 * * * cd /home/pi/dinkydash && source venv/bin/activate && python generate.py >> generate.log 2>&1
```

### Pi setup: Kiosk mode

This launches Chromium in fullscreen on boot so the Pi shows nothing but the dashboard.

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

Then edit `/home/pi/.config/lxsession/LXDE-pi/autostart`:

```
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@unclutter
@xset s off
@xset -dpms
@xset s noblank
@/home/pi/run.sh
```

This disables the screensaver, hides the mouse cursor, and launches the dashboard in kiosk mode on every boot.

### Pi setup: Display rotation (optional)

If your screen is mounted upside down, add to `/boot/firmware/config.txt`:

```ini
[all]
lcd_rotate=2
display_rotate=2
```

On Bookworm, the boot config lives at `/boot/firmware/config.txt` (not `/boot/config.txt`).

### Pi setup: Screen power schedule (optional)

Turn the display off at night and back on in the morning to save power.

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

```
0 22 * * * /home/pi/screen_control.sh off
0 7 * * * /home/pi/screen_control.sh on
```

---

## Troubleshooting

**"localhost refused to connect" on boot** — Chromium starts before Flask is ready. The `run.sh` script handles this by waiting up to 60 seconds, but if you wrote your own startup script, make sure it includes the wait loop.

**GNOME Keyring password dialog** — Chromium tries to use GNOME keyring on auto-login. The `--password-store=basic` flag in the kiosk script prevents this.

**Emoji not displaying** — You need the emoji font package: `sudo apt install fonts-noto-color-emoji && fc-cache -fv`

**Wayland switch dialog on boot** — Bookworm may prompt to switch from X11 to Wayland. Fix it with: `sudo raspi-config nonint do_wayland W1`

**Wi-Fi blocked after fresh install** — Bookworm soft-blocks Wi-Fi until you set a country: `sudo raspi-config nonint do_wifi_country DE && sudo rfkill unblock wifi`

---

## Quick reference

```bash
# Local development
source venv/bin/activate
python generate.py                    # today's board (one API call)
python generate.py --date 2026-12-24  # any date, for testing a countdown
python app.py                         # board at /, settings at /settings
python -m pytest tests/ -q            # the test suite

# On the Raspberry Pi
sudo systemctl status dinkydash      # Check service
sudo systemctl restart dinkydash     # Restart
journalctl -u dinkydash -f           # View logs
/home/pi/screen_control.sh on        # Screen on
/home/pi/screen_control.sh off       # Screen off
```

That's it. Once everything is set up, your family gets a brand new dashboard every morning — no maintenance required.
