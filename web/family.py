"""Resolve a request's family and its scoped store.

Cloud requests use the signed session or a verified screen token. Stores are
cached on Flask's g and share the app's pool. Single mode uses a fixed store.
See web/CLAUDE.md for route authentication requirements.
"""

import uuid

from flask import abort, current_app, g, session

from .session import FAMILY_ID


def current_store():
    """The store this request reads and writes through."""
    from . import CLOUD

    if current_app.config["MODE"] != CLOUD:
        return current_app.config["STORE"]
    return _for_the_session()


def current_family_id():
    """The family this request is for, as a string. Cloud mode only."""
    return _family_on_the_session()


def current_budget():
    """Return this family's cloud spend breaker, or NoBudget in single mode."""
    from dinkydash import budget as budget_module
    from . import CLOUD

    if current_app.config["MODE"] != CLOUD:
        return budget_module.NoBudget()
    return budget_module.for_family(_the_pool(), _family_on_the_session())


def current_access():
    """Hosted access for the signed-in parent; single mode has no account."""
    from dinkydash.lifecycle import access_for
    from . import CLOUD

    if current_app.config["MODE"] != CLOUD:
        return None
    return access_for(_the_pool(), _family_on_the_session())


def current_screen_token():
    """Return the screen token of the family on the session. Cloud mode only."""
    from dinkydash import screens

    return screens.token_for(_the_pool(), _family_on_the_session())


def store_for_token(token):
    """Return the request's store for a valid screen token, or None on a miss."""
    store = g.get("_store")
    if store is not None:
        return store

    from dinkydash import screens

    pool = _the_pool()
    family_id = screens.family_for_token(pool, token)
    if family_id is None:
        return None

    from dinkydash.pgstore import PostgresStore

    store = g._store = PostgresStore(pool, family_id)
    return store


def _for_the_session():
    """Return a PostgresStore scoped to the session and cached for this request."""
    store = g.get("_store")
    if store is not None:
        return store

    family_id = _family_on_the_session()
    from dinkydash.pgstore import PostgresStore

    store = g._store = PostgresStore(_the_pool(), family_id)
    return store


def _the_pool():
    """Return the app's shared pool, or fail if cloud mode is misconfigured."""
    pool = current_app.config.get("POOL")
    if pool is None:
        raise RuntimeError(
            "Cloud mode has no connection pool, so no request can be served."
        )
    return pool


def _family_on_the_session():
    """Parse the session's family UUID; reject a missing or malformed claim with 404."""
    claimed = session.get(FAMILY_ID)
    try:
        return str(uuid.UUID(str(claimed)))
    except (AttributeError, TypeError, ValueError):
        abort(404)
