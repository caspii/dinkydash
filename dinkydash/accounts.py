"""Users, the links that sign them in, and the families those links create.
Cloud mode only.

    normalise(email)                 -> the address as it is compared
    user_for(pool, email)            -> (user_id, family_id), or None
    issue_link(pool, user_id)        -> the plaintext token, or None if limited
    issue_signup_link(pool, email)   -> the same, for an address with no account
    consume_link(pool, token)        -> (user_id, family_id), or None
    sweep(pool)                      -> how many dead tokens were deleted

One email in, one link out, one session (PLAN.md phase 1). Signing in through
the link *is* email verification: there is no second step, no password, and
nothing to reset.

**Sign-up is the same act, and the same token** (DIN-41). An address with no
account gets a token carrying the address instead of a user id; spending it
creates the family and the user and signs them in. There is one `consume_link`
because single use is the property everything else rests on, and a second copy
of that statement is a second thing to keep right.

**The family is created when the link is clicked, never when the address is
submitted.** A `families` row starts a 14-day trial and the worker calls
Anthropic daily for it, so creating one on an unverified POST would let a
script run up a real bill with no card behind it. This way an unverified
sign-up costs one token row and one email, and the existing sweep is already
the cleanup. It is a rate limit's worth of protection rather than a cap: the
cap is the global spend breaker, which is PLAN.md phase 2 and still to come.

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
import json
import logging
import secrets
from datetime import timedelta

from . import config as config_module

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

# What `users.email` and `login_tokens.email` both allow, and the longest an
# address can be under RFC 5321. Checked here rather than left to the column,
# because a CHECK violation is a 500 on a route anybody can post to.
LONGEST_EMAIL = 320

# The trial, in the app rather than in Stripe (PLAN.md decisions 6 and phase 4):
# a family that never converts never becomes a Stripe customer.
TRIAL = timedelta(days=14)

# How many times to try for an unused screen token before giving up. 12
# characters of `config.ID_ALPHABET` is about 59 bits, so a collision is not
# something anyone will see — but the column is UNIQUE, and an unhandled
# violation here would spend somebody's sign-up link and hand them a 500. Three
# tries costs nothing and turns an astronomically rare 500 into a retry.
SCREEN_TOKEN_TRIES = 3


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


def issue_signup_link(pool, email, ttl=TOKEN_TTL, most=MOST_LIVE_LINKS):
    """Mint one token for an address with no account. Plaintext, or None.

    The same shape as `issue_link` and deliberately so: the same TTL, the same
    single use, and the same "at most three live at once" counted inside the
    INSERT rather than in a SELECT before it. The only difference is what the
    row points at — an address, because the user it will become does not exist
    yet.

    **It does not check whether the address already has an account**, and does
    not need to: `_start_a_family` signs an existing user in rather than making
    them a second family, so a token minted by mistake is harmless. The check
    belongs at the call site, which needs the answer anyway to choose which
    email to send.
    """
    address = normalise(email)
    if not address or "@" not in address or len(address) > LONGEST_EMAIL:
        return None
    token = new_token()
    with pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO login_tokens (email, token_hash, expires_at)
                   SELECT %s, %s, now() + %s
                   WHERE (SELECT count(*) FROM login_tokens
                          WHERE email = %s AND expires_at > now()) < %s
                   RETURNING id""",
                (address, hash_token(token), ttl, address, most),
            )
            if cur.fetchone() is None:
                # Same as the sign-in half: asking twice is what somebody does
                # when the first email is slow, so this is not an error.
                return None
    return token


def consume_link(pool, token):
    """Spend a token. Returns (user_id, family_id), or None for anything wrong.

    Expired, already used, and never issued are one answer on purpose. The
    caller shows one page for all three, so there is nothing here for a caller
    to leak by accident.

    **Two kinds of token, one statement.** The UPDATE below marks either kind
    used; what comes back decides what happens next. A `user_id` means somebody
    signing in. An `email` means somebody signing up, and the family is created
    here — inside the same transaction that spent the token, so a family can
    never exist for a link that did not work.
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
                   RETURNING user_id, email""",
                (hash_token(token),),
            )
            row = cur.fetchone()
            if row is None:
                return None
            user_id, email = row
            if user_id is None:
                return _start_a_family(cur, email)
            cur.execute(
                "UPDATE users SET last_login_at = now() WHERE id = %s "
                "RETURNING id, family_id",
                (user_id,),
            )
            return cur.fetchone()


