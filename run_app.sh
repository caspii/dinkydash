#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=5123 --debug