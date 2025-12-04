#!/usr/bin/env python
"""
Manual test script to verify DinkyDash functionality.
Creates test data and demonstrates core features.
"""
import json
from datetime import datetime
from dinkydash import create_app
from dinkydash.models import db, Family, User, Dashboard, Task, Countdown
from dinkydash.utils.auth import hash_password
from dinkydash.utils.rotation import get_current_person
from dinkydash.utils.countdown import calculate_days_remaining, format_countdown

def create_test_data():
    """Create test family, user, dashboard, tasks, and countdowns."""
    app = create_app()

    with app.app_context():
        # Clear existing data
        db.drop_all()
        db.create_all()

        print("Creating test data...")

        # Create family
        family = Family(name="Smith Family")
        db.session.add(family)
        db.session.commit()
        print(f"✓ Created family: {family.name} (ID: {family.id})")

        # Create user
        user = User(
            email="john@smith.family",
            password_hash=hash_password("password123"),
            tenant_id=family.id
        )
        db.session.add(user)
        db.session.commit()
        print(f"✓ Created user: {user.email} (ID: {user.id})")

        # Create dashboard
        dashboard = Dashboard(
            tenant_id=family.id,
            name="Kitchen Dashboard",
            layout_size="large",
            is_default=True
        )
        db.session.add(dashboard)
        db.session.commit()
        print(f"✓ Created dashboard: {dashboard.name} (ID: {dashboard.id})")

        # Create tasks
        tasks_data = [
            ("Dishes", ["Alice", "Bob", "Charlie"], "🍽"),
            ("Take out trash", ["Bob", "Charlie"], "🗑"),
            ("Feed the dog", ["Alice", "Charlie"], "🐕"),
        ]

        for name, rotation, emoji in tasks_data:
            task = Task(
                dashboard_id=dashboard.id,
                name=name,
                rotation_json=json.dumps(rotation),
                icon_type="emoji",
                icon_value=emoji
            )
            db.session.add(task)
            db.session.commit()

            # Test rotation
            current_person = get_current_person(task.rotation_json)
            print(f"✓ Created task: {name} - Today: {current_person} {emoji}")

        # Create countdowns
        countdowns_data = [
            ("Alice's Birthday", 6, 15, "🎂"),
            ("Christmas", 12, 25, "🎄"),
            ("Summer Vacation", 7, 1, "🏖"),
        ]

        for name, month, day, emoji in countdowns_data:
            countdown = Countdown(
                dashboard_id=dashboard.id,
                name=name,
                date_month=month,
                date_day=day,
                icon_type="emoji",
                icon_value=emoji
            )
            db.session.add(countdown)
            db.session.commit()

            # Test countdown calculation
            days = calculate_days_remaining(month, day)
            days_text = format_countdown(days)
            print(f"✓ Created countdown: {name} - {days_text} {emoji}")

        print("\n" + "="*60)
        print("Test data created successfully!")
        print("="*60)
        print("\nYou can now start the Flask app:")
        print("  flask run")
        print("\nThen visit http://localhost:5000")
        print("\nNote: Authentication UI is not yet implemented.")
        print("To test dashboard viewing, you'll need to manually log in")
        print("or modify the routes to skip authentication temporarily.")
        print("\nTest credentials:")
        print("  Email: john@smith.family")
        print("  Password: password123")
        print("="*60)


if __name__ == "__main__":
    create_test_data()
