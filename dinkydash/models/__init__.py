"""
Database models initialization.
Sets up SQLAlchemy and imports all models.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class TenantQuery(db.Query):
    """Custom query class that applies tenant filtering automatically."""
    
    def _maybe_filter_by_tenant(self):
        """Apply tenant filter if appropriate."""
        from flask import g
        
        # Skip if already filtered
        if hasattr(self, '_tenant_filtered') and self._tenant_filtered:
            return self
            
        # Get current tenant ID
        tenant_id = getattr(g, 'current_tenant_id', None)
        
        # If no tenant set, don't filter
        if tenant_id is None:
            return self
            
        # Apply filter
        filtered = self.filter_by(tenant_id=tenant_id)
        # Mark as filtered to avoid double filtering
        filtered._tenant_filtered = True
        return filtered
    
    def all(self):
        """Apply tenant filter before all()."""
        filtered = self._maybe_filter_by_tenant()
        if filtered is self:
            # No filtering needed, call parent
            return super(TenantQuery, self).all()
        return filtered.all()
        
    def first(self):
        """Apply tenant filter before first()."""  
        filtered = self._maybe_filter_by_tenant()
        if filtered is self:
            return super(TenantQuery, self).first()
        return filtered.first()
        
    def one(self):
        """Apply tenant filter before one()."""
        filtered = self._maybe_filter_by_tenant()
        if filtered is self:
            return super(TenantQuery, self).one()
        return filtered.one()
        
    def one_or_none(self):
        """Apply tenant filter before one_or_none()."""
        filtered = self._maybe_filter_by_tenant()
        if filtered is self:
            return super(TenantQuery, self).one_or_none()
        return filtered.one_or_none()
        
    def get(self, ident):
        """Apply tenant filter to get()."""
        obj = super().get(ident)
        if obj:
            from flask import g
            tenant_id = getattr(g, 'current_tenant_id', None)
            if tenant_id and hasattr(obj, 'tenant_id') and obj.tenant_id != tenant_id:
                return None
        return obj
        
    def count(self):
        """Apply tenant filter before count()."""
        filtered = self._maybe_filter_by_tenant()
        if filtered is self:
            return super(TenantQuery, self).count()
        return filtered.count()
        
    def exists(self):
        """Apply tenant filter before exists()."""
        filtered = self._maybe_filter_by_tenant()
        if filtered is self:
            return super(TenantQuery, self).exists()
        return filtered.exists()


class TenantModel(db.Model):
    """Abstract base model for tenant-scoped entities.
    
    All models that should be filtered by tenant_id should inherit from this.
    """
    __abstract__ = True
    query_class = TenantQuery
    tenant_id = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False, index=True)


# Import models after db is defined to avoid circular imports
from dinkydash.models.family import Family
from dinkydash.models.user import User
from dinkydash.models.dashboard import Dashboard
from dinkydash.models.task import Task
from dinkydash.models.countdown import Countdown

__all__ = ['db', 'TenantModel', 'Family', 'User', 'Dashboard', 'Task', 'Countdown']
