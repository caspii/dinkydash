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

    # Temporary welcome route for testing
    @app.route('/')
    def index():
        from flask import jsonify
        return jsonify({
            'status': 'DinkyDash v2.0.0-dev',
            'message': 'Multi-tenant family dashboard (in development)',
            'database': {
                'connected': True,
                'models': ['Family', 'User', 'Dashboard', 'Task', 'Countdown'],
                'tables_created': True
            },
            'completed': [
                'Project structure',
                'Database models',
                'Migrations setup'
            ],
            'next_steps': [
                'Authentication routes & forms',
                'Dashboard viewing',
                'HTMX auto-refresh'
            ],
            'progress': '21/42 MVP tasks (50%)'
        }), 200

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

    # Register error handlers (temporary JSON responses until templates created)
    @app.errorhandler(403)
    def forbidden_error(error):
        from flask import jsonify
        return jsonify({'error': 'Forbidden', 'status': 403}), 403

    @app.errorhandler(404)
    def not_found_error(error):
        from flask import jsonify
        return jsonify({'error': 'Not Found', 'status': 404}), 404

    @app.errorhandler(500)
    def internal_error(error):
        from flask import jsonify
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error', 'status': 500}), 500

    return app
