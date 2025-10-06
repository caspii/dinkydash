# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

DinkyDash is a family dashboard application designed to run on a Raspberry Pi. It displays:
- Recurring tasks/roles that rotate daily (e.g., whose turn to do dishes)
- Countdowns to important dates (birthdays, holidays, etc.)

The project has two main components:
1. **Flask Dashboard App** (root directory) - The main dashboard application
2. **Static Site Generator** (website/ directory) - Generates marketing/documentation site to GitHub Pages

## Development Commands

### Flask Dashboard App

**Setup**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Run locally**
```bash
python app.py
# or
flask run --host=0.0.0.0
```

**Deploy to Raspberry Pi**
```bash
./deploy_to_pi.sh
```

### Static Site Generator (Marketing Site)

**Build static site**
```bash
cd website
python build.py
```

This generates static HTML from Markdown content in `website/content/` to `docs/` for GitHub Pages.

## Architecture

### Flask Dashboard (`app.py`)

**Configuration-driven**: All dashboard content is defined in `config.yaml`:
- `recurring`: Items that rotate daily based on day-of-year (uses `tm_yday % len(choices)`)
- `countdowns`: Events with dates that show days remaining

**Key functions**:
- `get_recurring(item)`: Calculates today's rotation based on day-of-year modulo number of choices
- `calculate_days_remaining(target_date)`: Calculates days until next occurrence (handles year rollover)
- `get_sorted_countdowns()`: Sorts countdowns by days remaining (soonest first)

**Template**: Single-page dashboard (`templates/index.html`) auto-refreshes every 60 seconds, displays cards with emojis/images.

### Static Site Generator (`website/build.py`)

**Build pipeline**:
1. Reads Markdown files from `website/content/`
2. Extracts YAML front matter (title, description, template)
3. Converts Markdown to HTML using Python markdown library
4. Renders via Jinja2 templates in `website/templates/`
5. Outputs to `docs/` with clean URLs (about.md → about/index.html)
6. Preserves CNAME file for custom domain

### Configuration (`config.yaml`)

**Recurring items structure**:
```yaml
- title: "🍽"           # Emoji or text label
  repeat: 1             # Days per rotation (currently unused in code)
  choices:              # List of options that rotate daily
    - ["image.jpg"]     # Can be images or emoji text
```

**Countdown items structure**:
```yaml
- image: "name.jpg"     # Optional profile image
  title: "🎂"           # Event emoji/label
  date: "03/21"         # MM/DD format (year auto-calculated)
```

## Raspberry Pi Deployment

The `deploy_to_pi.sh` script uses rsync to copy files and restarts the systemd service `dinkydash.service`.

**Deployment flow**:
1. Syncs files via rsync (excludes venv, git, pycache)
2. Restarts systemd service on Pi

**Pi-specific setup notes** (from README):
- Install emoji fonts: `sudo apt install fonts-noto-color-emoji`
- Hide mouse cursor: `sudo apt-get install unclutter -y`
- Rotate display 180°: Add `lcd_rotate=2` to `/boot/config.txt`
