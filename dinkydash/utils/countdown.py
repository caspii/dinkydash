"""
Countdown calculation utilities.
Calculates days remaining until events, handling year rollover.
"""
from datetime import datetime, date


def calculate_days_remaining(month, day):
    """
    Calculate days remaining until the next occurrence of a date.

    Handles year rollover: if the date has passed this year, calculates
    days until next year's occurrence.

    Args:
        month (int): Month number (1-12)
        day (int): Day number (1-31)

    Returns:
        int: Number of days until next occurrence (0 if today)

    Raises:
        ValueError: If month or day are invalid
    """
    if not 1 <= month <= 12:
        raise ValueError(f"Invalid month: {month}. Must be 1-12.")

    if not 1 <= day <= 31:
        raise ValueError(f"Invalid day: {day}. Must be 1-31.")

    today = date.today()
    current_year = today.year

    # Try to create target date in current year
    try:
        target_date = date(current_year, month, day)
    except ValueError:
        raise ValueError(f"Invalid date: month={month}, day={day}")

    # If target date has passed this year, use next year
    if target_date < today:
        target_date = date(current_year + 1, month, day)

    # Calculate days remaining
    delta = target_date - today
    return delta.days


def get_target_date(month, day):
    """
    Get the next occurrence of a specific month/day as a date object.

    Args:
        month (int): Month number (1-12)
        day (int): Day number (1-31)

    Returns:
        date: The next occurrence of the specified date

    Raises:
        ValueError: If month or day are invalid
    """
    if not 1 <= month <= 12:
        raise ValueError(f"Invalid month: {month}. Must be 1-12.")

    if not 1 <= day <= 31:
        raise ValueError(f"Invalid day: {day}. Must be 1-31.")

    today = date.today()
    current_year = today.year

    # Try to create target date in current year
    try:
        target_date = date(current_year, month, day)
    except ValueError:
        raise ValueError(f"Invalid date: month={month}, day={day}")

    # If target date has passed this year, use next year
    if target_date < today:
        target_date = date(current_year + 1, month, day)

    return target_date


def format_countdown(days_remaining):
    """
    Format days remaining into human-readable text.

    Args:
        days_remaining (int): Number of days until event

    Returns:
        str: Formatted countdown text (e.g., "Today!", "Tomorrow", "5 days")
    """
    if days_remaining == 0:
        return "Today!"
    elif days_remaining == 1:
        return "Tomorrow"
    else:
        return f"{days_remaining} days"
