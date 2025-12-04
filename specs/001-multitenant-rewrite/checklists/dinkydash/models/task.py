"""
Task model - Recurring tasks with rotation and icons.
Tasks rotate daily among family members.
"""
from datetime import datetime
from dinkydash.models import db


class Task(db.Model):
    """Recurring task model"""
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    dashboard_id = db.Column(db.Integer, db.ForeignKey('dashboards.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    rotation_json = db.Column(db.Text, nullable=False)  # JSON array of person names
    icon_type = db.Column(db.String(20), nullable=False)  # 'emoji' or 'image'
    icon_value = db.Column(db.String(255), nullable=False)  # Emoji text or image path
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        db.Index('idx_tasks_dashboard_id', 'dashboard_id'),
    )

    def __repr__(self):
        return f'<Task {self.name}>'
