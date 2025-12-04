"""
Family model - Tenant root entity.
Each family represents a separate tenant in the multi-tenant system.
"""
from datetime import datetime
from dinkydash.models import db


class Family(db.Model):
    """Family/Tenant model"""
    __tablename__ = 'families'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    users = db.relationship('User', backref='family', lazy=True, cascade='all, delete-orphan')
    dashboards = db.relationship('Dashboard', backref='family', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Family {self.name}>'
