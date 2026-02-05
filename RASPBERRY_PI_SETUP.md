# Raspberry Pi DinkyDash Setup Documentation

**Last Updated:** 2026-02-05
**OS Upgrade Completed:** Buster (10) → Bookworm (12) via fresh install

---

## Hardware

| Component | Value |
|-----------|-------|
| Model | Raspberry Pi 4 Model B Rev 1.4 |
| Memory | 4GB RAM |
| Storage | 64GB SD Card |
| Display | DSI Touchscreen (800x480 @ 60Hz, rotated 180°) |

### Display Details

- **Connection:** DSI-1 (not HDMI)
- **Resolution:** 800x480 pixels
- **Refresh Rate:** 60.03 Hz
- **Rotation:** 180° (configured via `lcd_rotate=2` and `display_rotate=2`)

---

## Operating System

| Property | Value |
|----------|-------|
| OS | Raspberry Pi OS (Debian 12 Bookworm) |
| Kernel | 6.6.51+rpt-rpi-v8 |
| Architecture | aarch64 (64-bit) |
| Hostname | raspberrypi |
| IP Address (Wi-Fi) | 192.168.178.183 or 192.168.178.189 (DHCP) |
| Display Server | X11 (not Wayland) |

---

## DinkyDash Application

### Overview

Running the **legacy v1.x config-based** version of DinkyDash (not the new multi-tenant version).

| Property | Value |
|----------|-------|
| Location | `/home/pi/dinkydash` |
| Version | v1.x (config.yaml based) |
| Python | 3.11.2 |
| Flask | 3.0.0 |
| Node.js | v20.20.0 |
| npm | 10.8.2 |
| URL | http://raspberrypi:5000/ |

### Project Structure (Legacy App Only)

```
/home/pi/dinkydash/
├── app.py              # Flask application (single route)
├── config.yaml         # Task and countdown configuration
├── requirements.txt    # Flask, PyYAML
├── run_app.sh          # Startup script for systemd
├── templates/
│   └── index.html      # Single page template (Bootstrap 5 Quartz theme)
├── static/             # Family member photos
│   ├── caspar.jpg
│   ├── estelle.jpg
│   ├── jessica.jpg
│   ├── josephine.jpg
│   └── snae.jpg
└── venv/               # Python virtual environment
```

### Virtual Environment Packages

```
Flask        3.0.0
PyYAML       6.0.1
Jinja2       3.1.6
Werkzeug     3.1.5
blinker      1.9.0
click        8.3.1
itsdangerous 2.2.0
MarkupSafe   3.0.3
```

---

## Systemd Service

**Service File:** `/etc/systemd/system/dinkydash.service`

```ini
[Unit]
Description=Family Dashboard Flask App
After=network.target

[Service]
ExecStart=/home/pi/dinkydash/run_app.sh
User=pi
WorkingDirectory=/home/pi/dinkydash
Restart=always

[Install]
WantedBy=multi-user.target
```

**Startup Script:** `/home/pi/dinkydash/run_app.sh`

```bash
#!/bin/bash
cd /home/pi/dinkydash
source venv/bin/activate
export FLASK_APP=app.py
flask run --host=0.0.0.0
```

**Service Status:** Active and running, enabled at boot

---

## Kiosk Mode Configuration

### Chromium Autostart

**File:** `/home/pi/.config/lxsession/LXDE-pi/autostart`

```
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@unclutter
@xset s off
@xset -dpms
@xset s noblank
@/home/pi/run.sh
```

### Kiosk Launch Script

**File:** `/home/pi/run.sh`

```bash
#!/bin/sh
# Wait for Flask service to be ready (max 60 seconds)
echo 'Waiting for DinkyDash service...'
i=0
while [ $i -lt 60 ]; do
    if curl -s -o /dev/null -w '' http://localhost:5000/ 2>/dev/null; then
        echo 'DinkyDash is ready!'
        break
    fi
    i=$((i + 1))
    sleep 1
done

# Launch Chromium in kiosk mode
/usr/bin/chromium-browser --kiosk --password-store=basic --disable-infobars --enable-features=OverlayScrollbar --disable-restore-session-state --noerrdialogs http://localhost:5000/
```

### Important Chromium Flags

| Flag | Purpose |
|------|---------|
| `--kiosk` | Fullscreen kiosk mode |
| `--password-store=basic` | Prevents GNOME keyring password dialog |
| `--disable-infobars` | Hides info bars |
| `--noerrdialogs` | Suppresses error dialogs |
| `--disable-restore-session-state` | Clean start each time |

### Display Settings

- Screen saver: Disabled (`xset s off`)
- DPMS (power management): Disabled (`xset -dpms`)
- Screen blanking: Disabled (`xset s noblank`)
- Unclutter: Hides mouse cursor after inactivity

