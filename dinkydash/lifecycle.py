"""Hosted access boundaries. All decisions use the database's aware clock."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .claude_client import GenerationError

FROZEN_BOARD_PERIOD = timedelta(days=30)
ENDED_MESSAGE = "Your trial or subscription has ended. Board updates are paused."


@dataclass(frozen=True)
class Access:
    lapsed_at: datetime | None
    now: datetime

    @property
    def ended(self):
        return self.lapsed_at is not None

    @property
    def show_last_board(self):
        return self.ended and self.now < self.lapsed_at + FROZEN_BOARD_PERIOD

    def require_live(self):
        if self.ended:
            raise GenerationError(ENDED_MESSAGE)


def access_for(pool, family_id):
    """Check the deadline even if the worker has not swept this family yet.

    An active paid account ignores its old trial deadline. The migration fills
    missing trial deadlines from account creation and requires one thereafter.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT CASE
                          WHEN status = 'lapsed' THEN lapsed_at
                          WHEN status = 'trialing' AND trial_ends_at <= now()
                              THEN trial_ends_at
                      END, now()
               FROM families WHERE id = %s""", (family_id,),
        )
        row = cur.fetchone()
    if row is None:
        from .pgstore import NoSuchFamily
        raise NoSuchFamily(f"No family {family_id}")
    return Access(*row)


def expire_trials(pool):
    """Persist ended trials once; a delayed or repeated sweep keeps the deadline."""
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """UPDATE families
               SET status = 'lapsed', lapsed_at = trial_ends_at, updated_at = now()
               WHERE status = 'trialing' AND trial_ends_at <= now()
               RETURNING id""",
        )
        return len(cur.fetchall())
