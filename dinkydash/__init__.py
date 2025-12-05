"""
Flask application factory.
Initializes the application with all extensions and blueprints.
"""
import os
from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from dinkydash.models import db
from dinkydash.config import config_map
from dinkydash.utils.tenant import init_tenant_filter, register_tenant_models


# Initialize extensions
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()


def create_app(config_class=None):
    """Application factory pattern"""
    app = Flask(__name__)

    # Load configuration
    if config_class is None:
        env = os.environ.get('FLASK_ENV', 'production')
        config_class = config_map.get(env, config_map['production'])

    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Initialize tenant filtering after db is initialized
    init_tenant_filter(db)

    # Configure Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    # Import models to ensure they're registered
    from dinkydash.models import Family, User, Dashboard, Task, Countdown
    
    # Register tenant models for automatic tenant_id insertion
    register_tenant_models(db, [Dashboard, Task, Countdown])

    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from flask import g
        user = User.query.get(int(user_id))
        if user:
            g.current_tenant_id = user.tenant_id
        return user

    # Welcome route
    @app.route('/')
    def index():
        from flask import redirect, url_for, render_template
        from flask_login import current_user

        # If logged in, redirect to dashboard
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.view'))

        # Otherwise, show welcome page
        is_dev = app.config.get('DEBUG', False)
        return render_template('welcome.html', is_dev=is_dev)

    # Development-only demo login
    @app.route('/demo-login')
    def demo_login():
        """Quick demo login with pre-populated data (development only)."""
        from flask import redirect, url_for, flash, g
        from flask_login import login_user
        import json

        # Only allow in development mode
        if not app.config.get('DEBUG', False):
            flash('Demo login is only available in development mode.', 'error')
            return redirect(url_for('index'))

        # Find or create demo user
        demo_email = 'demo@dinkydash.local'
        user = User.query.filter_by(email=demo_email).first()

        if not user:
            # Create demo family
            family = Family(name="Demo Family")
            db.session.add(family)
            db.session.flush()

            # Create demo user
            from dinkydash.utils.auth import hash_password
            user = User(
                email=demo_email,
                password_hash=hash_password('demo123'),
                tenant_id=family.id
            )
            db.session.add(user)
            db.session.flush()

            # Create demo dashboard
            dashboard = Dashboard(
                tenant_id=family.id,
                name="Family Dashboard",
                layout_size="large",
                is_default=True
            )
            db.session.add(dashboard)
            db.session.flush()

            # Create demo tasks
            tasks_data = [
                ("Dishes", ["Alice", "Bob", "Charlie"], "🍽"),
                ("Take out trash", ["Bob", "Charlie"], "🗑"),
                ("Feed the dog", ["Alice", "Charlie"], "🐕"),
                ("Water plants", ["Alice", "Bob"], "🌱"),
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

            # Create demo countdowns
            countdowns_data = [
                ("Alice's Birthday", 6, 15, "🎂"),
                ("Bob's Birthday", 9, 22, "🎂"),
                ("Christmas", 12, 25, "🎄"),
                ("New Year", 1, 1, "🎆"),
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

        # Log in the demo user
        login_user(user)
        g.current_tenant_id = user.tenant_id
        flash('Logged in as Demo User! Explore the dashboard.', 'success')
        return redirect(url_for('dashboard.view'))


    # Register blueprints (will be created in user story phases)
    try:
        from dinkydash.routes.auth import auth_bp
        from dinkydash.routes.dashboard import dashboard_bp
        from dinkydash.routes.admin import admin_bp

        app.register_blueprint(auth_bp)
        app.register_blueprint(dashboard_bp)
        app.register_blueprint(admin_bp)
    except ImportError:
        # Blueprints not yet created
        pass

    # Register error handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        from flask import render_template
        error_description = getattr(error, 'description', None)
        return render_template('errors/403.html', error_description=error_description), 403

    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        error_description = getattr(error, 'description', None)
        return render_template('errors/404.html', error_description=error_description), 404

    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        db.session.rollback()
        error_description = getattr(error, 'description', None)
        return render_template('errors/500.html', error_description=error_description), 500

    return app
