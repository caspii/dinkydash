"""
Countdown model - Events with dates and icons.
Automatically calculates days remaining until next occurrence.
"""
from datetime import datetime
from dinkydash.models import db, TenantModel


class Countdown(TenantModel):
    """Countdown event model"""
    __tablename__ = 'countdowns'

    id = db.Column(db.Integer, primary_key=True)
    dashboard_id = db.Column(db.Integer, db.ForeignKey('dashboards.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    date_month = db.Column(db.Integer, nullable=False)  # 1-12
    date_day = db.Column(db.Integer, nullable=False)  # 1-31
    icon_type = db.Column(db.String(20), nullable=False)  # 'emoji' or 'image'
    icon_value = db.Column(db.String(255), nullable=False)  # Emoji text or image path
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        db.Index('idx_countdowns_dashboard_id', 'dashboard_id'),
        db.Index('idx_countdowns_tenant_id', 'tenant_id'),
    )

    def __repr__(self):
        return f'<Countdown {self.name}>'
