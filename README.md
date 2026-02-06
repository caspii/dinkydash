# DinkyDash

An AI-powered daily dashboard for families, running on a Raspberry Pi.

Website: [dinkydash.co](https://dinkydash.co)

Every morning at 6am, DinkyDash calls the Claude API to generate a fresh, personalized dashboard — with calendar events, chore rotations, countdowns, fun facts, and daily challenges — then displays it on a small screen at home.

## What the dashboard shows

- AI-generated daily greeting and headline
- Person cards for each family member
- Chore rotation badges (automatically rotated daily)
- Countdowns to birthdays, holidays, and special dates
- Calendar events pulled from Google Calendar
- Fun facts, daily challenges, and a pet corner

## How it works

```
[cron @ 6am] → generate.py → fetches Google Calendar
                            → builds prompt with family context
                            → calls Claude API
                            → saves dashboard_data.json

[browser]    → app.py       → reads dashboard_data.json
                            → renders dashboard on screen
```

---

## Getting started

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/settings/keys)
- A Google Calendar iCal URL (Google Calendar → Settings → Integrate calendar → Public address in iCal format)

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

Edit `config.yaml` with your family's details:

```yaml
location: "Berlin, Germany"

calendar_url: "https://calendar.google.com/calendar/ical/your-email/basic.ics"

calendar_filter_emails:
  - "spouse@example.com"

people:
  - name: "Alice"
    date_of_birth: "2015-03-15"
    sex: "female"
    image: "alice.jpg"
    email: "alice@example.com"
    interests: "drawing, dinosaurs"
  - name: "Bob"
    date_of_birth: "2017-06-20"
    sex: "male"
    image: "bob.jpg"
    interests: "legos, soccer"

pets:
  - name: "Buddy"
    type: "dog"
    image: "pet.jpg"

recurring:
  - title: "Set Table"
    emoji: "🍽"
    choices: ["Alice", "Bob"]
  - title: "Feed Pet"
    emoji: "🐕"
    choices: ["Bob", "Alice"]

special_dates:
  - title: "Christmas"
    emoji: "🎄"
    date: "12/25"
  - title: "Summer Vacation"
    emoji: "☀️"
    date: "07/01"

claude_model: "claude-sonnet-4-5-20250929"
max_tokens: 2048
data_file: "dashboard_data.json"
anthropic_api_key_env: "ANTHROPIC_API_KEY"
```

### 3. Add your API key

Create a `.env` file:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Add family photos

Copy photos to the `static/` directory. Filenames must match the `image` field in your config.

### 5. Generate and run

```bash
python generate.py        # Generate today's dashboard
flask run --host=0.0.0.0  # Start the server
```

Open http://localhost:5000 to see your dashboard. Use http://localhost:5000/preview for an 800x480 preview matching the Pi display.

---

## Configuration reference

| Field | Description |
|-------|-------------|
| `location` | Your city/country, used for context in AI content |
| `calendar_url` | Google Calendar public iCal URL |
| `calendar_filter_emails` | Only show events where these emails are attendees |
| `people[]` | Family members: `name`, `date_of_birth` (YYYY-MM-DD), `sex`, `image`, `email`, `interests` |
| `pets[]` | Pets: `name`, `type`, `image` |
| `recurring[]` | Rotating chores: `title`, `emoji`, `choices` (list of names, rotated daily) |
| `special_dates[]` | Countdowns: `title`, `emoji`, `date` (MM/DD) |
| `claude_model` | Which Claude model to use |
| `max_tokens` | Max response length |
| `data_file` | Path for generated JSON (default: `dashboard_data.json`) |
| `anthropic_api_key_env` | Name of the env var holding your API key |

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

Add this line to generate a fresh dashboard every morning at 6am:

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

## License

MIT
