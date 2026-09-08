---
title: Getting Started with DinkyDash
template: page.html
description: Set up DinkyDash from scratch — first on your computer, then as a permanent wall dashboard on a Raspberry Pi running the current Raspberry Pi OS.
---

This guide takes you from nothing to a working family dashboard. You start on your own computer, see the board, then move it onto a Raspberry Pi that shows it on the wall and refreshes itself every morning.

You do not need an Anthropic API key to try it — there is a no-key preview in step 3. You only need a key for the AI-written daily line, which runs once a day.

## What you need

- **Python 3.11 or newer.**
- **One or more calendar links** in iCal format. Google Calendar, Apple iCloud Calendar and Outlook all give you one — see [find your calendar link](#find-your-calendar-link) below for the steps. Treat that link like a password: anyone who has it can read that calendar.
- **An Anthropic API key** ([get one here](https://console.anthropic.com/settings/keys)) — only for the daily headline and one line of copy. You can run the whole board without it first.
- **A Raspberry Pi** with a small screen, for the permanent version. A Pi 4 with 2GB of RAM and the official 7-inch display (800×480) is the easy path. Hardware details are on the [Raspberry Pi build guide](/raspberry-pi-family-calendar/).

---

<h2 id="find-your-calendar-link">Find your calendar link</h2>

DinkyDash reads calendars over iCal, the sharing format every calendar app speaks. **Google Calendar, Apple iCloud Calendar and Outlook all give you an iCal link**, and any of the three works. Add one per person and they merge into a single agenda.

This is a link, not a login. DinkyDash never signs in to your Google, Apple or Microsoft account — it fetches the link on a schedule, and can only read.

### Google Calendar

1. Open [Google Calendar](https://calendar.google.com/) in a browser on a computer. The phone apps do not expose this.
2. In the left sidebar, hover over the calendar, then open its menu (⋮) → **Settings and sharing**.
3. Scroll down to **Integrate calendar**.
4. Copy the address under **Secret address in iCal format**.

If the address ever leaks, **Reset** on that same screen issues a new one and kills the old. On a work or school account an administrator can switch secret addresses off altogether — if the section is missing, that is why, and a personal calendar is the way round it.

### Apple iCloud Calendar

1. Open [iCloud Calendar](https://www.icloud.com/calendar/) in a browser and sign in. You can also do this from the Calendar app on a Mac, iPhone or iPad.
2. Hover over the calendar in the sidebar and open its share options.
3. Switch on **Public Calendar**, then **Copy Link**.
4. **Paste it as it is.** A `webcal://` link is converted to `https://` for you — the rest of the address stays exactly as it is. Links have to be https; a plain `http://` feed is refused, because it would send the secret address across the network in the clear.

"Public" here means a long random address rather than a listed page, but anyone holding it can read that calendar — keep it to yourself. Turning sharing off and on again issues a *different* link, and the old one stops working, so the board will need the new one.

### Outlook and Microsoft 365

1. Open [Outlook on the web](https://outlook.live.com/calendar/) and go to **Settings** (the gear) → **Calendar** → **Shared calendars**.
2. Under **Publish a calendar**, choose the calendar you want.
3. Set the permission to **Can view all details**. The lesser options hide event titles, and titles are what the board shows.
4. Press **Publish**. Two links appear — copy the **ICS** one, not the HTML one.

### Then paste it in

Put the link in `config.yaml` under `calendars:` (step 2 below), or add it later from the settings page: **Settings → Calendars → Add a calendar**, then press **Check this link** to confirm it works before you save.

Whichever provider it came from, treat the link like a password. Anyone who has it can read that calendar, for as long as it exists, and there is no way to see who has.

<h3 id="personal-calendar">A personal calendar with work in it</h3>

You do not need a separate family calendar. If your own calendar also holds work meetings and private appointments, paste it anyway, then fill in **Only show events shared with** on that calendar with the other parent's email address. Only the events they are invited to, or that they organised, reach the board. Everything else stays off it, and is never sent to Claude.

Two things to get right:

- **Use the address on the invitation.** Google, Apple and Outlook all record guests by email address, so it has to be the one you actually invite them with. If they have two, list both with a comma between them.
- **Press Check this link before you save.** With a guest list filled in, it says how many events get through out of how many, and warns you if none do. That usually means the address is not the one on the invitations, or that nothing in the next fortnight has been shared yet.

Each calendar has its own list, so the school calendar, which has no guests, is left alone. Saving a calendar clears whatever was fetched from it before, so nothing from before the guest list lingers; the board picks it up again at the next refresh, or straight away if you press **Refresh calendars**. In `config.yaml` the same setting is `shared_with`, a list of addresses under that calendar.

---

## Part 1 — Run it on your computer

### Step 1: Get the code

```bash
git clone https://github.com/caspii/dinkydash.git
cd dinkydash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The `venv` is a private folder for DinkyDash's Python packages, so they do not touch the rest of your system. Recent Raspberry Pi OS and macOS both block installing packages without one.

### Step 2: Make your config

```bash
cp config.example.yaml config.yaml
```

`config.yaml` is the single source of truth. You can edit it by hand now, or leave it and do everything from the settings page in step 5 — they write the same file. A typical config looks like this:

```yaml
family_name: "The Wilsons"
timezone: "Europe/Berlin"     # decides when "today" rolls over
location: "Berlin, Germany"   # optional, flavours the daily line
theme: light                  # or dark

calendars:                    # as many as you like; merged into one agenda
  - label: "Alice's calendar"
    url: "https://calendar.google.com/calendar/ical/you%40gmail.com/private-xxxx/basic.ics"
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

The example URL above is deliberately fake. Paste your own iCal address in its place — [find your calendar link](#find-your-calendar-link) has the steps for Google, Apple and Outlook. Add one calendar entry per person, and they all merge into a single agenda.

### Step 3: See the board with no API key

You can look at the real board before you get an API key. This costs nothing and calls no service:

```bash
python sample_board.py     # writes a board for today, with a canned headline
python app.py              # starts the server
```

Open **http://localhost:5000**. The chore turns, ages and countdowns are computed from the `config.yaml` you just wrote, so edit it, reload, and you see your own family. Only the headline and the one written line are fake. `sample_board.py` refuses to overwrite a real board, so it is safe to leave in place.

Stop the server with `Ctrl+C` when you are done looking.

### Step 4: Add your Anthropic API key

The daily line comes from the Claude API. Create a file called `.env` in the project folder:

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

`.env` holds the key and nothing else. The key never goes in `config.yaml`, because that file is meant to be shared and edited.

### Step 5: Generate the real board and run it

```bash
python generate.py        # fetches calendars, calls Claude, writes today's board
python app.py             # starts the server
```

Now these three pages are live:

- **http://localhost:5000** — the board.
- **http://localhost:5000/settings** — change people, chores, calendars, colours and the timezone from a phone. It writes `config.yaml` and keeps your comments.
- **http://localhost:5000/preview** — the board at the Pi, TV and tablet sizes at once, handy for a layout change.

#### Config fields explained

| Field | What it does |
|---|---|
| `family_name` | Shown in the corner of the board. |
| `timezone` | An IANA name like `Europe/Berlin`. Decides when "today" rolls over and how event times read. Set it even on a Pi whose clock is already local — the engine works from this, not the machine clock. |
| `location` | Your city and country. Optional; gives the daily line local flavour. |
| `theme` | `light` or `dark`. |
| `calendars` | One entry per iCal feed: a `label`, a `url` (the secret iCal address) and `enabled`. Merged into one agenda. An optional `shared_with` list of email addresses shows only the events with one of those people as a guest or organiser. |
| `people` | `name`, `date_of_birth` (YYYY-MM-DD), an `avatar_emoji`, an `avatar_color`, and `interests` that feed the daily line. |
| `pets` | `name`, `type` and an `avatar_emoji`. |
| `recurring` | Chores that rotate one person per day, in the order you list under `choices`. |
| `special_dates` | Countdowns to yearly events, as `MM/DD` with no year. |
| `claude_model` | `claude-haiku-4-5` costs roughly $0.13 a month at one board a day. `claude-sonnet-5` writes better for about three times that. |
| `max_tokens` | Maximum length of the AI response. |

The settings page adds a short `id` to each person, pet, chore, date and calendar the first time you open it. Leave those alone — they are how the page tells one entry from another.

**Upgrading an old config?** A single `calendar_url` becomes the first entry in `calendars` automatically, and a `calendar_filter_emails` list moves onto that entry as its `shared_with`. Photos are gone; the board uses an emoji and a colour.

#### Editing from your phone

Everything on the board is editable at `/settings`. Two things worth knowing:

- **A saved board is from this morning.** Editing a chore or a person shows up on the next page load, but the headline and daily line are only rewritten each morning. Press **Rewrite now** on the settings home page to get fresh copy immediately. Each press is one API call.
- **Adding a calendar checks the link.** Paste an iCal address and press **Check this link**. It tells you how many events it found and what the next one is, so you are not left guessing whether the URL works.
- **A personal calendar can keep its private side.** Fill in **Only show events shared with** on that calendar, and only the events the other parent is on reach the board. See [a personal calendar with work in it](#personal-calendar) above.

The board can be in one of three states: the normal board, a first-run "waiting" screen before anything is generated, or a stale state after a failed or missing run. When stale, the times, turns and countdowns are still today's — only the written line is old, and the board says so.

---

## Part 2 — Put it on a Raspberry Pi

This turns a Pi with a small screen into a wall dashboard that boots straight into the board and refreshes itself. The examples use the username `pi` and the folder `/home/pi`. If you chose a different username in Raspberry Pi Imager, substitute it everywhere.

### Step 1: Install Raspberry Pi OS

Install **Raspberry Pi OS** with the [Raspberry Pi Imager](https://www.raspberrypi.com/software/). In the imager's settings, set your username, enable SSH, and enter your Wi-Fi name and password. The current release is Trixie (Debian 13), which boots into a Wayland desktop — the kiosk steps below cover that, with an X11 alternative.

### Step 2: First boot — connect and install packages

SSH in from your computer, update, and install what the board and the browser need:

```bash
ssh pi@raspberrypi.local
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git python3-venv chromium fonts-noto-color-emoji
```

The emoji font is not optional — without it, every avatar and chore marker shows as an empty box.

### Step 3: Copy DinkyDash onto the Pi

Clone it directly on the Pi:

```bash
cd /home/pi
git clone https://github.com/caspii/dinkydash.git
cd dinkydash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
```

Then edit `config.yaml` with your family's details, or fill it in later from the settings page. For updating the Pi after the first time, see [Updating later](#updating-later).

### Step 4: Add your API key on the Pi

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." > /home/pi/dinkydash/.env
```

Check it works:

```bash
python generate.py
python app.py
```

Open `http://raspberrypi.local:5000` from another device on the same network to confirm the board appears, then stop it with `Ctrl+C`.

### Step 5: Run it as a service

A systemd service starts the board on boot and restarts it if it ever stops. `run_app.sh` ships with the repo and is what the service runs.

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

The board serves on port 5000. To use another port, add a line like `Environment=DINKYDASH_PORT=5123` under `[Service]` and use that port everywhere below.

Enable and start it:

```bash
chmod +x /home/pi/dinkydash/run_app.sh
sudo systemctl daemon-reload
sudo systemctl enable dinkydash.service
sudo systemctl start dinkydash.service
```

### Step 6: Keep the board up to date

A cron job ticks every five minutes, and each tick does only what your settings say is owed —
nothing at all, most of the time. Calendars are re-fetched every hour, so an appointment added at
09:00 for 15:00 reaches the board the same afternoon. The daily line is written once, at 6am. Both
are yours to change under **Settings → How often it updates**.

```bash
crontab -e
```

Add this line:

```cron
*/5 * * * * cd /home/pi/dinkydash && venv/bin/python generate.py --tick >> generate.log 2>&1
```

Runs never pile up: if one is still going when the next is due, the next skips itself. If a run
fails, the previous board stays up and labels itself stale — the screen never goes blank, and the
next tick tries again.

The old daily line still works, and does the fetch and the line together:

```cron
0 6 * * * cd /home/pi/dinkydash && venv/bin/python generate.py >> generate.log 2>&1
```

It just never sees a change you make to your calendar during the day, and the settings above have
no effect on it. Use one line or the other, not both.

### Step 7: Show the board full screen at boot (kiosk)

Kiosk mode launches Chromium full screen with nothing around it. Current Raspberry Pi OS uses the Wayland desktop by default, so that is the main path. A classic X11 alternative follows for people who want the older, simpler tools.

First, save this launcher as `/home/pi/run.sh`. It waits for the board to answer before opening the browser, which avoids the "localhost refused to connect" screen at boot:

```bash
#!/bin/sh
# Wait up to 60 seconds for DinkyDash to answer, then open it full screen.
echo 'Waiting for DinkyDash...'
i=0
while [ $i -lt 60 ]; do
    if curl -s -o /dev/null http://localhost:5000/ 2>/dev/null; then
        break
    fi
    i=$((i + 1))
    sleep 1
done

chromium \
  --kiosk \
  --password-store=basic \
  --disable-infobars \
  --disable-restore-session-state \
  --noerrdialogs \
  --no-first-run \
  --enable-features=OverlayScrollbar \
  http://localhost:5000/
```

Make it executable:

```bash
chmod +x /home/pi/run.sh
```

Turn screen blanking off so the board does not disappear after ten minutes: run `sudo raspi-config`, then **Display Options → Screen Blanking → No**. (Non-interactively: `sudo raspi-config nonint do_blanking 1`.)

#### The Wayland desktop (the default)

Create the file `/home/pi/.config/labwc/autostart` and put one line in it:

```sh
/home/pi/run.sh &
```

Reboot. The Pi logs in, the desktop starts, and the board opens full screen once the service is up.

One rough edge on Wayland: the mouse pointer does not hide itself when idle. If a mouse is plugged in, park the pointer in a corner, or unplug it — a wall panel needs no mouse. If that bothers you, use the X11 alternative below, which hides the pointer properly.

#### The X11 alternative (classic tools)

X11 is the older desktop. It is a little more work to switch to, but the mature tools for hiding the pointer and controlling the screen all work. This is what the DinkyDash Pi runs.

Switch the desktop to X11:

```bash
sudo raspi-config nonint do_wayland W1
```

Then edit `/home/pi/.config/lxsession/LXDE-pi/autostart` so it reads:

```
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@unclutter
@xset s off
@xset -dpms
@xset s noblank
@/home/pi/run.sh
```

That hides the pointer (`unclutter`), stops the screen blanking (`xset`), and launches the board. Reboot to apply. On the newest OS the X11 session differs and this file may not exist — if so, prefer the Wayland path above.

### Step 8: Turn the screen off at night (optional)

Save power by switching the panel's backlight off overnight. Save this as `/home/pi/screen_control.sh`:

```bash
#!/bin/bash
# Turn the display backlight off or on. This works with the current graphics
# driver, where the older `vcgencmd display_power` command no longer does.
BL=/sys/class/backlight/*/bl_power
case "$1" in
    off) echo 1 | sudo tee $BL >/dev/null ;;
    on)  echo 0 | sudo tee $BL >/dev/null ;;
    *)   echo "Usage: $0 [on|off]"; exit 1 ;;
esac
```

Make it executable and schedule it in `crontab -e`:

```bash
chmod +x /home/pi/screen_control.sh
```

```cron
0 22 * * * /home/pi/screen_control.sh off
0 7 * * * /home/pi/screen_control.sh on
```

The Pi keeps running; only the panel sleeps. This uses the backlight file directly, so it works the same on Wayland and X11. It relies on the default user's passwordless `sudo`, which Raspberry Pi Imager sets up.

### Step 9: Rotate the display (optional)

If the screen is mounted upside down:

- **Simplest:** open **Screens** in the desktop's settings (the Control Centre on Trixie), right-click the display and set its orientation.
- **On Wayland, from a script:** add a line above the browser launch in `/home/pi/.config/labwc/autostart`, for example `wlr-randr --output DSI-1 --transform 180 &`.
- **On X11:** add `@xrandr --output DSI-1 --rotate inverted` to the autostart file from step 7.

The old `lcd_rotate` and `display_rotate` lines in `config.txt` no longer apply with the current graphics driver — use one of the methods above instead. If you have a touchscreen and the touch points end up mirrored, add `dtoverlay=vc4-kms-dsi-7inch,invx,invy` to `/boot/firmware/config.txt`.

---

## Troubleshooting

**Emoji show as empty boxes.** Install the font and refresh the cache: `sudo apt install fonts-noto-color-emoji && fc-cache -fv`.

**"localhost refused to connect" at boot.** Chromium started before the board was ready. The `run.sh` above waits up to 60 seconds; make sure your autostart calls it rather than launching Chromium directly.

**The board is a day behind.** A generation run failed. Look at `generate.log` in the project folder. The usual causes are an expired API key, no network at 6am, or a calendar link that stopped working. Fix it, then press **Rewrite now** on the settings page.

**Times are off by an hour.** The timezone under Settings → Family & system is what the engine uses, not the machine clock. Set it even if the clock is already local.

**A calendar shows nothing.** Check it under Settings → Calendars — a failed feed says so. Apple regenerates iCloud links when a calendar stops being shared, so a link that worked last month may need replacing. If the calendar has **Only show events shared with** filled in, open it and press **Check this link**: a working link with no events getting through means the address is not the one on the invitations.

**A GNOME keyring password box appears.** The `--password-store=basic` flag in `run.sh` prevents this. Make sure it is present.

**The screen still blanks.** Confirm you set **Screen Blanking → No** (Wayland) or that the `@xset` lines are present (X11).

**Wi-Fi is blocked after a fresh install.** Some images soft-block Wi-Fi until you set a country: `sudo raspi-config nonint do_wifi_country DE && sudo rfkill unblock wifi` (use your own country code).

---

## Updating later

To push a code change from your computer to the Pi, the repo includes `deploy_to_pi.sh`. It copies the code across and leaves the Pi's own `config.yaml`, board data and `.env` untouched, then installs any new dependencies and restarts the service. It creates the virtualenv on a first deploy, so it works for the initial install as well as later updates.

```bash
./deploy_to_pi.sh                          # deploy
./deploy_to_pi.sh --dry-run                # preview the changes, touch nothing
PI_HOST=192.168.1.50 ./deploy_to_pi.sh     # if raspberrypi.local doesn't resolve
```

By default it talks to `raspberrypi.local`. If that name does not resolve, pass the Pi's address with `PI_HOST` as shown above.

To update by hand on the Pi instead:

```bash
cd /home/pi/dinkydash
git pull
venv/bin/pip install -r requirements.txt
sudo systemctl restart dinkydash.service
```

---

## Quick reference

```bash
# On your computer
source venv/bin/activate
python sample_board.py                # a board with no API call, for a first look
python generate.py                    # today's real board (one API call)
python generate.py --date 2026-12-24  # any date, for checking a countdown
python app.py                         # board at /, settings at /settings

# On the Raspberry Pi
sudo systemctl status dinkydash       # is it running
sudo systemctl restart dinkydash      # restart after a change
journalctl -u dinkydash -f            # the app's log
tail -f /home/pi/dinkydash/generate.log   # last night's generation
/home/pi/screen_control.sh off        # screen off
/home/pi/screen_control.sh on         # screen on
```

Once it is set up, the family gets a fresh dashboard every morning, and there is nothing to tap and nothing to maintain.
