"""
Multi-tenant isolation utilities.
Automatically filters database queries by tenant_id to prevent cross-tenant data access.
"""
from flask import g, abort
from sqlalchemy import event


def get_current_tenant_id():
    """
    Get the current tenant ID from Flask's g object.

    Returns:
        int: Current tenant ID, or None if not set

    Raises:
        403: If tenant_id is required but not set
    """
    return getattr(g, 'current_tenant_id', None)


def require_tenant():
    """
    Ensure a tenant is set in the current context.

    Raises:
        403: If no tenant_id is set in g.current_tenant_id
    """
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        abort(403, description="Tenant context required")
    return tenant_id


def init_tenant_filter(db):
    """
    Initialize automatic tenant filtering for database queries.

    Since TenantModel already has a custom query_class, this function
    now just serves as a placeholder for any additional tenant filtering
    setup that might be needed in the future.

    Args:
        db: Flask-SQLAlchemy database instance
    """
    # Tenant filtering is now handled by TenantQuery class in models/__init__.py
    pass


def set_tenant_on_insert(mapper, connection, target):
    """
    Automatically set tenant_id on new records.

    This is called by SQLAlchemy before inserting a record.
    If the model has a tenant_id column and it's not set,
    this will automatically set it to the current tenant.

    Args:
        mapper: SQLAlchemy mapper
        connection: Database connection
        target: The model instance being inserted
    """
    if hasattr(target, 'tenant_id'):
        # Only set if not already set
        if target.tenant_id is None:
            tenant_id = get_current_tenant_id()
            if tenant_id is not None:
                target.tenant_id = tenant_id


def register_tenant_models(db, models):
    """
    Register models for automatic tenant_id insertion.

    Args:
        db: Flask-SQLAlchemy database instance
        models (list): List of model classes that have tenant_id
    """
    for model in models:
        if hasattr(model, 'tenant_id'):
            event.listen(model, 'before_insert', set_tenant_on_insert)
