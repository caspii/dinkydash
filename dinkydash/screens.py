"""The token that puts a dashboard on a wall. Cloud mode only.

    looks_like_a_token(value)      -> is this worth a query at all
    family_for_token(pool, token)  -> the family id, or None
    rotate(pool, family_id)        -> the new token, or None if that family is gone

A wall panel cannot sign in. There is no keyboard on a kitchen tablet left on a
shelf, and a thirty-day session is the wrong shape for furniture anyway — so
the dashboard is reached by an unguessable URL instead (PLAN.md, Screen URLs), and
this module is the only thing that turns one into a family.

**The token is a bearer credential with none of a magic link's defences.** It
does not expire, it is not single use, and it is meant to sit in a browser for
months. Three things carry the weight instead:

* **it is only ever a dashboard.** No settings, no email address, no way to change
  anything. What leaks is one family's day, which is bad and is not an account;
* **rotation is the revocation**, and it is the whole of it. `rotate` below is
  what a parent presses when a screenshot went somewhere it should not have,
  and the old URL stops working the moment they do;
* **~59 bits.** Twelve characters of `config.ID_ALPHABET`, which is the
  unambiguous one — a token that has to be read off a television and typed on a
  remote cannot contain `0`, `O`, `1` or `l`.

**This is the third unscoped read in the product**, after `worker.family_ids`
and `dinkydash/accounts.py`, and it is unscoped for the same kind of reason:
there is no session to scope to. A screen is anonymous by design. Everything it
then reads goes through a `PostgresStore` built for exactly the family the
token named, so the scoping rule that matters is untouched.

Like `accounts.py`, this imports no driver: it is handed a pool and asks it for
connections, so `pgstore.py` and `db.py` remain the only two files that pull in
psycopg. (Written that way round on purpose — `grep -rn "import psycopg"` is
the check CLAUDE.md tells people to run, and a docstring that answers it is a
docstring that makes the check useless.)
"""

import logging

from . import config as config_module

log = logging.getLogger(__name__)

# What the column allows, and therefore the only lengths worth a round trip.
# `families.screen_token` is `CHECK (length(screen_token) BETWEEN 10 AND 32)`.
SHORTEST_TOKEN = 10
LONGEST_TOKEN = 32

# Attempts before `rotate` gives up. The same three as `accounts._new_family`,
# and for the same reason: a collision is not something anyone will see, but
# the column is UNIQUE and an unhandled violation would be a 500 on a button
# press.
TRIES = 3


def looks_like_a_token(value):
    """Could this be one of ours? Checked before it reaches a query.

    Not a security boundary — the token is compared exactly, and a parameterised
    query is what keeps the value out of the SQL. This is here so that a crawler
    walking `/s/wp-admin.php` costs a string comparison rather than a connection
    from a pool with 22 of them behind it, and so a URL long enough to be an
    attack is refused before anything hashes it.
    """
    if not isinstance(value, str):
        return False
    if not SHORTEST_TOKEN <= len(value) <= LONGEST_TOKEN:
        return False
    return set(value) <= set(config_module.ID_ALPHABET)


def family_for_token(pool, token):
    """Which family's dashboard that URL shows, or None.

    One answer for a token that is malformed, mistyped, rotated away or never
    issued, in the same way `accounts.consume_link` gives one answer for
    expired, spent and never-issued. There is nothing here for a caller to leak
    by accident, and nothing an enumerator can tell apart.
    """
    if not looks_like_a_token(token):
        return None
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM families WHERE screen_token = %s", (token,))
        row = cur.fetchone()
        return row[0] if row else None


def token_for(pool, family_id):
    """That family's current screen token, or None if the family is gone.

    The inverse of `family_for_token`, and the only other query here. It is
    what the settings page prints and what `/preview` frames, so it is asked
    for by a signed-in caller that already holds the family id — never by a
    caller holding the token, which would be asking a question it already
    knows the answer to.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT screen_token FROM families WHERE id = %s",
                    (family_id,))
        row = cur.fetchone()
        return row[0] if row else None


def rotate(pool, family_id):
    """Give that family a new screen token, and return it. None if it is gone.

    **Scoped by its caller**, which passes the family on the session — this
    takes an id rather than finding one, so there is no way to rotate somebody
    else's dashboard without first holding their session.

    The new token is generated and checked in the same statement, so the UNIQUE
    index is the backstop rather than the error path. `screen_token_rotated_at`
    moves with it because a parent asking "did I already do this?" is the whole
    reason that column exists.
    """
    for _ in range(TRIES):
        token = config_module.new_screen_token()
        with pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE families
                       SET screen_token = %s, screen_token_rotated_at = now(),
                           updated_at = now()
                       WHERE id = %s
                         AND NOT EXISTS (
                             SELECT 1 FROM families WHERE screen_token = %s)
                       RETURNING id""",
                    (token, family_id, token),
                )
                if cur.fetchone() is not None:
                    log.info("Rotated a screen token.")
                    return token
    # Either every generated token collided — which is not a thing that happens
    # at 59 bits — or the family does not exist. The caller cannot tell the two
    # apart and does not need to: both mean "no new URL", and a session naming a
    # family that has gone is already handled by `NoSuchFamily` elsewhere.
    return None

