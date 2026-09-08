"""Users, and the links that sign them in. Cloud mode only.

    normalise(email)             -> the address as it is compared
    user_for(pool, email)        -> (user_id, family_id), or None
    issue_link(pool, user_id)    -> the plaintext token, or None if rate-limited
    consume_link(pool, token)    -> (user_id, family_id), or None
    sweep(pool)                  -> how many dead tokens were deleted

One email in, one link out, one session (PLAN.md phase 1). Signing in through
the link *is* email verification: there is no second step, no password, and
nothing to reset.

**Only the hash is stored.** The plaintext exists for the length of one email
and is never written anywhere else — not to a row, not to a log line, not into
an exception message. Whoever reads the database gets 64 characters of SHA-256
and no way back to a working link.

**SHA-256, not a slow KDF.** A password is low-entropy and needs bcrypt or
argon2 to make guessing expensive. This token is 32 random bytes from
`secrets`, so there is nothing to guess and a slow hash would only make every
login slower. What matters instead is that the lookup cannot be walked, and it
cannot: an attacker would have to invert SHA-256 to control the value being
matched.

**Single use is one statement.** `UPDATE ... WHERE used_at IS NULL AND
expires_at > now() RETURNING` decides and marks in the same breath, so two
clicks on one link — or a mail scanner following it a second before the person
does — cannot both come back with a user. A read-then-write would let both
through, and it would look correct in every test that ran them in order.

**Time comes from Postgres, never from Python.** `now()` is the transaction's
clock, one clock for however many web instances, and it cannot drift out of
step with the row it is being compared to.

This module imports no psycopg — it is handed a pool and asks it for
connections — so the rule that `pgstore.py` and `db.py` are the only files
importing the driver still holds. It is not part of the engine either: nothing
under the `generate()` boundary knows that users exist.
"""

import hashlib
import logging
import secrets
from datetime import timedelta

log = logging.getLogger(__name__)

# How long a link works. Short because a link is a bearer credential and its
# whole defence is not being around long.
TOKEN_TTL = timedelta(minutes=15)

# 32 bytes of entropy, url-safe, which is 43 characters. Long enough that
# enumeration is not a thing; short enough to survive a mail client wrapping
# a line.
TOKEN_BYTES = 32

# The per-person rate limit, and it is a spend control as much as a security
# one: every request sends an email on an account whose sender reputation is
# shared with KeepTheScore.
#
# Counted as "unexpired links", which has two consequences worth stating
# because both have been misread:
#
# * the sweep cannot affect it — a row it deletes is one this no longer counts;
# * **a used link still counts.** Spending one does not free a slot. The limit
#   is on emails sent in a window, and the email went whatever happened next.
MOST_LIVE_LINKS = 3

# Anything longer than a real token is not one, and there is no reason to hash
# it to find that out. A URL can carry a great deal.
LONGEST_TOKEN = 200


def normalise(email):
    """The address as it is compared and stored: trimmed and lower-cased.

    Email local parts are case-sensitive to the letter of the RFC and to
    nobody's mail server. A parent who types their address with a capital on
    Tuesday has to get in on Wednesday.
    """
    return (email or "").strip().lower()


def new_token():
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token):
    """What the row holds. Hex, so it fits the column's TEXT and its length check."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def user_for(pool, email):
    """Who that address belongs to, or None.

    Compared with `lower()` on both sides rather than trusting how the row was
    written, because a user created by hand or by an import is not this
    module's doing. `users` holds one row per family, so the scan this costs is
    not worth a functional index yet — when it is, the index is
    `(lower(email))` and this query is already shaped for it.
    """
    address = normalise(email)
    if not address:
        return None
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, family_id FROM users WHERE lower(email) = %s",
            (address,),
        )
        return cur.fetchone()


def issue_link(pool, user_id, ttl=TOKEN_TTL, most=MOST_LIVE_LINKS):
    """Mint one token for that user. Returns the plaintext, or None if limited.

    The limit is inside the INSERT rather than a SELECT before it, so two
    requests arriving together cannot both read "two live links" and both make
    a third. The caller must answer identically either way — a request that is
    silently dropped and one that sends an email have to look the same from
    outside, or the rate limit becomes the account-enumeration oracle that the
    identical wording exists to prevent.
    """
    token = new_token()
    with pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO login_tokens (user_id, token_hash, expires_at)
                   SELECT %s, %s, now() + %s
                   WHERE (SELECT count(*) FROM login_tokens
                          WHERE user_id = %s AND expires_at > now()) < %s
                   RETURNING id""",
                (user_id, hash_token(token), ttl, user_id, most),
            )
            if cur.fetchone() is None:
                # Not an error and not logged as one: asking twice is what a
                # person does when the first email is slow.
                return None
    return token


def consume_link(pool, token):
    """Spend a token. Returns (user_id, family_id), or None for anything wrong.

    Expired, already used, and never issued are one answer on purpose. The
    caller shows one page for all three, so there is nothing here for a caller
    to leak by accident.
    """
    if not token or len(token) > LONGEST_TOKEN:
        return None
    with pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE login_tokens
                   SET used_at = now()
                   WHERE token_hash = %s
                     AND used_at IS NULL
                     AND expires_at > now()
                   RETURNING user_id""",
                (hash_token(token),),
            )
            row = cur.fetchone()
            if row is None:
                return None
            cur.execute(
                "UPDATE users SET last_login_at = now() WHERE id = %s "
                "RETURNING id, family_id",
                (row[0],),
            )
            return cur.fetchone()


def sweep(pool):
    """Delete every token that has expired. Returns how many went.

    A used token is deleted by the same rule, once its fifteen minutes are up:
    there is nothing to learn from keeping it, and a table of hashes of dead
    credentials is a table somebody has to think about in the privacy policy.
    Walks `login_tokens_expires_idx`, which exists for this.
    """
    with pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM login_tokens WHERE expires_at < now()")
            return cur.rowcount
