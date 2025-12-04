"""
Authentication routes (login, register, logout).
To be implemented in future user stories.
"""
from flask import Blueprint

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login')
def login():
    """Login page (placeholder)."""
    return "Login page - to be implemented", 501


@auth_bp.route('/register')
def register():
    """Registration page (placeholder)."""
    return "Registration page - to be implemented", 501


@auth_bp.route('/logout')
def logout():
    """Logout (placeholder)."""
    return "Logout - to be implemented", 501