---

## Scheduled Tasks (Cron)

**Crontab for user `pi`:**

```cron
# Screen power management
0 22 * * * /home/pi/screen_control.sh off   # Turn off display at 10 PM
0 7 * * * /home/pi/screen_control.sh on     # Turn on display at 7 AM
```

**Screen Control Script:** `/home/pi/screen_control.sh`

```bash
#!/bin/bash
if [ "$1" = "off" ]; then
    vcgencmd display_power 0
elif [ "$1" = "on" ]; then
    vcgencmd display_power 1
else
    echo "Usage: $0 [on|off]"
    exit 1
fi
```

---

## Boot Configuration

**File:** `/boot/firmware/config.txt` (relevant settings)

```ini
[all]
lcd_rotate=2          # Display rotated 180 degrees
display_rotate=2      # Alternative rotation setting
```

**Note:** On Bookworm, the boot partition is at `/boot/firmware/` not `/boot/`.

---

## Network Configuration

| Property | Value |
|----------|-------|
| Hostname | raspberrypi |
| Wi-Fi SSID | Goethe32_EG |
| Wi-Fi Country | DE |
| SSH | Enabled (passwordless via key) |
| User | pi |
| Password | ludwig123 |

### SSH Access

Passwordless SSH is configured. Connect with:

```bash
ssh pi@raspberrypi
```

SSH key is in `/home/pi/.ssh/authorized_keys`.

---

## Installed Software

| Package | Version | Purpose |
|---------|---------|---------|
| Python | 3.11.2 | Flask runtime |
| Node.js | 20.20.0 | JavaScript runtime |
| npm | 10.8.2 | Node package manager |
| Chromium | (system) | Kiosk browser |
| fonts-noto-color-emoji | (system) | Emoji display |

---

## Troubleshooting & Lessons Learned

### Issue: "localhost refused to connect" on boot

**Cause:** Race condition - Chromium starts before Flask service is ready.

**Solution:** Modified `/home/pi/run.sh` to wait up to 60 seconds for Flask to respond before launching Chromium.

### Issue: GNOME Keyring password dialog

**Cause:** Chromium tries to use GNOME keyring for password storage on auto-login.

**Solution:** Added `--password-store=basic` flag to Chromium launch command.

### Issue: Emoji fonts not displaying

**Cause:** Raspberry Pi OS Lite doesn't include emoji fonts.

**Solution:** Install `fonts-noto-color-emoji`:
```bash
sudo apt install fonts-noto-color-emoji
fc-cache -fv
```

### Issue: "Wayland switch" dialog on boot

**Cause:** Bookworm prompts to switch from X11 to Wayland.

**Solution:** Set X11 as default via raspi-config:
```bash
sudo raspi-config nonint do_wayland W1
```

### Issue: Locale warning on SSH login

**Cause:** Client sends LC_ALL which doesn't exist on server.

**Solution:** Disable AcceptEnv in `/etc/ssh/sshd_config`:
```bash
sudo sed -i 's/AcceptEnv LANG LC_\*/#AcceptEnv LANG LC_*/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

### Issue: Wi-Fi blocked by rfkill

**Cause:** Fresh Bookworm install has Wi-Fi soft-blocked until country is set.

**Solution:**
```bash
sudo raspi-config nonint do_wifi_country DE
sudo rfkill unblock wifi
```

### Issue: Multi-tenant code conflicts with legacy app

**Cause:** Running `deploy_to_pi.sh` syncs the entire repo including the `dinkydash/` package.

**Solution:** Only deploy legacy files. Remove conflicting directories:
```bash
rm -rf /home/pi/dinkydash/dinkydash
rm -rf /home/pi/dinkydash/migrations
rm -rf /home/pi/dinkydash/tests
```

---

## Deployment Warning

**DO NOT** run `deploy_to_pi.sh` as it will sync the multi-tenant codebase and break the legacy app.

To deploy updates to the legacy app, manually copy only:
- `app.py` (legacy version from git history)
- `config.yaml`
- `templates/index.html`
- `static/*.jpg`
- `requirements.txt` (Flask + PyYAML only)

---

## Quick Reference Commands

```bash
# SSH to Pi
ssh pi@raspberrypi

# Check service status
sudo systemctl status dinkydash

# Restart service
sudo systemctl restart dinkydash

# View service logs
journalctl -u dinkydash -f

# Restart Chromium
pkill -f chromium && DISPLAY=:0 nohup /home/pi/run.sh > /dev/null 2>&1 &

# Screen on/off
/home/pi/screen_control.sh on
/home/pi/screen_control.sh off

# Check display info
DISPLAY=:0 xrandr
```