def _start_a_family(cur, email):
    """Create the family and the parent, and return (user_id, family_id).

    **One transaction, and the caller's.** A `families` row with no user is
    unreachable and a `users` row with no family violates the foreign key, so
    there is no half-way state worth keeping — and because this runs inside the
    same transaction that spent the token, a failure anywhere leaves the token
    unspent and the person able to click again.

    **A second link for the same new address must not make a second family.**
    Two POSTs before either click mints two tokens, and both work. So the
    address is looked up first, and the INSERT that follows carries
    `ON CONFLICT DO NOTHING` for the case where the two clicks land close
    enough together that the lookup missed. Losing that race means undoing the
    family just created — hence the DELETE, which removes a row nothing else
    can have seen yet.
    """
    address = normalise(email)
    cur.execute("SELECT id FROM users WHERE lower(email) = %s", (address,))
    existing = cur.fetchone()
    if existing is None:
        family_id = _new_family(cur)
        cur.execute(
            """INSERT INTO users (family_id, email, last_login_at)
               VALUES (%s, %s, now())
               ON CONFLICT (email) DO NOTHING
               RETURNING id, family_id""",
            (family_id, address),
        )
        made = cur.fetchone()
        if made is not None:
            log.info("Created a family for a %s address.", _domain(address))
            return made
        cur.execute("DELETE FROM families WHERE id = %s", (family_id,))

    cur.execute(
        "UPDATE users SET last_login_at = now() WHERE lower(email) = %s "
        "RETURNING id, family_id",
        (address,),
    )
    return cur.fetchone()


def _new_family(cur):
    """One `families` row, on the trial, with a screen token and a board to show.

    The token is generated here and checked in the same statement rather than
    trusted, so the UNIQUE index is the backstop and not the error path.
    """
    starter = json.dumps(config_module.starter_config())
    for _ in range(SCREEN_TOKEN_TRIES):
        token = config_module.new_screen_token()
        cur.execute(
            """INSERT INTO families (screen_token, config, trial_ends_at)
               SELECT %s, %s::jsonb, now() + %s
               WHERE NOT EXISTS (
                   SELECT 1 FROM families WHERE screen_token = %s)
               RETURNING id""",
            (token, starter, TRIAL, token),
        )
        row = cur.fetchone()
        if row is not None:
            return row[0]
    raise RuntimeError(
        f"No unused screen token in {SCREEN_TOKEN_TRIES} tries, which should "
        "not be possible at 59 bits — check new_screen_token.")


def _domain(address):
    """The part of an address that is not a person, for a log line.

    The same rule the login route follows: a flood from one domain is worth
    seeing, and the list of who has an account is the thing none of this
    publishes.
    """
    _, _, domain = normalise(address).partition("@")
    return f"@{domain}" if domain else "@?"


def address_for(pool, user_id):
    """The address on that account, or None. For showing somebody their own.

    Deliberately a query rather than a session value: `web/session.py` puts two
    ids in the cookie and no email, because Flask signs the cookie and does not
    encrypt it.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT email FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None


def delete_family(pool, family_id):
    """Delete a family and everything belonging to it. Returns True if there was one.

    **The cascade does most of this, and there is exactly one thing it cannot
    reach.** `families` is the root and every other table references it with
    `ON DELETE CASCADE` — users, agendas, generations, content_history,
    calendar_health, model_spend — and `login_tokens` follows its user. But a
    **sign-up token has no user** (DIN-41): it carries an address instead,
    precisely so that it can exist before the family does. Nothing cascades to
    it, so it is deleted here by address, in the same transaction.

    Left alone it would expire in fifteen minutes and be swept, so this is not a
    security hole — it is the difference between "deleted" meaning what the
    privacy policy says it means and meaning nearly that.

    One transaction, so a half-deleted family is not a state that can exist.
    """
    with pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT email FROM users WHERE family_id = %s", (family_id,))
            addresses = [row[0] for row in cur.fetchall()]
            if addresses:
                cur.execute(
                    "DELETE FROM login_tokens WHERE user_id IS NULL AND email = ANY(%s)",
                    (addresses,),
                )
            cur.execute("DELETE FROM families WHERE id = %s RETURNING id",
                        (family_id,))
            gone = cur.fetchone() is not None
    if gone:
        # The id, never the address. A deletion is worth a line — it is the one
        # thing nobody can undo — and the line must not be the record of who
        # left that the deletion was supposed to remove.
        log.info("Deleted family %s and everything belonging to it.", family_id)
    return gone


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
