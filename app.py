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


if __name__ == "__main__":
    app.run(debug=True)
