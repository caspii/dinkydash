# DinkyDash

![mockup.png](mockup.png)

## Introduction

DinkyDash is a simple, customizable dashboard designed to display family-oriented information such as recurring tasks, countdowns to special events, and daily rotations. It's perfect for mounting on a Raspberry Pi with a display in a common area of your home, providing at-a-glance information for all family members.

DinkyDash is great for quickly answering those questions that kids like to ask again and again and again and again.

- "How many days till Christmas?"
- "Who's turn is it to take the trash out?"
- "When is my birthday party?"

The dashboard shows:
- Today's date
- Recurring tasks or roles (e.g., who's turn it is to do the dishes)
- Countdowns to important dates (birthdays, holidays, events)

DinkyDash is built with Flask and can be easily configured using a YAML file, making it simple to update and maintain without diving into the code.

## Technical Details

### Stack
- Backend: Python 3 with Flask
- Frontend: HTML5 and CSS (Bootstrap 5)
- Configuration: YAML

### Key Components
1. `app.py`: The main Flask application that serves the dashboard.
2. `config.yaml`: Configuration file for customizing dashboard content.
3. `templates/index.html`: The single-page template for the dashboard display.
4. `run_app.sh`: Bash script to start the Flask application.

### Setup

**TODO: Complete this section**

1. Clone the repository to your Raspberry Pi.
2. Create a Python virtual environment and install dependencies:

## Setting up the pi

**TODO: Complete this section**

Install emoji fonts: `sudo apt install fonts-noto-color-emoji`

Install unclutter to hide mouse: `sudo apt-get install unclutter -y`

To turn the screen orientation by 180° enter this on a new line in /boot/config.txt and the screen will turn upside-down after a reboot: `lcd_rotate=2`

