"""
User model - Authentication and family membership.
Integrates with Flask-Login for session management.
"""
from datetime import datetime
from flask_login import UserMixin
from dinkydash.models import db


class User(UserMixin, db.Model):
    """User model with Flask-Login integration"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.email}>'
