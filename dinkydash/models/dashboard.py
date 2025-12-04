"""
Dashboard model - Multiple dashboards per family.
Each dashboard can have different layout sizes and contains tasks/countdowns.
"""
from datetime import datetime
from dinkydash.models import db


class Dashboard(db.Model):
    """Dashboard model"""
    __tablename__ = 'dashboards'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    layout_size = db.Column(db.String(20), nullable=False, default='medium')  # small, medium, large
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    tasks = db.relationship('Task', backref='dashboard', lazy=True, cascade='all, delete-orphan')
    countdowns = db.relationship('Countdown', backref='dashboard', lazy=True, cascade='all, delete-orphan')

    # Indexes
    __table_args__ = (
        db.Index('idx_dashboards_tenant_id', 'tenant_id'),
    )

    def __repr__(self):
        return f'<Dashboard {self.name}>'
