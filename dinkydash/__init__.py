"""The DinkyDash generation engine.

Pure-ish: every function here takes the data it needs and returns data. No
module reads config.yaml, looks at the clock, or writes files — the caller
injects `today` and owns all I/O. That is what lets one code path serve a
Raspberry Pi cron job and, later, a multi-tenant scheduler, and it is what
makes any of this testable.
"""

__all__ = ["context", "calendars", "prompt", "claude_client", "generate", "config", "history"]
