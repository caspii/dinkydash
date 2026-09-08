#!/usr/bin/env python3
"""Print a working sign-in link for an account that already exists. Cloud mode only.

    python login_link.py you@example.com
    python login_link.py you@example.com --base-url http://127.0.0.1:5173

**Why this exists.** The settings UI is behind a magic link, and a magic link
arrives by email. That is right for a parent and tedious for the person editing
the page, who would otherwise wait on SendGrid to look at their own change. It
is also what support needs on the day somebody's mail is bouncing.

**There is no bypass here, and there must never be one.** It mints an ordinary
token through `dinkydash.accounts`, subject to the same fifteen minutes, the
same single use and the same per-address limit of three live links. The only
thing it skips is the email.

**What it prints is a credential.** Anyone holding that line can sign in as
that person until it is spent. It grants nothing you did not already have —
running it needs the database password — but pasting it into an issue, a chat
or a screenshot hands it to somebody who has neither.

**It does not create accounts, and no longer needs to.** Sign-up is the
product's job and the product now does it (DIN-41): posting an address to
`/login` sends a link, and clicking that link creates the family. This is for
getting into an account that already exists without waiting on email — which
is the developer's case and the support case, not a new family's.

Reads `DATABASE_URL`, like the app.
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from dinkydash import accounts, db

load_dotenv()


def base_url(given):
    """Where the link should point. Explicit, then the app's hostname, then local.

    https for a real hostname because the token is a bearer credential and a
    plain-http link puts it on the wire; http for the fallback because that is
    what `flask run` serves on a laptop.
    """
    if given:
        return given.rstrip("/")
    host = os.environ.get("DINKYDASH_APP_HOST", "").strip()
    if host:
        return f"https://{host}"
    return "http://127.0.0.1:5000"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Print a sign-in link for an existing DinkyDash account.")
    parser.add_argument("email", help="the address on the account")
    parser.add_argument("--base-url",
                        help="where the link points (default: DINKYDASH_APP_HOST, "
                             "else http://127.0.0.1:5000)")
    parser.add_argument("--database-url", help="override DATABASE_URL")
    args = parser.parse_args(argv)

    pool = db.pool(args.database_url or db.require("DATABASE_URL"))
    try:
        user = accounts.user_for(pool, args.email)
        if user is None:
            # Said plainly here, unlike the web route: this is a local tool run
            # by somebody holding the database password, so there is nobody to
            # enumerate accounts for.
            print(f"No account for {args.email}. To make one, post the address "
                  f"to /login and click the link it sends — that is what "
                  f"creates a family.", file=sys.stderr)
            return 1

        token = accounts.issue_link(pool, user[0])
        if token is None:
            minutes = int(accounts.TOKEN_TTL.total_seconds() // 60)
            # **Spending one does not free a slot.** The limit counts every
            # unexpired token, used or not, so clicking a link does not buy
            # another. Saying otherwise sends somebody off to click a link that
            # will not help.
            print(f"{args.email} already has {accounts.MOST_LIVE_LINKS} live links. "
                  f"They are counted until they expire, whether or not they have "
                  f"been used, so the wait is up to {minutes} minutes.",
                  file=sys.stderr)
            return 1

        print(f"{base_url(args.base_url)}/login/link?t={token}")
        print("Works once, for fifteen minutes. Do not paste it anywhere.",
              file=sys.stderr)
    finally:
        pool.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
