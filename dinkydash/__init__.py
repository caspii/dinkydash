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

    # Configure Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    # Import models to ensure they're registered
    from dinkydash.models import Family, User, Dashboard, Task, Countdown

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
        return render_template('welcome.html')

    # Temporary test login route for development
    @app.route('/test-login')
    def test_login():
        from flask import redirect, url_for, flash, g
        from flask_login import login_user

        # Find test user
        user = User.query.filter_by(email='john@smith.family').first()

        if user:
            login_user(user)
            g.current_tenant_id = user.tenant_id
            flash('Logged in successfully as test user!', 'success')
            return redirect(url_for('dashboard.view'))
        else:
            flash('Test user not found. Please run test_manual.py first.', 'error')
            return redirect(url_for('index'))

    # Temporary logout route for development
    @app.route('/logout')
    def logout():
        from flask import redirect, url_for, flash
        from flask_login import logout_user, current_user

        if current_user.is_authenticated:
            logout_user()
            flash('Logged out successfully.', 'info')

        return redirect(url_for('index'))

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
