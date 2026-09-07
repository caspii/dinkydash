#!/usr/bin/env bash
# Deploy DinkyDash to the Raspberry Pi.
#
#   ./deploy_to_pi.sh              # deploy
#   ./deploy_to_pi.sh --dry-run    # show what would change, do nothing
#
# Host, user and directory can be overridden from the environment:
#   PI_HOST=192.168.178.164 ./deploy_to_pi.sh
set -euo pipefail

PI_USER="${PI_USER:-pi}"
PI_HOST="${PI_HOST:-raspberrypi.local}"   # plain 'raspberrypi' can resolve to a stale IP
PI_DIR="${PI_DIR:-/home/pi/dinkydash}"
REMOTE="$PI_USER@$PI_HOST"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/"   # the repo, not your current directory
SSH="ssh -o ConnectTimeout=8"

DRY_RUN=""
[ "${1:-}" = "--dry-run" ] && DRY_RUN="--dry-run"

echo "Deploying to $REMOTE:$PI_DIR ..."

# Fail early with a clear message if the Pi isn't reachable.
if ! $SSH "$REMOTE" true 2>/dev/null; then
    echo "Can't reach $REMOTE. Check it's on, or run: PI_HOST=<its IP> $0" >&2
    exit 1
fi

$SSH "$REMOTE" "mkdir -p '$PI_DIR'"

# Copy the code. Everything the Pi owns is protected from being overwritten and,
# with --delete, from being removed: the settings and data written on the Pi
# (config.yaml, dashboard_data.json, content_history.json, generate.log), the
# API key (.env), the virtualenv, and the build- and dev-only trees.
#
# --stats rather than --info=stats1: macOS 15 replaced rsync with openrsync,
# which speaks protocol 29 and rejects --info outright. --stats is understood by
# both, and by rsync 2.6.9 before it.
rsync -az --stats --delete $DRY_RUN \
    --exclude='.git/' \
    --exclude='venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.swp' \
    --exclude='.pytest_cache/' \
    --exclude='.conductor/' \
    --exclude='.context/' \
    --exclude='.env' \
    --exclude='config.yaml' \
    --exclude='dashboard_data.json' \
    --exclude='content_history.json' \
    --exclude='.tick.lock' \
    --exclude='*.log' \
    --exclude='website/' \
    --exclude='design/' \
    --exclude='tests/' \
    "$SRC" "$REMOTE:$PI_DIR/"

if [ -n "$DRY_RUN" ]; then
    echo "Dry run only; nothing changed."
    exit 0
fi

# A fresh Pi has no virtualenv yet; create it on first deploy.
$SSH "$REMOTE" "cd '$PI_DIR' && [ -d venv ] || python3 -m venv venv"
$SSH "$REMOTE" "cd '$PI_DIR' && venv/bin/pip install -q -r requirements.txt"

# Restart the app if the service is installed; otherwise point at the setup guide.
if $SSH "$REMOTE" "test -f /etc/systemd/system/dinkydash.service"; then
    $SSH "$REMOTE" "sudo systemctl restart dinkydash.service"
    echo "Restarted dinkydash.service."
else
    echo "Note: dinkydash.service isn't installed yet. See the setup guide, Part 2 step 5."
fi

echo "Done."
