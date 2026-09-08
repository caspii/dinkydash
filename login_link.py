#!/usr/bin/env python3
"""Print a login link for an existing account without sending email.

Requires database access and uses the ordinary token limits. The printed URL
is a credential. Pass --base-url http://127.0.0.1:5173 for a local preview.
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from dinkydash import accounts, db
from web.urls import app_origin

load_dotenv()


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
            print(f"No account for {args.email}. To make one, post the address "
                  f"to /login and click the link it sends — that is what "
                  f"creates a family.", file=sys.stderr)
            return 1

        token = accounts.issue_link(pool, user[0])
        if token is None:
            minutes = int(accounts.TOKEN_TTL.total_seconds() // 60)
            print(f"{args.email} already has {accounts.MOST_LIVE_LINKS} live links. "
                  f"They are counted until they expire, whether or not they have "
                  f"been used, so the wait is up to {minutes} minutes.",
                  file=sys.stderr)
            return 1

        origin = app_origin(os.environ.get("DINKYDASH_APP_HOST", ""),
                            override=args.base_url)
        print(f"{origin}/login/link?t={token}")
        print("Works once, for fifteen minutes. Do not paste it anywhere.",
              file=sys.stderr)
    finally:
        pool.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
