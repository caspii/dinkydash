from flask import Flask, render_template
import json
import os
from datetime import datetime

app = Flask(__name__)

DATA_FILE = os.environ.get("DINKYDASH_DATA_FILE", "dashboard_data.json")


def load_dashboard_data():
    """Load the pre-generated dashboard data JSON."""
    try:
        with open(DATA_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@app.route("/")
def index():
    data = load_dashboard_data()
    today = datetime.now().strftime("%A, %B %d")
    if data:
        today = data.get("today_display", today)
    return render_template("index.html", data=data, today=today)


@app.route("/preview")
def preview():
    """Show the dashboard in an 800x480 iframe matching the Pi display."""
    return """<!doctype html>
<html><head><title>DinkyDash Preview (800x480)</title>
<style>
  body { margin: 0; background: #1a1a2e; display: flex; align-items: center;
         justify-content: center; height: 100vh; font-family: sans-serif; }
  .frame { border: 3px solid #444; border-radius: 8px; overflow: hidden;
           box-shadow: 0 0 40px rgba(0,0,0,0.5); }
  .label { color: #666; text-align: center; margin-top: 12px; font-size: 13px; }
  iframe { display: block; border: none; }
</style></head><body>
<div>
  <div class="frame"><iframe src="/" width="800" height="480"></iframe></div>
  <div class="label">Raspberry Pi display — 800 × 480</div>
</div>
</body></html>"""


if __name__ == "__main__":
    app.run(debug=True)
