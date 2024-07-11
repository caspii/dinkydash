from flask import Flask, render_template
import yaml
from datetime import datetime, date

app = Flask(__name__)


def load_config():
    with open('config.yaml', 'r') as file:
        return yaml.safe_load(file)


def calculate_days_remaining(target_date):
    today = date.today()
    current_year = today.year

    target = datetime.strptime(f"{target_date}/{current_year}", "%m/%d/%Y").date()

    # If the date has already passed this year, use next year
    if target < today:
        target = target.replace(year=current_year + 1)

    difference = target - today
    return difference.days


def get_sorted_countdowns(countdowns):
    return sorted(
        countdowns,
        key=lambda x: calculate_days_remaining(x['date'])
    )


def get_recurring(people):
    people_count = len(people)
    days_into_year = datetime.now().timetuple().tm_yday
    todays_index = days_into_year % people_count
    return people[todays_index]


@app.route('/')
def index():
    config = load_config()
    today = datetime.now().strftime("%A, %B %d, %Y")

    for item in config['recurring']:
        item['today'] = get_recurring(item['people'])

    sorted_countdowns = get_sorted_countdowns(config['countdowns'])
    for countdown in sorted_countdowns:
        countdown['days_remaining'] = calculate_days_remaining(countdown['date'])

    return render_template('index.html',
                           today=today,
                           recurring=config['recurring'],
                           countdowns=sorted_countdowns)


if __name__ == '__main__':
    app.run(debug=True)