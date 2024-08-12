---
title: About DinkyDash
template: page.html
---

DinkyDash is a simple, customizable dashboard designed to display family-oriented information such as recurring tasks, countdowns to special events, and daily rotations. It's perfect for mounting on a Raspberry Pi with a display in a common area of your home, providing at-a-glance information for all family members.

## Why DinkyDash?

DinkyDash is great for quickly answering those questions that kids like to ask again and again and again and again:

- "How many days till Christmas?"
- "Who's turn is it to take the trash out?"
- "When is my birthday party?"

## Features

The dashboard shows:
- Today's date
- Recurring tasks or roles (e.g., who's turn it is to do the dishes)
- Countdowns to important dates (birthdays, holidays, events)

## Technical Details

DinkyDash is built with Flask and can be easily configured using a YAML file, making it simple to update and maintain without diving into the code.

### Stack
- Backend: Python 3 with Flask
- Frontend: HTML5 and CSS (Bootstrap 5)
- Configuration: YAML

### Key Components
1. `app.py`: The main Flask application that serves the dashboard.
2. `config.yaml`: Configuration file for customizing dashboard content.
3. `templates/index.html`: The single-page template for the dashboard display.
4. `run_app.sh`: Bash script to start the Flask application.

For more detailed setup instructions and technical information, please visit our [GitHub repository](https://github.com/caspii/dinkydash).