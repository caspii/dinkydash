#!/bin/bash

# Deploy DinkyDash to Raspberry Pi

REMOTE_USER="pi"
REMOTE_HOST="raspberrypi"
REMOTE_DIR="/home/pi/dinkydash"

set -e

echo "Deploying to $REMOTE_HOST..."

# Ensure remote directory exists
ssh -q $REMOTE_USER@$REMOTE_HOST "mkdir -p $REMOTE_DIR"

# Sync files (quiet mode)
rsync -az --exclude='venv' \
          --exclude='.git' \
          --exclude='__pycache__' \
          --exclude='*.pyc' \
          --exclude='*.log' \
          --exclude='*.swp' \
          "$(pwd)/" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/"

# Install dependencies quietly
ssh -q $REMOTE_USER@$REMOTE_HOST "cd $REMOTE_DIR && source venv/bin/activate && pip install -q -r requirements.txt"

# Restart service
ssh -q $REMOTE_USER@$REMOTE_HOST "sudo systemctl restart dinkydash.service"

echo "Done."