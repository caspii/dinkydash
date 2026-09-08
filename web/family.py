"""Which family a request is for, and the store that reaches only their rows.

    current_store()   the store this request reads and writes through

One line decides the whole of multi-tenancy:

    cloud    one store per request, built from the family on the session
    single   one store per process, because there is one family and no session

**In cloud mode the family comes from the session and from nowhere else.**
Not from a path segment, not from a query parameter, not from a form field and
not from a header. That is a stronger promise than checking an id against the
session, because there is no id to check: nothing a caller can send reaches a
query as a family selector. When a route does one day need to name a family in
its URL — the admin view is the likely first — the check belongs here, before
the store is built, and **a mismatch is a 404 and never a 403**: "forbidden"
confirms the row exists, which tells one family that another one does.

The ids that *do* appear in URLs today are item ids inside one family's config
document — `/settings/people/<item_id>`. They are already scoped by which
family's config was loaded, so another family's id is simply not in the list
and `find_item` 404s. `tests/test_tenancy.py` asserts that rather than assuming
it.

**One store per request must not mean one pool per request.** The pool is
built once in `create_app` and lives for the life of the process; a
`PostgresStore` is two attributes wrapped round it and costs nothing to build.
Building a `ConnectionPool` per request would exhaust the cluster's 22
connections and DigitalOcean's PgBouncer in front of them.

The worker does not come through here and must not. `worker.family_ids` is the
one deliberately unscoped read in the product, because there is no request and
no user: walking every family is its job.
"""

import uuid

from flask import abort, current_app, g, session

from .session import FAMILY_ID


def current_store():
    """The store this request reads and writes through."""
    from . import CLOUD

    if current_app.config["MODE"] != CLOUD:
        # One family, one file, no session. A Pi builds this once at start-up.
        return current_app.config["STORE"]
    return _for_the_session()


def current_family_id():
    """The family this request is for, as a string. Cloud mode only."""
    return _family_on_the_session()


def _for_the_session():
    """One `PostgresStore`, cached for the length of this request.

    Cached on `g` rather than rebuilt, so two calls in one view are one object
    — and so that "one store per request" is literally true rather than
    approximately true.
    """
    store = g.get("_store")
    if store is not None:
        return store

    family_id = _family_on_the_session()
    pool = current_app.config.get("POOL")
    if pool is None:
        raise RuntimeError(
            "Cloud mode has no connection pool, so no request can be served."
        )

    from dinkydash.pgstore import PostgresStore

    store = g._store = PostgresStore(pool, family_id)
    return store


def _family_on_the_session():
    """The family id on the session, checked before it can reach a query.

    Flask signs the cookie, so this value is one we put there — but it is
    parsed as a UUID anyway before it goes anywhere near SQL. Belt and braces
    costs one function call, and "the session is signed" is the kind of
    assumption that survives right up until somebody adds a second way to write
    a session.

    **404, not a redirect.** Every route that reaches a store in cloud mode is
    behind `session.guard`, which sends a signed-out visitor to `/login`. So
    getting here without a family means something is wrong rather than somebody
    being signed out, and 404 is the answer that says nothing at all.
    """
    claimed = session.get(FAMILY_ID)
    try:
        return str(uuid.UUID(str(claimed)))
    except (AttributeError, TypeError, ValueError):
        abort(404)
