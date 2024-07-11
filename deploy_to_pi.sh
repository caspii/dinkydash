#!/bin/bash

# Bash script to deploy files to a Raspberry Pi running a Flask app

# Configuration
LOCAL_DIR="$(pwd)"  # Assumes you're running this script from your project directory
REMOTE_USER="pi"
REMOTE_HOST="raspberrypi"  # Or use the IP address of your Raspberry Pi
REMOTE_DIR="/home/pi/dinkydash"

# Ensure the remote directory exists
ssh $REMOTE_USER@$REMOTE_HOST "mkdir -p $REMOTE_DIR"

# Use rsync to copy files, excluding .venv, .git, and other unnecessary files
rsync -avz --exclude='venv' \
           --exclude='.git' \
           --exclude='__pycache__' \
           --exclude='*.pyc' \
           --exclude='*.pyo' \
           --exclude='*.pyd' \
           --exclude='*.log' \
           --exclude='*.swp' \
           "$LOCAL_DIR/" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/"

# If successful, print a success message
if [ $? -eq 0 ]; then
    echo "Files successfully copied to Raspberry Pi"
else
    echo "Error occurred while copying files"
fi

# Optionally, restart the Flask service on the Raspberry Pi
ssh $REMOTE_USER@$REMOTE_HOST "sudo systemctl restart dinkydash.service"

echo "Flask service restarted on Raspberry Pi"