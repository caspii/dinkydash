"""Which family a request is for, and the store that reaches only their rows.

    current_store()   the store this request reads and writes through

One line decides the whole of multi-tenancy:

    cloud    one store per request, built from the family on the session
    single   one store per process, because there is one family and no session

**In cloud mode the family comes from the session and from nowhere else** —
with exactly one exception, which is below and is the whole of it. Not from a
path segment, not from a query parameter, not from a form field and not from a
header. That is a stronger promise than checking an id against the session,
because there is no id to check: nothing a caller can send reaches a query as a
family selector. When a route does one day need to name a *family* in its URL —
the admin view is the likely first — the check belongs here, before the store
is built, and **a mismatch is a 404 and never a 403**: "forbidden" confirms the
row exists, which tells one family that another one does.

**The exception is the screen, and it is not a hole in that rule.** A wall
panel cannot sign in, so `/s/<token>` names a family with an unguessable
credential instead of a session (DIN-42). What a caller sends is still not a
family *id*: it is a 59-bit secret that `screens.family_for_token` either
resolves to exactly one family or does not resolve at all, and everything read
afterwards goes through a `PostgresStore` scoped to that family like any other.
Both doors are here, in one file, on purpose — if a third is ever added it
should be as obvious as these two are.

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


def current_budget():
    """What this request's family may still spend on the model.

    `NoBudget` in single mode — a self-hoster's key is their own bill, and the
    board is not multi-tenant. In cloud mode a Postgres-backed breaker for the
    family on the session, which is the same money the worker spends and so is
    counted in the same place (DIN-43).
    """
    from dinkydash import budget as budget_module
    from . import CLOUD

    if current_app.config["MODE"] != CLOUD:
        return budget_module.NoBudget()
    return budget_module.for_family(_the_pool(), _family_on_the_session())


def current_screen_token():
    """The screen token of the family on the session. Cloud mode only.

    Lives here rather than in a route because it needs the same two things
    `current_store` does — the process pool, and the family the session names —
    and because "which family" should be answered in one file however it is
    being asked.
    """
    from dinkydash import screens

    return screens.token_for(_the_pool(), _family_on_the_session())


def store_for_token(token):
    """The store for the family that screen token belongs to, or None.

    The screen's half of `current_store`, and the only place a caller's own
    string decides which family gets read. Two things keep that safe:

    * **the token is a secret, not an identifier.** A wrong one names nothing —
      there is no neighbouring family to land on the way an off-by-one id would
      find one — so guessing is the only attack, and 59 bits is the answer to it;
    * **one answer for every kind of miss.** Never issued, mistyped and rotated
      away this morning all return None here, and `web/routes/screen.py` turns
      that into a 404 and never a 403. It answers rather than this function,
      because a miss is also the thing the screen rate limit counts.

    Cached on `g` like the session's store, so the board and its manifest are
    one lookup rather than two, and one object rather than two.
    """
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
    """One `PostgresStore`, cached for the length of this request.

    Cached on `g` rather than rebuilt, so two calls in one view are one object
    — and so that "one store per request" is literally true rather than
    approximately true.
    """
    store = g.get("_store")
    if store is not None:
        return store

    family_id = _family_on_the_session()
    from dinkydash.pgstore import PostgresStore

    store = g._store = PostgresStore(_the_pool(), family_id)
    return store


def _the_pool():
    """The process-wide pool, or a loud failure.

    **One pool per process, never one per request.** The cluster has 22
    connections and a PgBouncer in front of them; a `PostgresStore` is two
    attributes wrapped round this and costs nothing to build.
    """
    pool = current_app.config.get("POOL")
    if pool is None:
        raise RuntimeError(
            "Cloud mode has no connection pool, so no request can be served."
        )
    return pool


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
