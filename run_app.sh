#!/bin/bash
# Started by dinkydash.service. Uses the venv's python directly so systemd
# doesn't need a login shell to activate it.
cd /home/pi/dinkydash
exec venv/bin/python app.py
