"""
Database models initialization.
Sets up SQLAlchemy and imports all models.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import models after db is defined to avoid circular imports
from dinkydash.models.family import Family
from dinkydash.models.user import User
from dinkydash.models.dashboard import Dashboard
from dinkydash.models.task import Task
from dinkydash.models.countdown import Countdown

__all__ = ['db', 'Family', 'User', 'Dashboard', 'Task', 'Countdown']
