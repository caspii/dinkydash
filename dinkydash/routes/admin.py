"""
Admin routes for managing dashboards, tasks, and countdowns.
To be implemented in future user stories.
"""
from flask import Blueprint

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
def index():
    """Admin dashboard (placeholder)."""
    return "Admin page - to be implemented", 501
