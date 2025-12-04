"""
Task rotation utilities.
Calculates which person is assigned to a task based on day-of-year rotation.
"""
import json
from datetime import datetime


def get_current_person(rotation_json):
    """
    Calculate the current person assigned to a task based on day-of-year rotation.

    The rotation uses day-of-year modulo the number of people to ensure
    daily rotation and consistent assignment across years.

    Args:
        rotation_json (str): JSON array of person names, e.g., '["Alice", "Bob", "Charlie"]'

    Returns:
        str: Name of the person currently assigned to the task

    Raises:
        ValueError: If rotation_json is empty or invalid JSON
    """
    if not rotation_json:
        raise ValueError("rotation_json cannot be empty")

    try:
        rotation_list = json.loads(rotation_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in rotation_json: {e}")

    if not rotation_list:
        raise ValueError("rotation_list cannot be empty")

    # Get day of year (1-365 or 1-366 for leap years)
    day_of_year = datetime.now().timetuple().tm_yday

    # Calculate index using modulo
    index = (day_of_year - 1) % len(rotation_list)

    return rotation_list[index]


def get_person_for_date(rotation_json, target_date):
    """
    Calculate which person is assigned to a task on a specific date.

    Args:
        rotation_json (str): JSON array of person names
        target_date (datetime): The date to calculate assignment for

    Returns:
        str: Name of the person assigned on that date

    Raises:
        ValueError: If rotation_json is empty or invalid JSON
    """
    if not rotation_json:
        raise ValueError("rotation_json cannot be empty")

    try:
        rotation_list = json.loads(rotation_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in rotation_json: {e}")

    if not rotation_list:
        raise ValueError("rotation_list cannot be empty")

    # Get day of year for target date
    day_of_year = target_date.timetuple().tm_yday

    # Calculate index using modulo
    index = (day_of_year - 1) % len(rotation_list)

    return rotation_list[index]
