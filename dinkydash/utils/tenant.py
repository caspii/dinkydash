"""
Multi-tenant isolation utilities.
Automatically filters database queries by tenant_id to prevent cross-tenant data access.
"""
from flask import g, abort
from sqlalchemy import event
from sqlalchemy.orm import Query


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

    This sets up SQLAlchemy event listeners that automatically add
    tenant_id filters to all queries on models with a tenant_id column.

    Args:
        db: Flask-SQLAlchemy database instance
    """

    @event.listens_for(Query, "before_compile", retval=True)
    def _before_compile(query):
        """
        Automatically add tenant_id filter to queries.

        This event listener runs before every query is compiled and
        adds a filter for the current tenant_id if:
        1. The model has a tenant_id column
        2. A tenant_id is set in g.current_tenant_id
        3. The query doesn't already have a tenant_id filter
        """
        # Get current tenant ID
        tenant_id = get_current_tenant_id()

        # If no tenant set, don't filter (allows admin queries)
        if tenant_id is None:
            return query

        # Check if the query is for a model with tenant_id
        for entity in query.column_descriptions:
            # Get the model class
            model = entity.get('entity') or entity.get('type')
            if model is None:
                continue

            # Check if model has tenant_id column
            if hasattr(model, 'tenant_id'):
                # Check if query already has tenant_id filter
                # (to avoid duplicate filters)
                whereclause = query.whereclause
                if whereclause is not None:
                    # Convert to string to check if tenant_id is already filtered
                    where_str = str(whereclause.compile(compile_kwargs={"literal_binds": True}))
                    if 'tenant_id' in where_str:
                        # Already has tenant_id filter, skip
                        return query

                # Add tenant_id filter
                query = query.filter(model.tenant_id == tenant_id)
                break

        return query


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
