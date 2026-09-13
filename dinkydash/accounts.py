"""Cloud accounts and magic links.

Only SHA-256 hashes of random tokens are stored. Consuming a link verifies the
mailbox; a signup creates its family in that same transaction. Unexpired
tokens count toward the email limit even after use. See dinkydash/CLAUDE.md
for the authentication invariants and the design rationale.
"""

import hashlib
import json
import logging
import secrets
from datetime import timedelta

from . import config as config_module

log = logging.getLogger(__name__)

TOKEN_TTL = timedelta(minutes=15)
TOKEN_BYTES = 32
MOST_LIVE_LINKS = 3
LONGEST_TOKEN = 200
LONGEST_EMAIL = 320
TRIAL = timedelta(days=14)
SCREEN_TOKEN_TRIES = 3


def normalise(email):
    """The address as it is compared and stored: trimmed and lower-cased."""
    return (email or "").strip().lower()


def new_token():
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token):
    """What the row holds. Hex, so it fits the column's TEXT and its length check."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def user_for(pool, email):
    """Return (user_id, family_id) for an address, or None."""
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
    """Mint a login token, or return None when the recipient is limited."""
    return _issue_link(pool, user_id, None, ttl, most)


def issue_signup_link(pool, email, ttl=TOKEN_TTL, most=MOST_LIVE_LINKS):
    """Mint a signup token for a valid address, or None if invalid or limited."""
    address = normalise(email)
    if not address or "@" not in address or len(address) > LONGEST_EMAIL:
        return None
    return _issue_link(pool, None, address, ttl, most)


def _issue_link(pool, user_id, email, ttl, most):
    """Serialise issuance for one recipient, including when no user exists yet."""
    token = new_token()
    subject = f"login_tokens:{user_id}:{email}"
    digest = hashlib.sha256(subject.encode("utf-8")).digest()
    lock_key = int.from_bytes(digest[:8], "big", signed=True)
    with pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            # Acquire the lock in a separate statement so the INSERT's READ
            # COMMITTED snapshot includes any issuer that just committed.
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))
            cur.execute(
                """INSERT INTO login_tokens (user_id, email, token_hash, expires_at)
                   SELECT %s, %s, %s, now() + %s
                   WHERE (SELECT count(*) FROM login_tokens
                          WHERE (user_id = %s OR email = %s)
                            AND expires_at > now()) < %s
                   RETURNING id""",
                (user_id, email, hash_token(token), ttl, user_id, email, most),
            )
            if cur.fetchone() is None:
                return None
    return token


def consume_link(pool, token):
    """Spend a token and return (user_id, family_id), or None for any invalid link.

    The token update and any family creation share a transaction. A failed signup
    therefore leaves the token usable.
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
    """Create or find this address's family inside the caller's transaction.

    Concurrent clicks can race the user insert. The loser deletes its provisional
    family and signs in to the account the other transaction created.
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
    """Create a trial family with a screen token and starter config."""
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
    """Return only the recipient's domain for logging."""
    _, _, domain = normalise(address).partition("@")
    return f"@{domain}" if domain else "@?"


def address_for(pool, user_id):
    """Read the account's address; the signed, unencrypted session stores only ids."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT email FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None


def delete_family(pool, family_id):
    """Delete a family and its dependent rows in one transaction.

    Signup tokens have no user foreign key, so delete those by address explicitly.
    Returns whether the family existed.
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
        log.info("Deleted family %s and everything belonging to it.", family_id)
    return gone


def sweep(pool):
    """Delete expired tokens, including used ones, and return the count."""
    with pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM login_tokens WHERE expires_at < now()")
            return cur.rowcount
